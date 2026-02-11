"""Export Archistruct extracted contacts to Google Sheets."""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
if os.path.isdir('/app'):
    sys.path.insert(0, '/app')

from sqlalchemy import text
from app.db import async_session_maker, engine


async def export():
    async with async_session_maker() as session:
        rows = (await session.execute(text("""
            SELECT dc.domain, dc.name, dc.url, dc.confidence,
                   dc.company_info->>'industry' as industry,
                   dc.company_info->>'location' as location,
                   dc.company_info->>'services' as services,
                   dc.company_info->>'description' as description,
                   ec.email, ec.phone, ec.first_name, ec.last_name,
                   ec.job_title, ec.source::text,
                   dc.reasoning
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON dc.id = ec.discovered_company_id
            WHERE dc.project_id = 24 AND dc.is_target = true
            ORDER BY dc.confidence DESC NULLS LAST, dc.domain, ec.source
        """))).fetchall()

        print(f"Found {len(rows)} contact rows")

        # Also get targets with NO contacts (for completeness)
        no_contact_rows = (await session.execute(text("""
            SELECT dc.domain, dc.name, dc.url, dc.confidence,
                   dc.company_info->>'industry' as industry,
                   dc.company_info->>'location' as location,
                   dc.company_info->>'services' as services,
                   dc.company_info->>'description' as description,
                   dc.reasoning
            FROM discovered_companies dc
            WHERE dc.project_id = 24 AND dc.is_target = true
            AND dc.id NOT IN (
                SELECT DISTINCT discovered_company_id FROM extracted_contacts
            )
            ORDER BY dc.confidence DESC NULLS LAST
        """))).fetchall()

        print(f"Found {len(no_contact_rows)} targets with no contacts")

        headers = [
            "Domain", "Company Name", "Website", "Confidence",
            "Industry", "Location", "Services", "Description",
            "Email", "Phone", "First Name", "Last Name",
            "Job Title", "Source", "Reasoning"
        ]
        sheet_rows = [headers]

        for r in rows:
            (domain, name, url, confidence, industry, location,
             services, description, email, phone, first_name,
             last_name, job_title, source, reasoning) = r

            # Parse services if JSON array
            if services:
                try:
                    svc = json.loads(services)
                    if isinstance(svc, list):
                        services = ", ".join(svc)
                except:
                    pass

            sheet_rows.append([
                domain or "",
                name or "",
                url or f"https://{domain}" if domain else "",
                round(confidence, 2) if confidence else "",
                industry or "",
                location or "",
                (services or "")[:200],
                (description or "")[:200],
                email or "",
                phone or "",
                first_name or "",
                last_name or "",
                job_title or "",
                source or "",
                (reasoning or "")[:200],
            ])

        # Add targets with no contacts
        for r in no_contact_rows:
            (domain, name, url, confidence, industry, location,
             services, description, reasoning) = r

            if services:
                try:
                    svc = json.loads(services)
                    if isinstance(svc, list):
                        services = ", ".join(svc)
                except:
                    pass

            sheet_rows.append([
                domain or "",
                name or "",
                url or f"https://{domain}" if domain else "",
                round(confidence, 2) if confidence else "",
                industry or "",
                location or "",
                (services or "")[:200],
                (description or "")[:200],
                "", "", "", "", "",
                "NO_CONTACTS",
                (reasoning or "")[:200],
            ])

        from app.services.google_sheets_service import google_sheets_service

        if not google_sheets_service.is_configured():
            print("Google Sheets not configured!")
            return

        contact_count = sum(1 for r in sheet_rows[1:] if r[8])  # rows with email
        sheet_url = google_sheets_service.create_and_populate(
            title=f"Archistruct Contacts ({len(rows)} contacts, {contact_count} emails)",
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
