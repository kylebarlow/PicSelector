import os
import math
import calendar
import datetime

import flask
from flask import request, jsonify
from flask_user import login_required, UserManager, roles_required, current_user


import pandas as pd
# import psycopg2

import config

import boto3
# import botocore
import botocore.exceptions

from sql_alchemy_classes import *
import sqlalchemy

# Create all database tables
# db.create_all()

# Setup Flask-User and specify the User data-model
user_manager = UserManager(app, db, User)

# The Home page is accessible to anyone
@app.route('/')
def home_page():
    years = pd.read_sql_query('''
        SELECT DISTINCT EXTRACT(YEAR FROM creation_time) as year
        FROM media
        WHERE creation_time >= '2000-01-01 01:00:00'
        ORDER BY year
    ''', db.engine)['year'].values
    years = [str(int(year)) for year in years]
    year_links = [flask.url_for('year_gallery', year=year) for year in years]
    year_tuples = [(x, y) for x, y in zip(years, year_links)]
    return flask.render_template('home.html', year_tuples=year_tuples)

@login_required
@app.route('/_vote', methods = ['POST'])
def vote():
    media_id = request.form.get('mediaid', -1, type=int)
    vote_value = request.form.get('votevalue', None, type=int)
    assert(media_id >= 0)

    current_vote = pd.read_sql_query(
        '''
        SELECT votes.vote_value, media.id as mediaid
        from media
        LEFT JOIN votes on media.id = votes.media_id
        WHERE media.id=%s
        AND (votes.user_id=%s OR votes.user_id IS NULL)        ''',
        db.engine,
        params=(
            media_id, current_user.id,
        ),
    )
    assert(len(current_vote) == 1)
    current_vote = current_vote.iloc[0]['vote_value']

    if vote_value == 1:
        if current_vote == 1:
            new_vote_value = 0
        else:
            new_vote_value = 1
    elif vote_value == -1:
        if current_vote == -1:
            new_vote_value = 0
        else:
            new_vote_value = -1
    else:
        raise Exception()

    if pd.isna(current_vote):
        query = "INSERT INTO votes (vote_value, user_id, media_id) VALUES (%d, %d, %d)" % (int(new_vote_value), current_user.id, int(media_id))
    else:    
        query = "UPDATE votes SET vote_value = %d WHERE media_id = %d AND user_id = %d" % (int(new_vote_value), int(media_id), current_user.id)
    db.engine.execute(sqlalchemy.text(query))
    return jsonify(votevalue=new_vote_value, mediaid=media_id)

@app.route('/gallery/<int:year>')
@roles_required('Admin')
@login_required
def year_gallery(year):
    months = pd.read_sql_query('''
        SELECT DISTINCT EXTRACT(MONTH FROM creation_time) as month
        FROM media
        WHERE creation_time >= '%d-01-01 00:00:00'
        AND creation_time <= '%d-12-31 23:59:59'
        ORDER BY month
    ''' % (int(year), int(year)), db.engine)['month'].values
    months = [str(int(month)) for month in months]
    month_links = [flask.url_for('month_gallery', year=year, month=month) for month in months]
    month_tuples = [(x, y) for x, y in zip(months, month_links)]
    return flask.render_template('year.html', month_tuples=month_tuples)

@app.route('/robots.txt')
def robots():
    return 'User-agent: * Disallow: /'

@app.route('/gallery/<int:year>/<int:month>')
@roles_required('Admin')
@login_required
def month_gallery(year, month):
    return month_gallery_page(year, month, 1)

@app.route('/gallery/<int:year>/<int:month>/<int:page>')
@roles_required('Admin')
@login_required
def month_gallery_page(year, month, page, column_width=400, items_per_page=50):
    this_month_start = datetime.datetime(year, month, 1)
    next_month_start = (this_month_start + datetime.timedelta(days=calendar.monthrange(year, month)[1] + 5)).replace(day=1)
    prev_month_start = (this_month_start - datetime.timedelta(days=5)).replace(day=1)
    current_user_id = current_user.id

    media = pd.read_sql_query(
        '''
        SELECT media.creation_time, media.media_type, media.height, media.width, media.s3_key, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height, votes.vote_value, media.id as mediaid
        from media
        JOIN thumbnail ON thumbnail.media_id=media.id
        LEFT JOIN votes on media.id = votes.media_id
        WHERE creation_time >= %s
        AND creation_time < %s
        AND (votes.user_id=%s OR votes.user_id IS NULL)
        ORDER BY creation_time ASC
        ''',
        db.engine,
        params=(
            this_month_start, next_month_start, current_user_id,
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
            'vote_value': row['vote_value'],
            'mediaid': row['mediaid'],
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
