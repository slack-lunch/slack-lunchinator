import bs4
from requests import get


from lunchinator.models import Meal, Restaurant


class AbstractParser:
    URL = None
    ENCODING = 'UTF-8'
    HEADERS = {
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3814.0 Safari/537.36',
        'accept-encoding': 'gzip, deflate, br'
    }

    WEEK_DAYS_CZ = [
        'Pondělí',
        'Úterý',
        'Středa',
        'Čtvrtek',
        'Pátek'
    ]

    def __init__(self):
        self._restaurant = None

    def get_meals(self, restaurant: Restaurant):
        """Parses meals from given URL.

            :returns list of meals (not saved to db yet).
        """
        raise NotImplementedError

    def _get_text(self):
        req = get(self.URL, headers=self.HEADERS)
        req.encoding = self.ENCODING
        return req.text

    def _get_soup(self):
        html = self._get_text()
        return bs4.BeautifulSoup(html, features="html.parser")

    def _build_meal(self, name, price, restaurant: Restaurant):
        return Meal(name=name, price=price, restaurant=restaurant)


class FixedOfferParser(AbstractParser):
    def get_meals(self, restaurant: Restaurant):
        return [self._build_meal(f'Standard offer of {restaurant.name}', None, restaurant)]
