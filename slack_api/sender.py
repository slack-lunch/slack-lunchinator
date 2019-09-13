import os
import itertools
from datetime import date

from unidecode import unidecode

from lunchinator.models import User, Meal, Restaurant
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
        favourite_restaurants = set(user.favorite_restaurants.all())
        user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}

        if user.slack_id not in self._meals_user_restaurants_messages:
            self._meals_user_restaurants_messages[user.slack_id] = {}

        for restaurant in meals.keys():
            if (restaurant in favourite_restaurants) or (restaurant.name == Restaurant.ADHOC_NAME):
                blocks = SlackSender.restaurant_meal_blocks(restaurant, meals[restaurant], user_meals_pks)

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
            if any(r.pk == restaurant_id and r.name != Restaurant.ADHOC_NAME for r in meals.keys()):
                self._api.delete_message(self._api.user_channel(user.slack_id),
                                         self._meals_user_restaurants_messages[user.slack_id][restaurant_id])
                self._meals_user_restaurants_messages[user.slack_id].pop(restaurant_id)

        if user.slack_id not in self._other_actions_user_message_sent:
            self._send_other_controls(user.slack_id)
            self._other_actions_user_message_sent.add(user.slack_id)

    @staticmethod
    def restaurant_meal_blocks(restaurant: Restaurant, meals: list, user_meals_pks: set):
        blocks = [
                     {"type": "section", "text": {"type": "mrkdwn", "text": f"*{restaurant.name}*"}},
                     {"type": "divider"}
        ] + [SlackSender._meal_voting_block(
            m,
            "Vote" if (user_meals_pks is not None) and (m.pk not in user_meals_pks) else None,
            "select_meal"
        ) for m in meals]
        if not meals:
            blocks.append({
                "type": "section",
                "text": {"type": "plain_text", "text": "<none>"},
            })
        return blocks

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
        blocks = SlackSender.recommendation_blocks(text, recs, user_meals_pks)

        if user.slack_id in self._recommendations_user_message:
            ts = self._api.update_message(self._api.user_channel(user.slack_id), self._recommendations_user_message[user.slack_id], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(user.slack_id), text, blocks)
        self._recommendations_user_message[user.slack_id] = ts

    @staticmethod
    def recommendation_blocks(title: str, recommendations: list, user_meals_pks: set):
        return [
                {"type": "section", "text": {"type": "mrkdwn", "text": title}},
                {"type": "divider"}
            ] + [SlackSender._meal_voting_block(
                    m,
                    "Vote" if (user_meals_pks is not None) and (m.pk not in user_meals_pks) else None,
                    "select_recommended_meal",
                    f"{m.restaurant.name}, score={s:.3f}"
                 ) for m, s in recommendations]

    @staticmethod
    def search_blocks(text: str, query_words: list, meals: list, user_meals_pks: set):
        return [
                   {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                   {"type": "divider"}
               ] + [
                   SlackSender._meal_voting_block(
                       m,
                       "Vote" if (user_meals_pks is not None) and (m.pk not in user_meals_pks) else None,
                       "select_meal",
                       f"{m.restaurant.name}",
                       highlighted_words=query_words
                   ) for m in meals
        ]

    def print_restaurants(self, userid: str, restaurants: list, selected_restaurants: list):
        text = "*Available Restaurants*"
        blocks = SlackSender.restaurant_blocks(text, restaurants, {r.pk for r in selected_restaurants})

        if userid in self._restaurants_user_message:
            ts = self._api.update_message(self._api.user_channel(userid), self._restaurants_user_message[userid], text, blocks)
        else:
            ts = self._api.message(self._api.user_channel(userid), text, blocks)
        self._restaurants_user_message[userid] = ts

    @staticmethod
    def restaurant_blocks(title: str, restaurants: list, selected_ids: set):
        return [
             {"type": "section", "text": {"type": "mrkdwn", "text": title}},
             {"type": "divider"}
        ] + [{
            "type": "section",
            "text": {"type": "plain_text", "text": restaurant.name},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Add" if not selected_ids or restaurant.pk not in selected_ids else "Remove"},
                "action_id": "add_restaurant" if not selected_ids or restaurant.pk not in selected_ids else "remove_restaurant",
                "value": str(restaurant.pk)
            }
        } for restaurant in restaurants]

    def post_selections(self, selections: list):
        restaurant_users = [(s.meal.restaurant, s.user) for s in selections if s.meal.restaurant.name != Restaurant.ADHOC_NAME]
        text = "*Current Selections*"
        blocks = [
             {"type": "section", "text": {"type": "mrkdwn", "text": text}},
             {"type": "divider"}
        ] + SlackSender._selections_entity_to_blocks(restaurant_users)

        adhoc_meal_users = [(s.meal, s.user) for s in selections if s.meal.restaurant.name == Restaurant.ADHOC_NAME]
        if adhoc_meal_users:
            blocks.extend(SlackSender._selections_entity_to_blocks(adhoc_meal_users))

        if self._selection_message is None:
            ts = self._api.message(self._lunch_channel, text, blocks)
        else:
            ts = self._api.update_message(self._lunch_channel, self._selection_message, text, blocks)
        self._selection_message = ts

    @staticmethod
    def _selections_entity_to_blocks(entity_users: list):
        key_fun = lambda ent_user: ent_user[0].name
        entity_users_grouped = [
            (entity, {entity_user[1].slack_id for entity_user in entity_users})
            for entity, entity_users
            in itertools.groupby(sorted(entity_users, key=key_fun), key_fun)
        ]
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{entity_name} _({len(user_ids)})_\n" + ", ".join([f"<@{uid}>" for uid in user_ids])
                }
            } for entity_name, user_ids in
            sorted(entity_users_grouped, key=lambda entity_users: (-len(entity_users[1]), entity_users[0]))
        ]

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
    def _meal_voting_block(meal: Meal, button: str, action_prefix: str, extra_info: str = None,
                           highlighted_words: list = None) -> dict:
        block = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": SlackSender._meal_text(meal, extra_info, highlighted_words)}
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
    def _meal_text(meal: Meal, extra_info: str, highlighted_words: list = None) -> str:
        value = ""
        if meal.price:
            value += " _" + str(meal.price) + "_"
        if extra_info:
            value += ", " + extra_info

        if highlighted_words:
            meal_name = ' '.join(
                f'*{w}*' if any(hw in unidecode(w).lower() for hw in highlighted_words) else w
                for w in meal.name.split()
            )
        else:
            meal_name = meal.name

        return f"{meal_name}{value}"
