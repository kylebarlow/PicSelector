import sqlite3

import flask
from flask import Flask
import flask_login

import settings_env

app = Flask(__name__)
app.secret_key = settings_env.secret_key
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

DATABASE = 'db.sql3'

def get_db():
    db = getattr(flask.g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def hello_world():
        return 'Hello, World!'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

