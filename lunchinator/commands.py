from datetime import date
from slack_api.sender import SlackSender
from lunchinator.models import User, Selection, Meal, Restaurant


class Commands:
    __instance = None

    def __new__(cls):
        if Commands.__instance is None:
            Commands.__instance = object.__new__(cls)
        return Commands.__instance

    def __init__(self):
        self._sender = SlackSender()

    def select_meals(self, userid: str, meal_ids: list, recommended: bool):
        user = User.objects.get(slack_id=userid)
        if user is None:
            user = User(slack_id=userid).save()

        for m_id in meal_ids:
            meal = Meal.objects.get(pk=m_id)
            selection = Selection.objects.get(meal=meal, user=user)
            if selection is None:
                selection = Selection(meal=meal, user=user)
            selection.recommended = recommended
            selection.save()

        self._sender.post_selections()

    def select_restaurants(self, userid: str, restaurant_ids: list):
        user = self._user(userid)

        for r_id in restaurant_ids:
            restaurant = Restaurant.objects.get(pk=r_id)
            user.favorite_restaurants.add(restaurant)

        self._sender.send_meals(user)

    def erase(self, userid: str):
        user = self._user(userid)
        Selection.objects.filter(meal__date=date.today(), user=user).clear()
        self._sender.post_selections()

    def recommend(self, userid: str, number: int):
        self._sender.print_recommendation(self._get_recommendations(number, userid), userid)

    def list_restaurants(self, userid: str):
        user = self._user(userid)
        self._sender.print_restaurants(userid, Restaurant.objects.all(), user.favorite_restaurants.all())

    def clear_restaurants(self, userid):
        user = self._user(userid)
        user.favorite_restaurants.clear()
        self._sender.print_restaurants(userid, Restaurant.objects.all(), [])

    def _get_recommendations(self, number: int, userid: str) -> list:
        return []

    def _user(self, userid: str) -> User:
        user = User.objects.get(slack_id=userid)
        if user is None:
            user = User(slack_id=userid).save()
        return user
