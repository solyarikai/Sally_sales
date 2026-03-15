#!/usr/bin/env python3
"""
UAE-Pakistan Priority Scoring v3 — Enterprise-filtered, company-centric.

Key changes from v2:
- Enterprise blacklist (banks, airlines, government, Big4, FAANG)
- Contact-count-based enterprise detection (10+ contacts = exclude)
- Company-centric scoring (group by domain, score company, select best contacts)
- Multiplicative model: Pakistan connection x Company fit x Role authority
- Role tier selection: max 3 contacts per company
- Detailed business-case reasoning

Usage: docker exec leadgen-backend python3 /tmp/uae_pk_v3_score.py
"""

import json
import io
import sys
import asyncio
import time
import re
import hashlib
from collections import Counter, defaultdict

from google.oauth2 import service_account
from googleapiclient.discovery import build
import httpx

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-Pakistan - New Only'
OUTPUT_TAB = 'UAE-Pakistan Priority 2000'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# ============================================================
# ENTERPRISE BLACKLIST
# ============================================================
ENTERPRISE_BLACKLIST_DOMAINS = {
    # Banks & Financial
    'sc.com', 'bankfab.com', 'huawei.com', 'emiratesnbd.com', 'deloitte.com',
    'mashreq.com', 'alfuttaim.com', 'dib.ae', 'adcb.com', 'enbd.com',
    'pwc.com', 'ey.com', 'kpmg.com', 'mckinsey.com', 'bcg.com',
    'accenture.com', 'amazon.com', 'google.com', 'microsoft.com', 'meta.com',
    'oracle.com', 'ibm.com', 'samsung.com', 'siemens.com', 'bosch.com',
    'emirates.com', 'etihad.com', 'flydubai.com', 'dnata.com',
    'adnoc.ae', 'aramco.com', 'sabic.com', 'taqa.com',
    'emaar.com', 'damac.com', 'nakheel.com', 'aldar.com',
    'du.ae', 'etisalat.ae', 'e-and.com',
    'careem.com', 'uber.com', 'noon.com', 'souq.com',
    'hsbc.com', 'citibank.com', 'jpmorgan.com', 'goldmansachs.com',
    'barclays.com', 'bnpparibas.com', 'deutschebank.com',
    'unilever.com', 'nestle.com', 'pepsico.com', 'cocacola.com',
    'procter.com', 'pg.com', 'jnj.com', 'pfizer.com', 'novartis.com',
    # UAE-specific large entities
    'rakbank.ae', 'dubaiholding.com', 'sbp.org.pk', 'positivity.org',
    'damacproperties.com', 'dwtc.com', 'dpworld.com', 'rta.ae',
    'azizidevelopments.com', 'confidential.careers',
    'majid-al-futtaim.com', 'maf.ae', 'jumeirah.com', 'meraas.com',
    'dubaiproperties.ae', 'tecom.ae', 'difc.ae',
    'nbad.com', 'adib.ae', 'cbd.ae', 'fab.com',
    'etisalatdigital.com', 'du.com',
    'ge.com', 'honeywell.com', 'schneider-electric.com', 'abb.com',
    'shell.com', 'bp.com', 'totalenergies.com', 'chevron.com',
    'bain.com', 'oliverwyman.com', 'rolandberger.com',
    'bat.com', 'bat.co.uk',  # British American Tobacco
    'morganstanley.com', 'credit-suisse.com', 'ubs.com',
    'gartner.com', 'forrester.com',
    'apple.com', 'netflix.com', 'salesforce.com', 'adobe.com', 'intel.com',
    'cisco.com', 'vmware.com', 'dell.com', 'hp.com', 'lenovo.com',
    # Pharma & large corps that slipped through
    'novonordisk.com', 'astrazeneca.com', 'roche.com', 'sanofi.com',
    'gsk.com', 'merck.com', 'abbvie.com', 'bayer.com',
    'hubpower.com',  # Hub Power Company (Pakistan utility)
    'islamic-relief.org',  # Large NGO
    'seera.sa',  # Seera Group (1000+ employees, travel conglomerate)
}

ENTERPRISE_BLACKLIST_KEYWORDS = [
    'bank', 'banking', 'insurance', 'reinsurance',
    'airline', 'airways',
    'petroleum', 'oil & gas', 'oil and gas',
    'government', 'ministry', 'authority', 'municipality',
    'university', 'college', 'school of',
    'hospital', 'healthcare system',
    'armed forces', 'military', 'police', 'navy', 'army',
    'central bank', 'reserve bank',
    'stock exchange', 'securities commission',
]

# Shared hosting / platform domains — treat as no-domain
SHARED_HOSTING_DOMAINS = {
    'vercel.app', 'netlify.app', 'herokuapp.com', 'github.io', 'gitlab.io',
    'web.app', 'firebaseapp.com', 'azurewebsites.net', 'cloudfront.net',
    'wordpress.com', 'wixsite.com', 'squarespace.com', 'blogspot.com',
    'shopify.com', 'myshopify.com', 'godaddysites.com',
    'outlook.com', 'gmail.com', 'yahoo.com', 'hotmail.com',
    'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'google.com', 'apple.com',  # Already in enterprise list but just in case
}

# ============================================================
# ROLE TIERS
# ============================================================
ROLE_TIER_1_KEYWORDS = [
    'cfo', 'chief financial', 'finance director', 'director of finance',
    'head of finance', 'vp finance', 'vice president finance',
    'payroll', 'controller', 'chief accountant', 'treasurer',
    'financial controller', 'head of payments', 'director finance',
]
ROLE_TIER_2_KEYWORDS = [
    'coo', 'chief operating', 'operations director', 'director of operations',
    'head of operations', 'vp operations', 'vice president operations',
    'hr director', 'director of hr', 'head of hr', 'head of people',
    'chief people', 'chief human', 'vp hr', 'vice president hr',
    'procurement', 'head of procurement', 'director procurement',
    'people operations', 'people & culture',
]
ROLE_TIER_3_KEYWORDS = [
    'ceo', 'chief executive', 'founder', 'co-founder', 'cofounder',
    'owner', 'managing director', 'general manager', 'president',
    'country manager', 'regional manager', 'regional director',
    'managing partner', 'senior partner', 'partner',
]
ROLE_TIER_4_KEYWORDS = [
    'cto', 'chief technology', 'vp engineering', 'head of engineering',
    'director of engineering', 'bd director', 'business development director',
    'head of sales', 'sales director', 'commercial director',
    'head of business', 'director business development',
]

ANTI_TITLES = [
    'intern', 'student', 'freelanc', 'looking for', 'seeking',
    'unemployed', 'open to work', 'job seek', 'junior developer',
    'associate', 'executive assistant', 'receptionist', 'clerk',
    'trainee', 'apprentice',
]

# ============================================================
# INDUSTRY DETECTION
# ============================================================
INDUSTRY_KEYWORDS = {
    'outsourcing': ['outsourc', 'bpo', 'offshoring', 'nearshoring'],
    'staffing': ['staffing', 'recruitment', 'talent acqui', 'headhunt', 'hiring'],
    'software': ['software', 'saas', 'app develop', 'web develop', 'mobile develop'],
    'technology': ['technology', 'tech company', 'it company', 'information tech'],
    'it_services': ['it services', 'it solutions', 'managed services', 'it consult'],
    'consulting': ['consulting', 'consultancy', 'advisory', 'management consult'],
    'digital_agency': ['digital agency', 'creative agency', 'design agency', 'web agency'],
    'marketing_agency': ['marketing', 'advertising', 'media agency', 'pr agency', 'digital marketing'],
    'fintech': ['fintech', 'financial tech', 'payment', 'crypto', 'blockchain', 'defi'],
    'ecommerce': ['ecommerce', 'e-commerce', 'online retail', 'marketplace'],
    'professional_services': ['professional service', 'legal', 'accounting', 'audit'],
    'construction': ['construction', 'building', 'contracting', 'civil engineer'],
    'real_estate': ['real estate', 'property', 'realty', 'broker'],
    'trading': ['trading', 'import', 'export', 'commodit'],
    'logistics': ['logistics', 'freight', 'shipping', 'supply chain', 'courier'],
    'food': ['food', 'restaurant', 'catering', 'f&b', 'hospitality'],
    'healthcare': ['healthcare', 'medical', 'pharma', 'clinic', 'health'],
    'education': ['education', 'training', 'academy', 'learning', 'edtech'],
}

INDUSTRY_SCORES = {
    'outsourcing': 100, 'staffing': 95, 'software': 90, 'it_services': 85,
    'technology': 85, 'saas': 80, 'consulting': 75, 'digital_agency': 75,
    'marketing_agency': 70, 'fintech': 70, 'ecommerce': 60,
    'professional_services': 60, 'logistics': 50, 'food': 45,
    'construction': 40, 'real_estate': 35, 'trading': 30,
    'healthcare': 25, 'education': 20, 'unknown': 50,
}

# ============================================================
# PAKISTANI UNIVERSITIES (for school matching)
# ============================================================
PAKISTANI_SCHOOLS = [
    'lums', 'lahore university', 'iba karachi', 'iba sukkur',
    'nust', 'national university of sciences',
    'aga khan', 'agha khan',
    'comsats', 'fast', 'nuces',
    'ned university', 'uet lahore', 'uet peshawar',
    'quaid-i-azam', 'quaid-e-azam', 'qau',
    'university of karachi', 'university of lahore',
    'university of punjab', 'punjab university',
    'university of peshawar', 'university of sindh',
    'ghulam ishaq khan', 'giki',
    'bahria university', 'air university',
    'szabist', 'habib university',
    'kinnaird', 'fc college', 'forman christian',
    'lahore school of economics', 'lse lahore',
    'institute of business administration',
    'beaconhouse', 'nixor', 'aitchison',
    'umt',  # University of Management and Technology
    # NOTE: Do NOT include city names here — they match on location text, not schools
]


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json', scopes=SCOPES
    )
    creds = creds.with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


def read_sheet(sheets):
    """Read all contacts from the source tab."""
    print("=== STEP 1: Reading Google Sheet ===")
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SOURCE_TAB}'!A1:W20000",
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("  ERROR: No data!")
        return []

    header = rows[0]
    print(f"  Header ({len(header)} cols): {header}")
    print(f"  Total rows: {len(rows) - 1}")

    # Map header to indices
    col_map = {}
    for i, h in enumerate(header):
        col_map[h.strip().lower()] = i

    contacts = []
    for row in rows[1:]:
        while len(row) < len(header):
            row.append('')

        def g(key):
            idx = col_map.get(key)
            if idx is not None and idx < len(row):
                return str(row[idx]).strip()
            return ''

        c = {
            'name': g('name'),
            'first_name': g('first name'),
            'last_name': g('last name'),
            'email': g('email'),
            'title': g('title'),
            'company': g('company'),
            'domain': g('domain').lower(),
            'location': g('location'),
            'linkedin_url': g('linkedin url'),
            'phone': g('phone'),
            'industry': g('industry'),
            'company_size': g('company size'),
            'company_location': g('company location'),
            'schools': g('schools (from clay)'),
            'origin_score': int(g('origin score') or '0'),
            'name_match_reason': g('name match reason'),
            'search_type': g('search type'),
        }
        contacts.append(c)

    print(f"  Contacts loaded: {len(contacts)}")
    return contacts


def is_enterprise_blacklisted(domain, company_name):
    """Check if a company is on the enterprise blacklist."""
    if not domain and not company_name:
        return False, ''

    # Domain blacklist
    d = domain.lower().strip()
    if d in ENTERPRISE_BLACKLIST_DOMAINS:
        return True, f'blacklisted domain: {d}'

    # Government domains
    if '.gov' in d or '.mil' in d:
        return True, f'government domain: {d}'

    # Keyword blacklist (check company name and domain)
    combined = (company_name + ' ' + d).lower()
    for kw in ENTERPRISE_BLACKLIST_KEYWORDS:
        if kw in combined:
            return True, f'enterprise keyword: {kw}'

    return False, ''


def detect_role_tier(title):
    """Determine role tier 1-5 (1=best). Returns (tier, tier_label)."""
    t = (title or '').lower()

    if not t or any(kw in t for kw in ANTI_TITLES):
        return 5, 'anti/unknown'

    if any(kw in t for kw in ROLE_TIER_1_KEYWORDS):
        return 1, 'Finance/Payment'
    if any(kw in t for kw in ROLE_TIER_2_KEYWORDS):
        return 2, 'Operations/HR'
    if any(kw in t for kw in ROLE_TIER_3_KEYWORDS):
        return 3, 'Executive'
    if any(kw in t for kw in ROLE_TIER_4_KEYWORDS):
        return 4, 'Technical/BD'

    # Check for generic senior titles
    senior_keywords = ['head of', 'director', 'vp', 'vice president', 'chief', 'senior manager']
    if any(kw in t for kw in senior_keywords):
        return 3, 'Senior (generic)'

    if 'manager' in t:
        return 4, 'Manager (generic)'

    return 5, 'Other'


def detect_industry_from_signals(company_name, domain, title):
    """Detect industry from company name, domain, and title signals."""
    text = f"{company_name} {domain} {title}".lower()

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return industry

    # Domain-based heuristics
    d = domain.lower()
    if any(ext in d for ext in ['.tech', '.io', '.dev', '.ai', '.app']):
        return 'technology'
    if 'consult' in d:
        return 'consulting'

    return 'unknown'


def has_pakistani_school(schools_str, name_match_reason):
    """Check if contact has a Pakistani school connection.
    Only match on actual school/education text, not location mentions."""
    # Check schools field directly
    schools_text = (schools_str or '').lower()
    for school in PAKISTANI_SCHOOLS:
        if school in schools_text:
            return True

    # Check name_match_reason only if it contains education keywords
    reason = (name_match_reason or '').lower()
    if 'university' in reason or 'education' in reason or 'school' in reason or 'college' in reason:
        # Extract education-related part
        for school in PAKISTANI_SCHOOLS:
            if school in reason:
                return True

    return False


def compute_pakistan_score(contacts_group):
    """
    Compute Pakistan connection score (0-100) for a company group.
    Based on origin scores and school data of all contacts at the company.
    """
    strong_signals = 0  # origin_score >= 10 (language/school confirmed)
    medium_signals = 0  # origin_score 8-9 (name match)
    school_confirmed = 0

    for c in contacts_group:
        os = c['origin_score']
        if os >= 10:
            strong_signals += 1
        elif os >= 8:
            medium_signals += 1

        if has_pakistani_school(c.get('schools', ''), c.get('name_match_reason', '')):
            school_confirmed += 1

    if school_confirmed > 0:
        # University confirmed — strongest signal
        base = 70
        bonus = min(school_confirmed * 10, 30)
        return min(base + bonus, 100), f'{school_confirmed} school-confirmed'
    elif strong_signals > 0:
        # Language/Urdu confirmed
        base = 55
        bonus = min(strong_signals * 10, 35) + min(medium_signals * 3, 10)
        return min(base + bonus, 100), f'{strong_signals} language-confirmed, {medium_signals} name-match'
    elif medium_signals > 0:
        # Name-only matches
        base = 20
        bonus = min(medium_signals * 8, 40)
        return min(base + bonus, 60), f'{medium_signals} name-match only'
    else:
        return 5, 'no Pakistan signal'


def compute_size_fit(contact_count, company_size_str):
    """Compute company size fit score (0-100). Sweet spot: 10-200 employees."""
    cs = (company_size_str or '').lower()

    # If we have explicit size data
    if '10001' in cs or '10,001' in cs:
        return 0, '10001+ employees'
    if '5001' in cs or '5,001' in cs:
        return 5, '5001-10000 employees'
    if '1001' in cs or '1,001' in cs:
        return 10, '1001-5000 employees'
    if '501' in cs:
        return 20, '501-1000 employees'
    if '201' in cs:
        return 40, '201-500 employees'
    if '51' in cs:
        return 80, '51-200 employees (good fit)'
    if '11' in cs:
        return 100, '11-50 employees (perfect)'
    if '1-10' in cs or '2-10' in cs:
        return 60, '1-10 employees (small)'

    # Estimate from contact count in our dataset
    if contact_count >= 10:
        return 0, f'{contact_count} contacts = likely enterprise (EXCLUDED)'
    elif contact_count >= 7:
        return 10, f'{contact_count} contacts = likely 500+ employees'
    elif contact_count >= 5:
        return 20, f'{contact_count} contacts = likely 200-500 employees'
    elif contact_count == 4:
        return 35, f'{contact_count} contacts = likely 100-300 employees'
    elif contact_count == 3:
        return 50, f'3 contacts = likely 50-200 employees'
    elif contact_count == 2:
        return 65, f'2 contacts = likely 20-100 employees'
    elif contact_count == 1:
        return 75, f'1 contact = likely small company (good fit)'
    else:
        return 50, 'unknown size'


def compute_role_score(tier):
    """Score for best role tier at company."""
    return {1: 100, 2: 80, 3: 60, 4: 40, 5: 10}.get(tier, 10)


def score_company(domain, contacts_group, domain_status):
    """
    Score a company (group of contacts at same domain) using v3 model.
    Returns (score, reasoning, selected_contacts).
    """
    # --- PAKISTAN CONNECTION (0-100, weight 35%) ---
    pakistan_score, pakistan_reason = compute_pakistan_score(contacts_group)

    # --- COMPANY SIZE FIT (0-100, weight 25%) ---
    # Use the first contact's company_size if available
    company_size_str = ''
    for c in contacts_group:
        if c.get('company_size'):
            company_size_str = c['company_size']
            break
    size_fit, size_reason = compute_size_fit(len(contacts_group), company_size_str)

    # --- INDUSTRY FIT (0-100, weight 20%) ---
    company_name = contacts_group[0].get('company', '')
    sample_title = contacts_group[0].get('title', '')
    industry = detect_industry_from_signals(company_name, domain, sample_title)
    industry_fit = INDUSTRY_SCORES.get(industry, 50)

    # --- DOMAIN QUALITY (0-100, weight 10%) ---
    ds = domain_status.get(domain, 'UNKNOWN')
    if ds == 'VERIFIED':
        domain_quality = 100
    elif ds == 'UNKNOWN':
        domain_quality = 50
    else:
        domain_quality = 10

    # --- BEST ROLE (0-100, weight 10%) ---
    # Classify all contacts by tier, select best
    for c in contacts_group:
        c['_role_tier'], c['_role_label'] = detect_role_tier(c.get('title', ''))

    best_tier = min(c['_role_tier'] for c in contacts_group)
    role_score = compute_role_score(best_tier)

    # --- FINAL SCORE (weighted sum) ---
    final = (
        pakistan_score * 0.35 +
        size_fit * 0.25 +
        industry_fit * 0.20 +
        domain_quality * 0.10 +
        role_score * 0.10
    )

    # --- SELECT BEST CONTACTS (max 3 per company) ---
    # Sort by: tier ASC, origin_score DESC, data completeness DESC
    def contact_sort_key(c):
        completeness = sum([
            bool(c.get('email')),
            bool(c.get('linkedin_url')),
            bool(c.get('phone')),
            bool(c.get('schools')),
        ])
        return (c['_role_tier'], -c['origin_score'], -completeness)

    sorted_contacts = sorted(contacts_group, key=contact_sort_key)

    # Pick up to 3, trying to get different tiers and different people
    selected = []
    tiers_seen = set()
    names_seen = set()
    for c in sorted_contacts:
        if len(selected) >= 3:
            break
        # Dedup by name (same person may appear with slight variations)
        name_key = (c.get('first_name', '') + c.get('last_name', '')).lower().strip()
        if name_key in names_seen:
            continue
        if c['_role_tier'] not in tiers_seen or len(selected) < 3:
            selected.append(c)
            tiers_seen.add(c['_role_tier'])
            names_seen.add(name_key)

    # --- BUILD REASONING ---
    location = contacts_group[0].get('location', 'UAE')
    reasoning = (
        f"[{company_name}] {domain} (score {final:.0f}/100) — "
        f"Pakistani-origin contacts at UAE {industry} company. "
        f"PAKISTAN CONNECTION: {pakistan_reason}. "
        f"SIZE FIT: {size_reason}. "
        f"INDUSTRY: {industry} ({industry_fit}/100). "
        f"DOMAIN: {ds}. "
        f"BEST ROLE: Tier {best_tier} ({selected[0].get('title', '?')}). "
        f"WHY EASYSTAFF: {industry} company in {location} with Pakistan talent pipeline. "
        f"Current pain: likely using bank wires ($30-45/transfer) or Wise (no compliance docs). "
        f"EasyStaff saves compliance + cost."
    )

    return final, reasoning, selected, {
        'pakistan_score': pakistan_score,
        'pakistan_reason': pakistan_reason,
        'size_fit': size_fit,
        'size_reason': size_reason,
        'industry': industry,
        'industry_fit': industry_fit,
        'domain_status': ds,
        'domain_quality': domain_quality,
        'role_score': role_score,
        'best_tier': best_tier,
        'contact_count': len(contacts_group),
    }


async def verify_domains_batch(domains, existing_cache=None):
    """Verify domains via HTTP. Returns {domain: status}."""
    cache = dict(existing_cache or {})
    to_check = [d for d in domains if d not in cache and d and '.' in d]

    print(f"  Domains to verify: {len(to_check)} (cached: {len(cache)})")
    if not to_check:
        return cache

    sem = asyncio.Semaphore(15)
    checked = 0

    async def check_one(client, domain):
        nonlocal checked
        async with sem:
            for proto in ['https', 'http']:
                try:
                    resp = await client.head(f"{proto}://{domain}", follow_redirects=True, timeout=6.0)
                    if resp.status_code < 400:
                        cache[domain] = 'VERIFIED'
                        checked += 1
                        if checked % 100 == 0:
                            print(f"    Verified {checked}/{len(to_check)}...")
                        return
                except Exception:
                    pass
            cache[domain] = 'DEAD'
            checked += 1
            if checked % 100 == 0:
                print(f"    Verified {checked}/{len(to_check)}...")

    async with httpx.AsyncClient(
        headers={'User-Agent': 'Mozilla/5.0 (compatible)'},
        verify=False
    ) as client:
        tasks = [check_one(client, d) for d in to_check]
        await asyncio.gather(*tasks)

    verified = sum(1 for s in cache.values() if s == 'VERIFIED')
    dead = sum(1 for s in cache.values() if s == 'DEAD')
    print(f"  Results: VERIFIED={verified}, DEAD={dead}, UNKNOWN={len(domains) - verified - dead}")
    return cache


def write_to_sheet(sheets, rows_data):
    """Write results to the output tab."""
    print(f"\n=== STEP 6: Writing {len(rows_data)} rows to Sheet ===")

    header = [
        'Rank', 'First Name', 'Last Name', 'Title', 'Role Tier',
        'Company', 'Domain', 'Domain Status', 'Location',
        'LinkedIn URL', 'Email', 'Phone', 'Pakistani School',
        'Company Score', 'Pakistan Connection', 'Company Size Est',
        'Industry', 'Contacts at Company', 'Reasoning'
    ]

    values = [header] + rows_data

    # Clear existing content
    try:
        sheets.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range=f"'{OUTPUT_TAB}'!A1:S3000"
        ).execute()
        print("  Cleared existing content")
    except Exception as e:
        print(f"  Clear failed (tab may not exist): {e}")

    # Write new data
    body = {'values': values}
    result = sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{OUTPUT_TAB}'!A1",
        valueInputOption='RAW',
        body=body
    ).execute()
    print(f"  Written {result.get('updatedRows', 0)} rows")


async def main():
    t0 = time.time()
    out = io.StringIO()

    def p(s=''):
        print(s)
        out.write(s + '\n')

    sheets = get_sheets_service()

    # ========================================
    # STEP 1: Read data
    # ========================================
    contacts = read_sheet(sheets)
    if not contacts:
        return

    # ========================================
    # STEP 2: Load domain cache from previous run
    # ========================================
    domain_cache = {}
    try:
        with open('/tmp/uae_pk_prioritized.json') as f:
            old_data = json.load(f)
        for c in old_data:
            d = (c.get('domain') or '').strip().lower()
            ds = c.get('domain_status', '')
            if d and ds in ('VERIFIED', 'DEAD'):
                domain_cache[d] = ds
        print(f"  Loaded {len(domain_cache)} cached domain statuses from v2")
    except Exception as e:
        print(f"  No domain cache available: {e}")

    # ========================================
    # STEP 3: Group by domain/company
    # ========================================
    p("\n=== STEP 3: Grouping by company ===")

    # Dedup contacts by LinkedIn URL (same person listed multiple times)
    seen_linkedin = set()
    deduped = []
    dup_count = 0
    for c in contacts:
        li = (c.get('linkedin_url') or '').strip().rstrip('/')
        if li and li in seen_linkedin:
            dup_count += 1
            continue
        if li:
            seen_linkedin.add(li)
        deduped.append(c)
    p(f"  Deduped {dup_count} duplicate LinkedIn profiles")
    contacts = deduped

    # Group contacts by domain (or company name if no domain)
    company_groups = defaultdict(list)
    no_domain_count = 0

    for c in contacts:
        domain = c.get('domain', '').strip().lower()
        # Treat shared hosting domains as no-domain (including subdomains)
        if domain in SHARED_HOSTING_DOMAINS or any(domain.endswith('.' + sh) for sh in SHARED_HOSTING_DOMAINS):
            domain = ''
        if domain and '.' in domain:
            company_groups[domain].append(c)
        else:
            # Use company name as key for domainless contacts
            company = c.get('company', '').strip()
            if company:
                key = f"__nodomain__{company.lower()}"
                company_groups[key].append(c)
                no_domain_count += 1
            # Skip contacts with no domain AND no company

    p(f"  Total company groups: {len(company_groups)}")
    p(f"  Contacts with domain: {sum(len(v) for k, v in company_groups.items() if not k.startswith('__'))}")
    p(f"  Contacts without domain (by company name): {no_domain_count}")

    # ========================================
    # STEP 4: Enterprise filtering
    # ========================================
    p("\n=== STEP 4: Enterprise filtering ===")

    filtered_groups = {}
    excluded_enterprise = {}
    excluded_big_count = {}

    for key, group in company_groups.items():
        domain = key if not key.startswith('__nodomain__') else ''
        company_name = group[0].get('company', '')

        # Check blacklist
        is_bl, bl_reason = is_enterprise_blacklisted(domain, company_name)
        if is_bl:
            excluded_enterprise[key] = (len(group), bl_reason)
            continue

        # Check contact count (10+ = enterprise)
        if len(group) >= 10:
            excluded_big_count[key] = len(group)
            continue

        filtered_groups[key] = group

    excluded_ent_contacts = sum(cnt for cnt, _ in excluded_enterprise.values())
    excluded_big_contacts = sum(excluded_big_count.values())
    p(f"  Excluded by blacklist: {len(excluded_enterprise)} companies ({excluded_ent_contacts} contacts)")
    p(f"  Excluded by 10+ contacts: {len(excluded_big_count)} companies ({excluded_big_contacts} contacts)")
    p(f"  Remaining companies: {len(filtered_groups)} ({sum(len(g) for g in filtered_groups.values())} contacts)")

    # Show top excluded
    p("\n  Top excluded (blacklist):")
    for key, (cnt, reason) in sorted(excluded_enterprise.items(), key=lambda x: -x[1][0])[:15]:
        p(f"    {key}: {cnt} contacts — {reason}")
    p("\n  Excluded (10+ contacts):")
    for key, cnt in sorted(excluded_big_count.items(), key=lambda x: -x[1])[:15]:
        p(f"    {key}: {cnt} contacts")

    # ========================================
    # STEP 5: Verify domains (top candidates)
    # ========================================
    p("\n=== STEP 5: Domain verification ===")

    # Collect all unique domains from filtered groups
    all_domains = set()
    for key in filtered_groups:
        if not key.startswith('__nodomain__'):
            all_domains.add(key)

    p(f"  Unique domains to verify: {len(all_domains)}")

    # Verify top 800 + any not yet cached
    # Sort domains by group size (more contacts = more important to verify)
    domains_by_priority = sorted(
        all_domains,
        key=lambda d: len(filtered_groups.get(d, [])),
        reverse=True
    )

    # Verify top 800 that aren't cached
    domains_to_verify = [d for d in domains_by_priority[:800] if d not in domain_cache]
    if domains_to_verify:
        p(f"  Verifying {len(domains_to_verify)} uncached domains (of top 800)...")
        domain_cache = await verify_domains_batch(domains_to_verify, domain_cache)
    else:
        p(f"  All top 800 domains already cached")

    # Also verify any remaining top domains not in top 800
    # For the remaining, status will be UNKNOWN (acceptable)

    # ========================================
    # STEP 6: Score all companies
    # ========================================
    p("\n=== STEP 6: Scoring companies ===")

    scored_companies = []

    for key, group in filtered_groups.items():
        domain = key if not key.startswith('__nodomain__') else ''
        score, reasoning, selected, details = score_company(domain, group, domain_cache)
        scored_companies.append({
            'key': key,
            'domain': domain,
            'company': group[0].get('company', ''),
            'score': score,
            'reasoning': reasoning,
            'selected': selected,
            'details': details,
        })

    # Sort by score descending
    scored_companies.sort(key=lambda x: -x['score'])

    p(f"  Scored {len(scored_companies)} companies")
    if scored_companies:
        p(f"  Top score: {scored_companies[0]['score']:.1f} — {scored_companies[0]['company']} ({scored_companies[0]['domain']})")
        p(f"  Bottom score: {scored_companies[-1]['score']:.1f}")

    # ========================================
    # STEP 7: Build final ranked list (max 2000 contacts)
    # ========================================
    p("\n=== STEP 7: Building final ranked list ===")

    final_contacts = []
    for comp in scored_companies:
        for c in comp['selected']:
            final_contacts.append({
                **c,
                'company_score': comp['score'],
                'company_reasoning': comp['reasoning'],
                'company_details': comp['details'],
                'domain_status': domain_cache.get(comp['domain'], 'UNKNOWN'),
            })
            if len(final_contacts) >= 2000:
                break
        if len(final_contacts) >= 2000:
            break

    p(f"  Final contacts: {len(final_contacts)}")
    companies_in_final = len(set(c.get('domain', c.get('company', '')) for c in final_contacts))
    p(f"  Companies represented: {companies_in_final}")

    # ========================================
    # STEP 8: Write to Google Sheet
    # ========================================
    sheet_rows = []
    for rank, c in enumerate(final_contacts, 1):
        det = c.get('company_details', {})
        sheet_rows.append([
            rank,
            c.get('first_name', ''),
            c.get('last_name', ''),
            c.get('title', ''),
            f"Tier {c.get('_role_tier', '?')}: {c.get('_role_label', '?')}",
            c.get('company', ''),
            c.get('domain', ''),
            c.get('domain_status', 'UNKNOWN'),
            c.get('location', ''),
            c.get('linkedin_url', ''),
            c.get('email', ''),
            c.get('phone', ''),
            c.get('schools', ''),
            f"{c.get('company_score', 0):.1f}",
            f"{det.get('pakistan_score', 0):.0f} — {det.get('pakistan_reason', '')}",
            det.get('size_reason', ''),
            f"{det.get('industry', 'unknown')} ({det.get('industry_fit', 50)})",
            str(det.get('contact_count', 1)),
            c.get('company_reasoning', ''),
        ])

    write_to_sheet(sheets, sheet_rows)

    # ========================================
    # STEP 9: Save JSON
    # ========================================
    with open('/tmp/uae_pk_v3_scored.json', 'w') as f:
        # Clean non-serializable fields
        export = []
        for c in final_contacts:
            ec = {k: v for k, v in c.items() if k != 'company_details' and not k.startswith('_')}
            ec['company_details'] = c.get('company_details', {})
            export.append(ec)
        json.dump(export, f, indent=1)
    p(f"\n  Saved /tmp/uae_pk_v3_scored.json ({len(final_contacts)} contacts)")

    # ========================================
    # STEP 10: COMPREHENSIVE SUMMARY
    # ========================================
    p("\n" + "=" * 100)
    p("COMPREHENSIVE SUMMARY — UAE-Pakistan Priority Scoring v3")
    p("=" * 100)

    p(f"\nTotal contacts in Sheet: {len(contacts)}")
    p(f"Total company groups: {len(company_groups)}")
    p(f"Excluded (enterprise blacklist): {len(excluded_enterprise)} companies ({excluded_ent_contacts} contacts)")
    p(f"Excluded (10+ contacts): {len(excluded_big_count)} companies ({excluded_big_contacts} contacts)")
    p(f"Remaining after filtering: {len(filtered_groups)} companies")
    p(f"Final list: {len(final_contacts)} contacts from {companies_in_final} companies")

    # Score distribution
    p("\n--- Score Distribution (all scored companies) ---")
    buckets = Counter()
    for comp in scored_companies:
        bucket = int(comp['score'] // 10) * 10
        buckets[bucket] += 1
    for bucket in sorted(buckets.keys(), reverse=True):
        bar = '#' * (buckets[bucket] // 10)
        p(f"  {bucket:3d}-{bucket+9:3d}: {buckets[bucket]:5d} companies {bar}")

    # Score distribution of final 2000
    p("\n--- Score Distribution (final 2000 contacts) ---")
    final_buckets = Counter()
    for c in final_contacts:
        bucket = int(c['company_score'] // 10) * 10
        final_buckets[bucket] += 1
    for bucket in sorted(final_buckets.keys(), reverse=True):
        bar = '#' * (final_buckets[bucket] // 5)
        p(f"  {bucket:3d}-{bucket+9:3d}: {final_buckets[bucket]:5d} contacts {bar}")

    # Top 50 companies with FULL reasoning
    p("\n--- TOP 50 COMPANIES (Full Reasoning) ---")
    for i, comp in enumerate(scored_companies[:50], 1):
        det = comp['details']
        sel = comp['selected']
        p(f"\n{'='*80}")
        p(f"#{i:3d} | SCORE: {comp['score']:.1f}/100 | {comp['company']} ({comp['domain']})")
        p(f"{'='*80}")
        p(f"  Pakistan Connection: {det['pakistan_score']:.0f}/100 — {det['pakistan_reason']}")
        p(f"  Size Fit: {det['size_fit']:.0f}/100 — {det['size_reason']}")
        p(f"  Industry: {det['industry']} ({det['industry_fit']}/100)")
        p(f"  Domain: {det['domain_status']} ({det['domain_quality']}/100)")
        p(f"  Best Role: Tier {det['best_tier']} ({det['role_score']}/100)")
        p(f"  Contacts at company: {det['contact_count']}")
        p(f"  Selected contacts:")
        for j, c in enumerate(sel, 1):
            p(f"    {j}. {c.get('first_name', '')} {c.get('last_name', '')} — {c.get('title', '')} "
              f"(Tier {c.get('_role_tier', '?')}: {c.get('_role_label', '?')}, "
              f"origin={c['origin_score']}, LinkedIn={'YES' if c.get('linkedin_url') else 'NO'})")
        p(f"  REASONING: {comp['reasoning']}")

    # Role tier distribution
    p("\n--- Role Tier Distribution (final 2000) ---")
    tier_counts = Counter(c.get('_role_tier', 5) for c in final_contacts)
    tier_labels = {1: 'Finance/Payment', 2: 'Operations/HR', 3: 'Executive', 4: 'Technical/BD', 5: 'Other'}
    for tier in sorted(tier_counts.keys()):
        p(f"  Tier {tier} ({tier_labels.get(tier, '?')}): {tier_counts[tier]} contacts")

    # Industry distribution
    p("\n--- Industry Distribution (final 2000) ---")
    ind_counts = Counter(c.get('company_details', {}).get('industry', 'unknown') for c in final_contacts)
    for ind, cnt in ind_counts.most_common():
        p(f"  {ind:<25} {cnt:5d}")

    # Pakistan connection strength
    p("\n--- Pakistan Connection Strength (final 2000) ---")
    pk_buckets = Counter()
    for c in final_contacts:
        pk = c.get('company_details', {}).get('pakistan_score', 0)
        if pk >= 70:
            pk_buckets['Strong (70-100)'] += 1
        elif pk >= 50:
            pk_buckets['Good (50-69)'] += 1
        elif pk >= 30:
            pk_buckets['Moderate (30-49)'] += 1
        else:
            pk_buckets['Weak (0-29)'] += 1
    for label in ['Strong (70-100)', 'Good (50-69)', 'Moderate (30-49)', 'Weak (0-29)']:
        p(f"  {label}: {pk_buckets.get(label, 0)} contacts")

    # Company size estimate distribution
    p("\n--- Company Size Estimate (final 2000) ---")
    size_buckets = Counter()
    for c in final_contacts:
        sf = c.get('company_details', {}).get('size_fit', 50)
        if sf >= 80:
            size_buckets['Perfect (11-50 emp)'] += 1
        elif sf >= 60:
            size_buckets['Good (1-10 or 51-200)'] += 1
        elif sf >= 40:
            size_buckets['OK (201-500)'] += 1
        elif sf >= 20:
            size_buckets['Large (500+)'] += 1
        else:
            size_buckets['Enterprise (1000+)'] += 1
    for label in ['Perfect (11-50 emp)', 'Good (1-10 or 51-200)', 'OK (201-500)', 'Large (500+)', 'Enterprise (1000+)']:
        p(f"  {label}: {size_buckets.get(label, 0)} contacts")

    # Domain status distribution
    p("\n--- Domain Status (final 2000) ---")
    ds_counts = Counter(c.get('domain_status', 'UNKNOWN') for c in final_contacts)
    for status, cnt in ds_counts.most_common():
        p(f"  {status}: {cnt}")

    # Full top 200 contacts
    p("\n--- FULL TOP 200 CONTACTS ---")
    p(f"{'#':>4} {'Score':>6} {'Name':<28} {'Title':<38} {'Company':<28} {'Domain':<22} {'Dom':>4} {'Tier':>4} {'PK':>4} {'Size':>4} {'Ind':>4}")
    p("-" * 170)
    for i, c in enumerate(final_contacts[:200], 1):
        det = c.get('company_details', {})
        name = f"{c.get('first_name', '')} {c.get('last_name', '')}"
        p(f"{i:4d} {c['company_score']:6.1f} {name[:27]:<28} {(c.get('title', '') or '')[:37]:<38} "
          f"{(c.get('company', '') or '')[:27]:<28} {(c.get('domain', '') or '')[:21]:<22} "
          f"{c.get('domain_status', '?')[:4]:>4} T{c.get('_role_tier', '?'):<3} "
          f"{det.get('pakistan_score', 0):>3.0f} {det.get('size_fit', 0):>4.0f} {det.get('industry_fit', 50):>4}")

    # Save output
    with open('/tmp/uae_pk_v3_results.txt', 'w') as f:
        f.write(out.getvalue())
    p(f"\n  Full output saved to /tmp/uae_pk_v3_results.txt")
    p(f"  Total time: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    asyncio.run(main())
