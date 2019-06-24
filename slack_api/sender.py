import os
import itertools
from datetime import date
from lunchinator.models import User, Selection, Meal, Restaurant
from slack_api.api import SlackApi
from slack_api.singleton import Singleton


class SlackSender(metaclass=Singleton):

    def __init__(self):
        self._lunch_channel = os.environ['LUNCHINATOR_LUNCH_CHANNEL']
        self._api = SlackApi()

        self._selection_message = None
        self._user_selection_message = {}
        self._restaurants_user_message = {}
        self._recommendations_user_message = {}
        self._meals_user_restaurants_messages = {}
        self._other_actions_user_message_sent = set()

    def reset(self):
        self._selection_message = None
        self._user_selection_message = {}
        self._restaurants_user_message = {}
        self._recommendations_user_message = {}
        self._meals_user_restaurants_messages = {}
        self._other_actions_user_message_sent = set()

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
                blocks = SlackSender._meals_blocks(meals[restaurant], "meals"+str(restaurant.pk),
                        lambda group: [SlackSender._meal_field(meal) for meal in group],
                        lambda group: [SlackSender._meal_action_element(meal) for meal in group])
                blocks.insert(0, {"type": "section", "text": {"type": "mrkdwn", "text": f"*=== {restaurant.name} ===*"}})
                ts = self._api.message(self._api.user_channel(user.slack_id), f"*=== {restaurant.name} ===*", blocks)
                self._meals_user_restaurants_messages[user.slack_id][restaurant.pk] = ts

        for restaurant_id in set(self._meals_user_restaurants_messages[user.slack_id].keys())\
                .difference({r.pk for r in user.favorite_restaurants.all()}):
            self._api.delete_message(self._api.user_channel(user.slack_id),
                                     self._meals_user_restaurants_messages[user.slack_id][restaurant_id])
            self._meals_user_restaurants_messages[user.slack_id].pop(restaurant_id)

        if user.slack_id not in self._other_actions_user_message_sent:
            self._send_other_controls(user.slack_id)
            self._other_actions_user_message_sent.add(user.slack_id)

    def _send_other_controls(self, userid: str):
        blocks = [{
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "erase"}, "action_id": "erase", "value": "1"},
                {"type": "button", "text": {"type": "plain_text", "text": "recommend"}, "action_id": "recommend", "value": "1"},
                {"type": "button", "text": {"type": "plain_text", "text": "my selection"}, "action_id": "print_selection", "value": "1"}
            ]
        }, {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "select restaurants"}, "action_id": "restaurants", "value": "1"},
                {"type": "button", "text": {"type": "plain_text", "text": "clear restaurants"}, "action_id": "clear_restaurants", "value": "1"},
                {"type": "button", "text": {"type": "plain_text", "text": "invite"}, "action_id": "invite_dialog", "value": "1"}

            ]
        }]
        self._api.message(self._api.user_channel(userid), "Other controls", blocks)

    def invite(self, userid: str):
        blocks = [{
                "type": "actions",
                "elements": [{"type": "button", "text": {"type": "plain_text", "text": "select restaurants"}, "action_id": "restaurants", "value": "1"}]
        }]
        self._api.message(self._api.user_channel(userid), "Lunchinator invite", blocks)

    def invite_dialog(self, trigger_id: str):
        self._api.user_dialog(trigger_id)

    def print_recommendation(self, recs: list, userid: str):
        blocks = SlackSender._meals_blocks(recs, "recommended_meals",
              lambda group: [SlackSender._meal_field(meal, f"{meal.restaurant.name}, score={score}") for meal, score in group],
              lambda group: [SlackSender._meal_action_element(meal) for meal, score in group])
        text = f"*Recommendations*"

        if userid in self._recommendations_user_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._recommendations_user_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._recommendations_user_message[userid] = ts

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        blocks = [{
            "type": "actions",
            "block_id": "restaurants"+str(i),
            "elements": [{"type": "button", "text": {"type": "plain_text", "text": r.name}, "value": str(r.pk), "action_id": "restaurant"+str(r.pk)} for r in restaurant_group]
        } for i, restaurant_group in enumerate(SlackSender._grouper(restaurants, 5))]

        restaurant_fields = [{"type": "plain_text", "text": f"{restaurant.name}"} for restaurant in selected_restaurants]
        if not restaurant_fields:
            restaurant_fields = [{"type": "plain_text", "text": "<none>"}]

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Selected restaurants*"
            },
            "fields": restaurant_fields
        })

        text = "Available restaurants"
        if userid in self._restaurants_user_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._restaurants_user_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._restaurants_user_message[userid] = ts

    def post_selections(self):
        restaurant_users = [(s.meal.restaurant, s.user) for s in Selection.objects.filter(meal__date=date.today()).all()]
        key_fun = lambda rest_user: rest_user[0].name
        restaurant_users_grouped = [(r, {ru[1].slack_id for ru in rus}) for r, rus in itertools.groupby(sorted(restaurant_users, key=key_fun), key_fun)]
        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{restaurant_name} ({len(user_ids)})*\n" + ", ".join([f"<@{uid}>" for uid in user_ids])
            }
        } for restaurant_name, user_ids in sorted(restaurant_users_grouped, key=lambda rest_users: (-len(rest_users[1]), rest_users[0]))]

        text = "*Current selection*"
        if self._selection_message is None:
            ts = self._api.message(self._lunch_channel, text, blocks)
        else:
            ts = self._api.update_message(self._lunch_channel, self._selection_message, text, blocks)
        self._selection_message = ts

    def post_selection(self, userid: str, meals: list):
        fields = [{
            "type": "mrkdwn",
            "text": f"{meal.restaurant.name}: *{meal.name}* {meal.price or ''}",
        } for meal in meals]

        if not fields:
            fields = [{"type": "plain_text", "text": "<none>"}]

        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Selection*",
            },
            "fields": fields
        }]
        text = "*Current selection*"
        if userid in self._user_selection_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._user_selection_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._user_selection_message[userid] = ts

    @staticmethod
    def _meals_blocks(data: list, block_id, group_to_fields, group_to_elements) -> list:
        return [x for i, group in enumerate(SlackSender._grouper(data, 4)) for x in [{
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": " ",
            },
            "fields": group_to_fields(group),
        }, {
            "type": "actions",
            "block_id": block_id + "_" + str(i),
            "elements": group_to_elements(group)
        }]]

    @staticmethod
    def _meal_field(meal: Meal, extra_info=None) -> dict:
        value = ""
        if meal.price is not None:
            value += " " + str(meal.price)
        if extra_info is not None:
            value += ", " + extra_info,
        return {
            "type": "mrkdwn",
            "text": f"*{meal.name}*" + value,
        }

    @staticmethod
    def _meal_action_element(meal: Meal) -> dict:
        if len(meal.name) > 16:
            text = meal.name[0:16] + "..."
        else:
            text = meal.name
        return {
            "type": "button",
            "text": {"type": "plain_text", "text": text},
            "value": str(meal.pk),
            "action_id": "meal" + str(meal.pk)
        }

    @staticmethod
    def _grouper(iterable, n):
        args = [iter(iterable)] * n
        return ([e for e in x if e is not None] for x in itertools.zip_longest(*args))
