#!/usr/bin/env python3
"""
Sheets sync — append fresh leads to master spreadsheet SL/GS tabs + update Analytics.

Reads local CSVs produced by pipeline's findymail step:
  - leads_with_email_{SEG}_{DATE}.csv    → SL {SEG} tab (14-col SmartLead format)
  - GetSales — {SEG}_without_email — {DD.MM}.csv → GS {SEG} tab (49-col GetSales format)

Then recalculates the Analytics tab:
  1. Lead counts (SL/GS/Total per segment)
  2. Title breakdown (FOUNDERS/HEAD/TECHLEAD/ACCOUNT_OPS/Other)
  3. Top countries per segment

Usage:
    python3 05_sheets_sync.py --date 2026-04-17 [--segments IMAGENCY,INFPLAT,SOCCOM,AFFPERF]
"""

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent
REPO_DIR = SOFIA_DIR.parent

MASTER_SHEET_ID = "1MK_ynBiUumk5NCRksQGvwEVBMi4G9iB5-i416lgrOEA"

SL_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "company_name",
    "website",
    "linkedin_url",
    "phone_number",
    "location",
    "title",
    "custom1",
    "custom2",
    "custom3",
    "custom4",
    "custom5",
]

GS_COLUMNS = [
    "system_uuid",
    "pipeline_stage",
    "full_name",
    "first_name",
    "last_name",
    "position",
    "headline",
    "about",
    "linkedin_id",
    "sales_navigator_id",
    "linkedin_nickname",
    "linkedin_url",
    "facebook_nickname",
    "twitter_nickname",
    "work_email",
    "personal_email",
    "work_phone",
    "personal_phone",
    "connections_number",
    "followers_number",
    "primary_language",
    "has_open_profile",
    "has_verified_profile",
    "has_premium",
    "location_country",
    "location_state",
    "location_city",
    "active_flows",
    "list_name",
    "tags",
    "company_name",
    "company_industry",
    "company_linkedin_id",
    "company_domain",
    "company_linkedin_url",
    "company_employees_range",
    "company_headquarter",
    "cf_location",
    "cf_competitor_client",
    "cf_message1",
    "cf_message2",
    "cf_message3",
    "cf_personalization",
    "cf_compersonalization",
    "cf_personalization1",
    "cf_message4",
    "cf_linkedin_personalization",
    "cf_subject",
    "created_at",
]


def _get_gsheets_creds() -> Path:
    candidates = [
        Path.home() / ".claude/google-sheets/token.json",
        SCRIPT_DIR.parent.parent / ".claude/mcp/google-sheets/token.json",
        Path.home() / "magnum-opus-project/repo/sofia/.google-sheets/token.json",
        SOFIA_DIR / ".google-sheets" / "token.json",
        SOFIA_DIR.parent / "sofia" / ".google-sheets" / "token.json",
        Path(os.environ.get("GOOGLE_SHEETS_TOKEN", "")),
    ]
    for p in candidates:
        if p and p.exists():
            return p
    print("  ✗ token.json not found. Candidates tried:")
    for p in candidates:
        print(f"    - {p}")
    sys.exit(1)


def _sheets_services():
    token_path = _get_gsheets_creds()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    sheets = build("sheets", "v4", credentials=creds).spreadsheets()
    return sheets


def _append_rows(sheets, sheet_id: str, tab_name: str, rows: list[list]):
    if not rows:
        return 0
    sheets.values().append(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(rows)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _map_to_sl(contact: dict, segment: str) -> list:
    """Map pipeline contact dict → SL 14-col format."""
    location = contact.get("company_country", "") or contact.get("country", "")
    return [
        contact.get("first_name", ""),
        contact.get("last_name", ""),
        contact.get("email", ""),
        contact.get("company_name", ""),
        contact.get("domain", ""),
        contact.get("linkedin_url", ""),
        "",  # phone_number
        location,
        contact.get("title", ""),
        "",  # custom1
        "",  # custom2
        "",  # custom3
        "",  # custom4
        segment,  # custom5
    ]


def _map_to_gs(gs_row: dict) -> list:
    """GetSales CSV is already in 49-col format — just project to column list."""
    return [gs_row.get(col, "") for col in GS_COLUMNS]


FOUNDER_KW = [
    "ceo",
    "co-founder",
    "cofounder",
    "co founder",
    "founder",
    " owner",
    "president",
    "managing director",
    "general manager",
    "managing partner",
]
TECHLEAD_KW = [
    "cto",
    "cpo",
    "cio",
    "vp engineering",
    "vp of engineering",
    "head of engineering",
    "head of product",
    "head of technology",
    "head of tech",
    "tech lead",
    "technical lead",
    "lead developer",
    "vp technology",
    "vp of technology",
    "vp product",
    "vp of product",
    "chief technology",
    "chief product",
    "technical director",
    "technology director",
]
ACCOUNT_OPS_KW = [
    "coo",
    "cmo",
    "cfo",
    "cco",
    "cro",
    "account manager",
    "account director",
    "client success",
    "customer success",
    "head of operations",
    "head of partnerships",
    "operations",
    "partnerships",
    "bizdev",
    "biz dev",
    "chief operating",
    "chief marketing",
    "chief financial",
    "chief revenue",
    "chief commercial",
]
HEAD_KW = [
    "svp",
    "evp",
    " vp ",
    "vp,",
    "vp of",
    "director",
    "head of",
    "senior manager",
]


def classify_title(title: str) -> str:
    if not title:
        return "Other"
    t = f" {title.lower()} "
    if any(k in t for k in FOUNDER_KW):
        return "FOUNDERS"
    if any(k in t for k in TECHLEAD_KW):
        return "TECHLEAD"
    if any(k in t for k in ACCOUNT_OPS_KW):
        return "ACCOUNT_OPS"
    if any(k in t for k in HEAD_KW):
        return "HEAD"
    return "Other"


def _read_tab_rows(sheets, sheet_id: str, tab_name: str) -> list[list]:
    try:
        res = (
            sheets.values()
            .get(spreadsheetId=sheet_id, range=f"{tab_name}!A:AX")
            .execute()
        )
        return res.get("values", [])
    except Exception as e:
        print(f"  ⚠ Read {tab_name} failed: {e}")
        return []


def _update_analytics(sheets, sheet_id: str, segments: list[str]):
    print("\n  Обновляю Analytics…")

    sl_data = {seg: _read_tab_rows(sheets, sheet_id, f"SL {seg}") for seg in segments}
    gs_data = {seg: _read_tab_rows(sheets, sheet_id, f"GS {seg}") for seg in segments}

    counts = []
    title_matrix = {
        "FOUNDERS": {},
        "HEAD": {},
        "TECHLEAD": {},
        "ACCOUNT_OPS": {},
        "Other": {},
    }
    country_tops = {}

    for seg in segments:
        sl_rows = sl_data[seg][1:] if len(sl_data[seg]) > 1 else []
        gs_rows = gs_data[seg][1:] if len(gs_data[seg]) > 1 else []

        sl_count = len(sl_rows)
        gs_count = len(gs_rows)
        counts.append((seg, sl_count, gs_count, sl_count + gs_count))

        # Title idx: SL col 8 (title), GS col 5 (position)
        title_counter = Counter()
        for r in sl_rows:
            t = r[8] if len(r) > 8 else ""
            title_counter[classify_title(t)] += 1
        for r in gs_rows:
            t = r[5] if len(r) > 5 else ""
            title_counter[classify_title(t)] += 1

        for bucket in title_matrix:
            title_matrix[bucket][seg] = title_counter.get(bucket, 0)

        # Country: SL col 7 (location), GS col 37 (cf_location)
        country_counter = Counter()
        for r in sl_rows:
            c = (r[7] if len(r) > 7 else "").strip()
            if c:
                country_counter[c] += 1
        for r in gs_rows:
            c = (r[37] if len(r) > 37 else "").strip()
            if c:
                country_counter[c] += 1
        country_tops[seg] = country_counter.most_common(5)

    # Write Analytics
    today = datetime.now().strftime("%Y-%m-%d")

    values = [[f"ANALYTICS — OS | All Segments — {today}"], []]

    # Section 1: Lead Counts
    values.append(["1. LEAD COUNTS"])
    values.append(["Segment", "SmartLead", "GetSales", "Total"])
    total_sl = total_gs = total_all = 0
    for seg, sl_c, gs_c, tot in counts:
        values.append([seg, sl_c, gs_c, tot])
        total_sl += sl_c
        total_gs += gs_c
        total_all += tot
    values.append(["TOTAL", total_sl, total_gs, total_all])
    values.extend([[], [], []])

    # Section 2: Title breakdown
    values.append(["2. TITLE / ROLE BREAKDOWN"])
    header = ["Group"]
    for seg in segments:
        header.extend([seg, "%"])
    header.extend(["TOTAL", "%"])
    values.append(header)

    seg_totals = {
        seg: sum(title_matrix[b][seg] for b in title_matrix) for seg in segments
    }
    grand_total = sum(seg_totals.values())

    for bucket in ["FOUNDERS", "HEAD", "TECHLEAD", "ACCOUNT_OPS", "Other"]:
        row = [bucket]
        bucket_total = 0
        for seg in segments:
            cnt = title_matrix[bucket][seg]
            seg_tot = seg_totals[seg] or 1
            row.extend([cnt, f"{cnt / seg_tot * 100:.1f}%"])
            bucket_total += cnt
        row.extend([bucket_total, f"{bucket_total / (grand_total or 1) * 100:.1f}%"])
        values.append(row)

    row = ["TOTAL"]
    for seg in segments:
        row.extend([seg_totals[seg], "100%"])
    row.extend([grand_total, "100%"])
    values.append(row)
    values.extend([[], []])

    # Section 2 definitions
    values.append(["Group definitions:"])
    values.append(
        [
            "FOUNDERS",
            "CEO, Co-Founder, Founder, Owner, President, Managing Director, General Manager, Managing Partner",
        ]
    )
    values.append(
        [
            "HEAD",
            "VP, SVP, EVP, Director, Head of [any], Senior Manager, Lead (generic)",
        ]
    )
    values.append(
        [
            "TECHLEAD",
            "CTO, CPO, CIO, VP/Head of Engineering/Product/Tech, Tech Lead, Lead Developer",
        ]
    )
    values.append(
        [
            "ACCOUNT_OPS",
            "COO, CMO, CFO, CCO, CRO, Account Manager/Director, Client Success, Operations, Partnerships, BizDev",
        ]
    )
    values.extend([[], [], []])

    # Section 3: Top countries (side by side)
    header_row = []
    for seg in segments:
        header_row.extend([f"{seg} — топ стран:", "", "", ""])
    values.append(header_row)

    max_tops = max(len(country_tops[seg]) for seg in segments) if segments else 0
    for i in range(max_tops):
        row = []
        for seg in segments:
            tops = country_tops[seg]
            if i < len(tops):
                row.extend([tops[i][0], tops[i][1], "", ""])
            else:
                row.extend(["", "", "", ""])
        values.append(row)

    # Clear old Analytics, write new
    sheets.values().clear(spreadsheetId=sheet_id, range="Analytics!A1:Z200").execute()
    sheets.values().update(
        spreadsheetId=sheet_id,
        range="Analytics!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    print("  ✓ Analytics обновлён")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--segments", default="IMAGENCY,INFPLAT,SOCCOM,AFFPERF")
    ap.add_argument("--sheet-id", default=MASTER_SHEET_ID)
    ap.add_argument("--skip-analytics", action="store_true")
    args = ap.parse_args()

    segments = [s.strip().upper() for s in args.segments.split(",") if s.strip()]
    date = args.date
    dd_mm = datetime.strptime(date, "%Y-%m-%d").strftime("%d_%m")
    dd_dot_mm = dd_mm.replace("_", ".")

    pipeline_dir = SOFIA_DIR / "output" / "OnSocial" / "pipeline"
    gs_dir = SOFIA_DIR.parent / "sofia" / "get_sales_hub" / dd_mm
    # Fallback: when invoked from sales_engineer local path
    if not gs_dir.exists():
        gs_dir = SOFIA_DIR / "get_sales_hub" / dd_mm

    print(f"\n  Master sheet: {args.sheet_id}")
    print(f"  Date: {date}")
    print(f"  Segments: {', '.join(segments)}")
    print(f"  Pipeline dir: {pipeline_dir}")
    print(f"  GetSales dir: {gs_dir}\n")

    sheets = _sheets_services()

    # Append to SL/GS tabs
    for seg in segments:
        sl_csv = pipeline_dir / f"leads_with_email_{seg}_{date}.csv"
        gs_csv = gs_dir / f"GetSales — {seg}_without_email — {dd_dot_mm}.csv"

        sl_contacts = _read_csv(sl_csv)
        gs_contacts = _read_csv(gs_csv)

        sl_rows = [_map_to_sl(c, seg) for c in sl_contacts]
        gs_rows = [_map_to_gs(c) for c in gs_contacts]

        appended_sl = _append_rows(sheets, args.sheet_id, f"SL {seg}", sl_rows)
        appended_gs = _append_rows(sheets, args.sheet_id, f"GS {seg}", gs_rows)
        print(f"  {seg}: SL +{appended_sl} | GS +{appended_gs}")

    # Update Analytics
    if not args.skip_analytics:
        _update_analytics(sheets, args.sheet_id, segments)

    print("\n  ✓ Done.\n")


if __name__ == "__main__":
    main()
