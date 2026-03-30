#!/usr/bin/env python3
"""
Score AU-PH and Arabic-SA corridors with RELAXED filters.
KPI: maximize target contacts in correct location.
Origin signal (Filipino/SA person in buyer country) is the primary qualifier.
Don't gate on website data — these are pre-qualified by diaspora signal.
"""
import sys
import os
import json
import csv
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, '/app')
from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

CORRIDORS = {
    'au-philippines': {
        'source_tab': 'AU-Philippines',
        'output_tab': 'AU-PH Targets',
        'talent_country': 'philippines',
        'buyer_signals': ['australia', 'sydney', 'melbourne', 'brisbane', 'perth',
                         'adelaide', 'canberra', 'gold coast', 'hobart', 'darwin',
                         'new south wales', 'victoria', 'queensland', 'western australia'],
        'exclude_locations': ['philippines', 'manila', 'cebu', 'davao', 'makati', 'quezon',
                             'india', 'mumbai', 'delhi', 'bangalore', 'indonesia', 'jakarta',
                             'pakistan', 'karachi', 'lahore'],
    },
    'arabic-southafrica': {
        'source_tab': 'Arabic-SouthAfrica',
        'output_tab': 'Arabic-SA Targets',
        'talent_country': 'south africa',
        'buyer_signals': ['qatar', 'doha', 'saudi', 'riyadh', 'jeddah', 'bahrain', 'manama',
                         'kuwait', 'oman', 'muscat', 'uae', 'dubai', 'abu dhabi',
                         'united arab', '\u0642\u0637\u0631', '\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629',
                         '\u0627\u0644\u0628\u062d\u0631\u064a\u0646', '\u0627\u0644\u0643\u0648\u064a\u062a',
                         '\u0639\u0645\u0627\u0646', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a',
                         '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a',
                         '\u0627\u0644\u0631\u064a\u0627\u0636'],
        'exclude_locations': ['south africa', 'johannesburg', 'cape town', 'durban', 'pretoria',
                             'india', 'mumbai', 'delhi', 'nigeria', 'lagos', 'kenya', 'nairobi',
                             'pakistan', 'karachi', 'lahore'],
    },
}

# Anti-titles (definitely not decision makers)
ANTI_TITLES = ['intern', 'student', 'trainee', 'junior', 'assistant', 'receptionist',
               'freelancer', 'freelance', 'volunteer', 'virtual assistant']

# Good titles (decision makers for payroll/operations)
GOOD_TITLES = {
    'T1': ['cfo', 'chief financial', 'vp finance', 'head of finance', 'finance director',
           'head of payroll', 'payroll manager', 'finance manager'],
    'T2': ['coo', 'chief operating', 'vp operations', 'head of operations', 'operations director'],
    'T3': ['chro', 'chief hr', 'vp hr', 'head of hr', 'head of people', 'hr director',
           'people operations', 'talent', 'human resources director'],
    'T4': ['ceo', 'founder', 'co-founder', 'managing director', 'general manager', 'owner',
           'president', 'partner', 'principal'],
    'T5': ['cto', 'vp engineering', 'head of technology', 'tech lead', 'engineering director'],
}

BLACKLIST_DOMAINS = {
    '500.co', 'google.com', 'facebook.com', 'meta.com', 'amazon.com', 'microsoft.com',
    'apple.com', 'linkedin.com', 'uber.com', 'airbnb.com', 'twitter.com', 'x.com',
}


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


def get_role_tier(title):
    t = title.lower()
    if any(a in t for a in ANTI_TITLES):
        return 99, 0
    for tier_name, keywords in GOOD_TITLES.items():
        if any(k in t for k in keywords):
            tier_num = int(tier_name[1])
            return tier_num, 10 - tier_num
    # Director/Head/VP not in specific category
    if any(k in t for k in ['director', 'head of', 'vp ', 'vice president', 'manager']):
        return 6, 4
    return 7, 2


def score_corridor(corridor_key, sheets):
    config = CORRIDORS[corridor_key]
    source_tab = config['source_tab']
    buyer_signals = config['buyer_signals']
    exclude_locs = config['exclude_locations']

    print(f"\n{'='*60}")
    print(f"CORRIDOR: {corridor_key.upper()}")
    print(f"{'='*60}")

    # Read contacts
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{source_tab}'!A1:Z30000"
    ).execute()
    rows = result.get('values', [])
    headers = rows[0]
    col = {h.strip(): i for i, h in enumerate(headers)}

    def gv(row, name):
        idx = col.get(name, -1)
        return (row[idx] or '').strip() if idx >= 0 and idx < len(row) else ''

    contacts = []
    for row in rows[1:]:
        contacts.append({
            'first_name': gv(row, 'First Name'),
            'last_name': gv(row, 'Last Name'),
            'email': gv(row, 'Email'),
            'title': gv(row, 'Title'),
            'company': gv(row, 'Company'),
            'domain': gv(row, 'Domain'),
            'location': gv(row, 'Location'),
            'linkedin_url': gv(row, 'LinkedIn URL'),
            'industry': gv(row, 'Industry'),
            'origin_score': gv(row, 'Origin Score'),
        })
    print(f"Total contacts: {len(contacts)}")

    # STEP 1: Location filter — MUST be in buyer country
    filtered = []
    excl_talent = excl_other = excl_empty = 0
    for c in contacts:
        loc = c['location'].lower()
        if not loc:
            excl_empty += 1
            continue
        if any(ex in loc for ex in exclude_locs):
            excl_talent += 1
            continue
        if any(s in loc for s in buyer_signals):
            filtered.append(c)
        else:
            excl_other += 1

    print(f"After location filter: {len(filtered)} (excl talent_country={excl_talent}, other={excl_other}, empty={excl_empty})")

    # STEP 2: Anti-title + blacklist filter only (RELAXED — no domain/website gate)
    clean = []
    bl_d = bl_t = bl_e = 0
    domain_counts = Counter(c['domain'].lower() for c in filtered if c['domain'])
    for c in filtered:
        d = c['domain'].lower().strip() if c['domain'] else ''
        if d in BLACKLIST_DOMAINS:
            bl_d += 1
            continue
        if d and domain_counts[d] >= 15:  # Enterprise: 15+ contacts same domain
            bl_e += 1
            continue
        tier, score = get_role_tier(c['title'])
        if tier == 99:
            bl_t += 1
            continue
        c['role_tier'] = tier
        c['role_score'] = score
        clean.append(c)

    print(f"After filters: {len(clean)} (blacklist={bl_d}, enterprise={bl_e}, anti-title={bl_t})")

    # STEP 3: Group by company, pick up to 3 per company, best roles first
    companies = defaultdict(list)
    for c in clean:
        d = c['domain'].lower().strip() if c['domain'] else ''
        key = d if d else f"__name__{c['company'].lower().strip()}"
        companies[key].append(c)

    print(f"Unique companies: {len(companies)}")

    selected = []
    seen_li = set()
    seen_names = set()

    # Sort companies by best contact role
    sorted_companies = sorted(companies.items(),
                              key=lambda x: min(c['role_tier'] for c in x[1]))

    for key, cc in sorted_companies:
        cc.sort(key=lambda c: (c['role_tier'], -int(c.get('origin_score') or '0')))
        picked = 0
        for c in cc:
            if picked >= 3:
                break
            li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
            name = f"{c['first_name']} {c['last_name']}".lower().strip()
            if li and li in seen_li:
                continue
            if name and name != ' ' and name in seen_names:
                continue

            origin = int(c.get('origin_score') or '0')
            selected.append({
                'rank': 0,
                'first_name': c['first_name'],
                'last_name': c['last_name'],
                'email': c.get('email', ''),
                'title': c['title'],
                'role_tier': f"T{c['role_tier']}",
                'company': c['company'],
                'domain': c.get('domain', ''),
                'location': c['location'],
                'linkedin_url': c.get('linkedin_url', ''),
                'origin_score': origin,
                'industry': c.get('industry', ''),
            })
            picked += 1
            if li:
                seen_li.add(li)
            if name and name != ' ':
                seen_names.add(name)

    for i, s in enumerate(selected):
        s['rank'] = i + 1

    print(f"Selected: {len(selected)} contacts from {len(companies)} companies")

    # STEP 4: Write to new tab
    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f"{config['output_tab']} {ts}"

    header = ['Rank', 'First Name', 'Last Name', 'Email', 'Title', 'Role Tier',
              'Company', 'Domain', 'Location', 'LinkedIn URL', 'Origin Score', 'Industry']
    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([s[k] for k in ['rank', 'first_name', 'last_name', 'email',
                                           'title', 'role_tier', 'company', 'domain',
                                           'location', 'linkedin_url', 'origin_score', 'industry']])

    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name,
                  'gridProperties': {'rowCount': max(5000, len(sheet_rows) + 100)}}}}]}
        ).execute()
    except Exception:
        pass

    for i in range(0, len(sheet_rows), 500):
        batch = sheet_rows[i:i + 500]
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{i + 1}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    # Stats
    print(f"\nRole distribution:")
    for tier in sorted(Counter(s['role_tier'] for s in selected)):
        cnt = sum(1 for s in selected if s['role_tier'] == tier)
        print(f"  {tier}: {cnt}")

    print(f"\nLocation distribution (top 10):")
    for loc, cnt in Counter(s['location'] for s in selected).most_common(10):
        print(f"  {cnt:>4}  {loc[:50]}")

    print(f"\nWrote to: '{tab_name}'")
    print(f"Total: {len(selected)} contacts")

    # Save JSON
    json_path = f'/tmp/{corridor_key.replace("-", "_")}_targets.json'
    json.dump(selected, open(json_path, 'w'), indent=2, ensure_ascii=False)
    print(f"JSON: {json_path}")

    return selected


def main():
    sheets = get_sheets_service()
    for corridor in CORRIDORS:
        score_corridor(corridor, sheets)


if __name__ == '__main__':
    main()
