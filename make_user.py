import flask
from flask import Flask, request, render_template_string
from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_user import login_required, UserManager, UserMixin


import pandas as pd
# import psycopg2

from picture_functions import DatabaseConnector
import config

import boto3
# import botocore
import botocore.exceptions

from sql_alchemy_classes import *

# Create all database tables
# db.create_all()

# Setup Flask-User and specify the User data-model
user_manager = UserManager(app, db, User)

# admin_role = Role(name='Admin')
# db.session.add(admin_role)
# db.session.commit()

# guest_role = Role(name='family')
# db.session.add(guest_role)
# db.session.commit()

# user = User()
# user.username = 'kyle'
# user.first_name = 'Kyle'
# user.last_name = 'Barlow'
# user.email = 'kylebarlow@gmail.com'
# user.password = user_manager.hash_password('')

# user.roles = [admin_role]

# db.session.add(user)
# db.session.commit()

# user = User()
# user.username = 'malia'
# user.first_name = 'Malia'
# user.last_name = 'McPherson'
# user.email = 'maliamcpherson@gmail.com'
# user.password = user_manager.hash_password('')

# admin_role = Role.query.filter_by(id=1).first()
# user.roles = [admin_role]

# db.session.add(user)
# db.session.commit()

# user = User()
# user.username = 'family'
# user.first_name = 'Family'
# user.last_name = 'User'
# user.email = 'family@barlo.ws'
# user.password = user_manager.hash_password('ohana')

# guest_role = Role.query.filter_by(id=2).first()
# user.roles = [guest_role]

# db.session.add(user)
# db.session.commit()