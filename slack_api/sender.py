import os
import itertools
from operator import itemgetter
from datetime import date
from lunchinator.models import User, Selection, Meal, Restaurant
from slack_api.api import SlackApi
from slack_api.singleton import Singleton


class SlackSender(metaclass=Singleton):

    def __init__(self):
        self._lunch_channel = os.environ['LUNCHINATOR_LUNCH_CHANNEL']
        self._selection_message = None
        self._selection_user_message = {}
        self._restaurants_user_message = {}
        self._recommendations_user_message = {}
        self._meals_user_restaurants_messages = {}
        self._other_actions_user_message_sent = set()
        self._api = SlackApi()

    def send_to_slack(self):
        for u in User.objects.all():
            self.send_meals(u)

    def send_meals(self, user: User):
        restaurants = Restaurant.objects.filter(enabled=True).all()
        meals = {r: r.meals.filter(date=date.today()).all() for r in restaurants}

        if user.slack_id not in self._meals_user_restaurants_messages:
            self._meals_user_restaurants_messages[user.slack_id] = {}

        for restaurant in user.favorite_restaurants.all():
            if (restaurant in meals) and (restaurant.pk not in self._meals_user_restaurants_messages[user.slack_id]):
                atts = SlackSender._meals_attachments(meals[restaurant], restaurant.name, "meals_selection",
                        lambda group: [SlackSender._meal_field(meal) for meal in group],
                        lambda group: [SlackSender._meal_action(meal) for meal in group])
                ts = self._api.message(self._api.user_channel(user.slack_id), f"*=== {restaurant.name} ===*", atts)
                self._meals_user_restaurants_messages[user.slack_id][restaurant.pk] = ts

        for restaurant_id in set(self._meals_user_restaurants_messages[user.slack_id].keys())\
                .difference({r.pk for r in user.favorite_restaurants.all()}):
            self._api.delete_message(self._api.user_channel(user.slack_id),
                                     self._meals_user_restaurants_messages[user.slack_id][restaurant_id])

        if user.slack_id not in self._other_actions_user_message_sent:
            self._send_other_controls(user.slack_id)
            self._other_actions_user_message_sent.add(user.slack_id)

    def _send_other_controls(self, userid: str):
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

        self._api.message(self._api.user_channel(userid), "Other controls", [att])

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
        atts = SlackSender._meals_attachments(recs, "Recommendations", "recommendations_selection",
              lambda group: [SlackSender._meal_field(meal, f"{meal.restaurant.name}, score={score}") for meal, score in group],
              lambda group: [SlackSender._meal_action(meal) for meal, score in group])
        text = f"*Recommendations>*"

        if userid in self._recommendations_user_message:
            self._api.update_message(self._api.user_channel(userid), self._recommendations_user_message[userid], text, atts)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, atts)
            self._recommendations_user_message[userid] = ts

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

        text = "Available restaurants"
        if userid in self._restaurants_user_message:
            self._api.update_message(self._api.user_channel(userid), self._restaurants_user_message[userid], text, atts)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, atts)
            self._restaurants_user_message[userid] = ts

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
            current_ts = self._selection_user_message.get(userid)

        if current_ts is None:
            ts = self._api.message(channel, text, [att])
            if userid is None:
                self._selection_message = ts
            else:
                self._selection_user_message[userid] = ts
        else:
            self._api.update_message(channel, current_ts, text, [att])

    @staticmethod
    def _meals_attachments(data: list, fallback: str, callback_id: str, group_to_fields, group_to_actions) -> list:
        return [{
            "fallback": fallback,
            "color": "good",
            "attachment_type": "default",
            "callback_id": callback_id,
            "fields": group_to_fields(group),
            "actions": group_to_actions(group)
        } for group in SlackSender._grouper(data, 5)]

    @staticmethod
    def _meal_field(meal: Meal, extra_info=None) -> dict:
        value = ""
        if meal.price is not None:
            value = str(meal.price)
        if extra_info is not None:
            value += ", " + extra_info,
        return {
            "title": meal.name,
            "value": value,
            "short": False
        }

    @staticmethod
    def _meal_action(meal: Meal) -> dict:
        if len(meal.name) > 16:
            text = meal.name[0:16] + "..."
        else:
            text = meal.name
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
