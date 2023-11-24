FROM postgres:15
ENV POSTGRES_DB my_database
COPY pics_schema.sql /docker-entrypoint-initdb.d/
