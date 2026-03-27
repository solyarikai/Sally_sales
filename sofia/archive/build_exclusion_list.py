#!/usr/bin/env python3
"""Build exclusion list CSV from all OnSocial outreach sources."""

import json
import csv
import os
import sys

BASE = "/Users/user/.claude/projects/-Users-user-Library-Mobile-Documents-com-apple-CloudDocs-sales-engineer/ebf57204-0271-441c-8817-11df928d725d/tool-results"
OUT = "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/sales_engineer/projects/OnSocial/exclusion_list_apollo.csv"
CACHE_DIR = "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/sales_engineer/projects/OnSocial/data"

all_contacts = []

def safe_get(row, idx, default=""):
    if idx < len(row):
        val = row[idx]
        if val is None:
            return default
        return str(val).strip()
    return default

def clean_name(name):
    name = name.strip()
    if name == "--":
        return ""
    return name

def clean_linkedin(li):
    li = li.strip()
    if li in ("--", "NA", ""):
        return ""
    return li

# ============================================================
# 1. Large JSON files
# ============================================================
json_files = [
    ("mcp-google-sheets-get_sheet_data-1773341671054.txt", "Marketing agencies"),
    ("mcp-google-sheets-get_sheet_data-1773341672104.txt", "IM platforms & SaaS"),
    ("mcp-google-sheets-get_sheet_data-1773341673379.txt", "Generic"),
]

for fname, source_sheet in json_files:
    fpath = os.path.join(BASE, fname)
    with open(fpath, 'r') as f:
        data = json.load(f)

    rows = data["result"]["valueRanges"][0]["values"]
    for row in rows[1:]:
        first_name = clean_name(safe_get(row, 0))
        last_name = clean_name(safe_get(row, 1))
        email = safe_get(row, 8)
        linkedin = clean_linkedin(safe_get(row, 9))
        company = safe_get(row, 10)
        website = safe_get(row, 11)

        if not first_name and not last_name and not email and not linkedin:
            continue

        all_contacts.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "company": company,
            "website": website,
            "linkedin": linkedin,
            "source_sheet": source_sheet,
        })

print(f"After JSON files: {len(all_contacts)} contacts")

# ============================================================
# 2-6: Load from cache JSON files (saved separately)
# ============================================================
# No_name
cache_file = os.path.join(CACHE_DIR, "no_name_cache.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        rows = json.load(f)
    for row in rows:
        all_contacts.append({
            "first_name": clean_name(safe_get(row, 0)),
            "last_name": clean_name(safe_get(row, 1)),
            "email": safe_get(row, 2),
            "company": safe_get(row, 3),
            "website": safe_get(row, 4),
            "linkedin": clean_linkedin(safe_get(row, 5)),
            "source_sheet": "No_name",
        })
    print(f"After No_name: {len(all_contacts)} contacts")
else:
    print(f"WARNING: {cache_file} not found")

# WANNA TALK
cache_file = os.path.join(CACHE_DIR, "wanna_talk_cache.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        rows = json.load(f)
    for row in rows:
        first_name = clean_name(safe_get(row, 0))
        if not first_name:
            continue
        all_contacts.append({
            "first_name": first_name,
            "last_name": clean_name(safe_get(row, 1)),
            "email": safe_get(row, 7),
            "linkedin": clean_linkedin(safe_get(row, 8)),
            "company": safe_get(row, 9),
            "website": safe_get(row, 10),
            "source_sheet": "WANNA TALK",
        })
    print(f"After WANNA TALK: {len(all_contacts)} contacts")
else:
    print(f"WARNING: {cache_file} not found")

# email replies
cache_file = os.path.join(CACHE_DIR, "email_replies_cache.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        rows = json.load(f)
    for row in rows:
        first_name = clean_name(safe_get(row, 0))
        last_name = clean_name(safe_get(row, 1))
        email = safe_get(row, 4)
        if not first_name and not last_name and not email:
            continue
        all_contacts.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "linkedin": clean_linkedin(safe_get(row, 3)),
            "company": safe_get(row, 6),
            "website": safe_get(row, 7),
            "source_sheet": "email_replies",
        })
    print(f"After email_replies: {len(all_contacts)} contacts")
else:
    print(f"WARNING: {cache_file} not found")

# LI replies
cache_file = os.path.join(CACHE_DIR, "li_replies_cache.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        rows = json.load(f)
    for row in rows:
        first_name = clean_name(safe_get(row, 0))
        last_name = clean_name(safe_get(row, 1))
        email = safe_get(row, 4)
        linkedin = clean_linkedin(safe_get(row, 3))
        if not first_name and not last_name and not email and not linkedin:
            continue
        all_contacts.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "linkedin": linkedin,
            "company": safe_get(row, 6),
            "website": safe_get(row, 7),
            "source_sheet": "LI_replies",
        })
    print(f"After LI_replies: {len(all_contacts)} contacts")
else:
    print(f"WARNING: {cache_file} not found")

# BLACKLIST
cache_file = os.path.join(CACHE_DIR, "blacklist_cache.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        rows = json.load(f)
    for row in rows:
        website_raw = safe_get(row, 1)
        if not website_raw:
            continue
        website = website_raw.strip().rstrip("/")
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        all_contacts.append({
            "first_name": "",
            "last_name": "",
            "email": "",
            "company": domain,
            "website": website,
            "linkedin": "",
            "source_sheet": "BLACKLIST",
        })
    print(f"After BLACKLIST: {len(all_contacts)} contacts")
else:
    print(f"WARNING: {cache_file} not found")

# ============================================================
# Deduplicate
# ============================================================
seen_emails = set()
seen_linkedin = set()
seen_company_website = set()
unique_contacts = []

for c in all_contacts:
    email = c["email"].lower().strip()
    linkedin = c["linkedin"].lower().strip()
    cw_key = (c["company"].lower().strip(), c["website"].lower().strip())

    if email:
        if email in seen_emails:
            continue
        seen_emails.add(email)
    elif linkedin:
        if linkedin in seen_linkedin:
            continue
        seen_linkedin.add(linkedin)
    elif c["company"] or c["website"]:
        if cw_key in seen_company_website:
            continue
        seen_company_website.add(cw_key)
    else:
        continue

    unique_contacts.append(c)

print(f"\nTotal before dedup: {len(all_contacts)}")
print(f"Total after dedup: {len(unique_contacts)}")

# ============================================================
# Write CSV
# ============================================================
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=[
        "first_name", "last_name", "email", "company", "website", "linkedin", "source_sheet"
    ])
    writer.writeheader()
    writer.writerows(unique_contacts)

print(f"\nCSV written to: {OUT}")

from collections import Counter
source_counts = Counter(c["source_sheet"] for c in unique_contacts)
print("\nContacts per source:")
for source, count in sorted(source_counts.items()):
    print(f"  {source}: {count}")
