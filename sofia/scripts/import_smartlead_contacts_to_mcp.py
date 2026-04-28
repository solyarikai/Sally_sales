#!/usr/bin/env python3
"""
One-shot import of ALL SmartLead contacts (not just negative replies)
into MCP `discovered_companies` as is_blacklisted=true.

Why this exists:
  Daily `blacklist_sync_smartlead.py --target both` only catches NEW negative
  replies. But MCP project 438 also needs to know about everyone we've EVER
  contacted via SmartLead, so its gathering pipeline doesn't re-target them.

  In the leadgen-postgres `project_blacklist`, this layer is already covered
  by source='pipeline' (149 entries written at upload-time) + source='onsocial_20k'
  (10 656 from initial dump). The MCP DB has no equivalent.

  This script closes that gap with a one-shot UPSERT. Run once, then forget.

How it works:
  1. List all `c-OnSocial_*` SmartLead campaigns.
  2. For each campaign, fetch ALL leads (no category filter).
  3. Extract domain from email/website. Apply whitelist (free providers,
     our own domains).
  4. UPSERT into mcp-postgres / discovered_companies project_id=438:
     - UPDATE existing rows: set is_blacklisted=TRUE if not already set.
     - INSERT hollow rows: with project=438, company=199, is_blacklisted=TRUE.

Idempotent. Safe to re-run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reuse plumbing from the main sync script (same directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blacklist_sync_smartlead import (  # noqa: E402
    DB_TARGETS,
    PROJECT_REGISTRY,
    _esc,
    _psql,
    extract_domain_from_lead,
    iter_campaign_leads,
    list_project_campaigns,
    load_api_key,
    _OWN_DOMAINS,
    _FREE_EMAIL_DOMAINS,
)


def collect_all_contact_domains(api_key: str, campaign_prefix: str) -> dict[str, str]:
    """
    Returns dict[domain -> campaign_name (most recent campaign that contained it)].
    No category filter — pulls EVERYONE we've ever written to.
    """
    domains: dict[str, str] = {}
    campaigns = list_project_campaigns(api_key, campaign_prefix)
    print(f"Campaigns matching {campaign_prefix!r}: {len(campaigns)}")
    for camp in campaigns:
        camp_id = camp["id"]
        camp_name = camp.get("name", f"#{camp_id}")
        count = 0
        for row in iter_campaign_leads(camp_id, api_key, None):
            lead = row.get("lead") or {}
            domain = extract_domain_from_lead(lead)
            if not domain or domain in _FREE_EMAIL_DOMAINS or domain in _OWN_DOMAINS:
                continue
            domains[domain] = camp_name  # keep last-seen campaign for reason
            count += 1
        print(f"  {camp_id}  {camp_name[:55]:55s}  {count:>5} leads")
    return domains


def upsert_all_to_mcp(
    domains: dict[str, str],
    project_id: int,
    company_id: int,
    dry_run: bool,
) -> dict[str, int]:
    if not domains:
        return {"updated": 0, "inserted": 0}

    if dry_run:
        sample = list(domains.items())[:10]
        print(
            f"  [dry-run] would upsert {len(domains)} domains into project {project_id}"
        )
        for d, c in sample:
            print(f"    ? {d}  (from {c})")
        if len(domains) > 10:
            print(f"    ... and {len(domains) - 10} more")
        return {"updated": 0, "inserted": 0}

    BATCH = 500
    items = list(domains.items())
    updated_total = 0
    inserted_total = 0
    n_batches = (len(items) + BATCH - 1) // BATCH

    for i in range(0, len(items), BATCH):
        chunk = items[i : i + BATCH]
        bnum = i // BATCH + 1

        # Step 1: UPDATE existing not-yet-blacklisted rows in this chunk.
        update_values = ",".join(f"('{_esc(d)}', '{_esc(c)}')" for d, c in chunk)
        update_sql = (
            "UPDATE discovered_companies dc "
            "SET is_blacklisted = TRUE, "
            "    blacklist_reason = 'smartlead_existing_contact:' || v.campaign, "
            "    updated_at = NOW() "
            f"FROM (VALUES {update_values}) AS v(domain, campaign) "
            f"WHERE dc.project_id = {project_id} "
            "  AND LOWER(dc.domain) = LOWER(v.domain) "
            "  AND dc.is_blacklisted = FALSE "
            "RETURNING dc.domain;"
        )
        upd = _psql("mcp", update_sql, timeout=600)
        if upd.returncode != 0:
            raise RuntimeError(
                f"UPDATE failed at batch {bnum}: {upd.stderr.strip()[:500]}"
            )
        chunk_updated = [ln.strip() for ln in upd.stdout.splitlines() if ln.strip()]
        updated_total += len(chunk_updated)

        # Step 2: INSERT hollow rows for unknown domains in this chunk.
        insert_values = ",".join(
            f"({project_id}, {company_id}, '{_esc(d)}', TRUE, "
            f"'smartlead_existing_contact:{_esc(c)}', NOW(), NOW())"
            for d, c in chunk
        )
        insert_sql = (
            "INSERT INTO discovered_companies "
            "(project_id, company_id, domain, is_blacklisted, blacklist_reason, "
            " created_at, updated_at) "
            f"VALUES {insert_values} "
            "ON CONFLICT (project_id, domain) DO NOTHING "
            "RETURNING domain;"
        )
        ins = _psql("mcp", insert_sql, timeout=600)
        if ins.returncode != 0:
            raise RuntimeError(
                f"INSERT failed at batch {bnum}: {ins.stderr.strip()[:500]}"
            )
        chunk_inserted = [ln.strip() for ln in ins.stdout.splitlines() if ln.strip()]
        inserted_total += len(chunk_inserted)
        print(
            f"  batch {bnum}/{n_batches}: +{len(chunk_updated)} updated, "
            f"+{len(chunk_inserted)} inserted"
        )

    return {"updated": updated_total, "inserted": inserted_total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default="onsocial",
        help=f"Project from PROJECT_REGISTRY. Known: {', '.join(sorted(PROJECT_REGISTRY))}.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    name = args.project.lower()
    if name not in PROJECT_REGISTRY:
        raise SystemExit(f"Unknown project {name!r}.")
    entry = PROJECT_REGISTRY[name]
    if "mcp" not in entry:
        raise SystemExit(f"Project {name!r} has no mcp target in registry.")

    mcp_pid = entry["mcp"]["project_id"]
    mcp_cid = entry["mcp"]["company_id"]
    prefix = entry["campaign_prefix"]
    print(f"Project: {name}  (mcp project_id={mcp_pid}, company_id={mcp_cid})")
    print(f"Campaign prefix: {prefix!r}")
    print(f"Container: {DB_TARGETS['mcp']['container']}\n")

    api_key = load_api_key()
    domains = collect_all_contact_domains(api_key, prefix)
    print(f"\nUnique domains across all campaigns: {len(domains)}")

    result = upsert_all_to_mcp(domains, mcp_pid, mcp_cid, dry_run=args.dry_run)
    if not args.dry_run:
        print(
            f"\nDone. UPDATED {result['updated']} existing rows, "
            f"INSERTED {result['inserted']} new hollow rows in project {mcp_pid}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
