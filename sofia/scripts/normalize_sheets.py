#!/usr/bin/env python3
"""
Normalize Google Sheets data for SmartLead import tabs.
Normalizes: first_name, last_name, company_name, website, linkedin_url
"""

import json
import re
import os

# ─── Company name normalization rules ────────────────────────────────────────
# Keep these as the canonical reference

# Words that should stay lowercase (unless first/last word)
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
    "for",
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

# Abbreviations/acronyms that should stay UPPERCASE
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

# Known company name overrides (exact replacements)
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
    """True if string has both upper and lower letters (intentional brand casing)."""
    has_upper = any(c.isupper() for c in s)
    has_lower = any(c.islower() for c in s)
    return has_upper and has_lower


def normalize_company_name(name: str) -> str:
    """
    Normalize a company name.
    Rules (in order):
    1. Strip whitespace
    2. Check COMPANY_OVERRIDES (case-insensitive)
    3. If already mixed-case (e.g. 'HypeAuditor', 'iMOX', 'twigBIG') — leave as-is
    4. If all-lowercase or all-uppercase → apply Title Case with UPPER_WORDS/LOWER_WORDS exceptions
    """
    if not name or not name.strip():
        return name

    stripped = name.strip()

    # 1. Override table (case-insensitive)
    lower_key = stripped.lower()
    if lower_key in COMPANY_OVERRIDES:
        return COMPANY_OVERRIDES[lower_key]

    # 2. If already mixed-case — it's an intentional brand name, don't touch
    if is_mixed_case(stripped):
        return stripped

    # 3. All-lower or all-upper → Title Case
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


# Name particles that stay lowercase when not first word
NAME_PARTICLES = {
    "de",
    "van",
    "von",
    "der",
    "den",
    "la",
    "le",
    "du",
    "di",
    "da",
    "do",
    "los",
    "las",
}


def capitalize_name_part(part: str) -> str:
    """
    Capitalize a single name token properly:
    - Mc/Mac prefix: McFarland, MacDonald
    - O' prefix: O'Brien
    - Hyphenated: Mary-Jane
    - ALL CAPS → Title case
    - already mixed case → leave as-is
    """
    if not part:
        return part

    # Already mixed case (intentional) — preserve
    if is_mixed_case(part):
        return part

    # Mc prefix: McFarland
    mc = re.match(r"^(Mc|mc|MC)(.+)$", part)
    if mc:
        return "Mc" + mc.group(2).capitalize()

    # Mac prefix (only if followed by uppercase letter in original, e.g. MacDonald)
    mac = re.match(r"^(Mac|mac|MAC)([A-Z].*)$", part, re.IGNORECASE)
    if mac:
        return "Mac" + mac.group(2).capitalize()

    # Hyphenated: Mary-Jane
    if "-" in part:
        return "-".join(capitalize_name_part(p) for p in part.split("-"))

    # O'Brien, D'Angelo
    if "'" in part:
        sub = part.split("'", 1)
        return sub[0].capitalize() + "'" + sub[1].capitalize()

    return part.capitalize()


def normalize_name(name: str) -> str:
    """
    Normalize a person's name:
    - Title Case each word
    - Preserve particles (de, van, von...) as lowercase unless they're first
    - Handle Mc/Mac, O', hyphenated names
    - ALL CAPS → Title Case
    """
    if not name or not name.strip():
        return name

    parts = name.strip().split()
    normalized = []
    for i, part in enumerate(parts):
        lower_part = part.lower()
        if i > 0 and lower_part in NAME_PARTICLES:
            normalized.append(lower_part)
        else:
            normalized.append(capitalize_name_part(part))
    return " ".join(normalized)


def normalize_domain(domain: str) -> str:
    """
    Normalize website/domain:
    - Remove https://, http://, www.
    - Remove trailing slash
    - Lowercase
    """
    if not domain or not domain.strip():
        return domain
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.rstrip("/")
    return d


def normalize_linkedin_url(url: str) -> str:
    """
    Normalize LinkedIn URL:
    - Ensure https://linkedin.com/in/{slug} format (no www)
    - Remove trailing slash
    - Lowercase the base, preserve slug case
    """
    if not url or not url.strip():
        return url
    u = url.strip()
    # Extract slug
    match = re.search(r"linkedin\.com/in/([^/?#\s]+)", u, re.IGNORECASE)
    if match:
        slug = match.group(1).rstrip("/")
        return f"https://linkedin.com/in/{slug}"
    # If it's just a slug or partial, return as-is cleaned
    return u.rstrip("/")


def normalize_row(row: dict, sheet_name: str) -> dict:
    """Normalize a single row dict in-place."""
    result = dict(row)

    if "first_name" in result:
        result["first_name"] = normalize_name(result["first_name"])

    if "last_name" in result:
        result["last_name"] = normalize_name(result["last_name"])

    if "company_name" in result:
        result["company_name"] = normalize_company_name(result["company_name"])

    if "website" in result:
        result["website"] = normalize_domain(result["website"])

    if "linkedin_url" in result:
        result["linkedin_url"] = normalize_linkedin_url(result["linkedin_url"])

    return result


def load_sheet_file(path: str):
    """Load a tool-result file and extract rows."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = json.loads(raw["result"])
    return data["values"]  # list of dicts when as_json=true


def rows_to_2d(rows: list[dict], headers: list[str]) -> list[list]:
    """Convert list of dicts back to 2D array (values only, no header row)."""
    result = []
    for row in rows:
        result.append([row.get(h, "") for h in headers])
    return result


def normalize_sheet(rows: list[dict], sheet_name: str):
    """Normalize all rows and return (headers, normalized_2d)."""
    if not rows:
        return [], []
    headers = list(rows[0].keys())
    normalized = [normalize_row(r, sheet_name) for r in rows]
    return headers, rows_to_2d(normalized, headers)


def diff_count(original: list[dict], normalized: list[list], headers: list[str]):
    """Count how many cells changed."""
    changed = 0
    for i, orig_row in enumerate(original):
        if i >= len(normalized):
            break
        for j, h in enumerate(headers):
            orig_val = str(orig_row.get(h, "") or "")
            norm_val = str(normalized[i][j] if j < len(normalized[i]) else "")
            if orig_val != norm_val:
                changed += 1
    return changed


if __name__ == "__main__":
    base = "/Users/user/.claude/projects/-Users-user-sales-engineer/65a83b8f-0927-469f-a0bf-74fa01556e62/tool-results"

    sheets = [
        {
            "name": "SL IMAGENCY",
            "file": os.path.join(
                base, "mcp-google-sheets-sheets_read_range-1776258302283.txt"
            ),
        },
        {
            "name": "SL INFPLAT",
            "file": os.path.join(
                base, "mcp-google-sheets-sheets_read_range-1776258303435.txt"
            ),
        },
        {
            "name": "SL AFFPERF",
            "file": os.path.join(
                base, "mcp-google-sheets-sheets_read_range-1776258304494.txt"
            ),
        },
        {
            "name": "SL SOCCOM",
            "file": os.path.join(
                base, "mcp-google-sheets-sheets_read_range-1776258304238.txt"
            ),
        },
    ]

    for sheet in sheets:
        rows = load_sheet_file(sheet["file"])
        headers, normalized_2d = normalize_sheet(rows, sheet["name"])
        n_changed = diff_count(rows, normalized_2d, headers)
        print(f"{sheet['name']}: {len(rows)} rows, {n_changed} cells changed")

        # Output: header row + data
        full_output = [headers] + normalized_2d
        out_path = f"/tmp/normalized_{sheet['name'].replace(' ', '_')}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(full_output, f, ensure_ascii=False, indent=2)
        print(f"  → saved to {out_path}")
