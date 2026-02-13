"""Sync ALL leads from latest Deliryo SmartLead campaigns into contacts table."""
import asyncio
import httpx
import os
from app.db.database import async_session_maker
from sqlalchemy import text


LATEST_CAMPAIGN_IDS = [2933525, 2929798, 2927471, 2921357]


async def fetch_all_campaign_emails(client, api_key, campaign_id):
    """Fetch all lead emails from a SmartLead campaign."""
    emails = set()
    offset = 0
    while True:
        r = await client.get(
            f'https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads',
            params={'api_key': api_key, 'offset': offset, 'limit': 100}
        )
        data = r.json()
        leads = data.get('data', [])
        if not leads:
            break
        for lead in leads:
            email = lead.get('lead', {}).get('email', '')
            if email:
                emails.add(email.lower().strip())
        offset += 100
        total = int(data.get('total_leads', 0))
        if offset >= total:
            break
        await asyncio.sleep(0.3)
    return emails


async def main():
    api_key = os.environ.get('SMARTLEAD_API_KEY')

    # Fetch all emails from latest campaigns
    all_emails = set()
    async with httpx.AsyncClient(timeout=30) as client:
        for cid in LATEST_CAMPAIGN_IDS:
            emails = await fetch_all_campaign_emails(client, api_key, cid)
            print(f"Campaign {cid}: {len(emails)} emails")
            all_emails.update(emails)
    print(f"Total unique emails from latest campaigns: {len(all_emails)}")

    # Check which are missing from contacts table
    async with async_session_maker() as s:
        r = await s.execute(text("SELECT DISTINCT lower(email) FROM contacts WHERE email IS NOT NULL"))
        existing = {row[0] for row in r.fetchall()}

    missing = all_emails - existing
    print(f"Already in contacts: {len(all_emails - missing)}")
    print(f"Missing from contacts: {len(missing)}")

    if not missing:
        print("Nothing to sync!")
        return

    # Insert missing emails
    async with async_session_maker() as s:
        inserted = 0
        for email in missing:
            domain = email.split('@')[-1] if '@' in email else None
            await s.execute(text("""
                INSERT INTO contacts (company_id, email, domain, source, status, is_active, created_at, updated_at)
                VALUES (1, :email, :domain, 'smartlead_deliryo_sync', 'contacted', true, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {"email": email, "domain": domain})
            inserted += 1
        await s.commit()
        print(f"Inserted {inserted} new contacts")

    # Verify
    async with async_session_maker() as s:
        r = await s.execute(text("SELECT COUNT(*) FROM contacts WHERE source = 'smartlead_deliryo_sync'"))
        print(f"Total smartlead_deliryo_sync contacts: {r.scalar()}")


asyncio.run(main())
