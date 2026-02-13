"""
Push ALL target contacts to the 3 Deliryo 11.02 SmartLead campaigns.
Bypasses the "already pushed" filter — SmartLead deduplicates on their end.

Campaigns:
  2929798 — Из РФ БЕЗ ИМЕНИ (generic/no name)
  2933525 — Из РФ Англ имена (English names)
  2927471 — Из РФ (Russian names)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


CAMPAIGNS = {
    "noname": "2929798",   # БЕЗ ИМЕНИ
    "en_name": "2933525",  # Англ имена
    "ru_name": "2927471",  # Из РФ
}


async def main():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        from app.core.config import settings
        database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    api_key = os.environ.get("SMARTLEAD_API_KEY", "")
    if not api_key:
        print("ERROR: SMARTLEAD_API_KEY not set")
        return

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Get ALL unique target contacts
    async with async_session() as session:
        rows = await session.execute(text("""
            SELECT DISTINCT ON (lower(ec.email))
                ec.email, ec.first_name, ec.last_name, ec.job_title,
                dc.domain, dc.name as company_name, dc.url
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 18
              AND dc.is_target = true
              AND ec.email IS NOT NULL AND ec.email != ''
            ORDER BY lower(ec.email), ec.id DESC
        """))
        contacts = rows.fetchall()

    print(f"Total unique target contacts: {len(contacts)}")

    # 2. Classify each contact
    from app.services.name_classifier import classify_contact

    buckets = {"noname": [], "en_name": [], "ru_name": []}

    for c in contacts:
        cls = classify_contact(
            email=c.email,
            first_name=c.first_name,
            last_name=c.last_name,
        )

        # Route: priority 10=noname, 5=en_name, 1=ru_name
        if not cls["has_name"] or cls["is_generic_email"]:
            buckets["noname"].append(c)
        elif cls["language"] == "en":
            buckets["en_name"].append(c)
        else:
            # Russian or unknown → Russian campaign
            buckets["ru_name"].append(c)

    for bk, bl in buckets.items():
        print(f"  {bk}: {len(bl)} contacts → campaign {CAMPAIGNS[bk]}")

    # 3. Push to SmartLead
    total_uploaded = 0
    total_duplicates = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for bucket_key, bucket_contacts in buckets.items():
            if not bucket_contacts:
                continue

            campaign_id = CAMPAIGNS[bucket_key]
            print(f"\nPushing {len(bucket_contacts)} contacts to campaign {campaign_id} ({bucket_key})...")

            # Push in batches of 100
            for i in range(0, len(bucket_contacts), 100):
                batch = bucket_contacts[i:i+100]
                leads = []
                for c in batch:
                    lead = {
                        "email": c.email,
                        "first_name": c.first_name or "",
                        "last_name": c.last_name or "",
                        "company_name": c.company_name or "",
                        "website": c.url or (f"https://{c.domain}" if c.domain else ""),
                    }
                    if c.job_title:
                        lead["custom_fields"] = {"job_title": c.job_title}
                    leads.append(lead)

                resp = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                    params={"api_key": api_key},
                    json={"lead_list": leads},
                    timeout=60,
                )

                if resp.status_code == 200:
                    data = resp.json() if resp.text else {}
                    uploaded = data.get("upload_count", len(leads))
                    dupes = data.get("duplicate_count", 0)
                    invalid = data.get("invalid_email_count", 0)
                    total_uploaded += uploaded
                    total_duplicates += dupes
                    print(f"  Batch {i//100 + 1}: uploaded={uploaded}, duplicates={dupes}, invalid={invalid}")
                else:
                    print(f"  ERROR: {resp.status_code} {resp.text[:200]}")

                await asyncio.sleep(1)  # Rate limit

    print(f"\n=== DONE ===")
    print(f"Total uploaded: {total_uploaded}")
    print(f"Total duplicates (already in campaigns): {total_duplicates}")
    print(f"Net new leads added: {total_uploaded}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
