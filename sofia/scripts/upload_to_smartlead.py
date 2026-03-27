#!/usr/bin/env python3
"""
Universal Smartlead upload: dedup + upload already-enriched CSV to an existing campaign.

Use this when enrichment (Findymail) is already done and you just need to upload leads.
For a full enrichment + upload pipeline, use findymail_to_smartlead.py instead.

Usage:
    python upload_to_smartlead.py --input <emails.csv> --campaign-id <id>

    # With optional overrides:
    python upload_to_smartlead.py \\
        --input "projects/OnSocial/segments/Target - emails.csv" \\
        --campaign-id 3064335 \\
        --email-col "FM_Email"          # default: "Email"
        --no-normalize-company          # skip company name normalization

Output files (auto-derived from --input):
    <input_stem> - with_email.csv      contacts that had an email
    <input_stem> - without_email.csv   contacts without email (for GetSales)
"""

import argparse
import asyncio
import csv
import re
import time
from pathlib import Path

import os

import httpx

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"
BATCH_SIZE = 100

LEGAL_SUFFIXES = re.compile(
    r'\s*[,.]?\s*(GmbH|Ltd\.?|Limited|LLC|Inc\.?|Corp\.?|SAS|S\.A\.S\.?|'
    r'BV|B\.V\.|NV|N\.V\.|SRL|AB|AS|Oy|KG|AG|OÜ|Pvt\.?\s*Ltd\.?|Pte\.?\s*Ltd\.?|'
    r'S\.A\.|SA|SL|SLU|SpA|Srl|SARL|EIRL|SASU|S\.r\.l\.)\s*$',
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    if not name:
        return name
    name = LEGAL_SUFFIXES.sub("", name).strip().rstrip(".,")
    if "-" in name and name == name.lower():
        name = name.replace("-", " ")
    if name == name.lower() and len(name) > 4:
        name = name.title()
    elif name == name.upper() and len(name) > 4:
        name = name.title()
    return name.strip()


def to_lead(row: dict, email_col: str, normalize: bool) -> dict:
    name_parts = row.get("Name", "").strip().split()
    first = name_parts[0] if name_parts else ""
    last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    company = row.get("Company", "").strip()
    if normalize:
        company = normalize_company(company)
    return {
        "email": row.get(email_col, "").strip(),
        "first_name": first,
        "last_name": last,
        "company_name": company,
        "linkedin_profile": row.get("Profile URL", "").strip(),
        "custom_fields": {
            "title": row.get("Title", row.get("Job title", "")).strip(),
            "location": row.get("Location", "").strip(),
        },
    }


async def upload_batch(client: httpx.AsyncClient, campaign_id: int,
                       leads: list[dict]) -> int:
    r = await client.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/leads",
        params={"api_key": SMARTLEAD_API_KEY},
        json={"lead_list": leads, "settings": {"ignore_global_block_list": False}},
        timeout=60.0,
    )
    if r.status_code == 200:
        data = r.json()
        count = data.get("upload_count", len(leads))
        return count if isinstance(count, int) else len(leads)
    elif r.status_code == 429:
        return -429  # signal to retry
    else:
        print(f"  WARN {r.status_code}: {r.text[:200]}")
        return 0


async def main():
    parser = argparse.ArgumentParser(
        description="Dedup and upload enriched CSV to an existing Smartlead campaign"
    )
    parser.add_argument("--input", required=True,
                        help="Path to enriched CSV (with Email column)")
    parser.add_argument("--campaign-id", required=True, type=int,
                        help="Smartlead campaign ID to upload leads into")
    parser.add_argument("--email-col", default="Email",
                        help="Column name containing the email address (default: Email)")
    parser.add_argument("--no-normalize-company", action="store_true",
                        help="Skip company name normalization")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return

    stem = input_path.stem
    parent = input_path.parent
    with_email_path = parent / f"{stem} - with_email.csv"
    without_email_path = parent / f"{stem} - without_email.csv"

    rows = list(csv.DictReader(input_path.open(encoding="utf-8")))
    print(f"Total rows: {len(rows)}")

    # Dedup by email + Profile URL
    seen_emails: set[str] = set()
    seen_urls: set[str] = set()
    with_email: list[dict] = []
    without_email: list[dict] = []

    for row in rows:
        email = row.get(args.email_col, "").strip().lower()
        url = row.get("Profile URL", "").strip()

        if email:
            if email in seen_emails:
                continue
            if url and url in seen_urls:
                continue
            seen_emails.add(email)
            if url:
                seen_urls.add(url)
            with_email.append(row)
        else:
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            without_email.append(row)

    print(f"With email (deduped): {len(with_email)}")
    print(f"Without email:        {len(without_email)}")

    # Save split CSVs
    fieldnames = list(rows[0].keys()) if rows else []
    with with_email_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(with_email)

    with without_email_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(without_email)

    print(f"Saved: {with_email_path.name}")
    print(f"Saved: {without_email_path.name}")

    if not with_email:
        print("No leads to upload.")
        return

    # Build lead payloads
    normalize = not args.no_normalize_company
    leads_payload = [to_lead(r, args.email_col, normalize) for r in with_email]

    # Upload in batches
    print(f"\nUploading {len(leads_payload)} leads to campaign {args.campaign_id}...")
    total_uploaded = 0

    async with httpx.AsyncClient() as client:
        for i in range(0, len(leads_payload), BATCH_SIZE):
            batch = leads_payload[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            count = await upload_batch(client, args.campaign_id, batch)

            if count == -429:
                print(f"  Rate limit on batch {batch_num} — waiting 70s...")
                time.sleep(70)
                count = await upload_batch(client, args.campaign_id, batch)

            total_uploaded += max(count, 0)
            print(f"  Batch {batch_num}: {count} uploaded [{total_uploaded}/{len(leads_payload)}]")
            time.sleep(1)

    print(f"\n=== DONE ===")
    print(f"Uploaded: {total_uploaded} / {len(leads_payload)} leads to campaign {args.campaign_id}")
    print(f"Without email (for GetSales): {len(without_email)} contacts in {without_email_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
