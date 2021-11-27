import os
import math
import calendar
import datetime

import flask
from flask import Flask
import flask_login

import pandas as pd
# import psycopg2

import settings_env
from picture_functions import DatabaseConnector
import config

import boto3
# import botocore
import botocore.exceptions

app = Flask(__name__)
app.secret_key = settings_env.secret_key
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/gallery/<int:year>/<int:month>')
def month_gallery(year, month):
    return month_gallery_page(year, month, 1)

@app.route('/gallery/<int:year>/<int:month>/<int:page>')
def month_gallery_page(year, month, page, column_width=400, items_per_page=50):
    this_month_start = datetime.datetime(year, month, 1)
    next_month_start = (this_month_start + datetime.timedelta(days=calendar.monthrange(year, month)[1] + 5)).replace(day=1)
    prev_month_start = (this_month_start - datetime.timedelta(days=5)).replace(day=1)

    with DatabaseConnector() as conn:
        media = pd.read_sql_query(
            '''
            SELECT media.creation_time, media.media_type, media.height, media.width, media.s3_key, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height from media
            JOIN thumbnail ON thumbnail.media_id=media.id
            WHERE creation_time >= %s
            AND creation_time < %s
            ORDER BY creation_time ASC
            ''',
            conn,
            params=(
                this_month_start, next_month_start,
            ),
        )

    session = boto3.session.Session(
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        profile_name=None,
    )
    s3_client = session.client(
        "s3",
        config=config.boto_config,
        endpoint_url=config.s3_endpoint_url,
    )

    thumbnails = []
    photoswipe_i = 0
    last_photo_index = media.loc[ media['media_type']==0 ].iloc[-1].name
    
    if len(media) > items_per_page:
        page_header_text = ' - Page %d of %d' % (page, math.ceil(len(media)/items_per_page))
    else:
        page_header_text = ''
    if len(media) > items_per_page and page < math.ceil(len(media)/items_per_page):
        next_page_url = flask.url_for('month_gallery_page', year=year, month=month, page=page + 1)
    else:
        next_page_url = ''

    starting_i = (page - 1) * items_per_page
    ending_i = page * items_per_page + 1
    for index, row in media.iloc[starting_i : ending_i].iterrows():
        # width = min(column_width, row['width'])
        # if width == row['width']:
        #     height = row['height']
        # else:
        #     height = int( (column_width / row['width']) * row['height'] )
        if index == last_photo_index:
            comma = ''
        else:
            comma = ','

        d = {
            'url': s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': config.s3_bucket_name,
                    'Key': row['thumbnail_key'],
                },
                ExpiresIn=60*60,  # One hour in seconds
            ),
            'original_url': s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': config.s3_bucket_name,
                    'Key': row['s3_key'],
                },
                ExpiresIn=60*60,  # One hour in seconds
            ),
            'width': row['thumbnail_width'],
            'height': row['thumbnail_height'],
            'original_width': row['width'],
            'original_height': row['height'],
            'media_type': row['media_type'],
            'formatted_date': row['creation_time'].strftime("%b %d, %I:%M:%S %p"),
            'comma': comma,
            'photoswipe_index': photoswipe_i,
        }
        if row['media_type'] == 1:
            fname, extension = os.path.splitext(row['s3_key'])
            d['video_type'] = extension[1:]
            # d['html'] = '''<video width="%d" height="%d" controls autoplay muted><source src="%s" type="video/mp4"></video>''' % (d['original_height'], d['original_height'], d['original_url'])
        else:
            photoswipe_i += 1
            d['video_type'] = ''
        thumbnails.append(d)
    
    if next_month_start > datetime.datetime.now():
        next_month_url = 'None'
    else:
        next_month_url = flask.url_for('month_gallery', year=next_month_start.year, month=next_month_start.month)

    return flask.render_template(
        'month_gallery_simple.html',
        thumbnails=thumbnails,
        page_header_text=page_header_text,
        year=year, month=month,
        next_page_url=next_page_url,
        next_month_url=next_month_url,
        prev_month_url=flask.url_for('month_gallery', year=prev_month_start.year, month=prev_month_start.month),
    )


@login_manager.user_loader
def load_user(user_id):
    return flask.User.get(user_id)

