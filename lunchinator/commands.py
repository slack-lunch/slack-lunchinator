from datetime import date

from recommender.recommender import Recommender
from lunchinator.models import User, Selection, Meal, Restaurant
from restaurants import PARSERS
import traceback


class Commands:

    def __init__(self, sender):
        self._sender = sender

    def select_meals(self, userid: str, meal_ids: list, recommended: bool):
        user = User.objects.get_or_create(slack_id=userid)[0]

        restaurants = set()
        for m_id in meal_ids:
            meal = Meal.objects.get(pk=m_id)
            restaurants.add(meal.restaurant)
            selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
            selection.recommended = recommended
            selection.save()

        self._sender.send_meals(user, list(restaurants))
        self._sender.post_selections(Selection.objects.filter(meal__date=date.today()).all())

    def erase_meals(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        user.selections.filter(meal__date=date.today()).delete()
        self._sender.post_selections(Selection.objects.filter(meal__date=date.today()).all())

    def print_selection(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        meals = [s.meal for s in user.selections.filter(meal__date=date.today()).all()]
        self._sender.post_selection(user.slack_id, meals)

    def recommend_meals(self, userid: str, number: int):
        user = User.objects.get_or_create(slack_id=userid)[0]
        rec = Recommender(user)
        self._sender.print_recommendation(rec.get_recommendations(number), user)

    def list_restaurants(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        self._sender.print_restaurants(userid, Restaurant.objects.filter(enabled=True).all(), user.favorite_restaurants.all())

    def select_restaurants(self, userid: str, restaurant_ids: list):
        user = User.objects.get_or_create(slack_id=userid)[0]

        for r_id in restaurant_ids:
            restaurant = Restaurant.objects.get(pk=r_id)
            user.favorite_restaurants.add(restaurant)

        user.enabled = True
        user.save()
        self._sender.print_restaurants(user.slack_id, Restaurant.objects.filter(enabled=True).all(), user.favorite_restaurants.all())
        self._sender.send_meals(user, Restaurant.objects.filter(enabled=True).all())

    def clear_restaurants(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        user.favorite_restaurants.clear()
        self._sender.print_restaurants(userid, Restaurant.objects.filter(enabled=True).all(), [])

    def quit(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        user.enabled = False
        user.save()
        self._sender.message(userid, "Bye")

    def parse_and_send_meals(self):
        meal_cnt = Meal.objects.filter(date=date.today()).count()
        print(f"Read {meal_cnt} meals from DB")

        restaurants = Restaurant.objects.filter(enabled=True).all()

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
    def _parse(restaurant: Restaurant) -> list:
        try:
            return PARSERS[restaurant.provider]().get_meals()
        except Exception as ex:
            print("Failed parsing " + str(restaurant))
            print(ex)
            traceback.print_exc()
            return []
