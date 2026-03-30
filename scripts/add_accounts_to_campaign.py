#!/usr/bin/env python3
"""Add all Petr email accounts to SmartLead campaign."""
import asyncio
import httpx
import os
import sys
import json

sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SL_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
BASE = 'https://server.smartlead.ai/api/v1'
CAMPAIGN_ID = '3042239'
INFRA_SHEET = '1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg'


async def main():
    gs = GoogleSheetsService()

    # 1. Read Petr email accounts from infra sheet
    print("Reading email accounts from infra sheet...")
    raw = gs.read_sheet_raw(INFRA_SHEET, 'Accounts infra')
    petr_emails = []
    for row in raw[1:]:
        source = row[0].strip() if len(row) > 0 else ''
        login = row[1].strip() if len(row) > 1 else ''
        if source == 'Petr' and login:
            petr_emails.append(login)
    print(f"Petr accounts: {len(petr_emails)}")

    async with httpx.AsyncClient(timeout=30) as c:
        # 2. Get all email accounts from SmartLead
        print("\nFetching SmartLead email accounts...")
        all_accounts = []
        offset = 0
        while True:
            r = await c.get(f"{BASE}/email-accounts",
                           params={"api_key": SL_KEY, "offset": offset, "limit": 100})
            if r.status_code != 200:
                print(f"Error: {r.status_code} {r.text[:200]}")
                break
            batch = r.json()
            if not batch:
                break
            all_accounts.extend(batch)
            offset += 100
            if len(batch) < 100:
                break

        print(f"Total SmartLead accounts: {len(all_accounts)}")

        # 3. Match Petr emails to SmartLead account IDs
        sl_map = {}
        for acc in all_accounts:
            email = acc.get('from_email', '').lower()
            sl_map[email] = acc.get('id')

        matched = []
        missing = []
        for email in petr_emails:
            sl_id = sl_map.get(email.lower())
            if sl_id:
                matched.append((email, sl_id))
            else:
                missing.append(email)

        print(f"\nMatched to SmartLead: {len(matched)}")
        if missing:
            print(f"NOT in SmartLead ({len(missing)}):")
            for e in missing:
                print(f"  {e}")

        # 4. Add matched accounts to campaign
        print(f"\nAdding {len(matched)} accounts to campaign {CAMPAIGN_ID}...")
        added = 0
        errors = 0
        for email, sl_id in matched:
            try:
                r = await c.post(
                    f"{BASE}/campaigns/{CAMPAIGN_ID}/email-accounts",
                    params={"api_key": SL_KEY},
                    json={"email_account_ids": [sl_id]}
                )
                if r.status_code == 200:
                    added += 1
                else:
                    print(f"  Error adding {email}: {r.status_code} {r.text[:100]}")
                    errors += 1
            except Exception as e:
                print(f"  Error adding {email}: {e}")
                errors += 1

            await asyncio.sleep(0.3)  # Rate limit

        print(f"\nDone! Added: {added}, Errors: {errors}")

        # 5. Verify
        r = await c.get(f"{BASE}/campaigns/{CAMPAIGN_ID}/email-accounts",
                       params={"api_key": SL_KEY})
        if r.status_code == 200:
            camp_accounts = r.json()
            print(f"Campaign now has {len(camp_accounts)} email accounts")


if __name__ == '__main__':
    asyncio.run(main())
