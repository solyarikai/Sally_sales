#!/usr/bin/env python3
import asyncio, httpx, os, sys
sys.path.insert(0, '/app')

SL_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
BASE = 'https://server.smartlead.ai/api/v1'
CID = '3042239'

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BASE}/campaigns/{CID}/email-accounts", params={"api_key": SL_KEY})
        accounts = r.json()
        rinat_accs = [a for a in accounts if 'rinat' in a.get('from_email', '').lower()]
        print(f"Removing {len(rinat_accs)} rinat accounts...")

        removed = 0
        for acc in rinat_accs:
            aid = acc.get('id')
            r2 = await c.request("DELETE", f"{BASE}/campaigns/{CID}/email-accounts",
                params={"api_key": SL_KEY},
                json={"email_account_ids": [aid]})
            if r2.status_code == 200:
                removed += 1
            await asyncio.sleep(0.3)

        print(f"Removed: {removed}")

        r3 = await c.get(f"{BASE}/campaigns/{CID}/email-accounts", params={"api_key": SL_KEY})
        final = r3.json()
        print(f"Final: {len(final)} accounts (all petr@)")

if __name__ == '__main__':
    asyncio.run(main())
