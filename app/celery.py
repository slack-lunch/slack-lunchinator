from datetime import date
import os
import django

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from slack_api.sender import SlackSender
from lunchinator.models import Restaurant, Meal
from restaurants import PARSERS

app = Celery('lunchinator')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.timezone = 'Europe/Prague'


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(hour=11, minute=0, day_of_week='1-5'), parse_and_send_meals.s())


@app.task
def parse_and_send_meals():
    meal_cnt = Meal.objects.filter(date=date.today()).count()
    print(f"Read {meal_cnt} meals from DB")

    restaurants = Restaurant.objects.filter(enabled=True).all()

    if meal_cnt == 0:
        meals = {r: parse(r) for r in restaurants}
        print(f"Parsed {sum(map(len, meals.values()))} meals from {len(meals)} restaurant")
        for ms in meals.values():
            for m in ms:
                m.save()

    SlackSender().send_to_slack()


def parse(restaurant: Restaurant) -> list:
    try:
        return PARSERS[restaurant.provider]().get_meals()
    except:
        print("Failed parsing " + str(restaurant))
        return []
