FROM python:3.7-slim-stretch

COPY requirements.txt /opt/
RUN /usr/local/bin/pip3 install -r /opt/requirements.txt

COPY manage.py /opt/
COPY app /opt/app
COPY lunchinator /opt/lunchinator
COPY parsing /opt/parsing
COPY recommender /opt/recommender
COPY slack_api /opt/slack_api

EXPOSE 8000
WORKDIR /opt

RUN ["/usr/local/bin/python3", "./manage.py", "migrate"]
CMD ["/usr/local/bin/python3", "./manage.py", "runserver", "0.0.0.0:8000"]
