#!/usr/bin/env python3
"""
UAE-Pakistan God Scorer — maximize real targets, remove only actual shit.

KEEP if: UAE-located + decision-maker title + not enterprise/competitor
REMOVE only: wrong location, enterprise mega-corps, competitors, anti-titles, PK-HQ companies

DO NOT remove for: missing domain, missing website, "wrong" surname, low origin score.
These are NOT disqualifiers — a company without a website still hires freelancers.
"""
import sys
import json
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, '/app')
from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-Pakistan'  # Main gathered tab with all contacts

UAE_KW = ['dubai', 'abu dhabi', 'sharjah', 'uae', 'united arab', 'ajman',
          'ras al', 'fujairah', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a',
          '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a']

EXCLUDE_LOCATIONS = ['pakistan', 'karachi', 'lahore', 'islamabad', 'rawalpindi',
                     'faisalabad', 'peshawar', 'multan',
                     'india', 'mumbai', 'delhi', 'bangalore', 'chennai', 'pune',
                     'noida', 'gurgaon', 'gurugram', 'hyderabad, india',
                     'nigeria', 'lagos', 'kenya', 'nairobi']

# Anti-titles: definitely not decision-makers
ANTI_TITLES = ['intern', 'student', 'trainee', 'junior', 'assistant to',
               'receptionist', 'freelancer', 'freelance', 'volunteer',
               'virtual assistant', ' va ', 'data entry']

# Enterprise mega-corps that won't use EasyStaff
ENTERPRISE_BLACKLIST = {
    # Tech giants
    'google.com', 'facebook.com', 'meta.com', 'amazon.com', 'microsoft.com',
    'apple.com', 'linkedin.com', 'uber.com', 'airbnb.com', 'twitter.com', 'x.com',
    'oracle.com', 'ibm.com', 'sap.com', 'salesforce.com', 'cisco.com', 'intel.com',
    'nvidia.com', 'samsung.com', 'dell.com', 'hp.com', 'vmware.com', 'adobe.com',
    'mastercard.com', 'visa.com', 'paypal.com',
    # Big consulting
    'accenture.com', 'deloitte.com', 'pwc.com', 'ey.com', 'kpmg.com',
    'mckinsey.com', 'bcg.com', 'bain.com',
    # Banks
    'jpmorgan.com', 'goldmansachs.com', 'morganstanley.com', 'citi.com',
    'hsbc.com', 'barclays.com', 'standardchartered.com',
    # UAE mega-corps
    'adnoc.ae', 'adnocdrilling.ae', 'emirates.com', 'etihad.com', 'emaar.com',
    'dp-world.com', 'masdar.ae', 'mubadala.com',
    # Competitors / payroll companies
    'deel.com', 'remote.com', 'papayaglobal.com', 'oysterhr.com', 'letsdeel.com',
    'remotepass.com', 'multiplier.com', 'globalization-partners.com',
    'velocity-global.com', 'rippling.com', 'gusto.com', 'adp.com',
    # India outsourcing giants (PK-adjacent, already have payroll sorted)
    'infosys.com', 'tcs.com', 'wipro.com', 'hcl.com', 'techm.com',
    'cognizant.com', 'mindtree.com', 'mphasis.com',
    # From v7 verified exclude list
    'softmindsol.com', 'wpexperts.io', 'abhi.co', 'allomate.com', 'mnadigital.io',
    'ovexbee.com', 'daairah.com', 'techdigital.biz', 'greencorebeauty.com',
    'dynasoftcloud.com', 'pxgeo.com', 'ikragcae.com',
}

# PK-HQ domains (company is based IN Pakistan, not a UAE company hiring PK talent)
PK_HQ_SIGNALS = ['.pk', 'pakistan', 'lahore', 'karachi', 'islamabad']


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
    # T1: Finance/Payroll (best for EasyStaff)
    if any(k in t for k in ['cfo', 'chief financial', 'vp finance', 'head of finance',
                             'finance director', 'payroll', 'finance manager', 'controller']):
        return 1, 10
    # T2: Operations
    if any(k in t for k in ['coo', 'chief operating', 'vp operations', 'head of operations',
                             'operations director', 'operations manager']):
        return 2, 9
    # T3: HR/People
    if any(k in t for k in ['chro', 'chief hr', 'chief people', 'vp hr', 'head of hr',
                             'head of people', 'hr director', 'talent', 'human resources director']):
        return 3, 8
    # T4: CEO/Founder
    if any(k in t for k in ['ceo', 'founder', 'co-founder', 'cofounder', 'managing director',
                             'general manager', 'owner', 'president', 'partner', 'principal']):
        return 4, 7
    # T5: Tech leadership
    if any(k in t for k in ['cto', 'vp engineering', 'head of technology', 'head of engineering',
                             'engineering director', 'tech lead', 'it director']):
        return 5, 6
    # T6: Director/Head (general)
    if any(k in t for k in ['director', 'head of', 'vp ', 'vice president']):
        return 6, 5
    # T7: Manager
    if any(k in t for k in ['manager', 'lead', 'senior']):
        return 7, 3
    return 8, 1


def main():
    sheets = get_sheets_service()

    print(f'Reading {SOURCE_TAB}...')
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SOURCE_TAB}'!A1:Z30000"
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
            'search_type': gv(row, 'Search Type'),
            'schools': gv(row, 'Schools (from Clay)'),
            'match_reason': gv(row, 'Name Match Reason'),
        })
    print(f'Total raw: {len(contacts)}')

    # Load already-scored contacts from existing campaign tab to skip them
    already_scored_li = set()
    for existing_tab in ['UAE-PK FINAL 0316_1035', 'UAE-PK VERIFIED 0316_0854']:
        try:
            ex = sheets.spreadsheets().values().get(
                spreadsheetId=SHEET_ID,
                range=f"'{existing_tab}'!A1:Z20000"
            ).execute()
            ex_rows = ex.get('values', [])
            if ex_rows:
                ex_headers = ex_rows[0]
                ex_col = {h.strip(): i for i, h in enumerate(ex_headers)}
                li_idx = ex_col.get('LinkedIn URL', 9)
                for r in ex_rows[1:]:
                    li = (r[li_idx] if li_idx < len(r) else '').strip().lower().rstrip('/')
                    if li:
                        already_scored_li.add(li)
        except Exception:
            pass
    print(f'Already scored (in campaign): {len(already_scored_li)}')

    # Filter to only NEW contacts
    new_contacts = []
    for c in contacts:
        li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
        if li and li in already_scored_li:
            continue
        new_contacts.append(c)
    contacts = new_contacts
    print(f'New contacts to score: {len(contacts)}')

    # ─── STEP 1: LOCATION FILTER ───
    in_uae = []
    excl = Counter()
    for c in contacts:
        loc = c['location'].lower()
        if not loc:
            excl['empty_location'] += 1
            continue
        if any(x in loc for x in EXCLUDE_LOCATIONS):
            excl['talent_country'] += 1
            continue
        if any(x in loc for x in UAE_KW):
            in_uae.append(c)
        else:
            excl['other_country'] += 1

    print(f'\nStep 1 — Location: {len(in_uae)} in UAE')
    for k, v in excl.most_common():
        print(f'  Excluded {k}: {v}')

    # ─── STEP 2: REMOVE REAL SHIT ONLY ───
    clean = []
    rm = Counter()
    domain_counts = Counter(c['domain'].lower() for c in in_uae if c['domain'])

    for c in in_uae:
        d = c['domain'].lower().strip() if c['domain'] else ''

        # Enterprise blacklist
        if d in ENTERPRISE_BLACKLIST:
            rm['enterprise_blacklist'] += 1
            continue

        # Domain has 15+ contacts = enterprise (internal hiring team, not EasyStaff target)
        if d and domain_counts[d] >= 15:
            rm['enterprise_domain_15+'] += 1
            continue

        # PK-HQ company (based in Pakistan, not UAE company hiring PK talent)
        if d and any(d.endswith(sig) for sig in ['.pk']):
            rm['pk_domain'] += 1
            continue

        # Anti-title
        tier, score = get_role_tier(c['title'])
        if tier == 99:
            rm['anti_title'] += 1
            continue

        # Empty title
        if not c['title'].strip():
            rm['empty_title'] += 1
            continue

        c['role_tier'] = tier
        c['role_score'] = score
        clean.append(c)

    print(f'\nStep 2 — Clean: {len(clean)} (removed {sum(rm.values())})')
    for k, v in rm.most_common():
        print(f'  {k}: {v}')

    # ─── STEP 3: GROUP BY COMPANY, PICK BEST 3 ───
    companies = defaultdict(list)
    for c in clean:
        d = c['domain'].lower().strip() if c['domain'] else ''
        key = d if d else f"__name__{c['company'].lower().strip()}"
        companies[key].append(c)

    print(f'\nStep 3 — Companies: {len(companies)}')

    selected = []
    seen_li = set()
    seen_names = set()

    for key, cc in companies.items():
        # Sort: best role tier first, then highest origin score
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
            st = c.get('search_type', '')

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
                'origin_signal': c.get('match_reason', '')[:60],
                'search_type': st,
                'schools': c.get('schools', ''),
                'industry': c.get('industry', ''),
            })
            picked += 1
            if li:
                seen_li.add(li)
            if name and name != ' ':
                seen_names.add(name)

    for i, s in enumerate(selected):
        s['rank'] = i + 1

    print(f'\nStep 3 — Selected: {len(selected)} contacts')

    # ─── STATS ───
    print(f'\nRole distribution:')
    for tier in sorted(Counter(s['role_tier'] for s in selected)):
        cnt = sum(1 for s in selected if s['role_tier'] == tier)
        print(f'  {tier}: {cnt}')

    print(f'\nSearch type distribution:')
    for st, cnt in Counter(s['search_type'] for s in selected).most_common():
        print(f'  {st or "(unknown)"}: {cnt}')

    print(f'\nOrigin score distribution:')
    for o, cnt in sorted(Counter(s['origin_score'] for s in selected).items()):
        print(f'  {o}: {cnt}')

    print(f'\nLocation (top 5):')
    for loc, cnt in Counter(s['location'] for s in selected).most_common(5):
        print(f'  {cnt:>5}  {loc[:50]}')

    # ─── STEP 4: WRITE ───
    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f'UAE-PK GOD SCORED {ts}'

    header = ['Rank', 'First Name', 'Last Name', 'Email', 'Title', 'Role Tier',
              'Company', 'Domain', 'Location', 'LinkedIn URL', 'Origin Score',
              'Origin Signal', 'Search Type', 'Schools', 'Industry']
    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([s[k] for k in ['rank', 'first_name', 'last_name', 'email',
                                           'title', 'role_tier', 'company', 'domain',
                                           'location', 'linkedin_url', 'origin_score',
                                           'origin_signal', 'search_type', 'schools', 'industry']])

    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name,
                  'gridProperties': {'rowCount': max(10000, len(sheet_rows) + 100)}}}}]}
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
        print(f'  Wrote rows {i+1}-{i+len(batch)}')

    # Save JSON
    json.dump(selected, open('/tmp/uae_pk_god_scored.json', 'w'), indent=2, ensure_ascii=False)

    print(f'\n{"="*60}')
    print(f'RESULT: {len(selected)} contacts from {len(companies)} companies')
    print(f'Tab: {tab_name}')
    print(f'Pipeline: {len(contacts)} raw -> {len(in_uae)} UAE -> {len(clean)} clean -> {len(selected)} selected (3/company)')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
