#!/usr/bin/env python3
"""
Sync SmartLead campaign domains into campaign_blacklist.json.

Pulls all leads from all SmartLead campaigns via CSV export,
extracts domains from emails and websites, and merges into
the campaign_blacklist.json file used by the OnSocial pipeline.

Usage:
  python3 scripts/sync_smartlead_to_blacklist.py --dry-run   # preview changes
  python3 scripts/sync_smartlead_to_blacklist.py              # apply changes
"""

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://server.smartlead.ai/api/v1"
SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "")
MIN_INTERVAL = 0.4  # 150 req/min under 200/min limit
BLACKLIST_PATH = Path(__file__).resolve().parent.parent / "sofia" / "data" / "input" / "campaign_blacklist.json"
csv.field_size_limit(10 * 1024 * 1024)

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.fr",
    "outlook.com", "hotmail.com", "hotmail.co.uk", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com", "mac.com",
    "mail.com", "email.com", "protonmail.com", "proton.me",
    "yandex.ru", "yandex.com", "ya.ru",
    "mail.ru", "bk.ru", "inbox.ru", "list.ru",
    "zoho.com", "zohomail.com",
    "fastmail.com", "tutanota.com", "gmx.com", "gmx.de",
    "web.de", "t-online.de", "freenet.de",
    "orange.fr", "wanadoo.fr", "laposte.net", "sfr.fr",
    "libero.it", "virgilio.it", "alice.it",
    "163.com", "126.com", "qq.com", "sina.com",
    "naver.com", "daum.net", "hanmail.net",
    "rediffmail.com", "rocketmail.com",
}


def norm_domain(raw: str) -> str:
    """Normalize domain: strip protocol, www, port, trailing slash."""
    if not raw:
        return ""
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0]
    d = d.split("?")[0]
    d = d.split("#")[0]
    d = d.split(":")[0]  # strip port
    return d.strip()


def get_campaigns(sess: requests.Session) -> list[dict]:
    """Fetch all SmartLead campaigns."""
    resp = sess.get(f"{BASE_URL}/campaigns", params={"api_key": SMARTLEAD_API_KEY}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_domains_from_campaign(sess: requests.Session, campaign_id: int, campaign_name: str) -> set[str]:
    """Download CSV export for a campaign and extract domains from emails + custom fields."""
    try:
        resp = sess.get(
            f"{BASE_URL}/campaigns/{campaign_id}/leads-export",
            params={"api_key": SMARTLEAD_API_KEY},
            timeout=(10, 120),
        )
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT: {campaign_name[:40]}")
        return set()
    except Exception as e:
        print(f"  ERR: {campaign_name[:40]}: {e}")
        return set()

    if resp.status_code == 429:
        print(f"  429: {campaign_name[:40]} — sleeping 5s")
        time.sleep(5)
        return set()
    if resp.status_code != 200:
        return set()

    domains = set()
    try:
        text = resp.text.replace("\x00", "")  # strip null bytes
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception as e:
        print(f"  CSV err: {campaign_name[:40]}: {e}")
        return set()

    for row in rows:
        # Extract domain from email
        email = (row.get("email") or "").strip().lower()
        if email and "@" in email:
            domain = norm_domain(email.split("@", 1)[1])
            if domain and "." in domain and domain not in GENERIC_EMAIL_DOMAINS:
                domains.add(domain)

        # Extract from custom fields (Website / Company Domain)
        try:
            cf = json.loads(row.get("custom_fields", "{}") or "{}")
        except Exception:
            cf = {}
        for field in ("Website", "Company Domain", "Company_Domain", "website", "company_domain"):
            val = cf.get(field, "")
            if val:
                d = norm_domain(val)
                if d and "." in d and d not in GENERIC_EMAIL_DOMAINS:
                    domains.add(d)

    return domains


def load_blacklist(path: Path) -> dict:
    """Load existing blacklist JSON."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"domains": [], "count": 0}


def save_blacklist(path: Path, data: dict, backup: bool = True):
    """Save blacklist JSON with optional backup."""
    if backup and path.exists():
        date_str = time.strftime("%Y-%m-%d")
        backup_path = path.with_suffix(f".{date_str}.backup.json")
        shutil.copy2(path, backup_path)
        print(f"\n  Backup: {backup_path.name}")

    data["domains"] = sorted(set(data["domains"]))
    data["count"] = len(data["domains"])
    data["last_smartlead_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {path.name} ({data['count']} domains)")


def main():
    parser = argparse.ArgumentParser(description="Sync SmartLead domains → campaign_blacklist.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--blacklist", type=str, default=None, help="Custom blacklist path")
    args = parser.parse_args()

    if not SMARTLEAD_API_KEY:
        print("ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    bl_path = Path(args.blacklist) if args.blacklist else BLACKLIST_PATH
    print(f"=== SmartLead → Blacklist Sync ===")
    print(f"Blacklist: {bl_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    # Load existing blacklist
    blacklist = load_blacklist(bl_path)
    existing_count = blacklist.get("count", len(blacklist.get("domains", [])))
    bl_set = set(blacklist.get("domains", []))
    print(f"Existing blacklist: {existing_count} domains")

    # Fetch campaigns
    sess = requests.Session()
    print("\nFetching campaigns...")
    campaigns = get_campaigns(sess)
    print(f"Total campaigns: {len(campaigns)}")

    # Extract domains from all campaigns
    all_domains = set()
    started = time.time()

    for idx, camp in enumerate(campaigns):
        cid = camp.get("id")
        cname = camp.get("name", f"#{cid}")
        t0 = time.time()

        domains = extract_domains_from_campaign(sess, cid, cname)
        all_domains.update(domains)

        if (idx + 1) % 25 == 0 or idx < 3:
            elapsed = time.time() - started
            rate = (idx + 1) / elapsed * 60 if elapsed > 0 else 0
            eta = (len(campaigns) - idx - 1) / rate if rate > 0 else 0
            print(f"  [{idx+1}/{len(campaigns)}] {len(all_domains):,} domains | "
                  f"{rate:.0f} camps/min | ETA {eta:.1f}m | +{len(domains)} from {cname[:30]}")

        wait = MIN_INTERVAL - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)

    elapsed_total = time.time() - started
    print(f"\nDone in {elapsed_total:.0f}s")
    print(f"Total domains from SmartLead: {len(all_domains):,}")

    # Calculate diff
    new_domains = all_domains - bl_set
    already_in = all_domains & bl_set
    print(f"Already in blacklist: {len(already_in):,}")
    print(f"New to add: {len(new_domains):,}")

    if not new_domains:
        print("\nNothing to add — blacklist is up to date.")
        return

    # Show sample
    sample = sorted(new_domains)[:20]
    print(f"\nSample of new domains:")
    for d in sample:
        print(f"  {d}")
    if len(new_domains) > 20:
        print(f"  ... and {len(new_domains) - 20} more")

    if args.dry_run:
        print(f"\n[DRY RUN] Would add {len(new_domains)} domains → total {existing_count + len(new_domains)}")
        return

    # Merge and save
    bl_set.update(new_domains)
    blacklist["domains"] = sorted(bl_set)
    blacklist["count"] = len(bl_set)

    # Track source
    sources = blacklist.get("sources", {})
    sources["smartlead_sync"] = len(new_domains)
    blacklist["sources"] = sources

    save_blacklist(bl_path, blacklist)
    print(f"\nDone! {existing_count} → {len(bl_set)} domains (+{len(new_domains)} new)")


if __name__ == "__main__":
    main()
