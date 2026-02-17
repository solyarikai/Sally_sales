"""
Find 1000+ NEW OnSocial target companies + contacts.

Strategy — 5 parallel prongs:
  1. Expand geographies (15+ new geos for existing 3 segments)
  2. Add new segments (talent_management, social_commerce, brand_partnerships, gaming_influencer, creator_tools)
  3. Apollo Org Search (keyword_tags × locations matrix)
  4. Directory & list scraping via Google (clutch, G2, awards, rankings)
  5. Local language queries (ES, PT, DE, FR, IT, TR)

Exclusion system:
  - 191 paid client domains (already in project_blacklist)
  - Existing targets (via _build_skip_set)
  - Smartlead campaign 2944931 contacts (added to project_blacklist here)
  - Already-analyzed domains (standard skip set)

Run on Hetzner:
  docker run -d --name onsocial-1000 --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... -e APOLLO_API_KEY=... \
    -e SMARTLEAD_API_KEY=... -e GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python -u /scripts/onsocial_1000_search.py'
"""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("onsocial_1000")

PROJECT_ID = 42
COMPANY_ID = 1
SMARTLEAD_CAMPAIGN_ID = "2944931"
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"

# ============================================================
# SEARCH CONFIG: all 8 segments × 20 geos
# ============================================================

EXPANDED_CONFIG = {
    "segments": {
        # ---- EXISTING 3 segments (expanded geos) ----
        "influencer_agencies": {
            "priority": 1,
            "label_en": "Influencer Marketing Agencies",
            "geos": {
                # Existing 5 geos
                "spain": {
                    "cities_en": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga", "Bilbao"],
                    "country_en": "Spain",
                },
                "poland": {
                    "cities_en": ["Warsaw", "Krakow", "Wroclaw", "Gdansk", "Poznan"],
                    "country_en": "Poland",
                },
                "nordics": {
                    "cities_en": ["Stockholm", "Oslo", "Copenhagen", "Helsinki", "Gothenburg"],
                    "country_en": "Scandinavia",
                },
                "usa": {
                    "cities_en": ["New York", "Los Angeles", "Miami", "Chicago", "San Francisco",
                                  "Austin", "Nashville", "Atlanta", "Denver", "Portland"],
                    "country_en": "USA",
                },
                "latam": {
                    "cities_en": ["Mexico City", "Buenos Aires", "São Paulo", "Bogota", "Lima", "Santiago"],
                    "country_en": "Latin America",
                },
                # ---- NEW geos ----
                "uk": {
                    "cities_en": ["London", "Manchester", "Birmingham", "Leeds", "Edinburgh", "Dublin"],
                    "country_en": "United Kingdom",
                },
                "dach": {
                    "cities_en": ["Berlin", "Munich", "Hamburg", "Vienna", "Zurich", "Frankfurt"],
                    "country_en": "Germany",
                },
                "france": {
                    "cities_en": ["Paris", "Lyon", "Marseille", "Amsterdam", "Brussels"],
                    "country_en": "France",
                },
                "italy": {
                    "cities_en": ["Milan", "Rome", "Turin"],
                    "country_en": "Italy",
                },
                "canada": {
                    "cities_en": ["Toronto", "Vancouver", "Montreal", "Calgary"],
                    "country_en": "Canada",
                },
                "australia": {
                    "cities_en": ["Sydney", "Melbourne", "Brisbane", "Auckland"],
                    "country_en": "Australia",
                },
                "india": {
                    "cities_en": ["Mumbai", "Delhi", "Bangalore", "Hyderabad"],
                    "country_en": "India",
                },
                "sea": {
                    "cities_en": ["Singapore", "Bangkok", "Jakarta", "Manila", "Kuala Lumpur"],
                    "country_en": "Southeast Asia",
                },
                "middle_east": {
                    "cities_en": ["Dubai", "Riyadh", "Abu Dhabi", "Jeddah"],
                    "country_en": "Middle East",
                },
                "turkey": {
                    "cities_en": ["Istanbul", "Ankara"],
                    "country_en": "Turkey",
                },
                "eastern_europe": {
                    "cities_en": ["Prague", "Bucharest", "Budapest", "Sofia", "Zagreb"],
                    "country_en": "Eastern Europe",
                },
                "south_africa": {
                    "cities_en": ["Johannesburg", "Cape Town"],
                    "country_en": "South Africa",
                },
                "japan_korea": {
                    "cities_en": ["Tokyo", "Seoul", "Osaka"],
                    "country_en": "Japan",
                },
                "portugal": {
                    "cities_en": ["Lisbon", "Porto"],
                    "country_en": "Portugal",
                },
            },
            "vars": {
                "company_type_en": [
                    "influencer marketing agency", "influencer agency",
                    "creator marketing agency", "social media influencer agency",
                    "influencer management agency", "talent management agency",
                    "creator economy agency", "micro-influencer agency",
                    "KOL agency", "brand ambassador agency",
                ],
                "service_en": [
                    "influencer campaign management", "creator partnerships",
                    "influencer discovery", "brand collaboration",
                    "influencer outreach", "sponsored content", "creator marketplace",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type} {city}",
                "top {company_type} {country}",
                "{service} agency {city}",
                "{service} {country}",
                "{company_type} for brands {country}",
            ],
            "templates_ru": [],
        },
        "influencer_platforms": {
            "priority": 2,
            "label_en": "Influencer Marketing Platforms / SaaS",
            "geos": {
                "usa": {"cities_en": ["New York", "Los Angeles", "San Francisco", "Austin"], "country_en": "USA"},
                "uk": {"cities_en": ["London", "Manchester"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin", "Munich"], "country_en": "Germany"},
                "france": {"cities_en": ["Paris", "Amsterdam"], "country_en": "France"},
                "india": {"cities_en": ["Mumbai", "Bangalore"], "country_en": "India"},
                "sea": {"cities_en": ["Singapore", "Jakarta"], "country_en": "Southeast Asia"},
                "canada": {"cities_en": ["Toronto", "Vancouver"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney", "Melbourne"], "country_en": "Australia"},
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "nordics": {"cities_en": ["Stockholm", "Copenhagen", "Helsinki"], "country_en": "Scandinavia"},
                "latam": {"cities_en": ["Mexico City", "São Paulo", "Buenos Aires"], "country_en": "Latin America"},
                "italy": {"cities_en": ["Milan"], "country_en": "Italy"},
                "middle_east": {"cities_en": ["Dubai"], "country_en": "Middle East"},
                "japan_korea": {"cities_en": ["Tokyo", "Seoul"], "country_en": "Japan"},
            },
            "vars": {
                "platform_type_en": [
                    "influencer marketing platform", "influencer discovery tool",
                    "creator marketplace", "influencer analytics platform",
                    "influencer CRM", "creator economy platform",
                    "influencer database", "influencer search engine",
                ],
                "service_en": [
                    "influencer API", "creator API", "social media API",
                    "influencer data API", "campaign management tool",
                    "influencer ROI analytics",
                ],
            },
            "templates_en": [
                "{platform_type} {country}",
                "{platform_type} {city}",
                "best {platform_type} {country}",
                "{platform_type} for agencies",
                "{platform_type} with API",
                "{service} platform",
                "{service} for agencies",
            ],
            "templates_ru": [],
        },
        "ugc_agencies": {
            "priority": 3,
            "label_en": "UGC Agencies & Platforms",
            "geos": {
                "usa": {"cities_en": ["New York", "Los Angeles", "Miami", "Chicago"], "country_en": "USA"},
                "uk": {"cities_en": ["London", "Manchester"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin", "Munich"], "country_en": "Germany"},
                "france": {"cities_en": ["Paris"], "country_en": "France"},
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "nordics": {"cities_en": ["Stockholm", "Copenhagen"], "country_en": "Scandinavia"},
                "latam": {"cities_en": ["Mexico City", "São Paulo", "Buenos Aires"], "country_en": "Latin America"},
                "canada": {"cities_en": ["Toronto", "Vancouver"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney", "Melbourne"], "country_en": "Australia"},
                "india": {"cities_en": ["Mumbai", "Bangalore"], "country_en": "India"},
                "italy": {"cities_en": ["Milan"], "country_en": "Italy"},
                "middle_east": {"cities_en": ["Dubai"], "country_en": "Middle East"},
            },
            "vars": {
                "company_type_en": [
                    "UGC agency", "user generated content agency",
                    "UGC platform", "content creator agency",
                    "UGC marketing agency", "creator content agency",
                ],
                "service_en": [
                    "UGC campaigns", "user generated content",
                    "UGC video production", "creator content",
                    "UGC marketplace",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type} {country}",
                "{service} agency {city}",
                "{company_type} for brands",
                "top {company_type} {country}",
            ],
            "templates_ru": [],
        },

        # ---- NEW 5 segments ----
        "talent_management": {
            "priority": 4,
            "label_en": "Creator/Influencer Talent Management",
            "geos": {
                "usa": {"cities_en": ["New York", "Los Angeles", "Miami", "Nashville", "Atlanta"], "country_en": "USA"},
                "uk": {"cities_en": ["London", "Manchester"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin", "Munich", "Hamburg"], "country_en": "Germany"},
                "france": {"cities_en": ["Paris"], "country_en": "France"},
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "nordics": {"cities_en": ["Stockholm", "Copenhagen"], "country_en": "Scandinavia"},
                "latam": {"cities_en": ["Mexico City", "São Paulo", "Buenos Aires"], "country_en": "Latin America"},
                "canada": {"cities_en": ["Toronto", "Vancouver"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney", "Melbourne"], "country_en": "Australia"},
                "india": {"cities_en": ["Mumbai", "Delhi", "Bangalore"], "country_en": "India"},
                "sea": {"cities_en": ["Singapore", "Bangkok", "Jakarta"], "country_en": "Southeast Asia"},
                "middle_east": {"cities_en": ["Dubai", "Riyadh"], "country_en": "Middle East"},
                "italy": {"cities_en": ["Milan", "Rome"], "country_en": "Italy"},
                "turkey": {"cities_en": ["Istanbul"], "country_en": "Turkey"},
            },
            "vars": {
                "company_type_en": [
                    "influencer talent management", "creator talent agency",
                    "influencer management company", "creator representation",
                    "social media talent agency", "digital talent management",
                    "YouTuber management", "TikTok talent agency",
                ],
                "service_en": [
                    "influencer representation", "creator management",
                    "talent booking", "brand deal negotiation",
                    "influencer talent roster",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type} {country}",
                "{service} agency {city}",
                "{service} company {country}",
                "{company_type} for creators",
                "top {company_type}",
            ],
            "templates_ru": [],
        },
        "social_commerce": {
            "priority": 5,
            "label_en": "Social Commerce & Live Shopping Platforms",
            "geos": {
                "usa": {"cities_en": ["New York", "Los Angeles", "San Francisco"], "country_en": "USA"},
                "uk": {"cities_en": ["London"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin"], "country_en": "Germany"},
                "france": {"cities_en": ["Paris"], "country_en": "France"},
                "sea": {"cities_en": ["Singapore", "Bangkok", "Jakarta"], "country_en": "Southeast Asia"},
                "latam": {"cities_en": ["São Paulo", "Mexico City"], "country_en": "Latin America"},
                "india": {"cities_en": ["Mumbai", "Bangalore"], "country_en": "India"},
                "middle_east": {"cities_en": ["Dubai"], "country_en": "Middle East"},
                "canada": {"cities_en": ["Toronto"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney"], "country_en": "Australia"},
            },
            "vars": {
                "company_type_en": [
                    "social commerce platform", "live shopping platform",
                    "shoppable content platform", "influencer commerce",
                    "creator monetization platform", "affiliate marketing platform",
                    "social selling platform", "creator storefront",
                ],
                "service_en": [
                    "social commerce", "live shopping", "shoppable content",
                    "influencer affiliate", "creator monetization",
                    "social selling tools",
                ],
            },
            "templates_en": [
                "{company_type} {country}",
                "{company_type} {city}",
                "best {company_type}",
                "{service} platform",
                "{service} for brands",
                "{company_type} for influencers",
                "top {service} tools",
            ],
            "templates_ru": [],
        },
        "brand_partnerships": {
            "priority": 6,
            "label_en": "Brand Partnership & Sponsorship Agencies",
            "geos": {
                "usa": {"cities_en": ["New York", "Los Angeles", "Chicago", "Miami"], "country_en": "USA"},
                "uk": {"cities_en": ["London", "Manchester"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin", "Munich"], "country_en": "Germany"},
                "france": {"cities_en": ["Paris"], "country_en": "France"},
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "canada": {"cities_en": ["Toronto"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney", "Melbourne"], "country_en": "Australia"},
                "india": {"cities_en": ["Mumbai"], "country_en": "India"},
                "middle_east": {"cities_en": ["Dubai"], "country_en": "Middle East"},
            },
            "vars": {
                "company_type_en": [
                    "brand partnership agency", "sponsorship agency",
                    "brand collaboration agency", "influencer sponsorship agency",
                    "brand deal agency", "endorsement agency",
                ],
                "service_en": [
                    "brand partnerships", "sponsorship deals",
                    "brand collaborations", "influencer sponsorship",
                    "creator brand deals",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type} {country}",
                "{service} agency {city}",
                "{service} {country}",
                "{company_type} for brands",
            ],
            "templates_ru": [],
        },
        "gaming_influencer": {
            "priority": 7,
            "label_en": "Gaming & Esports Influencer Marketing",
            "geos": {
                "usa": {"cities_en": ["Los Angeles", "New York", "San Francisco", "Austin"], "country_en": "USA"},
                "uk": {"cities_en": ["London"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin", "Hamburg"], "country_en": "Germany"},
                "nordics": {"cities_en": ["Stockholm", "Copenhagen"], "country_en": "Scandinavia"},
                "sea": {"cities_en": ["Singapore", "Manila", "Jakarta"], "country_en": "Southeast Asia"},
                "japan_korea": {"cities_en": ["Tokyo", "Seoul"], "country_en": "Japan"},
                "latam": {"cities_en": ["São Paulo", "Mexico City"], "country_en": "Latin America"},
                "france": {"cities_en": ["Paris"], "country_en": "France"},
            },
            "vars": {
                "company_type_en": [
                    "gaming influencer agency", "esports marketing agency",
                    "gaming influencer platform", "Twitch marketing agency",
                    "gaming creator agency", "esports talent agency",
                ],
                "service_en": [
                    "gaming influencer marketing", "esports sponsorship",
                    "Twitch influencer campaigns", "gaming creator partnerships",
                    "streamer marketing",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type}",
                "{service} agency",
                "{service} {country}",
                "top {company_type} {country}",
            ],
            "templates_ru": [],
        },
        "creator_tools": {
            "priority": 8,
            "label_en": "Creator Economy Tools & SaaS",
            "geos": {
                "usa": {"cities_en": ["San Francisco", "New York", "Los Angeles", "Austin"], "country_en": "USA"},
                "uk": {"cities_en": ["London"], "country_en": "United Kingdom"},
                "dach": {"cities_en": ["Berlin"], "country_en": "Germany"},
                "canada": {"cities_en": ["Toronto", "Vancouver"], "country_en": "Canada"},
                "australia": {"cities_en": ["Sydney"], "country_en": "Australia"},
                "india": {"cities_en": ["Bangalore", "Mumbai"], "country_en": "India"},
                "sea": {"cities_en": ["Singapore"], "country_en": "Southeast Asia"},
                "nordics": {"cities_en": ["Stockholm"], "country_en": "Scandinavia"},
            },
            "vars": {
                "company_type_en": [
                    "creator analytics tool", "creator monetization tool",
                    "link in bio platform", "creator economy SaaS",
                    "influencer analytics tool", "social media analytics tool",
                    "content creator tool", "creator management software",
                ],
                "service_en": [
                    "creator analytics", "influencer analytics",
                    "creator monetization", "social media management",
                    "content scheduling", "creator CRM",
                ],
            },
            "templates_en": [
                "{company_type} {country}",
                "{company_type} {city}",
                "best {company_type}",
                "{service} platform",
                "{service} tool",
                "top {company_type}",
                "{service} for influencers",
            ],
            "templates_ru": [],
        },
    },
    "doc_keywords": [
        # ---- Existing doc keywords for original 5 geos ----
        ["influencer_agencies", "usa", "en", [
            "influencer marketing agency NYC", "influencer agency Los Angeles",
            "top influencer marketing agencies USA", "best influencer agencies 2025",
            "creator marketing agency", "micro influencer agency",
            "TikTok influencer agency", "Instagram influencer agency",
            "YouTube influencer agency", "influencer talent management",
        ]],
        ["influencer_agencies", "spain", "en", [
            "influencer marketing agency Spain", "influencer agency Barcelona",
            "influencer agency Madrid", "social media agency Spain",
        ]],
        ["influencer_agencies", "poland", "en", [
            "influencer marketing agency Poland", "influencer agency Warsaw",
            "social media agency Poland", "creator agency Poland",
        ]],
        ["influencer_agencies", "nordics", "en", [
            "influencer marketing agency Sweden", "influencer agency Stockholm",
            "influencer agency Norway", "influencer agency Denmark",
            "influencer marketing Scandinavia", "Nordic influencer agency",
        ]],
        ["influencer_agencies", "latam", "en", [
            "influencer marketing agency Mexico", "influencer agency Brazil",
            "influencer agency Argentina", "Latin America influencer agency",
        ]],

        # ---- NEW geos for influencer_agencies ----
        ["influencer_agencies", "uk", "en", [
            "influencer marketing agency London", "influencer agency UK",
            "top influencer agencies United Kingdom", "creator agency London",
            "TikTok agency London", "Instagram agency UK",
            "influencer agency Manchester", "influencer agency Dublin",
        ]],
        ["influencer_agencies", "dach", "en", [
            "influencer marketing agency Germany", "influencer agency Berlin",
            "influencer agency Munich", "Influencer Agentur Deutschland",
            "influencer agency Austria", "influencer agency Vienna",
            "influencer agency Switzerland", "influencer agency Zurich",
        ]],
        ["influencer_agencies", "france", "en", [
            "influencer marketing agency France", "influencer agency Paris",
            "agence marketing d'influence Paris", "influencer agency Amsterdam",
            "influencer agency Brussels", "agence influenceurs France",
        ]],
        ["influencer_agencies", "italy", "en", [
            "influencer marketing agency Italy", "influencer agency Milan",
            "agenzia influencer marketing Milano", "agenzia influencer Italia",
            "influencer agency Rome",
        ]],
        ["influencer_agencies", "canada", "en", [
            "influencer marketing agency Canada", "influencer agency Toronto",
            "influencer agency Vancouver", "influencer agency Montreal",
            "best influencer agencies Canada",
        ]],
        ["influencer_agencies", "australia", "en", [
            "influencer marketing agency Australia", "influencer agency Sydney",
            "influencer agency Melbourne", "influencer agency Auckland",
            "best influencer agencies Australia",
        ]],
        ["influencer_agencies", "india", "en", [
            "influencer marketing agency India", "influencer agency Mumbai",
            "influencer agency Bangalore", "influencer agency Delhi",
            "top influencer agencies India", "KOL agency India",
        ]],
        ["influencer_agencies", "sea", "en", [
            "influencer marketing agency Singapore", "influencer agency Southeast Asia",
            "influencer agency Bangkok", "influencer agency Jakarta",
            "influencer agency Manila", "KOL agency SEA",
        ]],
        ["influencer_agencies", "middle_east", "en", [
            "influencer marketing agency Dubai", "influencer agency UAE",
            "influencer agency Middle East", "influencer agency Saudi Arabia",
            "KOL agency MENA", "social media agency Dubai",
        ]],
        ["influencer_agencies", "turkey", "en", [
            "influencer marketing agency Turkey", "influencer agency Istanbul",
            "influencer ajansı İstanbul", "influencer pazarlama Türkiye",
        ]],
        ["influencer_agencies", "eastern_europe", "en", [
            "influencer marketing agency Czech Republic", "influencer agency Prague",
            "influencer agency Romania", "influencer agency Hungary Budapest",
            "influencer agency Bulgaria", "influencer agency Croatia",
        ]],
        ["influencer_agencies", "south_africa", "en", [
            "influencer marketing agency South Africa", "influencer agency Johannesburg",
            "influencer agency Cape Town", "best influencer agencies Africa",
        ]],
        ["influencer_agencies", "japan_korea", "en", [
            "influencer marketing agency Japan", "influencer agency Tokyo",
            "KOL agency Korea", "influencer agency Seoul",
        ]],
        ["influencer_agencies", "portugal", "en", [
            "influencer marketing agency Portugal", "influencer agency Lisbon",
            "agência de influenciadores Portugal",
        ]],

        # ---- Platforms doc keywords ----
        ["influencer_platforms", None, "en", [
            "influencer marketing platform", "influencer discovery platform",
            "creator marketplace platform", "influencer CRM software",
            "influencer analytics tool", "social media influencer platform",
            "influencer marketing software", "influencer API platform",
            "creator economy platform", "influencer database tool",
            "best influencer marketing platforms 2025",
        ]],

        # ---- UGC doc keywords ----
        ["ugc_agencies", None, "en", [
            "UGC agency", "user generated content agency",
            "UGC platform for brands", "UGC marketing",
            "best UGC agencies 2025", "creator content marketplace",
        ]],

        # ---- Prong 4: Directory & List scraping ----
        ["influencer_agencies", None, "en", [
            "top influencer marketing agencies 2025",
            "best influencer marketing platforms 2025",
            "clutch.co influencer marketing",
            "G2 influencer marketing software",
            "influencer marketing hub agency directory",
            "the drum influencer agencies",
            "campaign best influencer agencies",
            "adweek influencer marketing",
            "influencer marketing awards winners 2025",
            "best UGC agencies 2025",
            "top creator economy companies",
            "social media marketing agency ranking 2025",
            "capterra influencer marketing tools",
            "product hunt influencer tools",
            "influencer marketing agency of the year",
            "fastest growing influencer agencies",
            "inc 5000 influencer marketing",
            "top 100 influencer marketing companies",
            "webfx top influencer agencies",
            "business of apps influencer platforms",
        ]],

        # ---- Prong 5: Local language queries ----
        # Spanish
        ["influencer_agencies", "spain", "es", [
            "agencia de influencers Madrid",
            "agencia marketing de influencers Barcelona",
            "agencia de influencers España",
            "plataforma de influencers España",
            "mejor agencia de influencers España",
        ]],
        ["influencer_agencies", "latam", "es", [
            "agencia de marketing de influencers México",
            "agencia de influencers Buenos Aires",
            "agencia de influencers Bogotá",
            "plataforma de influencers Latinoamérica",
            "agencia de influencers Colombia",
        ]],
        # Portuguese
        ["influencer_agencies", "portugal", "pt", [
            "agência de influenciadores Lisboa",
            "agência marketing de influência Portugal",
            "plataforma de influenciadores Portugal",
        ]],
        ["influencer_agencies", "latam", "pt", [
            "agência de influenciadores São Paulo",
            "plataforma de influenciadores Brasil",
            "agência de marketing de influência Brasil",
            "melhor agência de influenciadores Brasil",
        ]],
        # German
        ["influencer_agencies", "dach", "de", [
            "Influencer Marketing Agentur Berlin",
            "Influencer Agentur München",
            "Influencer Plattform Deutschland",
            "beste Influencer Agentur Deutschland",
            "Influencer Marketing Agentur Wien",
            "Influencer Agentur Schweiz",
        ]],
        # French
        ["influencer_agencies", "france", "fr", [
            "agence marketing d'influence Paris",
            "agence d'influenceurs France",
            "plateforme influenceurs France",
            "meilleure agence influenceurs Paris",
            "agence de marketing d'influence Lyon",
        ]],
        # Italian
        ["influencer_agencies", "italy", "it", [
            "agenzia influencer marketing Milano",
            "agenzia di influencer Roma",
            "piattaforma influencer Italia",
            "migliore agenzia influencer Italia",
        ]],
        # Turkish
        ["influencer_agencies", "turkey", "tr", [
            "influencer ajansı İstanbul",
            "influencer pazarlama ajansı Türkiye",
            "en iyi influencer ajansı",
        ]],
    ],
}

# ---- Apollo Org Search config (Prong 3) ----
APOLLO_KEYWORD_TAGS = [
    ["influencer marketing"],
    ["creator economy"],
    ["UGC", "user generated content"],
    ["influencer platform"],
    ["social media marketing agency"],
    ["creator marketplace"],
    ["talent management", "influencer"],
    ["influencer analytics"],
    ["brand ambassador"],
    ["social commerce", "influencer"],
]

APOLLO_LOCATIONS = [
    "United States", "United Kingdom", "Germany", "France", "Spain",
    "India", "Australia", "Brazil", "United Arab Emirates", "Canada",
    "Italy", "Netherlands", "Sweden", "Poland", "Singapore",
]


# ============================================================
# Phase 0: Smartlead exclusion
# ============================================================
async def phase0_smartlead_exclusion():
    """Fetch Smartlead campaign leads and add their domains to project_blacklist."""
    from app.db import async_session_maker
    from app.services.smartlead_service import smartlead_service
    from app.models.domain import ProjectBlacklist
    from sqlalchemy import text

    logger.info("=" * 60)
    logger.info("PHASE 0: Smartlead exclusion")
    logger.info("=" * 60)

    if not smartlead_service.is_connected():
        logger.warning("Smartlead not configured — skipping exclusion")
        return 0

    # Fetch all leads with pagination
    all_leads = []
    offset = 0
    batch_size = 100
    while True:
        result = await smartlead_service.get_campaign_leads(
            campaign_id=SMARTLEAD_CAMPAIGN_ID,
            offset=offset,
            limit=batch_size,
        )
        leads = result.get("leads", [])
        if not leads:
            break
        all_leads.extend(leads)
        offset += batch_size
        if len(leads) < batch_size:
            break
        await asyncio.sleep(0.2)

    logger.info(f"Fetched {len(all_leads)} leads from Smartlead campaign {SMARTLEAD_CAMPAIGN_ID}")

    # Extract unique domains from emails
    domains = set()
    for lead in all_leads:
        email = (lead.get("email") or "").lower().strip()
        if email and "@" in email:
            domain = email.split("@")[1]
            if domain and "." in domain and domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
                domains.add(domain)

    logger.info(f"Extracted {len(domains)} unique domains from Smartlead leads")

    # Insert into project_blacklist
    async with async_session_maker() as session:
        inserted = 0
        for domain in domains:
            try:
                await session.execute(text("""
                    INSERT INTO project_blacklist (project_id, domain, reason, source)
                    VALUES (:pid, :domain, :reason, :source)
                    ON CONFLICT (project_id, domain) DO NOTHING
                """), {
                    "pid": PROJECT_ID,
                    "domain": domain,
                    "reason": f"already_in_smartlead_campaign_{SMARTLEAD_CAMPAIGN_ID}",
                    "source": "smartlead_exclusion",
                })
                inserted += 1
            except Exception:
                pass
        await session.commit()
        logger.info(f"Added {inserted} domains to project_blacklist from Smartlead")

    return len(domains)


# ============================================================
# Phase 1: Update search_config
# ============================================================
async def phase1_update_config():
    """Write expanded search_config to DB."""
    from app.db import async_session_maker
    from sqlalchemy import text, select
    from app.models.domain import ProjectSearchKnowledge

    logger.info("=" * 60)
    logger.info("PHASE 1: Update search_config")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == PROJECT_ID
            )
        )
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=PROJECT_ID)
            session.add(knowledge)

        knowledge.search_config = EXPANDED_CONFIG
        await session.commit()

        # Verify
        total_geos = 0
        total_templates = 0
        for seg_key, seg in EXPANDED_CONFIG["segments"].items():
            n_geos = len(seg["geos"])
            n_templates = len(seg.get("templates_en", []))
            total_geos += n_geos
            total_templates += n_templates
            logger.info(f"  {seg_key}: {n_geos} geos, {n_templates} templates")

        total_doc = sum(len(entry[3]) for entry in EXPANDED_CONFIG["doc_keywords"])
        logger.info(f"  doc_keywords: {len(EXPANDED_CONFIG['doc_keywords'])} groups, {total_doc} phrases")
        logger.info(f"  Total: {len(EXPANDED_CONFIG['segments'])} segments, {total_geos} geos, {total_templates} templates")


# ============================================================
# Phase 2: Segment Search (Google SERP)
# ============================================================
async def phase2_segment_search():
    """Run segment search for all new segment×geo combinations."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchEngine

    logger.info("=" * 60)
    logger.info("PHASE 2: Segment Search (Google SERP)")
    logger.info("=" * 60)

    # Build list of all segment×geo combos
    combos = []
    for seg_key, seg in EXPANDED_CONFIG["segments"].items():
        for geo_key in seg["geos"]:
            combos.append((seg_key, geo_key))

    logger.info(f"Total segment×geo combos: {len(combos)}")

    total_targets = 0
    total_queries = 0
    total_domains = 0

    for i, (seg_key, geo_key) in enumerate(combos):
        logger.info(f"\n--- [{i+1}/{len(combos)}] {seg_key}/{geo_key} ---")

        try:
            async with async_session_maker() as session:
                stats = await company_search_service.run_segment_search(
                    session=session,
                    project_id=PROJECT_ID,
                    company_id=COMPANY_ID,
                    segment_key=seg_key,
                    geo_key=geo_key,
                    search_engine=SearchEngine.GOOGLE_SERP,
                    ai_expand_rounds=0,  # No AI expansion — rely on templates + doc keywords
                )

            total_targets += stats.get("targets_found", 0)
            total_queries += stats.get("total_queries", 0)
            total_domains += stats.get("domains_found", 0)

            logger.info(
                f"  → {stats.get('total_queries', 0)} queries, "
                f"{stats.get('domains_found', 0)} domains, "
                f"{stats.get('targets_found', 0)} targets"
            )

            # Running totals
            logger.info(
                f"  Running: {total_queries} queries, "
                f"{total_domains} domains, {total_targets} targets"
            )
        except Exception as e:
            logger.error(f"  FAILED: {e}")
            continue

    logger.info(f"\nPhase 2 done: {total_queries} queries, {total_domains} domains, {total_targets} targets")
    return {"queries": total_queries, "domains": total_domains, "targets": total_targets}


# ============================================================
# Phase 3: Apollo Org Search
# ============================================================
async def phase3_apollo_search():
    """Run Apollo org search: keyword_tags × locations matrix."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine,
        SearchQuery, SearchResult, Domain, DomainSource, DomainStatus,
    )
    from app.models.contact import Project
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("PHASE 3: Apollo Org Search")
    logger.info("=" * 60)

    if not apollo_service.is_configured():
        logger.warning("Apollo not configured — skipping")
        return {"domains": 0, "targets": 0}

    async with async_session_maker() as session:
        # Load project
        proj_result = await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )
        project = proj_result.scalar_one()

        # Build skip set
        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        logger.info(f"Skip set: {len(skip_set)} domains")

        # Create a single SearchJob for all Apollo queries
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.APOLLO_ORG,
            queries_total=0,
            project_id=PROJECT_ID,
            config={"source": "apollo_org_search", "target_segments": project.target_segments},
        )
        session.add(job)
        await session.flush()

        all_domains = set()
        query_count = 0

        for keyword_tags in APOLLO_KEYWORD_TAGS:
            for location in APOLLO_LOCATIONS:
                query_count += 1
                logger.info(f"  Apollo [{query_count}]: {keyword_tags} × {location}")

                try:
                    orgs = await apollo_service.search_organizations_all_pages(
                        keyword_tags=keyword_tags,
                        locations=[location],
                        max_pages=5,  # Cap at 500 orgs per combo
                        per_page=100,
                    )
                except Exception as e:
                    logger.error(f"    Failed: {e}")
                    continue

                # Extract domains
                for org in orgs:
                    domain = org.get("primary_domain") or ""
                    domain = domain.lower().strip().rstrip("/")
                    if domain and "." in domain and domain not in skip_set:
                        all_domains.add(domain)

                # Save query
                sq = SearchQuery(
                    search_job_id=job.id,
                    query_text=f"Apollo: {keyword_tags} in {location}",
                    segment="apollo_org",
                    geo=location.lower().replace(" ", "_"),
                    language="en",
                )
                session.add(sq)

                await asyncio.sleep(0.3)  # Rate limit

        job.queries_total = query_count
        await session.commit()

        # Register new domains
        new_domains = list(all_domains - skip_set)
        logger.info(f"Apollo found {len(all_domains)} unique domains, {len(new_domains)} new (after skip set)")

        if new_domains:
            # Register domains in Domain table
            from app.services.domain_service import domain_service
            for d in new_domains:
                try:
                    await domain_service.register_domain(
                        session=session,
                        domain=d,
                        source=DomainSource.SEARCH_GOOGLE,  # Closest match
                    )
                except Exception:
                    pass
            await session.commit()

            # Scrape and analyze in batches
            batch_size = 50
            total_targets = 0
            for batch_start in range(0, len(new_domains), batch_size):
                batch = new_domains[batch_start:batch_start + batch_size]
                logger.info(f"  Analyzing batch {batch_start//batch_size + 1}: {len(batch)} domains")

                try:
                    await company_search_service._scrape_and_analyze_domains(
                        session=session,
                        job=job,
                        domains=batch,
                        target_segments=project.target_segments,
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"  Batch analysis failed: {e}")
                    await session.rollback()

            # Count targets
            target_result = await session.execute(
                select(SearchResult).where(
                    SearchResult.search_job_id == job.id,
                    SearchResult.is_target == True,
                )
            )
            total_targets = len(target_result.scalars().all())

        else:
            total_targets = 0

        # Mark job complete
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.domains_found = len(new_domains)
        await session.commit()

        logger.info(f"Phase 3 done: {query_count} queries, {len(new_domains)} domains, {total_targets} targets")
        return {"domains": len(new_domains), "targets": total_targets}


# ============================================================
# Phase 4: Contact extraction (auto-enriched by pipeline)
# ============================================================
async def phase4_contact_extraction():
    """Extract contacts for all target companies missing contacts."""
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany
    from app.services.pipeline_service import pipeline_service
    from sqlalchemy import select, text

    logger.info("=" * 60)
    logger.info("PHASE 4: Contact extraction for targets without contacts")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Find targets with 0 or NULL contacts
        result = await session.execute(
            select(DiscoveredCompany.id, DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.contacts_count.in_([0, None]),
            )
        )
        no_contacts = result.fetchall()
        logger.info(f"{len(no_contacts)} target companies have 0 contacts")

        if not no_contacts:
            return

        # Batch extract contacts
        batch_size = 20
        for batch_start in range(0, len(no_contacts), batch_size):
            batch = no_contacts[batch_start:batch_start + batch_size]
            dc_ids = [row[0] for row in batch]
            logger.info(f"  Extracting contacts batch {batch_start//batch_size + 1}: {len(dc_ids)} companies")

            try:
                stats = await pipeline_service.extract_contacts_batch(
                    session=session,
                    discovered_company_ids=dc_ids,
                    company_id=COMPANY_ID,
                )
                logger.info(f"  Batch result: {stats}")
            except Exception as e:
                logger.error(f"  Extraction failed: {e}")

        # Summary
        r = await session.execute(text("""
            SELECT count(DISTINCT ec.discovered_company_id)
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL
        """), {"pid": PROJECT_ID})
        companies_with_email = r.scalar()
        r = await session.execute(text("""
            SELECT count(*)
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL
        """), {"pid": PROJECT_ID})
        total_emails = r.scalar()
        logger.info(f"Phase 4 done: {companies_with_email} companies with email, {total_emails} total contacts")


# ============================================================
# Phase 5: Export to Google Sheets
# ============================================================
async def phase5_export():
    """Export all targets + contacts to Google Sheets."""
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text
    import json

    logger.info("=" * 60)
    logger.info("PHASE 5: Export to Google Sheets")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Load targets
        targets = await session.execute(text("""
            SELECT
                dc.domain,
                dc.name as company_name,
                dc.confidence,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status,
                sr.reasoning,
                sq.query_text as source_query,
                sj.search_engine,
                sr.matched_segment,
                'https://' || dc.domain as url
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.domain = dc.domain AND sr.project_id = dc.project_id
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.confidence DESC
        """), {"pid": PROJECT_ID})
        target_rows = targets.fetchall()

        # Deduplicate by domain
        seen_domains = set()
        unique_targets = []
        for row in target_rows:
            if row.domain not in seen_domains:
                seen_domains.add(row.domain)
                unique_targets.append(row)

        # Collect query metadata per domain
        domain_meta = {}
        for row in target_rows:
            d = row.domain
            if d not in domain_meta:
                domain_meta[d] = {"queries": [], "engines": set(), "segments": set()}
            if row.source_query:
                domain_meta[d]["queries"].append(row.source_query)
            if row.search_engine:
                domain_meta[d]["engines"].add(str(row.search_engine))
            if row.matched_segment:
                domain_meta[d]["segments"].add(row.matched_segment)

        # Load contacts
        contacts_result = await session.execute(text("""
            SELECT
                dc.domain,
                ec.first_name, ec.last_name, ec.email, ec.phone,
                ec.job_title, ec.linkedin_url, ec.source, ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.domain, ec.is_verified DESC, ec.source DESC
        """), {"pid": PROJECT_ID})
        contact_rows = contacts_result.fetchall()

        domain_contacts = {}
        for c in contact_rows:
            domain_contacts.setdefault(c.domain, []).append(c)

        # Build sheet
        headers = [
            "First Name", "Last Name", "Email", "Job Title", "LinkedIn",
            "Phone", "Contact Source", "Verified",
            "Domain", "URL", "Company Name", "Description",
            "Industry", "Services", "Location",
            "Confidence", "Language", "Industry Match", "Service Match",
            "Company Type", "Geography",
            "Review Status", "Search Engine", "Segment", "Source Query",
            "Reasoning",
        ]
        data = [headers]
        contacts_with_email = 0

        for row in unique_targets:
            services = row.services
            if services:
                try:
                    sl = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(sl) if isinstance(sl, list) else str(services)
                except Exception:
                    pass

            meta = domain_meta.get(row.domain, {})
            engines = ", ".join(meta.get("engines", set()))
            segments = ", ".join(meta.get("segments", set()))
            queries = meta.get("queries", [])
            source_query = queries[0] if queries else ""

            company_cols = [
                row.domain, row.url, row.company_name or "", row.description or "",
                row.industry or "", services or "", row.location or "",
            ]
            score_cols = [
                str(row.confidence or ""),
                str(row.language_match or ""), str(row.industry_match or ""),
                str(row.service_match or ""), str(row.company_type_score or ""),
                str(row.geography_match or ""),
            ]
            search_cols = [
                row.review_status or "", engines, segments, source_query,
            ]
            reasoning_col = [row.reasoning or ""]

            contacts = domain_contacts.get(row.domain, [])
            for c in contacts:
                if not c.email:
                    continue
                contact_cols = [
                    c.first_name or "", c.last_name or "",
                    c.email or "", c.job_title or "",
                    c.linkedin_url or "", c.phone or "",
                    str(c.source or ""),
                    "Yes" if c.is_verified else "",
                ]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                contacts_with_email += 1

        logger.info(f"Sheet: {len(unique_targets)} target companies, {contacts_with_email} contacts with email, {len(data)-1} rows")

        # Write to sheet
        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service

        if sheets:
            try:
                sheets.spreadsheets().values().clear(
                    spreadsheetId=SHEET_ID, range="Sheet1",
                ).execute()
                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID, range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: wrote {len(data)-1} rows to Google Sheet")
            except Exception as e:
                logger.error(f"Sheet update failed: {e}")
        else:
            logger.warning("Google Sheets not initialized — saving JSON fallback")
            with open("/scripts/onsocial_targets_1000.json", "w") as f:
                json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)


# ============================================================
# MAIN
# ============================================================
async def main():
    from app.db import async_session_maker
    from sqlalchemy import text

    start_time = time.time()

    logger.info("=" * 60)
    logger.info("OnSocial 1000+ Target Search")
    logger.info(f"Project: {PROJECT_ID}, Company: {COMPANY_ID}")
    logger.info(f"Started: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    # Pre-run stats
    async with async_session_maker() as session:
        r = await session.execute(text(
            "SELECT count(*) FROM discovered_companies WHERE project_id = :pid AND is_target = true"
        ), {"pid": PROJECT_ID})
        existing_targets = r.scalar()
        r = await session.execute(text(
            "SELECT count(*) FROM project_blacklist WHERE project_id = :pid"
        ), {"pid": PROJECT_ID})
        blacklist_count = r.scalar()
        logger.info(f"Pre-run: {existing_targets} existing targets, {blacklist_count} blacklisted domains")

    # Phase 0: Smartlead exclusion
    try:
        await phase0_smartlead_exclusion()
    except Exception as e:
        logger.error(f"Phase 0 failed: {e}")

    # Phase 1: Update config
    try:
        await phase1_update_config()
    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")

    # Phase 2: Segment search (biggest lever)
    phase2_stats = {"queries": 0, "domains": 0, "targets": 0}
    try:
        phase2_stats = await phase2_segment_search()
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")

    # Phase 3: Apollo org search
    phase3_stats = {"domains": 0, "targets": 0}
    try:
        phase3_stats = await phase3_apollo_search()
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")

    # Phase 4: Contact extraction
    try:
        await phase4_contact_extraction()
    except Exception as e:
        logger.error(f"Phase 4 failed: {e}")

    # Phase 5: Export
    try:
        await phase5_export()
    except Exception as e:
        logger.error(f"Phase 5 failed: {e}")

    # Final summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        r = await session.execute(text(
            "SELECT count(*) FROM discovered_companies WHERE project_id = :pid AND is_target = true"
        ), {"pid": PROJECT_ID})
        total_targets = r.scalar()

        r = await session.execute(text("""
            SELECT count(*) FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL
        """), {"pid": PROJECT_ID})
        total_emails = r.scalar()

        r = await session.execute(text("""
            SELECT count(DISTINCT dc.domain) FROM discovered_companies dc
            JOIN project_blacklist pb ON dc.domain = pb.domain AND dc.project_id = pb.project_id
            WHERE dc.is_target = true AND dc.project_id = :pid
        """), {"pid": PROJECT_ID})
        blacklist_overlap = r.scalar()

        new_targets = total_targets - existing_targets

    logger.info(f"Total targets: {total_targets} ({existing_targets} old + {new_targets} new)")
    logger.info(f"Total contacts with email: {total_emails}")
    logger.info(f"Blacklist overlap check: {blacklist_overlap} (should be 0)")
    logger.info(f"Phase 2 (Google SERP): {phase2_stats}")
    logger.info(f"Phase 3 (Apollo Org): {phase3_stats}")
    logger.info(f"Elapsed: {elapsed/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
