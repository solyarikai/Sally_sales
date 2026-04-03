"""
Seed Deliryo project with structured segments and keywords from tasks/deliryo files.
Updates:
1. Project target_segments — comprehensive segment description
2. ProjectSearchKnowledge — good_query_patterns from keyword files, anti-keywords for Ukraine
"""
import asyncio
import json
from app.db.database import async_session_maker
from sqlalchemy import text

PROJECT_ID = 18

# ============ Structured target segments text ============
# Based on segments_russia.md, segments_international.md, and feedback:
# - NO UKRAINE
# - Not only luxury — broader HNWI services
# - goldas.group is a target example

TARGET_SEGMENTS = """КОМПАНИЯ: Companies serving Russian-speaking HNWI (high net worth individuals) who need cross-border financial services, real estate, legal structuring, migration, and wealth management. NOT luxury-only — any company facilitating cross-border operations for wealthy Russian-speaking clients.

STRICT EXCLUSION: NO Ukraine-based companies. Any company in Ukraine must be rejected.

SEGMENTS (by priority):

1. REAL ESTATE AGENCIES & BROKERS (Priority #1)
   Russian and international agencies selling property abroad to Russian/CIS buyers.
   Sub-segments:
   - Dubai/UAE agencies (RERA brokers, Russian-speaking)
   - Turkey agencies (Antalya, Istanbul, Bodrum, Alanya)
   - Cyprus agencies (Limassol, Paphos, Larnaca, North Cyprus)
   - Thailand/Bali agencies (Phuket, Pattaya, Bangkok, Bali)
   - Montenegro agencies (Budva, Tivat, Kotor)
   - Spain/Portugal agencies (Costa del Sol, Marbella, Lisbon, Algarve)
   - Greece agencies (Athens, Crete, Mykonos, Rhodes)
   - Aggregators of overseas property (Tranio, Prian, Realting type)
   - Developers with Russian buyers (CEE, Dubai)
   Example targets: real estate agencies, property brokers, developers selling to Russian HNWI

2. INVESTMENT COMPANIES & WEALTH MANAGERS (Priority #2)
   - Investment boutiques serving wealthy clients
   - Private banking desks (Sber Private, Alfa Private, etc.)
   - Independent financial advisors (IFA)
   - Asset management with foreign products
   - Family offices (single and multi)
   - Wealth advisors
   - Private banks with Russian-speaking desks (Swiss, Singapore, Dubai)
   - PPLI/insurance brokers for UHNWI

3. LEGAL & TAX COMPANIES (Priority #3)
   - International tax planning firms
   - Foreign trade (VED) lawyers
   - Cross-border M&A firms
   - Asset structuring (trusts, funds, holding companies)
   - Tax consultants for relocants/expats
   - Corporate services (Cyprus, UAE, Estonia, Georgia, Serbia)
   - Offshore formation providers

4. MIGRATION & RELOCATION COMPANIES (Priority #4)
   - Immigration agencies (residence permits, citizenship by investment)
   - IT relocation services
   - Golden Visa agents (Spain, Portugal, Greece, UAE)
   - CBI agents (Caribbean, Turkey)
   - EB-5 agents

5. CRYPTO & OTC COMPANIES (Priority #6)
   - OTC desks for large crypto transactions
   - Crypto funds with Russian investors
   - Mining companies needing legalization
   - Licensed crypto exchanges

6. IMPORTERS (Priority #7)
   - Auto importers (from UAE, Korea, China)
   - Equipment importers
   - Luxury goods buyers
   - VED companies (general import/export)

ГЕОГРАФИЯ: Russia (Moscow, SPb), UAE (Dubai, Abu Dhabi), Turkey (Istanbul, Antalya), Cyprus (Limassol), Thailand (Phuket, Bangkok), Indonesia (Bali), Georgia (Tbilisi), Montenegro (Budva, Tivat), Spain (Marbella, Barcelona), Portugal (Lisbon, Algarve), Greece (Athens), Switzerland (Zurich, Geneva), Singapore, Czech Republic (Prague), Serbia (Belgrade), Estonia (Tallinn).

ЯЗЫК: Russian and English. Russian-language sites = higher priority (indicates Russian client base).
"""

# ============ Keywords from files, organized as good_query_patterns ============
# Selected high-value keywords from keywords_russia.md and keywords_international.md

GOOD_QUERY_PATTERNS_RU = [
    # Segment 1: Real estate
    "агентство недвижимости Дубай",
    "купить недвижимость в Дубае",
    "купить виллу Дубай",
    "недвижимость ОАЭ для россиян",
    "русский риелтор Дубай",
    "агентство недвижимости Турция",
    "купить квартиру Анталья",
    "недвижимость Кипр",
    "квартира Лимассол купить",
    "купить кондо Пхукет",
    "агентство недвижимости Пхукет",
    "купить виллу Бали",
    "недвижимость Черногория",
    "квартира Будва купить",
    "недвижимость Испания для россиян",
    "вилла Марбелья",
    "Golden Visa Испания",
    "Golden Visa Греция",
    "купить недвижимость за рубежом",
    "зарубежная недвижимость",
    "премиум брокер недвижимость",
    # Segment 2: Investment
    "инвестиционная компания Москва",
    "управляющая компания инвестиции",
    "private banking Москва",
    "инвестиционный советник",
    "семейный офис Москва",
    "family office Москва",
    "управление капиталом",
    "доверительное управление",
    "инвестиции за рубежом",
    # Segment 3: Legal
    "международное налоговое планирование",
    "юрист ВЭД",
    "M&A юрист международный",
    "структурирование активов",
    "создание траста",
    "оффшорная структура",
    "налоговый консультант для уехавших",
    # Segment 4: Migration
    "ВНЖ за инвестиции",
    "иммиграционный консультант",
    "второе гражданство",
    "Golden Visa",
    "релокация IT",
    # Segment 5: Crypto
    "OTC крипто Москва",
    "криптовалютный фонд",
    "майнинг биткоин Россия",
    # Segment 6: Import
    "импорт авто из ОАЭ",
    "ВЭД компания Москва",
]

GOOD_QUERY_PATTERNS_EN = [
    # Real estate
    "buy property Dubai",
    "real estate agency Dubai",
    "Russian speaking realtor Dubai",
    "buy villa Dubai",
    "buy apartment Turkey",
    "real estate agent Turkey",
    "buy property Cyprus",
    "Limassol property",
    "buy villa Bali",
    "Phuket real estate",
    "buy property Montenegro",
    "buy property Spain Golden Visa",
    "buy property Portugal Golden Visa",
    "buy property Greece",
    # Migration
    "Golden Visa Spain",
    "Golden Visa Portugal",
    "Golden Visa Greece",
    "citizenship by investment",
    "UAE Golden Visa",
    "immigration consultant investment",
    # Wealth
    "wealth management Dubai",
    "wealth management Switzerland",
    "family office services",
    "private banking Russian clients",
    "PPLI insurance",
    # Legal
    "law firm Cyprus company",
    "company formation UAE",
    "company formation Dubai",
    "offshore company formation",
    "law firm Georgia Tbilisi",
    "company registration Estonia",
    # PropTech
    "proptech Dubai",
    "crypto real estate platform",
]

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

CONFIRMED_DOMAIN_ADDITIONS = [
    "goldas.group",
]


async def main():
    async with async_session_maker() as s:
        # 1. Update project target_segments
        await s.execute(text("""
            UPDATE projects SET target_segments = :ts WHERE id = :pid
        """), {"ts": TARGET_SEGMENTS, "pid": PROJECT_ID})
        print(f"Updated project {PROJECT_ID} target_segments ({len(TARGET_SEGMENTS)} chars)")

        # 2. Update ProjectSearchKnowledge
        r = await s.execute(text(
            "SELECT id, anti_keywords, confirmed_domains, good_query_patterns, industry_keywords "
            "FROM project_search_knowledge WHERE project_id = :pid"
        ), {"pid": PROJECT_ID})
        row = r.fetchone()

        if not row:
            print("No knowledge row — creating one")
            await s.execute(text("""
                INSERT INTO project_search_knowledge (project_id, good_query_patterns, anti_keywords, confirmed_domains)
                VALUES (:pid, :gqp, :anti, :confirmed)
            """), {
                "pid": PROJECT_ID,
                "gqp": json.dumps(GOOD_QUERY_PATTERNS_RU + GOOD_QUERY_PATTERNS_EN),
                "anti": json.dumps(UKRAINE_ANTI_KEYWORDS),
                "confirmed": json.dumps(CONFIRMED_DOMAIN_ADDITIONS),
            })
        else:
            kid = row[0]
            anti_kw = row[1] or []
            confirmed = row[2] or []
            good_patterns = row[3] or []
            industry_kw = row[4] or []

            # Add Ukraine anti-keywords
            existing_lower = {k.lower() for k in anti_kw}
            new_anti = [k for k in UKRAINE_ANTI_KEYWORDS if k.lower() not in existing_lower]
            anti_kw.extend(new_anti)
            print(f"Added {len(new_anti)} Ukraine anti-keywords (total: {len(anti_kw)})")

            # Add confirmed domains
            existing_domains = {d.lower() for d in confirmed}
            new_domains = [d for d in CONFIRMED_DOMAIN_ADDITIONS if d.lower() not in existing_domains]
            confirmed.extend(new_domains)
            print(f"Added {len(new_domains)} confirmed domains (total: {len(confirmed)})")

            # Replace good_query_patterns with comprehensive list from keyword files
            all_patterns = GOOD_QUERY_PATTERNS_RU + GOOD_QUERY_PATTERNS_EN
            # Merge with existing, deduplicate
            existing_patterns_lower = {p.lower() for p in good_patterns}
            new_patterns = [p for p in all_patterns if p.lower() not in existing_patterns_lower]
            good_patterns.extend(new_patterns)
            print(f"Added {len(new_patterns)} query patterns (total: {len(good_patterns)})")

            # Add broader industry keywords
            broader_keywords = [
                "cross-border payments", "международные переводы",
                "USDT exchange", "обмен криптовалюты",
                "трансграничные платежи", "HNWI services",
                "wealth management", "управление активами",
                "OTC desk", "gold trading",
                "immigration consulting", "инвестиционная миграция",
                "real estate brokerage", "агентство недвижимости",
                "property investment", "инвестиции в недвижимость",
                "corporate structuring", "структурирование бизнеса",
                "offshore formation", "оффшорная компания",
            ]
            existing_ind_lower = {k.lower() for k in industry_kw}
            new_ind = [k for k in broader_keywords if k.lower() not in existing_ind_lower]
            industry_kw.extend(new_ind)
            print(f"Added {len(new_ind)} industry keywords (total: {len(industry_kw)})")

            await s.execute(text("""
                UPDATE project_search_knowledge
                SET anti_keywords = :anti,
                    confirmed_domains = :confirmed,
                    good_query_patterns = :gqp,
                    industry_keywords = :industry,
                    updated_at = NOW()
                WHERE id = :kid
            """), {
                "anti": json.dumps(anti_kw),
                "confirmed": json.dumps(confirmed),
                "gqp": json.dumps(good_patterns),
                "industry": json.dumps(industry_kw),
                "kid": kid,
            })
            print(f"Updated knowledge row {kid}")

        await s.commit()
        print("Done! All changes committed.")


asyncio.run(main())
