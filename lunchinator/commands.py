from datetime import date

from recommender.recommender import Recommender
from lunchinator.models import User, Selection, Meal, Restaurant
from slack_api.sender import SlackSender
from restaurants import PARSERS
import traceback
from django.core.exceptions import ObjectDoesNotExist


class Commands:

    def __init__(self, sender: SlackSender):
        self._sender = sender

    def select_meals(self, userid: str, meal_ids: list, recommended: bool):
        user = Commands.user(userid)
        restaurants = set()

        for m_id in meal_ids:
            meal = Meal.objects.get(pk=m_id)
            restaurants.add(meal.restaurant)
            selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
            selection.recommended = recommended
            selection.save()

        self._sender.send_meals(user, list(restaurants))
        self._sender.post_selections(Commands.today_selections())

    def erase_meals(self, userid: str, meal_ids: list):
        user = Commands.user(userid)
        restaurants = set()

        for m_id in meal_ids:
            selections = user.selections.filter(meal__date=date.today(), meal__pk=m_id)
            restaurants.update({selection.meal.restaurant for selection in selections})
            selections.delete()

        self._sender.post_selections(Commands.today_selections())
        self.print_selection(userid)
        self._sender.send_meals(user, list(restaurants))

    def print_selection(self, userid: str):
        user = Commands.user(userid)
        meals = [s.meal for s in user.selections.filter(meal__date=date.today()).all()]
        self._sender.post_selection(user.slack_id, meals)

    def recommend_meals(self, userid: str, number: int):
        user = Commands.user(userid)
        rec = Recommender(user)
        self._sender.print_recommendation(rec.get_recommendations(number), user)

    def list_restaurants(self, userid: str):
        user = Commands.user(userid)
        self._sender.print_restaurants(userid, Commands.all_restaurants(), user.favorite_restaurants.all())

    def select_restaurants(self, userid: str, restaurant_ids: list):
        user = Commands.user(userid)

        for r_id in restaurant_ids:
            restaurant = Restaurant.objects.get(pk=r_id)
            user.favorite_restaurants.add(restaurant)

        user.enabled = True
        user.save()
        self._sender.print_restaurants(user.slack_id, Commands.all_restaurants(), user.favorite_restaurants.all())
        self._sender.send_meals(user, Commands.all_restaurants())

    def erase_restaurants(self, userid: str, restaurant_ids: list):
        user = Commands.user(userid)

        for r_id in restaurant_ids:
            user.favorite_restaurants.remove(Restaurant.objects.get(pk=r_id))

        user.save()
        self._sender.print_restaurants(user.slack_id, Commands.all_restaurants(), user.favorite_restaurants.all())
        self._sender.send_meals(user, Commands.all_restaurants())

    def quit(self, userid: str):
        user = Commands.user(userid)
        user.enabled = False
        user.save()
        self._sender.message(userid, "Bye")

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
        for user in User.objects.filter(enabled=True).all():
            self._sender.send_meals(user, restaurants)

    @staticmethod
    def all_restaurants():
        return Restaurant.objects.filter(enabled=True).all()

    @staticmethod
    def today_selections():
        return Selection.objects.filter(meal__date=date.today()).all()

    @staticmethod
    def user(userid: str, allow_create: bool = True):
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
            return PARSERS[restaurant.provider]().get_meals(restaurant)
        except Exception as ex:
            print("Failed parsing " + str(restaurant))
            print(ex)
            traceback.print_exc()
            return []
