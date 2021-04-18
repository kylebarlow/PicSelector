import datetime

import flask
from flask import Flask
import flask_login

import pandas as pd
import psycopg2

import settings_env
from picture_functions import DatabaseConnector
import config

import boto3
import botocore
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
    this_month_start = datetime.datetime(year, month, 1)
    next_month_start = (this_month_start + datetime.timedelta(days=32)).replace(day=1)
    prev_month_start = (this_month_start - datetime.timedelta(days=5)).replace(day=1)

    with DatabaseConnector() as conn:
        media = pd.read_sql_query(
            '''
            SELECT media.creation_time, media.media_type, media.height, media.width, media.s3_key, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height from media
            JOIN thumbnail ON thumbnail.media_id=media.id
            WHERE creation_time >= %s
            AND creation_time <= %s
            ORDER BY creation_time
            ''',
            conn,
            params=(
                this_month_start, next_month_start,
            ),
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

    thumbnails = []
    for index, row in media.iterrows():
        thumbnails.append(
            {
                'url': s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={
                        'Bucket': config.s3_bucket_name,
                        'Key': row['thumbnail_key'],
                    },
                    ExpiresIn=60*60,  # One hour in seconds
                ),
            }
        )
    
    return flask.render_template(
        'month_gallery.html',
        thumbnails=thumbnails,
        next_month_url=flask.url_for('month_gallery', year=prev_month_start.year, month=prev_month_start.month)
    )


@login_manager.user_loader
def load_user(user_id):
    return flask.User.get(user_id)

