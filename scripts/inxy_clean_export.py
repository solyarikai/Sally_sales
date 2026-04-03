"""
Inxy — Export ONLY actual gaming ICP targets to Google Sheet.
Filters out non-gaming companies (fintech, legal, migration, crypto funds etc.)
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("inxy_clean")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48
SHARE_WITH = ["pn@getsally.io"]


async def main():
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info("=" * 60)
    logger.info("INXY — CLEAN EXPORT: ONLY GAMING ICP TARGETS")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # First: check Apollo org search config
        result = await session.execute(text("""
            SELECT sj.id, sj.config, sj.search_engine::text
            FROM search_jobs sj
            WHERE sj.project_id = 48
            AND sj.config->>'segment' LIKE 'apollo%'
        """))
        apollo_jobs = result.fetchall()
        for aj in apollo_jobs:
            logger.info(f"Apollo job {aj.id}: {aj.config}")

        # Get ALL companies with full info
        result = await session.execute(text("""
            SELECT
                dc.id,
                dc.domain,
                'https://' || dc.domain as url,
                COALESCE(dc.name, sr.company_info->>'name', '') as company_name,
                COALESCE(sr.company_info->>'description', '') as description,
                COALESCE(sr.company_info->>'location', '') as location,
                COALESCE(sr.company_info->>'industry', '') as industry,
                COALESCE(sr.matched_segment, dc.matched_segment, '') as segment,
                COALESCE(sr.confidence, dc.confidence, 0) as confidence,
                COALESCE(sr.reasoning, dc.reasoning, '') as reasoning,
                CASE
                    WHEN dc.company_info->>'source' = 'team_xlsx' THEN 'Manual (XLSX)'
                    WHEN sj.config->>'segment' = 'team_manual' THEN 'Manual (XLSX)'
                    WHEN sj.search_engine = 'YANDEX_API' THEN 'Yandex'
                    WHEN sj.search_engine = 'GOOGLE_SERP' THEN 'Google'
                    WHEN sj.config->>'segment' LIKE 'apollo%' THEN 'Apollo'
                    ELSE COALESCE(sj.search_engine::text, 'Unknown')
                END as discovery_source,
                COALESCE(sq.query_text, '') as search_query,
                COALESCE(sq.geo, sj.config->>'geo', '') as search_geo,
                dc.apollo_org_data->>'country' as apollo_country,
                dc.apollo_org_data->>'estimated_num_employees' as employees,
                dc.apollo_org_data->>'annual_revenue_printed' as revenue,
                dc.apollo_org_data->>'founded_year' as founded_year,
                dc.apollo_org_data->>'keywords' as apollo_keywords,
                (SELECT string_agg(DISTINCT ec.email, ', ')
                 FROM extracted_contacts ec
                 WHERE ec.discovered_company_id = dc.id AND ec.email IS NOT NULL
                ) as existing_emails
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.id = dc.search_result_id
            LEFT JOIN search_jobs sj ON sj.id = COALESCE(sr.search_job_id, dc.search_job_id)
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            WHERE dc.project_id = :project_id
                AND dc.is_target = true
            ORDER BY dc.domain
        """), {"project_id": PROJECT_ID})
        all_rows = result.fetchall()

    logger.info(f"Total is_target=true: {len(all_rows)}")

    # Gaming-related keywords for filtering
    GAMING_KEYWORDS = {
        'skin', 'skins', 'game', 'gaming', 'csgo', 'cs2', 'dota', 'steam',
        'rust', 'tf2', 'fortnite', 'roblox', 'case', 'loot', 'box', 'unbox',
        'trade', 'trading', 'marketplace', 'items', 'virtual', 'boost',
        'boosting', 'coin', 'coins', 'gold', 'key', 'keys', 'card', 'cards',
        'top-up', 'topup', 'gift', 'giftcard', 'voucher', 'credit', 'credits',
        'fifa', 'wow', 'warcraft', 'minecraft', 'valorant', 'pubg', 'apex',
        'league', 'legends', 'overwatch', 'diablo', 'path', 'exile',
        'account', 'accounts', 'item', 'currency', 'digital', 'goods',
        'esport', 'bet', 'wager', 'casino', 'slot', 'gamble',
        'nft', 'play', 'player', 'gamer',
        'sell', 'buy', 'shop', 'store', 'market',
    }

    # Non-gaming keywords (definitely not ICP)
    NON_GAMING = {
        'bank', 'banking', 'fintech', 'payment', 'insurance', 'invest',
        'wealth', 'advisory', 'consulting', 'legal', 'law', 'tax',
        'migration', 'immigration', 'visa', 'real estate', 'property',
        'venture', 'capital', 'fund', 'hedge', 'asset management',
        'staffing', 'recruiting', 'hr', 'payroll', 'accounting',
        'blockchain infrastructure', 'defi', 'protocol', 'validator',
    }

    # Definite gaming segments
    GAMING_SEGMENTS = {'team_confirmed', 'gaming', 'gaming_top_up'}
    # Definite non-gaming segments
    NON_GAMING_SEGMENTS = {'legal', 'migration', 'investment'}

    filtered = []
    excluded = []

    for row in all_rows:
        segment = row.segment
        source = row.discovery_source
        domain = row.domain.lower()
        desc = (row.description or '').lower()
        name = (row.company_name or '').lower()
        reasoning = (row.reasoning or '').lower()
        keywords = (row.apollo_keywords or '').lower()
        query = (row.search_query or '').lower()

        # Always include XLSX team companies
        if source == 'Manual (XLSX)' or segment in GAMING_SEGMENTS:
            filtered.append(row)
            continue

        # Always exclude non-gaming segments
        if segment in NON_GAMING_SEGMENTS:
            excluded.append((row.domain, f"segment={segment}"))
            continue

        # For Yandex/Google — queries were gaming-specific, include
        if source in ('Yandex', 'Google'):
            filtered.append(row)
            continue

        # For Apollo org and others — check if gaming-related
        all_text = f"{domain} {name} {desc} {keywords} {reasoning} {query}"

        # Check for gaming signals
        gaming_score = sum(1 for kw in GAMING_KEYWORDS if kw in all_text)
        non_gaming_score = sum(1 for kw in NON_GAMING if kw in all_text)

        # Domain-level gaming signals
        gaming_domain_parts = ['skin', 'game', 'play', 'csgo', 'cs2', 'dota',
                                'rust', 'tf2', 'loot', 'case', 'trade', 'boost',
                                'coin', 'gold', 'key', 'shop', 'buy', 'sell',
                                'roblox', 'blox', 'steam', 'item', 'market',
                                'fifa', 'wow', 'craft', 'bet', 'casino',
                                'gamer', 'gg', 'io']
        domain_gaming = sum(1 for kw in gaming_domain_parts if kw in domain)

        is_gaming = (gaming_score >= 2 and non_gaming_score < 2) or domain_gaming >= 2

        if is_gaming:
            filtered.append(row)
        else:
            excluded.append((row.domain, f"gaming={gaming_score} non_gaming={non_gaming_score} domain={domain_gaming}"))

    logger.info(f"Filtered gaming ICP: {len(filtered)}")
    logger.info(f"Excluded non-gaming: {len(excluded)}")

    # Log excluded
    for domain, reason in excluded[:30]:
        logger.info(f"  EXCLUDED: {domain} ({reason})")

    # Count by source
    sources = {}
    for r in filtered:
        src = r.discovery_source or 'Unknown'
        sources[src] = sources.get(src, 0) + 1
    logger.info(f"By source: {sources}")

    # Build sheet
    headers = [
        "Domain", "URL", "Company Name", "Description",
        "Location", "Industry", "Segment", "Confidence",
        "Reasoning",
        "Discovery Source", "Search Query", "Search Geo",
        "Country (Apollo)", "Employees", "Revenue", "Founded Year",
        "Apollo Keywords", "Existing Emails",
    ]

    data = [headers]
    for row in filtered:
        data.append([
            row.domain or "",
            row.url or "",
            row.company_name or "",
            (row.description or "")[:300],
            row.location or "",
            row.industry or "",
            row.segment or "",
            str(row.confidence or ""),
            (row.reasoning or "")[:400],
            row.discovery_source or "",
            row.search_query or "",
            row.search_geo or "",
            row.apollo_country or "",
            row.employees or "",
            row.revenue or "",
            row.founded_year or "",
            (row.apollo_keywords or "")[:200],
            row.existing_emails or "",
        ])

    logger.info(f"Exporting {len(data)-1} gaming ICP targets to Google Sheets...")

    title = f"Inxy Gaming ICP Targets for Clay — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    url = google_sheets_service.create_and_populate(title=title, data=data, share_with=SHARE_WITH)

    if url:
        logger.info(f"SUCCESS: {url}")
    else:
        logger.error("Google Sheets failed, saving JSON")
        with open("/scripts/inxy_gaming_targets.json", "w") as f:
            json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)
        logger.info("JSON saved: /scripts/inxy_gaming_targets.json")


if __name__ == "__main__":
    asyncio.run(main())
