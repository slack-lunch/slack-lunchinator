import os
import itertools
from datetime import date
from lunchinator.models import User, Meal
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

    def send_meals(self, user: User, restaurants: list):
        meals = {r: r.meals.filter(date=date.today()).all() for r in restaurants}
        user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}

        if user.slack_id not in self._meals_user_restaurants_messages:
            self._meals_user_restaurants_messages[user.slack_id] = {}

        for restaurant in user.favorite_restaurants.all():
            if restaurant in meals:
                blocks = [
                             {"type": "section", "text": {"type": "mrkdwn", "text": f"*{restaurant.name}*"}},
                             {"type": "divider"}
                         ] + [SlackSender._meal_voting_block(
                                m,
                                "meals" + str(restaurant.pk) + "_" + str(i),
                                m.pk not in user_meals_pks
                         ) for i, m in enumerate(meals[restaurant])]
                if not meals[restaurant]:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "plain_text", "text": "<none>"},
                    })

                if restaurant.pk in self._meals_user_restaurants_messages[user.slack_id]:
                    ts = self._api.update_message(
                        self._api.user_channel(user.slack_id),
                        self._meals_user_restaurants_messages[user.slack_id][restaurant.pk],
                        restaurant.name,
                        blocks
                    )
                else:
                    ts = self._api.message(self._api.user_channel(user.slack_id), restaurant.name, blocks)
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
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Other Controls*"}},
            {"type": "divider"},
            {
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
                    {"type": "button", "text": {"type": "plain_text", "text": "quit"}, "action_id": "quit", "value": "1"},
                    {"type": "button", "text": {"type": "plain_text", "text": "invite"}, "action_id": "invite_dialog", "value": "1"}

                ]
            }
        ]
        self._api.message(self._api.user_channel(userid), "Other Controls", blocks)

    def invite(self, userid: str):
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*You are invited to Lunchinator!*"}},
            {"type": "divider"},
            {
                    "type": "actions",
                    "elements": [{"type": "button", "text": {"type": "plain_text", "text": "select restaurants"}, "action_id": "restaurants", "value": "1"}]
            }
        ]
        self._api.message(self._api.user_channel(userid), "Lunchinator invite", blocks)

    def invite_dialog(self, trigger_id: str):
        self._api.user_dialog(trigger_id)

    def print_recommendation(self, recs: list, user: User):
        user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
        text = "*Recommendations*"
        blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                {"type": "divider"}
            ] + [SlackSender._meal_voting_block(
                    m,
                    "recommended_meals" + str(i),
                    m.pk not in user_meals_pks,
                    f"{m.restaurant.name}, score={s}"
                 ) for i, (m, s) in enumerate(recs)]

        if user.slack_id in self._recommendations_user_message:
            ts = self._api.update_message(self._api.user_channel(user.slack_id), self._recommendations_user_message[user.slack_id], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(user.slack_id), text, blocks)
        self._recommendations_user_message[user.slack_id] = ts

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        text = "*Available Restaurants*"
        restaurant_fields = [{"type": "plain_text", "text": f"{restaurant.name}"} for restaurant in selected_restaurants]
        if not restaurant_fields:
            restaurant_fields = [{"type": "plain_text", "text": "<none>"}]

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "divider"}
         ] + [
            {
                "type": "actions",
                "block_id": "restaurants"+str(i),
                "elements": [{"type": "button", "text": {"type": "plain_text", "text": r.name}, "value": str(r.pk), "action_id": "restaurant"+str(r.pk)} for r in restaurant_group]
            } for i, restaurant_group in enumerate(SlackSender._grouper(restaurants, 5))
        ] + [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Selected Restaurants*"
                },
                "fields": restaurant_fields
            }
        ]

        if userid in self._restaurants_user_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._restaurants_user_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._restaurants_user_message[userid] = ts

    def post_selections(self, selections: list):
        restaurant_users = [(s.meal.restaurant, s.user) for s in selections]
        key_fun = lambda rest_user: rest_user[0].name
        restaurant_users_grouped = [(r, {ru[1].slack_id for ru in rus}) for r, rus in itertools.groupby(sorted(restaurant_users, key=key_fun), key_fun)]
        text = "*Current Selections*"
        blocks = [
             {"type": "section", "text": {"type": "mrkdwn", "text": text}},
             {"type": "divider"}
         ] + [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{restaurant_name} _({len(user_ids)})_\n" + ", ".join([f"<@{uid}>" for uid in user_ids])
                }
            } for restaurant_name, user_ids in sorted(restaurant_users_grouped, key=lambda rest_users: (-len(rest_users[1]), rest_users[0]))
        ]

        if self._selection_message is None:
            ts = self._api.message(self._lunch_channel, text, blocks)
        else:
            ts = self._api.update_message(self._lunch_channel, self._selection_message, text, blocks)
        self._selection_message = ts

    def post_selection(self, userid: str, meals: list):
        text = "*Your Current Selection*"
        fields = [{
            "type": "mrkdwn",
            "text": f"{meal.restaurant.name}: {meal.name}{' _' + str(meal.price) + '_' if meal.price else ''}"
        } for meal in meals]

        if not fields:
            fields = [{"type": "plain_text", "text": "<none>"}]

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}, "fields": fields}
        ]
        if userid in self._user_selection_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._user_selection_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._user_selection_message[userid] = ts

    def message(self, userid: str, msg: str):
        self._api.message(self._api.user_channel(userid), msg)

    @staticmethod
    def _meal_voting_block(meal: Meal, block_id: str, allow_voting: bool, extra_info: str = None) -> dict:
        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": SlackSender._meal_text(meal, extra_info)},
            "block_id": block_id
        }
        if allow_voting:
            block["accessory"] = {
                "type": "button",
                "text": {"type": "plain_text", "text": "Vote"},  # "emoji": True,
                "value": str(meal.pk)
            }
        return block

    @staticmethod
    def _meal_text(meal: Meal, extra_info: str) -> str:
        value = ""
        if meal.price:
            value += " _" + str(meal.price) + "_"
        if extra_info:
            value += ", " + extra_info
        return f"{meal.name}{value}"

    @staticmethod
    def _grouper(iterable, n):
        args = [iter(iterable)] * n
        return ([e for e in x if e is not None] for x in itertools.zip_longest(*args))
