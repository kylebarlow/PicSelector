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

from tqdm import tqdm

from picture_functions import DatabaseConnector, process_image

root_dir = sys.argv[1]

# with DatabaseConnector() as conn:
#     media = pd.read_sql_query(
#         '''
#         SELECT media.creation_time, media.media_type, media.height, media.width, media.s3_key, thumbnail.key as thumbnail_key, media.id AS media_id,
#        keys.key AS path_key,
#        thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height from media
# JOIN thumbnail ON thumbnail.media_id=media.id
# JOIN keys on media.id = keys.media_id
# WHERE media.media_type=0
#         ''',
#         conn,
#     )

# print('Retrieved %d rows' % len(media))

# new_thumb_values = []
# failed_image_paths = []
# for index, row in tqdm(list(media.iterrows())):
#     ipath = os.path.join(root_dir, row['path_key'])
#     if not os.path.isfile(ipath):
#         print('Missing file:', ipath)
#         continue

#     try:
#         metadata = process_image(ipath, run_hashing=False)
#     except Exception:
#         failed_image_paths.append(ipath)
#         continue
#     metadata['fpath_relative'] = os.path.relpath(ipath, root_dir)

#     if 'thumbnail' in metadata and 'thumbnail_path' in metadata['thumbnail'] and os.path.isfile(metadata['thumbnail']['thumbnail_path']):
#         fname, extension = os.path.splitext(metadata['fpath_relative'])
#         thumb_key = fname + '-%dw_%dh' % (metadata['thumbnail']['thumbnail_width'], metadata['thumbnail']['thumbnail_height']) + extension
        
#         os.remove(metadata['thumbnail']['thumbnail_path'])
#         new_thumb_values.append((row['media_id'], int(metadata['height']), int(metadata['width'])))

# if len(failed_image_paths) > 0:
#     print('Failed image paths:', failed_image_paths)
#     with open('failed_image_paths_dim.txt', 'w') as f:
#         for failed_image_path in failed_image_paths:
#             f.write(failed_image_path+'\n')

# pd.DataFrame(new_thumb_values, columns=['media_id', 'height', 'width']).to_csv('regen_dim.csv', index=False)

df = pd.read_csv('regen_dim.csv')
new_thumb_values = []
for index, row in df.iterrows():
    new_thumb_values.append(tuple([int(x) for x in row.values]))
print('%d thumbnail rows to update' % len(new_thumb_values))

with DatabaseConnector() as conn:
    cursor = conn.cursor()
    update_query = """UPDATE media AS m
                    SET height = e.height,
                    width = e.width
                    FROM (VALUES %s) AS e(id, height, width) 
                    WHERE e.id = m.id;"""

    psycopg2.extras.execute_values(
        cursor, update_query, new_thumb_values, template=None, page_size=100,
    )
    conn.commit()
