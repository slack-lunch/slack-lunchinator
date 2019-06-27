FROM python:3.7-slim-stretch

RUN apt-get update
RUN apt-get install -y rabbitmq-server
RUN apt-get install -y build-essential
RUN apt-get clean all

COPY requirements.txt /opt/
RUN /usr/local/bin/pip3 install -r /opt/requirements.txt

COPY manage.py /opt/
COPY app /opt/app
COPY lunchinator /opt/lunchinator
COPY restaurants /opt/restaurants
COPY recommender /opt/recommender
COPY slack_api /opt/slack_api

EXPOSE 8000
WORKDIR /opt

RUN ["/usr/local/bin/python3", "./manage.py", "migrate"]

CMD rabbitmq-server & celery -A app worker -l info -c 1 & celery -A app beat -l info & ./manage.py runserver 0.0.0.0:8000
