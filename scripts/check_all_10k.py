#!/usr/bin/env python3
"""
Check ALL 10K UAE-PK contacts. Flag every issue.
Output: JSON with all contacts + flags, summary stats.
"""
import sys, json
from collections import Counter, defaultdict
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
TAB = 'UAE-PK GOD SCORED 0316_1856'

# ─── BLACKLISTS ───

ENTERPRISE_DOMAINS = {
    # Tech
    'google.com', 'facebook.com', 'meta.com', 'amazon.com', 'microsoft.com',
    'apple.com', 'linkedin.com', 'uber.com', 'airbnb.com', 'oracle.com',
    'ibm.com', 'sap.com', 'salesforce.com', 'cisco.com', 'intel.com',
    'nvidia.com', 'samsung.com', 'dell.com', 'adobe.com', 'mastercard.com',
    'visa.com', 'paypal.com', 'stripe.com', 'vmware.com',
    # Consulting
    'accenture.com', 'deloitte.com', 'pwc.com', 'ey.com', 'kpmg.com',
    'mckinsey.com', 'bcg.com', 'bain.com',
    # Banks
    'jpmorgan.com', 'goldmansachs.com', 'morganstanley.com', 'citi.com',
    'hsbc.com', 'barclays.com', 'standardchartered.com', 'ubs.com',
    # UAE mega-corps
    'adnoc.ae', 'adnocdrilling.ae', 'emirates.com', 'etihad.com', 'emaar.com',
    'dp-world.com', 'masdar.ae', 'mubadala.com', 'adq.ae', 'adia.ae',
    'dewa.gov.ae', 'dubaiholding.com', 'meraas.com', 'aldar.com',
    'etisalat.ae', 'du.ae', 'enbd.com', 'adib.ae', 'fab.com',
    'rakbank.ae', 'cbd.ae', 'mashreqbank.com', 'nbad.com',
    # Saudi mega-corps
    'aramco.com', 'sabic.com', 'stc.com.sa', 'neom.com',
    # Competitors
    'deel.com', 'remote.com', 'papayaglobal.com', 'oysterhr.com',
    'remotepass.com', 'multiplier.com', 'velocity-global.com',
    'rippling.com', 'gusto.com', 'adp.com', 'paychex.com',
    'globalization-partners.com', 'letsdeel.com',
    # India IT giants
    'infosys.com', 'tcs.com', 'wipro.com', 'hcl.com', 'techm.com',
    'cognizant.com', 'mindtree.com', 'mphasis.com', 'lti.com',
    # Other enterprise
    'siemens.com', 'ge.com', 'bosch.com', 'schneider-electric.com',
    'abb.com', 'honeywell.com', 'johnson-controls.com',
    'unilever.com', 'nestle.com', 'pg.com', 'loreal.com',
    'shell.com', 'bp.com', 'totalenergies.com', 'chevron.com',
    'exxonmobil.com', 'halliburton.com', 'schlumberger.com',
    'hilton.com', 'marriott.com', 'ihg.com', 'accor.com', 'hyatt.com',
    'dhl.com', 'fedex.com', 'ups.com', 'maersk.com',
}

# Recruitment/staffing — they're competitors not targets
RECRUITMENT_KEYWORDS = [
    'recruitment', 'staffing', 'headhunt', 'talent acquisition agency',
    'executive search', 'manpower', 'hr consultancy', 'placement',
    'recruiting firm', 'search firm', 'employment agency',
]

# Government — won't use EasyStaff
GOV_KEYWORDS = [
    'government', 'ministry', 'municipality', 'authority', 'department of',
    'federal', 'police', 'military', 'army', 'navy', 'defence',
    'embassy', 'consulate', 'public sector',
]

# Anti-titles
ANTI_TITLES = [
    'intern', 'student', 'trainee', 'junior', 'assistant to',
    'receptionist', 'freelancer', 'freelance', 'volunteer',
    'virtual assistant', 'data entry', 'graphic designer',
    'photographer', 'videographer', 'content writer',
    'social media manager', 'influencer', 'blogger',
]

# Non-decision-maker titles (not worth emailing)
WEAK_TITLES = [
    'accountant', 'bookkeeper', 'analyst', 'coordinator',
    'executive', 'officer', 'specialist', 'associate',
    'consultant', 'advisor', 'agent',
]

gs = GoogleSheetsService()
raw = gs.read_sheet_raw(SHEET_ID, TAB)
headers = raw[0]
rows = raw[1:]
col = {h: i for i, h in enumerate(headers)}

print(f'Checking ALL {len(rows)} contacts...')

flags = defaultdict(list)  # flag_type -> list of row details
clean_count = 0
flagged_rows = set()

for i, row in enumerate(rows):
    def g(name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    row_num = i + 2
    fn = g('First Name')
    ln = g('Last Name')
    name = f'{fn} {ln}'.strip()
    title = g('Title')
    company = g('Company')
    domain = g('Domain').lower()
    loc = g('Location')
    li = g('LinkedIn URL')
    origin = g('Origin Score')
    search_type = g('Search Type')
    industry = g('Industry')
    row_flags = []

    # 1. Enterprise domain
    if domain in ENTERPRISE_DOMAINS:
        row_flags.append('ENTERPRISE')
        flags['enterprise'].append(f'{name} | {company} | {domain}')

    # 2. Recruitment/staffing company (competitor)
    comp_lower = company.lower()
    title_lower = title.lower()
    if any(k in comp_lower for k in RECRUITMENT_KEYWORDS):
        row_flags.append('RECRUITMENT_COMPANY')
        flags['recruitment_company'].append(f'{name} | {company}')

    # 3. Government
    if any(k in comp_lower for k in GOV_KEYWORDS) or domain.endswith('.gov.ae') or domain.endswith('.gov'):
        row_flags.append('GOVERNMENT')
        flags['government'].append(f'{name} | {company} | {domain}')

    # 4. .pk domain (Pakistan HQ)
    if domain.endswith('.pk'):
        row_flags.append('PK_DOMAIN')
        flags['pk_domain'].append(f'{name} | {company} | {domain}')

    # 5. .in domain (India HQ — questionable)
    if domain.endswith('.in') and not domain.endswith('linkedin.in'):
        row_flags.append('IN_DOMAIN')
        flags['in_domain'].append(f'{name} | {company} | {domain}')

    # 6. Anti-title
    if any(a in title_lower for a in ANTI_TITLES):
        row_flags.append('ANTI_TITLE')
        flags['anti_title'].append(f'{name} | {title}')

    # 7. Weak title (not decision-maker enough)
    has_strong = any(k in title_lower for k in [
        'ceo', 'cfo', 'coo', 'cto', 'cmo', 'cpo', 'chief', 'founder',
        'co-founder', 'managing director', 'general manager', 'owner',
        'president', 'partner', 'principal', 'vp', 'vice president',
        'director', 'head of', 'head',
    ])
    if not has_strong and any(w in title_lower for w in WEAK_TITLES):
        row_flags.append('WEAK_TITLE')
        flags['weak_title'].append(f'{name} | {title} | {company}')

    # 8. Empty/garbage name
    if not fn or not ln or len(name) < 3:
        row_flags.append('BAD_NAME')
        flags['bad_name'].append(f'Row {row_num}: "{fn}" "{ln}"')

    # 9. Name has garbage characters
    if any(c in name for c in [')', '(', '@', '#', '®', '™', 'CIPD', 'CHRMP', 'MIEMA', 'PHRi', 'CIWFM', 'MBA', 'CPA', 'PMP']):
        row_flags.append('CREDENTIAL_IN_NAME')
        flags['credential_in_name'].append(f'{name} | {title}')

    # 10. Company name suggests Pakistan HQ
    pk_company_signals = ['lahore', 'karachi', 'islamabad', 'rawalpindi', 'pakistan',
                          'peshawar', 'faisalabad']
    if any(s in comp_lower for s in pk_company_signals):
        row_flags.append('PK_COMPANY_NAME')
        flags['pk_company_name'].append(f'{name} | {company}')

    # 11. Company name suggests India HQ
    india_company_signals = ['mumbai', 'delhi', 'bangalore', 'hyderabad, india',
                             'chennai', 'pune', 'noida', 'india pvt', 'india ltd',
                             'india private']
    if any(s in comp_lower for s in india_company_signals):
        row_flags.append('INDIA_COMPANY_NAME')
        flags['india_company_name'].append(f'{name} | {company}')

    # 12. Very short company name (might be garbage)
    if len(company) < 2:
        row_flags.append('EMPTY_COMPANY')
        flags['empty_company'].append(f'{name} | company="{company}"')

    # 13. Title is just credentials/abbreviations
    if title and len(title) < 4:
        row_flags.append('SHORT_TITLE')
        flags['short_title'].append(f'{name} | title="{title}"')

    # 14. "Entrepreneur" with no company — likely not real target
    if 'entrepreneur' in title_lower and not domain:
        row_flags.append('ENTREPRENEUR_NO_DOMAIN')
        flags['entrepreneur_no_domain'].append(f'{name} | {title} | {company}')

    if row_flags:
        flagged_rows.add(i)
    else:
        clean_count += 1

# ─── SUMMARY ───
print(f'\n{"="*70}')
print(f'RESULTS: {len(rows)} contacts checked')
print(f'{"="*70}')
print(f'CLEAN: {clean_count} ({clean_count*100/len(rows):.1f}%)')
print(f'FLAGGED: {len(flagged_rows)} ({len(flagged_rows)*100/len(rows):.1f}%)')

print(f'\n--- FLAGS BY TYPE ---')
# Severity: REMOVE vs REVIEW
remove_flags = ['enterprise', 'recruitment_company', 'government', 'pk_domain', 'anti_title', 'pk_company_name']
review_flags = ['in_domain', 'weak_title', 'bad_name', 'credential_in_name', 'india_company_name',
                'empty_company', 'short_title', 'entrepreneur_no_domain']

print(f'\nSHOULD REMOVE:')
remove_total = 0
for flag_type in remove_flags:
    items = flags.get(flag_type, [])
    if items:
        print(f'  {flag_type}: {len(items)}')
        for item in items[:5]:
            print(f'    {item}')
        if len(items) > 5:
            print(f'    ... +{len(items)-5} more')
        remove_total += len(items)

print(f'\n  TOTAL TO REMOVE: {remove_total}')

print(f'\nREVIEW (borderline):')
review_total = 0
for flag_type in review_flags:
    items = flags.get(flag_type, [])
    if items:
        print(f'  {flag_type}: {len(items)}')
        for item in items[:3]:
            print(f'    {item}')
        if len(items) > 3:
            print(f'    ... +{len(items)-3} more')
        review_total += len(items)

print(f'\n  TOTAL TO REVIEW: {review_total}')
print(f'\nFINAL CLEAN ESTIMATE: {clean_count} contacts ({clean_count*100/len(rows):.1f}%)')

# Save full flagged list
flagged_output = []
for i, row in enumerate(rows):
    if i in flagged_rows:
        def g(name):
            idx = col.get(name, -1)
            return (row[idx] if idx >= 0 and idx < len(row) else '').strip()
        flagged_output.append({
            'row': i + 2,
            'name': g('First Name') + ' ' + g('Last Name'),
            'title': g('Title'),
            'company': g('Company'),
            'domain': g('Domain'),
            'location': g('Location'),
        })

json.dump(flagged_output, open('/tmp/uae_pk_flagged.json', 'w'), indent=2, ensure_ascii=False)
print(f'\nFlagged contacts saved: /tmp/uae_pk_flagged.json')
