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
    return counts
