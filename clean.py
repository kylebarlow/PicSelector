import sys
import os
import pandas as pd
from picture_functions import DatabaseConnector
from tqdm import tqdm
import psycopg2
import psycopg2.extras

root_dir = sys.argv[1]

with DatabaseConnector() as conn:
    df = pd.read_sql_query(
        '''
        SELECT media.id AS media_id, media.s3_key AS media_s3_key,
        thumbnail.id AS thumbnail_id, thumbnail.key AS thumbnail_s3_key,
        images.id AS images_id, videos.id AS videos_id
        FROM media
LEFT JOIN thumbnail ON thumbnail.media_id=media.id
LEFT JOIN images ON images.id=media.id
LEFT JOIN videos on media.id = videos.id
        ''',
        conn,
    )
    keys = pd.read_sql_query(
        '''
        SELECT * FROM keys
        ''',
        conn,
    )

print('Retrieved %d joined rows' % len(df))
print('Retrieved %d keys rows' % len(keys))

missing_keys = []
missing_keys_media_ids = []
for i in tqdm(range(len(keys))):
    row = keys.iloc[i]
    if not os.path.isfile(os.path.join(root_dir, row['key'])):
        missing_keys.append(int(row['key_id']))
        missing_keys_media_ids.append(int(row['media_id']))
print('%d keys are not present locally' % len(missing_keys))
if len(missing_keys) > 1:
    print('Deleting keys with missing filesystem files')
    with DatabaseConnector() as conn:
        cursor = conn.cursor()
        delete_query = """DELETE FROM keys
                        WHERE keys.key_id IN %s;"""

        cursor.execute(
           delete_query, (tuple(missing_keys),),
        )
        conn.commit()

media_rows_with_no_filesystem_key = set(df['media_id'].values) - (set(keys['media_id'].values) - set(missing_keys_media_ids))
print('%d media rows have no filesytem key' % len(media_rows_with_no_filesystem_key))
if len(media_rows_with_no_filesystem_key) > 0:
    files_actually_present_media_id = []
    files_actually_present_fs_key = []
    for media_id in media_rows_with_no_filesystem_key:
        row = df.loc[df['media_id'] == media_id]
        assert(len(row) == 1)
        row = row.iloc[0]
        if os.path.isfile(os.path.join(root_dir, row['media_s3_key'])):
            files_actually_present_media_id.append(int(media_id))
            files_actually_present_fs_key.append(row['media_s3_key'])
    print('%d have files, but no DB entry. Adding.' % len(files_actually_present_media_id))
    with DatabaseConnector() as conn:
        cursor = conn.cursor()
        psycopg2.extras.execute_values(
            cursor,
            '''INSERT INTO keys (media_id, key)
            VALUES %s
            ;''',
            tuple(zip(files_actually_present_media_id, files_actually_present_fs_key)),
            template=None,
        )
        conn.commit()

print('%d rows have no thumbnails' % len(df.loc[df['thumbnail_id'].isna()]))