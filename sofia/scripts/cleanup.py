#!/usr/bin/env python3
"""
Universal pre-Findymail cleanup: filter + normalize + deduplicate Apollo CSV exports.

Usage:
    python cleanup.py --input <raw.csv> --output <filtered.csv>

    # With optional overrides:
    python cleanup.py \\
        --input "projects/OnSocial/segments/Target - raw.csv" \\
        --output "projects/OnSocial/segments/Target - filtered.csv" \\
        --exclude-uploaded "Target - AMERICAS - with_email.csv" \\
        --max-contacts 3000 \\
        --no-dm-filter        # skip decision-maker title filtering
        --no-keyword-filter   # skip industry keyword filtering

Output:
    <output>.csv   — filtered, normalized contacts ready for Findymail
    Stats printed to stdout (removed reasons with counts)

Column mapping (Apollo export → Findymail expected):
    "Links"  → "Profile URL"   (auto-renamed)
    "Company" → normalized in place
"""

import argparse
import csv
import re
from pathlib import Path

# ── Legal suffix stripping ────────────────────────────────────────────────────
LEGAL_SUFFIXES = re.compile(
    r'\s*[,.]?\s*(GmbH|Ltd\.?|Limited|LLC|Inc\.?|Corp\.?|SAS|S\.A\.S\.?|'
    r'BV|B\.V\.|NV|N\.V\.|SRL|AB|AS|Oy|KG|AG|OÜ|Pvt\.?\s*Ltd\.?|Pte\.?\s*Ltd\.?|'
    r'S\.A\.|SA|SL|SLU|SpA|Srl|SARL|EIRL|SASU|S\.r\.l\.)\s*$',
    re.IGNORECASE,
)

# ── Industry keywords that indicate non-target contacts ──────────────────────
TRASH_KEYWORDS = {
    "web development", "web design", "seo", "pr agency", "public relations",
    "crisis communication", "software development", "it services", "consulting",
    "accounting", "legal", "law firm", "financial services", "insurance",
    "real estate", "construction", "manufacturing", "logistics", "supply chain",
}

# ── Titles to exclude (non-decision-makers) ───────────────────────────────────
REMOVE_TITLES = [
    "human resources", "hr ", " hr", "social media manager",
    "customer success", "creator success", "partner relations",
    "product designer", "product design", "software engineer", "product engineer",
    "branding & culture", "branding and culture", "marketing manager",
    "compliance", "head of operations", "operations manager",
    "campaign manager", "kol specialist", "content manager",
    "production manager", "finance manager", "community lead",
    "project management", "engineering manager", "account executive",
    "back end engineer", "client manager", "video editor",
    "key account manager", "account manager", "social media manager",
    "influencer marketing campaign manager", "client partner",
    "head of finance", "chief people officer",
    "manager",  # standalone — checked only if none of KEEP_TITLES matches
]

# These override REMOVE_TITLES — keep even if a bad keyword is present
KEEP_TITLES = [
    "co-founder", "ceo", "cto", "coo", "cmo", "cfo", "cco",
    "founder", "growth director", "sales director", "account director",
    "head of growth", "head of strategy", "head of sales",
    "vice general manager", "business development",
    "partnerships manager", "client service and operations director",
    "data & media analytics", "marketing leader",
]


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize_company(name: str) -> str:
    if not name:
        return name
    name = LEGAL_SUFFIXES.sub("", name).strip().rstrip(".,")
    # slug: "the-models" → "The Models"
    if "-" in name and name == name.lower():
        name = name.replace("-", " ")
    # all lowercase > 4 chars → Title Case
    if name == name.lower() and len(name) > 4:
        name = name.title()
    # ALLCAPS > 4 chars → Title Case (preserves short abbreviations like VEED, EBO)
    elif name == name.upper() and len(name) > 4:
        name = name.title()
    return name.strip()


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_decision_maker(title: str) -> bool:
    t = title.lower()
    for keep in KEEP_TITLES:
        if keep in t:
            return True
    for bad in REMOVE_TITLES:
        if bad in t:
            return False
    return True


def get_linkedin_url(row: dict) -> str:
    """Try both 'Profile URL' and legacy 'Links' column names."""
    return row.get("Profile URL", row.get("Links", "")).strip()


def filter_row(row: dict, dm_filter: bool, keyword_filter: bool) -> tuple[bool, str]:
    """Returns (keep, reason_if_removed)."""
    li = get_linkedin_url(row)
    if not li:
        return False, "no_linkedin"

    if not row.get("Name", "").strip():
        return False, "no_name"

    # Apollo score
    score = row.get("People Auto-Score", row.get("Auto Score", row.get("Score", ""))).lower()
    if "not a fit" in score or score.strip() == "0":
        return False, "not_a_fit"

    if keyword_filter:
        keywords_raw = row.get("Company · Keywords", row.get("Company Keywords", "")).lower()
        for kw in TRASH_KEYWORDS:
            if kw in keywords_raw:
                return False, f"kw:{kw}"

    if dm_filter:
        title = row.get("Title", row.get("Job title", "")).strip()
        if title and not is_decision_maker(title):
            return False, f"non_dm:{title[:40]}"

    return True, ""


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter and normalize Apollo CSV export before Findymail enrichment"
    )
    parser.add_argument("--input", required=True,
                        help="Path to raw Apollo CSV export")
    parser.add_argument("--output",
                        help="Output path (default: <input_stem> - filtered.csv)")
    parser.add_argument("--exclude-uploaded", action="append", default=[],
                        metavar="CSV",
                        help="CSV file(s) with already-uploaded contacts to exclude "
                             "(matched by Profile URL). Repeatable.")
    parser.add_argument("--max-contacts", type=int, default=0,
                        help="Keep only top N contacts sorted by Score (0 = all)")
    parser.add_argument("--no-dm-filter", action="store_true",
                        help="Skip decision-maker title filtering")
    parser.add_argument("--no-keyword-filter", action="store_true",
                        help="Skip industry keyword filtering")
    return parser.parse_args()


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem} - filtered.csv"

    # Load exclusion lists (already-uploaded contacts)
    excluded_urls: set[str] = set()
    for excl_file in args.exclude_uploaded:
        p = Path(excl_file)
        if p.exists():
            for row in csv.DictReader(p.open(encoding="utf-8")):
                url = row.get("Profile URL", "").strip().rstrip("/")
                if url:
                    excluded_urls.add(url)
            print(f"Exclusion list: {len(excluded_urls)} URLs from {p.name}")
        else:
            print(f"WARN: exclusion file not found: {p}")

    # Read input
    rows = list(csv.DictReader(input_path.open(encoding="utf-8")))
    print(f"Raw contacts: {len(rows)}")

    # Deduplicate by Profile URL
    seen_urls: dict[str, dict] = {}
    for r in rows:
        url = get_linkedin_url(r).rstrip("/")
        if not url:
            continue
        if url not in seen_urls:
            seen_urls[url] = r
        else:
            # Prefer row with better score
            old_score = seen_urls[url].get("Score", seen_urls[url].get("Auto Score", ""))
            new_score = r.get("Score", r.get("Auto Score", ""))
            if new_score and not old_score:
                seen_urls[url] = r

    print(f"After dedup by Profile URL: {len(seen_urls)}")

    # Sort by Score desc (for --max-contacts)
    def score_key(r):
        try:
            return float(r.get("Score", r.get("People Auto-Score", 0)) or 0)
        except Exception:
            return 0.0

    sorted_rows = sorted(seen_urls.values(), key=score_key, reverse=True)

    # Filter
    filtered = []
    removed_stats: dict[str, int] = {}

    for row in sorted_rows:
        url = get_linkedin_url(row).rstrip("/")

        # Skip already-uploaded contacts
        if url in excluded_urls:
            removed_stats["already_uploaded"] = removed_stats.get("already_uploaded", 0) + 1
            continue

        keep, reason = filter_row(
            row,
            dm_filter=not args.no_dm_filter,
            keyword_filter=not args.no_keyword_filter,
        )
        if not keep:
            removed_stats[reason] = removed_stats.get(reason, 0) + 1
            continue

        # Normalize company name
        company_key = "Company"
        row[company_key] = normalize_company(row.get(company_key, ""))

        # Rename "Links" → "Profile URL" for Findymail compatibility
        if "Links" in row and "Profile URL" not in row:
            row["Profile URL"] = row.pop("Links")
        elif "Links" in row:
            row.pop("Links")

        filtered.append(row)

        if args.max_contacts and len(filtered) >= args.max_contacts:
            break

    # Stats
    print(f"\nRemoved: {len(sorted_rows) - len(filtered)}")
    for reason, count in sorted(removed_stats.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    print(f"\nKept: {len(filtered)}")

    if not filtered:
        print("Nothing to save.")
        return

    # Write output
    fieldnames = list(filtered[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filtered)

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
