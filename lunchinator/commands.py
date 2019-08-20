from datetime import date

from recommender.recommender import Recommender
from lunchinator.models import User, Selection, Meal, Restaurant
from lunchinator.text_parser import TextParser
from slack_api.sender import SlackSender
from restaurants import PARSERS
import traceback
import re
from django.core.exceptions import ObjectDoesNotExist


class Commands:

    def __init__(self, sender: SlackSender):
        self._sender = sender
        self._parser = TextParser(Commands._all_restaurants())

    def select_meals(self, userid: str, meal_ids: list, recommended: bool):
        user = Commands._user(userid)
        restaurants = set()

        for m_id in meal_ids:
            meal = Meal.objects.get(pk=m_id)
            restaurants.add(meal.restaurant)
            selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
            selection.recommended = recommended
            selection.save()

        self._sender.send_meals(user, list(restaurants))
        self._sender.post_selections(Commands._today_selections())

    def erase_meals(self, userid: str, meal_ids: list):
        user = Commands._user(userid)
        restaurants = set()

        for m_id in meal_ids:
            selections = user.selections.filter(meal__date=date.today(), meal__pk=m_id)
            restaurants.update({selection.meal.restaurant for selection in selections})
            selections.delete()

        self._sender.post_selections(Commands._today_selections())
        self.print_selection(userid)
        self._sender.send_meals(user, list(restaurants))

    def print_selection(self, userid: str):
        user = Commands._user(userid)
        meals = [s.meal for s in user.selections.filter(meal__date=date.today()).all()]
        self._sender.post_selection(user.slack_id, meals)

    def recommend_meals(self, userid: str, number: int):
        user = Commands._user(userid)
        rec = Recommender(user)
        self._sender.print_recommendation(rec.get_recommendations(number), user)

    def list_restaurants(self, userid: str):
        user = Commands._user(userid)
        self._sender.print_restaurants(userid, Commands._all_restaurants(), user.favorite_restaurants.all())

    def select_restaurants(self, userid: str, restaurant_ids: list):
        user = Commands._user(userid)

        for r_id in restaurant_ids:
            restaurant = Restaurant.objects.get(pk=r_id)
            user.favorite_restaurants.add(restaurant)

        user.enabled = True
        user.save()
        self._sender.print_restaurants(user.slack_id, Commands._all_restaurants(), user.favorite_restaurants.all())
        self._sender.send_meals(user, Commands._all_restaurants())

    def erase_restaurants(self, userid: str, restaurant_ids: list):
        user = Commands._user(userid)

        for r_id in restaurant_ids:
            user.favorite_restaurants.remove(Restaurant.objects.get(pk=r_id))

        user.save()
        self._sender.print_restaurants(user.slack_id, Commands._all_restaurants(), user.favorite_restaurants.all())
        self._sender.send_meals(user, Commands._all_restaurants())

    def quit(self, userid: str):
        user = Commands._user(userid)
        user.enabled = False
        user.save()
        self._sender.message(userid, "Bye")

    def parse_and_send_meals(self):
        meal_cnt = Meal.objects.filter(date=date.today()).count()
        print(f"Read {meal_cnt} meals from DB")

        restaurants = Commands._all_restaurants()

        if meal_cnt == 0:
            meals = {r: Commands._parse(r) for r in restaurants}
            print(f"Parsed {sum(map(len, meals.values()))} meals from {len(meals)} restaurant")
            for ms in meals.values():
                for m in ms:
                    m.save()

        self._sender.reset()
        for user in User.objects.filter(enabled=True).all():
            self._sender.send_meals(user, restaurants)

    def select_meals_by_text(self, user_id: str, text: str):
        user = Commands._user(user_id, allow_create=False)
        if user:
            user_meals_pks = {s.meal.pk for s in user.selections.filter(meal__date=date.today()).all()}
        else:
            user_meals_pks = None

        meal_groups = TextParser.split_by_whitespace(text)
        if not re.compile('[0-9]').match(text):
            blocks = []
            for restaurant_prefix in meal_groups:
                restaurant = self._parser.restaurant_by_prefix(restaurant_prefix)
                if restaurant:
                    meals = restaurant.meals.filter(date=date.today()).all()
                    blocks.extend(SlackSender.restaurant_meal_blocks(restaurant, meals, user_meals_pks))
                else:
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"`{restaurant_prefix}` not found"}})

            return {
                "response_type": "ephemeral",
                "text": "Restaurant offers",
                "blocks": blocks
            }
        # self.select_meals(user_id, meal_ids, recommended=False)

    def select_restaurants_by_text(self, user_id: str, text: str):
        restaurant_ids = TextParser.split_by_whitespace(text)
        # self.select_restaurants(user_id, restaurant_ids)

    def erase_meals_by_text(self, user_id: str, text: str):
        meal_groups = TextParser.split_by_whitespace(text)

    def erase_restaurants_by_text(self, user_id: str, text: str):
        restaurant_ids = TextParser.split_by_whitespace(text)

    @staticmethod
    def _all_restaurants():
        return Restaurant.objects.filter(enabled=True).all()

    @staticmethod
    def _today_selections():
        return Selection.objects.filter(meal__date=date.today()).all()

    @staticmethod
    def _user(userid: str, allow_create: bool = True):
        if allow_create:
            return User.objects.get_or_create(slack_id=userid)[0]
        else:
            try:
                return User.objects.get(slack_id=userid)
            except ObjectDoesNotExist:
                return None

    @staticmethod
    def _parse(restaurant: Restaurant) -> list:
        try:
            return PARSERS[restaurant.provider]().get_meals()
        except Exception as ex:
            print("Failed parsing " + str(restaurant))
            print(ex)
            traceback.print_exc()
            return []
