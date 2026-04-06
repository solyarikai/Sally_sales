#!/usr/bin/env python3.11
"""
Segment new leads from OS | Leads | IMAGENCY — 2026-03-28
- Classifies companies: IMAGENCY / INFPLAT / OTHER
- Filters irrelevant titles
- Assigns DM clusters within IMAGENCY (FOUNDERS_CSUITE / CREATIVE_LEADERSHIP / ACCOUNT_OPS)
- Saves two sheets to Google Sheets
"""

import sys
import asyncio
import json
import os
from collections import Counter

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../.claude/mcp/google-sheets")
)
from server import (
    sheets_read_range,
    ReadRangeInput,
    sheets_create_spreadsheet,
    CreateSpreadsheetInput,
)
from server import (
    sheets_write_range,
    WriteRangeInput,
)

SOURCE_SHEET_ID = "1HrYSGsi43EwcybPz5BhVyM18tXwc3H3fFSZHck4kqeE"
TODAY = "2026-04-06"

# ══════════════════════════════════════════════════════════════
# COMPANY SEGMENT CLASSIFICATION
# ══════════════════════════════════════════════════════════════

COMPANY_SEGMENTS = {
    # IMAGENCY — IM-first agencies / agencies with strong influencer practice
    "Mindshare": "IMAGENCY",
    "VaynerMedia": "IMAGENCY",
    "Acceleration Partners": "IMAGENCY",
    "NewGen": "IMAGENCY",
    "Digital Voices": "IMAGENCY",
    "Born Social": "IMAGENCY",
    "Ear to the Ground": "IMAGENCY",
    "PrettyGreen": "IMAGENCY",
    "Fifty": "IMAGENCY",
    "Kaplow": "IMAGENCY",
    "Chtrbox": "IMAGENCY",
    "Flightstory": "IMAGENCY",
    # INFPLAT — Influencer platforms / SaaS tools
    "Influential": "INFPLAT",
    "IZEA": "INFPLAT",
    "#Paid": "INFPLAT",
    "Glewee | All-In-One Influencer Marketing Platform": "INFPLAT",
    "Glewee": "INFPLAT",
    "LTK": "INFPLAT",
    "CreatorDB": "INFPLAT",
    "Launchmetrics": "INFPLAT",
    "Meltwater": "INFPLAT",
    "Spotter": "INFPLAT",
    "Jellysmack": "INFPLAT",
    "Lumanu": "INFPLAT",
    "Heepsy": "INFPLAT",
    "Julius by Triller": "INFPLAT",
    "Breakr": "INFPLAT",
    # OTHER — irrelevant
    "Kantar": "OTHER",
    "inDrive": "OTHER",
    "Patreon": "OTHER",
    "Cognizant": "OTHER",
    "Dovetail": "OTHER",
    "PFR Group": "OTHER",
}

# ══════════════════════════════════════════════════════════════
# TITLE EXCLUSION — clearly not decision-makers
# ══════════════════════════════════════════════════════════════

EXCLUDED_TITLE_PATTERNS = [
    "talent acquisition",
    "recruiter",
    "recruiting",
    "hr ",
    "people partner",
    "technical business partner",
    "software engineer",
    "data engineer",
    "director of engineering",
    "head of engineering",
    "director of software",
    "senior director of software",
    "senior director of engineering",
    "director of data engineering",
    "vp, analytics engineering",
    "analytics engineering",
    "head of data engineering",
    "franchise owner",  # inDrive
    "executive assistant",
    "ea to ceo",
    "senior associate",  # Cognizant
    "intern",
    "assistant",
    "coordinator",
    "junior",
    "chief of staff to coo",  # operational, not a buyer
    "talent management partner",
    "head of global product policy",
    "head of payments",
    "resume writer",
    "director of private charitable",
    "adviser to ceo",  # not a buyer
    "client servicing & influencer relations at chtrbox | aspiring",  # student-level title
    "svp, enterprise sales",  # sales person, not a buyer
    "research strategist - the diary",  # niche content role
]


def is_excluded(title: str) -> bool:
    t = title.lower().strip()
    for pattern in EXCLUDED_TITLE_PATTERNS:
        if pattern in t:
            return True
    return False


# ══════════════════════════════════════════════════════════════
# DM CLUSTER CLASSIFICATION (for IMAGENCY)
# ══════════════════════════════════════════════════════════════

FOUNDERS_PATTERNS = [
    "ceo",
    "founder",
    "co-founder",
    "cofounder",
    "president",
    "owner",
    "managing partner",
    "senior partner",
    "managing director",
    "general manager",
    "chief executive",
    "chief operating",
    "chief product",
    "chief technology",
    "chief commercial",
    "chief strategy",
    "chief marketing",
    "coo",
    "cto",
    "cmo",
    "cpo",
    "cso",
    "executive director",
    "svp",
    "senior vice president",
    "vp,",
    "vice president",
    "partner",
]

CREATIVE_PATTERNS = [
    "creative director",
    "executive creative",
    "associate creative",
    "head of creative",
    "chief creative",
    "creative strategy",  # head/director level
    "head of brand strategy",
    "global head of creative",
]

ACCOUNT_OPS_PATTERNS = [
    "account director",
    "business director",
    "client service",
    "head of strategy",
    "head of operations",
    "head of account",
    "head of partnerships",
    "head of influencer",
    "director, client",
    "director of client",
    "vp, client",
    "vp, growth",
    "strategic partnerships director",
    "global account director",
    "director, brand partnerships",
    "director, creator",
    "director of influencer",
    "influencer director",
    "talent director",
    "head of talent",
    "associate influencer director",
    "director, co-founder",  # borderline - treated as FOUNDERS below
]


def classify_dm_cluster(title: str) -> str:
    t = title.lower().strip()

    # Creative first (most specific)
    for pattern in CREATIVE_PATTERNS:
        if pattern in t:
            return "CREATIVE_LEADERSHIP"

    # Founders/C-Suite
    for pattern in FOUNDERS_PATTERNS:
        if pattern in t:
            return "FOUNDERS_CSUITE"

    # Account/Ops
    for pattern in ACCOUNT_OPS_PATTERNS:
        if pattern in t:
            return "ACCOUNT_OPS"

    # Fallback: if it has "director" or "head of" it's probably account ops
    if "director" in t or "head of" in t:
        return "ACCOUNT_OPS"

    return "FOUNDERS_CSUITE"  # default for unclassified senior titles


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════


async def main():
    print("Reading source sheet...")
    raw = await sheets_read_range(
        ReadRangeInput(
            spreadsheet_id=SOURCE_SHEET_ID, range="Sheet1!A1:Z1000", as_json=True
        )
    )
    data = json.loads(raw)
    rows = data["values"]
    print(f"Total rows: {len(rows)}")

    imagency_rows = []
    infplat_rows = []
    other_rows = []
    excluded_title_rows = []

    for row in rows:
        company = row.get("Company", "").strip()
        title = row.get("Title", "").strip()
        name = row.get("Name", "").strip()
        email = row.get("Email", "").strip()
        location = row.get("Location", "").strip()
        profile_url = row.get("Profile URL", "").strip()
        verified = row.get("Verified", "").strip()

        segment = COMPANY_SEGMENTS.get(company, "OTHER")

        if segment == "OTHER":
            other_rows.append(row)
            continue

        if is_excluded(title):
            excluded_title_rows.append(
                {**row, "segment": segment, "exclusion_reason": "title"}
            )
            continue

        first_name = name.split()[0] if name else ""
        last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

        base = {
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company,
            "job_title": title,
            "email": email,
            "linkedin_profile": profile_url,
            "location": location,
            "verified": verified,
        }

        if segment == "IMAGENCY":
            dm_cluster = classify_dm_cluster(title)
            imagency_rows.append({**base, "dm_cluster": dm_cluster})
        elif segment == "INFPLAT":
            infplat_rows.append(base)

    # ── Stats ──
    print("\n--- Results ---")
    print(f"IMAGENCY:       {len(imagency_rows)}")
    print(f"INFPLAT:        {len(infplat_rows)}")
    print(f"OTHER (skip):   {len(other_rows)}")
    print(f"Excluded title: {len(excluded_title_rows)}")

    if imagency_rows:
        dm_counts = Counter(r["dm_cluster"] for r in imagency_rows)
        print("\nIMAGENCY DM clusters:")
        for k, v in dm_counts.items():
            print(f"  {k}: {v}")

    # ── Write IMAGENCY sheet ──
    imagency_sheet_name = f"OS | Leads | IMAGENCY_NEW — {TODAY}"
    print(f"\nCreating sheet: {imagency_sheet_name}")
    imagency_cols = [
        "first_name",
        "last_name",
        "company_name",
        "job_title",
        "email",
        "linkedin_profile",
        "location",
        "dm_cluster",
        "verified",
    ]
    await write_to_new_sheet(imagency_sheet_name, imagency_rows, imagency_cols)

    # ── Write INFPLAT sheet ──
    infplat_sheet_name = f"OS | Leads | INFPLAT_NEW — {TODAY}"
    print(f"Creating sheet: {infplat_sheet_name}")
    infplat_cols = [
        "first_name",
        "last_name",
        "company_name",
        "job_title",
        "email",
        "linkedin_profile",
        "location",
        "verified",
    ]
    await write_to_new_sheet(infplat_sheet_name, infplat_rows, infplat_cols)

    print("\nDone.")


async def write_to_new_sheet(name: str, rows: list, cols: list):
    if not rows:
        print(f"  Skipped (0 rows): {name}")
        return

    result_raw = await sheets_create_spreadsheet(CreateSpreadsheetInput(title=name))
    result = json.loads(result_raw)
    sheet_id = result["spreadsheet_id"]

    # Build values: header + data
    header = cols
    data_rows = [[r.get(c, "") for c in cols] for r in rows]
    all_values = [header] + data_rows

    await sheets_write_range(
        WriteRangeInput(spreadsheet_id=sheet_id, range="Sheet1!A1", values=all_values)
    )
    print(f"  Wrote {len(rows)} rows → {name} ({sheet_id})")
    print(f"  https://docs.google.com/spreadsheets/d/{sheet_id}/edit")


if __name__ == "__main__":
    asyncio.run(main())
