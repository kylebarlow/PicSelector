from enum import _auto_null
import os
import datetime
import sys
import io
import time
import hashlib
import multiprocessing
import shutil
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
        SELECT media.s3_key AS media_key, thumbnail.key as thumbnail_key, media.id AS media_id, thumbnail.id AS thumbnail_id, thumbnail.height as thumbnail_height, thumbnail.width as thumbnail_width
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
            all_s3_keys.append(line.strip())
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
media_keys_df = s3_keys_df.copy().rename(columns={'thumbnail_key': 'media_key'})
s3_keys_df = s3_keys_df.reset_index().rename(columns={'index': 's3_key_index'})
media_keys_df = media_keys_df.reset_index().rename(columns={'index': 'media_key_index'})
media = media.merge(s3_keys_df, on='thumbnail_key', how='left')
media = media.merge(media_keys_df, on='media_key', how='left')

print('%d thumbnails missing' % len(media.loc[media['s3_key_index'].isna()]))
print('%d thumbnails missing also have missing media keys' % len(media.loc[media['s3_key_index'].isna() & media['media_key_index'].isna()]))
try:
    assert(len(media.loc[media['s3_key_index'].isna() & media['media_key_index'].isna()]) == 0)
except AssertionError:
    print(media.loc[media['s3_key_index'].isna() & media['media_key_index'].isna()])
    raise
if len(media.loc[media['s3_key_index'].isna()]) == 0:
    sys.exit()


def generate_missing_thumbnail(row):
    global my_s3_client
    extension = row['media_key'].split('.')[-1]
    with tempfile.TemporaryDirectory(prefix='thumb_') as tmp:
        temp_path = os.path.join(tmp, 'image.' + extension)
        my_s3_client.download_file(config.s3_bucket_name, row['media_key'], temp_path)

        max_size = (row['thumbnail_width'], row['thumbnail_height'])
        with open(temp_path, 'rb') as f:
            fdata = f.read()
        image = PIL.Image.open(io.BytesIO(fdata))
        thumbnail = PIL.ImageOps.exif_transpose(image).copy()
        thumbnail.thumbnail(max_size)
        thumbnail_path = os.path.join(tmp, 'thumbnail.jpg')
        with open(thumbnail_path, 'wb') as f:
            try:
                thumbnail.save(f, format='JPEG')
            except OSError:
                thumbnail.convert('RGB').save(f, format='JPEG')
        my_s3_client.upload_file(thumbnail_path, config.s3_bucket_name, row['thumbnail_key'])


def init_worker():
    os.nice(10)
    my_session = boto3.session.Session(
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
    )
    global my_s3_client
    my_s3_client = my_session.client(
        "s3",
        config=config.boto_config,
        endpoint_url=config.s3_endpoint_url,
    )


reporter = tqdm(total=len(media.loc[media['s3_key_index'].isna()]))


def callback_helper(t):
    reporter.update()


pool = multiprocessing.Pool(processes=8, initializer=init_worker)
for index, row in media.loc[media['s3_key_index'].isna()].iterrows():
    pool.apply_async(generate_missing_thumbnail, args=(row,), callback=callback_helper)

pool.close()
pool.join()
reporter.close()
