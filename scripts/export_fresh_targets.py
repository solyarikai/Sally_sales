#!/usr/bin/env python3
"""Export non-overlapping Deliryo target domains to Google Sheets."""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
if os.path.isdir('/app'):
    sys.path.insert(0, '/app')

from sqlalchemy import select, text
from app.db import async_session_maker, engine


async def export():
    async with async_session_maker() as session:
        # Get non-overlapping target domains with company info
        rows = (await session.execute(text("""
            SELECT sr.domain, sr.confidence, sr.reasoning,
                   sr.company_info::text, sr.scores::text,
                   sr.analyzed_at, sr.source_query_id
            FROM search_results sr
            WHERE sr.project_id = 18 AND sr.is_target = true
            AND lower(sr.domain) NOT IN (
                SELECT DISTINCT lower(domain) FROM contacts
                WHERE company_id = 1 AND domain IS NOT NULL AND campaigns IS NOT NULL
            )
            ORDER BY sr.confidence DESC NULLS LAST
        """))).fetchall()

        print(f"Found {len(rows)} non-overlapping targets")

        # Get query texts for source_query_id mapping
        query_ids = [r[6] for r in rows if r[6]]
        query_map = {}
        if query_ids:
            qrows = (await session.execute(text(
                "SELECT id, query_text FROM search_queries WHERE id = ANY(:ids)"
            ), {"ids": query_ids})).fetchall()
            query_map = {r[0]: r[1] for r in qrows}

        # Build sheet data
        headers = ["Domain", "Website", "Confidence", "Company Name", "Industry",
                   "Services", "Location", "Description", "Source Query", "Analyzed At"]
        sheet_rows = [headers]

        for r in rows:
            domain, confidence, reasoning, company_info_str, scores_str, analyzed_at, sq_id = r
            ci = {}
            if company_info_str:
                try:
                    ci = json.loads(company_info_str)
                except:
                    pass

            sheet_rows.append([
                domain,
                f"https://{domain}",
                round(confidence, 2) if confidence else "",
                ci.get("company_name", ""),
                ci.get("industry", ""),
                ", ".join(ci["services"]) if isinstance(ci.get("services"), list) else ci.get("services", ""),
                ci.get("location", ""),
                ci.get("description", "")[:200] if ci.get("description") else "",
                query_map.get(sq_id, "") if sq_id else "",
                analyzed_at.strftime("%Y-%m-%d %H:%M") if analyzed_at else "",
            ])

        # Export to Google Sheets
        from app.services.google_sheets_service import google_sheets_service

        if not google_sheets_service.is_configured():
            print("Google Sheets not configured, dumping CSV instead")
            import csv
            with open("/tmp/deliryo_fresh_targets.csv", "w") as f:
                writer = csv.writer(f)
                writer.writerows(sheet_rows)
            print("Saved to /tmp/deliryo_fresh_targets.csv")
            return

        sheet_url = google_sheets_service.create_and_populate(
            title=f"Deliryo Fresh Targets ({len(rows)} domains)",
            data=sheet_rows,
            share_with=["pn@getsally.io"],
        )
        print(f"Google Sheet: {sheet_url}")


async def main():
    try:
        await export()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
