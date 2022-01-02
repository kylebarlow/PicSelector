import sys
import shutil
import os
import pandas as pd
from picture_functions import DatabaseConnector, process_image
from tqdm import tqdm
import psycopg2
import psycopg2.extras
import random

with DatabaseConnector() as conn:
    df = pd.read_sql_query(
        '''
        SELECT media.id AS media_id, media.s3_key AS media_s3_key,
        thumbnail.id AS thumbnail_id, thumbnail.key AS thumbnail_s3_key,
        images.id AS images_id,
        media.sha256_hash,
        images.average_hash1, images.average_hash2, images.average_hash3, images.average_hash4
        FROM media
LEFT JOIN thumbnail ON thumbnail.media_id=media.id
LEFT JOIN images ON images.id=media.id
        ''',
        conn,
    )
    keys = pd.read_sql_query(
        '''
        SELECT * FROM keys
        ''',
        conn,
    )
    votes = pd.read_sql_query('SELECT * from votes', conn)

df['s3_key_fname'] = df['media_s3_key'].str.split('/').str[-1].str.strip()
df['average_hash'] = df['average_hash1'] + df['average_hash2'] + df['average_hash3'] + df['average_hash4']

print('Retrieved %d joined rows' % len(df))
print('Retrieved %d keys rows' % len(keys))

root_dir = '/media/bespin/kyle/backups/pictures_other/sigal/_build'

pic_extensions = ['.jpg', '.png', '.gif', '.JPG']
all_extensions = set()
pic_files = []
for root, dirs, files in os.walk(root_dir, topdown=False):
    for name in files:
        fpath = os.path.join(root, name)
        if 'thumbnails' in fpath or 'static' in fpath:
            continue
        all_extensions.add(name.split('.')[-1])
        for pic_extension in pic_extensions:
            if name.endswith(pic_extension):
                pic_files.append(fpath)
                continue
print('Found file extensions:', all_extensions)
print('Found %d picture files' % len(pic_files))
random.shuffle(pic_files)
# print(pic_files[:50])

print(df['s3_key_fname'].head())

mapped_db_images = []
unmapped_images = []
for pic_file in tqdm(pic_files):
    fname = pic_file.split('/')[-1].strip()
    mapped_df = df.loc[df['s3_key_fname'] == fname]
    # print(pic_file, fname, len(mapped_df))
    if len(mapped_df) == 1:
        mapped_db_images.append(mapped_df)
    elif len(mapped_df) == 0:
        unmapped_images.append(pic_file)
    elif len(mapped_df) > 1:
        image_data = process_image(pic_file)
        mapped_df = mapped_df.loc[mapped_df['average_hash'] == image_data['image_only']['hashes']['average']]
        if len(mapped_df) == 1:
            mapped_db_images.append(mapped_df)
        # else:
        #     print('Ambiguous:', pic_file)
        #     print(mapped_df)
        #     image_data = process_image(pic_file)
print(unmapped_images)
print('%d unambiguous mappings to s3 key fname' % len(mapped_db_images))
print('%d images unmapped' % (len(unmapped_images)))
print('%d ambigously mapped' % (len(pic_files) - len(unmapped_images) - len(mapped_db_images)))

# for unmapped_image in unmapped_images:
#     old_relpath = os.path.relpath(unmapped_image, root_dir)
#     new_path = os.path.join('/media/bespin/kyle/pictures/misc/sigal', old_relpath)
#     if not os.path.isdir(os.path.dirname(new_path)):
#         os.makedirs(os.path.dirname(new_path))
#     shutil.copy(unmapped_image, new_path)

mapped_db_images = pd.concat(mapped_db_images, sort=False, ignore_index=True)
already_voted = set()
with DatabaseConnector() as conn:
    cursor = conn.cursor()
    for index, row in mapped_db_images.iterrows():
        if len(votes.loc[(votes['media_id'] == row['media_id']) & (votes['user_id'] == 1)]) > 0:
            continue
        if row['media_id'] in already_voted:
            continue
        already_voted.add(row['media_id'])
        cursor.execute(
            '''INSERT INTO votes (user_id, media_id, vote_value)
            VALUES(%s, %s, %s)
            ;''',
            (
                1, row['media_id'], 1
            ),
        )
        conn.commit()
        if index % 100 == 0:
            print(index)
