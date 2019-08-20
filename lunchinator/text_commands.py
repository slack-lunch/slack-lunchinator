from datetime import date

from lunchinator.commands import Commands
from slack_api.sender import SlackSender
import re


class TextCommands:

    def __init__(self):
        self._restaurants = sorted(Commands.all_restaurants(), key=lambda r: r.name.lower())

    def select_meals(self, user_id: str, text: str):
        user = Commands.user(user_id, allow_create=False)
        if user:
            user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
        else:
            user_meals_pks = None

        meal_groups = TextCommands.split_by_whitespace(text)
        if not re.compile('[0-9]').match(text):
            blocks = []
            for restaurant_prefix in meal_groups:
                restaurant = self._restaurant_by_prefix(restaurant_prefix)
                if restaurant:
                    meals = restaurant.meals.filter(date=date.today()).all()
                    blocks.extend(SlackSender.restaurant_meal_blocks(restaurant, meals, user_meals_pks))
                else:
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"`{restaurant_prefix}` not found"}})

            return {
                "response_type": "ephemeral",
                "text": "*Restaurant Offers*",
                "blocks": blocks
            }
        # self.select_meals(user_id, meal_ids, recommended=False)

    def select_restaurants(self, user_id: str, text: str):
        restaurant_ids = TextCommands.split_by_whitespace(text)
        # self.select_restaurants(user_id, restaurant_ids)

    def erase_meals(self, user_id: str, text: str):
        meal_groups = TextCommands.split_by_whitespace(text)

    def erase_restaurants(self, user_id: str, text: str):
        restaurant_ids = TextCommands.split_by_whitespace(text)

    def list_restaurants(self, userid: str):
        user = Commands.user(userid, allow_create=False)
        if user:
            selected_restaurants_ids = {r.pk for r in user.favorite_restaurants.all()}
        else:
            selected_restaurants_ids = None

        text = "*Available Restaurants*"
        return {
            "response_type": "ephemeral",
            "text": text,
            "blocks": SlackSender.restaurant_blocks(text, Commands.all_restaurants(), selected_restaurants_ids)
        }

    @staticmethod
    def split_by_whitespace(s: str):
        return s.split()

    def _restaurant_by_prefix(self, prefix):
        p = prefix.lower()
        for r in self._restaurants:
            if r.name.lower().startswith(p):
                return r
        return None
