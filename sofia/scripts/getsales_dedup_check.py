#!/usr/bin/env python3
"""
Compare ALL_CAMPAIGNS_scored.csv against GetSales dump.
Find leads already in GetSales (by LinkedIn nickname or email).
"""
import csv
import json
import re

GS_DUMP = "/tmp/gs_linkedin_set.json"
CSV_IN  = "/tmp/smartlead_export/ALL_CAMPAIGNS_scored.csv"
CSV_OUT_CLEAN    = "/tmp/smartlead_export/ALL_CAMPAIGNS_scored_deduped.csv"
CSV_OUT_DUPES    = "/tmp/smartlead_export/GS_DUPES.csv"


def extract_nickname(linkedin_url):
    """Extract slug from LinkedIn URL: /in/john-doe-123 -> john-doe-123"""
    if not linkedin_url:
        return ""
    url = linkedin_url.strip().lower().rstrip("/")
    m = re.search(r'/in/([^/?#]+)', url)
    return m.group(1).strip() if m else ""


def main():
    print("Loading GetSales dump...")
    with open(GS_DUMP) as f:
        gs_data = json.load(f)

    gs_linkedin = set(gs_data["linkedin"])   # nicknames, lowercase
    gs_email    = set(gs_data["email"])       # emails, lowercase
    gs_contacts = gs_data["contacts"]         # nickname -> {name, email, status}
    print(f"  GetSales: {len(gs_linkedin):,} LinkedIn, {len(gs_email):,} emails")

    print("Loading scored leads CSV...")
    with open(CSV_IN) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        leads = list(reader)
    print(f"  Scored leads: {len(leads)}")

    dupes = []
    clean = []

    for row in leads:
        li_url = row.get("linkedin_url", "")
        email  = (row.get("email") or "").lower().strip()
        nick   = extract_nickname(li_url)

        in_gs_li    = nick and (nick in gs_linkedin)
        in_gs_email = email and (email in gs_email)

        if in_gs_li or in_gs_email:
            # Find GetSales contact info
            gs_info = gs_contacts.get(nick, {})
            row["gs_match_by"]     = "linkedin" if in_gs_li else "email"
            row["gs_name"]         = gs_info.get("name", "")
            row["gs_email"]        = gs_info.get("email", "")
            row["gs_status"]       = gs_info.get("status", "")
            row["li_nickname"]     = nick
            dupes.append(row)
        else:
            clean.append(row)

    print(f"\nResults:")
    print(f"  Already in GetSales: {len(dupes)}")
    print(f"  Clean (not in GS):   {len(clean)}")

    if dupes:
        print("\nDuplicates found:")
        for d in dupes:
            print(f"  [{d['campaign_name']}] {d['email']} | {d['full_name']} | "
                  f"match_by={d['gs_match_by']} | gs_status={d.get('gs_status','?')}")

    # Write clean CSV
    with open(CSV_OUT_CLEAN, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean)
    print(f"\nClean CSV: {CSV_OUT_CLEAN} ({len(clean)} leads)")

    # Write dupes CSV
    dupe_fields = (fieldnames or []) + ["gs_match_by", "gs_name", "gs_email", "gs_status", "li_nickname"]
    with open(CSV_OUT_DUPES, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=dupe_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(dupes)
    print(f"Dupes CSV: {CSV_OUT_DUPES} ({len(dupes)} leads)")

    # Campaign breakdown
    from collections import Counter
    dupe_by_campaign = Counter(d["campaign_name"] for d in dupes)
    clean_by_campaign = Counter(c["campaign_name"] for c in clean)
    print("\nBreakdown by campaign:")
    for cname in ["INFPLAT_MENA_APAC", "INFPLAT_INDIA", "IMAGENCY_INDIA", "INDIA_GENERAL"]:
        total = dupe_by_campaign.get(cname, 0) + clean_by_campaign.get(cname, 0)
        print(f"  {cname}: {total} total | {dupe_by_campaign.get(cname,0)} in GS | {clean_by_campaign.get(cname,0)} clean")


if __name__ == "__main__":
    main()
