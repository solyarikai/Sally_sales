#!/usr/bin/env python3
"""
Create AU-PH SmartLead campaign, set sequence, add email accounts, upload leads.

Same style as UAE-PK campaign 3048388 but adapted for Australian recipients
who have Filipino-origin teams/contractors.

Run on Hetzner:
  docker exec leadgen-backend python3 /app/easystaff-global/setup_au_ph_campaign.py

Steps:
  1. Create SmartLead campaign (DRAFT)
  2. Set 5-email sequence (Australia-adapted)
  3. Add same 12 Petr email accounts from 3048388
  4. Merge au_ph_with_emails.csv + au_ph_OPUS_FINAL.csv for location data
  5. Upload leads to campaign
  6. Add campaign to easystaff global project
"""
import asyncio
import csv
import json
import os
import sys
from collections import Counter
from io import StringIO

sys.path.insert(0, '/app')

from app.services.smartlead_service import SmartleadService
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CAMPAIGN_NAME = "AU-Philippines Petr 19/03"
SL_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
SL_BASE = 'https://server.smartlead.ai/api/v1'

# Same 12 Petr accounts from campaign 3048388
ACCOUNT_IDS = [
    13583534, 13583530, 13583527, 13583525, 13583519, 13583482,
    13583480, 13583474, 13583463, 13583457, 13583454, 12300717,
]

# Data files on Hetzner (mounted at /scripts/)
EMAILS_CSV = '/scripts/data/au_ph_with_emails.csv'
OPUS_FINAL_CSV = '/scripts/data/au_ph_OPUS_FINAL.csv'

# Project API
API_BASE = "http://localhost:8000/api"
HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Sequence — same as UAE-PK 3048388 but with {{city}} personalization
# ---------------------------------------------------------------------------
SEQUENCES = [
    {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "{{first_name}} \u2013 paying freelancers abroad?",
        "email_body": """Hi {{first_name}},

We at Easystaff help companies pay freelancers globally with fees under 1% \u2013 zero fees for your freelancers.

You can pay contractors via cards, PayPal, and USDT wallets \u2013 all paperwork handled by us.

Recently helped a company in {{city}} switch from Deel to paying 50 contractors across 8 countries, saving them $3,000/month on platform fees and exchange rates.

Would you like to calculate the cost benefit for your case?

Petr Nikolaev
BDM, Easystaff
Trusted by 5,000+ teams worldwide"""
    },
    {
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3},
        "subject": "",
        "email_body": """Hi {{first_name}},

Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.

We offer a better way:
- Cut out the middleman: Save the 10-20% freelance marketplace fees
- No annual contracts: Pay only for what you use
- Same-day payouts to any country, real human support (no bots)
- One compliant B2B invoice for all freelancer payments

Open to a quick demo call this week?"""
    },
    {
        "seq_number": 3,
        "seq_delay_details": {"delay_in_days": 4},
        "subject": "",
        "email_body": """Hi {{first_name}},

Just making sure my emails are getting through.

Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.

For 50+ contractors/month, we offer custom rates below any competitor.

Can I send you a 2-minute walkthrough video?"""
    },
    {
        "seq_number": 4,
        "seq_delay_details": {"delay_in_days": 7},
        "subject": "",
        "email_body": """Would it be easier to connect on LinkedIn or Telegram?

If you already have a payment solution, happy to compare \u2013 many clients switch after seeing the total cost difference.

Sent from my iPhone"""
    },
    {
        "seq_number": 5,
        "seq_delay_details": {"delay_in_days": 7},
        "subject": "",
        "email_body": """Hi {{first_name}},

I know you're busy and probably have a payment solution already.

But many clients switch to us for better terms, real human support, and fewer issues with global payouts compared to competitors' rigid systems or hidden fees.

If improving international payments is still a goal, I'm here to help.

Petr Nikolaev
BDM, Easystaff
Trusted by 5,000+ teams worldwide"""
    },
]


# ---------------------------------------------------------------------------
# City extraction from location string
# ---------------------------------------------------------------------------
# Map "Greater X Area" and suburb names to clean city names
CITY_ALIASES = {
    'greater sydney area': 'Sydney',
    'greater melbourne area': 'Melbourne',
    'greater brisbane area': 'Brisbane',
    'greater perth area': 'Perth',
    'greater adelaide area': 'Adelaide',
    'greater darwin area': 'Darwin',
    'greater newcastle area': 'Newcastle',
    'greater hobart area': 'Hobart',
    'greater geelong area': 'Geelong',
    'greater gold coast area': 'Gold Coast',
    'brisbane city': 'Brisbane',
    'sydney': 'Sydney',
    'melbourne': 'Melbourne',
    'brisbane': 'Brisbane',
    'perth': 'Perth',
    'adelaide': 'Adelaide',
    'gold coast': 'Gold Coast',
    'canberra': 'Canberra',
    'darwin': 'Darwin',
    'hobart': 'Hobart',
    'newcastle': 'Newcastle',
    'wollongong': 'Wollongong',
    'geelong': 'Geelong',
    'ballarat north': 'Ballarat',
    'sunshine coast': 'Sunshine Coast',
}

# State → default city fallback
STATE_CITY = {
    'new south wales': 'Sydney',
    'victoria': 'Melbourne',
    'queensland': 'Brisbane',
    'western australia': 'Perth',
    'south australia': 'Adelaide',
    'australian capital territory': 'Canberra',
    'northern territory': 'Darwin',
    'tasmania': 'Hobart',
}

FALLBACK_CITY = 'Australia'


def extract_city(location: str) -> str:
    """Extract clean city name from location string like 'Camden Park, New South Wales, Australia'."""
    if not location:
        return FALLBACK_CITY

    parts = [p.strip() for p in location.split(',')]

    # Try first part as city alias
    first = parts[0].lower()
    if first in CITY_ALIASES:
        return CITY_ALIASES[first]

    # Try state (second-to-last part before "Australia") → default city
    for part in parts:
        part_lower = part.strip().lower()
        if part_lower in STATE_CITY:
            return STATE_CITY[part_lower]

    # If location is just "Australia" or unrecognized, use fallback
    if 'australia' in location.lower():
        return FALLBACK_CITY

    # Use first part as-is if nothing else matches
    return parts[0] if parts[0] else FALLBACK_CITY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_leads():
    """Merge au_ph_with_emails.csv + au_ph_OPUS_FINAL.csv. Extract city for {{city}} variable."""
    # Load emails
    with open(EMAILS_CSV) as f:
        reader = csv.DictReader(f)
        email_rows = list(reader)
    print(f"Loaded {len(email_rows)} contacts with emails")

    # Load OPUS FINAL for location data
    opus_by_li = {}
    with open(OPUS_FINAL_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            li = (row.get('LinkedIn') or '').strip().rstrip('/')
            if li:
                opus_by_li[li.lower()] = row

    print(f"Loaded {len(opus_by_li)} OPUS FINAL contacts by LinkedIn URL")

    leads = []
    matched_loc = 0
    for e in email_rows:
        li = (e.get('linkedin_url') or '').strip().rstrip('/')
        opus = opus_by_li.get(li.lower(), {}) if li else {}

        location = opus.get('Location', '') or ''
        company_url = e.get('company_url', '') or opus.get('Domain', '') or ''
        city = extract_city(location)

        lead = {
            "email": e['email'],
            "first_name": e.get('first_name', ''),
            "last_name": e.get('last_name', ''),
            "company_name": e.get('company_name', '') or opus.get('Company', ''),
            "website": company_url,
            "custom_fields": {
                "city": city,
            },
        }

        if location:
            lead["custom_fields"]["location"] = location
            matched_loc += 1

        title = e.get('title', '') or opus.get('Title', '')
        if title:
            lead["custom_fields"]["title"] = title

        if li:
            lead["custom_fields"]["linkedin_url"] = li

        leads.append(lead)

    print(f"Matched location data: {matched_loc}/{len(leads)}")

    # City distribution
    cities = Counter()
    for lead in leads:
        cities[lead["custom_fields"]["city"]] += 1

    print("\nCity distribution (for {{city}} variable):")
    for city, cnt in cities.most_common(15):
        print(f"  {cnt:>4}  {city}")

    return leads


async def main():
    sl = SmartleadService()

    # ── Step 1: Create Campaign ──
    print("=" * 60)
    print("STEP 1: Creating SmartLead Campaign")
    print("=" * 60)
    result = await sl.create_campaign(CAMPAIGN_NAME)
    campaign_id = result.get('id') if result else None
    print(f"Campaign created: {CAMPAIGN_NAME}")
    print(f"Campaign ID: {campaign_id}")
    if not campaign_id:
        print("ERROR: Failed to create campaign")
        return

    # ── Step 2: Set Sequence ──
    print("\n" + "=" * 60)
    print("STEP 2: Setting 5-email sequence")
    print("=" * 60)
    seq_result = await sl.set_campaign_sequences(str(campaign_id), SEQUENCES)
    print(f"Sequence set: {seq_result}")

    # Verify
    steps = await sl.get_campaign_sequences(str(campaign_id))
    print(f"Verified: {len(steps)} steps")
    for s in steps:
        seq_num = s.get('seq_number', '?')
        subj = s.get('subject', '') or '(reply thread)'
        delay = s.get('seq_delay_details', {})
        print(f"  Step {seq_num}: delay={delay} subject='{subj[:50]}'")

    # ── Step 3: Add Email Accounts ──
    print("\n" + "=" * 60)
    print("STEP 3: Adding 12 Petr email accounts")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as c:
        added = 0
        errors = 0
        for acc_id in ACCOUNT_IDS:
            try:
                r = await c.post(
                    f"{SL_BASE}/campaigns/{campaign_id}/email-accounts",
                    params={"api_key": SL_KEY},
                    json={"email_account_ids": [acc_id]}
                )
                if r.status_code == 200:
                    added += 1
                else:
                    print(f"  Error adding {acc_id}: {r.status_code} {r.text[:100]}")
                    errors += 1
            except Exception as e:
                print(f"  Error adding {acc_id}: {e}")
                errors += 1
            await asyncio.sleep(0.3)

        print(f"Added: {added}, Errors: {errors}")

        # Verify accounts
        r = await c.get(
            f"{SL_BASE}/campaigns/{campaign_id}/email-accounts",
            params={"api_key": SL_KEY}
        )
        if r.status_code == 200:
            camp_accs = r.json()
            print(f"Campaign now has {len(camp_accs)} email accounts")

    # ── Step 4: Upload Leads ──
    print("\n" + "=" * 60)
    print("STEP 4: Uploading AU-PH leads")
    print("=" * 60)
    leads = load_leads()

    # Upload in batches of 100
    async with httpx.AsyncClient(timeout=60) as c:
        total_uploaded = 0
        for i in range(0, len(leads), 100):
            batch = leads[i:i + 100]
            try:
                r = await c.post(
                    f"{SL_BASE}/campaigns/{campaign_id}/leads",
                    params={"api_key": SL_KEY},
                    json={"lead_list": batch}
                )
                if r.status_code == 200:
                    resp = r.json()
                    uploaded = resp.get('upload_count', len(batch))
                    total_uploaded += uploaded
                    print(f"  Batch {i // 100 + 1}: uploaded {uploaded}")
                else:
                    print(f"  Batch {i // 100 + 1} error: {r.status_code} {r.text[:200]}")
            except Exception as e:
                print(f"  Batch {i // 100 + 1} error: {e}")
            await asyncio.sleep(1)

        print(f"Total uploaded: {total_uploaded}")

    # ── Step 5: Add to easystaff global project ──
    print("\n" + "=" * 60)
    print("STEP 5: Adding campaign to easystaff global project")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as client:
        # Get project
        resp = await client.get(f"{API_BASE}/contacts/projects/names", headers=HEADERS)
        projects = resp.json() if resp.status_code == 200 else []
        es_global = next((p for p in projects if 'easystaff global' in p.get('name', '').lower()), None)

        if es_global:
            project_id = es_global['id']
            print(f"Found easystaff global project: id={project_id}")

            # Get current campaign_filters
            resp = await client.get(f"{API_BASE}/contacts/projects/{project_id}", headers=HEADERS)
            if resp.status_code == 200:
                project_data = resp.json()
                filters = project_data.get('campaign_filters') or []
                if CAMPAIGN_NAME not in filters:
                    filters.append(CAMPAIGN_NAME)
                    resp = await client.patch(
                        f"{API_BASE}/contacts/projects/{project_id}",
                        headers=HEADERS,
                        json={"campaign_filters": filters}
                    )
                    if resp.status_code == 200:
                        print(f"Added '{CAMPAIGN_NAME}' to campaign_filters")
                    else:
                        print(f"Error updating filters: {resp.status_code} {resp.text[:200]}")
                else:
                    print(f"Campaign already in filters")

                # Update ownership rules to also match AU-Philippines prefix
                rules = project_data.get('campaign_ownership_rules') or {}
                prefixes = rules.get('prefixes', [])
                if 'AU-Philippines Petr' not in prefixes:
                    prefixes.append('AU-Philippines Petr')
                    rules['prefixes'] = prefixes
                    resp = await client.patch(
                        f"{API_BASE}/contacts/projects/{project_id}",
                        headers=HEADERS,
                        json={"campaign_ownership_rules": rules}
                    )
                    if resp.status_code == 200:
                        print(f"Added 'AU-Philippines Petr' prefix to ownership rules")
                    else:
                        print(f"Error updating rules: {resp.status_code}")
        else:
            print("ERROR: easystaff global project not found")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Campaign: {CAMPAIGN_NAME}")
    print(f"Campaign ID: {campaign_id}")
    print(f"SmartLead URL: https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics")
    print(f"Sequence: 5 steps")
    print(f"Email accounts: 12")
    print(f"Leads: {len(leads)}")
    print(f"")
    print(f"MANUAL STEPS:")
    print(f"  1. Add tag 'petr easystaff global' in SmartLead UI")
    print(f"  2. Review sequence in SmartLead UI")
    print(f"  3. Start campaign from SmartLead UI when ready")


if __name__ == '__main__':
    asyncio.run(main())
