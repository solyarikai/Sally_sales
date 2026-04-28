#!/usr/bin/env python3
"""
SmartLead negative leads -> project_blacklist sync.

Closes the gap where leads who replied "Not Interested" / "Do Not Contact" /
"Negative Reply" / "Not Qualified" or unsubscribed remained re-targetable
in future pipeline runs because their domains were never added to the
blacklist.

How it works:
  1. List all SmartLead campaigns whose name starts with `c-OnSocial_`.
  2. For each campaign, fetch leads filtered by negative `lead_category_id`
     (3, 4, 77594, 77596, 78987) using SmartLead's server-side filter.
  3. Also fetch unsubscribed leads (no category filter — scan all, keep
     `is_unsubscribed=True`).
  4. Extract domain from email (preferred) or website. Normalize.
  5. Upsert into `project_blacklist` (project_id=42) with
     source='smartlead_negative', reason='lead_category_id=N' or 'unsubscribed'.

Run locations:
  - Backfill (one-shot): `python3 blacklist_sync_smartlead.py --backfill`
  - Daily incremental:   `python3 blacklist_sync_smartlead.py --since 24h`
                         (uses created_at on the SmartLead lead-campaign mapping)

Designed for Hetzner — uses `docker exec leadgen-postgres` for DB writes,
matching the existing pipeline pattern. SmartLead API key is read from
env (`SMARTLEAD_API_KEY`) or `.env` in the repo root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"
ONSOCIAL_PROJECT_ID = 42
ONSOCIAL_CAMPAIGN_PREFIX = "c-OnSocial_"

NEGATIVE_CATEGORY_IDS = {
    3: "Not Interested",
    4: "Do Not Contact",
    77594: "Negative Reply",
    77596: "Do Not Contact (custom)",
    78987: "Not Qualified",
}

PAGE_SIZE = 100
REQUEST_PAUSE_S = 0.4
MAX_RETRIES = 6


def load_api_key() -> str:
    key = os.environ.get("SMARTLEAD_API_KEY")
    if key:
        return key
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("SMARTLEAD_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("SMARTLEAD_API_KEY not found in env or .env")


def smartlead_get(path: str, api_key: str, params: dict | None = None) -> dict | list:
    full_params = {"api_key": api_key}
    if params:
        full_params.update(params)
    for attempt in range(MAX_RETRIES):
        resp = requests.get(f"{SMARTLEAD_BASE}{path}", params=full_params, timeout=60)
        if resp.status_code == 429:
            wait = min(60, 2 ** (attempt + 2))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        time.sleep(REQUEST_PAUSE_S)
        return resp.json()
    raise RuntimeError(f"SmartLead API rate-limited after retries: {path}")


def get_campaign_total_leads(campaign_id: int, api_key: str, lead_category_id: int | None) -> int:
    """One lightweight call. Returns total_leads for filter, or 0 if unknown."""
    params = {"limit": 1, "offset": 0}
    if lead_category_id is not None:
        params["lead_category_id"] = lead_category_id
    data = smartlead_get(f"/campaigns/{campaign_id}/leads", api_key, params)
    if isinstance(data, dict):
        raw = data.get("total_leads", data.get("total"))
        try:
            return int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            return 0
    return len(data) if isinstance(data, list) else 0


def list_onsocial_campaigns(api_key: str) -> list[dict]:
    data = smartlead_get("/campaigns", api_key)
    if isinstance(data, dict):
        data = data.get("campaigns") or data.get("data") or []
    return [
        c for c in data
        if str(c.get("name", "")).startswith(ONSOCIAL_CAMPAIGN_PREFIX)
    ]


def iter_campaign_leads(
    campaign_id: int,
    api_key: str,
    lead_category_id: int | None = None,
) -> Iterable[dict]:
    offset = 0
    while True:
        params = {"limit": PAGE_SIZE, "offset": offset}
        if lead_category_id is not None:
            params["lead_category_id"] = lead_category_id
        data = smartlead_get(f"/campaigns/{campaign_id}/leads", api_key, params)
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            return
        for row in rows:
            yield row
        if len(rows) < PAGE_SIZE:
            return
        offset += PAGE_SIZE


@dataclass(frozen=True)
class BlacklistEntry:
    domain: str
    reason: str


_DOMAIN_TRIM_RE = re.compile(r"^https?://", re.I)


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""
    s = value.strip().lower()
    s = _DOMAIN_TRIM_RE.sub("", s)
    s = s.split("/", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def extract_domain_from_lead(lead: dict) -> str:
    email = (lead.get("email") or "").strip().lower()
    if "@" in email:
        return email.split("@", 1)[1]
    website = lead.get("website") or lead.get("company_url") or ""
    return normalize_domain(website)


# Our own domains — never blacklist (test forwards, internal addresses).
_OWN_DOMAINS = {
    "getsally.io", "sally.io", "onsocial.io", "onsocial-influence.com",
    "magnumops.com",
}

# Free email providers — never blacklist a whole provider domain.
_FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me",
    "protonmail.com", "gmx.com", "gmx.de", "mail.com", "yandex.ru",
    "yandex.com", "qq.com", "163.com", "126.com",
}


def _passes_since(row: dict, since: datetime | None) -> bool:
    if not since:
        return True
    raw_ts = row.get("created_at")
    if not raw_ts:
        return True
    try:
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except ValueError:
        return True
    return ts >= since


def collect_negative_domains(
    api_key: str,
    since: datetime | None,
    skip_unsubscribed: bool = False,
) -> dict[str, BlacklistEntry]:
    """Returns dict[domain -> BlacklistEntry], deduped by domain."""
    domains: dict[str, BlacklistEntry] = {}
    campaigns = list_onsocial_campaigns(api_key)
    print(f"OnSocial campaigns to scan: {len(campaigns)}")
    for camp in campaigns:
        camp_id = camp["id"]
        camp_name = camp.get("name", f"#{camp_id}")
        # Skip empty-or-not-relevant campaigns fast: check totals per category first.
        total_per_cat = {}
        for cat_id in NEGATIVE_CATEGORY_IDS:
            try:
                total_per_cat[cat_id] = get_campaign_total_leads(camp_id, api_key, cat_id)
            except Exception as exc:
                print(f"    {camp_id} cat {cat_id} probe failed: {exc}")
                total_per_cat[cat_id] = 0
        nonempty = {k: v for k, v in total_per_cat.items() if v > 0}
        if not nonempty and skip_unsubscribed:
            print(f"  campaign {camp_id} | {camp_name} — empty, skipped")
            continue
        print(f"  campaign {camp_id} | {camp_name}  totals={nonempty or '∅'}")

        for cat_id, total in total_per_cat.items():
            if total == 0:
                continue
            cat_name = NEGATIVE_CATEGORY_IDS[cat_id]
            count = 0
            for row in iter_campaign_leads(camp_id, api_key, cat_id):
                if not _passes_since(row, since):
                    continue
                lead = row.get("lead") or {}
                domain = extract_domain_from_lead(lead)
                if not domain or domain in _FREE_EMAIL_DOMAINS or domain in _OWN_DOMAINS:
                    continue
                if domain not in domains:
                    domains[domain] = BlacklistEntry(
                        domain=domain,
                        reason=f"smartlead category {cat_id} ({cat_name})",
                    )
                count += 1
            if count:
                print(f"    cat {cat_id} ({cat_name}): {count} leads")

        if skip_unsubscribed:
            continue

        # Unsubscribed sweep — expensive (no server-side filter). Skip via flag for daily mode.
        unsub_count = 0
        for row in iter_campaign_leads(camp_id, api_key, None):
            lead = row.get("lead") or {}
            if not lead.get("is_unsubscribed"):
                continue
            if not _passes_since(row, since):
                continue
            domain = extract_domain_from_lead(lead)
            if not domain or domain in _FREE_EMAIL_DOMAINS or domain in _OWN_DOMAINS:
                continue
            if domain not in domains:
                domains[domain] = BlacklistEntry(domain=domain, reason="smartlead unsubscribed")
            unsub_count += 1
        if unsub_count:
            print(f"    unsubscribed: {unsub_count} leads")
    return domains


def existing_blacklisted_domains() -> set[str]:
    """Read existing project_blacklist via docker exec. Hetzner-only."""
    cmd = [
        "docker", "exec", "leadgen-postgres",
        "psql", "-U", "leadgen", "-d", "leadgen", "-tA", "-c",
        f"SELECT LOWER(domain) FROM project_blacklist WHERE project_id = {ONSOCIAL_PROJECT_ID};",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"psql read failed: {result.stderr.strip()[:200]}")
    return {ln.strip() for ln in result.stdout.splitlines() if ln.strip()}


def insert_new_entries(entries: list[BlacklistEntry], dry_run: bool) -> int:
    if not entries:
        return 0
    if dry_run:
        print(f"  [dry-run] would insert {len(entries)} entries")
        for e in entries[:10]:
            print(f"    + {e.domain}  ({e.reason})")
        if len(entries) > 10:
            print(f"    ... and {len(entries) - 10} more")
        return 0

    # Build a single multi-row INSERT with ON CONFLICT DO NOTHING for idempotency.
    values_sql = ",".join(
        f"({ONSOCIAL_PROJECT_ID}, '{e.domain.replace(chr(39), chr(39)*2)}', "
        f"'{e.reason.replace(chr(39), chr(39)*2)}', 'smartlead_negative', NOW())"
        for e in entries
    )
    sql = (
        "INSERT INTO project_blacklist (project_id, domain, reason, source, created_at) "
        f"VALUES {values_sql} "
        "ON CONFLICT (project_id, domain) DO NOTHING "
        "RETURNING domain;"
    )
    cmd = [
        "docker", "exec", "-i", "leadgen-postgres",
        "psql", "-U", "leadgen", "-d", "leadgen", "-tA", "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"psql insert failed: {result.stderr.strip()[:500]}")
    inserted = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    return len(inserted)


def parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    if value == "backfill":
        return None
    m = re.match(r"^(\d+)([hd])$", value.strip())
    if not m:
        raise SystemExit(f"--since must be like '24h' or '7d' (got {value!r})")
    n = int(m.group(1))
    unit = m.group(2)
    delta = timedelta(hours=n) if unit == "h" else timedelta(days=n)
    return datetime.now(timezone.utc) - delta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", default=None,
        help="Time window: '24h', '7d', etc. Omit or use --backfill to scan all leads.",
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="One-shot full sweep across all OnSocial campaigns.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be inserted, don't write to DB.",
    )
    parser.add_argument(
        "--export-json", default=None,
        help="Optional: dump collected new domains to a JSON file.",
    )
    parser.add_argument(
        "--skip-unsubscribed", action="store_true",
        help="Skip the expensive unsubscribed sweep (no server-side filter). "
             "Use for daily incremental runs; backfill should keep it on.",
    )
    args = parser.parse_args()

    if args.backfill and args.since:
        raise SystemExit("Use either --backfill or --since, not both.")

    since = None if args.backfill else parse_since(args.since)
    if since:
        print(f"Mode: incremental, since {since.isoformat()}")
    else:
        print("Mode: full backfill")

    api_key = load_api_key()
    collected = collect_negative_domains(api_key, since, skip_unsubscribed=args.skip_unsubscribed)
    print(f"\nUnique negative domains collected: {len(collected)}")

    existing = existing_blacklisted_domains()
    print(f"Already in project_blacklist (project {ONSOCIAL_PROJECT_ID}): {len(existing)}")

    new_entries = [e for d, e in collected.items() if d not in existing]
    print(f"New domains to insert: {len(new_entries)}")

    if args.export_json and new_entries:
        Path(args.export_json).write_text(
            json.dumps([{"domain": e.domain, "reason": e.reason} for e in new_entries], indent=2)
        )
        print(f"  wrote {args.export_json}")

    inserted = insert_new_entries(new_entries, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"\nInserted: {inserted} (idempotent — duplicates skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
