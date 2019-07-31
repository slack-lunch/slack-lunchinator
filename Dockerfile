FROM python:3.7-slim-stretch

RUN apt-get update && \
 apt-get install -y rabbitmq-server && \
 apt-get install -y build-essential && \
 apt-get install -y libcurl3 libcurl4-openssl-dev libssl-dev gcc && \
 apt-get clean all

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

CMD rabbitmq-server & sleep 5 && celery -A app worker -c 1 & sleep 5 && celery -A app beat & sleep 10 && ./manage.py runserver 0.0.0.0:8000
