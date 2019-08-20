
class TextParser:

    def __init__(self, restaurants: list):
        self._restaurants = sorted(restaurants, key=lambda r: r.name.lower())

    @staticmethod
    def split_by_whitespace(s: str):
        return s.split()

    def restaurant_by_prefix(self, prefix):
        p = prefix.lower()
        for r in self._restaurants:
            if r.name.lower().startswith(p):
                return r
        return None
