#!/usr/bin/env python3
"""
Enrich "Not Interested" Google Sheet with company location and size.

Reads the sheet, matches companies against:
1. PostgreSQL DB (contacts table - location, geo, segment)
2. tam_companies.json (Location, Primary Industry)
3. uae_god_search_companies.json (employees, city, country)

Adds/updates two columns: Company Location, Company Size
"""

import json
import os
import sys
import re
import logging
from pathlib import Path

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
SPREADSHEET_ID = "1hh6LNTST_1MxLPERyjDkSHIZNOnFmwZvsyvKDHwQkYI"
SHEET_GID = "135248658"
CREDS_PATH = "/home/leadokol/magnum-opus-project/repo/google-credentials.json"
IMPERSONATE_EMAIL = "services@getsally.io"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "leadgen"
DB_USER = "leadgen"
DB_PASS = os.environ.get("DB_PASSWORD", "leadgen_secret")

# Local data files
DATA_DIR = Path("/home/leadokol/magnum-opus-project/repo")
TAM_FILE = DATA_DIR / "scripts/clay/exports/tam_companies.json"
UAE_FILE = DATA_DIR / "easystaff-global/data/uae_god_search_companies.json"

# Clay Size UUID → human-readable range (approximate, based on distribution)
CLAY_SIZE_MAP = {
    "23fe921e-d385-4400-a6d9-e19d3510499e": "1-50",
    "9617d0e9-ed73-4cbf-8abb-1d65a0ab1ada": "51-200",
    "b9c2c641-c517-45b9-99bd-0df0a1e5e703": "201-500",
    "da3a7cc6-4f8f-4ae2-8373-33ba26783725": "501-1000",
    "2bc5199b-9ea9-4d74-99e9-c9eee8dccebd": "1001-5000",
    "328e4ad8-7918-4dbd-977f-e334b72a1f65": "5001-10000",
    "f40c32d2-2816-4766-a253-fc99dd82e2be": "10001-50000",
    "f321fdc8-538f-419a-83ea-b8594070044f": "50000+",
}


def norm_domain(raw: str) -> str:
    """Normalize domain: strip scheme, www, trailing slash."""
    if not raw:
        return ""
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0].strip()
    return d


def extract_domain_from_email(email: str) -> str:
    if email and '@' in email:
        return email.split('@')[1].strip().lower()
    return ""


# ── Load local JSON data ─────────────────────────────────────────────────────
def load_json_index():
    """Build lookup dicts: domain -> {location, size} from local files."""
    index = {}  # domain -> {location, size}

    # TAM companies
    if TAM_FILE.exists():
        with open(TAM_FILE) as f:
            tam = json.load(f)
        for c in tam:
            domain = norm_domain(c.get("Domain", ""))
            if not domain:
                continue
            location = c.get("Location", "") or ""
            country = c.get("Country", "") or ""
            loc = location if location else country

            # Decode Clay size UUID
            size_raw = c.get("Size", "")
            size = ""
            if size_raw:
                uids = re.findall(
                    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                    size_raw
                )
                for uid in uids:
                    if uid in CLAY_SIZE_MAP:
                        size = CLAY_SIZE_MAP[uid]
                        break

            if domain not in index:
                index[domain] = {"location": loc, "size": size, "source": "tam"}
            else:
                if not index[domain].get("location") and loc:
                    index[domain]["location"] = loc
                if not index[domain].get("size") and size:
                    index[domain]["size"] = size

        log.info(f"TAM: loaded {len(tam)} companies")

    # UAE companies
    if UAE_FILE.exists():
        with open(UAE_FILE) as f:
            uae = json.load(f)
        for c in uae:
            domain = norm_domain(c.get("domain", ""))
            if not domain:
                continue
            city = c.get("city", "") or ""
            country = c.get("country", "") or ""
            loc = ", ".join(filter(None, [city, country]))
            employees = c.get("employees")
            size = str(employees) if employees else ""

            if domain not in index:
                index[domain] = {"location": loc, "size": size, "source": "uae"}
            else:
                if not index[domain].get("location") and loc:
                    index[domain]["location"] = loc
                if not index[domain].get("size") and size:
                    index[domain]["size"] = size

        log.info(f"UAE: loaded {len(uae)} companies")

    return index


# ── DB lookup ────────────────────────────────────────────────────────────────
def build_db_company_names(conn, domains: list) -> dict:
    """Return domain -> company_name from contacts + discovered_companies."""
    if not domains:
        return {}
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(domains))
    result = {}

    # contacts (prefer non-empty, most common name)
    cur.execute(
        f"SELECT domain, company_name, COUNT(*) AS cnt FROM contacts "
        f"WHERE domain IN ({placeholders}) AND company_name IS NOT NULL AND company_name != '' "
        f"GROUP BY domain, company_name ORDER BY domain, cnt DESC",
        domains,
    )
    for domain, name, _ in cur.fetchall():
        d = norm_domain(domain)
        if d not in result:
            result[d] = name

    # discovered_companies fallback
    cur.execute(
        f"SELECT domain, name FROM discovered_companies "
        f"WHERE domain IN ({placeholders}) AND name IS NOT NULL AND name != ''",
        domains,
    )
    for domain, name in cur.fetchall():
        d = norm_domain(domain)
        if d not in result:
            result[d] = name

    return result


def build_db_index():
    """Build domain -> {location, size} from DB (discovered_companies + contacts)."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASS
        )
        cur = conn.cursor()

        idx = {}  # domain -> {location, size}

        # 1. discovered_companies: structured company_info + apollo_org_data
        cur.execute("""
            SELECT domain, company_info, apollo_org_data
            FROM discovered_companies
            WHERE domain IS NOT NULL AND domain != ''
        """)
        for domain, ci, aod in cur.fetchall():
            d = norm_domain(domain)
            if not d:
                continue
            loc = ""
            size = ""
            if ci and isinstance(ci, dict):
                raw_loc = ci.get("location") or ""
                if raw_loc and raw_loc != "not specified":
                    loc = raw_loc
            if aod and isinstance(aod, dict):
                emp = aod.get("num_employees") or aod.get("employee_count")
                if emp:
                    size = str(emp)
                if not loc:
                    city = aod.get("city") or ""
                    country = aod.get("country") or ""
                    loc = ", ".join(filter(None, [city, country]))
            idx[d] = {"location": loc, "size": size}

        # 2. contacts: use contact location as company proxy
        cur.execute("""
            SELECT domain, location, segment
            FROM contacts
            WHERE domain IS NOT NULL AND domain != ''
              AND location IS NOT NULL AND location != ''
        """)
        for domain, location, segment in cur.fetchall():
            d = norm_domain(domain)
            if not d:
                continue
            if d not in idx:
                idx[d] = {"location": location, "size": segment or ""}
            else:
                if not idx[d].get("location"):
                    idx[d]["location"] = location
                if not idx[d].get("size") and segment:
                    idx[d]["size"] = segment

        conn.close()
        domain_idx = idx
        email_idx = {}  # Not needed since we derive domain from email

        log.info(f"DB: indexed {len(domain_idx)} domains")
        return domain_idx, email_idx

    except Exception as ex:
        log.warning(f"DB lookup failed: {ex}")
        return {}, {}


# ── Google Sheets ─────────────────────────────────────────────────────────────
def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    if IMPERSONATE_EMAIL:
        creds = creds.with_subject(IMPERSONATE_EMAIL)
    return build("sheets", "v4", credentials=creds)


def gid_to_sheet_name(service, spreadsheet_id: str, gid: str) -> str:
    """Resolve numeric GID to sheet tab name."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        if str(sheet["properties"]["sheetId"]) == str(gid):
            return sheet["properties"]["title"]
    raise ValueError(f"Sheet with gid={gid} not found")


def read_sheet(service, spreadsheet_id: str, sheet_name: str):
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
    ).execute()
    return result.get("values", [])


def col_letter(n: int) -> str:
    """0-indexed column number to letter (A, B, ..., Z, AA, ...)."""
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def update_sheet(service, spreadsheet_id: str, sheet_name: str, updates: list):
    """
    updates: list of (row_1indexed, col_0indexed, value) tuples
    Sends as batch update.
    """
    if not updates:
        return

    data = []
    for row, col, value in updates:
        range_addr = f"'{sheet_name}'!{col_letter(col)}{row}"
        data.append({"range": range_addr, "values": [[value]]})

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()
    log.info(f"Wrote {len(updates)} cells to sheet")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("Loading local company data...")
    json_index = load_json_index()
    db_domain_idx, db_email_idx = build_db_index()

    log.info("Connecting to Google Sheets...")
    service = get_sheets_service()

    sheet_name = gid_to_sheet_name(service, SPREADSHEET_ID, SHEET_GID)
    log.info(f"Sheet tab: '{sheet_name}'")

    rows = read_sheet(service, SPREADSHEET_ID, sheet_name)
    if not rows:
        log.error("Sheet is empty or inaccessible")
        sys.exit(1)

    headers = [h.strip().lower() for h in rows[0]]
    raw_headers = rows[0]
    log.info(f"Columns ({len(headers)}): {raw_headers}")

    def find_col(*names):
        for name in names:
            for i, h in enumerate(headers):
                if name.lower() in h:
                    return i
        return -1

    col_email = find_col("email", "e-mail")
    col_domain = find_col("website", "domain", "site")

    # Collect all domains from email column to query company names
    all_domains = []
    for row in rows[1:]:
        email = row[col_email].strip() if col_email >= 0 and col_email < len(row) else ""
        domain = norm_domain(row[col_domain].strip() if col_domain >= 0 and col_domain < len(row) else "")
        if not domain and email:
            domain = extract_domain_from_email(email)
        if domain:
            all_domains.append(domain)

    # Build company names index from DB
    company_names: dict = {}
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASS
        )
        company_names = build_db_company_names(conn, list(set(all_domains)))
        conn.close()
        log.info(f"Company names found: {len(company_names)}")
    except Exception as ex:
        log.warning(f"DB company names lookup failed: {ex}")

    # Find or create output columns (Company Name, Company Location, Company Size)
    col_name_out = find_col("company name")
    col_loc_out = find_col("company location")
    col_size_out = find_col("company size", "employees", "employee")

    num_cols = len(headers)
    if col_name_out == -1:
        col_name_out = num_cols; num_cols += 1
    if col_loc_out == -1:
        col_loc_out = num_cols; num_cols += 1
    if col_size_out == -1:
        col_size_out = num_cols; num_cols += 1

    updates = []

    # Write column headers if new
    if col_name_out >= len(raw_headers):
        updates.append((1, col_name_out, "Company Name"))
    if col_loc_out >= len(raw_headers):
        updates.append((1, col_loc_out, "Company Location"))
    if col_size_out >= len(raw_headers):
        updates.append((1, col_size_out, "Company Size"))

    def lookup_loc_size(email: str, domain: str):
        e = (email or "").strip().lower()
        d = norm_domain(domain or "")
        if not d and e:
            d = extract_domain_from_email(e)
        entry = db_email_idx.get(e) or db_domain_idx.get(d) or json_index.get(d) or {}
        return entry.get("location", ""), entry.get("size", "")

    name_matched = loc_matched = 0

    for i, row in enumerate(rows[1:], start=2):
        def get(col):
            return row[col].strip() if 0 <= col < len(row) else ""

        email = get(col_email)
        domain = norm_domain(get(col_domain))
        if not domain and email:
            domain = extract_domain_from_email(email)

        # Company Name
        company_name = company_names.get(domain, "")
        cur_name = row[col_name_out].strip() if col_name_out < len(row) else ""
        if company_name and not cur_name:
            updates.append((i, col_name_out, company_name))
            name_matched += 1
            log.info(f"  Row {i}: {email} → {company_name}")

        # Location + Size
        loc, size = lookup_loc_size(email, domain)
        cur_loc = row[col_loc_out].strip() if col_loc_out < len(row) else ""
        cur_size = row[col_size_out].strip() if col_size_out < len(row) else ""
        if loc and not cur_loc:
            updates.append((i, col_loc_out, loc))
            loc_matched += 1
        if size and not cur_size:
            updates.append((i, col_size_out, size))

    log.info(f"Company names written: {name_matched}, locations: {loc_matched}")
    log.info(f"Total cells to write: {len(updates)}")

    if updates:
        update_sheet(service, SPREADSHEET_ID, sheet_name, updates)
        log.info("Done!")
    else:
        log.info("Nothing to write.")


if __name__ == "__main__":
    main()
