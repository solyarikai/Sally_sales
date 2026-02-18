"""Update OnSocial search config with proper English templates (no Russian)."""
import asyncio
import json
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

NEW_CONFIG = {
    "segments": {
        "influencer_agencies": {
            "priority": 1,
            "label_en": "Influencer Marketing Agencies",
            "label_ru": "Агентства инфлюенсер-маркетинга",
            "geos": {
                "spain": {
                    "cities_en": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga", "Bilbao"],
                    "cities_es": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Málaga", "Bilbao"],
                    "country_en": "Spain",
                    "country_es": "España",
                },
                "poland": {
                    "cities_en": ["Warsaw", "Krakow", "Wroclaw", "Gdansk", "Poznan", "Lodz"],
                    "cities_pl": ["Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań", "Łódź"],
                    "country_en": "Poland",
                    "country_pl": "Polska",
                },
                "nordics": {
                    "cities_en": ["Stockholm", "Oslo", "Copenhagen", "Helsinki", "Gothenburg", "Malmö"],
                    "country_en": "Scandinavia",
                },
                "usa": {
                    "cities_en": ["New York", "Los Angeles", "Miami", "Chicago", "San Francisco",
                                  "Austin", "Nashville", "Atlanta", "Denver", "Portland"],
                    "country_en": "USA",
                },
                "latam": {
                    "cities_en": ["Mexico City", "Buenos Aires", "São Paulo", "Bogota", "Lima", "Santiago"],
                    "cities_es": ["Ciudad de México", "Buenos Aires", "Bogotá", "Lima", "Santiago"],
                    "country_en": "Latin America",
                    "country_es": "Latinoamérica",
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
                "company_type_es": [
                    "agencia de marketing de influencers", "agencia de influencers",
                    "agencia de marketing digital", "agencia de redes sociales",
                    "agencia de creadores de contenido",
                ],
                "service_en": [
                    "influencer campaign management", "creator partnerships",
                    "influencer discovery platform", "brand collaboration",
                    "influencer outreach", "sponsored content", "creator marketplace",
                    "influencer analytics", "social media campaigns",
                ],
            },
            "templates_en": [
                "{company_type} in {city}",
                "{company_type} {city}",
                "{company_type} {country}",
                "{service} agency {city}",
                "{service} {country}",
                "best {company_type} {city}",
                "top {company_type} {country}",
                "{company_type} near {city}",
                "{service} company {city}",
                "{company_type} for brands {country}",
            ],
            "templates_es": [
                "{company_type} en {city}",
                "{company_type} en {country}",
                "mejor {company_type} {city}",
                "{company_type} para marcas {city}",
            ],
            "templates_ru": [],
        },
        "influencer_platforms": {
            "priority": 2,
            "label_en": "Influencer Marketing Platforms / SaaS",
            "label_ru": "Платформы инфлюенсер-маркетинга",
            "geos": {
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "poland": {"cities_en": ["Warsaw", "Krakow"], "country_en": "Poland"},
                "nordics": {"cities_en": ["Stockholm", "Oslo", "Copenhagen", "Helsinki"], "country_en": "Scandinavia"},
                "usa": {"cities_en": ["New York", "Los Angeles", "San Francisco", "Austin"], "country_en": "USA"},
                "latam": {"cities_en": ["Mexico City", "Buenos Aires", "São Paulo", "Bogota"], "country_en": "Latin America"},
            },
            "vars": {
                "platform_type_en": [
                    "influencer marketing platform", "influencer discovery tool",
                    "creator marketplace", "influencer analytics platform",
                    "social media management platform", "influencer CRM",
                    "creator economy platform", "influencer database",
                    "influencer search engine", "social listening platform",
                ],
                "service_en": [
                    "influencer API", "creator API", "social media API integration",
                    "influencer data API", "brand partnership platform",
                    "campaign management tool", "influencer ROI analytics",
                    "social media analytics API",
                ],
            },
            "templates_en": [
                "{platform_type} {country}",
                "{platform_type} {city}",
                "{service} {country}",
                "best {platform_type} {country}",
                "{platform_type} for agencies",
                "{platform_type} with API",
                "{service} platform",
                "{platform_type} for brands {country}",
                "top {platform_type}",
                "{service} for agencies",
            ],
            "templates_ru": [],
        },
        "ugc_agencies": {
            "priority": 3,
            "label_en": "UGC Agencies & Platforms",
            "label_ru": "UGC агентства",
            "geos": {
                "spain": {"cities_en": ["Madrid", "Barcelona"], "country_en": "Spain"},
                "poland": {"cities_en": ["Warsaw", "Krakow"], "country_en": "Poland"},
                "nordics": {"cities_en": ["Stockholm", "Copenhagen"], "country_en": "Scandinavia"},
                "usa": {"cities_en": ["New York", "Los Angeles", "Miami", "Chicago"], "country_en": "USA"},
                "latam": {"cities_en": ["Mexico City", "Buenos Aires", "São Paulo"], "country_en": "Latin America"},
            },
            "vars": {
                "company_type_en": [
                    "UGC agency", "user generated content agency",
                    "UGC platform", "content creator agency",
                    "UGC marketing agency", "social proof agency",
                    "creator content agency",
                ],
                "service_en": [
                    "UGC campaigns", "user generated content",
                    "UGC video production", "creator content",
                    "social proof content", "UGC marketplace",
                ],
            },
            "templates_en": [
                "{company_type} {city}",
                "{company_type} {country}",
                "best {company_type} {country}",
                "{service} agency {city}",
                "{service} {country}",
                "{company_type} for brands",
                "top {company_type} {country}",
                "{service} platform {country}",
            ],
            "templates_ru": [],
        },
    },
    "doc_keywords": [
        ["influencer_agencies", "usa", "en", [
            "influencer marketing agency NYC", "influencer agency Los Angeles",
            "top influencer marketing agencies USA", "best influencer agencies 2024",
            "creator marketing agency", "micro influencer agency",
            "TikTok influencer agency", "Instagram influencer agency",
            "YouTube influencer agency", "influencer talent management",
        ]],
        ["influencer_agencies", "spain", "en", [
            "influencer marketing agency Spain", "influencer agency Barcelona",
            "influencer agency Madrid", "social media agency Spain",
            "creator agency Spain", "influencer marketing España",
        ]],
        ["influencer_agencies", "poland", "en", [
            "influencer marketing agency Poland", "influencer agency Warsaw",
            "social media agency Poland", "creator agency Poland",
            "influencer marketing Polska",
        ]],
        ["influencer_agencies", "nordics", "en", [
            "influencer marketing agency Sweden", "influencer agency Stockholm",
            "influencer agency Norway", "influencer agency Denmark",
            "influencer marketing Scandinavia", "Nordic influencer agency",
        ]],
        ["influencer_agencies", "latam", "en", [
            "influencer marketing agency Mexico", "influencer agency Brazil",
            "influencer agency Argentina", "Latin America influencer agency",
            "influencer marketing LATAM", "agencia de influencers",
        ]],
        ["influencer_platforms", None, "en", [
            "influencer marketing platform", "influencer discovery platform",
            "creator marketplace platform", "influencer CRM software",
            "influencer analytics tool", "social media influencer platform",
            "influencer marketing software", "influencer API platform",
            "creator economy platform", "influencer database tool",
        ]],
        ["ugc_agencies", None, "en", [
            "UGC agency", "user generated content agency",
            "UGC platform for brands", "UGC marketing",
            "best UGC agencies", "creator content marketplace",
        ]],
    ],
}


async def main():
    from app.db import async_session_maker
    from sqlalchemy import text

    async with async_session_maker() as session:
        await session.execute(
            text("UPDATE project_search_knowledge SET search_config = :config WHERE project_id = 42"),
            {"config": json.dumps(NEW_CONFIG, ensure_ascii=False)},
        )
        await session.commit()
        print("OnSocial search config updated successfully!")

        # Verify
        r = await session.execute(text("SELECT search_config FROM project_search_knowledge WHERE project_id = 42"))
        row = r.fetchone()
        config = row[0]
        for k, v in config["segments"].items():
            geos = list(v["geos"].keys())
            en = len(v.get("templates_en", []))
            ru = len(v.get("templates_ru", []))
            es = len(v.get("templates_es", []))
            print(f"  {k}: {len(geos)} geos, {en} en, {ru} ru, {es} es templates")
        print(f"  doc_keywords: {len(config['doc_keywords'])} entries")


if __name__ == "__main__":
    asyncio.run(main())
