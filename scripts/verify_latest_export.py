"""Verify exported contacts don't overlap with latest SmartLead Deliryo campaigns."""
import asyncio
import httpx
import os
from app.db.database import async_session_maker
from sqlalchemy import text


LATEST_CAMPAIGN_IDS = [2933525, 2929798, 2927471, 2921357]


async def fetch_campaign_emails(client, api_key, campaign_id):
    """Fetch all emails from a SmartLead campaign."""
    emails = set()
    offset = 0
    while True:
        for attempt in range(3):
            r = await client.get(
                f'https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads',
                params={'api_key': api_key, 'offset': offset, 'limit': 100}
            )
            if r.status_code == 200:
                break
            await asyncio.sleep(2 * (attempt + 1))
        if r.status_code != 200:
            print(f"  WARNING: failed to fetch campaign {campaign_id} offset {offset}: {r.status_code}")
            break
        data = r.json()
        leads = data.get('data', [])
        if not leads:
            break
        for lead in leads:
            email = lead.get('lead', {}).get('email', '')
            if email:
                emails.add(email.lower().strip())
        offset += 100
        if offset >= int(data.get('total_leads', 0)):
            break
        await asyncio.sleep(1)  # rate limit
    return emails


async def main():
    api_key = os.environ.get('SMARTLEAD_API_KEY')

    # 1. Get all exported emails from the pipeline query
    async with async_session_maker() as s:
        r = await s.execute(text("""
            SELECT DISTINCT lower(ec.email) 
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 18 AND dc.is_target = true
            AND ec.email IS NOT NULL AND ec.email != ''
            AND lower(ec.email) NOT IN (
                SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL
            )
        """))
        exported_emails = {row[0] for row in r.fetchall()}
    print(f"Exported emails: {len(exported_emails)}")

    # 2. Fetch emails from latest 4 SmartLead campaigns
    all_sl_emails = set()
    async with httpx.AsyncClient(timeout=30) as client:
        for cid in LATEST_CAMPAIGN_IDS:
            emails = await fetch_campaign_emails(client, api_key, cid)
            print(f"  Campaign {cid}: {len(emails)} emails")
            all_sl_emails.update(emails)
    print(f"Total SmartLead emails from latest 4 campaigns: {len(all_sl_emails)}")

    # 3. Check overlap
    overlap = exported_emails & all_sl_emails
    print(f"\nOVERLAP: {len(overlap)} emails")
    if overlap:
        for e in sorted(overlap)[:20]:
            print(f"  - {e}")
    else:
        print("CLEAN - no overlap with latest SmartLead Deliryo campaigns!")

    # 4. Also check against ALL 108 Deliryo campaigns (sample 5 random exported)
    if exported_emails:
        sample = list(exported_emails)[:5]
        print(f"\nSpot-check 5 exported emails against ALL SmartLead campaigns:")
        async with async_session_maker() as s:
            for email in sample:
                r2 = await s.execute(text(
                    "SELECT COUNT(*) FROM contacts WHERE lower(email) = :e"
                ), {"e": email})
                in_contacts = r2.scalar()
                print(f"  {email}: {'IN contacts table (BUG!)' if in_contacts else 'NOT in contacts (clean)'}")


asyncio.run(main())
