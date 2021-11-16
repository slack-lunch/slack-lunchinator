from restaurants.abstract_parser import FixedOfferParser
from restaurants.prague import \
    EmpiriaParser, ObederiaParser, NolaParser, CoolnaParser, PotrefenaHusaParser, \
    CityTowerSodexoParser, DiCarloParser, EnterpriseParser, CorleoneParser, \
    PankrackyRynekParser, PerfectCanteenParser, HarrysRestaurantParser, GlobusParser,\
    PolygonParser, BramboryParser

_PARSER_CLASSES = [
    EmpiriaParser,
    ObederiaParser,
    NolaParser,
    CoolnaParser,
    PotrefenaHusaParser,
    CityTowerSodexoParser,
    DiCarloParser,
    EnterpriseParser,
    CorleoneParser,
    PerfectCanteenParser,
    HarrysRestaurantParser,
    FixedOfferParser,
    GlobusParser,
    PolygonParser,
    BramboryParser
]

PARSERS = {
    p.__name__: p
    for p in _PARSER_CLASSES
}
