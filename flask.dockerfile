# syntax=docker/dockerfile:1

FROM ubuntu:22.04 

RUN apt update
RUN apt install -y ffmpeg python3-pip

WORKDIR /python_docker

COPY library/Flask_User-1.0.2.3-py2.py3-none-any.whl /python_docker
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

RUN apt install -y nginx

WORKDIR /webwork
COPY pic_selector_app.py .
COPY wsgi.py .
COPY pic_selector.ini .
COPY system_config/pic_selector.service /etc/systemd/system/pic_selector.service
COPY system_config/pic_selector.site /etc/nginx/sites-available/pic_selector

RUN ln -s /etc/nginx/sites-available/pic_selector /etc/nginx/sites-enabled/pic_selector

# CMD [ "python3", "-m" , "flask", "--app", "pic_selector_app", "run", "--host=0.0.0.0", "--port=5000"]
