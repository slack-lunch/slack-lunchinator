from restaurants.prague import \
    EmpiriaParser, ObederiaParser, NolaParser, CoolnaParser, PotrefenaHusaParser, \
    CityTowerSodexoParser, DiCarloParser, EnterpriseParser, CorleoneParser, \
    PankrackyRynekParser, PerfectCanteenParser

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
    # PankrackyRynekParser,
    # PerfectCanteenParser
]

PARSERS = {
    p.__name__: p
    for p in _PARSER_CLASSES
}
