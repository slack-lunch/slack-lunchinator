import re
from datetime import datetime
from io import BytesIO

from pytesseract import pytesseract

from lunchinator.models import Restaurant
from restaurants.abstract_parser import AbstractParser

from contextlib import contextmanager
import tempfile
import requests

from pdfminer.high_level import extract_text_to_fp

from PIL import Image

from unidecode import unidecode
import html


class MenickaAbstractParser(AbstractParser):
    ENCODING = 'WINDOWS-1250'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()

        today_menu_div = soup.find('div', {'class': 'menicka'})

        meals = []

        for meal_li in today_menu_div.find_all('li'):
            name = meal_li.find('div', {'class': 'polozka'}).text
            try:
                price = float(meal_li.find("div", {'class': 'cena'}).text.split()[0])
            except (IndexError, AttributeError):
                price = 0.0
            meals.append(self._build_meal(name, price, restaurant))
        return meals


class EmpiriaParser(MenickaAbstractParser):
    URL = 'https://www.menicka.cz/2165-cafe-empiria.html'


class ObederiaParser(MenickaAbstractParser):
    URL = 'https://www.menicka.cz/5666-obederia.html'


class NolaParser(MenickaAbstractParser):
    # URL = 'https://www.restu.cz/nola-restaurant-a-cafe/menu/'
    URL = 'https://www.menicka.cz/4437-nola-restaurant--cafe.html'


class CoolnaParser(MenickaAbstractParser):
    # URL = 'https://www.coolnasy.cz/'
    URL = 'https://www.menicka.cz/1216-coolna.html'


class PotrefenaHusaParser(MenickaAbstractParser):
    # URL = 'http://www.potrefene-husy.cz/cz/pankrac-poledni-menu'
    URL = 'https://www.menicka.cz/3815-potrefena-husa-na-pankraci.html'


class CityTowerSodexoParser(AbstractParser):
    URL = 'http://citytower.portal.sodexo.cz/cs/uvod'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()

        meals = []

        for meal_td in soup.find_all('td', {'class': 'popisJidla'}):
            name = meal_td.text
            price_text = meal_td.find_next_sibling("td").text
            price = float(price_text.split()[0]) if price_text else None
            meals.append(self._build_meal(name, price, restaurant))
        return meals


class DiCarloParser(AbstractParser):
    URL = 'https://www.dicarlo.cz/pankrac/'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        daily_menu_div = soup.find('div', {'class': 'daily-menu-section__table'})

        meals = []

        for meal_td in daily_menu_div.find_all('td', {'class': 'food-menu__desc'}):
            name = meal_td.find('h3').text
            try:
                price = float(meal_td.find_next_sibling('td', {'class': 'food-menu__price'}).text.split()[0])
            except IndexError:
                continue
            meals.append(self._build_meal(name, price, restaurant))
        return meals


class EnterpriseParser(AbstractParser):
    URL = 'https://www.prague-catering.cz/provozovny/Enterprise-kantyna/Denni-menu-Enterprise/'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()

        meals = []
        pizza = False
        counter = 0
        start_of_day_menu = False
        for meal_tr in soup.find_all('tr'):
            if meal_tr.text.startswith('DENNÍ NABÍDKA'):
                start_of_day_menu = True
            if not start_of_day_menu:
                continue

            name_td, price_td = meal_tr.find_all('td')
            if len(name_td.find_all(re.compile('^h'))) > 0:
                pizza = "Pizza" in name_td.text
                counter = 0
                continue
            price_re = re.search('([0-9]+)', price_td.text)
            if price_re:
                price = price_re.group(1)
            else:
                price = None

            try:
                if (price is not None and not pizza) or (pizza and counter > 0 and counter % 2 == 0):
                    meals.append(self._build_meal(name_td.text, float(price) if price is not None else None, restaurant))
            except ValueError:
                pass
            else:
                counter += 1

        return meals


class CorleoneParser(AbstractParser):
    URL = 'https://www.corleone.cz/pizzeria-arkady/tydenni-nabidka'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        today = datetime.today()
        date = f'{today.day}.{today.month}.'

        meals = []

        day_tr = soup.find('th', text=lambda s: date in s).parent
        meal_tr = day_tr.find_next_sibling()
        while meal_tr and meal_tr.get('class')[0] != 'date':
            name_td, price_td = meal_tr.find_all('td')
            name = name_td.text
            price = float(price_td.find('u').text)
            meals.append(self._build_meal(name, price, restaurant))
            meal_tr = meal_tr.find_next_sibling()
        return meals


@contextmanager
def open_url(url):
    with tempfile.NamedTemporaryFile() as tfile:
        tfile.write(requests.get(url).content)
        tfile.flush()
        tfile.seek(0)
        yield tfile


class PerfectCanteenParser(AbstractParser):
    URL = 'http://menu.perfectcanteen.cz/pdf/27/cz/price/a3'

    WEEKLY_MENU_SECTIONS = [
        'PASTA FRESCA BAR',
        'CHEF´S SPECIAL',
        'PERFECT STEAK s omáčkou \\(.*\\)',
        'PŘÍLOHY'
    ]

    def _get_text(self):
        with open_url(self.URL) as menu_pdf, tempfile.NamedTemporaryFile() as out:
            extract_text_to_fp(menu_pdf, out)
            out.seek(0)
            return list(out)[0].decode('utf-8')

    @staticmethod
    def _extract_meal_and_price(s):
        regex = r'(.*) ([0-9]+)'
        name, price = re.search(regex, s).groups()
        name = re.search('(.+) {2}.*', name).group(1).strip()  # remove allergens
        return name, float(price)

    def _extract_meals_from_section(self, s, restaurant: Restaurant):
        meals = []
        for m in re.findall('(.*? [0-9]+) Kč', s):
            name, price = self._extract_meal_and_price(m)
            meals.append(self._build_meal(name, price, restaurant))
        return meals

    def _extract_todays_menu(self, s, restaurant: Restaurant):
        week_day = self.WEEK_DAYS_CZ[datetime.today().weekday()]
        todays_menu = re.search(f'{week_day}(.*)TÝDENNÍ NABÍDKA', s).group(1).split('Každý den')[0]
        return self._extract_meals_from_section(todays_menu, restaurant)

    def _extract_weekly_menu(self, s, restaurant: Restaurant):
        meals = []

        weekly_menu = re.search('TÝDENNÍ NABÍDKA(.*PŘÍLOHY)', s).group(1)
        for start, end in zip(self.WEEKLY_MENU_SECTIONS, self.WEEKLY_MENU_SECTIONS[1:]):
            try:
                section_meals = re.search(f'{start} *(.*){end}', weekly_menu).group(1)
                meals.extend(self._extract_meals_from_section(section_meals, restaurant))
            except AttributeError:
                pass
        return meals

    def get_meals(self, restaurant: Restaurant):
        text = self._get_text()
        meals = []
        meals.extend(self._extract_todays_menu(text, restaurant))
        meals.extend(self._extract_weekly_menu(text, restaurant))
        return meals


class HarrysRestaurantParser(AbstractParser):
    URL = 'http://www.harrysrestaurant.cz/poledni-menu'

    def _get_specialty(self, menu, restaurant: Restaurant):
        spec_idx = menu.index('Specialita šéfkuchaře pondělí — pátek')
        pond_inx = menu.index('Pondělí')

        return self._build_meal(' '.join(menu[spec_idx + 1:pond_inx]), None, restaurant)

    def _get_todays_menu(self, menu, restaurant: Restaurant):
        week_day_n = datetime.today().weekday()

        decoded_menu = list(map(unidecode, menu))
        decoded_weekdays = list(map(unidecode, self.WEEK_DAYS_CZ))

        week_day = decoded_weekdays[week_day_n]
        start_idx = decoded_menu.index(week_day) + 1

        try:
            next_week_day = decoded_weekdays[week_day_n + 1]
            end_idx = decoded_menu.index(next_week_day)
        except IndexError:
            # It's Friday, Friday
            # Gotta get down on Friday
            # Everybody's lookin' forward to the weekend, weekend
            end_idx = -1

        today_menu = menu[start_idx:end_idx]

        meals = []

        meal_parts = []
        for meal_part in today_menu:
            if meal_part.endswith('-'):
                *meal_part, price = meal_part.rsplit(' ', 1)  # meal_part might be empty if price is on a new line
                meal_parts.extend(meal_part)
                meals.append(self._build_meal(' '.join(meal_parts), int(price.split(',')[0]), restaurant))
                meal_parts = []
            else:
                meal_parts.append(meal_part)

        return meals

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        menu_img_url = soup.find('h4').find('img')['src']
        response = requests.get(menu_img_url)
        img = Image.open(BytesIO(response.content))
        menu_text = pytesseract.image_to_string(img, lang='ces')

        menu = re.compile(r"([^\s].*)", re.MULTILINE).findall(menu_text)

        meals = [self._get_specialty(menu, restaurant)]
        meals.extend(self._get_todays_menu(menu, restaurant))

        return meals


class PankrackyRynekParser(AbstractParser):
    URL = ''

    def get_meals(self, restaurant: Restaurant):
        pass


class GlobusParser(AbstractParser):
    URL = 'https://www.globus.cz/freshpankrac.html'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        today_menu_div = soup.find('div', {'class': 'FreshPage-menuItem--green'})
        meals = []

        for meal_div in today_menu_div.find_all('div', {'class': 'FreshPage-menuListItem'}):
            name = next(meal_div.stripped_strings)
            price_span = meal_div.find("span", {'class': 'FreshPage-menuListPrice'})
            if price_span:
                try:
                    price = float(price_span.text.split(html.unescape('&nbsp;'))[-1].split(',')[0].strip())
                except ValueError:
                    price = None
            else:
                price = None
            meals.append(self._build_meal(name, price, restaurant))

        return meals


class PolygonParser(AbstractParser):
    URL = 'http://www.polygon-canteen.cz/'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        obedy = soup.find('li', {'id': 'page_obedy'})
        meals = []
        week_day = self.WEEK_DAYS_CZ[datetime.today().weekday()]
        started = False
        for tr in obedy.find_all('tr'):
            if started:
                if any(wd in tr.text for wd in self.WEEK_DAYS_CZ):
                    break
                tds = tr.find_all('td')
                if len(tds) >= 4 and tds[1].text.strip() and tds[0].text.strip():
                    name = tds[1].text.strip()
                    try:
                        price = float(tds[3].text.strip().split()[0].strip())
                    except (ValueError, IndexError):
                        price = None

                    meals.append(self._build_meal(name, price, restaurant))
            else:
                if week_day in tr.text:
                    started = True

        return meals


class BramboryParser(AbstractParser):
    URL = 'https://www.bramborynapankraci.cz/'

    def get_meals(self, restaurant: Restaurant):
        soup = self._get_soup()
        menu = soup.find('div', {'class': 'denninabidka'})
        meals = []
        for food, price in zip(menu.find_all('h4', {'class': 'foodbox-item'}),
                               menu.find_all('span', {'class': 'price'})):
            try:
                price = float(price.text.strip().split(',', 1)[0])
            except Exception:
                price = 0.0
            meals.append(self._build_meal(food.text.strip(), price, restaurant))
        return meals
