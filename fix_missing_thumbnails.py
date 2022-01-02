from enum import _auto_null
import os
import datetime
import sys
import io
import time
import hashlib
import multiprocessing
import tempfile
from pprint import pprint

import filetype
import watchdog
import watchdog.events
import watchdog.observers
import PIL
from PIL.ExifTags import TAGS, GPSTAGS
import imagehash
# import face_recognition
from dateutil import parser as dateutil_parser
import ffmpeg
import numpy as np
import pandas as pd

from sshtunnel import SSHTunnelForwarder
import psycopg2
import psycopg2.extras
import config

import boto3
import botocore
import botocore.exceptions

from picture_functions import DatabaseConnector, process_image

from tqdm import tqdm

with DatabaseConnector() as conn:
    media = pd.read_sql_query(
        '''
        SELECT media.s3_key, thumbnail.key as thumbnail_key, media.id AS media_id, thumbnail.id AS thumbnail_id
        FROM media
JOIN thumbnail ON thumbnail.media_id=media.id
WHERE media.media_type=0
        ''',
        conn,
    )

session = boto3.session.Session(
    aws_access_key_id=config.access_key,
    aws_secret_access_key=config.secret_key,
)
s3_client = session.client(
    "s3",
    config=config.boto_config,
    endpoint_url=config.s3_endpoint_url,
)

print('Retrieved %d total rows, %d unique media IDs' % (len(media), media['media_id'].nunique()))

assert(len(media) == media['media_id'].nunique())

all_s3_keys_cache = '/tmp/all_s3_keys'
all_s3_keys = []
if os.path.isfile(all_s3_keys_cache):
    with open(all_s3_keys_cache, 'r') as f:
        for line in f:
            all_s3_keys_cache.append(line)
else:
    kwargs = {'Bucket': config.s3_bucket_name}
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp['Contents']:
            all_s3_keys.append(obj['Key'])

        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break
    with open(all_s3_keys_cache, 'w') as f:
        for k in all_s3_keys:
            f.write(k+'\n')

print('%d total keys in S3' % len(all_s3_keys))

s3_keys_df = pd.Series(all_s3_keys, name='thumbnail_key').to_frame()
s3_keys_df = s3_keys_df.reset_index().rename(columns={'index': 's3_key_index'})
media = media.merge(s3_keys_df, on='thumbnail_key', how='left')

print('%d thumbnails missing' % len(media.loc[media['s3_key_index'].isna()]))

sys.exit()

new_thumb_values = []
keys_to_remove = []
failed_image_paths = []
for index, row in tqdm(list(media.iterrows())):
    ipath = os.path.join(root_dir, row['path_key'])
    if not os.path.isfile(ipath):
        print('Missing file:', ipath)
        continue

    try:
        metadata = process_image(ipath, run_hashing=False)
    except Exception:
        failed_image_paths.append(ipath)
        continue
    metadata['fpath_relative'] = os.path.relpath(ipath, root_dir)

    if 'thumbnail' in metadata and 'thumbnail_path' in metadata['thumbnail'] and os.path.isfile(metadata['thumbnail']['thumbnail_path']):
        fname, extension = os.path.splitext(metadata['fpath_relative'])
        thumb_key = fname + '-%dw_%dh' % (metadata['thumbnail']['thumbnail_width'], metadata['thumbnail']['thumbnail_height']) + extension
        try:
            response = s3_client.upload_file(metadata['thumbnail']['thumbnail_path'], config.s3_bucket_name, thumb_key)
            os.remove(metadata['thumbnail']['thumbnail_path'])
            new_thumb_values.append((row['media_id'], thumb_key, int(metadata['thumbnail']['thumbnail_height']), int(metadata['thumbnail']['thumbnail_width']), int(metadata['thumbnail']['thumbnail_size'])))
            if row['thumbnail_key'] != thumb_key:
                keys_to_remove.append(row['thumbnail_key'])
        except botocore.exceptions.ClientError as e:
            print(e)
            continue

if len(failed_image_paths) > 0:
    print('Failed image paths:', failed_image_paths)
    with open('failed_image_paths.txt', 'w') as f:
        for failed_image_path in failed_image_paths:
            f.write(failed_image_path+'\n')

pd.DataFrame(new_thumb_values, columns=['media_id', 'key', 'height', 'width', 'filesize']).to_csv('new_thumb.csv', index=False)

df = pd.read_csv('new_thumb.csv')
new_thumb_values = []
for index, row in tqdm(list(df.iterrows())):
    new_thumb_values.append(tuple(row.values))
print('%d thumbnail rows to update' % len(new_thumb_values))

with DatabaseConnector() as conn:
    cursor = conn.cursor()
    update_query = """UPDATE thumbnail AS t
                    SET key = e.key,
                    height = e.height,
                    width = e.width,
                    file_size = e.file_size
                    FROM (VALUES %s) AS e(media_id, key, height, width, file_size)
                    WHERE e.media_id = t.media_id;"""

    psycopg2.extras.execute_values(
        cursor, update_query, new_thumb_values, template=None, page_size=100,
    )
    conn.commit()

print('%d thumbnail keys to remove' % len(keys_to_remove))
for key in keys_to_remove:
    s3_client.delete_object(Bucket=config.s3_bucket_name, Key=key)
