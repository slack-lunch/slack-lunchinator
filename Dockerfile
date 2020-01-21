FROM python:3.7-slim-stretch

RUN apt-get update && \
 apt-get install -y build-essential curl cron tesseract-ocr libtesseract-dev tesseract-ocr-ces && \
 apt-get clean all && \
 rm -rf /var/lib/apt/lists/*

RUN echo 'Europe/Prague' >/etc/timezone
RUN rm -f /etc/localtime && ln -s /usr/share/zoneinfo/Europe/Prague /etc/localtime

RUN echo '0 11 * * 1-5 . /opt/env && /usr/bin/curl http://localhost:8000/$URL_PREFIX/lunchinator/trigger' >/etc/cron.d/lunchinator && \
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

RUN mkdir /opt/static

EXPOSE 8000
WORKDIR /opt

CMD /bin/echo "URL_PREFIX=$URL_PREFIX" >/opt/env && /usr/sbin/cron && ./manage.py migrate && ./manage.py collectstatic --noinput && ./manage.py runserver 0.0.0.0:8000
