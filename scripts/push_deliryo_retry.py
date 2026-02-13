"""Retry push to existing campaigns with correct API format."""
import asyncio
import httpx
import os
from datetime import datetime
from app.db.database import async_session_maker
from sqlalchemy import text, select
from app.models.pipeline import CampaignPushRule
from app.services.name_classifier import classify_contact, match_rule
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = 18
COMPANY_ID = 1
API_KEY = os.environ.get('SMARTLEAD_API_KEY')

# Map rule names to campaign IDs we already created
CAMPAIGN_MAP = {
    "No name (generic email)": "2935077",
    "Russian + name": "2935078",
    "English + name": "2935079",
}

async def main():
    print(f"\n{'='*60}")
    print(f"DELIRYO RETRY PUSH — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}\n")

    # Load rules
    async with async_session_maker() as session:
        result = await session.execute(
            select(CampaignPushRule).where(
                CampaignPushRule.project_id == PROJECT_ID,
                CampaignPushRule.is_active == True,
            ).order_by(CampaignPushRule.priority.desc())
        )
        rules = result.scalars().all()

    # Get new contacts
    async with async_session_maker() as session:
        rows = await session.execute(text("""
            SELECT ec.id, ec.email, ec.first_name, ec.last_name, ec.job_title,
                   dc.domain, dc.name as company_name, dc.url
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.company_id = :cid
            AND dc.is_target = true
            AND ec.email IS NOT NULL AND ec.email <> ''
            AND lower(ec.email) NOT IN (
                SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL
            )
            ORDER BY ec.id
        """), {"pid": PROJECT_ID, "cid": COMPANY_ID})
        contacts = rows.fetchall()

    print(f"New contacts to push: {len(contacts)}")
    if not contacts:
        print("Nothing to push!")
        return

    # Classify
    buckets = {rule.id: [] for rule in rules}
    for contact in contacts:
        cls = classify_contact(email=contact.email, first_name=contact.first_name, last_name=contact.last_name)
        for rule in rules:
            if match_rule(cls, rule):
                buckets[rule.id].append((contact, cls))
                break

    for rule in rules:
        print(f"  {rule.name}: {len(buckets[rule.id])} contacts → campaign {CAMPAIGN_MAP.get(rule.name, '?')}")

    # First fix email accounts on all 3 campaigns
    async with httpx.AsyncClient(timeout=60) as client:
        for rule in rules:
            campaign_id = CAMPAIGN_MAP.get(rule.name)
            if not campaign_id:
                continue

            # Assign email accounts with correct format
            if rule.email_account_ids:
                r = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts",
                    params={"api_key": API_KEY},
                    json={"email_account_ids": rule.email_account_ids},
                )
                print(f"  Email accounts for {rule.name}: {r.status_code}")

        # Push leads
        for rule in rules:
            bucket = buckets.get(rule.id, [])
            if not bucket:
                continue
            campaign_id = CAMPAIGN_MAP.get(rule.name)
            if not campaign_id:
                continue

            leads = []
            for contact, cls in bucket:
                lead = {
                    "email": contact.email,
                    "first_name": contact.first_name or "",
                    "last_name": contact.last_name or "",
                    "company_name": contact.company_name or "",
                    "website": contact.url or (f"https://{contact.domain}" if contact.domain else ""),
                }
                if contact.job_title:
                    lead["custom_fields"] = {"job_title": contact.job_title}
                leads.append(lead)

            # Push with correct format: {lead_list: [...]}
            BATCH = 100
            total_pushed = 0
            for i in range(0, len(leads), BATCH):
                batch = leads[i:i + BATCH]
                resp = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                    params={"api_key": API_KEY},
                    json={"lead_list": batch},
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    total_pushed += data.get("upload_count", len(batch))
                    print(f"  {rule.name}: pushed {data.get('upload_count', len(batch))} leads (dupes: {data.get('duplicate_count', 0)}, invalid: {data.get('invalid_email_count', 0)})")
                else:
                    print(f"  {rule.name}: FAILED {resp.status_code} {resp.text[:300]}")
                await asyncio.sleep(1)

            # Record in DB
            async with async_session_maker() as session:
                for contact, cls in bucket:
                    domain = contact.email.split("@")[-1] if "@" in contact.email else None
                    await session.execute(text("""
                        INSERT INTO contacts (company_id, email, first_name, last_name, domain,
                                              source, status, is_active, created_at, updated_at)
                        VALUES (:cid, :email, :fname, :lname, :domain,
                                'smartlead_pipeline_push', 'contacted', true, NOW(), NOW())
                        ON CONFLICT DO NOTHING
                    """), {
                        "cid": COMPANY_ID, "email": contact.email,
                        "fname": contact.first_name or "", "lname": contact.last_name or "",
                        "domain": domain,
                    })
                await session.commit()

            print(f"  {rule.name}: total={total_pushed}, recorded in DB")

    # Verify
    async with async_session_maker() as session:
        rows = await session.execute(text("""
            SELECT COUNT(*) FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.company_id = :cid
            AND dc.is_target = true AND ec.email IS NOT NULL AND ec.email <> ''
            AND lower(ec.email) NOT IN (SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL)
        """), {"pid": PROJECT_ID, "cid": COMPANY_ID})
        remaining = rows.scalar()
    print(f"\nRemaining unpushed: {remaining}")

asyncio.run(main())
