#!/usr/bin/env python3
"""
Audit all OnSocial SmartLead campaigns:
1. Export all leads from all OnSocial campaigns
2. Find duplicates (same email across campaigns)
3. Categorize by reply status
4. Cross-reference with blacklist
5. Find replied/interested leads still in active campaigns

Read-only — no modifications to SmartLead or blacklist.
"""

import csv
import json
import ssl
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5"
SSL_CTX = ssl._create_unverified_context()
RATE_PAUSE = 0.35

BLACKLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "input"
    / "campaign_blacklist.json"
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "OnSocial"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def api_get(endpoint, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}{endpoint}?{qs}"
    req = Request(url)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
    for attempt in range(3):
        try:
            with urlopen(req, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(RATE_PAUSE)
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5)
                continue
            raise


def api_post(endpoint, body=None, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}{endpoint}?{qs}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 SmartLead-CLI/1.0")
    for attempt in range(3):
        try:
            with urlopen(req, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                time.sleep(RATE_PAUSE)
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5)
                continue
            raise


def get_all_onsocial_campaigns():
    """Get all OnSocial campaigns."""
    data = api_get("/campaigns/", {"include_tags": "true"})
    camps = data if isinstance(data, list) else data.get("campaigns", [])
    return [c for c in camps if "onsocial" in c.get("name", "").lower()]


def fetch_leads_paginated(campaign_id):
    """Fetch all leads from a campaign with pagination."""
    all_leads = []
    offset = 0
    limit = 100
    while True:
        data = api_get(
            f"/campaigns/{campaign_id}/leads", {"offset": offset, "limit": limit}
        )
        if isinstance(data, dict):
            leads = data.get("data", [])
            total = int(data.get("total_leads", data.get("total", 0)))
        elif isinstance(data, list):
            leads = data
            total = len(data)
        else:
            break
        if not leads:
            break
        all_leads.extend(leads)
        if len(all_leads) >= total or len(leads) < limit:
            break
        offset += limit
    return all_leads


def extract_lead_info(item, campaign_name, campaign_id, campaign_status):
    """Extract normalized lead info."""
    lead = item.get("lead", item)
    cf = lead.get("custom_fields") or {}
    if isinstance(cf, str):
        try:
            cf = json.loads(cf)
        except Exception:
            cf = {}

    email = (lead.get("email") or "").strip().lower()
    domain = email.split("@")[1] if "@" in email else ""

    # Get job title from various fields
    job_title = ""
    for key in ("job_title", "title", "position", "designation", "Job Title", "Title"):
        val = cf.get(key) or lead.get(key)
        if val and str(val).strip():
            job_title = str(val).strip()
            break

    return {
        "email": email,
        "domain": domain,
        "first_name": lead.get("first_name", ""),
        "last_name": lead.get("last_name", ""),
        "company_name": lead.get("company_name", ""),
        "job_title": job_title,
        "lead_id": lead.get("id", ""),
        "campaign_lead_map_id": item.get("campaign_lead_map_id", ""),
        "status": item.get("status", lead.get("status", "")),
        "lead_category_id": item.get("lead_category_id", ""),
        "is_unsubscribed": lead.get("is_unsubscribed", False),
        "campaign_name": campaign_name,
        "campaign_id": campaign_id,
        "campaign_status": campaign_status,
        "linkedin": lead.get("linkedin_profile", "")
        or cf.get("linkedin_url", "")
        or cf.get("LinkedIn", ""),
    }


def load_blacklist():
    """Load campaign blacklist domains."""
    if BLACKLIST_PATH.exists():
        bl = json.loads(BLACKLIST_PATH.read_text())
        return set(bl.get("domains", []))
    return set()


def main():
    print("=" * 70)
    print("  OnSocial Lead Audit")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # 1. Get campaigns
    print("\n[1/5] Fetching OnSocial campaigns...")
    campaigns = get_all_onsocial_campaigns()
    active_camps = [c for c in campaigns if c.get("status", "").upper() == "ACTIVE"]
    print(f"  Total: {len(campaigns)} campaigns ({len(active_camps)} ACTIVE)")

    # 2. Fetch all leads
    print("\n[2/5] Fetching leads from all campaigns...")
    all_leads = []
    for i, camp in enumerate(campaigns):
        cid = camp["id"]
        cname = camp.get("name", f"#{cid}")
        cstatus = camp.get("status", "?")

        leads = fetch_leads_paginated(cid)
        for item in leads:
            info = extract_lead_info(item, cname, cid, cstatus)
            all_leads.append(info)

        print(
            f"  [{i + 1}/{len(campaigns)}] {cname[:50]:50s} | {cstatus:>10} | {len(leads):>5} leads"
        )

    print(f"\n  Total leads across all campaigns: {len(all_leads):,}")

    # 3. Find duplicates
    print("\n[3/5] Finding duplicates...")
    email_to_campaigns = defaultdict(list)
    for lead in all_leads:
        if lead["email"]:
            email_to_campaigns[lead["email"]].append(lead)

    duplicates = {
        email: leads for email, leads in email_to_campaigns.items() if len(leads) > 1
    }

    # Duplicates in ACTIVE campaigns specifically
    active_dupes = {}
    for email, leads in duplicates.items():
        active_leads = [l for l in leads if l["campaign_status"].upper() == "ACTIVE"]
        if len(active_leads) > 1:
            active_dupes[email] = active_leads

    print(f"  Unique emails: {len(email_to_campaigns):,}")
    print(f"  Emails in 2+ campaigns: {len(duplicates):,}")
    print(f"  Emails in 2+ ACTIVE campaigns: {len(active_dupes):,}")

    # 4. Categorize by reply status
    print("\n[4/5] Categorizing leads...")

    # SmartLead statuses: STARTED, INPROGRESS, COMPLETED, PAUSED, STOPPED
    # Categories we care about: replied, interested (positive), do-not-contact
    # lead_category_id mapping (from SmartLead):
    # 1 = Interested, 2 = Not Interested, 3 = Do Not Contact, etc.
    # Let's also check for 'is_replied' status

    # First, let's get categories
    try:
        categories = api_get("/leads/fetch-categories")
        print(f"  Lead categories: {json.dumps(categories, indent=2)[:500]}")
    except Exception as e:
        print(f"  Warning: could not fetch categories: {e}")
        categories = []

    # Classify leads
    replied_leads = [
        l for l in all_leads if l["status"] and "REPLIED" in str(l["status"]).upper()
    ]
    # Actually SmartLead uses lead_category_id for interest level
    # Let's group by status and category
    status_counts = defaultdict(int)
    category_counts = defaultdict(int)
    for l in all_leads:
        status_counts[l["status"]] += 1
        cat = l.get("lead_category_id", "")
        if cat:
            category_counts[cat] += 1

    print("\n  Lead statuses:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {status:>20s}: {count:>5}")

    print("\n  Lead categories (non-empty):")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    category_id={cat:>5}: {count:>5}")

    # CRITICAL: find leads that replied / have meetings but are ALSO in active campaigns
    # We need to check message history for replied leads
    # But that would be too many API calls. Instead, let's use the data we have.

    # Approach: find emails where at least one instance has replied/interested status
    # AND at least one instance is in an ACTIVE campaign with STARTED/INPROGRESS status
    dangerous_leads = []
    for email, leads in email_to_campaigns.items():
        has_replied = any(
            l["status"]
            and (
                "REPLIED" in str(l["status"]).upper()
                or "REPLY" in str(l["status"]).upper()
            )
            for l in leads
        )
        has_interested = any(
            str(l.get("lead_category_id", ""))
            in ("1", "6", "7")  # common interested category IDs
            for l in leads
        )
        has_do_not_contact = any(
            str(l.get("lead_category_id", "")) in ("3",) for l in leads
        )

        # Is this email still active in some campaign?
        active_in_progress = [
            l
            for l in leads
            if l["campaign_status"].upper() == "ACTIVE"
            and l["status"] in ("STARTED", "INPROGRESS", "IN_PROGRESS")
        ]

        if (has_replied or has_interested or has_do_not_contact) and active_in_progress:
            dangerous_leads.append(
                {
                    "email": email,
                    "replied": has_replied,
                    "interested": has_interested,
                    "do_not_contact": has_do_not_contact,
                    "active_campaigns": [
                        (l["campaign_name"], l["campaign_id"], l["status"])
                        for l in active_in_progress
                    ],
                    "all_campaigns": [
                        (
                            l["campaign_name"],
                            l["campaign_id"],
                            l["status"],
                            str(l.get("lead_category_id", "")),
                        )
                        for l in leads
                    ],
                }
            )

    print(
        f"\n  DANGEROUS: {len(dangerous_leads)} leads replied/interested but still active in other campaigns!"
    )

    # 5. Cross-reference with blacklist
    print("\n[5/5] Cross-referencing with blacklist...")
    bl_domains = load_blacklist()
    print(f"  Blacklist domains: {len(bl_domains):,}")

    # Find leads whose domain IS in blacklist but they're still in active campaigns
    bl_bypass = []
    for lead in all_leads:
        if lead["campaign_status"].upper() == "ACTIVE" and lead["domain"] in bl_domains:
            bl_bypass.append(lead)

    print(f"  Leads in ACTIVE campaigns with blacklisted domain: {len(bl_bypass)}")

    # Find replied lead domains NOT in blacklist
    replied_domains_missing = set()
    for email, leads in email_to_campaigns.items():
        has_replied = any(
            l["status"] and "REPLIED" in str(l["status"]).upper() for l in leads
        )
        if has_replied:
            for l in leads:
                if l["domain"] and l["domain"] not in bl_domains:
                    replied_domains_missing.add(l["domain"])

    print(f"  Replied lead domains NOT in blacklist: {len(replied_domains_missing)}")

    # ============================================================
    # OUTPUT REPORTS
    # ============================================================
    today = datetime.now().strftime("%Y-%m-%d")

    # Report 1: All leads master export
    master_path = OUTPUT_DIR / f"OS_Audit_AllLeads_{today}.csv"
    fields = [
        "email",
        "domain",
        "first_name",
        "last_name",
        "company_name",
        "job_title",
        "status",
        "lead_category_id",
        "campaign_name",
        "campaign_id",
        "campaign_status",
        "lead_id",
        "linkedin",
        "is_unsubscribed",
    ]
    with open(master_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_leads)
    print(f"\n  Saved: {master_path.name} ({len(all_leads)} rows)")

    # Report 2: Duplicates
    dupes_path = OUTPUT_DIR / f"OS_Audit_Duplicates_{today}.csv"
    dupe_rows = []
    for email, leads in sorted(duplicates.items()):
        for l in leads:
            row = dict(l)
            row["dupe_count"] = len(leads)
            row["in_active_campaigns"] = sum(
                1 for x in leads if x["campaign_status"].upper() == "ACTIVE"
            )
            dupe_rows.append(row)
    dupe_fields = fields + ["dupe_count", "in_active_campaigns"]
    with open(dupes_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=dupe_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(dupe_rows)
    print(
        f"  Saved: {dupes_path.name} ({len(dupe_rows)} rows, {len(duplicates)} unique emails)"
    )

    # Report 3: Dangerous leads (replied but still active)
    danger_path = OUTPUT_DIR / f"OS_Audit_Dangerous_{today}.csv"
    danger_rows = []
    for d in dangerous_leads:
        danger_rows.append(
            {
                "email": d["email"],
                "replied": d["replied"],
                "interested": d["interested"],
                "do_not_contact": d["do_not_contact"],
                "active_campaigns": " | ".join(
                    f"{name} (id={cid}, status={s})"
                    for name, cid, s in d["active_campaigns"]
                ),
                "all_campaigns": " | ".join(
                    f"{name} (id={cid}, status={s}, cat={cat})"
                    for name, cid, s, cat in d["all_campaigns"]
                ),
            }
        )
    with open(danger_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "email",
                "replied",
                "interested",
                "do_not_contact",
                "active_campaigns",
                "all_campaigns",
            ],
        )
        w.writeheader()
        w.writerows(danger_rows)
    print(f"  Saved: {danger_path.name} ({len(danger_rows)} rows)")

    # Report 4: Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total campaigns:     {len(campaigns)}")
    print(f"  Active campaigns:    {len(active_camps)}")
    print(f"  Total leads:         {len(all_leads):,}")
    print(f"  Unique emails:       {len(email_to_campaigns):,}")
    print(f"  Duplicates:          {len(duplicates):,} emails in 2+ campaigns")
    print(f"  Active dupes:        {len(active_dupes):,} emails in 2+ ACTIVE campaigns")
    print(
        f"  DANGEROUS:           {len(dangerous_leads)} (replied/interested but still getting emails)"
    )
    print(f"  Blacklist domains:   {len(bl_domains):,}")
    print(
        f"  BL bypass (active):  {len(bl_bypass)} leads in active camps with blacklisted domain"
    )
    print(
        f"  Missing from BL:     {len(replied_domains_missing)} replied domains not in blacklist"
    )
    print()

    if dangerous_leads:
        print(
            "  TOP DANGEROUS LEADS (replied/interested but still in active campaigns):"
        )
        for d in dangerous_leads[:20]:
            flags = []
            if d["replied"]:
                flags.append("REPLIED")
            if d["interested"]:
                flags.append("INTERESTED")
            if d["do_not_contact"]:
                flags.append("DNC")
            active = [f"{name[:30]}" for name, _, _ in d["active_campaigns"]]
            print(
                f"    {d['email']:40s} [{', '.join(flags)}] → still in: {', '.join(active)}"
            )
        if len(dangerous_leads) > 20:
            print(f"    ... and {len(dangerous_leads) - 20} more")

    if active_dupes:
        print("\n  TOP DUPLICATES IN ACTIVE CAMPAIGNS:")
        for email, leads in list(active_dupes.items())[:15]:
            camps = [f"{l['campaign_name'][:30]} ({l['status']})" for l in leads]
            print(f"    {email:40s} → {', '.join(camps)}")
        if len(active_dupes) > 15:
            print(f"    ... and {len(active_dupes) - 15} more")


if __name__ == "__main__":
    main()
