#!/usr/bin/env python3
"""Spot-check UAE-PK GOD SCORED 10K contacts in batches."""
import sys, random
from collections import Counter
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
TAB = 'UAE-PK GOD SCORED 0316_1856'

UAE_KW = ['dubai', 'abu dhabi', 'sharjah', 'uae', 'united arab', 'ajman',
          'ras al', 'fujairah', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a',
          '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a']
BAD_LOC = ['pakistan', 'karachi', 'lahore', 'islamabad', 'india', 'mumbai',
           'delhi', 'bangalore', 'nigeria', 'kenya']
ENTERPRISE_DOMAINS = {'google.com', 'facebook.com', 'meta.com', 'amazon.com',
                      'microsoft.com', 'apple.com', 'linkedin.com', 'oracle.com',
                      'adnoc.ae', 'emirates.com', 'deel.com', 'remote.com'}
ANTI_TITLES = ['intern', 'student', 'trainee', 'virtual assistant', 'freelance']

gs = GoogleSheetsService()
raw = gs.read_sheet_raw(SHEET_ID, TAB)
headers = raw[0]
rows = raw[1:]
col = {h: i for i, h in enumerate(headers)}

print(f'Total: {len(rows)}')

# ─── AUTOMATED CHECKS ───
issues = {
    'wrong_location': [],
    'bad_location_leaked': [],
    'enterprise_leaked': [],
    'anti_title_leaked': [],
    'empty_title': [],
    'empty_name': [],
    'empty_linkedin': [],
    'duplicate_linkedin': [],
}

seen_li = set()
for i, row in enumerate(rows):
    def g(name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    loc = g('Location').lower()
    domain = g('Domain').lower()
    title = g('Title').lower()
    li = g('LinkedIn URL').lower().rstrip('/')
    name = g('First Name') + ' ' + g('Last Name')

    # Wrong location
    if not any(k in loc for k in UAE_KW):
        issues['wrong_location'].append(f'Row {i+2}: {name} | {loc}')

    # Bad location leaked
    if any(k in loc for k in BAD_LOC):
        issues['bad_location_leaked'].append(f'Row {i+2}: {name} | {loc}')

    # Enterprise leaked
    if domain in ENTERPRISE_DOMAINS:
        issues['enterprise_leaked'].append(f'Row {i+2}: {name} | {domain}')

    # Anti-title leaked
    if any(a in title for a in ANTI_TITLES):
        issues['anti_title_leaked'].append(f'Row {i+2}: {name} | {title}')

    # Empty fields
    if not g('Title'):
        issues['empty_title'].append(f'Row {i+2}: {name}')
    if not g('First Name') or not g('Last Name'):
        issues['empty_name'].append(f'Row {i+2}: {g("First Name")} {g("Last Name")}')
    if not li:
        issues['empty_linkedin'].append(f'Row {i+2}: {name}')

    # Duplicate LinkedIn
    if li and li in seen_li:
        issues['duplicate_linkedin'].append(f'Row {i+2}: {name} | {li[:50]}')
    if li:
        seen_li.add(li)

print('\n=== AUTOMATED ISSUE SCAN ===')
for issue, items in issues.items():
    print(f'{issue}: {len(items)}')
    for item in items[:3]:
        print(f'  {item}')
    if len(items) > 3:
        print(f'  ... +{len(items)-3} more')

# ─── RANDOM SPOT CHECK: 3 batches of 10 ───
print('\n=== RANDOM SPOT CHECK (30 contacts) ===')
sample = random.sample(rows, min(30, len(rows)))

for batch_num in range(3):
    batch = sample[batch_num*10:(batch_num+1)*10]
    print(f'\n--- Batch {batch_num+1} ---')
    for row in batch:
        def g(name):
            idx = col.get(name, -1)
            return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

        fn = g('First Name')
        ln = g('Last Name')
        title = g('Title')[:40]
        company = g('Company')[:25]
        loc = g('Location')[:35]
        domain = g('Domain')
        origin = g('Origin Score')
        st = g('Search Type')[:15]
        print(f'  {fn:12s} {ln:18s} | {title:40s} | {company:25s} | {loc:35s} | O={origin} {st}')

# ─── AGGREGATE STATS ───
print('\n=== AGGREGATE QUALITY ===')

# Companies with 4+ contacts (should be 0 — cap is 3)
domain_idx = col.get('Domain', 7)
company_idx = col.get('Company', 6)
company_counts = Counter()
for row in rows:
    d = (row[domain_idx] if domain_idx < len(row) else '').strip().lower()
    c = (row[company_idx] if company_idx < len(row) else '').strip().lower()
    key = d if d else f'__name__{c}'
    company_counts[key] += 1

over_3 = [(k, v) for k, v in company_counts.items() if v > 3]
print(f'Companies with >3 contacts: {len(over_3)}')
for k, v in sorted(over_3, key=lambda x: -x[1])[:5]:
    print(f'  {v}x  {k}')

# Domain distribution
no_domain = sum(1 for r in rows if not (r[domain_idx] if domain_idx < len(r) else '').strip())
print(f'\nNo domain: {no_domain}/{len(rows)} ({no_domain*100/len(rows):.0f}%)')

# .pk domains that leaked
pk_domains = sum(1 for r in rows if (r[domain_idx] if domain_idx < len(r) else '').strip().lower().endswith('.pk'))
print(f'.pk domains: {pk_domains}')

# India .in domains
in_domains = sum(1 for r in rows if (r[domain_idx] if domain_idx < len(r) else '').strip().lower().endswith('.in'))
print(f'.in domains: {in_domains}')

total_issues = sum(len(v) for v in issues.values())
print(f'\nTOTAL ISSUES: {total_issues}/{len(rows)} ({total_issues*100/len(rows):.1f}%)')
