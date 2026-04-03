"""Push Deliryo contacts to SmartLead + log before/after."""
import asyncio
import json
from datetime import datetime
from app.db.database import async_session_maker
from sqlalchemy import text
from app.models.pipeline import CampaignPushRule
from app.services.name_classifier import classify_contact, match_rule
from sqlalchemy import select
import httpx
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = 18
COMPANY_ID = 1
API_KEY = os.environ.get('SMARTLEAD_API_KEY')

async def get_new_contacts(session):
    """Get contacts not yet in SmartLead."""
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
    return rows.fetchall()


async def main():
    print(f"\n{'='*60}")
    print(f"DELIRYO SMARTLEAD PUSH — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}\n")

    # 1. Load rules
    async with async_session_maker() as session:
        result = await session.execute(
            select(CampaignPushRule).where(
                CampaignPushRule.project_id == PROJECT_ID,
                CampaignPushRule.company_id == COMPANY_ID,
                CampaignPushRule.is_active == True,
            ).order_by(CampaignPushRule.priority.desc())
        )
        rules = result.scalars().all()
    
    print(f"Push rules loaded: {len(rules)}")
    for r in rules:
        print(f"  #{r.id} | {r.name} | lang={r.language} | has_name={r.has_first_name} | priority={r.priority}")

    # 2. Get new contacts
    async with async_session_maker() as session:
        contacts = await get_new_contacts(session)
    
    print(f"\nNew contacts to push: {len(contacts)}")
    if not contacts:
        print("Nothing to push!")
        return

    # 3. Classify contacts
    buckets = {rule.id: [] for rule in rules}
    unmatched = []

    for contact in contacts:
        cls = classify_contact(
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
        )
        matched = False
        for rule in rules:
            if match_rule(cls, rule):
                buckets[rule.id].append((contact, cls))
                matched = True
                break
        if not matched:
            unmatched.append((contact, cls))

    print(f"\nClassification results:")
    for rule in rules:
        print(f"  {rule.name}: {len(buckets[rule.id])} contacts")
    if unmatched:
        print(f"  Unmatched: {len(unmatched)} contacts")

    # 4. Push to SmartLead
    log_entries = []
    
    async with httpx.AsyncClient(timeout=60) as client:
        for rule in rules:
            bucket = buckets.get(rule.id, [])
            if not bucket:
                continue

            print(f"\n--- Pushing {len(bucket)} contacts for rule: {rule.name} ---")

            # Create campaign
            campaign_name = rule.campaign_name_template.replace(
                "{date}", datetime.utcnow().strftime("%d.%m")
            )
            
            resp = await client.post(
                "https://server.smartlead.ai/api/v1/campaigns/create",
                params={"api_key": API_KEY},
                json={"name": campaign_name},
            )
            if resp.status_code != 200:
                print(f"  FAILED to create campaign: {resp.status_code} {resp.text[:200]}")
                continue
            
            data = resp.json()
            campaign_id = str(data.get("id", ""))
            print(f"  Created campaign: '{campaign_name}' (ID: {campaign_id})")

            # Set sequences
            if rule.sequence_template:
                seq_resp = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/sequences",
                    params={"api_key": API_KEY},
                    json={"sequences": rule.sequence_template},
                )
                print(f"  Sequences set: {seq_resp.status_code}")

            # Set schedule
            schedule = rule.schedule_config or {
                "timezone": "Europe/Moscow",
                "days_of_the_week": [1, 2, 3, 4, 5],
                "start_hour": "09:00",
                "end_hour": "18:00",
                "min_time_btw_emails": 5,
                "max_new_leads_per_day": 50,
            }
            await client.post(
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/schedule",
                params={"api_key": API_KEY},
                json=schedule,
            )

            # Set settings
            settings_cfg = rule.campaign_settings or {
                "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
                "stop_lead_settings": "REPLY_TO_AN_EMAIL",
                "send_as_plain_text": False,
                "follow_up_percentage": 100,
            }
            await client.post(
                f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/settings",
                params={"api_key": API_KEY},
                json=settings_cfg,
            )

            # Assign email accounts
            if rule.email_account_ids:
                for acc_id in rule.email_account_ids:
                    await client.post(
                        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts",
                        params={"api_key": API_KEY},
                        json={"id": acc_id},
                    )
                print(f"  Assigned {len(rule.email_account_ids)} email accounts")

            # Upload leads in batches
            BATCH = 100
            total_pushed = 0
            for i in range(0, len(bucket), BATCH):
                batch = bucket[i:i + BATCH]
                leads = []
                for contact, cls in batch:
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

                resp = await client.post(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads",
                    params={"api_key": API_KEY},
                    json=leads,
                    timeout=60,
                )
                if resp.status_code == 200:
                    total_pushed += len(leads)
                    print(f"  Pushed batch {i//BATCH + 1}: {len(leads)} leads (total: {total_pushed})")
                else:
                    print(f"  FAILED batch: {resp.status_code} {resp.text[:200]}")
                
                await asyncio.sleep(1)

            log_entries.append({
                "rule": rule.name,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "contacts_pushed": total_pushed,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Record pushed contacts so they won't be re-pushed
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
            print(f"  Recorded {total_pushed} contacts in DB to prevent re-push")

    # 5. Summary
    print(f"\n{'='*60}")
    print(f"PUSH COMPLETE")
    print(f"{'='*60}")
    total_all = sum(e["contacts_pushed"] for e in log_entries)
    print(f"Total contacts pushed: {total_all}")
    for e in log_entries:
        print(f"  {e['rule']}: {e['contacts_pushed']} → campaign '{e['campaign_name']}' (ID: {e['campaign_id']})")

    # Verify remaining
    async with async_session_maker() as session:
        remaining = await get_new_contacts(session)
    print(f"\nRemaining unpushed: {len(remaining)}")

    # Save log
    print(f"\nLog entries: {json.dumps(log_entries, ensure_ascii=False, indent=2)}")


asyncio.run(main())
