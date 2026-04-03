"""Update Deliryo project search knowledge with Ukraine exclusions and broader targeting."""
import asyncio
import json
from app.db.database import async_session_maker
from sqlalchemy import text


UKRAINE_ANTI_KEYWORDS = [
    "Ukraine", "Украина", "Україна",
    "Kyiv", "Киев", "Київ",
    "Odessa", "Одесса", "Одеса",
    "Kharkiv", "Харьков", "Харків",
    "Lviv", "Львов", "Львів",
    "Dnipro", "Днепр", "Дніпро",
    "Zaporizhzhia", "Запорожье", "Запоріжжя",
    "Ukrainian market", "украинский рынок",
]

# goldas.group was flagged as false negative — it should be target
CONFIRMED_DOMAIN_ADDITIONS = [
    "goldas.group",
]


async def main():
    async with async_session_maker() as s:
        # Get current knowledge
        r = await s.execute(text(
            "SELECT id, anti_keywords, confirmed_domains, industry_keywords "
            "FROM project_search_knowledge WHERE project_id = 18"
        ))
        row = r.fetchone()
        if not row:
            print("No knowledge row for project 18!")
            return

        kid = row[0]
        anti_kw = row[1] or []
        confirmed = row[2] or []
        industry_kw = row[3] or []

        # Add Ukraine anti-keywords (deduplicate)
        existing_lower = {k.lower() for k in anti_kw}
        new_anti = [k for k in UKRAINE_ANTI_KEYWORDS if k.lower() not in existing_lower]
        anti_kw.extend(new_anti)
        print(f"Added {len(new_anti)} Ukraine anti-keywords (total: {len(anti_kw)})")

        # Add confirmed domains
        existing_domains = {d.lower() for d in confirmed}
        new_domains = [d for d in CONFIRMED_DOMAIN_ADDITIONS if d.lower() not in existing_domains]
        confirmed.extend(new_domains)
        print(f"Added {len(new_domains)} confirmed domains (total: {len(confirmed)})")

        # Add broader industry keywords for HNWI services
        broader_keywords = [
            "cross-border payments",
            "международные переводы",
            "USDT exchange",
            "обмен криптовалюты",
            "трансграничные платежи",
            "финансовые услуги для состоятельных клиентов",
            "HNWI services",
            "wealth management",
            "управление активами",
            "OTC desk",
            "gold trading",
            "золотые инвестиции",
        ]
        existing_ind_lower = {k.lower() for k in industry_kw}
        new_ind = [k for k in broader_keywords if k.lower() not in existing_ind_lower]
        industry_kw.extend(new_ind)
        print(f"Added {len(new_ind)} broader industry keywords (total: {len(industry_kw)})")

        # Update DB
        await s.execute(text("""
            UPDATE project_search_knowledge
            SET anti_keywords = :anti,
                confirmed_domains = :confirmed,
                industry_keywords = :industry,
                updated_at = NOW()
            WHERE id = :kid
        """), {
            "anti": json.dumps(anti_kw),
            "confirmed": json.dumps(confirmed),
            "industry": json.dumps(industry_kw),
            "kid": kid,
        })
        await s.commit()
        print("Done! Knowledge updated.")


asyncio.run(main())
