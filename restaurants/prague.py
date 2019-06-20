from datetime import datetime

from restaurants.abstract_parser import AbstractParser


class MenickaAbstractParser(AbstractParser):
    ENCODING = 'WINDOWS-1250'

    def get_meals(self):
        soup = self._get_soup()

        today_menu_div = soup.find('div', {'class': 'menicka'})

        meals = []

        for meal_div in today_menu_div.find_all('div', {'class': lambda c: c.startswith('nabidka')}):
            name = meal_div.text
            try:
                price = float(meal_div.find_next_sibling("div").text.split()[0])
            except IndexError:
                price = 0.0
            meals.append((name, price))
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
    URL = 'http://citytower.portal.sodexo.cz/en/introduction'

    def get_meals(self):
        soup = self._get_soup()

        meals = []

        for meal_td in soup.find_all('td', {'class': 'popisJidla'}):
            name = meal_td.text
            price = float(meal_td.find_next_sibling("td").text.split()[0])
            meals.append(self._build_meal(name, price))
        return meals


class DiCarloParser(AbstractParser):
    URL = 'https://www.dicarlo.cz/pankrac/'

    def get_meals(self):
        soup = self._get_soup()
        daily_menu_div = soup.find('div', {'class': 'daily-menu-section__table'})

        meals = []

        for meal_td in daily_menu_div.find_all('td', {'class': 'food-menu__desc'}):
            name = meal_td.find('h3').text
            try:
                price = float(meal_td.find_next_sibling('td', {'class': 'food-menu__price'}).text.split()[0])
            except IndexError:
                continue
            meals.append(self._build_meal(name, price))
        return meals


class EnterpriseParser(AbstractParser):
    URL = 'https://www.zomato.com/cs/KantynaEnterprise/denní-menu'

    def get_meals(self):
        soup = self._get_soup()
        today_menu_div = soup.find('div', {'class': 'tmi-group'})
        for excl in today_menu_div.find_all('div', {'class': 'bold600'}):
            excl.extract()
        meals_divs = today_menu_div.find_all('div', {'class': 'tmi'})

        meals = []

        for meal_div in meals_divs[:-4:2]:
            name = meal_div.find('div', {'class': 'tmi-name'}).text.strip()
            price_text = meal_div.find('div', {'class': 'tmi-price'})
            price = float(price_text.text) if price_text else None
            meals.append(self._build_meal(name, price))
        return meals


class CorleoneParser(AbstractParser):
    URL = 'https://www.corleone.cz/pizzeria-arkady/tydenni-nabidka'

    def get_meals(self):
        soup = self._get_soup()
        today = datetime.today()
        date = f'{today.day}.{today.month}.'

        meals = []

        day_tr = soup.find('th', text=lambda s: date in s).parent
        meal_tr = day_tr.find_next_sibling()
        while meal_tr.get('class')[0] != 'date':
            name_td, price_td = meal_tr.find_all('td')
            name = name_td.text
            price = float(price_td.find('u').text)
            meals.append(self._build_meal(name, price))
            meal_tr = meal_tr.find_next_sibling()
        return meals


class PankrackyRynekParser(AbstractParser):
    URL = ''

    def get_meals(self):
        pass


class PerfectCanteenParser(AbstractParser):
    URL = ''

    def get_meals(self):
        pass
