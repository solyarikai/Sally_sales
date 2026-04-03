"""
Inxy — Export ALL target companies to Google Sheet for Clay enrichment.
Includes: domain, company info, segment, reasoning, discovery source, search queries.
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
logger = logging.getLogger("inxy_export_targets")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48
SHARE_WITH = ["pn@getsally.io"]


async def main():
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info("=" * 60)
    logger.info("INXY — EXPORT ALL TARGET COMPANIES FOR CLAY")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        result = await session.execute(text("""
            SELECT
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
                    WHEN sj.config->>'segment' LIKE 'apollo%%' THEN 'Apollo'
                    ELSE COALESCE(sj.search_engine::text, 'Unknown')
                END as discovery_source,
                COALESCE(sq.query_text, '') as search_query,
                COALESCE(sq.geo, sj.config->>'geo', '') as search_geo,
                dc.apollo_org_data->>'country' as apollo_country,
                dc.apollo_org_data->>'estimated_num_employees' as employees,
                dc.apollo_org_data->>'annual_revenue_printed' as revenue,
                dc.apollo_org_data->>'founded_year' as founded_year,
                COALESCE(dc.contacts_count, 0) as contacts_count,
                COALESCE(dc.apollo_people_count, 0) as apollo_people_count,
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
            ORDER BY
                CASE
                    WHEN dc.company_info->>'source' = 'team_xlsx' THEN 0
                    WHEN sj.config->>'segment' = 'team_manual' THEN 0
                    ELSE 1
                END,
                dc.domain
        """), {"project_id": PROJECT_ID})
        rows = result.fetchall()

    logger.info(f"Total target companies: {len(rows)}")

    sources = {}
    for r in rows:
        src = r.discovery_source or "Unknown"
        sources[src] = sources.get(src, 0) + 1
    logger.info(f"By source: {sources}")

    with_emails = sum(1 for r in rows if r.existing_emails)
    logger.info(f"With existing emails: {with_emails}")
    logger.info(f"Without emails: {len(rows) - with_emails}")

    headers = [
        "Domain", "URL", "Company Name", "Description",
        "Location", "Industry", "Segment", "Confidence",
        "Reasoning",
        "Discovery Source", "Search Query", "Search Geo",
        "Country (Apollo)", "Employees", "Revenue", "Founded Year",
        "Contacts Count", "Apollo People Count", "Existing Emails",
    ]

    data = [headers]
    for row in rows:
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
            str(row.contacts_count or 0),
            str(row.apollo_people_count or 0),
            row.existing_emails or "",
        ])

    logger.info(f"Exporting {len(data)-1} rows to Google Sheets...")

    title = f"Inxy ALL Targets for Clay — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    url = google_sheets_service.create_and_populate(title=title, data=data, share_with=SHARE_WITH)

    if url:
        logger.info(f"SUCCESS: {url}")
    else:
        logger.error("Google Sheets export failed, saving JSON fallback")
        with open("/scripts/inxy_all_targets.json", "w") as f:
            json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)
        logger.info("JSON fallback saved: /scripts/inxy_all_targets.json")


if __name__ == "__main__":
    asyncio.run(main())
