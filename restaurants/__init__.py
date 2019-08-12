from restaurants.prague import \
    EmpiriaParser, ObederiaParser, NolaParser, CoolnaParser, PotrefenaHusaParser, \
    CityTowerSodexoParser, DiCarloParser, EnterpriseParser, CorleoneParser, \
    PankrackyRynekParser, PerfectCanteenParser, HarrysRestaurantParser

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
    # PankrackyRynekParser
]

PARSERS = {
    p.__name__: p
    for p in _PARSER_CLASSES
}
