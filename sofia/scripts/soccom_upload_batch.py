#!/usr/bin/env python3
"""Enrich SOCCOM Apollo contacts via FindyMail, upload to SmartLead, sync backend."""

import csv
import httpx
import time

FINDYMAIL_KEY = "dSxRrqArQIsG2E5zba36HLTy0pBk1bGZra5ZDtykea70c139"
SL_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
CAMPAIGN_ID = 3151592
CSV_PATH = "/tmp/soccom_apollo_contacts.csv"

with open(CSV_PATH) as f:
    rows = list(csv.DictReader(f))

print(f"Total: {len(rows)} contacts")

# Enrich missing emails via FindyMail
enriched = 0
for r in rows:
    if not r.get("Email", "").strip() and r.get("Person Linkedin Url", "").strip():
        url = r["Person Linkedin Url"].strip()
        if not url.startswith("http"):
            url = "https://" + url
        try:
            resp = httpx.post(
                "https://app.findymail.com/api/search/linkedin",
                headers={
                    "Authorization": f"Bearer {FINDYMAIL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"linkedin_url": url},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                email = data.get("contact", {}).get("email", "")
                if email:
                    r["Email"] = email
                    enriched += 1
                    name = f"{r['First Name']} {r['Last Name']}"
                    print(f"  Found: {name} -> {email}")
                else:
                    name = f"{r['First Name']} {r['Last Name']}"
                    print(f"  No email: {name}")
            elif resp.status_code == 429:
                print("  Rate limited, waiting...")
                time.sleep(65)
            else:
                name = f"{r['First Name']} {r['Last Name']}"
                print(f"  Error {resp.status_code}: {name}")
            time.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")

print(f"\nEnriched: {enriched} new emails")

# Filter to those with email
with_email = [r for r in rows if r.get("Email", "").strip()]
print(f"Total with email: {len(with_email)}")

# Build SmartLead leads
leads = []
for r in with_email:
    leads.append(
        {
            "email": r["Email"].strip(),
            "first_name": r.get("First Name", ""),
            "last_name": r.get("Last Name", ""),
            "company_name": r.get("Company Name", ""),
            "linkedin_profile": r.get("Person Linkedin Url", ""),
            "custom_fields": {
                "title": r.get("Title", ""),
                "country": r.get("Company Country", "") or r.get("Country", ""),
                "segment": "SOCIAL_COMMERCE",
            },
        }
    )

# Upload to SmartLead in batches of 50
total_uploaded = 0
for i in range(0, len(leads), 50):
    batch = leads[i : i + 50]
    resp = httpx.post(
        f"https://server.smartlead.ai/api/v1/campaigns/{CAMPAIGN_ID}/leads",
        params={"api_key": SL_KEY},
        json={"lead_list": batch},
        timeout=60,
    )
    if resp.status_code == 200:
        data = resp.json()
        uploaded = data.get("upload_count", 0)
        dupes = data.get("duplicate_count", 0)
        blocked = data.get("block_count", 0)
        total_uploaded += uploaded
        print(f"Batch {i // 50 + 1}: +{uploaded} (dupes={dupes}, blocked={blocked})")
    elif resp.status_code == 429:
        print("Rate limited, waiting...")
        time.sleep(65)
        resp2 = httpx.post(
            f"https://server.smartlead.ai/api/v1/campaigns/{CAMPAIGN_ID}/leads",
            params={"api_key": SL_KEY},
            json={"lead_list": batch},
            timeout=60,
        )
        if resp2.status_code == 200:
            total_uploaded += resp2.json().get("upload_count", 0)
    else:
        print(f"Error: {resp.status_code} {resp.text[:200]}")
    time.sleep(2)

print(f"\nTotal uploaded to SmartLead: {total_uploaded}")

# Sync to backend
bulk = []
for r in with_email:
    domain = (
        r.get("Website", "").replace("https://", "").replace("http://", "").strip("/")
    )
    bulk.append(
        {
            "email": r["Email"].strip(),
            "first_name": r.get("First Name", ""),
            "last_name": r.get("Last Name", ""),
            "company_name": r.get("Company Name", ""),
            "domain": domain,
            "job_title": r.get("Title", ""),
            "segment": "SOCIAL_COMMERCE",
            "project_id": 42,
            "source": "pipeline_step12",
            "linkedin_url": r.get("Person Linkedin Url", ""),
        }
    )

resp = httpx.post(
    "http://localhost:8000/api/contacts/bulk",
    headers={"X-Company-ID": "1", "Content-Type": "application/json"},
    json=bulk,
    timeout=60,
)
print(f"Backend sync: {resp.json()}")
