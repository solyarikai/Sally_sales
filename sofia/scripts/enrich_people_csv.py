#!/usr/bin/env python3.11
"""
Enrich OS_People_*.csv files:
- normalize all columns
- assign social_proof by company_country
- save enriched CSV locally + Google Sheets

Usage: python3.11 sofia/scripts/enrich_people_csv.py
"""

import csv
import os
import sys
from datetime import date
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent.parent
INPUT_DIR = REPO_DIR / "sofia" / "input"
TODAY = date.today().strftime("%Y-%m-%d")

# ── Social proof tables ───────────────────────────────────────────────────────

SOCIAL_PROOF = {
    "INFPLAT": {
        "United Kingdom": "Whalar, InfluencerUK, LADbible, and Billion Dollar Boy",
        "Germany": "Zalando, Linkster, Intermate, and Gocomo",
        "France": "Kolsquare, Skeepers, Ykone, and Favikon",
        "India": "Phyllo, KlugKlug, Qoruz, and Tonic Worldwide",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "United States": "Modash, Captiv8, and Lefty",
        "Canada": "Modash, Captiv8, and Lefty",
        "Brazil": "Modash and Captiv8",
        "Mexico": "Modash and Captiv8",
        "_default": "Modash, Captiv8, and Lefty",
    },
    "IMAGENCY": {
        "United Kingdom": "Whalar, InfluencerUK, LADbible, and Billion Dollar Boy",
        "Germany": "Zalando, Linkster, Intermate, and Gocomo",
        "France": "Kolsquare, Skeepers, Ykone, and Favikon",
        "India": "Phyllo, KlugKlug, Qoruz, and Tonic Worldwide",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "United States": "Viral Nation and Obviously",
        "Canada": "Viral Nation and Obviously",
        "Brazil": "Viral Nation and Captiv8",
        "Mexico": "Viral Nation and Captiv8",
        "_default": "Viral Nation and Obviously",
    },
    "SOCCOM": {
        "_default": "LTK, ShopMy, and Bazaarvoice",
    },
}

# ── Column mapping ────────────────────────────────────────────────────────────

COLUMN_MAP = {
    "first_name": ["First Name", "first_name"],
    "last_name": ["Last Name", "last_name"],
    "email": ["Email", "email", "Email Address"],
    "title": ["Title", "title", "Job Title"],
    "company_name": ["Company Name", "Company", "company", "Organization Name"],
    "company_name_for_emails": ["Company Name for Emails", "company_name_for_emails"],
    "domain": ["Website", "website", "Company Domain", "domain", "Domain"],
    "linkedin_url": [
        "Person Linkedin Url",
        "LinkedIn URL",
        "linkedin_url",
        "Person LinkedIn URL",
    ],
    "company_linkedin_url": ["Company Linkedin Url", "Company LinkedIn URL"],
    "country": ["Country", "country", "Person Country"],
    "company_country": ["Company Country", "company_country"],
    "city": ["City", "city", "Person City"],
    "employees": ["# Employees", "employees", "Number of Employees"],
    "industry": ["Industry", "industry"],
    "seniority": ["Seniority", "seniority"],
    "phone": ["Mobile Phone", "Phone", "phone"],
    "secondary_email": ["Secondary Email", "secondary_email"],
    "keywords": ["Keywords", "keywords"],
}


def _get(row: dict, field: str) -> str:
    for col in COLUMN_MAP.get(field, [field]):
        if col in row and str(row[col]).strip():
            return str(row[col]).strip()
    return ""


def _normalize_domain(raw: str) -> str:
    d = raw.strip().lower()
    for prefix in ["https://", "http://", "www."]:
        if d.startswith(prefix):
            d = d[len(prefix) :]
    return d.rstrip("/").split("/")[0]


def _normalize_company(name: str) -> str:
    if not name:
        return ""
    for suffix in [
        ", Inc.",
        " Inc.",
        ", LLC",
        " LLC",
        ", Ltd.",
        " Ltd.",
        " Limited",
        " GmbH",
        " S.A.",
        " B.V.",
        " AG",
        " SAS",
        " SRL",
    ]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip().strip(",").strip()


def get_social_proof(country: str, segment: str) -> str:
    table = SOCIAL_PROOF.get(segment, {})
    return table.get(country, table.get("_default", ""))


def enrich_csv(input_path: Path, segment: str) -> list[dict]:
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    enriched = []
    skipped = 0
    for row in rows:
        email = _get(row, "email")
        if not email or "@" not in email:
            skipped += 1
            continue

        domain_raw = _get(row, "domain") or email.split("@")[-1]
        domain = _normalize_domain(domain_raw)
        company_country = _get(row, "company_country") or _get(row, "country")

        enriched.append(
            {
                "first_name": _get(row, "first_name"),
                "last_name": _get(row, "last_name"),
                "email": email,
                "title": _get(row, "title"),
                "company_name": _normalize_company(_get(row, "company_name")),
                "company_name_for_emails": _get(row, "company_name_for_emails"),
                "domain": domain,
                "segment": segment,
                "linkedin_url": _get(row, "linkedin_url"),
                "company_linkedin_url": _get(row, "company_linkedin_url"),
                "country": _get(row, "country"),
                "city": _get(row, "city"),
                "company_country": company_country,
                "employees": _get(row, "employees"),
                "industry": _get(row, "industry"),
                "seniority": _get(row, "seniority"),
                "phone": _get(row, "phone"),
                "secondary_email": _get(row, "secondary_email"),
                "social_proof": get_social_proof(company_country, segment),
            }
        )

    print(
        f"  Rows: {len(rows)} total → {len(enriched)} with email, {skipped} skipped (no email)"
    )
    return enriched


def save_csv(rows: list[dict], path: Path):
    if not rows:
        print("  No rows to save")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved: {path} ({len(rows)} rows)")


def upload_to_sheets(rows: list[dict], sheet_name: str):
    try:
        sys.path.insert(0, str(REPO_DIR / "magnum-opus"))
        os.chdir(REPO_DIR / "magnum-opus")
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        token_path = REPO_DIR / "magnum-opus" / "infra" / "google-oauth-token.json"
        creds = Credentials.from_authorized_user_file(str(token_path))
        service = build("sheets", "v4", credentials=creds)
        drive = build("drive", "v3", credentials=creds)

        # OnSocial folder ID
        FOLDER_ID = "1Q3W3dKbGSU7JXBqf2oqCpSWmTmWwkST0"

        headers = list(rows[0].keys())
        values = [headers] + [[r.get(h, "") for h in headers] for r in rows]

        body = {"properties": {"title": sheet_name}}
        sheet = (
            service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        )
        sid = sheet["spreadsheetId"]

        service.spreadsheets().values().update(
            spreadsheetId=sid,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        drive.files().update(
            fileId=sid,
            addParents=FOLDER_ID,
            removeParents="root",
            fields="id, parents",
        ).execute()

        print(f"  Google Sheets: https://docs.google.com/spreadsheets/d/{sid}")
    except Exception as e:
        print(f"  ⚠ Sheets upload failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

SEGMENTS = [
    ("SOCCOM", "OS_People_SOCCOM_2026-04-10.csv", "SOCCOM"),
    ("INFPLAT", "OS_People_INFPLAT_2026-04-10.csv", "INFPLAT"),
    ("IMAGENCY", "OS_People_IMAGENCY_2026-04-10.csv", "IMAGENCY"),
]

for seg_code, filename, segment in SEGMENTS:
    input_path = INPUT_DIR / filename
    if not input_path.exists():
        print(f"\n[{seg_code}] ⚠ File not found: {input_path}")
        continue

    print(f"\n[{seg_code}]")
    rows = enrich_csv(input_path, segment)

    local_name = f"OS_People_{seg_code}_enriched_{TODAY}.csv"
    save_csv(rows, INPUT_DIR / local_name)

    sheet_name = f"OS | People | {seg_code} — {TODAY}"
    print(f"  Uploading to Sheets: {sheet_name}")
    upload_to_sheets(rows, sheet_name)

print("\nDone.")
