from restaurants.prague import \
    EmpiriaParser, ObederiaParser, NolaParser, CoolnaParser, PotrefenaHusaParser, \
    CityTowerSodexoParser, DiCarloParser, EnterpriseParser, CorleoneParser, \
    PankrackyRynekParser, PerfectCanteenParser

_PARSER_CLASSES = [
    (EmpiriaParser, 'emp'),
    (ObederiaParser, 'obd'),
    (NolaParser, 'nla'),
    (CoolnaParser, 'cln'),
    (PotrefenaHusaParser, 'ph'),
    (CityTowerSodexoParser, 'cts'),
    (DiCarloParser, 'dc'),
    (EnterpriseParser, 'ent'),
    (CorleoneParser, 'crl'),
    # (PankrackyRynekParser, ''),
    # (PerfectCanteenParser, '')
]

PARSERS = {
    p[0].__name__: p
    for p in _PARSER_CLASSES
}
