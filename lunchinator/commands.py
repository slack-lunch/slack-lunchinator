from datetime import date
from slack_api.sender import SlackSender
from lunchinator.models import User, Selection, Meal, Restaurant
from slack_api.singleton import Singleton


class Commands(metaclass=Singleton):

    def __init__(self):
        self._sender = SlackSender()

    def select_meals(self, userid: str, meal_ids: list, recommended: bool):
        user = User.objects.get_or_create(slack_id=userid)[0]

        for m_id in meal_ids:
            meal = Meal.objects.get(pk=m_id)
            selection = Selection.objects.get_or_create(meal=meal, user=user)[0]
            selection.recommended = recommended
            selection.save()

        self._sender.post_selections()

    def select_restaurants(self, userid: str, restaurant_ids: list):
        user = User.objects.get_or_create(slack_id=userid)[0]

        for r_id in restaurant_ids:
            restaurant = Restaurant.objects.get(pk=r_id)
            user.favorite_restaurants.add(restaurant)

        user.save()
        self._sender.send_meals(user)

    def erase(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        Selection.objects.filter(meal__date=date.today(), user=user.pk).delete()
        self._sender.post_selections()

    def recommend(self, userid: str, number: int):
        self._sender.print_recommendation(self._get_recommendations(number, userid), userid)

    def list_restaurants(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        self._sender.print_restaurants(userid, Restaurant.objects.all(), user.favorite_restaurants.all())

    def clear_restaurants(self, userid: str):
        user = User.objects.get_or_create(slack_id=userid)[0]
        user.favorite_restaurants.all().delete()
        self._sender.print_restaurants(userid, Restaurant.objects.all(), [])

    def _get_recommendations(self, number: int, userid: str) -> list:
        return []
