FROM python:3.7-slim-stretch

RUN apt-get update && \
 apt-get install -y rabbitmq-server && \
 apt-get install -y build-essential && \
 apt-get install -y libcurl3 libcurl4-openssl-dev libssl-dev gcc && \
 apt-get clean all && \
 rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/
RUN /usr/local/bin/pip3 install -r /opt/requirements.txt && \
  rm -rf /root/.cache/

COPY manage.py /opt/
COPY app /opt/app
COPY lunchinator /opt/lunchinator
COPY restaurants /opt/restaurants
COPY recommender /opt/recommender
COPY slack_api /opt/slack_api

EXPOSE 8000
WORKDIR /opt

CMD ./manage.py migrate && rabbitmq-server & sleep 5 && celery -A app worker -c 1 & sleep 5 && celery -A app beat & sleep 10 && ./manage.py runserver 0.0.0.0:8000
