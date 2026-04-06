#!/usr/bin/env python3.11
"""
Extract a SmartLead subsequence and create it as a standalone campaign.

Target: c-OnSocial_Re-engagement (subsequence of c-OnSocial_IM agencies & SaaS_US&EU)
"""

import os
import sys
import json
import httpx
import time

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE = "https://server.smartlead.ai/api/v1"

if not SMARTLEAD_API_KEY:
    print("ERROR: SMARTLEAD_API_KEY not set")
    sys.exit(1)


def sl(extra=None):
    p = {"api_key": SMARTLEAD_API_KEY}
    if extra:
        p.update(extra)
    return p


def get(path, params=None, timeout=30):
    r = httpx.get(f"{BASE}{path}", params=sl(params), timeout=timeout)
    r.raise_for_status()
    return r.json()


def post(path, data, params=None, timeout=30):
    r = httpx.post(f"{BASE}{path}", params=sl(params), json=data, timeout=timeout)
    if r.status_code >= 400:
        print(f"  API error {r.status_code}: {r.text[:500]}")
    r.raise_for_status()
    return r.json()


# ── Step 1: Find the parent campaign and subsequence ──

print("Fetching all campaigns...")
camps = get("/campaigns")
if isinstance(camps, dict):
    camps = camps.get("campaigns", camps.get("data", []))

parent = None
subseq = None

for c in camps:
    name = c.get("name", "")
    if "Re-engagement" in name and "OnSocial" in name:
        subseq = c
        print(f"  Found subsequence: {name} (id={c['id']})")
    if "IM agencies" in name and "SaaS_US&EU" in name and "c-OnSocial" in name:
        if parent is None:  # take first match only
            parent = c
            print(f"  Found parent: {name} (id={c['id']})")

if not subseq:
    # Subsequences might not show in /campaigns list
    # Try to get them from the parent campaign's subsequences endpoint
    if parent:
        print(f"\nSubsequence not in campaign list. Checking parent {parent['id']} subsequences...")
        try:
            subs = get(f"/campaigns/{parent['id']}/sub-sequence-campaigns")
            print(f"  Subsequences response: {json.dumps(subs, indent=2)[:500]}")
            for s in (subs if isinstance(subs, list) else subs.get("data", [])):
                name = s.get("name", s.get("campaign_name", ""))
                if "Re-engagement" in name:
                    subseq = s
                    print(f"  Found subsequence: {name} (id={s.get('id', s.get('campaign_id'))})")
                    break
        except Exception as e:
            print(f"  Sub-sequence endpoint failed: {e}")

    if not subseq:
        print("\nERROR: Could not find c-OnSocial_Re-engagement subsequence")
        print(f"Total campaigns found: {len(camps)}")
        # Print all campaign names for debugging
        for c in camps:
            print(f"  - {c.get('name', '?')} (id={c.get('id')})")
        sys.exit(1)

subseq_id = subseq.get("id", subseq.get("campaign_id"))
print(f"\nSubsequence ID: {subseq_id}")

# ── Step 2: Get sequences from the subsequence ──

print("\nFetching sequences...")
try:
    seq_data = get(f"/campaigns/{subseq_id}/sequences")
    if isinstance(seq_data, dict):
        sequences = seq_data.get("sequences", seq_data.get("data", []))
    else:
        sequences = seq_data
    print(f"  Found {len(sequences)} sequences")
    for s in sequences:
        print(f"    Seq {s.get('seq_number', '?')}: {s.get('subject', '(no subject)')[:60]}")
except Exception as e:
    print(f"  Failed to fetch sequences: {e}")
    sequences = []

# ── Step 3: Get leads from the subsequence ──

print("\nFetching leads...")
all_leads = []
offset = 0
limit = 100

while True:
    try:
        resp = get(f"/campaigns/{subseq_id}/leads",
                    params={"offset": offset, "limit": limit},
                    timeout=60)
        if isinstance(resp, list):
            leads = resp
        else:
            leads = resp.get("leads", resp.get("data", []))

        if not leads:
            break

        all_leads.extend(leads)
        print(f"  Fetched {len(all_leads)} leads so far...")
        offset += limit

        if len(leads) < limit:
            break
    except Exception as e:
        print(f"  Error fetching leads at offset {offset}: {e}")
        break

print(f"  Total leads: {len(all_leads)}")

# ── Step 4: Get email accounts from parent/subsequence ──

print("\nFetching email accounts...")
try:
    accounts = get(f"/campaigns/{subseq_id}/email-accounts")
    if isinstance(accounts, dict):
        account_ids = [a.get("id") for a in accounts.get("data", accounts.get("email_accounts", []))]
    elif isinstance(accounts, list):
        account_ids = [a.get("id") for a in accounts]
    else:
        account_ids = []
    print(f"  Found {len(account_ids)} email accounts")
except Exception as e:
    print(f"  Failed to fetch email accounts: {e}")
    account_ids = []

# ── Step 5: Get schedule from parent ──

print("\nFetching schedule...")
try:
    source_id = parent["id"] if parent else subseq_id
    schedule = get(f"/campaigns/{source_id}/schedule")
    print(f"  Schedule: {json.dumps(schedule, indent=2)[:300]}")
except Exception as e:
    print(f"  Failed to fetch schedule (non-critical): {e}")
    schedule = None

# ── Save data locally before creating campaign ──

export = {
    "subsequence_id": subseq_id,
    "parent_id": parent["id"] if parent else None,
    "sequences": sequences,
    "leads_count": len(all_leads),
    "leads": all_leads,
    "email_account_ids": account_ids,
    "schedule": schedule,
}

export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "re_engagement_export.json")
with open(export_path, "w") as f:
    json.dump(export, f, indent=2, default=str)
print(f"\nExported data to {export_path}")

# ── Step 6: Create new standalone campaign ──

NEW_CAMPAIGN_NAME = "c-OnSocial_Re-engagement_standalone"

# Campaign already created in previous run
EXISTING_CAMPAIGN_ID = 3121190
new_id = EXISTING_CAMPAIGN_ID
print(f"\nUsing existing campaign: {NEW_CAMPAIGN_NAME} (id={new_id})")

# ── Step 7: Add sequences ──

if sequences:
    print("\nAdding sequences...")
    # Clean sequences for upload (API returns camelCase but expects snake_case)
    clean_seqs = []
    for s in sequences:
        raw_delay = s.get("seq_delay_details", {})
        delay_days = raw_delay.get("delay_in_days", raw_delay.get("delayInDays", 0))
        clean_seqs.append({
            "seq_number": s.get("seq_number"),
            "seq_delay_details": {"delay_in_days": delay_days},
            "subject": s.get("subject", ""),
            "email_body": s.get("email_body", ""),
        })

    try:
        seq_resp = post(f"/campaigns/{new_id}/sequences", {"sequences": clean_seqs})
        print(f"  Sequences added: {seq_resp}")
    except Exception as e:
        print(f"  Failed to add sequences: {e}")

# ── Step 8: Set email accounts ──

# Email accounts already set in previous run
print(f"\nEmail accounts: already set ({len(account_ids)} accounts)")

# ── Step 9: Set schedule ──

if schedule:
    print("\nSetting schedule...")
    try:
        sched_resp = post(f"/campaigns/{new_id}/schedule", schedule)
        print(f"  Schedule set: {sched_resp}")
    except Exception as e:
        print(f"  Failed to set schedule: {e}")

# ── Step 10: Upload leads ──

if all_leads:
    print(f"\nUploading {len(all_leads)} leads in batches of 100...")
    lead_list = []
    for item in all_leads:
        # Leads may be nested under "lead" key
        lead = item.get("lead", item) if isinstance(item, dict) else item
        entry = {
            "email": lead.get("email", ""),
            "first_name": lead.get("first_name", ""),
            "last_name": lead.get("last_name", ""),
            "company_name": lead.get("company_name", ""),
        }
        # Copy custom fields
        cf = lead.get("custom_fields", {})
        if cf:
            entry["custom_fields"] = cf
        if lead.get("linkedin_profile"):
            entry["linkedin_profile"] = lead["linkedin_profile"]
        if entry["email"]:
            lead_list.append(entry)

    # Upload in batches
    batch_size = 100
    for i in range(0, len(lead_list), batch_size):
        batch = lead_list[i:i + batch_size]
        try:
            resp = post(f"/campaigns/{new_id}/leads", {"lead_list": batch},
                        timeout=60)
            print(f"  Batch {i // batch_size + 1}: uploaded {len(batch)} leads")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"  Rate limited, waiting 70s...")
                time.sleep(70)
                resp = post("/leads", {"lead_list": batch},
                            params={"campaign_id": new_id}, timeout=60)
                print(f"  Batch {i // batch_size + 1}: uploaded {len(batch)} leads (retry)")
            else:
                print(f"  Batch {i // batch_size + 1} failed: {e}")

print(f"""
{'='*50}
DONE!
New campaign: {NEW_CAMPAIGN_NAME}
Campaign ID: {new_id}
Sequences: {len(sequences)}
Leads: {len(all_leads)}
Email accounts: {len(account_ids)}

⚠️  Campaign is NOT activated. Activate manually in SmartLead UI.
⚠️  Review sequences and settings before activating.
{'='*50}
""")
