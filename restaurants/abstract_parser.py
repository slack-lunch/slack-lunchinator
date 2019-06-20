import bs4
from requests import get

from lunchinator.models import Meal, Restaurant


class AbstractParser:
    URL = None
    RESTAURANT_NAME = None
    ENCODING = 'UTF-8'

    def __init__(self):
        self._restaurant = None

    def get_meals(self):
        """Parses meals from given URL.

            :returns list of meals (not saved to db yet).
        """
        raise NotImplementedError

    def _get_soup(self):
        user_agent = {'User-agent': 'Mozilla/5.0'}
        req = get(self.URL, headers=user_agent)
        req.encoding = self.ENCODING
        html = req.text
        return bs4.BeautifulSoup(html, features="html.parser")

    def _build_meal(self, name, price):
        return Meal(name=name, price=price, restaurant=self.restaurant)

    @property
    def restaurant(self):
        if self._restaurant is None:
            self._restaurant = Restaurant.objects.get(provider=self.__class__.__name__)
        return self._restaurant
