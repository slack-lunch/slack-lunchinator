from datetime import date
from itertools import chain

from lunchinator.commands import Commands
from lunchinator.models import Selection, Meal, User, Restaurant
from recommender.recommender import Recommender
from slack_api.sender import SlackSender
import re
from django.http import HttpResponse
import json

from unidecode import unidecode


class TextCommands:

    def __init__(self, sender: SlackSender):
        self._sender = sender
        self._restaurants = sorted(Commands.all_restaurants(), key=lambda r: r.name.lower())
        self._re_some_digit = re.compile('[0-9]')
        self._re_meal = re.compile(r'([^\s0-9,]+)([0-9,]+)')

    def lunch_cmd(self, user_id: str, text: str, response_url: str):
        if not text:
            return TextCommands._help()
        elif text.startswith("recommend"):
            if len(text) > 9:
                try:
                    count = int(text[9:].strip())
                    if count <= 0 or count > 20:
                        raise ValueError("Invalid recommendation count")
                except ValueError:
                    return {"response_type": "ephemeral", "text": "Invalid count to recommend."}
            else:
                count = 5
            return self._recommend_meals(user_id, count)
        elif text.startswith("erase"):
            return self._erase_meals(user_id, text[5:].strip())
        elif text.startswith("create"):
            return ResponseWithAction({"response_type": "ephemeral", "text": "processing..."},
                                      lambda: self._create_meal(user_id, text[6:].strip(), response_url))
        elif text.startswith("search"):
            cmd, query = text.split(maxsplit=1)
            return self._search_meals(user_id, query)
        else:
            return self._select_meals(user_id, text)

    def lunch_rest_cmd(self, user_id: str, text: str):
        if not text:
            return self._list_restaurants(user_id)
        elif text.startswith("erase"):
            return self._erase_restaurants(user_id, text[5:].strip())
        else:
            return self._select_restaurants(user_id, text)

    def _select_meals(self, user_id: str, text: str):
        user = Commands.user(user_id, allow_create=False)
        meal_groups = TextCommands._split_by_whitespace(text)

        if self._re_some_digit.search(text):
            if user is None:
                return {"response_type": "ephemeral", "text": "You cannot vote when you have not joined Lunchinator.\n"
                                                              "Do so e.g. by selecting restaurants."}

            try:
                meals = [meal for meal_group in meal_groups for meal in self._parse_meals(meal_group)]
            except ValueError as e:
                return {"response_type": "ephemeral", "text": f"Parsing failed: {e}"}

            for meal in meals:
                selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
                selection.recommended = False
                selection.save()

            self._sender.post_selections(Commands.today_selections())
            return {"response_type": "ephemeral", "text": "voted"}

        else:
            blocks = []
            if user:
                user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
            else:
                user_meals_pks = None

            for restaurant_prefix in meal_groups:
                restaurant = self._restaurant_by_prefix(restaurant_prefix)
                if restaurant:
                    meals = restaurant.meals.filter(date=date.today()).all()
                    blocks.extend(SlackSender.restaurant_meal_blocks(restaurant, meals, user_meals_pks))
                else:
                    blocks.append(
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"`{restaurant_prefix}` not found"}}
                    )

            return {
                "response_type": "ephemeral",
                "text": "*Restaurant Offers*",
                "blocks": blocks
            }

    def _select_restaurants(self, user_id: str, text: str):
        user = Commands.user(user_id, allow_create=True)

        for r_prefix in TextCommands._split_by_whitespace(text):
            restaurant = self._restaurant_by_prefix(r_prefix)
            if restaurant is None:
                return {"type": "section", "text": {"type": "mrkdwn", "text": f"`{r_prefix}` not found"}}
            user.favorite_restaurants.add(restaurant)

        user.enabled = True
        user.save()

        # self._sender.send_meals(user, Commands.all_restaurants()) # TODO ???
        return self._list_restaurants(user_id)

    def _erase_meals(self, user_id: str, text: str):
        meal_groups = TextCommands._split_by_whitespace(text)
        user = Commands.user(user_id, allow_create=False)
        if user is None:
            return {"response_type": "ephemeral", "text": "You cannot erase when you have not joined Lunchinator.\n"
                                                          "Do so e.g. by selecting restaurants."}

        try:
            meals = [meal for meal_group in meal_groups for meal in self._parse_meals(meal_group)]
        except ValueError as e:
            return {"response_type": "ephemeral", "text": f"Parsing failed: {e}"}

        for meal in meals:
            selections = user.selections.filter(meal=meal)
            selections.delete()

        self._sender.post_selections(Commands.today_selections())
        return {"response_type": "ephemeral", "text": "erased"}

    def _erase_restaurants(self, user_id: str, text: str):
        user = Commands.user(user_id, allow_create=False)
        if user is None:
            return {"response_type": "ephemeral", "text": "You cannot erase when you have not joined Lunchinator.\n"
                                                          "Do so e.g. by selecting restaurants."}

        for r_prefix in TextCommands._split_by_whitespace(text):
            restaurant = self._restaurant_by_prefix(r_prefix)
            if restaurant is None:
                return {"type": "section", "text": {"type": "mrkdwn", "text": f"`{r_prefix}` not found"}}
            user.favorite_restaurants.remove(restaurant)

        user.save()

        # self._sender.send_meals(user, Commands.all_restaurants()) # TODO ???
        return self._list_restaurants(user_id)

    def _list_restaurants(self, user_id: str):
        user = Commands.user(user_id, allow_create=False)
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

    def _recommend_meals(self, user_id: str, count: int):
        user = Commands.user(user_id, allow_create=False)
        rec = Recommender(user)

        if user:
            user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
        else:
            user_meals_pks = None

        text = "*Recommendations*"
        return {
            "response_type": "ephemeral",
            "text": text,
            "blocks": SlackSender.recommendation_blocks(text, rec.get_recommendations(count), user_meals_pks)
        }

    def _create_meal(self, user_id: str, meal_name: str, response_url: str):
        user = Commands.user(user_id)
        restaurant = \
            Restaurant.objects.get_or_create(name=Restaurant.ADHOC_NAME, provider='None', url='', enabled=False)[0]
        meal = Meal.objects.create(name=meal_name, price=None, restaurant=restaurant)
        Selection.objects.create(meal=meal, user=user, recommended=False)

        self._sender.post_selections(Commands.today_selections())
        for u in User.objects.filter(enabled=True).all():
            self._sender.send_meals(u, [restaurant])

        self._sender._api.send_response(response_url, {"response_type": "ephemeral", "text": "created and voted for"})

    @staticmethod
    def _search_meals(user_id, query):
        user = Commands.user(user_id)
        if user:
            user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
        else:
            user_meals_pks = None

        user_restaurants = user.favorite_restaurants.all()
        other_restaurants = Restaurant.objects.exclude(id_in=[r.id for r in user_restaurants]).all()

        query_words = unidecode(query).lower().split()

        found_meals = []

        for rest in chain(user_restaurants, other_restaurants):
            for meal in rest.meals.all():
                normalized_name = unidecode(meal.name).lower()
                if any(w in normalized_name for w in query_words):
                    found_meals.append(meal)

        text = "*Found meals*" if found_meals else f"*No {query} for you today :(*"
        return {
            "response_type": "ephemeral",
            "text": text,
            "blocks": SlackSender.search_blocks(text, query_words, found_meals, user_meals_pks)
        }

    @staticmethod
    def _help():
        return {
            "response_type": "ephemeral",
            "text": "Welcome to Lunchinator!\n"
                    "* `/lunch` is for voting (`/lunch A3 B5`), or recommending (`/lunch recommend 6`).\n"
                    "* If you skip numbers in voting (`/lunch A B`), only the restaurant offers are printed,"
                    " and no voting takes place.\n"
                    "* `/lunch erase A2 B7` erases your selection today.\n"
                    "* There is also `/lunchrest` for "
                    "printing (`/lunchrest`) or selecting (`/lunchrest A B`) your favourite restaurants,"
                    " or clearing them (`/lunchrest erase A B`).\n"
                    "* The letters for specifying a restaurant can be any prefix of the restaurant name"
                    " (first matching wins).\n"
                    "* The numbers for specifying meals are their indices within the restaurant's today's offer"
                    " (1-based).\n"
                    "* `/lunch create order sushi` creates ad-hoc meal if to vote.\n"
                    "* `/lunch search lasagna losos` searches for meals that have 'lasagna' and/or 'losos' in them."
                    " First it displays meals from your selected restaurants and then from all the others."
        }

    @staticmethod
    def _split_by_whitespace(s: str):
        return s.split()

    def _restaurant_by_prefix(self, prefix):
        p = prefix.lower()
        for r in self._restaurants:
            if r.name.lower().startswith(p):
                return r
        return None

    def _parse_meals(self, meal: str):
        match = self._re_meal.fullmatch(meal)
        if not match:
            raise ValueError("Invalid syntax")

        restaurant = self._restaurant_by_prefix(match.group(1))
        if not restaurant:
            raise ValueError(f"`{match.group(1)}` not found")

        meals = []
        all_meals = restaurant.meals.filter(date=date.today()).all()
        for index in match.group(2).split(','):
            if not index:
                raise ValueError("Invalid syntax")
            idx = int(index) - 1
            if idx not in range(len(all_meals)):
                raise ValueError("Index out of range")
            meals.append(all_meals[idx])

        return meals


class ResponseWithAction(HttpResponse):

    def __init__(self, resp, action):
        super().__init__(json.dumps(resp), content_type="application/json")
        self._action = action

    def close(self):
        super(ResponseWithAction, self).close()
        self._action()
