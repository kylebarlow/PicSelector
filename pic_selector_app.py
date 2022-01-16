import os
import math
import calendar
import datetime
import pytz

import flask
from flask import request, jsonify
from flask_user import login_required, UserManager, roles_required, current_user

import numpy as np
import pandas as pd
from sqlalchemy.orm import deferred
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
@login_required
def home_page():
    df = pd.read_sql_query('''
        SELECT EXTRACT(YEAR FROM creation_time) as year, EXTRACT(MONTH FROM creation_time) as month, EXTRACT(DAY FROM creation_time) as day, creation_time, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height, SUM(votes.vote_value) AS sum_votes, media.id as mediaid
        from media
        JOIN thumbnail ON thumbnail.media_id=media.id
        LEFT JOIN votes on media.id = votes.media_id
        WHERE media_type = 0 AND EXTRACT(YEAR FROM creation_time) IS NOT NULL
        GROUP BY mediaid, thumbnail_key, thumbnail_width, thumbnail_height
    ''', db.engine)
    df = df.loc[~df['year'].isna()]
    df['randcol'] = np.random.random(size=df.shape[0])
    df['sum_votes'] = df['sum_votes'].fillna(0)
    df = df.sort_values(['year', 'sum_votes', 'randcol'], ascending=[True, False, True])
    df['year_str'] = df['year'].astype(int).astype(str)
    df_years = df.loc[(df['sum_votes'] >= 0) & (df['year'] >= 2006)].drop_duplicates('year')
    df_years['year_link'] = df_years['year'].apply(lambda year: flask.url_for('year_gallery', year=year))
    df_years = generate_signed_urls_helper(df_years)
    df_fav_years = df.loc[df['sum_votes'] > 0].drop_duplicates('year')
    df_fav_years['year_link'] = df_fav_years['year'].apply(lambda year: flask.url_for('fav_year_gallery', year=year))
    df_fav_years = generate_signed_urls_helper(df_fav_years)

    local_time = pytz.timezone('UTC').localize(datetime.datetime.utcnow()).astimezone(pytz.timezone('America/Los_Angeles'))
    df_day = df.loc[(df['sum_votes'] > 0) & (df['month'] == local_time.month) & (df['day'] == local_time.day) & (df['year'] < local_time.year)].drop_duplicates('year')
    df_day = generate_signed_urls_helper(df_day)
    df_day['display_time'] = df_day['creation_time'].apply(lambda x: x.strftime('%Y, %A'))    
    def suffix(d):
        return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

    def custom_strftime(format, t):
        return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))
    current_date_header_display = custom_strftime('%B {S}', local_time)

    return flask.render_template('home.html', all_year_df=df_years, fav_year_df=df_fav_years, df_day=df_day, len_df_day=len(df_day), current_date_header_display=current_date_header_display)


def generate_signed_urls_helper(df, s3_key_col = 'thumbnail_key', url_col='thumbnail_url'):
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
    df[url_col] = df[s3_key_col].apply(lambda s3_key:
        s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': config.s3_bucket_name,
                'Key': s3_key,
            },
            ExpiresIn=60*60,  # One hour in seconds
        )
    )
    return df


@login_required
@roles_required('Admin')
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
    return render_year(year, favs_only=False)


@app.route('/favs/<int:year>')
@login_required
def fav_year_gallery(year):
    return render_year(year, favs_only=True)

def render_year(year, favs_only=True):
    df = get_months_df(year, favs_only=favs_only)
    return flask.render_template('year.html', months_df=df)


def get_months_df(year, favs_only=True):
    df = pd.read_sql_query('''
        SELECT EXTRACT(MONTH FROM creation_time) as month, creation_time, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height, SUM(votes.vote_value) AS sum_votes, media.id as mediaid
        from media
        JOIN thumbnail ON thumbnail.media_id=media.id
        LEFT JOIN votes on media.id = votes.media_id
        WHERE media_type = 0 AND EXTRACT(MONTH FROM creation_time) IS NOT NULL
        AND creation_time >= '%d-01-01 00:00:00'
        AND creation_time <= '%d-12-31 23:59:59'
        GROUP BY mediaid, thumbnail_key, thumbnail_width, thumbnail_height
    ''' % (int(year), int(year)), db.engine)
    df = df.loc[~df['month'].isna()]
    df['randcol'] = np.random.random(size=df.shape[0])
    df['sum_votes'] = df['sum_votes'].fillna(0)
    df = df.sort_values(['month', 'sum_votes', 'randcol'], ascending=[True, False, True])
    df['month_str'] = df['month'].astype(int).apply(lambda x: calendar.month_name[x])
    if favs_only:
        month_route = 'fav_month_gallery'
        df = df.loc[df['sum_votes'] > 0]
    else:
        month_route = 'month_gallery'
    df = df.drop_duplicates('month')
    df['month_link'] = df['month'].apply(lambda month: flask.url_for(month_route, year=year, month=month))
    df = generate_signed_urls_helper(df)
    return df


@app.route('/robots.txt')
def robots():
    return 'User-agent: * Disallow: /'

@app.route('/gallery/<int:year>/<int:month>')
@roles_required('Admin')
@login_required
def month_gallery(year, month):
    return month_gallery_page(year, month, 1)


@app.route('/favs/<int:year>/<int:month>')
@login_required
def fav_month_gallery(year, month):
    return fav_month_gallery_page(year, month, 1)


@app.route('/gallery/<int:year>/<int:month>/<int:page>')
@roles_required('Admin')
@login_required
def month_gallery_page(year, month, page):
    return render_month(year, month, page, favs_only=False)


@app.route('/favs/<int:year>/<int:month>/<int:page>')
@login_required
def fav_month_gallery_page(year, month, page):
    return render_month(year, month, page, favs_only=True)


def get_days_df(year, month, favs_only=True):
    this_month_start = datetime.datetime(year, month, 1)
    next_month_start = (this_month_start + datetime.timedelta(days=calendar.monthrange(year, month)[1] + 5)).replace(day=1)
    current_user_id = current_user.id

    df = pd.read_sql_query(
        '''
        SELECT media.creation_time, media.media_type, media.height, media.width, media.s3_key, thumbnail.key as thumbnail_key, thumbnail.width as thumbnail_width, thumbnail.height as thumbnail_height, votes.vote_value, media.id as mediaid, q2.sum_all_votes, votes.user_id as votes_user_id
        from media
        JOIN thumbnail ON thumbnail.media_id=media.id
        LEFT JOIN votes on media.id = votes.media_id
        LEFT JOIN (
            SELECT media.id AS q2_mediaid, SUM(votes.vote_value) AS sum_all_votes
            from media
            LEFT JOIN votes on media.id = votes.media_id
            AND creation_time >= %s
            AND creation_time < %s
            GROUP BY q2_mediaid, creation_time
        ) q2 ON q2.q2_mediaid=media.id
        WHERE creation_time >= %s
        AND creation_time < %s
        ORDER BY creation_time ASC
        ''',
        db.engine,
        params=(
            this_month_start, next_month_start, this_month_start, next_month_start,
        ),
    )
    df['vote_matches_my_user_id'] = 0
    df.loc[df['votes_user_id'] == current_user_id, 'vote_matches_my_user_id'] = 1
    df = df.sort_values(['creation_time', 'vote_matches_my_user_id'], ascending=[True, False])
    df = df.drop_duplicates('mediaid')
    df['vote_value'] = df['vote_value'].fillna(0)
    df.loc[(df['vote_matches_my_user_id'] == 0) & (df['vote_value'] != 0), 'vote_value'] = 0
    df['sum_all_votes'] = df['sum_all_votes'].fillna(0)
    if favs_only:
        df = df.loc[df['sum_all_votes'] > 0]

    return df


def render_month(year, month, page, column_width=400, items_per_page=50, favs_only=True):
    if favs_only:
        month_route = 'fav_month_gallery_page'
        items_per_page = items_per_page * 2
    else:
        month_route = 'month_gallery_page'

    this_month_start = datetime.datetime(year, month, 1)
    next_month_start = (this_month_start + datetime.timedelta(days=calendar.monthrange(year, month)[1] + 5)).replace(day=1)
    prev_month_start = (this_month_start - datetime.timedelta(days=5)).replace(day=1)
    media = get_days_df(year, month, favs_only=favs_only)

    thumbnails = []
    photoswipe_i = 0
    last_photo_index = media.loc[ media['media_type']==0 ].iloc[-1].name
    
    max_page = math.ceil(len(media)/items_per_page)
    if len(media) > items_per_page:
        page_header_text = ' - Page %d of %d' % (page, max_page)
    else:
        page_header_text = ''
    
    next_page_url = ''
    if page > 1:
        next_page_url += '<a href="%s">Previous page</a> ' % (flask.url_for(month_route, year=year, month=month, page=page - 1),)
    for page_i in range(1, max_page+1):
        if page_i == page:
            next_page_url += '<b>%d</b> ' % (page,)
        else:
            next_page_url += '<a href="%s">%d</a> ' % (flask.url_for(month_route, year=year, month=month, page=page_i), page_i)
    if len(media) > items_per_page and page < max_page:
        next_page_url += '<a href="%s">Next page</a>' % flask.url_for(month_route, year=year, month=month, page=page + 1)
    else:
        next_page_url = next_page_url[:-1]

    starting_i = (page - 1) * items_per_page
    ending_i = page * items_per_page + 1

    media = generate_signed_urls_helper(media, s3_key_col='thumbnail_key', url_col='url')
    media = generate_signed_urls_helper(media, s3_key_col='s3_key', url_col='original_url')
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
            'url': row['url'],
            'original_url': row['original_url'],
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
    
    # TODO: don't link to non-existent month pages (pages with no content)

    if next_month_start > datetime.datetime.now():
        next_month_url = 'None'
    else:
        next_month_url = flask.url_for(month_route, year=next_month_start.year, month=next_month_start.month, page=1)

    return flask.render_template(
        'month_gallery_simple.html',
        thumbnails=thumbnails,
        page_header_text=page_header_text,
        year=year, month=month,
        next_page_url=next_page_url,
        next_month_url=next_month_url,
        prev_month_url=flask.url_for(month_route, year=prev_month_start.year, month=prev_month_start.month, page=1),
    )
