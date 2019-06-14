import itertools
from operator import itemgetter
from datetime import date
from lunchinator.models import User, Selection
from slack_api.slack_api import SlackApi


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

        for restaurant in self._meals.keys():
            att = {
                "fallback": restaurant.name,
                "color": "good",
                 "fields": [SlackSender._meal_field(m, idx) for idx, m in enumerate(self._meals[restaurant])]
            }
            self._api.message(self._lunch_channel, f"*=== {restaurant.acronym}: {restaurant.name} ===*", [att])

    @staticmethod
    def _meal_field(meal, idx: int, extra_info=None) -> dict:
        value = str(meal.price)
        if extra_info is not None:
            value += ", " + extra_info,
        return {
            "title": f"{meal.restaurant.acronym}{idx + 1}. {meal.name}",
            "value": value,
            "short": False
        }

    def send_to_user(self, userid: str, text: str):
        self._api.message(self._api.user_channel(userid), text)

    def send_meals(self, user: User):
        for restaurant in user.favorite_restaurants:
            if restaurant in self._meals:
                att = {
                    "fallback": restaurant.name,
                    "color": "good",
                    "fields": [SlackSender._meal_field(m, idx) for idx, m in enumerate(self._meals[restaurant])]
                }
                self._api.message(self._api.user_channel(user.slack_id), f"*=== {restaurant.acronym}: {restaurant.name} ===*", [att])

    def print_recommendation(self, recs: list, userid: str):
        rec_fields = [SlackSender._meal_field(meal, idx, f"{meal.restaurant.name}, score={score}") for meal, idx, score in recs]
        att = {
            "fallback": "Recommendations",
            "color": "good",
            "fields": rec_fields
        }
        text = f"*Recommendations for <@{userid}>*"
        self._api.message(self._api.user_channel(userid), text, [att])

    def print_restaurants(self, userid: str, title: str, restaurants: list):
        att = {
            "fallback": "Restaurants",
            "color": "good",
            "fields": [{"title": f"{r.acronym}: {r.name}", "value": None, "short": True} for r in restaurants]
        }
        self._api.message(self._api.user_channel(userid), title, [att])

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
