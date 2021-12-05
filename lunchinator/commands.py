from datetime import date

from recommender.recommender import Recommender
from lunchinator.models import User, Selection, Meal, Restaurant
from lunchinator import SlackUser
from slack_api.sender import SlackSender
from restaurants import PARSERS
import traceback
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned


class Commands:

    def __init__(self, sender: SlackSender):
        self._sender = sender
        self._recommendations = {}

    def select_meal(self, slack_user: SlackUser, meal_id: str, recommended: bool):
        user = Commands.user(slack_user)
        restaurants = set()

        meal = Meal.objects.get(pk=meal_id)
        restaurants.add(meal.restaurant)
        selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
        selection.recommended = recommended
        selection.save()

        if recommended:
            self._sender.print_recommendation(self._recommendations[user.slack_id], user)
        self._sender.send_meals(user, list(restaurants))
        self._sender.post_selections(Commands.today_selections())

    def erase_meal(self, slack_user: SlackUser, meal_id: str, recommended: bool):
        user = Commands.user(slack_user)
        restaurants = set()

        selections = user.selections.filter(meal__date=date.today(), meal__pk=meal_id)
        restaurants.update({selection.meal.restaurant for selection in selections})
        selections.delete()

        if recommended:
            self._sender.print_recommendation(self._recommendations[user.slack_id], user)
        self._sender.post_selections(Commands.today_selections())
        self.print_selection(slack_user)
        self._sender.send_meals(user, list(restaurants))

    def print_selection(self, slack_user: SlackUser):
        user = Commands.user(slack_user)
        meals = [s.meal for s in user.selections.filter(meal__date=date.today()).all()]
        self._sender.post_selection(user.slack_id, meals)

    def recommend_meals(self, slack_user: SlackUser, number: int):
        user = Commands.user(slack_user)
        rec = Recommender(user)
        recs = rec.get_recommendations(number)
        self._recommendations[user.slack_id] = recs
        self._sender.print_recommendation(recs, user)

    def list_restaurants(self, slack_user: SlackUser):
        user = Commands.user(slack_user)
        self._sender.print_restaurants(user.slack_id, Commands.all_restaurants(), user.all_favorite_restaurants())

    def select_restaurant(self, slack_user: SlackUser, restaurant_id: str):
        user = Commands.user(slack_user)

        restaurant = Restaurant.objects.get(pk=restaurant_id)
        user.favorite_restaurants.add(restaurant)

        user.enabled = True
        user.save()
        self._sender.print_restaurants(user.slack_id, Commands.all_restaurants(), user.all_favorite_restaurants())
        self._sender.send_meals(user, Commands.all_restaurants())

    def erase_restaurant(self, slack_user: SlackUser, restaurant_id: str):
        user = Commands.user(slack_user)

        user.favorite_restaurants.remove(Restaurant.objects.get(pk=restaurant_id))

        user.save()
        self._sender.print_restaurants(user.slack_id, Commands.all_restaurants(), user.all_favorite_restaurants())
        self._sender.send_meals(user, Commands.all_restaurants())

    def quit(self, slack_user: SlackUser):
        user = Commands.user(slack_user)
        user.enabled = False
        user.save()
        self._sender.message(user.slack_id, "Bye")

    def parse_and_send_meals(self):
        meal_cnt = Meal.objects.filter(date=date.today()).count()
        print(f"Read {meal_cnt} meals from DB")

        restaurants = Commands.all_restaurants()

        if meal_cnt == 0:
            meals = {r: Commands._parse(r) for r in restaurants}
            print(f"Parsed {sum(map(len, meals.values()))} meals from {len(meals)} restaurant")
            for ms in meals.values():
                for m in ms:
                    m.save()

        self._sender.reset()
        self._recommendations = {}
        for user in User.objects.filter(enabled=True).all():
            self._sender.send_meals(user, restaurants)

    def parse_and_send_meals_for_restaurant(self, restaurant_name: str) -> str:
        try:
            restaurant = Restaurant.objects.get(name=restaurant_name)
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            return 'Restaurant does not exist or is not unique'
        meal_cnt = Meal.objects.filter(date=date.today(), restaurant=restaurant).count()
        print(f"Read {meal_cnt} meals from DB for {restaurant}")

        if meal_cnt == 0:
            meals = Commands._parse(restaurant)
            print(f"Parsed {len(meals)} meals from {restaurant}")
            for m in meals:
                m.save()

        for user in User.objects.filter(enabled=True).all():
            self._sender.send_meals(user, [restaurant])
        return ''

    @staticmethod
    def all_restaurants():
        return Restaurant.objects.filter(enabled=True).all()

    @staticmethod
    def today_selections() -> List[Selection]:
        return Selection.objects.filter(meal__date=date.today()).all()

    @staticmethod
    def user(slack_user: SlackUser, allow_create: bool = True) -> Optional[User]:
        if allow_create:
            user = User.objects.get_or_create(slack_id=slack_user.user_id)[0]
        else:
            try:
                user = User.objects.get(slack_id=slack_user.user_id)
            except ObjectDoesNotExist:
                return None
        if slack_user.name is not None and user.name is None:
            user.name = slack_user.name
            user.save()
        return user

    @staticmethod
    def _parse(restaurant: Restaurant) -> list:
        try:
            return PARSERS[restaurant.provider]().get_meals(restaurant)
        except Exception as ex:
            print("Failed parsing " + str(restaurant))
            print(ex)
            traceback.print_exc()
            return []
