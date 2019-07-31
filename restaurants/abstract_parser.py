import bs4
from requests import get
import pycurl
from io import BytesIO

from lunchinator.models import Meal, Restaurant


class AbstractParser:
    URL = None
    RESTAURANT_NAME = None
    ENCODING = 'UTF-8'
    HEADER_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3814.0 Safari/537.36'
    HEADER_ACCEPT_ENCODING = 'gzip, deflate, br'
    OTHER_HEADERS = {
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8'
    }

    def __init__(self):
        self._restaurant = None

    def get_meals(self):
        """Parses meals from given URL.

            :returns list of meals (not saved to db yet).
        """
        raise NotImplementedError

    def _get_text(self):
        req = get(self.URL, headers={
            **self.OTHER_HEADERS,
            'user-agent': self.HEADER_USER_AGENT,
            'accept-encoding': self.HEADER_ACCEPT_ENCODING
        })
        req.encoding = self.ENCODING
        return req.text

    def _get_text_by_curl(self):
        buffer = BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL, self.URL)
        c.setopt(c.WRITEDATA, buffer)
        c.setopt(c.HTTP_VERSION, c.CURL_HTTP_VERSION_2_0)
        c.setopt(c.USERAGENT, self.HEADER_USER_AGENT)
        c.setopt(c.ACCEPT_ENCODING, self.HEADER_ACCEPT_ENCODING)
        c.setopt(c.HTTPHEADER, [f"{key}: {value}" for key, value in self.OTHER_HEADERS.items()])
        c.perform()
        c.close()

        body = buffer.getvalue()
        return body.decode(self.ENCODING)

    def _get_soup(self):
        html = self._get_text()
        return bs4.BeautifulSoup(html, features="html.parser")

    def _build_meal(self, name, price):
        return Meal(name=name, price=price, restaurant=self.restaurant)

    @property
    def restaurant(self):
        if self._restaurant is None:
            self._restaurant = Restaurant.objects.get(provider=self.__class__.__name__)
        return self._restaurant
