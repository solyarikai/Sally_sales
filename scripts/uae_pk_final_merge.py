#!/usr/bin/env python3
"""
UAE-PK Final Merge: Filter UAE-only contacts, enrich missing companies via Apollo,
cap 3 per company, write to NEW tab.

Steps:
1. Read UAE-PK VERIFIED + Reuse Scored tabs
2. Keep only UAE-located contacts
3. For companies with <3 UAE contacts, search Apollo for UAE-based decision-makers
4. Cap 3 per company, write NEW tab with timestamp
"""
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, '/app')
from app.services.apollo_service import ApolloService
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
MAX_PER_COMPANY = 3

UAE_KEYWORDS = ['dubai', 'abu dhabi', 'sharjah', 'uae', 'united arab',
                'ajman', 'ras al', 'fujairah', 'الإمارات', 'دبي']

DECISION_TITLES = [
    "CFO", "Chief Financial Officer", "VP Finance", "Head of Finance",
    "COO", "Chief Operating Officer", "VP Operations", "Head of Operations",
    "CHRO", "Chief HR Officer", "VP HR", "Head of HR", "Head of People",
    "CEO", "Founder", "Co-Founder", "Managing Director", "General Manager",
    "CTO", "VP Engineering", "Head of Technology",
    "Head of Payroll", "Payroll Manager", "Finance Director",
]


def is_uae_located(location: str) -> bool:
    loc = (location or '').lower()
    return any(k in loc for k in UAE_KEYWORDS)


def read_verified_tabs(gs):
    """Read both verified and reuse scored tabs, return combined rows."""
    tabs = [
        'UAE-PK VERIFIED 0316_0854',
        'UAE-PK Reuse Scored 0316_1016',
    ]
    all_rows = []
    headers = None
    for tab in tabs:
        print(f"Reading {tab}...")
        raw = gs.read_sheet_raw(SHEET_ID, tab)
        if not raw or len(raw) < 2:
            print(f"  Empty, skipping")
            continue
        if headers is None:
            headers = raw[0]
        rows = raw[1:]
        print(f"  {len(rows)} contacts")
        all_rows.extend(rows)
    return headers, all_rows


def filter_and_group(headers, rows):
    """Filter UAE-only contacts, group by domain/company."""
    col = {h: i for i, h in enumerate(headers)}

    def gv(row, name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    companies = defaultdict(lambda: {'uae': [], 'domain': '', 'name': '', 'score': 0})
    total = uae_count = 0

    for row in rows:
        total += 1
        domain = gv(row, 'Domain').lower()
        company = gv(row, 'Company')
        location = gv(row, 'Location')
        score = float(gv(row, 'Company Score') or '0')
        key = domain if domain else f"__name__{company.lower()}"

        companies[key]['domain'] = domain
        companies[key]['name'] = company
        companies[key]['score'] = max(companies[key]['score'], score)

        if is_uae_located(location):
            uae_count += 1
            companies[key]['uae'].append(row)

    print(f"\nTotal contacts: {total}")
    print(f"UAE-located: {uae_count}")
    print(f"Unique companies: {len(companies)}")
    print(f"Companies with UAE contacts: {sum(1 for c in companies.values() if c['uae'])}")
    print(f"Companies needing enrichment: {sum(1 for c in companies.values() if len(c['uae']) < MAX_PER_COMPANY and c['domain'])}")

    return companies, col


async def enrich_companies(companies, headers, col):
    """Use Apollo to find UAE-located decision-makers at companies with <3 UAE contacts."""
    apollo = ApolloService()

    # Sort by score (best companies first), filter to those needing contacts
    need_enrich = [
        (key, c) for key, c in companies.items()
        if len(c['uae']) < MAX_PER_COMPANY and c['domain'] and not key.startswith('__name__')
    ]
    need_enrich.sort(key=lambda x: -x[1]['score'])

    print(f"\n=== APOLLO ENRICHMENT ===")
    print(f"Companies to enrich: {len(need_enrich)}")
    print(f"Apollo credits estimate: ~{len(need_enrich) * 3} (3 per company)")

    enriched_count = 0
    apollo_contacts = 0
    errors = 0

    for i, (key, comp) in enumerate(need_enrich):
        domain = comp['domain']
        existing = len(comp['uae'])
        needed = MAX_PER_COMPANY - existing

        if i % 50 == 0 and i > 0:
            print(f"  Progress: {i}/{len(need_enrich)} companies, {apollo_contacts} contacts found, {errors} errors")

        try:
            # Search Apollo for decision-makers at this domain
            people = await apollo.enrich_by_domain(
                domain=domain,
                limit=min(needed + 2, 5),  # fetch a few extra to filter
                titles=DECISION_TITLES[:10],  # Apollo limits title count
            )

            found = 0
            for person in people:
                if found >= needed:
                    break

                # Check if UAE-located (Apollo returns city/state/country)
                raw = person.get('raw_data', {})
                city = (raw.get('city') or '').lower()
                state = (raw.get('state') or '').lower()
                country = (raw.get('country') or '').lower()
                full_loc = f"{city}, {state}, {country}"

                if not is_uae_located(full_loc):
                    continue

                # Build a row matching the verified tab format
                linkedin = person.get('linkedin_url', '')
                email = person.get('email', '')

                # Check dedup against existing UAE contacts
                existing_names = {r[col.get('First Name', 1)].lower() + ' ' + r[col.get('Last Name', 2)].lower()
                                  for r in comp['uae'] if len(r) > col.get('Last Name', 2)}
                name_check = f"{person.get('first_name', '').lower()} {person.get('last_name', '').lower()}"
                if name_check in existing_names:
                    continue

                # Build row in same format as verified tab
                new_row = [''] * len(headers)
                new_row[col.get('Rank', 0)] = ''
                new_row[col.get('First Name', 1)] = person.get('first_name', '')
                new_row[col.get('Last Name', 2)] = person.get('last_name', '')
                new_row[col.get('Email', 3)] = email
                new_row[col.get('Title', 4)] = person.get('job_title', '')
                new_row[col.get('Role Tier', 5)] = ''
                new_row[col.get('Company', 6)] = comp['name']
                new_row[col.get('Domain', 7)] = domain
                new_row[col.get('Location', 8)] = full_loc.title()
                new_row[col.get('LinkedIn URL', 9)] = linkedin
                new_row[col.get('Origin Signal', 10)] = 'Apollo UAE enrichment'
                if col.get('Company Score') is not None and col['Company Score'] < len(new_row):
                    new_row[col['Company Score']] = str(comp['score'])

                comp['uae'].append(new_row)
                found += 1
                apollo_contacts += 1

            if found > 0:
                enriched_count += 1

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error enriching {domain}: {e}")

        # Rate limit
        await asyncio.sleep(0.3)

    print(f"\n  Enrichment complete:")
    print(f"  Companies enriched: {enriched_count}")
    print(f"  New UAE contacts found: {apollo_contacts}")
    print(f"  Apollo credits used: {apollo.credits_used}")
    print(f"  Errors: {errors}")

    return companies


def write_final_tab(gs, companies, headers):
    """Write final merged list to new tab, capped at 3/company."""
    # Collect all UAE contacts, capped at 3/company, sorted by company score
    sorted_companies = sorted(companies.values(), key=lambda c: -c['score'])

    final_rows = []
    for comp in sorted_companies:
        for row in comp['uae'][:MAX_PER_COMPANY]:
            final_rows.append(row)

    # Re-rank
    rank_idx = 0  # Rank column
    for i, row in enumerate(final_rows):
        if len(row) > rank_idx:
            row[rank_idx] = str(i + 1)

    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f"UAE-PK FINAL {ts}"

    print(f"\n=== WRITING FINAL TAB ===")
    print(f"Tab: {tab_name}")
    print(f"Total contacts: {len(final_rows)}")
    print(f"Companies: {sum(1 for c in sorted_companies if c['uae'])}")

    # Create tab
    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name,
                  'gridProperties': {'rowCount': max(2500, len(final_rows) + 100)}}}}]}
        ).execute()
    except Exception as e:
        print(f"Tab creation warning: {e}")

    # Write in batches
    all_data = [headers] + final_rows
    batch_size = 500
    for i in range(0, len(all_data), batch_size):
        batch = all_data[i:i + batch_size]
        start = i + 1
        gs.sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{start}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()
        print(f"  Wrote rows {start}-{start + len(batch) - 1}")

    print(f"\nDone! {len(final_rows)} contacts in '{tab_name}'")
    print(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    return tab_name, len(final_rows)


async def main():
    gs = GoogleSheetsService()

    # Step 1: Read existing verified data
    headers, rows = read_verified_tabs(gs)
    if not headers:
        print("ERROR: No data!")
        return

    # Step 2: Filter UAE-only, group by company
    companies, col = filter_and_group(headers, rows)

    # Step 3: Enrich via Apollo
    companies = await enrich_companies(companies, headers, col)

    # Step 4: Write final merged tab
    write_final_tab(gs, companies, headers)


if __name__ == '__main__':
    asyncio.run(main())
