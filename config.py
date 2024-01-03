from botocore.config import Config

from flask import Flask

app = Flask(__name__)
app.config.from_prefixed_env()

postgres_over_ssh = False
database_name = app.config["POSTGRES_DB"]
postgres_user = app.config["POSTGRES_USER"]
postgres_pass = app.config["POSTGRES_PASSWORD"]
postgres_pass_quoted = app.config["POSTGRES_PASSWORD"]
postgres_host = app.config['POSTGRES_HOST']
flask_database_name = app.config["POSTGRES_DB"]
secret_key = app.config["S3_SECRET_KEY"]
access_key = app.config["S3_ACCESS_KEY"]
s3_endpoint_url = app.config["S3_ENDPOINT_URL"]
s3_bucket_name = app.config["S3_BUCKET_NAME"]
boto_config = Config(
    region_name=None,
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)

flask_settings = dict(
    SECRET_KEY=app.config["SECRET_KEY"],

    # Flask-SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://%s:%s@%s:5432/%s' % (postgres_user, postgres_pass_quoted, postgres_host, flask_database_name),
    SQLALCHEMY_TRACK_MODIFICATIONS = False,    # Avoids SQLAlchemy warning

    # Flask-User settings
    USER_APP_NAME = app.config["USER_APP_NAME"],      # Shown in and email templates and page footers
    USER_ENABLE_EMAIL = False,      # Disable email authentication
    USER_ENABLE_USERNAME = True,    # Enable username authentication
    USER_REQUIRE_RETYPE_PASSWORD = False,    # Simplify register form
    USER_ENABLE_REGISTER = False,
)
