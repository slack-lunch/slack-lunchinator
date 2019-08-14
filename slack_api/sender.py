import os
import itertools
from datetime import date
from lunchinator.models import User, Meal
from slack_api.api import SlackApi


class SlackSender:

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
                                "Vote" if m.pk not in user_meals_pks else None,
                                "select_meal"
                         ) for m in meals[restaurant]]
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
        confirm_dialog = {
            "title":   {"type": "plain_text", "text": "Quitting Lunchinator"},
            "text":    {"type": "plain_text", "text": "You really mean it?"},
            "confirm": {"type": "plain_text", "text": "oh really"},
            "deny":    {"type": "plain_text", "text": "nope"}
        }
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Other Controls*"}},
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "recommend"}, "action_id": "recommend"},
                    {"type": "button", "text": {"type": "plain_text", "text": "my selection"}, "action_id": "print_selection"}
                ]
            }, {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "select restaurants"}, "action_id": "restaurants"},
                    {"type": "button", "text": {"type": "plain_text", "text": "quit"}, "action_id": "quit", "style": "danger", "confirm": confirm_dialog},
                    {"type": "button", "text": {"type": "plain_text", "text": "invite"}, "action_id": "invite_dialog"}

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
                    "Vote" if m.pk not in user_meals_pks else None,
                    "select_recommended_meal",
                    f"{m.restaurant.name}, score={s:.3f}"
                 ) for m, s in recs]

        if user.slack_id in self._recommendations_user_message:
            ts = self._api.update_message(self._api.user_channel(user.slack_id), self._recommendations_user_message[user.slack_id], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(user.slack_id), text, blocks)
        self._recommendations_user_message[user.slack_id] = ts

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        selected_restaurants_ids = {r.pk for r in selected_restaurants}
        text = "*Available Restaurants*"
        blocks = [
             {"type": "section", "text": {"type": "mrkdwn", "text": text}},
             {"type": "divider"}
        ] + [{
            "type": "section",
            "text": {"type": "plain_text", "text": restaurant.name},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Add" if restaurant.pk not in selected_restaurants_ids else "Remove"},
                "action_id": "add_restaurant" if restaurant.pk not in selected_restaurants_ids else "remove_restaurant",
                "value": str(restaurant.pk)
            }
        } for restaurant in restaurants]

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
        blocks = [
             {"type": "section", "text": {"type": "mrkdwn", "text": text}},
             {"type": "divider"}
        ] + [SlackSender._meal_voting_block(
            meal,
            "Remove",
            "remove_meal",
            meal.restaurant.name
        ) for meal in meals]

        if not meals:
            blocks.append({
                "type": "section",
                "text": {"type": "plain_text", "text": "<none>"},
            })

        if userid in self._user_selection_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._user_selection_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._user_selection_message[userid] = ts

    def message(self, userid: str, msg: str):
        self._api.message(self._api.user_channel(userid), msg)

    @staticmethod
    def _meal_voting_block(meal: Meal, button: str, action_prefix: str, extra_info: str = None) -> dict:
        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": SlackSender._meal_text(meal, extra_info)}
        }
        if button:
            block["accessory"] = {
                "type": "button",
                "text": {"type": "plain_text", "text": button},
                "value": str(meal.pk),
                "action_id": action_prefix + str(meal.pk)
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
