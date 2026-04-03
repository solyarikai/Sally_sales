#!/usr/bin/env python3
"""
UAE-Pakistan v6 Lead Scoring Pipeline — "Act as God BDM"

IMPROVEMENTS over v5:
1. Conversion-informed role weights (from 50+ qualified leads analysis)
2. Merges ALL scrape caches (v5 498 + old 4200 raw HTML)
3. GPT-analyzes ALL companies with website content (not just 200)
4. Uses Clay enrichment: Schools, Company Size, Industry
5. Pakistan connection strength scoring (school + language + surname + company ops)
6. Sweet-spot company size targeting (10-50 employees)
7. Rich reasoning for every single company

KPI: 2000 prioritized contacts for Dubai-Pakistan corridor
"""

import asyncio
import json
import os
import re
import time
import warnings
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-Pakistan - New Only'
OUTPUT_TAB = 'UAE-Pakistan Priority 2000'

V5_SCRAPE = '/tmp/uae_pk_v5_scrape.json'
OLD_SCRAPE = '/tmp/uae_pk_v5_scrape_cache.json'
GPT_CACHE = '/tmp/uae_pk_v6_gpt.json'
SCRAPE_MERGED = '/tmp/uae_pk_v6_scrape.json'
SCORED_OUTPUT = '/tmp/uae_pk_v6_scored.json'
REASONING_LOG = '/tmp/uae_pk_v6_reasoning.jsonl'


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


# ─── CONSTANTS (CONVERSION-INFORMED) ──────────────────────────────────────────

# Based on 50+ qualified leads from reference sheet:
# Finance/Payroll: Karla (MedTrainer), Mani (Zocket) = DIRECT payment decision makers
# COO/VP Ops: Cinzia (Herabiotech), Ramon (SAM Labs) = control contractor relationships
# CEO/Founder: Juan Pablo, Alexander, Jhon Cohen = small company = they ARE the payroll
# HR: Morim (IGT Glass) = manages contractor relationships
# CTO: Saad (nur-engineering) = tech companies, offshore teams
ROLE_TIERS = {
    1: {  # Finance/Payroll — they literally pay contractors
        'keywords': ['cfo', 'chief financial', 'finance director', 'head of finance', 'vp finance',
                     'payroll', 'controller', 'treasurer', 'financial controller', 'head of payments',
                     'finance manager', 'accounts payable', 'finance lead', 'senior finance'],
        'score': 100
    },
    2: {  # Operations — they manage contractor workflows
        'keywords': ['coo', 'chief operating', 'operations director', 'head of operations',
                     'vp operations', 'operations manager', 'head of procurement',
                     'people operations', 'chief people', 'chief admin'],
        'score': 92
    },
    3: {  # HR/People — they onboard/manage contractors
        'keywords': ['hr director', 'head of hr', 'head of people', 'hr manager',
                     'talent acquisition', 'people & culture', 'people manager',
                     'hr business partner', 'chief human', 'vp people', 'head of talent'],
        'score': 85
    },
    4: {  # CEO/Founder — at small companies they DO everything
        'keywords': ['ceo', 'chief executive', 'founder', 'co-founder', 'owner',
                     'managing director', 'general manager', 'president', 'country manager',
                     'regional director', 'managing partner', 'sole proprietor', 'chairman'],
        'score': 75
    },
    5: {  # Tech leadership — offshore team decisions
        'keywords': ['cto', 'chief technology', 'vp engineering', 'head of engineering',
                     'engineering director', 'tech director', 'head of development',
                     'technical director', 'engineering manager'],
        'score': 55
    },
    6: {  # BD/Sales/Commercial — can refer internally
        'keywords': ['bd director', 'head of sales', 'sales director', 'commercial director',
                     'business development', 'partnerships', 'head of growth',
                     'chief commercial', 'chief revenue'],
        'score': 35
    },
    7: {  # Other professional
        'keywords': [],
        'score': 10
    },
}

ANTI_TITLES = ['intern', 'student', 'freelanc', 'looking for', 'seeking',
               'unemployed', 'open to work', 'trainee', 'apprentice',
               'virtual assistant', 'assistant', 'receptionist', 'driver',
               'security guard', 'cleaner', 'waiter']

UAE_SIGNALS = [
    'dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah', 'ras al-khaimah',
    'fujairah', 'umm al quwain', 'umm al-quwain', 'uae', 'united arab emirates',
    '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a',
    '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a \u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u0627\u0644\u0645\u062a\u062d\u062f\u0629',
    '\u0627\u0644\u0634\u0627\u0631\u0642\u0629', '\u0639\u062c\u0645\u0627\u0646',
    '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u0627\u0628\u0648\u0638\u0628\u064a',
    '\u0627\u0628\u0648 \u0638\u0628\u064a',
]

EXCLUDE_LOCATIONS = [
    'pakistan', 'karachi', 'lahore', 'islamabad', 'rawalpindi', 'faisalabad', 'peshawar',
    'india', 'mumbai', 'delhi', 'bangalore', 'hyderabad, india', 'chennai', 'pune', 'kolkata',
    'noida', 'gurgaon', 'gurugram',
]

BLACKLIST_DOMAINS = {
    'sc.com', 'bankfab.com', 'huawei.com', 'emiratesnbd.com', 'deloitte.com',
    'mashreq.com', 'alfuttaim.com', 'dib.ae', 'adcb.com', 'pwc.com', 'ey.com',
    'kpmg.com', 'amazon.com', 'google.com', 'microsoft.com', 'meta.com',
    'oracle.com', 'ibm.com', 'samsung.com', 'siemens.com', 'emirates.com',
    'etihad.com', 'flydubai.com', 'adnoc.ae', 'aramco.com', 'emaar.com',
    'damac.com', 'nakheel.com', 'du.ae', 'etisalat.ae', 'careem.com',
    'uber.com', 'noon.com', 'hsbc.com', 'citibank.com', 'jpmorgan.com',
    'unilever.com', 'nestle.com', 'pg.com', 'shell.com', 'bp.com', 'apple.com',
    'netflix.com', 'salesforce.com', 'cisco.com', 'dell.com', 'dubaiholding.com',
    'dpworld.com', 'rta.ae', 'majid-al-futtaim.com', 'jumeirah.com', 'meraas.com',
    'difc.ae', 'bat.com', 'accenture.com', 'mckinsey.com', 'bcg.com', 'bain.com',
    'gartner.com', 'adobe.com', 'intel.com', 'marriott.com', 'accor.com',
    'positivity.org', 'confidential.careers', 'damacproperties.com', 'dwtc.com',
    'sbp.org.pk', 'e-and.com', 'etisalatdigital.com', 'reckitt.com', 'sap.com',
    'bakerhughes.com', 'honeywell.com', 'schneider-electric.com', 'abb.com',
    'totalenergies.com', 'chevron.com', 'morganstanley.com', 'ubs.com',
    'novartis.com', 'pfizer.com', 'ge.com',
}

BLACKLIST_KEYWORDS = [
    'bank', 'banking', 'insurance', 'reinsurance', 'airline', 'airways', 'petroleum',
    'oil & gas', 'government', 'ministry', 'authority', 'municipality',
    'university', 'college', 'hospital', 'armed forces', 'military', 'police',
    'central bank', 'stock exchange', 'securities commission',
]

SHARED_HOSTING = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'linkedin.com',
    'facebook.com', 'vercel.app', 'netlify.app', 'herokuapp.com', 'github.io',
    'wordpress.com', 'wixsite.com', 'squarespace.com', 'shopify.com', 'google.com',
    'live.com', 'icloud.com', 'aol.com', 'protonmail.com', 'zoho.com',
}

# Industry fit for EasyStaff (contractor payroll):
# Best: outsourcing/staffing (they ARE the contractors market)
# Great: software/IT (offshore dev teams)
# Good: consulting/digital agency (project-based teams)
# OK: fintech/ecommerce (may have remote teams)
# Low: construction/real estate/trading (local labor)
INDUSTRY_FIT = {
    'outsourcing': 100, 'staffing': 95, 'recruitment': 95,
    'software': 90, 'it_services': 88, 'technology': 85,
    'consulting': 78, 'digital_agency': 76, 'creative_agency': 75,
    'fintech': 72, 'saas': 85, 'ai': 82,
    'ecommerce': 60, 'professional_services': 58,
    'education': 55, 'healthcare': 50,
    'logistics': 45, 'trading': 38,
    'construction': 30, 'real_estate': 28, 'hospitality': 25,
    'manufacturing': 35, 'retail': 30,
    'other': 45,
}

INDUSTRY_KEYWORDS = {
    'outsourcing': ['outsourc', 'bpo', 'offshoring', 'nearshoring', 'offshore'],
    'staffing': ['staffing', 'recruitment', 'talent acqui', 'headhunt', 'hiring', 'recruit'],
    'software': ['software', 'app develop', 'web develop', 'mobile develop', 'software dev'],
    'saas': ['saas', 'cloud platform', 'cloud service', 'subscription platform'],
    'ai': ['artificial intelligence', 'machine learning', 'deep learning', 'ai platform', 'ai-powered'],
    'technology': ['technology', 'tech company', 'it company', 'information tech'],
    'it_services': ['it services', 'it solutions', 'managed services', 'it consult'],
    'consulting': ['consulting', 'consultancy', 'advisory', 'management consult', 'strategy consult'],
    'digital_agency': ['digital agency', 'creative agency', 'design agency', 'web agency', 'marketing agency'],
    'fintech': ['fintech', 'financial tech', 'payment', 'crypto', 'blockchain', 'defi'],
    'ecommerce': ['ecommerce', 'e-commerce', 'online retail', 'marketplace'],
    'logistics': ['logistics', 'freight', 'shipping', 'supply chain', 'courier'],
    'trading': ['trading', 'import', 'export', 'commodit'],
    'professional_services': ['professional service', 'legal', 'accounting', 'audit'],
    'construction': ['construction', 'building', 'contracting'],
    'real_estate': ['real estate', 'property', 'realty', 'broker'],
    'education': ['education', 'e-learning', 'edtech', 'training platform', 'academy'],
    'healthcare': ['health', 'medical', 'pharma', 'biotech', 'wellness'],
    'manufacturing': ['manufacturing', 'factory', 'production', 'industrial'],
    'hospitality': ['hotel', 'restaurant', 'hospitality', 'tourism', 'travel'],
    'retail': ['retail', 'store', 'shop', 'fashion', 'apparel'],
}

# Pakistani schools that prove Pakistan connection
PK_SCHOOLS = [
    'lums', 'lahore university', 'iba karachi', 'iba sukkur',
    'nust', 'national university of sciences',
    'aga khan', 'agha khan',
    'gik', 'ghulam ishaq khan',
    'ned university', 'ned uni',
    'fast', 'fast-nu', 'national university of computer',
    'comsats', 'ciit',
    'uet lahore', 'uet peshawar', 'university of engineering and tech',
    'quaid-i-azam', 'quaid e azam',
    'university of karachi', 'university of lahore', 'university of peshawar',
    'university of punjab', 'punjab university',
    'bahria university', 'air university',
    'habib university', 'szabist', 'isb school',
    'beaconhouse', 'aitchison', 'karachi grammar',
    'lahore grammar', 'lyceum',
]


def strip_html(html):
    if not html:
        return ''
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_uae_location(loc):
    if not loc:
        return False
    loc_lower = loc.lower().strip()
    return any(s in loc_lower for s in UAE_SIGNALS)


def is_excluded_location(loc):
    if not loc:
        return True
    return any(ex in loc.lower() for ex in EXCLUDE_LOCATIONS)


def is_blacklisted_domain(domain):
    if not domain:
        return False
    d = domain.lower().strip()
    if d in BLACKLIST_DOMAINS:
        return True
    if d.endswith('.gov') or '.gov.' in d or d.endswith('.mil') or '.mil.' in d:
        return True
    return False


def is_blacklisted_company(company):
    if not company:
        return False
    c = company.lower()
    return any(kw in c for kw in BLACKLIST_KEYWORDS)


def is_shared_hosting(domain):
    if not domain:
        return True
    return domain.lower().strip() in SHARED_HOSTING


def get_role_tier(title):
    if not title:
        return 7, 10
    t = title.lower()
    for anti in ANTI_TITLES:
        if anti in t:
            return 99, 0  # disqualified
    for tier_num, tier_data in ROLE_TIERS.items():
        for kw in tier_data['keywords']:
            if kw in t:
                return tier_num, tier_data['score']
    return 7, 10


def detect_industry(company_name, domain, clay_industry='', website_text=''):
    """Multi-source industry detection: Clay > Website > Keywords > TLD"""
    # Clay industry (if available and meaningful)
    if clay_industry:
        ci = clay_industry.lower().strip()
        for ind, score in INDUSTRY_FIT.items():
            if ind in ci or ci in ind:
                return ind, score
        # Try keyword match on Clay industry text
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw in ci for kw in keywords):
                return ind, INDUSTRY_FIT.get(ind, 45)

    # Website text + company name + domain
    combined = f"{company_name or ''} {domain or ''} {website_text or ''}".lower()
    best_ind, best_score, best_matches = 'other', 45, 0
    for ind, keywords in INDUSTRY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > best_matches:
            best_ind = ind
            best_score = INDUSTRY_FIT.get(ind, 45)
            best_matches = matches

    # TLD fallback for tech companies
    if best_matches == 0 and domain:
        d = domain.lower()
        if any(d.endswith(ext) for ext in ['.io', '.ai', '.dev', '.tech', '.app']):
            return 'technology', INDUSTRY_FIT['technology']

    return best_ind, best_score


def estimate_company_size_score(clay_size, contact_count, gpt_estimate=None):
    """
    EasyStaff sweet spot: 10-50 employees (small enough to not have in-house payroll,
    big enough to have multiple contractors).
    From qualified leads: company sizes 1, 3, 7, 9, 40, 87 all converted.
    """
    size = None

    # GPT estimate first (most accurate)
    if gpt_estimate:
        text = str(gpt_estimate).replace(',', '').replace('~', '').replace('+', '')
        nums = re.findall(r'\d+', text)
        if nums:
            if len(nums) >= 2:
                size = (int(nums[0]) + int(nums[1])) // 2
            else:
                size = int(nums[0])

    # Clay company size
    if size is None and clay_size:
        text = str(clay_size).replace(',', '').replace('~', '').replace('+', '')
        nums = re.findall(r'\d+', text)
        if nums:
            if len(nums) >= 2:
                size = (int(nums[0]) + int(nums[1])) // 2
            else:
                size = int(nums[0])

    if size is not None:
        if 10 <= size <= 50:
            return 100, f"{size} employees (sweet spot)"
        elif 5 <= size <= 9:
            return 85, f"{size} employees (small but viable)"
        elif 51 <= size <= 200:
            return 80, f"{size} employees (mid-size, good)"
        elif 1 <= size <= 4:
            return 55, f"{size} employees (micro, may be too small)"
        elif 201 <= size <= 500:
            return 45, f"{size} employees (larger, may have in-house)"
        elif size > 500:
            return 15, f"{size} employees (enterprise, skip)"
        return 50, f"{size} employees"

    # Proxy from contact count (how many people from this company in our data)
    if contact_count == 1:
        return 60, "1 contact (size unknown)"
    elif contact_count == 2:
        return 58, "2 contacts (small company likely)"
    elif 3 <= contact_count <= 5:
        return 52, f"{contact_count} contacts (mid-size likely)"
    elif 6 <= contact_count <= 9:
        return 30, f"{contact_count} contacts (larger company likely)"
    return 50, "size unknown"


def pakistan_connection_score(origin_score, name_match_reason, schools_clay, company_name=''):
    """
    How strong is the Pakistan connection?
    10 = Urdu speaker in UAE (strongest - they DEFINITELY have PK connections)
    9 = Pakistani university educated (strong - they studied in PK)
    8 = Pakistani surname (moderate - cultural connection)
    """
    origin = int(origin_score) if origin_score else 0
    reasons = []

    score = 30  # baseline for anyone in UAE

    if origin >= 10:
        score = 100
        reasons.append("Urdu speaker (confirmed PK cultural tie)")
    elif origin >= 9:
        score = 90
        reasons.append("Pakistani university educated")
    elif origin >= 8:
        score = 80
        reasons.append("Pakistani surname/heritage")

    # Schools from Clay
    if schools_clay:
        sc = schools_clay.lower()
        for pk_school in PK_SCHOOLS:
            if pk_school in sc:
                score = max(score, 92)
                reasons.append(f"Studied at PK school: {schools_clay[:50]}")
                break

    # Company name Pakistan signals
    if company_name:
        cn = company_name.lower()
        pk_signals = ['pakistan', 'pk', 'karachi', 'lahore', 'islamabad']
        if any(s in cn for s in pk_signals):
            score = max(score, 85)
            reasons.append("Company name has Pakistan reference")

    return score, '; '.join(reasons) if reasons else "No specific PK signal (UAE-based)"


# ─── PHASE 1: READ + FILTER + PRE-SCORE ────────────────────────────────────

def phase1_prescore(sheets):
    print("=" * 80)
    print("UAE-PAKISTAN v6 LEAD SCORING PIPELINE — 'Act as God BDM'")
    print("=" * 80)
    print("\n[Phase 1] Reading source data & pre-scoring...")

    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SOURCE_TAB}'!A1:Z20000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("ERROR: No data!")
        return None, None

    headers = rows[0]
    col_idx = {h.strip(): i for i, h in enumerate(headers)}
    print(f"  Columns: {list(col_idx.keys())}")

    def gv(row, col):
        idx = col_idx.get(col)
        if idx is None or idx >= len(row):
            return ''
        return (row[idx] or '').strip()

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
            'phone': gv(row, 'Phone'),
            'clay_industry': gv(row, 'Industry'),
            'clay_company_size': gv(row, 'Company Size'),
            'company_location': gv(row, 'Company Location'),
            'schools_clay': gv(row, 'Schools (from Clay)'),
            'origin_score': gv(row, 'Origin Score'),
            'name_match_reason': gv(row, 'Name Match Reason'),
            'search_type': gv(row, 'Search Type'),
            'corridor': gv(row, 'Corridor'),
        })
    print(f"  Total contacts: {len(contacts)}")

    # Filter: UAE location + not excluded
    uae = []
    pk_excluded = other_excluded = 0
    for c in contacts:
        loc = c['location']
        if is_excluded_location(loc):
            if any(x in (loc or '').lower() for x in ['pakistan', 'karachi', 'lahore']):
                pk_excluded += 1
            else:
                other_excluded += 1
            continue
        if is_uae_location(loc):
            uae.append(c)
        else:
            other_excluded += 1
    print(f"  UAE contacts: {len(uae)} (excl PK={pk_excluded}, other={other_excluded})")

    # Normalize shared hosting domains
    for c in uae:
        if c['domain'] and is_shared_hosting(c['domain']):
            c['domain'] = ''

    # Blacklist + anti-title + enterprise filter
    domain_counts = Counter(c['domain'].lower() for c in uae if c['domain'])
    filtered = []
    stats = {'bl_domain': 0, 'bl_company': 0, 'enterprise': 0, 'anti_title': 0}
    for c in uae:
        d = c['domain'].lower().strip() if c['domain'] else ''
        if is_blacklisted_domain(d):
            stats['bl_domain'] += 1; continue
        if is_blacklisted_company(c['company']):
            stats['bl_company'] += 1; continue
        if d and domain_counts[d] >= 10:
            stats['enterprise'] += 1; continue
        tier, role_score = get_role_tier(c['title'])
        if tier == 99:
            stats['anti_title'] += 1; continue
        c['role_tier'] = tier
        c['role_score'] = role_score
        filtered.append(c)
    print(f"  After filters: {len(filtered)} (bl_domain={stats['bl_domain']}, bl_company={stats['bl_company']}, "
          f"enterprise={stats['enterprise']}, anti_title={stats['anti_title']})")

    # Group by company: domain if available, else company name
    companies = defaultdict(list)
    for c in filtered:
        d = c['domain'].lower().strip() if c['domain'] else ''
        key = d if d else f"__name__{c['company'].lower().strip()}"
        companies[key].append(c)
    print(f"  Unique companies: {len(companies)}")

    # Pre-score each company
    scored_companies = []
    for key, cc in companies.items():
        company_name = cc[0]['company']
        domain = cc[0]['domain'] if not key.startswith('__name__') else ''
        contact_count = len(cc)

        # Best role in company
        best_tier = min(c['role_tier'] for c in cc)
        best_role_score = max(c['role_score'] for c in cc)

        # Industry from Clay or keywords
        clay_industries = [c['clay_industry'] for c in cc if c.get('clay_industry')]
        clay_ind = clay_industries[0] if clay_industries else ''
        industry, industry_score = detect_industry(company_name, domain, clay_ind)

        # Company size from Clay
        clay_sizes = [c['clay_company_size'] for c in cc if c.get('clay_company_size')]
        clay_size = clay_sizes[0] if clay_sizes else ''
        size_score, size_detail = estimate_company_size_score(clay_size, contact_count)

        # Pakistan connection strength
        origin_scores = [int(c.get('origin_score') or '0') for c in cc]
        best_origin = max(origin_scores) if origin_scores else 0
        schools = [c['schools_clay'] for c in cc if c.get('schools_clay')]
        pk_score, pk_reason = pakistan_connection_score(
            best_origin,
            cc[0].get('name_match_reason', ''),
            schools[0] if schools else '',
            company_name
        )

        # TLD quality
        tld_score = 20
        if domain:
            d = domain.lower()
            if any(d.endswith(ext) for ext in ['.io', '.ai', '.tech', '.dev']):
                tld_score = 80
            elif d.endswith('.pk'):
                tld_score = 70
            elif any(d.endswith(ext) for ext in ['.com', '.ae', '.co']):
                tld_score = 60
            elif d.endswith('.org'):
                tld_score = 40
            else:
                tld_score = 45

        # FORMULA: Industry 25% + Size 20% + PK Connection 25% + Role 20% + Domain 10%
        pre_score = (
            industry_score * 0.25 +
            size_score * 0.20 +
            pk_score * 0.25 +
            best_role_score * 0.20 +
            tld_score * 0.10
        )

        scored_companies.append({
            'key': key,
            'company_name': company_name,
            'domain': domain,
            'contacts': cc,
            'contact_count': contact_count,
            'pre_score': round(pre_score, 2),
            'industry': industry,
            'industry_score': industry_score,
            'size_score': size_score,
            'size_detail': size_detail,
            'best_tier': best_tier,
            'best_role_score': best_role_score,
            'pk_score': pk_score,
            'pk_reason': pk_reason,
            'tld_score': tld_score,
            'clay_industry': clay_ind,
            'clay_size': clay_size,
        })

    scored_companies.sort(key=lambda x: -x['pre_score'])

    print(f"\n  Pre-score summary:")
    print(f"  Top: {scored_companies[0]['pre_score']} ({scored_companies[0]['company_name']})")
    print(f"  Median: {scored_companies[len(scored_companies)//2]['pre_score']}")
    for i, s in enumerate(scored_companies[:15]):
        print(f"    #{i+1} {s['pre_score']:.1f} | {s['company_name']} | {s['domain']} | "
              f"{s['industry']} | T{s['best_tier']} | PK:{s['pk_score']} | Size:{s['size_detail'][:30]}")

    return scored_companies, filtered


# ─── PHASE 2: MERGE + SCRAPE ──────────────────────────────────────────────

def load_and_merge_caches():
    """Merge v5 structured cache + old raw HTML cache + own previous run into unified format"""
    merged = {}

    # Load our own previous run first (best quality)
    if os.path.exists(SCRAPE_MERGED):
        try:
            own = json.load(open(SCRAPE_MERGED))
            for domain, data in own.items():
                if isinstance(data, dict) and data.get('status') == 'ok':
                    merged[domain] = data
            print(f"  Own v6 cache: {len(merged)} ok domains loaded")
        except Exception as e:
            print(f"  Own v6 cache error: {e}")

    # Load v5 structured cache (498 domains)
    if os.path.exists(V5_SCRAPE):
        try:
            v5 = json.load(open(V5_SCRAPE))
            for domain, data in v5.items():
                if isinstance(data, dict) and data.get('status') == 'ok':
                    merged[domain] = data
            print(f"  v5 cache: {len(merged)} ok domains loaded")
        except Exception as e:
            print(f"  v5 cache error: {e}")

    # Load old raw HTML cache (4200 domains as strings)
    if os.path.exists(OLD_SCRAPE):
        try:
            old = json.load(open(OLD_SCRAPE))
            added = 0
            for domain, content in old.items():
                if domain in merged:
                    continue  # v5 data is better
                if isinstance(content, str) and len(content) > 200:
                    # Parse HTML to extract structured data
                    title_m = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                    title = title_m.group(1).strip()[:200] if title_m else ''
                    desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', content, re.IGNORECASE)
                    if not desc_m:
                        desc_m = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)
                    description = desc_m.group(1).strip()[:500] if desc_m else ''
                    text = strip_html(content)[:3000]
                    if len(text) > 100:  # meaningful content
                        merged[domain] = {
                            'status': 'ok',
                            'title': title,
                            'description': description,
                            'text': text,
                            'source': 'old_cache'
                        }
                        added += 1
            print(f"  Old cache: {added} domains parsed and added (from {len(old)} total)")
        except Exception as e:
            print(f"  Old cache error: {e}")

    return merged


async def fetch_website(domain, semaphore, client):
    if not domain:
        return {'status': 'none', 'title': '', 'description': '', 'text': ''}
    url = f'https://{domain.lower().strip()}'
    async with semaphore:
        try:
            resp = await client.get(url, timeout=12.0, follow_redirects=True)
            if 200 <= resp.status_code < 400:
                html = resp.text
                if len(html) < 200:
                    return {'status': 'thin', 'title': '', 'description': '', 'text': strip_html(html)}
                title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                title = title_m.group(1).strip()[:200] if title_m else ''
                desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
                if not desc_m:
                    desc_m = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
                desc = desc_m.group(1).strip()[:500] if desc_m else ''
                text = strip_html(html)[:3000]
                return {'status': 'ok', 'title': title, 'description': desc, 'text': text}
            return {'status': 'dead', 'title': '', 'description': '', 'text': ''}
        except Exception:
            return {'status': 'dead', 'title': '', 'description': '', 'text': ''}


async def phase2_scrape(companies_sorted, merged_cache):
    import httpx

    print(f"\n[Phase 2] Scraping websites (merged cache has {len(merged_cache)} domains)...")

    # Find domains we need to scrape (top 1000 companies not in cache)
    to_scrape = []
    for comp in companies_sorted[:1000]:
        d = comp['domain']
        if d and d.lower() not in merged_cache and d.lower() not in [x.lower() for x in to_scrape]:
            to_scrape.append(d)
    print(f"  Need to scrape: {len(to_scrape)} domains")

    if not to_scrape:
        print("  All cached, skipping scrape")
        return merged_cache

    from app.core.config import settings
    proxy_password = getattr(settings, 'APIFY_PROXY_PASSWORD', None)
    client_kwargs = {
        'verify': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
    }
    if proxy_password:
        client_kwargs['proxy'] = f'http://auto:{proxy_password}@proxy.apify.com:8000'
        print("  Using Apify residential proxy")

    semaphore = asyncio.Semaphore(15)

    async with httpx.AsyncClient(**client_kwargs) as client:
        # Create all tasks upfront for true concurrency
        async def scrape_one(d):
            return d, await fetch_website(d, semaphore, client)

        tasks = [scrape_one(d) for d in to_scrape]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scraped = 0
        for res in results:
            if isinstance(res, Exception):
                continue
            d, data = res
            if data.get('status') == 'ok':
                merged_cache[d] = data
            scraped += 1

        print(f"    Scraped {scraped}/{len(to_scrape)} domains")

    with open(SCRAPE_MERGED, 'w') as f:
        json.dump(merged_cache, f, ensure_ascii=False)

    ok = sum(1 for v in merged_cache.values() if v.get('status') == 'ok')
    print(f"  Total scraped domains: {len(merged_cache)} ({ok} ok)")
    return merged_cache


# ─── PHASE 3: GPT-4O-MINI ANALYSIS ────────────────────────────────────────

async def gpt_analyze(company_name, domain, web_content, semaphore, client):
    prompt = f"""You are analyzing a company for EasyStaff — a B2B platform that helps companies pay their Pakistani/international contractors and freelancers from UAE.

COMPANY: {company_name}
DOMAIN: {domain}
WEBSITE:
{web_content[:2500]}

Analyze and respond in strict JSON:
{{
  "industry": "one of: outsourcing/staffing/software/saas/ai/it_services/consulting/digital_agency/fintech/ecommerce/logistics/trading/construction/real_estate/professional_services/education/healthcare/manufacturing/hospitality/retail/other",
  "what_they_do": "1 sentence",
  "employee_estimate": "number or range like 10-50",
  "has_pakistan_operations": true/false,
  "has_offshore_teams": true/false,
  "has_remote_workers": true/false,
  "contractor_friendly": true/false,
  "mentions_freelancers": true/false,
  "international_presence": true/false,
  "fit_score": 0-100,
  "fit_reason": "1 sentence why they would or wouldn't need EasyStaff for Pakistan contractor payments"
}}

Score 80-100 if: outsourcing/staffing/IT company with offshore teams or Pakistan presence
Score 60-79 if: tech/consulting company with remote workers, international operations
Score 40-59 if: small company that COULD have contractors abroad
Score 20-39 if: local-only business, manufacturing, retail
Score 0-19 if: enterprise, government, or irrelevant industry"""

    async with semaphore:
        try:
            response = await client.chat.completions.create(
                model='gpt-4o-mini',
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
                max_tokens=350,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {'error': str(e), 'fit_score': 0}


async def phase3_gpt(companies_sorted, scrape_data):
    import openai

    print(f"\n[Phase 3] GPT-4o-mini deep analysis...")

    # Load existing v6 GPT cache + v5 GPT cache
    cache = {}
    for cache_file in [GPT_CACHE, '/tmp/uae_pk_v5_gpt.json']:
        if os.path.exists(cache_file):
            try:
                old = json.load(open(cache_file))
                for k, v in old.items():
                    if k not in cache and 'error' not in v:
                        cache[k] = v
                print(f"  Loaded {cache_file}: {len(old)} entries")
            except Exception:
                pass
    print(f"  Total cached GPT analyses: {len(cache)}")

    from app.core.config import settings
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Select ALL companies with meaningful website content for GPT
    to_analyze = []
    for comp in companies_sorted:
        d = comp['domain']
        if not d or d.lower() in cache:
            continue
        sd = scrape_data.get(d, {})
        if not isinstance(sd, dict):
            continue
        content = f"{sd.get('title', '')} {sd.get('description', '')} {sd.get('text', '')}"
        if len(content.strip()) < 100:
            continue
        to_analyze.append((comp, content))

    print(f"  Companies to GPT-analyze: {len(to_analyze)}")
    est_cost = len(to_analyze) * 0.00015
    print(f"  Estimated cost: ${est_cost:.2f}")

    if not to_analyze:
        print("  Nothing new to analyze")
        return cache

    semaphore = asyncio.Semaphore(25)
    errors = 0

    # Process in batches of 100 for progress reporting + intermediate saves
    batch_size = 100
    for batch_start in range(0, len(to_analyze), batch_size):
        batch = to_analyze[batch_start:batch_start + batch_size]

        async def analyze_one(comp, text):
            return comp['domain'], await gpt_analyze(
                comp['company_name'], comp['domain'], text, semaphore, client)

        tasks = [analyze_one(comp, text) for comp, text in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                errors += 1
                continue
            domain, data = res
            if 'error' in data:
                errors += 1
            else:
                cache[domain] = data

        print(f"    Batch {batch_start//batch_size + 1}: analyzed {min(batch_start + batch_size, len(to_analyze))}/{len(to_analyze)} (errors: {errors})")
        with open(GPT_CACHE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)

    with open(GPT_CACHE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False)
    print(f"  Done: {len(to_analyze)} analyzed, {errors} errors, {len(cache)} total cached")
    return cache


# ─── PHASE 4: FINAL SCORING + OUTPUT ──────────────────────────────────────

def phase4_output(companies_sorted, scrape_data, gpt_data, sheets, all_filtered):
    print(f"\n[Phase 4] Final scoring & output...")

    reasoning_file = open(REASONING_LOG, 'w')

    final_scored = []
    for comp in companies_sorted:
        domain = comp['domain']
        gpt = gpt_data.get(domain) if domain else None
        has_gpt = gpt is not None and 'error' not in gpt

        if has_gpt:
            gpt_fit = gpt.get('fit_score', 0)
            gpt_ind = INDUSTRY_FIT.get(gpt.get('industry', 'other'), 45)
            gpt_sz_score, gpt_sz_detail = estimate_company_size_score(
                None, comp['contact_count'], gpt.get('employee_estimate'))

            # Pakistan operations from GPT
            pk_gpt = 30
            if gpt.get('has_pakistan_operations'):
                pk_gpt = 100
            elif gpt.get('has_offshore_teams'):
                pk_gpt = 75
            elif gpt.get('has_remote_workers'):
                pk_gpt = 60
            elif gpt.get('contractor_friendly'):
                pk_gpt = 55

            # Combine GPT PK signal with contact-level PK signal
            combined_pk = max(pk_gpt, comp['pk_score'])

            # FINAL FORMULA (GPT-enriched):
            # GPT fit: 30% | PK connection: 25% | Industry: 15% | Size: 15% | Role: 15%
            final = (
                gpt_fit * 0.30 +
                combined_pk * 0.25 +
                gpt_ind * 0.15 +
                gpt_sz_score * 0.15 +
                comp['best_role_score'] * 0.15
            )

            industry = gpt.get('industry', comp['industry'])
            size_est = str(gpt.get('employee_estimate', comp['clay_size'] or ''))
            pk_ops = 'YES' if gpt.get('has_pakistan_operations') else (
                'Offshore' if gpt.get('has_offshore_teams') else (
                'Remote' if gpt.get('has_remote_workers') else 'No'))
            contractor_sig = 'YES' if gpt.get('contractor_friendly') else (
                'Freelancers' if gpt.get('mentions_freelancers') else 'No')
            web_summary = gpt.get('what_they_do', '')[:150]
            reasoning = (
                f"GPT_fit={gpt_fit} | {industry}({gpt_ind}) | "
                f"Size={size_est}({gpt_sz_score}) | PKops={pk_ops}({combined_pk}) | "
                f"Role=T{comp['best_tier']}({comp['best_role_score']}) | "
                f"PK_contact={comp['pk_reason'][:50]} | "
                f"Why: {gpt.get('fit_reason', '')[:80]}"
            )
        else:
            final = comp['pre_score']
            industry = comp['industry']
            size_est = comp['clay_size'] or f"~{comp['contact_count']} contacts"
            pk_ops = ''
            contractor_sig = ''
            sd = scrape_data.get(domain, {}) if domain else {}
            if isinstance(sd, dict) and sd.get('status') == 'ok':
                web_summary = f"{sd.get('title', '')[:80]} | {sd.get('description', '')[:120]}"
            else:
                web_summary = ''
            reasoning = (
                f"PreScore | {industry}({comp['industry_score']}) | "
                f"Size={comp['size_detail'][:30]}({comp['size_score']}) | "
                f"PK={comp['pk_reason'][:50]}({comp['pk_score']}) | "
                f"Role=T{comp['best_tier']}({comp['best_role_score']}) | "
                f"TLD={comp['tld_score']}"
            )

        comp_data = {
            'company_name': comp['company_name'],
            'domain': domain,
            'contacts': comp['contacts'],
            'contact_count': comp['contact_count'],
            'final_score': round(final, 2),
            'has_gpt': has_gpt,
            'industry': industry,
            'size_estimate': size_est,
            'pk_ops': pk_ops,
            'contractor_signal': contractor_sig,
            'best_tier': comp['best_tier'],
            'best_role_score': comp['best_role_score'],
            'web_summary': web_summary,
            'reasoning': reasoning,
            'pk_score': comp['pk_score'],
            'pk_reason': comp['pk_reason'],
        }
        final_scored.append(comp_data)

        # Log reasoning
        reasoning_file.write(json.dumps({
            'company': comp['company_name'],
            'domain': domain,
            'final_score': round(final, 2),
            'has_gpt': has_gpt,
            'reasoning': reasoning,
        }, ensure_ascii=False) + '\n')

    reasoning_file.close()

    # Sort: GPT-analyzed first (more confident), then non-GPT
    gpt_companies = sorted([c for c in final_scored if c['has_gpt']], key=lambda x: -x['final_score'])
    non_gpt = sorted([c for c in final_scored if not c['has_gpt']], key=lambda x: -x['final_score'])
    all_companies = gpt_companies + non_gpt

    print(f"  GPT-analyzed: {len(gpt_companies)} companies")
    print(f"  Pre-score only: {len(non_gpt)} companies")
    if gpt_companies:
        print(f"  Top GPT score: {gpt_companies[0]['final_score']} ({gpt_companies[0]['company_name']})")

    # SELECT CONTACTS: max 3 per company, diversify roles, dedup
    selected = []
    seen_linkedin = set()
    seen_names = set()

    for comp in all_companies:
        if len(selected) >= 2000:
            break
        pool = comp['contacts']
        # Sort by: best role first, then highest PK origin score
        pool.sort(key=lambda c: (c['role_tier'], -int(c.get('origin_score') or '0')))
        picked = []
        picked_tiers = set()

        for c in pool:
            if len(picked) >= 3:
                break
            li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
            full_name = f"{c['first_name']} {c['last_name']}".lower().strip()

            # Dedup by LinkedIn
            if li and li in seen_linkedin:
                continue
            # Dedup by name
            if full_name and full_name != ' ' and full_name in seen_names:
                continue

            # Diversify roles: try different tiers
            tier = c['role_tier']
            if tier in picked_tiers and len(picked) < 3:
                # Check if there are contacts from other tiers we haven't picked
                remaining = [cc for cc in pool
                             if cc['role_tier'] != tier
                             and cc['role_tier'] not in picked_tiers
                             and (cc.get('linkedin_url') or '').lower().strip().rstrip('/') not in seen_linkedin]
                if remaining and len(picked) < 2:
                    continue  # skip this duplicate tier, pick diverse one next

            picked.append(c)
            picked_tiers.add(tier)
            if li:
                seen_linkedin.add(li)
            if full_name and full_name != ' ':
                seen_names.add(full_name)

        for c in picked:
            origin = int(c.get('origin_score') or '0')
            origin_labels = {10: 'Urdu speaker', 9: 'PK university', 8: 'PK surname'}
            origin_signal = origin_labels.get(origin, c.get('name_match_reason', '')[:50] or c.get('search_type', ''))

            selected.append({
                'rank': 0,
                'first_name': c['first_name'],
                'last_name': c['last_name'],
                'email': c.get('email', ''),
                'title': c['title'],
                'role_tier': f"T{c['role_tier']}",
                'company': comp['company_name'],
                'domain': comp['domain'],
                'location': c['location'],
                'linkedin_url': c.get('linkedin_url', ''),
                'origin_signal': origin_signal,
                'company_score': comp['final_score'],
                'industry': comp['industry'],
                'size_estimate': comp['size_estimate'],
                'pk_ops': comp['pk_ops'],
                'contractor_signal': comp['contractor_signal'],
                'contacts_at_company': comp['contact_count'],
                'web_summary': comp['web_summary'],
                'reasoning': comp['reasoning'],
            })

    for i, s in enumerate(selected):
        s['rank'] = i + 1

    print(f"\n  Selected: {len(selected)} contacts")

    # Write to Google Sheet
    print("\n  Writing to Google Sheet...")
    try:
        sheets.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range=f"'{OUTPUT_TAB}'!A1:Z3000"
        ).execute()
    except Exception:
        # Tab might not exist, create it
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': OUTPUT_TAB}}}]}
        ).execute()

    header = [
        'Rank', 'First Name', 'Last Name', 'Email', 'Title', 'Role Tier',
        'Company', 'Domain', 'Location', 'LinkedIn URL', 'Origin Signal',
        'Company Score', 'Industry', 'Size Estimate', 'Pakistan Ops',
        'Contractor Signal', 'Contacts at Company', 'Website Summary', 'Reasoning'
    ]
    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([
            s['rank'], s['first_name'], s['last_name'], s['email'], s['title'],
            s['role_tier'], s['company'], s['domain'], s['location'], s['linkedin_url'],
            s['origin_signal'], s['company_score'], s['industry'], s['size_estimate'],
            s['pk_ops'], s['contractor_signal'], s['contacts_at_company'],
            s['web_summary'], s['reasoning'],
        ])

    # Batch write
    batch_size = 500
    for i in range(0, len(sheet_rows), batch_size):
        batch = sheet_rows[i:i + batch_size]
        start_row = i + 1
        end_row = start_row + len(batch) - 1
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{OUTPUT_TAB}'!A{start_row}:S{end_row}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()
        print(f"    Wrote rows {start_row}-{end_row}")

    # Save local JSON
    json_output = [{k: v for k, v in s.items()} for s in selected]
    with open(SCORED_OUTPUT, 'w') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)

    # ─── PRINT COMPREHENSIVE SUMMARY ───────────────────────────────────────
    print("\n" + "=" * 80)
    print("FINAL SUMMARY — UAE-PAKISTAN OUTREACH PRIORITY 2000")
    print("=" * 80)

    print(f"\nPipeline: {len(all_filtered)} filtered → {len(all_companies)} companies → {len(selected)} contacts")
    print(f"GPT-analyzed companies: {len(gpt_companies)}")

    print("\n📊 Score Distribution:")
    for lo, hi in [(80, 101), (60, 80), (40, 60), (20, 40), (0, 20)]:
        cnt = sum(1 for s in selected if lo <= s['company_score'] < hi)
        bar = '#' * (cnt // 10)
        print(f"  {lo:>3}-{hi:<3}: {cnt:>4} contacts {bar}")

    print("\n🏭 Industry Distribution:")
    for ind, cnt in Counter(s['industry'] for s in selected).most_common(15):
        print(f"  {ind:<25}: {cnt}")

    print("\n👤 Role Tier Distribution:")
    tier_map = {
        'T1': 'Finance/Payroll', 'T2': 'Operations', 'T3': 'HR/People',
        'T4': 'CEO/Founder', 'T5': 'Tech Leadership', 'T6': 'BD/Sales', 'T7': 'Other'
    }
    for tier in sorted(Counter(s['role_tier'] for s in selected)):
        cnt = sum(1 for s in selected if s['role_tier'] == tier)
        print(f"  {tier} ({tier_map.get(tier, '?'):<20}): {cnt}")

    print("\n🇵🇰 Pakistan Connection:")
    pk_counts = Counter(s['origin_signal'] for s in selected if s['origin_signal'])
    for sig, cnt in pk_counts.most_common(10):
        print(f"  {sig[:40]:<42}: {cnt}")

    print("\n🏢 Top 30 Companies (by score):")
    shown = set()
    rank = 0
    for s in selected:
        if s['company'] in shown:
            continue
        shown.add(s['company'])
        rank += 1
        if rank > 30:
            break
        print(f"  #{rank:>2} Score={s['company_score']:>5.1f} | {s['company'][:30]:<30} | "
              f"{s['industry']:<15} | {s['pk_ops'] or 'pre-score'}")

    print(f"\n📋 Output: '{OUTPUT_TAB}' in sheet")
    print(f"   https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print(f"   JSON: {SCORED_OUTPUT}")
    print(f"   Reasoning log: {REASONING_LOG}")

    return selected


# ─── MAIN ─────────────────────────────────────────────────────────────────

async def async_main():
    t0 = time.time()
    sheets = get_sheets_service()

    # Phase 1: Read + filter + pre-score
    companies, filtered = phase1_prescore(sheets)
    if not companies:
        return
    print(f"  Phase 1: {time.time()-t0:.1f}s\n")

    # Phase 2: Merge caches + scrape remaining
    t2 = time.time()
    merged = load_and_merge_caches()
    scrape_data = await phase2_scrape(companies, merged)
    print(f"  Phase 2: {time.time()-t2:.1f}s")

    # Phase 3: GPT-4o-mini analysis
    t3 = time.time()
    gpt_data = await phase3_gpt(companies, scrape_data)
    print(f"  Phase 3: {time.time()-t3:.1f}s")

    # Phase 4: Final scoring + output
    phase4_output(companies, scrape_data, gpt_data, sheets, filtered)
    print(f"\nTotal: {time.time()-t0:.1f}s")


def main():
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
