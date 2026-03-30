#!/usr/bin/env python3
"""Upload FindyMail-enriched leads to SmartLead campaign."""
import asyncio
import json
import sys
import os

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

CAMPAIGN_ID = '3042239'
LEADS_FILE = '/tmp/uae_pk_leads_for_smartlead.json'


async def main():
    sl = SmartleadService()
    leads = json.load(open(LEADS_FILE))
    print(f"Leads to upload: {len(leads)}")

    # Format for SmartLead
    sl_leads = []
    for lead in leads:
        sl_leads.append({
            'email': lead['email'],
            'first_name': lead.get('first_name', ''),
            'last_name': lead.get('last_name', ''),
            'company_name': lead.get('company', ''),
            'website': lead.get('domain', ''),
            'custom_fields': {
                'title': lead.get('title', ''),
                'location': lead.get('location', ''),
                'linkedin_url': lead.get('linkedin_url', ''),
            }
        })

    # Upload in batches of 100
    batch_size = 100
    total_added = 0
    for i in range(0, len(sl_leads), batch_size):
        batch = sl_leads[i:i + batch_size]
        try:
            result = await sl.add_leads_to_campaign(CAMPAIGN_ID, batch)
            success = result.get('success', False)
            if success:
                total_added += len(batch)
                print(f"  Batch {i//batch_size + 1}: uploaded {len(batch)} leads")
            else:
                print(f"  Batch {i//batch_size + 1}: FAILED - {result}")
        except Exception as e:
            print(f"  Batch {i//batch_size + 1}: ERROR - {e}")

        await asyncio.sleep(1)  # Rate limit

    print(f"\nDone! Uploaded {total_added} leads to campaign {CAMPAIGN_ID}")


if __name__ == '__main__':
    asyncio.run(main())
