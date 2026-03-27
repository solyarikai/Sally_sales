#!/usr/bin/env python3
"""
Universal Findymail enrichment + Smartlead campaign creation pipeline.

Usage:
    python findymail_to_smartlead.py --input <filtered.csv> --campaign-name <name> --sequence <seq.json>

    # With optional overrides:
    python findymail_to_smartlead.py \\
        --input "projects/OnSocial/segments/Target - filtered.csv" \\
        --campaign-name "c-OnSocial_EUROPE #C v1" \\
        --sequence sequences/onsocial_default.json \\
        --email-accounts 2718958,2718959,2718960 \\
        --max-contacts 1500 \\
        --timezone "America/New_York" \\
        --skip-upload   # enrichment only, no Smartlead

Sequence JSON format (sequences/*.json):
    [
      {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "subject": "{{first_name}}, quick question about {{company_name}}",
        "email_body": "Hi {{first_name}},\\n\\n..."
      },
      ...
    ]

Output files (auto-derived from --input path):
    <input_stem> - emails.csv       all processed contacts + Email/Verified columns
    <input_stem> - with_email.csv   only contacts that got an email
Progress file:
    /tmp/findymail_<input_stem>.json  (auto-resume on re-run)
"""

import argparse
import asyncio
import csv
import json
import re
import time
from pathlib import Path

import os

import httpx

# ── API keys ──────────────────────────────────────────────────────────────────
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

FINDYMAIL_BASE = "https://app.findymail.com"
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

CONCURRENT = 5

# ── CSV Naming Convention ─────────────────────────────────────────────────────
# Naming: [PROJECT] | [TYPE] | [SEGMENT] — [DATE]
# Folder structure: output/OnSocial/{Leads,Import}/
from datetime import datetime
SOFIA_DIR_FM = Path(__file__).parent.parent
CSV_OUTPUT_DIR_FM = SOFIA_DIR_FM / "output" / "OnSocial"
CSV_LEADS_DIR = CSV_OUTPUT_DIR_FM / "Leads"
CSV_IMPORT_DIR_FM = CSV_OUTPUT_DIR_FM / "Import"
PROJECT_CODE_FM = "OS"

def _date_tag_fm() -> str:
    return datetime.now().strftime("%b %d")

# Default email accounts (OnSocial #C persona set)
DEFAULT_EMAIL_ACCOUNTS = [
    2718958, 2718959, 2718960, 2718961, 2718962,
    2718963, 2718964, 2718965, 2718966, 2718967,
    2718968, 2718969, 2718970, 2718971,
]

# Legal suffixes to strip from company names
LEGAL_SUFFIXES = re.compile(
    r'\s*[,.]?\s*(GmbH|Ltd\.?|Limited|LLC|Inc\.?|Corp\.?|SAS|S\.A\.S\.?|'
    r'BV|B\.V\.|NV|N\.V\.|SRL|AB|AS|Oy|KG|AG|OÜ|Pvt\.?\s*Ltd\.?|Pte\.?\s*Ltd\.?|'
    r'S\.A\.|SA|SL|SLU|SpA|Srl|SARL|EIRL|SASU|S\.r\.l\.)\s*$',
    re.IGNORECASE,
)


# ── Company name normalization ────────────────────────────────────────────────

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


# ── Findymail ─────────────────────────────────────────────────────────────────

def fm_headers():
    return {"Authorization": f"Bearer {FINDYMAIL_API_KEY}", "Content-Type": "application/json"}


async def find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers=fm_headers(),
            json={"linkedin_url": url},
            timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            email = data.get("email") or contact.get("email")
            verified = data.get("verified", False) or contact.get("verified", False)
            return {"email": email or "", "verified": verified}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        elif r.status_code == 404:
            return {"email": "", "verified": False}
        else:
            print(f"  WARN {r.status_code}: {r.text[:100]}")
            return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"email": "", "verified": False}


async def enrich(input_csv: Path, emails_csv: Path, with_email_csv: Path,
                 progress_file: Path, max_contacts: int) -> list[dict]:
    done: dict = {}
    if progress_file.exists():
        done = json.loads(progress_file.read_text())
        print(f"Resuming: {len(done)} already processed")

    rows = list(csv.DictReader(input_csv.open(encoding="utf-8")))
    print(f"Total contacts in file: {len(rows)}")

    def score_key(r):
        try:
            return float(r.get("Score", 0) or 0)
        except Exception:
            return 0.0

    rows.sort(key=score_key, reverse=True)
    rows = rows[:max_contacts]
    print(f"Processing top {len(rows)} by Score")

    sem = asyncio.Semaphore(CONCURRENT)
    found = not_found = skipped = 0
    out_of_credits = False

    async def process_one(row):
        nonlocal found, not_found, skipped, out_of_credits
        if out_of_credits:
            row["Email"] = ""
            row["Verified"] = ""
            return

        li_url = row.get("Profile URL", "").strip()
        if not li_url:
            row["Email"] = ""
            row["Verified"] = ""
            skipped += 1
            return

        if li_url in done:
            res = done[li_url]
            row["Email"] = res.get("email", "")
            row["Verified"] = str(res.get("verified", False))
            if res.get("email"):
                found += 1
            else:
                not_found += 1
            skipped += 1
            return

        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await find_email(client, li_url)
                except RuntimeError:
                    out_of_credits = True
                    row["Email"] = ""
                    row["Verified"] = ""
                    return

            row["Email"] = res.get("email", "")
            row["Verified"] = str(res.get("verified", False))
            done[li_url] = res

            if res.get("email"):
                found += 1
                print(f"  ✓ {row.get('Name', '')} → {res['email']}")
            else:
                not_found += 1

    t0 = time.time()
    batch_size = 20

    for i in range(0, len(rows), batch_size):
        if out_of_credits:
            print("\n❌ OUT OF CREDITS — stopping")
            break
        batch = rows[i:i + batch_size]
        await asyncio.gather(*[process_one(r) for r in batch])
        progress_file.write_text(json.dumps(done))
        processed = found + not_found + skipped
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed else 0
        eta = (len(rows) - processed) / rate if rate else 0
        print(f"[{processed}/{len(rows)}] found={found} not_found={not_found} "
              f"rate={rate:.1f}/s ETA={eta:.0f}s")

    progress_file.write_text(json.dumps(done))

    fieldnames = list(rows[0].keys()) if rows else []
    for f in ["Email", "Verified"]:
        if f not in fieldnames:
            fieldnames.append(f)

    with emails_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with_email = [r for r in rows if r.get("Email", "").strip()]
    with with_email_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(with_email)

    # IMPROVEMENT: Also save without_email.csv for Phase 2 (find_by_name) and GetSales
    without_email = [r for r in rows if not r.get("Email", "").strip() and r.get("Profile URL", "").strip()]
    # Replace "— emails" suffix with "— without_email" for the archive file
    stem_no_emails = re.sub(r"\s*[—-]\s*emails$", "", emails_csv.stem)
    without_email_csv = emails_csv.parent / f"{stem_no_emails} — without_email.csv"
    with without_email_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(without_email)

    elapsed = time.time() - t0
    print(f"\n=== Enrichment done ===")
    print(f"Processed: {found + not_found + skipped} / {len(rows)}")
    print(f"Found:     {found} ({found / max(1, found + not_found) * 100:.1f}% hit rate)")
    print(f"Output:    {with_email_csv} ({len(with_email)} contacts with email)")
    print(f"           {without_email_csv} ({len(without_email)} contacts without email → Phase 2 / GetSales)")
    print(f"Time:      {elapsed:.0f}s")

    return with_email


# ── Smartlead ─────────────────────────────────────────────────────────────────

def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}


def create_campaign(campaign_name: str) -> int:
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/create",
        params=sl_params(),
        json={
            "name": campaign_name,
            "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
            "send_as_plain_text": True,
            "stop_lead_settings": "REPLY_TO_AN_EMAIL",
        },
        timeout=30,
    )
    r.raise_for_status()
    campaign_id = r.json()["id"]
    print(f"Created campaign: {campaign_id} — {campaign_name}")
    return campaign_id


def add_sequences(campaign_id: int, sequence: list[dict]):
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/sequences",
        params=sl_params(),
        json={"sequences": sequence},
        timeout=30,
    )
    r.raise_for_status()
    print(f"Sequences added: {len(sequence)} steps")


def add_email_accounts(campaign_id: int, account_ids: list[int]):
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/email-accounts",
        params=sl_params(),
        json={"emailAccountIDs": account_ids},
        timeout=30,
    )
    r.raise_for_status()
    print(f"Email accounts added: {len(account_ids)}")


def set_schedule(campaign_id: int, timezone: str):
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/schedule",
        params=sl_params(),
        json={
            "timezone": timezone,
            "days_of_the_week": [1, 2, 3, 4, 5],
            "start_hour": "08:00",
            "end_hour": "18:00",
            "min_time_btw_emails": 10,
            "max_new_leads_per_day": 1000,
        },
        timeout=30,
    )
    r.raise_for_status()
    print(f"Schedule set: Mon-Fri 08:00-18:00 ({timezone})")


def sync_blacklist(rows: list[dict], blacklist_file: Path | None):
    """Add uploaded lead domains to blacklist file so they're excluded from future pipeline runs."""
    if not blacklist_file:
        return
    domains = set()
    for r in rows:
        email = r.get("Email", "").strip()
        if email and "@" in email:
            domain = email.split("@", 1)[1].lower().strip()
            if domain:
                domains.add(domain)
        company = r.get("Company Domain", "").strip() or r.get("Website", "").strip()
        if company:
            d = company.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            if d:
                domains.add(d)
    if not domains:
        return
    # Load existing blacklist
    if blacklist_file.exists():
        existing = json.loads(blacklist_file.read_text(encoding="utf-8"))
    else:
        existing = {"domains": [], "count": 0}
    bl_set = set(existing.get("domains", []))
    new_domains = domains - bl_set
    if not new_domains:
        print(f"\n🔒 Blacklist: all {len(domains)} domains already in blacklist")
        return
    bl_set.update(new_domains)
    existing["domains"] = sorted(bl_set)
    existing["count"] = len(bl_set)
    existing["last_synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with blacklist_file.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"\n🔒 Blacklist: added {len(new_domains)} new domains → {blacklist_file.name} (total: {len(bl_set)})")


def upload_leads(campaign_id: int, rows: list[dict]) -> int:
    leads = []
    for r in rows:
        name = r.get("Name", "").strip()
        parts = name.split(" ", 1)
        first = parts[0] if parts else ""
        last = parts[1] if len(parts) > 1 else ""

        leads.append({
            "email": r.get("Email", "").strip(),
            "first_name": first,
            "last_name": last,
            "company_name": normalize_company(r.get("Company", "")),
            "linkedin_profile": r.get("Profile URL", "").strip(),
            "custom_fields": {
                "title": r.get("Title", "").strip(),
                "location": r.get("Location", "").strip(),
            },
        })

    batch_size = 100
    total_ok = 0
    for i in range(0, len(leads), batch_size):
        batch = leads[i:i + batch_size]
        r = httpx.post(
            f"{SMARTLEAD_BASE}/leads",
            params={**sl_params(), "campaign_id": campaign_id},
            json={"lead_list": batch},
            timeout=60,
        )
        if r.status_code == 200:
            total_ok += len(batch)
            print(f"  Batch {i // batch_size + 1}: {len(batch)} leads (total {total_ok})")
        elif r.status_code == 429:
            print(f"  Rate limit — waiting 70s...")
            time.sleep(70)
            r2 = httpx.post(
                f"{SMARTLEAD_BASE}/leads",
                params={**sl_params(), "campaign_id": campaign_id},
                json={"lead_list": batch},
                timeout=60,
            )
            if r2.status_code == 200:
                total_ok += len(batch)
                print(f"  Batch {i // batch_size + 1} (retry): {len(batch)} leads (total {total_ok})")
            else:
                print(f"  WARN batch {i // batch_size + 1} retry failed: {r2.status_code} {r2.text[:200]}")
        else:
            print(f"  WARN batch {i // batch_size + 1}: {r.status_code} {r.text[:200]}")
        time.sleep(1)

    print(f"\nTotal uploaded: {total_ok} / {len(leads)}")
    return total_ok


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Findymail enrichment + Smartlead campaign upload pipeline"
    )
    parser.add_argument("--input", required=True,
                        help="Path to filtered CSV (must have 'Profile URL' and 'Company' columns)")
    parser.add_argument("--campaign-name", required=True,
                        help="Smartlead campaign name")
    parser.add_argument("--sequence", required=True,
                        help="Path to sequence JSON file (list of steps)")
    parser.add_argument("--email-accounts",
                        help="Comma-separated email account IDs (default: OnSocial #C set)")
    parser.add_argument("--max-contacts", type=int, default=1500,
                        help="Max contacts to enrich, sorted by Score desc (default: 1500)")
    parser.add_argument("--timezone", default="America/New_York",
                        help="Campaign timezone (default: America/New_York)")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Only enrich emails, skip Smartlead campaign creation")
    parser.add_argument("--blacklist-file", type=str, default=None,
                        help="Path to campaign_blacklist.json — uploaded domains will be added")
    return parser.parse_args()


async def main():
    args = parse_args()

    input_csv = Path(args.input)
    if not input_csv.exists():
        print(f"ERROR: input file not found: {input_csv}")
        return

    sequence_path = Path(args.sequence)
    if not sequence_path.exists():
        print(f"ERROR: sequence file not found: {sequence_path}")
        return

    sequence = json.loads(sequence_path.read_text())
    print(f"Sequence: {len(sequence)} steps loaded from {sequence_path.name}")

    email_accounts = DEFAULT_EMAIL_ACCOUNTS
    if args.email_accounts:
        email_accounts = [int(x.strip()) for x in args.email_accounts.split(",")]

    # Derive segment label from campaign name (e.g. "c-OnSocial_IMAGENCY #C v1" → "IMAGENCY")
    # Pattern: look for known segment codes or fall back to safe slug
    seg_match = re.search(r'[_\-\s]([A-Z][A-Z0-9_]+)\s*[#v\d]', args.campaign_name)
    seg_label = seg_match.group(1) if seg_match else re.sub(r"[^\w]+", "_", args.campaign_name).upper()[:20]
    date_tag = _date_tag_fm()

    # Create output dirs
    CSV_LEADS_DIR.mkdir(parents=True, exist_ok=True)
    CSV_IMPORT_DIR_FM.mkdir(parents=True, exist_ok=True)

    # Naming convention outputs:
    #   Import/  OS | Import | Findymail — SEGMENT — DATE - emails.csv    (all processed, with Verified column)
    #   Leads/   OS | Leads  | SEGMENT — DATE.csv                         (only contacts with email, ready for SmartLead)
    #   Import/  OS | Import | Findymail — SEGMENT — DATE - without_email.csv
    emails_csv = CSV_IMPORT_DIR_FM / f"{PROJECT_CODE_FM} | Import | Findymail — {seg_label} — {date_tag} — emails.csv"
    with_email_csv = CSV_LEADS_DIR / f"{PROJECT_CODE_FM} | Leads | {seg_label} — {date_tag}.csv"

    # Progress file: safe slug from campaign name
    safe_stem = re.sub(r"[^\w]+", "_", args.campaign_name).strip("_").lower()
    progress_file = Path(f"/tmp/findymail_{safe_stem}.json")

    print(f"=== Step 1: Enriching contacts via Findymail ===")
    print(f"Input:    {input_csv}")
    print(f"Progress: {progress_file}")
    with_email = await enrich(input_csv, emails_csv, with_email_csv,
                              progress_file, args.max_contacts)

    if not with_email:
        print("No emails found — stopping")
        return

    if args.skip_upload:
        print(f"\n--skip-upload set. Done. {len(with_email)} contacts with email in {with_email_csv}")
        return

    print(f"\n=== Step 2: Creating Smartlead campaign ===")
    campaign_id = create_campaign(args.campaign_name)
    add_sequences(campaign_id, sequence)
    add_email_accounts(campaign_id, email_accounts)
    set_schedule(campaign_id, args.timezone)

    print(f"\n=== Step 3: Uploading {len(with_email)} leads ===")
    upload_leads(campaign_id, with_email)

    # Sync uploaded domains to blacklist
    blacklist_path = Path(args.blacklist_file) if args.blacklist_file else None
    sync_blacklist(with_email, blacklist_path)

    print(f"\n=== DONE ===")
    print(f"Campaign ID: {campaign_id}")
    print(f"Status: DRAFTED (needs manual activation in Smartlead UI)")


if __name__ == "__main__":
    asyncio.run(main())
