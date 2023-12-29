#!/bin/bash

cd /webwork
uwsgi --ini pic_selector.ini &
nginx -g "daemon off;"
