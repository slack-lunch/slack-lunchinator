import itertools
from operator import itemgetter
from datetime import date
from lunchinator.models import User, Selection, Meal
from slack_api.api import SlackApi


class SlackSender:
    def __init__(self, api: SlackApi, lunch_channel: str, meals: dict, today: date):
        self._api = api
        self._lunch_channel = lunch_channel
        self._meals = meals
        self._today = today
        self._selection_message = None
        self._selection_user_message = {}

    def send_to_slack(self):
        for u in User.objects.all():
            self.send_meals(u)

    def send_meals(self, user: User):
        for restaurant in user.favorite_restaurants.all():
            if restaurant in self._meals:
                att = {
                    "fallback": restaurant.name,
                    "color": "good",
                    "attachment_type": "default",
                    "callback_id": "meals_selection",
                    "actions": [SlackSender._meal_action(meal) for meal in self._meals[restaurant]]
                }
                self._api.message(self._api.user_channel(user.slack_id), f"*=== {restaurant.name} ===*", [att])

        att = {
            "fallback": "Other controls",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "other_ops",
            "actions": [
                {"name": "operation", "text": "erase", "type": "button", "value": "erase"},
                {"name": "operation", "text": "recommend", "type": "button", "value": "recommend"},
                {"name": "operation", "text": "select restaurants", "type": "button", "value": "restaurants"}
            ]
        }
        self._api.message(self._api.user_channel(user.slack_id), "Other controls", [att])

    def print_recommendation(self, recs: list, userid: str):
        actions = [SlackSender._meal_action(meal, f"{meal.restaurant.name}, score={score}") for meal, score in recs]
        att = {
            "fallback": "Recommendations",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "recommendations_selection",
            "actions": actions
        }
        text = f"*Recommendations for <@{userid}>*"
        self._api.message(self._api.user_channel(user.slack_id), text, [att])

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        fields = [{"title": f"{restaurant.name}", "value": "selected", "short": False}
                  for restaurant in selected_restaurants]
        att = {
            "fallback": "Restaurants",
            "color": "good",
            "attachment_type": "default",
            "callback_id": "restaurants_selection",
            "fields": fields,
            "actions": [{"name": "restaurant", "text": r.name, "type": "button", "value": r.pk} for r in restaurants]
        }
        self._api.message(self._api.user_channel(userid), "Available restaurants", [att])

    def post_selections(self, userid: str = None):
        restaurant_users = [(s.meal.restaurant, s.user) for s in Selection.objects.filter(meal__date=self._today).all()]
        restaurant_users_grouped = [(r, [ru[1] for ru in rus]) for r, rus in itertools.groupby(sorted(restaurant_users, key=itemgetter(0)), itemgetter(0))]
        fields = [{"title": f"{restaurant.name} ({len(users)})", "value": ", ".join([f"<@{u.id}>" for u in users]), "short": False}
                  for restaurant, users in sorted(restaurant_users_grouped, key=lambda restaurant, users: (-len(users), restaurant.name))]
        att = {
            "fallback": "Selection",
            "color": "good",
            "fields": fields,
            "mrkdwn_in": {"fields"}
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
