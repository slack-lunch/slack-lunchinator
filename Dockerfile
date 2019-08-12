FROM python:3.7-slim-stretch

RUN apt-get update && \
 apt-get install -y build-essential libcurl3 libcurl4-openssl-dev libssl-dev curl cron && \
 apt-get clean all && \
 rm -rf /var/lib/apt/lists/*

RUN echo '0 9 * * 1-5 /usr/bin/curl http://localhost:8000/lunchinator/trigger' >/etc/cron.d/lunchinator && \
    /usr/bin/crontab /etc/cron.d/lunchinator

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

CMD /usr/sbin/cron && ./manage.py migrate && ./manage.py runserver 0.0.0.0:8000
