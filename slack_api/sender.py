import os
import itertools
from operator import itemgetter
from datetime import date
from lunchinator.models import User, Selection, Meal, Restaurant
from slack_api.api import SlackApi


class SlackSender:
    __instance = None

    def __new__(cls):
        if SlackSender.__instance is None:
            SlackSender.__instance = object.__new__(cls)
        return SlackSender.__instance

    def __init__(self):
        self._lunch_channel = os.environ['LUNCHINATOR_LUNCH_CHANNEL']
        self._selection_message = None
        self._selection_user_message = {}
        self._api = SlackApi()

    def send_to_slack(self):
        for u in User.objects.all():
            self.send_meals(u)

    def send_meals(self, user: User):
        restaurants = Restaurant.objects.filter(enabled=True).all()
        meals = {r: r.meals.filter(date=date.today()).all() for r in restaurants}

        for restaurant in user.favorite_restaurants.all():
            if restaurant in meals:
                atts = [{
                    "fallback": restaurant.name,
                    "color": "good",
                    "attachment_type": "default",
                    "callback_id": "meals_selection",
                    "actions": [SlackSender._meal_action(meal) for meal in meal_group]
                } for meal_group in SlackSender._grouper(meals[restaurant], 5)]
                self._api.message(self._api.user_channel(user.slack_id), f"*=== {restaurant.name} ===*", atts)

        att = {
            "fallback": "Other controls",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "other_ops",
            "actions": [
                {"name": "operation", "text": "erase", "type": "button", "value": "erase"},
                {"name": "operation", "text": "recommend", "type": "button", "value": "recommend"},
                {"name": "operation", "text": "select restaurants", "type": "button", "value": "restaurants"},
                {"name": "operation", "text": "clear restaurants", "type": "button", "value": "clear_restaurants"},
                {"name": "operation", "text": "invite", "type": "button", "value": "invite_dialog"}
            ]
        }
        self._api.message(self._api.user_channel(user.slack_id), "Other controls", [att])

    def invite(self, userid: str):
        att = {
            "fallback": "Lunchinator invite",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "other_ops",
            "actions": [
                {"name": "operation", "text": "select restaurants", "type": "button", "value": "restaurants"},
            ]
        }
        self._api.message(self._api.user_channel(userid), "Lunchinator invite", [att])

    def invite_dialog(self, trigger_id: str):
        self._api.user_dialog(trigger_id)

    def print_recommendation(self, recs: list, userid: str):
        atts = [{
            "fallback": "Recommendations",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "recommendations_selection",
            "actions": [SlackSender._meal_action(meal, f"{meal.restaurant.name}, score={score}") for meal, score in rec_group]
        } for rec_group in SlackSender._grouper(recs, 5)]
        text = f"*Recommendations for <@{userid}>*"
        self._api.message(self._api.user_channel(userid), text, atts)

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        atts = [{
            "fallback": "Restaurants",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "restaurants_selection",
            "actions": [{"name": "restaurant", "text": r.name, "type": "button", "value": r.pk} for r in restaurant_group]
        } for restaurant_group in SlackSender._grouper(restaurants, 5)]

        atts.append({
            "fallback": "Selected restaurants",
            "title": "Selected restaurants",
            "color": "good",
            "fields": [{"title": f"{restaurant.name}", "short": True} for restaurant in selected_restaurants]
        })

        self._api.message(self._api.user_channel(userid), "Available restaurants", atts)

    def post_selections(self, userid: str = None):
        restaurant_users = [(s.meal.restaurant, s.user) for s in Selection.objects.filter(meal__date=date.today()).all()]
        restaurant_users_grouped = [(r, [ru[1] for ru in rus]) for r, rus in itertools.groupby(sorted(restaurant_users, key=itemgetter(0).name), itemgetter(0).name)]
        fields = [{"title": f"{restaurant.name} ({len(users)})", "value": ", ".join([f"<@{u.slack_id}>" for u in users]), "short": False}
                  for restaurant, users in sorted(restaurant_users_grouped, key=lambda rest_users: (-len(rest_users[1]), rest_users[0].name))]
        att = {
            "fallback": "Selection",
            "color": "good",
            "fields": fields,
            "mrkdwn_in": ["fields"]
        }
        text = "*Current selection*"
        if userid is None:
            channel = self._lunch_channel
            current_ts = self._selection_message
        else:
            channel = self._api.user_channel(userid)
            current_ts = self._selection_user_message[userid]

        if current_ts is None:
            ts = self._api.message(channel, text, [att])
            if userid is None:
                self._selection_message = ts
            else:
                self._selection_user_message[userid] = ts
        else:
            self._api.update_message(channel, current_ts, text, [att])

    @staticmethod
    def _meal_action(meal: Meal, extra_info=None) -> dict:
        text = f"{meal.name} {meal.price}"
        if extra_info is not None:
            text += ", " + extra_info,
        return {
            "name": "meal",
            "text": text,
            "type": "button",
            "value": meal.pk
        }

    @staticmethod
    def _grouper(iterable, n):
        args = [iter(iterable)] * n
        return ([e for e in x if e is not None] for x in itertools.zip_longest(*args))
