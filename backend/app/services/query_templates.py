"""
Template-based systematic query builder for Deliryo project.

Defines all segments, geographies, variable fill-ins, and query templates.
Generates queries via cartesian product — deterministic, zero AI cost.
AI expansion (gpt-4o-mini) kicks in only when templates are exhausted.
"""
from __future__ import annotations
import itertools
import re
from typing import Optional

# ============================================================
# SEGMENT DEFINITIONS
# Each segment has: priority, labels, variable pools, geos, templates
# All data sourced from tasks/deliryo/keywords_*.md
# ============================================================

SEGMENTS: dict[str, dict] = {

    # ── Segment 1: Real Estate ──────────────────────────────
    "real_estate": {
        "priority": 1,
        "label_ru": "Недвижимость",
        "label_en": "Real Estate",

        "vars": {
            "company_type_ru": [
                "агентство недвижимости", "риелтор", "брокер недвижимости",
                "агент недвижимости",
            ],
            "company_type_en": [
                "real estate agency", "real estate agent", "property broker",
                "realtor", "real estate broker",
            ],
            "service_ru": [
                "купить квартиру", "купить виллу", "купить апартаменты",
                "купить пентхаус", "инвестиции в недвижимость", "новостройки",
                "off-plan",
            ],
            "service_en": [
                "buy apartment", "buy villa", "buy property",
                "buy penthouse", "property investment", "off-plan",
                "new development",
            ],
            "property_type_ru": [
                "квартиру", "виллу", "апартаменты", "пентхаус", "кондо",
            ],
            "property_type_en": [
                "apartment", "villa", "penthouse", "condo", "property",
            ],
        },

        "geos": {
            "dubai": {
                "cities_ru": ["Дубай", "Абу-Даби"],
                "cities_en": ["Dubai", "Abu Dhabi"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": ["Дубай Марина", "Палм Джумейра", "Даунтаун Дубай", "Business Bay", "JBR"],
                "districts_en": ["Dubai Marina", "Palm Jumeirah", "Downtown Dubai", "Business Bay", "JBR", "Dubai Hills", "Arabian Ranches", "JVC"],
            },
            "turkey": {
                "cities_ru": ["Анталья", "Стамбул", "Бодрум", "Аланья", "Фетхие", "Мерсин", "Калкан"],
                "cities_en": ["Antalya", "Istanbul", "Bodrum", "Alanya", "Fethiye", "Mersin"],
                "country_ru": "Турция",
                "country_en": "Turkey",
                "districts_ru": [],
                "districts_en": [],
            },
            "cyprus": {
                "cities_ru": ["Лимассол", "Пафос", "Ларнака", "Никосия", "Айя-Напа", "Протарас"],
                "cities_en": ["Limassol", "Paphos", "Larnaca", "Nicosia", "Ayia Napa"],
                "country_ru": "Кипр",
                "country_en": "Cyprus",
                "districts_ru": ["Северный Кипр"],
                "districts_en": ["North Cyprus"],
            },
            "thailand_bali": {
                "cities_ru": ["Пхукет", "Паттайя", "Бангкок", "Самуи", "Хуа Хин", "Краби"],
                "cities_en": ["Phuket", "Pattaya", "Bangkok", "Koh Samui", "Hua Hin", "Bali", "Canggu", "Seminyak", "Ubud"],
                "country_ru": "Таиланд",
                "country_en": "Thailand",
                "districts_ru": ["Бали", "Чангу", "Семиньяк", "Убуд"],
                "districts_en": ["Rawai", "Kata", "Kamala", "Uluwatu", "Jimbaran"],
            },
            "montenegro": {
                "cities_ru": ["Будва", "Тиват", "Котор", "Херцег-Нови", "Бар", "Подгорица"],
                "cities_en": ["Budva", "Tivat", "Kotor", "Herceg Novi", "Bar", "Podgorica"],
                "country_ru": "Черногория",
                "country_en": "Montenegro",
                "districts_ru": ["Порто Монтенегро", "Бечичи", "Петровац"],
                "districts_en": ["Porto Montenegro", "Becici", "Petrovac"],
            },
            "spain_portugal": {
                "cities_ru": ["Барселона", "Мадрид", "Марбелья", "Аликанте", "Малага", "Валенсия", "Лиссабон", "Порту"],
                "cities_en": ["Barcelona", "Madrid", "Marbella", "Alicante", "Malaga", "Valencia", "Lisbon", "Porto", "Algarve", "Cascais"],
                "country_ru": "Испания",
                "country_en": "Spain",
                "districts_ru": ["Коста дель Соль", "Коста Бланка", "Ибица", "Майорка", "Тенерифе", "Алгарве", "Мадейра"],
                "districts_en": ["Costa del Sol", "Costa Blanca", "Ibiza", "Mallorca", "Tenerife", "Algarve", "Madeira"],
            },
            "greece": {
                "cities_ru": ["Афины", "Салоники", "Крит", "Родос", "Корфу", "Миконос"],
                "cities_en": ["Athens", "Thessaloniki", "Crete", "Rhodes", "Corfu", "Mykonos", "Santorini", "Halkidiki"],
                "country_ru": "Греция",
                "country_en": "Greece",
                "districts_ru": [],
                "districts_en": [],
            },
            "global_aggregator": {
                "cities_ru": [],
                "cities_en": [],
                "country_ru": "за рубежом",
                "country_en": "abroad",
                "districts_ru": [],
                "districts_en": [],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{company_type} {country}",
            "купить {property_type} в {city}",
            "купить {property_type} {city}",
            "{company_type} {country} для россиян",
            "русский {company_type} {city}",
            "русскоязычный {company_type} {city}",
            "лучшие {company_type} {city} 2025",
            "рейтинг {company_type} {country}",
            "ВНЖ {country} через недвижимость",
            "недвижимость {city}",
            "недвижимость {district}",
            "инвестиции в недвижимость {city}",
            "{service} в {city}",
            "новостройки {city}",
            "off-plan {city}",
        ],
        "templates_en": [
            "{company_type} {city}",
            "{company_type} {country}",
            "buy {property_type} {city}",
            "Russian speaking {company_type} {city}",
            "top {company_type} {country} 2025",
            "{property_type} for sale {city}",
            "property investment {city}",
            "off-plan {city}",
            "new development {city}",
            "luxury {property_type} {city}",
            "Golden Visa {country} property",
            "{district} property",
            "{district} {property_type}",
        ],
    },

    # ── Segment 2: Investment ───────────────────────────────
    "investment": {
        "priority": 2,
        "label_ru": "Инвестиции",
        "label_en": "Investment",

        "vars": {
            "company_type_ru": [
                "инвестиционная компания", "управляющая компания", "инвестиционный советник",
                "инвестиционный бутик", "финансовый консультант", "брокер",
            ],
            "company_type_en": [
                "wealth management", "investment advisory", "asset management",
                "financial advisor", "portfolio manager",
            ],
            "service_ru": [
                "управление активами", "доверительное управление", "инвестиционный консалтинг",
                "private banking", "приватный банкинг", "инвестиции за рубежом",
                "зарубежные инвестиции", "финансовое планирование",
            ],
            "service_en": [
                "wealth management", "asset management", "private banking",
                "portfolio management", "investment advisory", "financial planning",
                "PPLI insurance",
            ],
        },

        "geos": {
            "moscow": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": ["Moscow"],
                "country_ru": "Россия",
                "country_en": "Russia",
                "districts_ru": [],
                "districts_en": [],
            },
            "switzerland": {
                "cities_ru": ["Цюрих", "Женева", "Лугано"],
                "cities_en": ["Zurich", "Geneva", "Lugano"],
                "country_ru": "Швейцария",
                "country_en": "Switzerland",
                "districts_ru": [],
                "districts_en": [],
            },
            "singapore": {
                "cities_ru": ["Сингапур"],
                "cities_en": ["Singapore"],
                "country_ru": "Сингапур",
                "country_en": "Singapore",
                "districts_ru": [],
                "districts_en": [],
            },
            "dubai_difc": {
                "cities_ru": ["Дубай"],
                "cities_en": ["Dubai", "Abu Dhabi"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": ["DIFC"],
                "districts_en": ["DIFC", "ADGM"],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{service} {city}",
            "{service} {country}",
            "лучшие {company_type} {city}",
            "{company_type} для состоятельных клиентов",
            "независимый финансовый советник {city}",
            "семейный офис {city}",
            "family office {city}",
        ],
        "templates_en": [
            "{company_type} {city}",
            "{service} {city}",
            "{service} {country}",
            "{company_type} Russian clients",
            "private banking {city}",
            "family office {city}",
            "multi family office {city}",
            "independent asset manager {country}",
            "DFSA regulated {city}",
        ],
    },

    # ── Segment 3: Legal ────────────────────────────────────
    "legal": {
        "priority": 3,
        "label_ru": "Юридические",
        "label_en": "Legal",

        "vars": {
            "company_type_ru": [
                "юридическая фирма", "юрист", "налоговый консультант",
                "юридическая компания", "адвокат",
            ],
            "company_type_en": [
                "law firm", "tax advisory", "corporate services",
                "company formation", "legal services",
            ],
            "service_ru": [
                "международное налоговое планирование", "юрист ВЭД",
                "структурирование активов", "создание траста",
                "M&A юрист", "оффшорная структура", "регистрация компании",
                "налоги при релокации", "КИК консультант",
            ],
            "service_en": [
                "company registration", "company formation", "tax planning",
                "corporate structuring", "offshore company formation",
                "trust formation", "holding company",
            ],
        },

        "geos": {
            "moscow": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": [],
                "country_ru": "Россия",
                "country_en": "Russia",
                "districts_ru": [],
                "districts_en": [],
            },
            "cyprus_legal": {
                "cities_ru": ["Лимассол", "Никосия"],
                "cities_en": ["Limassol", "Nicosia", "Paphos", "Larnaca"],
                "country_ru": "Кипр",
                "country_en": "Cyprus",
                "districts_ru": [],
                "districts_en": [],
            },
            "uae_legal": {
                "cities_ru": ["Дубай", "Абу-Даби"],
                "cities_en": ["Dubai", "Abu Dhabi"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": [],
                "districts_en": ["DMCC", "JAFZA", "DIFC", "ADGM", "RAK"],
            },
            "estonia": {
                "cities_ru": ["Таллинн"],
                "cities_en": ["Tallinn"],
                "country_ru": "Эстония",
                "country_en": "Estonia",
                "districts_ru": [],
                "districts_en": [],
            },
            "georgia_legal": {
                "cities_ru": ["Тбилиси", "Батуми"],
                "cities_en": ["Tbilisi", "Batumi"],
                "country_ru": "Грузия",
                "country_en": "Georgia",
                "districts_ru": [],
                "districts_en": [],
            },
            "serbia_legal": {
                "cities_ru": ["Белград"],
                "cities_en": ["Belgrade", "Novi Sad"],
                "country_ru": "Сербия",
                "country_en": "Serbia",
                "districts_ru": [],
                "districts_en": [],
            },
            "offshore": {
                "cities_ru": [],
                "cities_en": ["BVI", "Cayman Islands", "Seychelles", "Mauritius", "Panama"],
                "country_ru": "оффшор",
                "country_en": "offshore",
                "districts_ru": [],
                "districts_en": ["Nevis", "Jersey", "Guernsey", "Isle of Man", "Luxembourg", "Liechtenstein"],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{service} {city}",
            "{service} {country}",
            "регистрация компании {country}",
            "открыть компанию {country}",
            "налоговое планирование {country}",
            "юрист по международным налогам {city}",
            "юрист ВЭД {city}",
            "структурирование активов {city}",
        ],
        "templates_en": [
            "{company_type} {city}",
            "{service} {city}",
            "{service} {country}",
            "company formation {city}",
            "company registration {country}",
            "{district} company",
            "freezone company {city}",
            "tax advisory {country}",
            "offshore company {country}",
            "holding company {country}",
            "trust formation {country}",
        ],
    },

    # ── Segment 4: Migration ────────────────────────────────
    "migration": {
        "priority": 4,
        "label_ru": "Миграция",
        "label_en": "Migration",

        "vars": {
            "company_type_ru": [
                "иммиграционный консультант", "иммиграционное агентство",
                "визовое агентство", "релокационный сервис",
            ],
            "company_type_en": [
                "immigration consultant", "immigration agency",
                "Golden Visa agent", "CBI consultant", "relocation consultant",
            ],
            "service_ru": [
                "ВНЖ за инвестиции", "второе гражданство", "Golden Visa",
                "иммиграция", "релокация IT", "получить ВНЖ",
                "гражданство за инвестиции",
            ],
            "service_en": [
                "Golden Visa", "citizenship by investment", "residence by investment",
                "investor visa", "second passport", "EB-5 visa",
                "digital nomad visa",
            ],
        },

        "geos": {
            "spain_gv": {
                "cities_ru": [],
                "cities_en": ["Barcelona", "Madrid", "Marbella"],
                "country_ru": "Испания",
                "country_en": "Spain",
                "districts_ru": [],
                "districts_en": [],
            },
            "portugal_gv": {
                "cities_ru": [],
                "cities_en": ["Lisbon", "Porto", "Algarve"],
                "country_ru": "Португалия",
                "country_en": "Portugal",
                "districts_ru": [],
                "districts_en": [],
            },
            "greece_gv": {
                "cities_ru": [],
                "cities_en": ["Athens", "Crete", "Thessaloniki"],
                "country_ru": "Греция",
                "country_en": "Greece",
                "districts_ru": [],
                "districts_en": [],
            },
            "uae_visa": {
                "cities_ru": ["Дубай"],
                "cities_en": ["Dubai", "Abu Dhabi"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": [],
                "districts_en": [],
            },
            "caribbean_cbi": {
                "cities_ru": [],
                "cities_en": ["St Kitts", "Dominica", "Grenada", "Antigua"],
                "country_ru": "Карибы",
                "country_en": "Caribbean",
                "districts_ru": [],
                "districts_en": [],
            },
            "montenegro_rp": {
                "cities_ru": ["Подгорица"],
                "cities_en": ["Podgorica"],
                "country_ru": "Черногория",
                "country_en": "Montenegro",
                "districts_ru": [],
                "districts_en": [],
            },
            "general_migration": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": [],
                "country_ru": "",
                "country_en": "",
                "districts_ru": [],
                "districts_en": [],
            },
            "eb5_usa": {
                "cities_ru": [],
                "cities_en": [],
                "country_ru": "США",
                "country_en": "USA",
                "districts_ru": [],
                "districts_en": [],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{service} {country}",
            "ВНЖ {country} за инвестиции",
            "Golden Visa {country}",
            "золотая виза {country}",
            "гражданство {country} за инвестиции",
            "иммиграция в {country}",
            "релокация IT {country}",
            "переезд в {country} помощь",
        ],
        "templates_en": [
            "Golden Visa {country}",
            "Golden Visa {country} agent",
            "{service} {country}",
            "citizenship by investment {country}",
            "{country} residence permit investment",
            "{company_type} {city}",
            "{country} investor visa",
            "second passport {country}",
            "EB-5 visa consultant",
        ],
    },

    # ── Segment 5: Family Offices / Wealth ──────────────────
    "family_office": {
        "priority": 5,
        "label_ru": "Family Offices",
        "label_en": "Family Offices",

        "vars": {
            "company_type_ru": [
                "семейный офис", "мультисемейный офис", "wealth management",
                "управление капиталом",
            ],
            "company_type_en": [
                "family office", "multi family office", "wealth management",
                "private wealth advisory", "independent asset manager",
            ],
            "service_ru": [
                "управление семейным капиталом", "private banking",
                "приватный банкинг", "wealth management",
                "управление состоянием",
            ],
            "service_en": [
                "family office services", "wealth planning",
                "estate planning", "family governance",
                "private banking",
            ],
        },

        "geos": {
            "moscow_fo": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": [],
                "country_ru": "Россия",
                "country_en": "Russia",
                "districts_ru": [],
                "districts_en": [],
            },
            "switzerland_fo": {
                "cities_ru": [],
                "cities_en": ["Zurich", "Geneva", "Lugano"],
                "country_ru": "Швейцария",
                "country_en": "Switzerland",
                "districts_ru": [],
                "districts_en": [],
            },
            "singapore_fo": {
                "cities_ru": [],
                "cities_en": ["Singapore"],
                "country_ru": "Сингапур",
                "country_en": "Singapore",
                "districts_ru": [],
                "districts_en": [],
            },
            "dubai_fo": {
                "cities_ru": ["Дубай"],
                "cities_en": ["Dubai"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": [],
                "districts_en": ["DIFC"],
            },
            "ppli_insurance": {
                "cities_ru": [],
                "cities_en": [],
                "country_ru": "",
                "country_en": "",
                "districts_ru": [],
                "districts_en": [],
            },
            "private_banks_ru": {
                "cities_ru": [],
                "cities_en": [],
                "country_ru": "",
                "country_en": "",
                "districts_ru": [],
                "districts_en": [],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{service} {city}",
            "family office {city}",
            "{service} {country}",
            "Сбер Private Banking",
            "Альфа Private Banking",
            "Газпромбанк Private Banking",
            "независимый управляющий активами {city}",
            "финансовый советник HNWI {city}",
        ],
        "templates_en": [
            "{company_type} {city}",
            "{service} {city}",
            "{company_type} {country}",
            "private banking Russian clients {city}",
            "Russian speaking private bank {city}",
            "PPLI insurance {country}",
            "external asset manager {country}",
        ],
    },

    # ── Segment 6: Crypto ───────────────────────────────────
    "crypto": {
        "priority": 6,
        "label_ru": "Крипто",
        "label_en": "Crypto",

        "vars": {
            "company_type_ru": [
                "OTC крипто", "криптовалютный фонд", "обменник криптовалют",
                "крипто обменник", "майнинг ферма",
            ],
            "company_type_en": [
                "OTC desk", "crypto fund", "crypto exchange",
                "mining farm", "crypto OTC",
            ],
            "service_ru": [
                "купить биткоин крупная сумма", "OTC USDT",
                "обмен крипты на рубли", "купить USDT за рубли",
                "промышленный майнинг", "управление криптоактивами",
            ],
            "service_en": [
                "buy property with crypto", "crypto real estate",
                "OTC bitcoin", "large crypto transaction",
            ],
        },

        "geos": {
            "moscow_crypto": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": [],
                "country_ru": "Россия",
                "country_en": "Russia",
                "districts_ru": ["Иркутск", "Красноярск", "Братск", "Новосибирск"],
                "districts_en": [],
            },
            "dubai_crypto": {
                "cities_ru": ["Дубай"],
                "cities_en": ["Dubai"],
                "country_ru": "ОАЭ",
                "country_en": "UAE",
                "districts_ru": [],
                "districts_en": [],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "{service} {city}",
            "OTC крипто {city}",
            "купить биткоин {city}",
            "майнинг биткоин {district}",
            "криптовалютный фонд {city}",
            "обменник USDT {city}",
            "легальный обмен криптовалюты {city}",
        ],
        "templates_en": [
            "{company_type} {city}",
            "crypto OTC {city}",
            "{service}",
            "buy property with crypto {city}",
        ],
    },

    # ── Segment 7: Importers ────────────────────────────────
    "importers": {
        "priority": 7,
        "label_ru": "Импортёры",
        "label_en": "Importers",

        "vars": {
            "company_type_ru": [
                "ВЭД компания", "таможенный брокер", "импортёр",
                "ВЭД агент", "автоимпорт", "байер люкс",
            ],
            "company_type_en": [],
            "service_ru": [
                "импорт авто из ОАЭ", "импорт авто из Дубая",
                "привезти авто из Кореи", "импорт оборудования",
                "параллельный импорт", "международные расчёты",
                "оплата зарубежному поставщику", "платежи за рубеж",
            ],
            "service_en": [],
            "source_ru": [
                "ОАЭ", "Дубай", "Корея", "Китай", "Япония", "Германия", "США",
            ],
        },

        "geos": {
            "moscow_import": {
                "cities_ru": ["Москва", "Санкт-Петербург"],
                "cities_en": [],
                "country_ru": "Россия",
                "country_en": "",
                "districts_ru": [],
                "districts_en": [],
            },
        },

        "templates_ru": [
            "{company_type} {city}",
            "импорт авто из {source}",
            "купить машину в {source}",
            "пригнать авто из {source}",
            "импорт оборудования из {source}",
            "ВЭД компания {city}",
            "международные платежи для бизнеса",
            "байер люкс {source}",
            "личный шоппер {source}",
        ],
        "templates_en": [],
    },
}


# ============================================================
# SEGMENT LABELS (for UI / API)
# ============================================================

SEGMENT_LABELS = {
    k: {"ru": v["label_ru"], "en": v["label_en"], "priority": v["priority"]}
    for k, v in SEGMENTS.items()
}

SEGMENT_KEYS = sorted(SEGMENTS.keys(), key=lambda k: SEGMENTS[k]["priority"])


# ============================================================
# TEMPLATE ENGINE
# ============================================================

def _normalize(q: str) -> str:
    """Normalize a query for deduplication."""
    return " ".join(q.strip().lower().split())


def build_segment_queries(
    segment_key: str,
    geo_key: str | None = None,
    language: str | None = None,
    existing_queries: set[str] | None = None,
) -> list[dict]:
    """
    Generate queries via cartesian product of templates x variables x geos.

    Returns list of dicts:
        [{"query": "...", "segment": "real_estate", "geo": "dubai", "language": "ru", "source": "template"}, ...]

    Deterministic, zero AI cost. Deduplicates against existing_queries.
    """
    seg = SEGMENTS.get(segment_key)
    if not seg:
        return []

    existing = existing_queries or set()
    results: list[dict] = []
    seen: set[str] = set(existing)

    geos = seg["geos"]
    if geo_key:
        geos = {geo_key: geos[geo_key]} if geo_key in geos else {}

    langs = [language] if language else ["ru", "en"]

    for gk, geo in geos.items():
        for lang in langs:
            templates = seg.get(f"templates_{lang}", [])
            if not templates:
                continue

            # Build variable pools for this language + geo
            var_pools = _build_var_pools(seg, geo, lang)

            for tmpl in templates:
                # Find all {placeholder} names in the template
                placeholders = re.findall(r"\{(\w+)\}", tmpl)
                if not placeholders:
                    # Static template
                    _add_query(tmpl, segment_key, gk, lang, results, seen)
                    continue

                # Get the value lists for each placeholder
                value_lists = []
                for ph in placeholders:
                    vals = var_pools.get(ph, [])
                    if not vals:
                        break
                    value_lists.append(vals)
                else:
                    # Cartesian product of all placeholder values
                    for combo in itertools.product(*value_lists):
                        mapping = dict(zip(placeholders, combo))
                        query = tmpl.format(**mapping)
                        _add_query(query, segment_key, gk, lang, results, seen)

    return results


def _build_var_pools(seg: dict, geo: dict, lang: str) -> dict[str, list[str]]:
    """Build variable pools from segment vars + geo data for a given language."""
    pools: dict[str, list[str]] = {}
    variables = seg.get("vars", {})

    # Segment-level vars (with language suffix)
    for var_name, values in variables.items():
        if var_name.endswith(f"_{lang}"):
            base_name = var_name[:-3]  # strip _ru or _en
            pools[base_name] = values
        elif not var_name.endswith("_ru") and not var_name.endswith("_en"):
            # Language-neutral var
            pools[var_name] = values

    # Geo-level vars
    cities = geo.get(f"cities_{lang}", [])
    if cities:
        pools["city"] = cities

    country = geo.get(f"country_{lang}", "")
    if country:
        pools["country"] = [country]

    districts = geo.get(f"districts_{lang}", [])
    if districts:
        pools["district"] = districts

    # Special: for importers "source" var
    if "source_ru" in variables and lang == "ru":
        pools["source"] = variables["source_ru"]
    if "source_en" in variables and lang == "en":
        pools["source"] = variables["source_en"]

    return pools


def _add_query(
    query: str,
    segment: str,
    geo: str,
    language: str,
    results: list[dict],
    seen: set[str],
) -> None:
    """Add a query to results if not a duplicate."""
    nq = _normalize(query)
    if not nq or len(nq) < 6 or nq in seen:
        return
    seen.add(nq)
    results.append({
        "query": query,
        "segment": segment,
        "geo": geo,
        "language": language,
        "source": "template",
    })


def count_all_queries() -> dict[str, dict[str, int]]:
    """Count how many template queries each segment x geo produces. For diagnostics."""
    counts: dict[str, dict[str, int]] = {}
    for seg_key in SEGMENT_KEYS:
        seg = SEGMENTS[seg_key]
        counts[seg_key] = {}
        for geo_key in seg["geos"]:
            queries = build_segment_queries(seg_key, geo_key)
            counts[seg_key][geo_key] = len(queries)
        counts[seg_key]["_total"] = sum(counts[seg_key].values())


# ============================================================
# RAW DOC KEYWORDS (from tasks/deliryo/keywords_*.md)
#
# Each entry: (segment_key, geo_key, language) -> list of raw phrases
# These are the exact keyword phrases from the docs, used as-is as queries.
# ============================================================

DOC_KEYWORDS: list[tuple[str, str, str, list[str]]] = [
    # ── keywords_russia.md ──
    # Segment 1: Real Estate
    # §1 Дубай
    ("real_estate", "dubai", "ru", [
        "купить недвижимость в Дубае", "купить квартиру в Дубае", "купить виллу в Дубае",
        "купить апартаменты в Дубае", "купить пентхаус Дубай", "недвижимость в ОАЭ",
        "агентство недвижимости Дубай", "агентство недвижимости ОАЭ",
        "инвестиции в недвижимость Дубай", "off-plan Дубай купить", "новостройки Дубай",
        "квартира Дубай Марина", "квартира Palm Jumeirah", "квартира Downtown Dubai",
        "вилла Dubai Hills", "вилла Arabian Ranches", "квартира Business Bay",
        "квартира JBR Дубай", "недвижимость Дубай для россиян",
        "купить недвижимость ОАЭ из России", "как купить квартиру в Дубае",
        "риелтор Дубай русскоязычный", "русский агент Дубай недвижимость",
        "недвижимость Абу-Даби", "недвижимость Рас-Аль-Хайма", "недвижимость Шарджа",
    ]),
    # §2 Турция
    ("real_estate", "turkey", "ru", [
        "купить недвижимость в Турции", "купить квартиру в Турции", "купить виллу в Турции",
        "квартира в Анталье купить", "квартира в Аланье купить", "квартира в Стамбуле купить",
        "вилла в Бодруме", "недвижимость Фетхие", "недвижимость Мерсин",
        "недвижимость Калкан", "недвижимость Белек", "недвижимость Сиде",
        "недвижимость Кемер", "недвижимость Трабзон", "недвижимость Бурса",
        "недвижимость Измир", "агентство недвижимости Турция",
        "ВНЖ Турция через недвижимость", "гражданство Турции за инвестиции",
        "новостройки Анталья", "новостройки Стамбул", "недвижимость Турция для россиян",
        "русский риелтор Турция", "жильё в Турции купить", "инвестиции недвижимость Турция",
    ]),
    # §3 Кипр
    ("real_estate", "cyprus", "ru", [
        "купить недвижимость Кипр", "купить квартиру Кипр", "купить виллу Кипр",
        "квартира Лимассол купить", "вилла Пафос купить", "недвижимость Ларнака",
        "недвижимость Никосия", "недвижимость Айя-Напа", "недвижимость Протарас",
        "недвижимость Северный Кипр", "квартира Северный Кипр",
        "агентство недвижимости Кипр", "ВНЖ Кипр через недвижимость",
        "ПМЖ Кипр недвижимость", "новостройки Лимассол",
        "инвестиции недвижимость Кипр", "русский риелтор Кипр",
    ]),
    # §4 Таиланд/Бали
    ("real_estate", "thailand_bali", "ru", [
        "купить недвижимость Таиланд", "купить кондо Пхукет", "купить виллу Пхукет",
        "кондо Паттайя купить", "квартира Бангкок купить", "недвижимость Самуи",
        "недвижимость Чиангмай", "недвижимость Хуа Хин", "недвижимость Краби",
        "вилла Пханган", "агентство недвижимости Таиланд",
        "агентство недвижимости Пхукет", "кондоминиум Таиланд",
        "инвестиции Таиланд недвижимость", "русский риелтор Пхукет",
        "русский агент Паттайя", "недвижимость Таиланд для россиян",
        "купить виллу Бали", "недвижимость Бали", "вилла Чангу",
        "вилла Семиньяк", "вилла Убуд", "агентство недвижимости Бали", "инвестиции Бали",
    ]),
    # §5 Черногория
    ("real_estate", "montenegro", "ru", [
        "купить недвижимость Черногория", "квартира Будва купить", "квартира Тиват купить",
        "вилла Черногория", "недвижимость Котор", "недвижимость Херцег-Нови",
        "недвижимость Бар", "недвижимость Подгорица", "недвижимость Бечичи",
        "недвижимость Петровац", "недвижимость Ульцинь", "Порто Монтенегро квартира",
        "агентство недвижимости Черногория", "ВНЖ Черногория недвижимость",
        "инвестиции Черногория", "русский риелтор Черногория",
    ]),
    # §6 Испания/Португалия
    ("real_estate", "spain_portugal", "ru", [
        "купить недвижимость Испания", "квартира Барселона купить", "вилла Марбелья",
        "недвижимость Коста дель Соль", "недвижимость Коста Бланка",
        "квартира Аликанте", "квартира Малага", "недвижимость Валенсия",
        "вилла Ибица", "вилла Майорка", "недвижимость Тенерифе", "квартира Мадрид",
        "недвижимость Эстепона", "недвижимость Бенидорм",
        "агентство недвижимости Испания", "Golden Visa Испания",
        "купить недвижимость Португалия", "квартира Лиссабон купить",
        "вилла Алгарве", "недвижимость Порту", "недвижимость Каскайш",
        "недвижимость Мадейра", "агентство недвижимости Португалия",
        "Golden Visa Португалия", "русский риелтор Испания",
    ]),
    # §7 Агрегаторы
    ("real_estate", "global_aggregator", "ru", [
        "купить недвижимость за рубежом", "зарубежная недвижимость",
        "недвижимость за границей", "портал зарубежной недвижимости",
        "каталог зарубежной недвижимости", "инвестиции в зарубежную недвижимость",
        "международная недвижимость", "купить квартиру за рубежом",
        "купить дом за границей", "недвижимость за рубежом для россиян",
        "зарубежная недвижимость от застройщика", "элитная недвижимость за рубежом",
    ]),

    # Segment 2: Investment
    # §8 Инвестиционные бутики
    ("investment", "moscow", "ru", [
        "инвестиционная компания Москва", "инвестиционная компания Санкт-Петербург",
        "управляющая компания инвестиции", "инвестиционный советник",
        "инвестиционный консалтинг", "управление активами Москва",
        "инвестиции для состоятельных клиентов", "инвестиционный бутик",
        "advisory фирма инвестиции", "частное управление капиталом",
        "доверительное управление", "управление портфелем",
        "инвестиционная advisory", "инвестиционное управление",
        # §9 Брокеры с private-сегментом
        "private banking Москва", "private banking Петербург", "премиальный брокер",
        "VIP брокерское обслуживание", "управление крупным капиталом",
        "АТОН инвестиции", "Финам Private", "БКС Ультима", "Ренессанс Капитал",
        "Тинькофф Private", "Открытие Private", "Совкомбанк Private",
        "Газпромбанк Private", "приватный банкинг",
        "премиальное обслуживание инвестиции", "брокер для состоятельных клиентов",
        # §10 Независимые финансовые советники
        "независимый финансовый советник", "финансовый консультант",
        "личный финансовый советник", "инвестиционный советник Москва",
        "инвестиционный советник Петербург", "финансовое планирование",
        "советник по инвестициям", "персональный финансовый консультант",
        "управление личными финансами", "финансовый планировщик",
        "IFA Россия", "независимый советник по инвестициям",
        # §11 УК с зарубежными продуктами
        "инвестиции за рубежом", "зарубежные инвестиции из России",
        "управляющая компания зарубежные активы", "ETF из России",
        "инвестировать за границей", "зарубежный брокер для россиян",
        "международные инвестиции", "портфель зарубежных активов",
        "зарубежные фонды", "unit-linked программы",
        "накопительное страхование жизни инвестиционное",
        "страховой полис инвестиционный",
    ]),

    # Segment 3: Legal
    # §12 Международное налоговое планирование
    ("legal", "moscow", "ru", [
        "международное налоговое планирование", "налоговый консультант международный",
        "оптимизация налогов за рубежом", "налоговое планирование ВЭД",
        "международное налогообложение", "юрист по международным налогам",
        "двойное налогообложение", "налоговый советник Москва",
        "налоговый советник Петербург", "трансфертное ценообразование",
        "международная налоговая оптимизация", "СИДН",
        "соглашение об избежании двойного налогообложения",
        "КИК контролируемые иностранные компании", "налоговый консалтинг международный",
        # §13 Юрфирмы по ВЭД
        "юрист ВЭД", "юридическое сопровождение ВЭД",
        "юрист внешнеэкономическая деятельность", "таможенный юрист",
        "сопровождение экспортных сделок", "валютный контроль юрист",
        "ВЭД консалтинг", "импорт экспорт юридические услуги",
        "юрист по валютному законодательству", "сопровождение импортных сделок",
        "консалтинг ВЭД Москва", "юрист международная торговля",
        # §14 M&A
        "M&A юрист", "M&A юрист Москва", "сделки слияния поглощения",
        "международные M&A", "трансграничные сделки юрист",
        "корпоративный юрист M&A", "due diligence юрист",
        "продажа бизнеса за рубеж", "покупка компании за границей",
        "международная сделка юрист", "корпоративный юрист международный",
        "M&A консалтинг", "юрист по сделкам с зарубежными активами",
        # §15 Структурирование активов
        "структурирование активов", "создание траста", "личный фонд",
        "оффшорная структура", "защита активов юрист", "холдинговая структура",
        "международное структурирование", "корпоративное структурирование",
        "семейный фонд", "наследственное планирование", "estate planning Россия",
        "траст для защиты активов", "международный холдинг",
        "структурирование бизнеса за рубежом", "зарубежный траст", "зарубежный фонд",
        # §16 Налоговые консультанты для релокантов
        "налоги при релокации", "налоговый консультант для уехавших",
        "налоговое резидентство при переезде", "налоги релокант",
        "валютный резидент", "КИК для уехавших", "налоги при смене резидентства",
        "НДФЛ нерезидент", "налоговый статус при эмиграции",
        "налоги для уехавших из России", "уведомление о КИК",
        "налог при продаже квартиры нерезидент", "декларация 3-НДФЛ нерезидент",
        "валютное резидентство", "счета за рубежом уведомление",
    ]),

    # Segment 4: Migration
    # §17 Миграционные агентства
    ("migration", "general_migration", "ru", [
        "ВНЖ за инвестиции", "иммиграция за рубеж", "получить ВНЖ",
        "второе гражданство", "иммиграционный консультант",
        "иммиграционное агентство Москва", "иммиграционное агентство Петербург",
        "помощь в иммиграции", "ПМЖ за рубежом", "вид на жительство за границей",
        "переезд за границу помощь", "эмиграция из России",
        "куда уехать из России", "иммиграция в Европу",
        "иммиграция в ОАЭ", "иммиграция в Канаду", "иммиграция в США",
        # §18 Релокация IT
        "релокация IT", "переезд программистов за границу",
        "релокация разработчиков", "IT релокация Грузия", "IT релокация Сербия",
        "IT релокация ОАЭ", "IT релокация Кипр", "IT релокация Армения",
        "IT релокация Черногория", "IT релокация Турция",
        "помощь с переездом IT", "релокация айтишников",
        "digital nomad visa", "виза цифрового кочевника",
        "удалённая работа за рубежом", "переезд в Дубай IT",
        # §19 Визовые (Golden Visa)
        "Golden Visa", "золотая виза", "ВНЖ за покупку недвижимости",
        "инвесторская виза", "Golden Visa Испания", "Golden Visa Греция",
        "Golden Visa Португалия", "Golden Visa ОАЭ", "ВНЖ через инвестиции",
        "резидентство за инвестиции", "инвестиционная виза",
        "визовое агентство Golden Visa", "помощь Golden Visa", "оформление Golden Visa",
    ]),

    # Segment 5: Family Offices
    # §20 Family offices
    ("family_office", "moscow_fo", "ru", [
        "семейный офис", "family office Москва", "family office Петербург",
        "управление семейным капиталом", "семейный фонд",
        "частное управление активами", "family office услуги",
        "семейное управление состоянием", "создание семейного офиса",
        "семейный офис для HNWI",
        # §21 Multi-family offices
        "мультисемейный офис", "multi family office Россия",
        "multi family office Москва", "управление капиталом нескольких семей",
        "MFO услуги", "мультисемейное управление активами",
        # §22 Private banking дески
        "private banking Москва", "Сбер Private Banking",
        "Альфа Private Banking", "Газпромбанк Private Banking",
        "ВТБ Private Banking", "Тинькофф Private", "Открытие Private",
        "Совкомбанк Private", "Росбанк Private", "Райффайзен Private",
        "премиальное банковское обслуживание", "приватный банкинг",
        "private banking Петербург", "private banking Россия",
        # §23 Wealth-советники
        "wealth management Россия", "wealth management Москва",
        "управление состоянием", "wealth advisor Россия",
        "консультант по управлению капиталом", "независимый управляющий активами",
        "wealth planning", "управление благосостоянием", "финансовый советник HNWI",
    ]),

    # Segment 6: Crypto
    # §24 OTC-дески
    ("crypto", "moscow_crypto", "ru", [
        "OTC крипто", "OTC крипто Москва", "OTC крипто Петербург",
        "купить криптовалюту крупная сумма", "OTC биткоин",
        "внебиржевая покупка крипто", "OTC USDT", "купить крипту оптом",
        "крупные крипто сделки", "OTC desk Россия", "OTC сделка биткоин",
        "купить биткоин крупная сумма", "обмен крупных сумм крипто",
        # §25 Крипто-фонды
        "криптовалютный фонд", "крипто инвестиционный фонд",
        "инвестиции в криптовалюту фонд", "фонд цифровых активов",
        "управление криптоактивами", "крипто фонд Россия",
        "криптовалютный инвестиционный фонд Москва", "инвестиции биткоин фонд",
        # §26 Майнинг
        "майнинг биткоин Россия", "майнинг ферма", "майнинг ферма Россия",
        "крипто майнинг", "промышленный майнинг", "майнинг оборудование",
        "майнинг Иркутск", "майнинг Красноярск", "майнинг Братск",
        "майнинг Новосибирск", "майнинг Казахстан", "дата центр майнинг",
        "легализация дохода майнинг", "налоги с майнинга", "майнинг отель",
        "облачный майнинг", "mining farm Russia",
        # §27 Обменники
        "обменник криптовалют", "обмен крипты на рубли", "купить биткоин за рубли",
        "обменник USDT", "легальный обмен криптовалюты", "лицензированный обменник",
        "купить USDT за рубли", "купить биткоин Москва",
        "обмен криптовалюты на наличные", "крипто обмен Петербург",
        "надёжный обменник крипты", "обменник с документами",
    ]),

    # Segment 7: Importers
    # §28-31
    ("importers", "moscow_import", "ru", [
        # §28 Импортёры авто
        "импорт авто из ОАЭ", "импорт авто из Дубая", "купить машину в Дубае",
        "привезти авто из Кореи", "импорт автомобилей из Китая",
        "авто из Эмиратов", "купить машину за рубежом", "автоимпорт",
        "параллельный импорт авто", "авто из Японии", "авто из Германии",
        "авто из США", "авто под заказ из-за рубежа",
        "пригнать авто из Дубая", "пригнать авто из Кореи", "автоброкер импорт",
        # §29 Импортёры оборудования
        "импорт оборудования", "импорт оборудования из Китая",
        "импорт оборудования из Европы", "импорт станков",
        "закупка оборудования за рубежом", "промышленный импорт",
        "поставка оборудования из-за рубежа", "ВЭД оборудование",
        "импорт медицинского оборудования", "импорт строительного оборудования",
        "импорт промышленного оборудования",
        # §30 Байеры luxury
        "байер люкс", "личный шоппер за рубежом", "персональный байер",
        "закупка luxury товаров", "шопинг за рубежом",
        "байер Милан", "байер Париж", "байер Дубай", "байер Лондон",
        "байер Италия", "личный закупщик люкс", "luxury шоппинг сервис",
        "персональный шопер Европа",
        # §31 ВЭД-компании
        "ВЭД компания", "ВЭД компания Москва", "ВЭД компания Петербург",
        "внешнеэкономическая деятельность", "импорт товаров",
        "экспорт из России", "международная торговля",
        "оплата зарубежному поставщику", "международные расчёты",
        "платежи за рубеж", "как оплатить поставщику за границей",
        "ВЭД агент", "ВЭД посредник", "таможенный брокер",
        "логистика ВЭД", "международные платежи для бизнеса",
    ]),

    # ── keywords_international.md ──
    # Segment 1: Real Estate (international)
    # §1 Дубай EN
    ("real_estate", "dubai", "en", [
        "buy property Dubai", "buy apartment Dubai", "buy villa Dubai",
        "buy penthouse Dubai", "property for sale Dubai", "apartment for sale Dubai",
        "villa for sale Dubai", "real estate agency Dubai", "real estate agent Dubai",
        "real estate broker Dubai", "property broker Dubai", "Dubai property investment",
        "investment property Dubai", "off-plan Dubai", "off-plan property Dubai",
        "new development Dubai", "Dubai Marina property", "Dubai Marina apartment",
        "Palm Jumeirah property", "Palm Jumeirah villa", "Downtown Dubai apartment",
        "Business Bay property", "JBR apartment", "Dubai Hills villa",
        "Arabian Ranches villa", "Jumeirah Village Circle property",
        "Dubai Creek Harbour", "Emaar Beachfront", "MBR City property",
        "DIFC apartment", "Dubai South property", "Damac properties Dubai",
        "Emaar properties Dubai", "Sobha Dubai", "Ellington properties",
        "RERA registered broker", "RERA agent Dubai",
        "Russian speaking realtor Dubai", "luxury real estate Dubai",
        "premium property Dubai", "Dubai property consultant",
        "Dubai real estate consultancy",
    ]),
    # §2 Турция EN
    ("real_estate", "turkey", "en", [
        "buy property Turkey", "buy apartment Turkey", "buy villa Turkey",
        "property for sale Turkey", "real estate agency Turkey",
        "real estate agent Turkey", "property broker Turkey",
        "Istanbul property", "Istanbul apartment buy", "Istanbul real estate",
        "Antalya property", "Antalya apartment", "Antalya real estate agent",
        "Alanya property", "Alanya apartment for sale", "Bodrum property",
        "Bodrum villa", "Fethiye property", "Fethiye villa for sale",
        "Mersin property", "Kalkan villa", "Belek property", "Side apartment",
        "Kemer property", "Trabzon apartment", "Bursa property", "Izmir real estate",
        "Kusadasi property", "Didim apartment",
        "Turkish citizenship by investment", "Turkey citizenship property",
        "Turkey residence permit property", "off-plan Turkey",
        "new development Istanbul", "new development Antalya",
        "luxury property Turkey",
    ]),
    # §3 Кипр EN
    ("real_estate", "cyprus", "en", [
        "buy property Cyprus", "buy apartment Cyprus", "buy villa Cyprus",
        "property for sale Cyprus", "real estate agency Cyprus",
        "real estate agent Cyprus", "property broker Cyprus",
        "Limassol property", "Limassol apartment", "Limassol real estate",
        "Paphos property", "Paphos villa", "Paphos real estate",
        "Larnaca property", "Larnaca apartment", "Nicosia property",
        "Ayia Napa property", "Protaras villa", "Famagusta property",
        "North Cyprus property", "North Cyprus apartment",
        "Cyprus property investment", "Cyprus residence permit property",
        "Cyprus permanent residency", "off-plan Cyprus",
        "new development Limassol", "luxury property Cyprus",
        "seaside property Cyprus",
    ]),
    # §4 Черногория EN
    ("real_estate", "montenegro", "en", [
        "buy property Montenegro", "buy apartment Montenegro", "buy villa Montenegro",
        "property for sale Montenegro", "real estate agency Montenegro",
        "real estate agent Montenegro", "Budva property", "Budva apartment",
        "Budva real estate", "Tivat property", "Tivat apartment", "Tivat real estate",
        "Porto Montenegro property", "Kotor property", "Kotor apartment",
        "Herceg Novi property", "Herceg Novi apartment", "Bar property",
        "Ulcinj property", "Podgorica property", "Podgorica apartment",
        "Becici property", "Petrovac apartment", "Montenegro property investment",
        "Montenegro residence permit property", "Montenegro citizenship",
        "off-plan Montenegro", "luxury property Montenegro",
        "seaside property Montenegro",
    ]),
    # §5 Португалия EN
    ("real_estate", "spain_portugal", "en", [
        "buy property Portugal", "buy apartment Portugal", "buy villa Portugal",
        "property for sale Portugal", "real estate agency Portugal",
        "real estate agent Portugal", "property broker Portugal",
        "Lisbon property", "Lisbon apartment", "Lisbon real estate",
        "Porto property", "Porto apartment", "Porto real estate",
        "Algarve property", "Algarve villa", "Faro property", "Lagos property",
        "Cascais property", "Cascais apartment", "Estoril property",
        "Sintra villa", "Madeira property", "Funchal apartment",
        "Silver Coast property", "Comporta property", "Vilamoura property",
        "Golden Visa Portugal property", "Portugal residence permit",
        "off-plan Portugal", "new development Lisbon", "luxury property Portugal",
        # §6 Испания EN
        "buy property Spain", "buy apartment Spain", "buy villa Spain",
        "property for sale Spain", "real estate agency Spain",
        "real estate agent Spain", "property broker Spain",
        "Barcelona property", "Barcelona apartment", "Barcelona real estate",
        "Madrid property", "Madrid apartment", "Marbella property",
        "Marbella villa", "Marbella real estate", "Costa del Sol property",
        "Costa del Sol apartment", "Costa Blanca property", "Alicante property",
        "Alicante apartment", "Malaga property", "Malaga apartment",
        "Valencia property", "Valencia apartment", "Ibiza property",
        "Ibiza villa", "Mallorca property", "Mallorca villa",
        "Tenerife property", "Tenerife apartment", "Gran Canaria property",
        "Sotogrande villa", "Estepona property", "Fuengirola apartment",
        "Torrevieja property", "Benidorm apartment",
        "Golden Visa Spain", "Spain residence permit investment",
        "off-plan Spain", "new development Costa del Sol", "luxury property Spain",
    ]),
    # §7 Греция EN
    ("real_estate", "greece", "en", [
        "buy property Greece", "buy apartment Greece", "buy villa Greece",
        "property for sale Greece", "real estate agency Greece",
        "real estate agent Greece", "Athens property", "Athens apartment",
        "Athens real estate", "Thessaloniki property", "Thessaloniki apartment",
        "Crete property", "Crete villa", "Chania property", "Heraklion property",
        "Rhodes property", "Rhodes villa", "Corfu property", "Corfu villa",
        "Mykonos property", "Mykonos villa", "Santorini property",
        "Halkidiki property", "Halkidiki villa", "Voula property",
        "Glyfada apartment", "Piraeus property", "Peloponnese property",
        "Golden Visa Greece property", "Greece residence permit investment",
        "off-plan Greece", "luxury property Greece",
        "island property Greece", "seaside villa Greece",
    ]),
    # §8 Таиланд EN
    ("real_estate", "thailand_bali", "en", [
        "buy property Thailand", "buy condo Thailand", "buy villa Thailand",
        "property for sale Thailand", "real estate agency Thailand",
        "real estate agent Thailand", "Phuket property", "Phuket condo",
        "Phuket villa", "Phuket real estate", "Bangkok property", "Bangkok condo",
        "Bangkok apartment", "Pattaya property", "Pattaya condo",
        "Pattaya apartment", "Koh Samui property", "Koh Samui villa",
        "Chiang Mai property", "Chiang Mai condo", "Hua Hin property",
        "Hua Hin condo", "Krabi property", "Koh Phangan villa",
        "Rawai villa", "Kata beach property", "Kamala property",
        "Bang Tao property", "Sukhumvit condo", "Silom apartment",
        "Thailand property investment", "Thailand condominium foreign",
        "off-plan Thailand", "new development Phuket",
        "luxury villa Thailand", "beachfront property Thailand",
        # §9 Бали EN
        "buy property Bali", "buy villa Bali", "villa for sale Bali",
        "property for sale Bali", "real estate agency Bali",
        "real estate agent Bali", "Bali investment property",
        "Bali villa investment", "Seminyak villa", "Canggu property",
        "Canggu villa", "Ubud property", "Ubud villa", "Uluwatu villa",
        "Jimbaran property", "Sanur property", "Nusa Dua villa",
        "Kuta property", "Tabanan villa", "Pererenan villa",
        "Bali leasehold", "Bali freehold", "PT PMA property Bali",
        "off-plan villa Bali", "luxury villa Bali",
        "beachfront property Bali", "Bali real estate for foreigners",
    ]),
    # §10 Девелоперы Дубай EN
    ("real_estate", "dubai", "en", [
        "Dubai developer", "Dubai property developer", "off-plan projects Dubai",
        "new launch Dubai", "Dubai new development", "Emaar projects",
        "Emaar new launch", "Damac projects", "Damac new development",
        "Sobha Realty projects", "Ellington properties new", "Meraas projects",
        "Nakheel new projects", "Azizi developments", "Omniyat Dubai",
        "Select Group Dubai", "MAG properties", "Binghatti developers",
        "Samana developers", "Danube properties", "Dubai master developer",
        "Dubai mega project", "Dubai residential project launch",
    ]),
    # §11 Девелоперы CEE
    ("real_estate", "spain_portugal", "en", [
        "real estate developer Czech Republic", "property developer Prague",
        "Prague new development", "Prague residential project",
        "Budapest real estate developer", "Budapest new apartments",
        "Hungary property developer", "Serbia property development",
        "Belgrade new development", "Belgrade residential project",
        "Poland real estate developer", "Warsaw new development",
        "Warsaw apartments new", "Krakow property developer",
        "CEE property investment", "Central Europe real estate developer",
        "Bratislava property", "Ljubljana real estate",
        "Zagreb property developer",
    ]),

    # Segment 2: Investment Migration (international)
    # §12 Golden Visa Испания
    ("migration", "spain_gv", "en", [
        "Golden Visa Spain", "Spain Golden Visa agent",
        "Spain Golden Visa consultant", "Spain investor visa",
        "Spain residence permit investment", "residency by investment Spain",
        "Spain Golden Visa property", "Spain Golden Visa requirements",
        "Barcelona Golden Visa", "Madrid Golden Visa", "Marbella Golden Visa",
    ]),
    # §13 Golden Visa Португалия
    ("migration", "portugal_gv", "en", [
        "Golden Visa Portugal", "Portugal Golden Visa agent",
        "Portugal Golden Visa consultant", "Portugal investor visa",
        "Portugal residence permit investment", "residency by investment Portugal",
        "Portugal Golden Visa fund", "Portugal Golden Visa requirements",
        "Lisbon Golden Visa", "Porto Golden Visa", "Algarve Golden Visa",
    ]),
    # §14 Golden Visa Греция
    ("migration", "greece_gv", "en", [
        "Golden Visa Greece", "Greece Golden Visa agent",
        "Greece Golden Visa consultant", "Greece investor visa",
        "Greece residence permit investment", "residency by investment Greece",
        "Greece Golden Visa property", "Greece Golden Visa requirements",
        "Athens Golden Visa", "Crete Golden Visa", "Thessaloniki Golden Visa",
    ]),
    # §15 CBI Карибы
    ("migration", "caribbean_cbi", "en", [
        "citizenship by investment", "CBI program", "second passport",
        "Caribbean citizenship", "St Kitts citizenship by investment",
        "St Kitts passport", "Dominica citizenship by investment",
        "Dominica passport", "Grenada citizenship by investment",
        "Grenada passport", "Antigua citizenship", "Vanuatu citizenship",
        "Malta citizenship", "Turkey citizenship by investment",
        "second citizenship", "CBI agent", "CBI consultant",
        "citizenship by investment consultant",
    ]),
    # §16 ВНЖ ОАЭ
    ("migration", "uae_visa", "en", [
        "UAE Golden Visa", "Dubai Golden Visa", "UAE investor visa",
        "UAE residency visa", "UAE residence permit", "Emirates ID",
        "Dubai residency by investment", "UAE 10 year visa",
        "UAE property visa", "Dubai freelance visa",
        "Abu Dhabi Golden Visa", "UAE entrepreneur visa",
        "UAE retirement visa", "Dubai startup visa",
    ]),
    # §17 ВНЖ Черногория
    ("migration", "montenegro_rp", "en", [
        "Montenegro residency", "Montenegro residence permit",
        "Montenegro residency by investment", "Montenegro residency property",
        "Montenegro citizenship by investment", "Montenegro permanent residency",
        "Podgorica residence permit", "Montenegro visa",
        "Montenegro digital nomad",
    ]),
    # §18 EB-5 США
    ("migration", "general_migration", "en", [
        "EB-5 visa", "EB-5 program", "EB-5 investment",
        "EB-5 investor visa", "EB-5 regional center",
        "EB-5 direct investment", "EB-5 consultant", "EB-5 agent",
        "EB-5 attorney", "green card by investment",
        "US investor visa", "US immigration investment",
        "EB-5 minimum investment", "EB-5 requirements", "E-2 visa",
    ]),
    # §19 Миграционные консультанты интернациональные
    ("migration", "general_migration", "en", [
        "immigration consultant", "investment migration consultant",
        "RCBI advisory", "residency by investment consultant",
        "citizenship by investment firm", "global mobility consultant",
        "immigration advisory firm", "immigration law firm",
        "relocation consultant", "international immigration",
        "investment migration agency", "immigration services",
    ]),

    # Segment 3: Wealth Management (international)
    # §20 Wealth Швейцария
    ("investment", "switzerland", "en", [
        "wealth management Switzerland", "Swiss wealth manager",
        "private wealth advisory Zurich", "asset management Switzerland",
        "Swiss private bank", "independent asset manager Switzerland",
        "Geneva wealth management", "Zurich wealth management",
        "Lugano wealth manager", "Swiss asset management",
        "EAM Switzerland", "external asset manager Switzerland",
        "Swiss portfolio manager", "wealth planning Switzerland",
    ]),
    # §21 Wealth Сингапур
    ("investment", "singapore", "en", [
        "wealth management Singapore", "Singapore asset manager",
        "private wealth Singapore", "family office Singapore",
        "licensed fund management Singapore", "MAS regulated wealth manager",
        "Singapore private bank", "Raffles Place wealth management",
        "Singapore wealth advisory", "multi family office Singapore",
        "Singapore capital management",
    ]),
    # §22 Wealth Дубай
    ("investment", "dubai_difc", "en", [
        "wealth management Dubai", "DIFC wealth manager",
        "Dubai asset management", "private wealth advisory Dubai",
        "DFSA regulated", "financial advisor Dubai",
        "wealth management UAE", "Abu Dhabi wealth management",
        "ADGM financial advisor", "Dubai private bank",
        "Dubai investment advisor", "wealth planning Dubai",
        "portfolio management Dubai", "UAE asset management",
    ]),
    # §23 Family offices международные
    ("family_office", "dubai_fo", "en", [
        "multi family office", "family office services",
        "international family office", "family office wealth management",
        "global family office", "family office advisory",
        "single family office setup", "family office platform",
        "family office solutions", "family office investment",
        "virtual family office", "digital family office", "family governance",
    ]),
    # §24 PPLI
    ("family_office", "switzerland_fo", "en", [
        "PPLI insurance", "private placement life insurance",
        "UHNWI insurance", "wealth protection insurance",
        "VUL insurance", "variable universal life",
        "international life insurance broker", "estate planning insurance",
        "Lombard International", "Investors Trust",
        "offshore life insurance", "unit-linked insurance",
        "insurance wrapper", "wealth structuring insurance",
        "high net worth insurance",
    ]),
    # §25 Private банки (русскоязычные дески)
    ("family_office", "switzerland_fo", "en", [
        "private banking Russian clients", "Russian speaking private bank",
        "private bank CIS clients", "Julius Baer Russian", "UBS Russian desk",
        "Pictet Russian clients", "Credit Suisse Russian",
        "Lombard Odier Russian", "EFG International",
        "private banking for Russians", "Swiss private bank Russian",
        "Singapore private bank Russian", "Dubai private bank Russian",
        "Liechtenstein private bank",
    ]),

    # Segment 4: Legal (international)
    # §26 Юрфирмы Кипр
    ("legal", "cyprus_legal", "en", [
        "law firm Cyprus", "corporate services Cyprus",
        "Cyprus company registration", "tax advisory Cyprus",
        "Limassol law firm", "Paphos law firm", "Nicosia law firm",
        "Larnaca law firm", "Cyprus trust formation",
        "Cyprus holding company", "Cyprus IP box",
        "Cyprus tax planning", "Cyprus audit firm",
        "Cyprus corporate structuring", "Cyprus substance",
        "Cyprus iGaming license",
    ]),
    # §27 Юрфирмы ОАЭ
    ("legal", "uae_legal", "en", [
        "law firm Dubai", "law firm Abu Dhabi", "company formation UAE",
        "company formation Dubai", "Dubai business setup",
        "freezone company UAE", "freezone company Dubai",
        "DMCC company", "JAFZA company", "DIFC company", "ADGM company",
        "corporate services Dubai", "corporate services Abu Dhabi",
        "tax advisory UAE", "Dubai mainland company",
        "RAK company formation", "Sharjah freezone", "Ajman freezone",
        "Fujairah company", "PRO services Dubai",
    ]),
    # §28 Юрфирмы Эстония
    ("legal", "estonia", "en", [
        "law firm Estonia", "Estonia e-Residency",
        "company registration Estonia", "crypto license Estonia",
        "Estonian company formation", "e-Residency services",
        "Tallinn law firm", "Estonia tax advisory",
        "Estonian holding company", "Estonia fintech license",
        "Estonia EMI license", "Estonia virtual office",
    ]),
    # §29 Юрфирмы Грузия
    ("legal", "georgia_legal", "en", [
        "law firm Georgia", "company registration Georgia",
        "Tbilisi business setup", "Georgia tax benefits",
        "Georgia company formation", "Tbilisi law firm", "Batumi law firm",
        "Georgia IT company", "Georgia virtual zone",
        "Georgia small business status", "Georgia free industrial zone",
        "Georgia tax free", "Georgia residence permit business",
    ]),
    # §30 Юрфирмы Сербия
    ("legal", "serbia_legal", "en", [
        "law firm Serbia", "company registration Serbia",
        "Belgrade business setup", "Serbia corporate services",
        "Serbia residence permit business", "Belgrade law firm",
        "Novi Sad law firm", "Serbia tax advisory",
        "Serbia company formation", "Serbia DOO registration",
        "Serbia freelance visa", "Serbia digital nomad",
        "Serbia business immigration",
    ]),
    # §31 Offshore-провайдеры
    ("legal", "offshore", "en", [
        "offshore company formation", "BVI company", "BVI company formation",
        "Cayman Islands company", "Cayman Islands formation",
        "offshore corporate services", "offshore trust",
        "offshore trust formation", "international holding structure",
        "offshore bank account", "Panama company", "Seychelles company",
        "Mauritius company", "Marshall Islands company", "Belize company",
        "Nevis LLC", "offshore foundation", "Liechtenstein foundation",
        "Jersey trust", "Guernsey trust", "Isle of Man company",
        "Hong Kong company", "Singapore holding", "Luxembourg holding",
        "Malta holding company",
    ]),
    # §32 Консалтинг Бали/ЮВА
    ("legal", "georgia_legal", "en", [
        "business setup Bali", "company registration Indonesia",
        "PT PMA Indonesia", "Bali business consultant",
        "Bali corporate services", "Denpasar law firm",
        "Indonesia tax advisor", "Indonesia business visa",
        "KITAS Indonesia", "Vietnam company formation",
        "Vietnam business setup", "Ho Chi Minh law firm",
        "Hanoi corporate services", "Thailand BOI",
        "Thailand company formation", "Bangkok law firm",
        "Thailand business setup", "Cambodia company formation",
        "Philippines company registration", "Malaysia company formation",
        "Kuala Lumpur law firm", "Myanmar company setup",
    ]),

    # Segment 5: PropTech
    # §33 PropTech ОАЭ
    ("real_estate", "dubai", "en", [
        "proptech UAE", "proptech Dubai", "real estate platform Dubai",
        "property marketplace UAE", "Dubai property portal",
        "real estate tech Dubai", "online property Dubai",
        "property listing Dubai", "Dubai real estate marketplace",
        "PropTech Abu Dhabi", "real estate SaaS Dubai",
        "property management platform UAE",
    ]),
    # §34 Агрегаторы зарубежной
    ("real_estate", "global_aggregator", "en", [
        "international property portal", "overseas property marketplace",
        "global real estate platform", "buy property abroad",
        "property listings international", "overseas property listings",
        "global property search", "international real estate marketplace",
    ]),
    # §35 Crypto-friendly платформы
    ("crypto", "dubai_crypto", "en", [
        "buy property with crypto", "buy property with bitcoin",
        "real estate tokenization", "blockchain real estate",
        "crypto real estate platform", "NFT real estate",
        "tokenized real estate", "buy apartment with USDT",
        "buy villa with crypto", "crypto property marketplace",
    ]),

    # ══════════════════════════════════════════════════════════
    # HIGH-CONVERSION EXPANSION — geo-specific queries based on
    # data analysis (Feb 2026). These target the highest-yield
    # segment+geo combos with city-level precision.
    # ══════════════════════════════════════════════════════════

    # ── MIGRATION (48.7% hit rate — TOP priority) ────────────

    # Greece GV — rephrased/expanded (100% hit rate on existing!)
    ("migration", "greece_gv", "en", [
        "Greece Golden Visa property requirements",
        "Athens property for Golden Visa",
        "Crete Golden Visa real estate",
        "Thessaloniki Golden Visa investment",
        "Greece residency by investment consultant",
        "Greece residence permit property purchase",
        "buy property Greece Golden Visa",
        "Greece investor residency agent",
        "Golden Visa Greece 250000",
        "Greek Golden Visa application",
    ]),
    ("migration", "greece_gv", "ru", [
        "Golden Visa Греция 250 000",
        "получить ВНЖ Греция через недвижимость",
        "агент Golden Visa Афины",
        "ВНЖ Греция через покупку недвижимости",
        "консультант по Golden Visa Греция",
        "резидентство Греция за инвестиции",
        "оформление Golden Visa Греция",
    ]),

    # Portugal GV — expanded
    ("migration", "portugal_gv", "en", [
        "Portugal Golden Visa fund investment",
        "Portugal Golden Visa 2025",
        "Portugal residency investment fund",
        "Lisbon Golden Visa consultant",
        "Portugal residence permit fund",
        "Portugal Golden Visa advisory",
        "Portugal residency by investment firm",
        "non-habitual resident Portugal",
        "NHR Portugal tax",
    ]),
    ("migration", "portugal_gv", "ru", [
        "Golden Visa Португалия фонд",
        "получить ВНЖ Португалия инвестиции",
        "консультант Golden Visa Лиссабон",
        "резидентство Португалия через инвестиции",
        "ВНЖ Португалия через фонд",
        "Португалия налоговый режим NHR",
    ]),

    # Spain GV — expanded
    ("migration", "spain_gv", "en", [
        "Spain Golden Visa 500000",
        "Spain investor visa property",
        "Barcelona Golden Visa consultant",
        "Marbella Golden Visa agent",
        "Spain residency investment property",
        "Spain residence by investment firm",
        "Spanish Golden Visa advisory",
        "buy property Spain residency",
    ]),
    ("migration", "spain_gv", "ru", [
        "Golden Visa Испания 500 000",
        "купить недвижимость Испания ВНЖ",
        "ВНЖ Испания через покупку жилья",
        "консультант Golden Visa Барселона",
        "резидентство Испания инвестиции",
        "Золотая виза Испания 2025",
    ]),

    # UAE visa — expanded
    ("migration", "uae_visa", "en", [
        "Dubai investor visa 2 million",
        "UAE 10 year Golden Visa property",
        "Abu Dhabi investor residency",
        "UAE freelance visa Dubai",
        "Dubai residency property investment",
        "UAE Golden Visa requirements 2025",
        "Emirates ID investor visa",
    ]),
    ("migration", "uae_visa", "ru", [
        "Golden Visa Дубай недвижимость",
        "ВНЖ ОАЭ через инвестиции",
        "резидентская виза ОАЭ 10 лет",
        "получить Golden Visa Дубай",
        "виза инвестора Абу-Даби",
        "резидентство Дубай за покупку недвижимости",
    ]),

    # EB-5 USA — new geo
    ("migration", "eb5_usa", "en", [
        "EB-5 visa program",
        "EB-5 investor visa USA",
        "green card by investment",
        "EB-5 regional center",
        "US immigration investment",
        "EB-5 minimum investment 2025",
        "EB-5 direct investment",
    ]),
    ("migration", "eb5_usa", "ru", [
        "EB-5 виза инвестора",
        "грин карта за инвестиции",
        "иммиграция США через инвестиции",
        "EB-5 программа",
        "инвестиционная виза США",
    ]),

    # Montenegro RP — expanded
    ("migration", "montenegro_rp", "en", [
        "Montenegro residency by investment",
        "Montenegro property residence permit",
        "Montenegro permanent residency",
        "Montenegro citizenship programme",
        "Podgorica residence permit",
        "Montenegro digital nomad visa",
    ]),
    ("migration", "montenegro_rp", "ru", [
        "ВНЖ Черногория за покупку недвижимости",
        "ПМЖ Черногория инвестиции",
        "гражданство Черногория программа",
        "резидентство Черногория",
        "переезд в Черногорию",
    ]),

    # ── REAL ESTATE — Turkey (91% hit!) ──────────────────────

    # Turkey — city-level expansion (highest conversion)
    ("real_estate", "turkey", "en", [
        "buy property Antalya",
        "buy apartment Istanbul",
        "buy villa Bodrum",
        "Alanya property for sale",
        "Fethiye villa for sale",
        "Mersin property investment",
        "Kalkan villa for sale",
        "Belek property for sale",
        "real estate agency Antalya",
        "real estate agent Istanbul",
        "real estate broker Turkey",
        "Turkish citizenship property investment",
        "Turkey residence permit property",
        "off-plan Antalya",
        "new development Istanbul",
        "luxury property Turkey",
        "Trabzon apartment for sale",
        "Bursa property",
        "Izmir real estate",
        "Kusadasi property for sale",
        "Didim apartment",
    ]),

    # Montenegro — expanded with English keywords
    ("real_estate", "montenegro", "en", [
        "buy property Montenegro",
        "buy apartment Budva",
        "buy apartment Tivat",
        "Porto Montenegro property",
        "Kotor real estate",
        "Herceg Novi apartment",
        "Bar property Montenegro",
        "Becici property",
        "Petrovac apartment",
        "real estate agency Montenegro",
        "Montenegro property investment",
        "seaside property Montenegro",
    ]),
    ("real_estate", "montenegro", "ru", [
        "купить недвижимость Черногория",
        "квартира Будва купить",
        "квартира Тиват купить",
        "вилла Черногория",
        "недвижимость Котор",
        "недвижимость Херцег-Нови",
        "недвижимость Бар",
        "Порто Монтенегро квартира",
        "агентство недвижимости Черногория",
    ]),

    # Spain — city-level expansion
    ("real_estate", "spain_portugal", "en", [
        "buy property Marbella",
        "buy apartment Barcelona",
        "buy villa Costa del Sol",
        "Alicante property for sale",
        "Malaga apartment for sale",
        "Tenerife property for sale",
        "Ibiza villa for sale",
        "Mallorca property",
        "Estepona property",
        "Benidorm apartment",
        "real estate agency Spain",
        "Spanish property investment",
        "Golden Visa Spain property",
        "luxury property Spain",
        "Costa Blanca property",
    ]),

    # Greece — city-level expansion EN
    ("real_estate", "greece", "en", [
        "buy property Greece",
        "buy apartment Athens",
        "buy villa Crete",
        "Rhodes property for sale",
        "Corfu villa for sale",
        "Mykonos property",
        "Halkidiki villa",
        "Thessaloniki apartment",
        "Santorini property",
        "real estate agency Greece",
        "Golden Visa Greece property investment",
        "Greece property investment",
        "island property Greece",
    ]),

    # Portugal — city-level expansion
    ("real_estate", "spain_portugal", "en", [
        "buy property Lisbon",
        "buy apartment Porto",
        "buy villa Algarve",
        "Cascais property",
        "Madeira property investment",
        "Funchal apartment",
        "Silver Coast property Portugal",
        "real estate agency Portugal",
        "Golden Visa Portugal property",
        "Portugal property investment",
    ]),

    # Bali — expansion
    ("real_estate", "thailand_bali", "en", [
        "buy villa Bali",
        "Bali investment property",
        "Seminyak villa for sale",
        "Canggu property investment",
        "Ubud villa for sale",
        "Uluwatu villa",
        "real estate agency Bali",
        "Bali villa investment ROI",
        "buy property Bali foreigner",
    ]),

    # ── FAMILY OFFICE (35.4% hit) ────────────────────────────

    # Switzerland — more specific queries
    ("family_office", "switzerland_fo", "en", [
        "wealth management Zurich",
        "wealth management Geneva",
        "independent asset manager Zurich",
        "Swiss wealth advisory",
        "Swiss external asset manager",
        "Swiss EAM",
        "Lugano asset management",
        "Zurich family office",
        "Geneva family office",
        "Swiss multi family office",
        "Swiss wealth planning",
    ]),

    # Dubai FO — expanded
    ("family_office", "dubai_fo", "en", [
        "family office Dubai",
        "DIFC family office",
        "Dubai wealth advisory",
        "wealth management ADGM",
        "Abu Dhabi family office",
        "UAE family office setup",
        "Dubai multi family office",
        "DFSA regulated advisor Dubai",
    ]),

    # Singapore — expanded
    ("family_office", "singapore_fo", "en", [
        "Singapore family office",
        "family office Singapore setup",
        "Singapore single family office",
        "variable capital company Singapore",
        "VCC Singapore",
        "Singapore wealth management",
        "Singapore multi family office",
        "MAS licensed fund manager",
    ]),

    # PPLI / insurance — new geo
    ("family_office", "ppli_insurance", "en", [
        "PPLI insurance",
        "private placement life insurance",
        "UHNWI insurance wealth",
        "wealth protection insurance international",
        "insurance wrapper wealth structuring",
        "international life insurance broker HNWI",
        "Lombard International insurance",
    ]),

    # Private banks — Russian desks
    ("family_office", "private_banks_ru", "en", [
        "private banking Russian clients",
        "Russian speaking private bank Switzerland",
        "Swiss private bank Russian desk",
        "Singapore private bank Russian",
        "Dubai private bank Russian clients",
        "private bank CIS clients",
        "Julius Baer Russian clients",
        "UBS Russian desk",
    ]),

    # ── INVESTMENT (23.4% hit) ────────────────────────────────

    # Switzerland — expanded
    ("investment", "switzerland", "en", [
        "asset management Switzerland",
        "Swiss investment advisory",
        "Swiss fund management",
        "independent portfolio manager Switzerland",
        "Zurich investment management",
        "Geneva asset management",
        "Swiss hedge fund",
        "Swiss private equity",
    ]),

    # Singapore — new expansion
    ("investment", "singapore", "en", [
        "investment management Singapore",
        "Singapore hedge fund",
        "licensed fund management Singapore",
        "Singapore investment advisory",
        "Singapore capital management",
        "MAS regulated fund Singapore",
    ]),

    # Dubai DIFC — expanded
    ("investment", "dubai_difc", "en", [
        "DIFC investment fund",
        "Dubai investment management",
        "DFSA regulated fund manager",
        "Abu Dhabi investment advisory",
        "UAE asset management ADGM",
        "Dubai hedge fund",
        "Dubai private equity",
    ]),

    # ── LEGAL — best geos only ────────────────────────────────

    # Moscow — international tax + structuring
    ("legal", "moscow", "ru", [
        "международное налоговое планирование Москва",
        "юрист по международным налогам Москва",
        "структурирование активов Москва",
        "корпоративное структурирование международное",
        "создание траста Россия",
        "личный фонд Россия",
        "защита активов юрист Москва",
        "M&A юрист международный Москва",
        "трансграничные сделки юрист Москва",
    ]),

    # UAE legal — company formation
    ("legal", "uae_legal", "en", [
        "law firm Dubai corporate",
        "DMCC company registration",
        "JAFZA company formation",
        "DIFC company formation",
        "ADGM company setup",
        "Dubai freezone company setup",
        "corporate services Abu Dhabi",
        "Dubai mainland company registration",
    ]),
    ("legal", "uae_legal", "ru", [
        "юридическая фирма Дубай",
        "открыть компанию Дубай",
        "регистрация компании ОАЭ фризона",
        "DMCC регистрация компании",
        "бизнес в Дубае открыть",
    ]),

    # Cyprus legal — holding + tax
    ("legal", "cyprus_legal", "en", [
        "Cyprus holding company setup",
        "Cyprus company registration",
        "Cyprus tax advisory firm",
        "Limassol law firm corporate",
        "Cyprus trust formation",
        "Cyprus IP box company",
        "Cyprus corporate structuring",
    ]),
    ("legal", "cyprus_legal", "ru", [
        "регистрация компании Кипр",
        "юридическая фирма Лимассол",
        "холдинг Кипр создание",
        "налоговое планирование Кипр",
        "бухгалтерия Кипр",
    ]),

    # Georgia legal
    ("legal", "georgia_legal", "en", [
        "Georgia company formation IT",
        "Tbilisi business setup company",
        "Georgia virtual zone company",
        "Georgia tax free business",
        "Georgia residence permit business",
    ]),
    ("legal", "georgia_legal", "ru", [
        "открыть компанию Грузия",
        "регистрация бизнеса Тбилиси",
        "виртуальная зона Грузия IT",
        "ВНЖ Грузия через бизнес",
    ]),

    # Estonia legal
    ("legal", "estonia", "en", [
        "Estonia e-Residency company",
        "Estonian company formation services",
        "Estonia crypto license 2025",
        "Estonia fintech license",
        "Estonia EMI license",
    ]),

    # Serbia legal
    ("legal", "serbia_legal", "en", [
        "Serbia company registration DOO",
        "Belgrade business setup services",
        "Serbia corporate services",
        "Serbia freelance visa business",
    ]),

    # Offshore — structures
    ("legal", "offshore", "en", [
        "BVI company formation services",
        "offshore trust formation Nevis",
        "Cayman Islands company formation",
        "international holding structure",
        "Liechtenstein foundation setup",
        "Jersey trust formation",
        "Luxembourg holding company",
    ]),
    ("legal", "offshore", "ru", [
        "оффшорная компания BVI",
        "регистрация оффшора Сейшелы",
        "оффшорный траст",
        "холдинговая структура международная",
    ]),

    # ══════════════════════════════════════════════════════════════════
    # ROUND 2: New keywords based on best-performing query patterns
    # (city-specific, service+city, English geo, product-specific)
    # ══════════════════════════════════════════════════════════════════

    # ── legal / moscow — tpq 0.099 (top converter) ──
    ("legal", "moscow", "ru", [
        "юрист по структурированию активов Москва",
        "международная юридическая компания Москва",
        "юрист по зарубежным активам Москва",
        "холдинговая структура юрист Москва",
        "юрист по международным сделкам Петербург",
        "налоговый юрист для бизнеса за рубежом",
        "юридический консалтинг международный Москва",
        "защита активов юрист Москва",
        "юрист КИК Москва",
        "международный налоговый консультант Петербург",
        "юрист оффшорная структура Москва",
        "юрист для нерезидентов России",
        "трансграничный юрист Россия",
        "сопровождение сделок за рубежом юрист",
        "юрист по наследственному планированию Москва",
        "зарубежный холдинг юрист Москва",
        "юрист по семейным фондам Москва",
        "структурирование бизнеса юрист Россия",
        "оптимизация налогов при релокации юрист",
        "юридическое сопровождение инвестиций за рубежом",
    ]),
    ("legal", "moscow", "en", [
        "international law firm Moscow",
        "cross-border transactions lawyer Russia",
        "asset protection attorney Moscow",
        "Russian international tax lawyer",
        "corporate structuring lawyer Moscow",
        "trust formation lawyer Russia",
        "M&A lawyer Russia cross-border",
        "wealth structuring attorney Moscow",
        "international estate planning Russia",
        "holding company setup Russia",
    ]),

    # ── legal / uae_legal — tpq 0.065 ──
    ("legal", "uae_legal", "en", [
        "freezone company formation consultant",
        "Dubai corporate structuring advisory",
        "DIFC company formation services",
        "ADGM company registration",
        "offshore company formation Abu Dhabi",
        "Dubai trust formation",
        "UAE holding company setup",
        "business restructuring consultant Dubai",
        "international tax planning Dubai",
        "corporate governance advisory UAE",
        "DMCC company registration consultant",
        "RAKEZ company formation",
        "tax advisory services Dubai",
    ]),
    ("legal", "uae_legal", "ru", [
        "открыть бизнес в ОАЭ консультант",
        "регистрация компании в Дубае фризона",
        "юрист для бизнеса ОАЭ",
        "корпоративное структурирование Дубай",
        "налоговое планирование ОАЭ",
        "бизнес консалтинг Дубай",
        "юридическое сопровождение бизнеса ОАЭ",
        "фризона DMCC регистрация",
        "открыть фирму в ОАЭ",
        "лицензия на бизнес Дубай",
    ]),

    # ── legal / cyprus_legal — tpq 0.053 ──
    ("legal", "cyprus_legal", "en", [
        "Cyprus international tax planning",
        "Cyprus holding company registration",
        "Limassol corporate services provider",
        "Cyprus IP box company formation",
        "Cyprus fund management company",
        "Cyprus fintech license application",
        "Paphos corporate services",
        "Cyprus substance requirements advisor",
        "Cyprus audit firm international",
        "Cyprus real estate company formation",
    ]),
    ("legal", "cyprus_legal", "ru", [
        "юрист Кипр для бизнеса",
        "регистрация холдинга Кипр",
        "налоговое планирование Кипр компания",
        "аудиторская компания Лимассол",
        "открыть компанию на Кипре",
        "IP box Кипр регистрация",
        "юридическая фирма Лимассол",
        "корпоративное структурирование Кипр",
    ]),

    # ── legal / georgia_legal — new keywords ──
    ("legal", "georgia_legal", "en", [
        "Tbilisi IT company registration",
        "Georgia virtual zone company",
        "Georgia small business status setup",
        "Georgia residence permit entrepreneur",
        "business consultant Tbilisi",
        "company formation Georgia for foreigners",
        "Georgia freelancer visa services",
    ]),
    ("legal", "georgia_legal", "ru", [
        "IT компания Грузия регистрация",
        "бизнес консультант Тбилиси",
        "открыть бизнес в Грузии из России",
        "виртуальная зона Грузия IT",
        "ВНЖ Грузия через бизнес",
        "юрист Батуми для бизнеса",
        "регистрация ООО в Грузии для россиян",
    ]),

    # ── legal / serbia_legal — new keywords ──
    ("legal", "serbia_legal", "en", [
        "company registration Belgrade for foreigners",
        "Serbia IT company formation",
        "Serbia digital nomad visa services",
        "Belgrade business consultant",
        "Serbia DOO company formation service",
        "Serbia tax residence setup",
    ]),
    ("legal", "serbia_legal", "ru", [
        "открыть бизнес в Сербии из России",
        "регистрация компании Белград для россиян",
        "юрист Сербия для бизнеса",
        "ВНЖ Сербия через бизнес",
        "налоговый консультант Сербия",
        "бухгалтерия Сербия для иностранцев",
    ]),

    # ── real_estate / turkey — tpq 0.096 (top converter!) ──
    ("real_estate", "turkey", "ru", [
        "элитная недвижимость Стамбул",
        "элитная недвижимость Анталья",
        "риелтор для россиян Стамбул",
        "риелтор для россиян Анталья",
        "виллы в Аланье для россиян",
        "инвестиции недвижимость Анталья",
        "инвестиции недвижимость Стамбул",
        "коммерческая недвижимость Стамбул",
        "рассрочка квартира Турция",
        "новый жилой комплекс Анталья",
        "застройщик Анталья",
        "застройщик Стамбул",
        "агентство недвижимости Аланья",
        "агентство недвижимости Стамбул",
        "агентство недвижимости Анталья",
        "жилой комплекс Мерсин",
        "продажа квартир Калкан",
        "продажа квартир Бодрум",
        "новостройки Аланья",
        "вилла с бассейном Анталья",
        "вилла с видом на море Аланья",
        "комплекс апартаментов Кемер",
        "пентхаус Стамбул",
        "дуплекс Анталья",
        "квартира Анкара купить",
    ]),
    ("real_estate", "turkey", "en", [
        "luxury apartment Istanbul",
        "luxury villa Antalya",
        "property agent Istanbul for foreigners",
        "property agent Antalya English speaking",
        "investment property Antalya",
        "investment property Istanbul",
        "commercial property Istanbul",
        "property installment Turkey",
        "new residential project Antalya",
        "property developer Antalya",
        "property developer Istanbul",
        "real estate agency Alanya",
        "real estate agency Istanbul",
        "real estate agency Antalya",
        "sea view apartment Turkey",
        "beachfront property Antalya",
        "penthouse Istanbul for sale",
        "villa with pool Alanya",
        "duplex apartment Turkey",
        "new build property Bodrum",
        "new build property Fethiye",
        "Mersin property agent",
        "Side real estate agency",
        "Kemer property for sale",
        "Turkey property management",
    ]),

    # ── real_estate / thailand_bali — tpq 0.068 ──
    ("real_estate", "thailand_bali", "ru", [
        "агент недвижимости Самуи",
        "агент недвижимости Краби",
        "купить виллу Самуи",
        "аренда виллы Пхукет с последующим выкупом",
        "инвестиции в недвижимость Пхукет",
        "инвестиции в кондо Паттайя",
        "новостройки Пхукет",
        "новостройки Паттайя",
        "русскоязычный риелтор Паттайя",
        "русскоязычный риелтор Самуи",
        "элитная недвижимость Пхукет",
        "вилла с бассейном Пхукет",
        "купить таунхаус Пхукет",
        "застройщик Пхукет",
        "жилой комплекс Пхукет",
        "квартира Паттайя у моря",
        "вилла Чиангмай",
        "купить дом Хуа Хин",
        "недвижимость Пхукет Раваи",
        "недвижимость Пхукет Ката",
        "недвижимость Пхукет Камала",
        "вилла Улувату Бали",
        "вилла Джимбаран Бали",
        "вилла Нуса Дуа Бали",
        "вилла Перенан Бали",
    ]),
    ("real_estate", "thailand_bali", "en", [
        "property agent Koh Samui",
        "property agent Krabi",
        "buy villa Koh Samui",
        "Phuket property investment return",
        "Pattaya condo investment",
        "new development Pattaya",
        "English speaking agent Phuket",
        "luxury villa Phuket",
        "beachfront villa Phuket",
        "pool villa Phuket for sale",
        "Phuket real estate agency for foreigners",
        "condo Rawai Phuket",
        "property Kata Beach Phuket",
        "Kamala property Phuket",
        "townhouse Phuket",
        "Phuket developer",
        "Bali villa for investment",
        "Uluwatu villa for sale",
        "Jimbaran property Bali",
        "Nusa Dua villa Bali",
        "Pererenan villa Bali",
        "Tabanan property Bali",
        "leasehold villa Bali",
        "Bali property management company",
        "Bali villa rental investment",
    ]),

    # ── migration / portugal_gv — tpq 0.091 ──
    ("migration", "portugal_gv", "en", [
        "Portugal Golden Visa fund investment",
        "Lisbon Golden Visa consultant",
        "Porto Golden Visa agent",
        "Portugal D7 visa consultant",
        "Portugal NHR tax regime consultant",
        "Portugal digital nomad visa",
        "residency planning Portugal",
        "retire in Portugal consultant",
        "Portugal Golden Visa lawyer",
        "Portugal real estate for residency",
        "relocate to Portugal services",
        "Portugal startup visa",
    ]),
    ("migration", "portugal_gv", "ru", [
        "Golden Visa Португалия консультант",
        "ВНЖ Португалия через фонд",
        "переезд в Португалию помощь",
        "Лиссабон иммиграционный агент",
        "Порту иммиграционный консультант",
        "D7 виза Португалия",
        "NHR налоговый режим Португалия",
        "Golden Visa Алгарве",
        "иммиграция в Португалию из России",
        "резидентство Португалия",
        "ВНЖ Португалия недвижимость",
        "стартап виза Португалия",
    ]),

    # ── migration / spain_gv — tpq 0.056 ──
    ("migration", "spain_gv", "en", [
        "Barcelona Golden Visa lawyer",
        "Madrid Golden Visa consultant",
        "Spain non-lucrative visa",
        "Spain digital nomad visa",
        "Malaga Golden Visa",
        "Valencia Golden Visa",
        "Costa del Sol Golden Visa",
        "Spain entrepreneur visa",
        "Spain investor residence",
        "relocate to Spain services",
        "Spain tax residence advisor",
    ]),
    ("migration", "spain_gv", "ru", [
        "Golden Visa Испания консультант",
        "ВНЖ Испания через недвижимость",
        "переезд в Испанию помощь",
        "иммиграционный агент Барселона",
        "иммиграционный консультант Мадрид",
        "Коста дель Соль Golden Visa",
        "резидентство Испания через инвестиции",
        "нелюкративная виза Испания",
        "иммиграция в Испанию из России",
        "визовый агент Испания",
    ]),

    # ── migration / montenegro_rp — tpq 0.065 ──
    ("migration", "montenegro_rp", "en", [
        "Montenegro residency agent",
        "Montenegro residence permit property",
        "Montenegro citizenship consultant",
        "Podgorica immigration lawyer",
        "Montenegro temporary residence",
        "relocate to Montenegro",
        "Montenegro business residence",
        "Montenegro retirement visa",
    ]),
    ("migration", "montenegro_rp", "ru", [
        "ВНЖ Черногория через недвижимость консультант",
        "переезд в Черногорию помощь",
        "иммиграционный агент Черногория",
        "ПМЖ Черногория консультант",
        "резидентство Черногория",
        "юрист ВНЖ Черногория",
        "временное проживание Черногория",
        "переезд в Будву",
    ]),

    # ── migration / general_migration — tpq 0.286! (highest) ──
    ("migration", "general_migration", "ru", [
        "релокационный сервис для бизнеса",
        "релокация семьи за рубеж",
        "релокационный сервис Россия",
        "помощь с переездом за границу",
        "релокация из России в Европу",
        "переезд за рубеж с семьей",
        "эмиграция из России консультант",
        "куда переехать из России 2025",
        "куда переехать из России 2026",
        "лучшие страны для эмиграции",
        "релокация бизнеса за рубеж",
        "переезд компании за рубеж",
        "консультант по релокации Москва",
        "консультант по релокации Петербург",
        "агент по переезду за рубеж",
        "помощь в эмиграции из России",
    ]),
    ("migration", "general_migration", "en", [
        "relocation consultant Russia",
        "Russian emigration consulting",
        "relocation services from Russia",
        "global mobility consultant CIS",
        "expat relocation advisory",
        "corporate relocation Russia",
        "family relocation international",
        "relocation agent Moscow",
    ]),

    # ── migration / greece_gv — tpq 0.043 ──
    ("migration", "greece_gv", "en", [
        "Athens Golden Visa property",
        "Crete Golden Visa agent",
        "Thessaloniki Golden Visa",
        "Greece residence permit lawyer",
        "Greek Golden Visa real estate",
        "relocate to Greece consultant",
        "Greece retirement visa",
        "Greece digital nomad visa",
    ]),
    ("migration", "greece_gv", "ru", [
        "Golden Visa Греция консультант",
        "ВНЖ Греция через недвижимость",
        "переезд в Грецию помощь",
        "иммиграция Греция из России",
        "Афины Golden Visa",
        "Крит ВНЖ через недвижимость",
        "Салоники Golden Visa",
        "резидентство Греция инвестиции",
    ]),

    # ── investment / switzerland — tpq 0.056 ──
    ("investment", "switzerland", "en", [
        "independent asset manager Zurich",
        "independent asset manager Geneva",
        "Swiss wealth advisory firm",
        "asset management Zurich for Russians",
        "external asset manager Switzerland",
        "private wealth management Lugano",
        "Swiss investment advisory",
        "portfolio management Geneva",
        "wealth advisory Lausanne",
        "Swiss EAM for CIS clients",
    ]),
    ("investment", "switzerland", "ru", [
        "управление активами Швейцария для россиян",
        "инвестиционный советник Цюрих",
        "инвестиционный советник Женева",
        "швейцарский управляющий активами",
        "частное управление капиталом Швейцария",
        "портфельное управление Лугано",
        "EAM Швейцария для россиян",
        "инвестиционный бутик Швейцария",
    ]),

    # ── investment / moscow — tpq 0.034 ──
    ("investment", "moscow", "ru", [
        "инвестиционная компания для HNWI Москва",
        "управление крупным капиталом Москва",
        "инвестиционный советник для состоятельных",
        "портфельное управление Москва",
        "финансовый консультант VIP Москва",
        "брокер для крупных инвесторов Москва",
        "инвестиционный бутик Москва",
        "управляющая компания для частных клиентов",
        "доверительное управление Петербург",
        "персональное управление инвестициями",
    ]),

    # ── crypto / dubai_crypto — tpq 0.050 ──
    ("crypto", "dubai_crypto", "ru", [
        "OTC крипто Дубай",
        "купить USDT Дубай",
        "обмен криптовалюты Дубай",
        "крипто обменник Дубай",
        "биткоин OTC Дубай",
        "криптовалютный фонд Дубай",
        "крипто компания ОАЭ",
        "VARA лицензия Дубай",
        "крипто брокер Дубай",
    ]),
    ("crypto", "dubai_crypto", "en", [
        "OTC crypto desk Dubai",
        "buy USDT Dubai",
        "crypto exchange Dubai licensed",
        "cryptocurrency fund Dubai",
        "VARA license Dubai",
        "crypto broker Dubai",
        "Bitcoin OTC Dubai",
        "crypto custody Dubai",
        "digital asset management UAE",
    ]),

    # ── crypto / moscow_crypto — tpq 0.033 ──
    ("crypto", "moscow_crypto", "ru", [
        "OTC крипто сделка Москва",
        "обмен USDT на рубли Москва",
        "купить биткоин Москва крупная сумма",
        "внебиржевая покупка крипто Петербург",
        "крипто обменник Петербург надёжный",
        "крипто фонд Москва",
        "управление крипто активами Москва",
        "крипто инвестиции фонд Россия",
    ]),

    # ── importers / moscow_import — tpq 0.041 ──
    ("importers", "moscow_import", "ru", [
        "импорт товаров из Китая Москва",
        "импорт товаров из Турции",
        "импорт из Дубай",
        "ВЭД агент Москва",
        "таможенный брокер импорт",
        "параллельный импорт из ОАЭ",
        "параллельный импорт из Турции",
        "поставки из Китая в Россию",
        "логистика импорт Москва",
        "закупка товаров за рубежом агент",
        "байер Дубай для бизнеса",
        "импорт электроники из Китая",
        "импорт запчастей из ОАЭ",
        "ВЭД консультант Москва",
    ]),

    # ── family_office / switzerland_fo — tpq 0.043 ──
    ("family_office", "switzerland_fo", "en", [
        "multi family office Zurich",
        "multi family office Geneva",
        "independent family office Switzerland",
        "family office advisory Lugano",
        "Swiss family governance",
        "wealth succession planning Switzerland",
        "Swiss single family office setup",
        "family office compliance Switzerland",
        "family office real estate Switzerland",
    ]),
    ("family_office", "switzerland_fo", "ru", [
        "семейный офис Швейцария",
        "мультисемейный офис Цюрих",
        "мультисемейный офис Женева",
        "управление семейным капиталом Швейцария",
        "наследственное планирование Швейцария",
        "семейный офис для россиян Швейцария",
    ]),

    # ── real_estate / montenegro — tpq 0.042 ──
    ("real_estate", "montenegro", "ru", [
        "элитная недвижимость Будва",
        "элитная недвижимость Тиват",
        "инвестиции в недвижимость Черногория",
        "квартира в Порто Монтенегро",
        "новостройки Будва",
        "новостройки Тиват",
        "застройщик Черногория",
        "пентхаус Будва",
        "вилла с видом на море Черногория",
        "риелтор Черногория для россиян",
        "агентство недвижимости Будва",
        "агентство недвижимости Тиват",
    ]),
    ("real_estate", "montenegro", "en", [
        "luxury apartment Budva",
        "luxury apartment Tivat",
        "investment property Montenegro",
        "Porto Montenegro real estate",
        "new development Budva",
        "new development Tivat",
        "Montenegro property developer",
        "sea view apartment Montenegro",
        "real estate agency Budva",
        "real estate agency Tivat",
        "beachfront property Montenegro",
    ]),

    # ── real_estate / spain_portugal — 0 targets but 418 new domains ──
    ("real_estate", "spain_portugal", "ru", [
        "элитная недвижимость Марбелья",
        "элитная недвижимость Барселона",
        "риелтор Испания для россиян",
        "риелтор Португалия для россиян",
        "инвестиции недвижимость Испания",
        "инвестиции недвижимость Португалия",
        "новостройки Коста дель Соль",
        "новостройки Лиссабон",
        "агентство недвижимости Марбелья",
        "агентство недвижимости Барселона",
        "агентство недвижимости Лиссабон",
        "квартира Алгарве купить",
        "вилла Ибица",
        "вилла Коста Бланка",
        "квартира Валенсия купить",
    ]),
    ("real_estate", "spain_portugal", "en", [
        "luxury property Marbella",
        "luxury property Barcelona",
        "property agent Spain English speaking",
        "property agent Portugal for foreigners",
        "investment property Spain",
        "investment property Portugal",
        "new development Costa del Sol",
        "new development Lisbon",
        "Marbella real estate agency",
        "Barcelona real estate agency",
        "Lisbon real estate agency",
        "Algarve property agent",
        "Ibiza villa for sale",
        "Costa Blanca property agent",
        "Valencia property for sale",
    ]),

    # ── real_estate / greece — tpq 0.017 ──
    ("real_estate", "greece", "ru", [
        "элитная недвижимость Афины",
        "элитная недвижимость Крит",
        "риелтор Греция для россиян",
        "инвестиции недвижимость Греция",
        "вилла на Крите купить",
        "квартира Афины купить",
        "недвижимость Салоники",
        "недвижимость Родос",
        "недвижимость Халкидики",
        "вилла Миконос",
        "вилла Санторини",
        "агентство недвижимости Афины",
        "агентство недвижимости Крит",
    ]),
    ("real_estate", "greece", "en", [
        "luxury property Athens",
        "luxury villa Crete",
        "property agent Greece for foreigners",
        "investment property Athens",
        "Thessaloniki real estate agent",
        "Rhodes property for sale",
        "Halkidiki property agent",
        "Mykonos villa for sale",
        "Santorini property",
        "Athens real estate agency",
        "Crete real estate agency",
        "Corfu villa for sale",
        "Peloponnese property",
    ]),

    # ── migration / caribbean_cbi — new additional ──
    ("migration", "caribbean_cbi", "en", [
        "St Kitts citizenship consultant",
        "Dominica CBI agent",
        "Grenada citizenship agent",
        "Antigua citizenship agent",
        "Caribbean CBI advisory firm",
        "second passport consultant",
        "citizenship by investment lawyer",
        "passport by investment agent",
        "Vanuatu citizenship agent",
    ]),
    ("migration", "caribbean_cbi", "ru", [
        "гражданство Сент-Китс агент",
        "гражданство Доминика консультант",
        "гражданство Гренада агент",
        "гражданство за инвестиции консультант",
        "второй паспорт агент",
        "паспорт за инвестиции консультант",
        "карибское гражданство помощь",
    ]),

    # ── migration / uae_visa — tpq 0.021 ──
    ("migration", "uae_visa", "en", [
        "Dubai Golden Visa consultant",
        "UAE investor visa agent",
        "Dubai 10 year visa consultant",
        "Abu Dhabi Golden Visa agent",
        "UAE freelance visa services",
        "Dubai startup visa consultant",
        "UAE entrepreneur visa agent",
        "Emirates ID services",
    ]),
    ("migration", "uae_visa", "ru", [
        "Golden Visa Дубай консультант",
        "виза инвестора ОАЭ агент",
        "резидентская виза Дубай помощь",
        "фрилансер виза Дубай",
        "предпринимательская виза ОАЭ",
        "Emirates ID получить помощь",
        "стартап виза Дубай",
    ]),

    # ── migration / eb5_usa — new ──
    ("migration", "eb5_usa", "en", [
        "EB-5 visa lawyer",
        "EB-5 regional center investment",
        "EB-5 direct investment consultant",
        "green card through investment consultant",
        "US immigration investor program",
        "EB-5 visa from Russia",
        "E-2 visa consultant",
        "US investor immigration lawyer",
    ]),
    ("migration", "eb5_usa", "ru", [
        "EB-5 виза адвокат",
        "грин карта за инвестиции консультант",
        "иммиграция в США через инвестиции",
        "EB-5 программа консультант",
        "инвестиционная виза США из России",
        "E-2 виза консультант",
    ]),

    # ── investment / dubai_difc — tpq 0.029 ──
    ("investment", "dubai_difc", "en", [
        "DIFC wealth manager",
        "DIFC asset management company",
        "Dubai wealth advisory firm",
        "DFSA regulated investment firm",
        "financial advisor Dubai DIFC",
        "ADGM asset management",
        "Abu Dhabi investment advisory",
        "Dubai portfolio management firm",
    ]),
    ("investment", "dubai_difc", "ru", [
        "управление активами Дубай",
        "инвестиционный советник Дубай",
        "финансовый консультант Дубай",
        "управление портфелем ОАЭ",
        "инвестиционная компания DIFC",
        "управление капиталом ОАЭ",
    ]),

    # ── investment / singapore — new ──
    ("investment", "singapore", "en", [
        "Singapore licensed fund manager",
        "MAS regulated asset manager",
        "Singapore multi family office",
        "Singapore wealth advisory",
        "Singapore EAM",
        "Singapore capital management firm",
        "Raffles Place investment advisory",
    ]),

    # ══════════════════════════════════════════════════════════════════
    # ROUND 3: Hyper-granular geo queries — cities, districts, areas
    # City/district-specific queries are the top converters
    # ══════════════════════════════════════════════════════════════════

    # ────────────────────────────────────────────
    # REAL ESTATE / TURKEY — districts & areas
    # ────────────────────────────────────────────
    ("real_estate", "turkey", "ru", [
        # Istanbul districts
        "недвижимость Бешикташ Стамбул", "квартира Кадыкёй Стамбул",
        "квартира Шишли Стамбул", "квартира Бакыркёй Стамбул",
        "квартира Бейоглу Стамбул", "недвижимость Сарыер Стамбул",
        "квартира Ускюдар Стамбул", "недвижимость Башакшехир Стамбул",
        "квартира Эсенюрт Стамбул", "пентхаус Бейликдюзю Стамбул",
        "квартира Маслак Стамбул", "недвижимость Левент Стамбул",
        "квартира Нишанташи Стамбул", "квартира Тарабья Стамбул",
        "вилла Бююкчекмедже Стамбул",
        # Antalya districts
        "квартира Коньяалты Анталья", "квартира Лара Анталья",
        "квартира Кепез Анталья", "вилла Дёшемеалты Анталья",
        "недвижимость Муратпаша Анталья", "квартира Хурма Анталья",
        "вилла Куздере Анталья",
        # Alanya districts
        "квартира Махмутлар Аланья", "квартира Оба Аланья",
        "квартира Тосмур Аланья", "квартира Авсаллар Аланья",
        "квартира Кестель Аланья", "квартира Конаклы Аланья",
        "пентхаус Клеопатра Аланья", "вилла Каргыджак Аланья",
        # Bodrum areas
        "вилла Ялыкавак Бодрум", "вилла Гюмюшлюк Бодрум",
        "вилла Тюркбюкю Бодрум", "квартира Битез Бодрум",
        "квартира Гюндоган Бодрум", "недвижимость Ортакент Бодрум",
        # Other Turkish cities - specifics
        "квартира Газипаша", "недвижимость Дидим", "квартира Кушадасы",
        "недвижимость Чешме", "вилла Дальян", "вилла Каш",
        "недвижимость Антакья", "квартира Конья",
    ]),
    ("real_estate", "turkey", "en", [
        # Istanbul districts
        "property Besiktas Istanbul", "apartment Kadikoy Istanbul",
        "apartment Sisli Istanbul", "property Sariyer Istanbul",
        "apartment Basaksehir Istanbul", "property Maslak Istanbul",
        "apartment Levent Istanbul", "property Nisantasi Istanbul",
        "apartment Beyoglu Istanbul", "property Uskudar Istanbul",
        "penthouse Beylikduzu Istanbul", "villa Buyukcekmece Istanbul",
        # Antalya districts
        "apartment Konyaalti Antalya", "apartment Lara Antalya",
        "property Kepez Antalya", "villa Dosemealti Antalya",
        "property Muratpasa Antalya", "apartment Hurma Antalya",
        # Alanya districts
        "apartment Mahmutlar Alanya", "apartment Oba Alanya",
        "apartment Tosmur Alanya", "apartment Avsallar Alanya",
        "apartment Kestel Alanya", "apartment Konakli Alanya",
        "penthouse Cleopatra Alanya", "villa Kargicak Alanya",
        # Bodrum areas
        "villa Yalikavak Bodrum", "villa Gumusluk Bodrum",
        "villa Turkbuku Bodrum", "property Bitez Bodrum",
        "property Gundogan Bodrum", "property Ortakent Bodrum",
        # Other cities
        "property Gazipasa", "property Didim", "property Kusadasi",
        "property Cesme", "villa Dalyan", "villa Kas Turkey",
        "property Demre", "apartment Finike",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / THAILAND_BALI — areas & beaches
    # ────────────────────────────────────────────
    ("real_estate", "thailand_bali", "ru", [
        # Phuket beaches/areas
        "недвижимость Най Харн Пхукет", "вилла Лаян Пхукет",
        "вилла Банг Тао Пхукет", "кондо Сурин Пхукет",
        "вилла Чернг Талай Пхукет", "недвижимость Най Янг Пхукет",
        "вилла Лагуна Пхукет", "квартира Патонг Пхукет",
        "недвижимость Таланг Пхукет", "вилла Май Кхао Пхукет",
        "кондо Карон Пхукет",
        # Pattaya areas
        "кондо Джомтьен Паттайя", "кондо Пратамнак Паттайя",
        "кондо Вонгамат Паттайя", "кондо На Джомтьен Паттайя",
        "кондо Центральная Паттайя", "недвижимость Банг Саре",
        # Samui areas
        "вилла Бопхут Самуи", "вилла Чавенг Самуи",
        "вилла Маенам Самуи", "вилла Ламай Самуи",
        "недвижимость Банг По Самуи",
        # Bangkok areas
        "кондо Сукхумвит Бангкок", "кондо Силом Бангкок",
        "кондо Саторн Бангкок", "кондо Он Нут Бангкок",
        "квартира Тонг Ло Бангкок", "кондо Асок Бангкок",
        # Bali areas
        "вилла Берава Бали", "вилла Умалас Бали",
        "вилла Кечак Бали", "вилла Менджанган Бали",
        "вилла Амед Бали", "вилла Ловина Бали",
        "вилла Букит Бали", "вилла Кута Утара Бали",
    ]),
    ("real_estate", "thailand_bali", "en", [
        # Phuket beaches/areas
        "villa Nai Harn Phuket", "villa Layan Phuket",
        "condo Surin Beach Phuket", "villa Cherng Talay Phuket",
        "property Nai Yang Phuket", "villa Laguna Phuket",
        "apartment Patong Phuket", "property Thalang Phuket",
        "villa Mai Khao Phuket", "condo Karon Phuket",
        "villa Cape Yamu Phuket", "property Ao Po Phuket",
        # Pattaya areas
        "condo Jomtien Pattaya", "condo Pratumnak Pattaya",
        "condo Wongamat Pattaya", "condo Na Jomtien Pattaya",
        "property Bang Saray", "condo Central Pattaya",
        # Samui areas
        "villa Bophut Koh Samui", "villa Chaweng Koh Samui",
        "villa Maenam Koh Samui", "villa Lamai Koh Samui",
        "property Bang Po Samui",
        # Bangkok
        "condo Sukhumvit Bangkok", "condo Silom Bangkok",
        "condo Sathorn Bangkok", "condo Thonglor Bangkok",
        "condo Asoke Bangkok", "condo On Nut Bangkok",
        # Bali areas
        "villa Berawa Bali", "villa Umalas Bali",
        "villa Amed Bali", "villa Lovina Bali",
        "villa Bukit Bali", "villa Kerobokan Bali",
        "villa Sanur Bali", "villa Candidasa Bali",
        "villa Tegallalang Bali", "villa Munduk Bali",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / SPAIN_PORTUGAL — cities & coasts
    # ────────────────────────────────────────────
    ("real_estate", "spain_portugal", "ru", [
        # Costa del Sol cities
        "недвижимость Фуэнхирола", "недвижимость Михас",
        "недвижимость Бенальмадена", "недвижимость Нерха",
        "недвижимость Эстепона", "квартира Торремолинос",
        "вилла Сотогранде", "недвижимость Манильва",
        # Costa Blanca cities
        "квартира Торревьеха", "квартира Бенидорм",
        "недвижимость Хавеа", "недвижимость Дения",
        "квартира Кальпе", "недвижимость Морайра",
        "недвижимость Альтеа", "квартира Ориуэла Коста",
        # Barcelona areas
        "квартира Эшампле Барселона", "квартира Сарриа Барселона",
        "квартира Грасиа Барселона", "недвижимость Ситжес",
        "недвижимость Кастельдефельс", "недвижимость Гава",
        # Mallorca
        "вилла Пальма де Майорка", "вилла Сольер Майорка",
        "недвижимость Андрач Майорка", "квартира Пуэрто Поленса",
        "недвижимость Санта Понса", "вилла Дейя Майорка",
        # Ibiza
        "вилла Сан Хосе Ибица", "квартира Ибица город",
        "вилла Санта Эулалия Ибица", "недвижимость Сан Антонио Ибица",
        # Canary Islands
        "квартира Коста Адехе Тенерифе", "недвижимость Лас Америкас",
        "квартира Санта Крус Тенерифе", "недвижимость Маспаломас",
        # Portugal cities
        "квартира Шиаду Лиссабон", "квартира Алфама Лиссабон",
        "квартира Принсипе Реал Лиссабон", "недвижимость Белен Лиссабон",
        "недвижимость Эшторил", "квартира Синтра",
        "квартира Рибейра Порту", "недвижимость Фару",
        "недвижимость Лагуш", "вилла Виламоура",
        "недвижимость Тавира", "квартира Фуншал Мадейра",
        "недвижимость Назаре", "недвижимость Компорта",
        "квартира Авейру",
    ]),
    ("real_estate", "spain_portugal", "en", [
        # Costa del Sol
        "property Fuengirola", "property Mijas Costa",
        "property Benalmadena", "property Nerja",
        "villa Sotogrande", "property Manilva",
        # Costa Blanca
        "apartment Torrevieja", "property Javea",
        "property Denia", "property Calpe",
        "property Moraira", "property Altea",
        "apartment Orihuela Costa",
        # Barcelona area
        "apartment Eixample Barcelona", "property Sarria Barcelona",
        "property Sitges", "property Castelldefels",
        # Mallorca
        "villa Palma de Mallorca", "villa Soller Mallorca",
        "property Andratx Mallorca", "property Puerto Pollensa",
        "villa Deya Mallorca", "property Santa Ponsa",
        # Ibiza
        "villa San Jose Ibiza", "property Santa Eulalia Ibiza",
        "property San Antonio Ibiza",
        # Canaries
        "property Costa Adeje Tenerife", "property Las Americas Tenerife",
        "apartment Maspalomas Gran Canaria",
        # Portugal cities/areas
        "apartment Chiado Lisbon", "apartment Alfama Lisbon",
        "apartment Principe Real Lisbon", "property Belem Lisbon",
        "property Estoril", "property Sintra",
        "apartment Ribeira Porto", "property Faro",
        "property Lagos Portugal", "villa Vilamoura",
        "property Tavira", "apartment Funchal Madeira",
        "property Nazare Portugal", "property Comporta",
        "property Aveiro",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / GREECE — islands & areas
    # ────────────────────────────────────────────
    ("real_estate", "greece", "ru", [
        # Athens areas
        "квартира Глифада Афины", "квартира Вула Афины",
        "квартира Кифисия Афины", "квартира Колонаки Афины",
        "недвижимость Пирей", "квартира Маруси Афины",
        "недвижимость Палео Фалиро", "квартира Неа Смирни",
        # Crete cities
        "вилла Ханья Крит", "вилла Ретимно Крит",
        "квартира Ираклион Крит", "вилла Элунда Крит",
        "недвижимость Агиос Николаос Крит", "вилла Киссамос Крит",
        # Islands
        "вилла Парос", "вилла Наксос", "квартира Закинф",
        "вилла Кефалония", "вилла Скиатос", "вилла Лефкада",
        "вилла Тасос", "недвижимость Эгина",
        "квартира Спецес", "вилла Идра",
        # Halkidiki
        "вилла Кассандра Халкидики", "вилла Ситония Халкидики",
        "недвижимость Пефкохори Халкидики",
        # Peloponnese
        "недвижимость Нафплион", "вилла Толо",
        "недвижимость Каламата", "вилла Порто Хели",
    ]),
    ("real_estate", "greece", "en", [
        # Athens areas
        "apartment Glyfada Athens", "apartment Voula Athens",
        "apartment Kifisia Athens", "apartment Kolonaki Athens",
        "property Piraeus", "property Paleo Faliro",
        # Crete cities
        "villa Chania Crete", "villa Rethymno Crete",
        "apartment Heraklion Crete", "villa Elounda Crete",
        "property Agios Nikolaos Crete", "villa Kissamos Crete",
        # Islands
        "villa Paros", "villa Naxos", "property Zakynthos",
        "villa Kefalonia", "villa Skiathos", "villa Lefkada",
        "villa Thassos", "property Aegina",
        "property Spetses", "villa Hydra",
        # Halkidiki
        "villa Kassandra Halkidiki", "villa Sithonia Halkidiki",
        "property Pefkohori Halkidiki",
        # Peloponnese
        "property Nafplio", "villa Porto Heli",
        "property Kalamata",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / CYPRUS — cities & areas
    # ────────────────────────────────────────────
    ("real_estate", "cyprus", "ru", [
        # Limassol areas
        "квартира Гермасойя Лимассол", "квартира Меса Гейтония Лимассол",
        "квартира Неаполис Лимассол", "квартира Агиос Тихонас Лимассол",
        "квартира Потамос Гермасойяс", "вилла Мони Лимассол",
        "вилла Писсури", "недвижимость Амафунта Лимассол",
        "квартира набережная Лимассол Марина",
        # Paphos areas
        "вилла Корал Бэй Пафос", "квартира Като Пафос",
        "вилла Пейя Пафос", "недвижимость Тала Пафос",
        "квартира Кисонерга Пафос", "вилла Полис Хрисоху",
        # Larnaca areas
        "квартира Маккензи Ларнака", "недвижимость Дромолаксия",
        "недвижимость Ливадия Ларнака", "квартира Фоиникудес Ларнака",
        # Famagusta
        "квартира Паралимни", "квартира Дериния",
        "квартира Каппарис", "недвижимость Айя Напа",
    ]),
    ("real_estate", "cyprus", "en", [
        # Limassol areas
        "apartment Germasogeia Limassol", "apartment Neapolis Limassol",
        "apartment Agios Tychonas Limassol", "villa Monagroulli Limassol",
        "villa Pissouri Cyprus", "property Amathus Limassol",
        "apartment Limassol Marina",
        # Paphos areas
        "villa Coral Bay Paphos", "apartment Kato Paphos",
        "villa Peyia Paphos", "property Tala Paphos",
        "apartment Kissonerga Paphos", "villa Polis Chrysochous",
        # Larnaca
        "apartment Mackenzie Larnaca", "property Dhromolaxia",
        "property Livadia Larnaca",
        # Famagusta
        "apartment Paralimni", "apartment Deryneia",
        "property Kapparis Cyprus", "property Protaras",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / MONTENEGRO — towns & areas
    # ────────────────────────────────────────────
    ("real_estate", "montenegro", "ru", [
        # Budva specifics
        "квартира Бечичи Будва", "квартира Рафаиловичи Будва",
        "квартира Пржно Будва", "квартира Свети Стефан",
        "квартира старый город Будва",
        # Tivat
        "квартира Донья Ластва Тиват", "квартира Селяново Тиват",
        "квартира Лепетане", "вилла Крашичи Тиват",
        # Kotor
        "квартира Доброта Котор", "квартира Столив Котор",
        "квартира Муо Котор", "квартира Пераст",
        "квартира Рисан",
        # Herceg Novi
        "квартира Мелине Херцег Нови", "квартира Игало",
        "квартира Биела", "квартира Дженовичи",
        # South
        "квартира Сутоморе", "квартира Добра Вода",
        "недвижимость Святой Стефан",
    ]),
    ("real_estate", "montenegro", "en", [
        "apartment Becici Budva", "apartment Rafailovici",
        "apartment Przno Budva", "property Sveti Stefan",
        "apartment Donja Lastva Tivat", "property Lepetane",
        "apartment Dobrota Kotor", "property Perast",
        "property Risan Montenegro", "apartment Igalo",
        "apartment Bijela Montenegro", "property Djenovici",
        "property Sutomore Montenegro",
    ]),

    # ────────────────────────────────────────────
    # REAL ESTATE / DUBAI — areas & communities
    # ────────────────────────────────────────────
    ("real_estate", "dubai", "ru", [
        "квартира Дубай Крик Харбор", "квартира Мейдан Дубай",
        "вилла Дамак Хиллс", "квартира Дубай Саут",
        "квартира Аль Фурджан Дубай", "вилла Тилал Аль Гаф",
        "квартира Дубай Хиллс Эстейт", "квартира Дубай Марина Гейт",
        "квартира МБР Сити", "вилла Эмаар Бичфронт",
        "квартира Джумейра Вилладж Сёркл", "вилла Аравийские Ранчи 3",
        "квартира Дубай Саут Гольф", "квартира Аль Джаддаф",
        "квартира Дубай Силикон Оазис", "квартира Таун Сквер Дубай",
    ]),
    ("real_estate", "dubai", "en", [
        "apartment Dubai Creek Harbour", "apartment Meydan Dubai",
        "villa Damac Hills 2", "property Dubai South",
        "apartment Al Furjan Dubai", "villa Tilal Al Ghaf",
        "apartment Dubai Hills Estate Mall", "apartment Marina Gate Dubai",
        "apartment MBR City", "villa Emaar Beachfront",
        "apartment JVC Dubai", "villa Arabian Ranches 3",
        "apartment Al Jaddaf Dubai", "property Dubai Silicon Oasis",
        "apartment Town Square Dubai", "villa The Valley Dubai",
        "apartment Sobha Hartland", "apartment Creek Rise Dubai",
        "property Jumeirah Golf Estates", "apartment Port de La Mer",
    ]),

    # ────────────────────────────────────────────
    # LEGAL / MOSCOW — specific service niches
    # ────────────────────────────────────────────
    ("legal", "moscow", "ru", [
        "юрист по трастам Москва", "юрист по зарубежным фондам Москва",
        "юрист по валютному контролю Москва",
        "юрист по КИК Петербург", "налоговый советник НДФЛ нерезидент",
        "юрист по международному структурированию Петербург",
        "юридическая фирма ВЭД Москва",
        "юрист по международным транзакциям",
        "юрист по оффшорам Петербург",
        "юрист по зарубежным счетам Москва",
        "юрист по двойному налогообложению",
        "юрист по международному наследству",
        "юрист по семейному фонду Петербург",
        "юрист по зарубежной недвижимости Москва",
        "юрист по зарубежным инвестициям Москва",
        "юридическое сопровождение релокации",
    ]),

    # ────────────────────────────────────────────
    # LEGAL / UAE — freezones & specific areas
    # ────────────────────────────────────────────
    ("legal", "uae_legal", "en", [
        "company formation DMCC Dubai", "company formation JAFZA",
        "company formation RAKEZ", "company formation IFZA Dubai",
        "company formation AFZA Ajman", "company formation SPC ADGM",
        "company formation Meydan freezone", "company formation DWTC",
        "company formation Hamriyah freezone",
        "business setup Abu Dhabi mainland",
        "business setup Sharjah freezone",
        "business setup Fujairah freezone",
        "PRO services Abu Dhabi", "PRO services Sharjah",
        "corporate bank account Dubai",
        "business license renewal Dubai",
    ]),
    ("legal", "uae_legal", "ru", [
        "регистрация компании DMCC Дубай", "регистрация JAFZA Дубай",
        "открыть компанию РАКЕЗ", "открыть компанию IFZA Дубай",
        "открыть компанию Абу-Даби", "фризона Шарджа регистрация",
        "фризона Фуджейра", "фризона Аджман",
        "бизнес лицензия Дубай", "банковский счет ОАЭ",
        "продление лицензии Дубай",
    ]),

    # ────────────────────────────────────────────
    # LEGAL / CYPRUS — service niches
    # ────────────────────────────────────────────
    ("legal", "cyprus_legal", "en", [
        "Limassol corporate services", "Paphos law firm English",
        "Larnaca company registration", "Nicosia tax advisory",
        "Cyprus investment fund RAIF", "Cyprus AIF license",
        "Cyprus forex license CySEC", "Cyprus EMI license",
        "Cyprus ship management company",
        "Cyprus nominee director service",
    ]),
    ("legal", "cyprus_legal", "ru", [
        "юрист Лимассол для бизнеса",
        "регистрация фонда Кипр", "CySEC лицензия Кипр",
        "аудитор Никосия", "бухгалтер Ларнака",
        "юрист Пафос для россиян",
    ]),

    # ────────────────────────────────────────────
    # LEGAL / GEORGIA — cities
    # ────────────────────────────────────────────
    ("legal", "georgia_legal", "ru", [
        "юрист Батуми для бизнеса из России",
        "бухгалтер Тбилиси для иностранцев",
        "регистрация компании Батуми",
        "IT компания Батуми регистрация",
        "юрист Кутаиси",
    ]),
    ("legal", "georgia_legal", "en", [
        "company registration Batumi", "law firm Batumi",
        "accountant Tbilisi for foreigners",
        "IT company Batumi setup", "tax advisor Kutaisi",
        "business visa Georgia Batumi",
    ]),

    # ────────────────────────────────────────────
    # LEGAL / SERBIA — cities
    # ────────────────────────────────────────────
    ("legal", "serbia_legal", "en", [
        "company registration Novi Sad", "law firm Novi Sad",
        "company registration Nis Serbia", "business setup Subotica",
        "tax advisor Novi Sad", "co-working visa Serbia Novi Sad",
    ]),
    ("legal", "serbia_legal", "ru", [
        "юрист Нови Сад для россиян", "регистрация компании Нови Сад",
        "бизнес Ниш Сербия", "юрист Белград для бизнеса",
        "бухгалтер Сербия для россиян",
    ]),

    # ────────────────────────────────────────────
    # MIGRATION / SPAIN — cities & regions
    # ────────────────────────────────────────────
    ("migration", "spain_gv", "en", [
        "Golden Visa Alicante", "Golden Visa Malaga",
        "Golden Visa Valencia", "Golden Visa Costa del Sol",
        "Golden Visa Costa Blanca", "Golden Visa Tenerife",
        "Golden Visa Mallorca", "Golden Visa Ibiza",
        "residency by investment Barcelona",
        "residency by investment Marbella",
        "immigration lawyer Barcelona", "immigration lawyer Madrid",
        "immigration lawyer Malaga", "immigration lawyer Marbella",
        "non-lucrative visa Spain Barcelona",
        "digital nomad visa Spain Barcelona",
        "digital nomad visa Spain Malaga",
    ]),
    ("migration", "spain_gv", "ru", [
        "Golden Visa Аликанте", "Golden Visa Малага",
        "Golden Visa Валенсия", "Golden Visa Тенерифе",
        "Golden Visa Майорка", "Golden Visa Ибица",
        "иммиграционный юрист Барселона",
        "иммиграционный юрист Мадрид",
        "иммиграционный юрист Малага",
        "виза цифрового кочевника Испания Барселона",
        "нелюкративная виза Испания Малага",
        "ВНЖ Коста дель Соль", "ВНЖ Коста Бланка",
    ]),

    # ────────────────────────────────────────────
    # MIGRATION / PORTUGAL — cities & regions
    # ────────────────────────────────────────────
    ("migration", "portugal_gv", "en", [
        "Golden Visa Porto agent", "Golden Visa Algarve agent",
        "Golden Visa Faro agent", "Golden Visa Silver Coast",
        "Golden Visa Madeira", "Golden Visa Azores",
        "immigration lawyer Lisbon", "immigration lawyer Porto",
        "D7 visa Lisbon consultant", "D7 visa Porto consultant",
        "D7 visa Algarve", "NHR regime consultant Lisbon",
        "digital nomad visa Portugal Lisbon",
        "digital nomad visa Portugal Porto",
        "startup visa Lisbon",
    ]),
    ("migration", "portugal_gv", "ru", [
        "Golden Visa Порту агент", "Golden Visa Фару агент",
        "Golden Visa Мадейра", "Golden Visa Азорские острова",
        "иммиграционный юрист Лиссабон",
        "иммиграционный юрист Порту",
        "D7 виза Лиссабон", "D7 виза Порту",
        "NHR режим консультант Лиссабон",
        "виза цифрового кочевника Португалия",
    ]),

    # ────────────────────────────────────────────
    # MIGRATION / GREECE — cities & islands
    # ────────────────────────────────────────────
    ("migration", "greece_gv", "en", [
        "Golden Visa Crete agent", "Golden Visa Thessaloniki agent",
        "Golden Visa Corfu", "Golden Visa Rhodes",
        "Golden Visa Mykonos", "Golden Visa Halkidiki",
        "immigration lawyer Athens", "immigration lawyer Thessaloniki",
        "residency by investment Crete",
        "digital nomad visa Greece Athens",
    ]),
    ("migration", "greece_gv", "ru", [
        "Golden Visa Крит агент", "Golden Visa Салоники агент",
        "Golden Visa Корфу", "Golden Visa Родос",
        "Golden Visa Миконос", "Golden Visa Халкидики",
        "иммиграционный юрист Афины",
        "иммиграционный юрист Салоники",
        "ВНЖ через недвижимость Крит",
    ]),

    # ────────────────────────────────────────────
    # MIGRATION / UAE — emirates & areas
    # ────────────────────────────────────────────
    ("migration", "uae_visa", "en", [
        "Golden Visa Dubai Marina consultant",
        "Golden Visa Abu Dhabi consultant",
        "Golden Visa Sharjah", "Golden Visa RAK",
        "freelance visa Dubai Marina", "freelance visa Abu Dhabi",
        "entrepreneur visa Abu Dhabi", "investor visa Abu Dhabi",
        "retirement visa Abu Dhabi",
    ]),
    ("migration", "uae_visa", "ru", [
        "Golden Visa Абу-Даби", "Golden Visa Шарджа",
        "фрилансер виза Абу-Даби", "предпринимательская виза Абу-Даби",
        "резидентская виза Шарджа", "резидентская виза РАК",
    ]),

    # ────────────────────────────────────────────
    # MIGRATION / GENERAL — Russian cities
    # ────────────────────────────────────────────
    ("migration", "general_migration", "ru", [
        "агент по переезду Москва", "агент по переезду Петербург",
        "консультант по эмиграции Москва",
        "консультант по эмиграции Петербург",
        "релокационное агентство Москва",
        "релокационное агентство Петербург",
        "релокация Казань", "релокация Новосибирск",
        "релокация Екатеринбург", "релокация Краснодар",
        "релокация из России Москва", "релокация из России Петербург",
        "помощь переезд Москва", "помощь переезд Петербург",
    ]),

    # ────────────────────────────────────────────
    # INVESTMENT / SWITZERLAND — cities
    # ────────────────────────────────────────────
    ("investment", "switzerland", "ru", [
        "управление активами Цюрих", "управление активами Женева",
        "управление активами Лугано", "управление активами Лозанна",
        "управление активами Базель", "инвестиционный бутик Цюрих",
        "инвестиционный бутик Женева", "инвестиционный бутик Лугано",
        "финансовый советник Цюрих", "финансовый советник Женева",
        "портфельный управляющий Цюрих", "портфельный управляющий Женева",
    ]),
    ("investment", "switzerland", "en", [
        "asset manager Zurich", "asset manager Geneva",
        "asset manager Lugano", "asset manager Lausanne",
        "asset manager Basel", "investment boutique Zurich",
        "investment boutique Geneva", "wealth advisor Zurich",
        "wealth advisor Geneva", "wealth advisor Lugano",
        "portfolio manager Zurich", "portfolio manager Geneva",
        "EAM Zurich", "EAM Geneva", "EAM Lugano",
    ]),

    # ────────────────────────────────────────────
    # INVESTMENT / MOSCOW — Russian cities
    # ────────────────────────────────────────────
    ("investment", "moscow", "ru", [
        "инвестиционный советник Петербург",
        "инвестиционная компания Петербург",
        "управляющая компания Петербург",
        "инвестиционный советник Казань",
        "инвестиционный советник Екатеринбург",
        "инвестиционный советник Новосибирск",
        "инвестиционный советник Краснодар",
        "инвестиционный советник Нижний Новгород",
        "финансовый консультант Петербург",
        "финансовый консультант Екатеринбург",
        "финансовый консультант Казань",
        "управление активами Петербург",
    ]),

    # ────────────────────────────────────────────
    # INVESTMENT / DUBAI — areas
    # ────────────────────────────────────────────
    ("investment", "dubai_difc", "en", [
        "wealth manager DIFC", "wealth manager ADGM",
        "financial advisor Abu Dhabi ADGM",
        "asset management Abu Dhabi",
        "portfolio management Abu Dhabi",
        "investment advisory Abu Dhabi",
        "wealth advisory Abu Dhabi",
        "family office Abu Dhabi ADGM",
    ]),
    ("investment", "dubai_difc", "ru", [
        "инвестиционный советник DIFC",
        "управление активами Абу-Даби",
        "финансовый советник Абу-Даби",
        "управление портфелем Абу-Даби",
    ]),

    # ────────────────────────────────────────────
    # CRYPTO / DUBAI — specific areas
    # ────────────────────────────────────────────
    ("crypto", "dubai_crypto", "en", [
        "crypto OTC desk DIFC", "crypto license VARA Dubai",
        "crypto fund DIFC", "crypto custody ADGM",
        "digital asset license Abu Dhabi",
        "crypto exchange Abu Dhabi",
        "Bitcoin OTC Abu Dhabi",
    ]),
    ("crypto", "dubai_crypto", "ru", [
        "крипто обменник DIFC Дубай", "VARA лицензия крипто Дубай",
        "OTC биткоин Абу-Даби", "крипто фонд DIFC",
        "крипто компания Абу-Даби",
    ]),

    # ────────────────────────────────────────────
    # CRYPTO / MOSCOW — Russian cities
    # ────────────────────────────────────────────
    ("crypto", "moscow_crypto", "ru", [
        "OTC крипто Петербург", "обменник USDT Петербург",
        "купить биткоин Петербург", "OTC крипто Казань",
        "OTC крипто Екатеринбург", "OTC крипто Новосибирск",
        "обменник крипто Краснодар", "купить USDT Казань",
        "крипто обмен Нижний Новгород",
    ]),

    # ────────────────────────────────────────────
    # IMPORTERS / MOSCOW — Russian cities & specifics
    # ────────────────────────────────────────────
    ("importers", "moscow_import", "ru", [
        "импорт из Китая Петербург", "импорт из Турции Петербург",
        "ВЭД компания Петербург", "импорт оборудования Петербург",
        "таможенный брокер Петербург", "логистика импорт Петербург",
        "импорт из Дубай Петербург", "ВЭД компания Екатеринбург",
        "импорт из Китая Новосибирск", "импорт оборудования Казань",
        "ВЭД компания Краснодар", "импорт Нижний Новгород",
        "параллельный импорт Петербург",
        "параллельный импорт Екатеринбург",
        "байер Стамбул", "байер Гуанчжоу",
        "закупщик Стамбул", "закупщик Иу Китай",
    ]),

    # ────────────────────────────────────────────
    # FAMILY OFFICE / SWITZERLAND — cities
    # ────────────────────────────────────────────
    ("family_office", "switzerland_fo", "en", [
        "family office Zurich", "family office Geneva",
        "family office Lugano", "family office Lausanne",
        "family office Basel", "multi family office Lugano",
        "wealth governance Zurich", "wealth governance Geneva",
        "succession planning Zurich", "succession planning Geneva",
        "private trust Zurich", "private trust Geneva",
    ]),
    ("family_office", "switzerland_fo", "ru", [
        "семейный офис Цюрих", "семейный офис Женева",
        "семейный офис Лугано", "семейный офис Лозанна",
        "наследственное планирование Цюрих",
        "наследственное планирование Женева",
    ]),

    # ────────────────────────────────────────────
    # FAMILY OFFICE / MOSCOW — Russian cities
    # ────────────────────────────────────────────
    ("family_office", "moscow_fo", "ru", [
        "семейный офис Петербург",
        "family office Петербург",
        "управление семейным капиталом Петербург",
        "создание семейного офиса Петербург",
        "мультисемейный офис Петербург",
        "wealth management Петербург",
        "управление состоянием Петербург",
    ]),

    # ────────────────────────────────────────────
    # FAMILY OFFICE / DUBAI — areas
    # ────────────────────────────────────────────
    ("family_office", "dubai_fo", "en", [
        "family office DIFC Dubai", "family office ADGM Abu Dhabi",
        "multi family office Dubai DIFC",
        "wealth advisory DIFC", "wealth advisory ADGM",
        "family office setup Abu Dhabi",
        "private trust Dubai DIFC",
    ]),
    ("family_office", "dubai_fo", "ru", [
        "семейный офис Дубай DIFC", "семейный офис Абу-Даби",
        "управление капиталом Абу-Даби",
        "wealth management Абу-Даби",
    ]),
]


def build_doc_keyword_queries(
    segment_key: str | None = None,
    geo_key: str | None = None,
    language: str | None = None,
    existing_queries: set[str] | None = None,
) -> list[dict]:
    """
    Return raw doc keyword phrases as query dicts, optionally filtered by segment/geo/language.
    These are exact keyword phrases from tasks/deliryo/keywords_*.md, used as-is.
    """
    existing = existing_queries or set()
    results: list[dict] = []
    seen: set[str] = set(existing)

    for seg, geo, lang, phrases in DOC_KEYWORDS:
        if segment_key and seg != segment_key:
            continue
        if geo_key and geo != geo_key:
            continue
        if language and lang != language:
            continue

        for phrase in phrases:
            _add_query(phrase, seg, geo, lang, results, seen)

    return results
    return counts
