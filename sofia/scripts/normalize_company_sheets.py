#!/usr/bin/env python3
"""
Normalize company_name column in all SL/GS sheets of the Import spreadsheet.
Uses existing OAuth token from google-sheets MCP.
"""

import json
import re
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID = "1MK_ynBiUumk5NCRksQGvwEVBMi4G9iB5-i416lgrOEA"
TOKEN_PATH = Path(__file__).parents[2] / ".claude/mcp/google-sheets/token.json"

LOWER_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "but",
    "or",
    "nor",
    "for",
    "so",
    "yet",
    "at",
    "by",
    "in",
    "of",
    "on",
    "to",
    "up",
    "as",
    "is",
    "via",
    "with",
    "from",
}

UPPER_WORDS = {
    "AI",
    "API",
    "B2B",
    "B2C",
    "CEO",
    "CFO",
    "CMO",
    "COO",
    "CPO",
    "CTO",
    "CRM",
    "DTC",
    "ESG",
    "GDP",
    "IMC",
    "INC",
    "LLC",
    "LLP",
    "LTD",
    "MCN",
    "NFC",
    "PR",
    "ROI",
    "SaaS",
    "SEO",
    "SMB",
    "SME",
    "SMM",
    "UK",
    "US",
    "USA",
    "UAE",
    "EU",
    "APAC",
    "EMEA",
    "LATAM",
    "IM",
    "KOL",
    "UGC",
    "MCM",
    "KPI",
}

COMPANY_OVERRIDES = {
    "imagency": "iMagency",
    "immagency": "iMagency",
    "sideqik": "Sideqik",
    "traackr": "Traackr",
    "grin": "GRIN",
    "mavrck": "Mavrck",
    "tagger": "Tagger",
    "klear": "Klear",
    "heepsy": "Heepsy",
    "lefty": "Lefty",
    "modash": "Modash",
    "hypeauditor": "HypeAuditor",
    "upfluence": "Upfluence",
    "aspire": "Aspire",
    "captiv8": "Captiv8",
    "creator.co": "Creator.co",
    "socialbakers": "Socialbakers",
    "sociallypowerful": "Socially Powerful",
    "ykone": "Ykone",
    "whalar": "Whalar",
    "samy alliance": "SAMY Alliance",
    "webedia": "Webedia",
    "billion dollar boy": "Billion Dollar Boy",
    "influencer": "Influencer",
    "viral nation": "Viral Nation",
    "ogilvy": "Ogilvy",
}


def is_mixed_case(s: str) -> bool:
    return any(c.isupper() for c in s) and any(c.islower() for c in s)


def normalize_company_name(name: str) -> str:
    if not name or not name.strip():
        return name

    stripped = name.strip()

    lower_key = stripped.lower()
    if lower_key in COMPANY_OVERRIDES:
        return COMPANY_OVERRIDES[lower_key]

    if is_mixed_case(stripped):
        return stripped

    words = re.split(r"(\s+|-)", stripped)
    result = []
    word_index = 0
    actual_words = [w for w in words if w.strip() and w != "-"]

    for token in words:
        if not token.strip() or token == "-":
            result.append(token)
            continue

        upper = token.upper()
        if upper in UPPER_WORDS:
            result.append(upper)
        elif (
            token.lower() in LOWER_WORDS
            and word_index > 0
            and word_index < len(actual_words) - 1
        ):
            result.append(token.lower())
        else:
            result.append(token[0].upper() + token[1:].lower())

        word_index += 1

    return "".join(result)


def get_service():
    token_data = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"],
    )
    if creds.expired:
        creds.refresh(Request())
        token_data["token"] = creds.token
        TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
    return build("sheets", "v4", credentials=creds)


def col_letter(n: int) -> str:
    """Convert 1-based column index to letter (1=A, 26=Z, 27=AA...)."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def process_sheet(service, sheet_name: str, company_col_index: int):
    """Read company_name column, normalize, write back changed cells."""
    sheets = service.spreadsheets()

    # Read header row to confirm column
    header_range = f"'{sheet_name}'!{col_letter(company_col_index)}1"
    header_result = (
        sheets.values().get(spreadsheetId=SPREADSHEET_ID, range=header_range).execute()
    )
    header = header_result.get("values", [[""]])[0][0]
    if header != "company_name":
        print(f"  ⚠️  Header mismatch: expected 'company_name', got '{header}'")
        return 0

    # Read all company names (row 2 onward)
    data_range = f"'{sheet_name}'!{col_letter(company_col_index)}2:{col_letter(company_col_index)}5000"
    result = (
        sheets.values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range=data_range,
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )

    rows = result.get("values", [])
    if not rows:
        print(f"  {sheet_name}: no data")
        return 0

    updates = []
    for i, row in enumerate(rows):
        original = row[0] if row else ""
        normalized = normalize_company_name(original)
        if original != normalized:
            row_num = i + 2  # 1-based, +1 for header
            updates.append(
                {
                    "range": f"'{sheet_name}'!{col_letter(company_col_index)}{row_num}",
                    "values": [[normalized]],
                }
            )

    if updates:
        body = {"valueInputOption": "RAW", "data": updates}
        sheets.values().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

    print(f"  {sheet_name}: {len(rows)} rows, {len(updates)} changed")
    return len(updates)


def main():
    service = get_service()

    # SL sheets: company_name is column D (4)
    sl_sheets = ["SL IMAGENCY", "SL INFPLAT", "SL AFFPERF", "SL SOCCOM"]
    # GS sheets: company_name is column AE (31)
    gs_sheets = ["GS SOCCOM", "GS IMAGENCY", "GS AFFPERF", "GS INFPLAT"]

    total = 0
    print("=== SL sheets (column D) ===")
    for name in sl_sheets:
        total += process_sheet(service, name, 4)

    print("=== GS sheets (column AE) ===")
    for name in gs_sheets:
        total += process_sheet(service, name, 31)

    print(f"\n✓ Total cells updated: {total}")


if __name__ == "__main__":
    main()
