#!/usr/bin/env python3
"""
UAE-Pakistan v7 Lead Scoring Pipeline — Via Negativa

Score by EXCLUDING bad fits, not confirming good ones.
Integrates 3 data sources: website scrape + GPT binary flags + Clay People Search.

Scoring weights (from plan):
- Origin signal: 40% (cultural network = primary hypothesis)
- Role authority: 20% (CFO > COO > HR > CEO > CTO)
- Survived all red flags: 20% (via negativa — passing IS the signal)
- Website outsourcing signal: 10% (mentions outsourcing/contractors/remote)
- Clay confirmation: 10% (5-30 talent-country employees = sweet spot)

Red flags (any = hard exclusion or heavy penalty):
1. HQ in talent country (.pk/.ph/.za domain, "based in Karachi")
2. Enterprise (100+ Clay employees, blacklist, 10+ contacts same domain)
3. Irrelevant industry (construction, hospitality — from GPT or keywords)
4. Contact not from talent-country origin (origin_score < 8)
5. Anti-title (intern, student, freelancer)
6. Talent country in country list only (20+ countries listed)
7. Formal talent-country office (Clay 50-100, GPT has_office)
8. Placeholder/empty website

Data sources loaded automatically:
- /tmp/uae_pk_v6_scrape.json (8500+ scraped homepages)
- /tmp/deep_scrape_v7.json (multi-page scrape for top companies)
- /tmp/{corridor}_v7_gpt_flags.json (GPT-4o-mini binary flags)
- ~/magnum-opus-project/repo/scripts/clay/exports/people_*.json (Clay employees)

Usage (inside Docker on server):
  python3 scripts/uae_pk_v7_score.py uae-pakistan
  python3 scripts/uae_pk_v7_score.py au-philippines
  python3 scripts/uae_pk_v7_score.py arabic-southafrica
  python3 scripts/uae_pk_v7_score.py   # all corridors
"""

import csv
import glob
import json
import os
import re
import sys
import time
import warnings
from collections import Counter, defaultdict

# Allow running from /scripts/ inside Docker (app is at /app)
if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

warnings.filterwarnings('ignore')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
# Persistent storage: /scripts/data/ survives container restarts
DATA_DIR = '/scripts/data' if os.path.isdir('/scripts/data') else '/tmp'
SCRAPE_CACHE = f'{DATA_DIR}/uae_pk_v6_scrape.json' if os.path.exists(f'/scripts/data/uae_pk_v6_scrape.json') else '/tmp/uae_pk_v6_scrape.json'
DEEP_SCRAPE_CACHE = f'{DATA_DIR}/deep_scrape_v7.json' if os.path.exists(f'/scripts/data/deep_scrape_v7.json') else '/tmp/deep_scrape_v7.json'
# Works in Docker (/scripts/) and on host (~/magnum-opus-project/repo/scripts/)
CLAY_EXPORTS_DIR = (
    '/scripts/clay/exports' if os.path.isdir('/scripts/clay/exports')
    else os.path.expanduser('~/magnum-opus-project/repo/scripts/clay/exports')
)


def corridor_files(corridor_name):
    slug = corridor_name.replace('-', '_')
    data_dir = '/scripts/data' if os.path.isdir('/scripts/data') else '/tmp'
    return {
        'analysis_csv': f'{data_dir}/{slug}_v8_company_analysis.csv',
        'scored_json': f'{data_dir}/{slug}_v8_scored.json',
        'gpt_flags': f'{data_dir}/{slug}_v8_gpt_flags.json',
    }


CORRIDOR_CONFIG = {
    'uae-pakistan': {
        'source_tab': 'UAE-Pakistan - New Only',
        'output_tab': 'UAE-Pakistan v8 Scored',
        'talent_country': 'pakistan',
        'talent_country_key': 'pakistan',
        'talent_cities': ['karachi', 'lahore', 'islamabad', 'rawalpindi', 'faisalabad', 'peshawar', 'multan'],
        'buyer_signals': ['dubai', 'abu dhabi', 'sharjah', 'ajman', 'uae', 'united arab emirates',
                          '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a'],
        'exclude_locations': ['pakistan', 'karachi', 'lahore', 'islamabad', 'rawalpindi',
                              'india', 'mumbai', 'delhi', 'bangalore', 'chennai', 'pune',
                              'noida', 'gurgaon', 'gurugram', 'hyderabad, india'],
        'select_count': 2000,
    },
    'au-philippines': {
        'source_tab': 'AU-Philippines - New Only',
        'output_tab': 'AU-Philippines v8 Scored',
        'talent_country': 'philippines',
        'talent_country_key': 'philippines',
        'talent_cities': ['manila', 'cebu', 'davao', 'makati', 'quezon', 'taguig', 'pasig', 'bgc'],
        'buyer_signals': ['australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide',
                          'canberra', 'gold coast', 'hobart', 'darwin', 'new south wales',
                          'victoria', 'queensland', 'western australia'],
        'exclude_locations': ['philippines', 'manila', 'cebu', 'davao', 'makati', 'quezon',
                              'india', 'mumbai', 'delhi', 'bangalore', 'indonesia', 'jakarta'],
        'select_count': 1000,
    },
    'arabic-southafrica': {
        'source_tab': 'Arabic-SouthAfrica - New Only',
        'output_tab': 'Arabic-SouthAfrica v8 Scored',
        'talent_country': 'south africa',
        'talent_country_key': 'south_africa',
        'talent_cities': ['johannesburg', 'cape town', 'durban', 'pretoria', 'port elizabeth', 'bloemfontein'],
        'buyer_signals': ['qatar', 'doha', 'saudi', 'riyadh', 'jeddah', 'bahrain', 'manama',
                          'kuwait', 'oman', 'muscat', 'uae', 'dubai', 'abu dhabi',
                          '\u0642\u0637\u0631', '\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629', '\u0627\u0644\u0628\u062d\u0631\u064a\u0646',
                          '\u0627\u0644\u0643\u0648\u064a\u062a', '\u0639\u0645\u0627\u0646'],
        'exclude_locations': ['south africa', 'johannesburg', 'cape town', 'durban', 'pretoria',
                              'india', 'mumbai', 'delhi', 'nigeria', 'lagos', 'kenya', 'nairobi'],
        'select_count': 1000,
    },
}


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


# ─── ENTERPRISE BLACKLIST ─────────────────────────────────────────────────

# Manually verified: PK-HQ companies with UAE shelf offices, competitors, non-UAE HQ
# Detected during quality review iteration — these pass all automated filters
# because their homepages hide PK addresses and GPT misclassifies HQ
VERIFIED_EXCLUDE = {
    'softmindsol.com',    # PK-HQ Lahore dev shop (Johar Town address on contact page)
    'wpexperts.io',       # PK-HQ Karachi WordPress agency (200+ PK staff)
    'abhi.co',            # PK-HQ fintech (Karachi) + payroll competitor
    'ipglobal247.com',    # Poland-HQ IT (founded in Poland per about page)
    'allomate.com',       # PK-HQ Lahore (Gulberg address)
    'mnadigital.io',      # PK-HQ Lahore (New Garden Town address)
    'ovexbee.com',        # PK-based digital agency (PK phone on homepage)
    'daairah.com',        # PK-HQ creative agency (PK phone on homepage)
    'techdigital.biz',    # PK-HQ (Model Town Lahore address + PK phone)
    'greencorebeauty.com', # PK-HQ (DHA Phase address, subsidiaries in Karachi/Lahore/Islamabad)
    'designersity.com', 'designersity.ae',  # India-based (Mumbai in about page)
    '3techno.com',        # 3000 PK employees = enterprise, likely PK operations center
    'dynasoftcloud.com',  # PK phone +92 on contact page, Lahore/Karachi offices
    'pxgeo.com',          # Enterprise 400+ employees, marine geophysics (in-house payroll)
    'ikragcae.com',       # HR recruitment + migration services = competitor-adjacent
    # Companies that pass ALL algorithmic filters but are known-bad.
    # ONLY add here when GPT misclassifies would_need_easystaff=True
    # for companies that clearly don't match ICP. Algorithm catches 14/19.
    'burkshipping.com',      # PK-HQ logistics — GPT wrongly says need=True
    'greatlinklogistics.com',# PK-HQ logistics — GPT wrongly says need=True
    'alphaedits.com',        # Freelancer wedding editor — GPT wrongly says need=True
    'alifinvestments.com',   # Restaurant/investment group — GPT wrongly says need=True
    'eandenterprise.com',    # Etisalat enterprise subsidiary — GPT missed enterprise flag
}

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
    'dpworld.com', 'rta.ae', 'jumeirah.com', 'meraas.com', 'difc.ae',
    'accenture.com', 'mckinsey.com', 'bcg.com', 'bain.com', 'adobe.com',
    'intel.com', 'marriott.com', 'accor.com', 'sap.com', 'ge.com',
    'morganstanley.com', 'ubs.com', 'novartis.com', 'pfizer.com',
    'bakerhughes.com', 'honeywell.com', 'schneider-electric.com',
    'totalenergies.com', 'chevron.com', 'positivity.org',
    # Global ad/media agencies (enterprise, thousands of employees)
    'ogilvy.com', 'saatchi.com', 'publicisgroupe.com', 'wpp.com', 'omnicomgroup.com',
    'dentsu.com', 'havas.com', 'leoburnett.com', 'tbwa.com', 'bbdo.com',
    'grey.com', 'jwt.com', 'mccann.com', 'ddb.com', 'fcb.com',
    # Global consulting firms
    'adlittle.com', 'rolandberger.com', 'oliverwyman.com', 'lek.com',
}

SHARED_HOSTING = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'linkedin.com',
    'facebook.com', 'vercel.app', 'netlify.app', 'herokuapp.com', 'github.io',
    'wordpress.com', 'wixsite.com', 'squarespace.com', 'shopify.com', 'google.com',
    'live.com', 'icloud.com', 'aol.com', 'protonmail.com', 'zoho.com',
}

ANTI_TITLES = ['intern', 'student', 'freelanc', 'looking for', 'seeking',
               'unemployed', 'open to work', 'trainee', 'apprentice',
               'virtual assistant', 'receptionist', 'driver', 'security guard',
               'cleaner', 'waiter', 'cashier']

# Hard-excluded industries — ONLY physically-impossible-remote.
# LEARNING: Real estate, retail, pet companies ACTUALLY CONVERTED.
# Any company can have remote contractors for marketing/admin/dev.
# Only exclude where remote work is physically impossible.
EXCLUDED_INDUSTRIES = {
    # Physical on-site work only
    'construction', 'hospitality',
    # Heavy industry (rigs, plants, mines)
    'oil and gas', 'mining',
    # Government (regulated procurement, won't use EasyStaff)
    'government', 'public sector',
}


# ─── DATA LOADERS ────────────────────────────────────────────────────────

def load_clay_employees():
    """Load Clay People Search exports, aggregate by domain → employee count."""
    clay_counts = defaultdict(int)
    clay_files = glob.glob(os.path.join(CLAY_EXPORTS_DIR, 'people_*.json'))
    total_records = 0

    for f in clay_files:
        basename = os.path.basename(f)
        # Skip meta/matched/unmatched/search_results — only people data
        if any(x in basename for x in ['meta', 'matched', 'unmatched', 'search_results']):
            continue
        try:
            data = json.load(open(f))
            if not isinstance(data, list):
                continue
            for person in data:
                domain = (person.get('Company Domain') or
                          person.get('company_domain') or '').lower().strip()
                if domain:
                    clay_counts[domain] += 1
                    total_records += 1
        except Exception:
            pass

    print(f"  Clay data: {total_records} employees across {len(clay_counts)} companies")
    return dict(clay_counts)


def load_gpt_flags(corridor_name):
    """Load GPT-4o-mini binary flags for a corridor."""
    files = corridor_files(corridor_name)
    gpt_file = files['gpt_flags']
    if os.path.exists(gpt_file):
        data = json.load(open(gpt_file))
        print(f"  GPT flags: {len(data)} domains")
        return data
    print(f"  GPT flags: not found ({gpt_file})")
    return {}


def load_deep_scrape():
    """Load multi-page deep scrape cache."""
    if os.path.exists(DEEP_SCRAPE_CACHE):
        data = json.load(open(DEEP_SCRAPE_CACHE))
        print(f"  Deep scrape: {len(data)} domains")
        return data
    print(f"  Deep scrape: not found")
    return {}


# ─── WEBSITE ANALYSIS (KEYWORD-BASED, GPT-AUGMENTED) ─────────────────────

def analyze_website(domain, scraped_data, gpt_flags, deep_data,
                    talent_country='pakistan', talent_cities=None):
    """
    Analyze company website using keyword rules + GPT flags when available.

    GPT flags OVERRIDE keyword detection for:
    - Industry classification (GPT vertical replaces keyword matching)
    - HQ detection (GPT hq_in_talent flag augments keyword detection)
    - Office detection (GPT has_office flag — NEW, keywords can't detect this well)
    - Outsourcing/contractor/remote signals (GPT augments keywords)
    """
    if not scraped_data or not isinstance(scraped_data, dict):
        if gpt_flags:
            # Have GPT analysis but no scrape — use GPT data alone
            return _build_from_gpt_only(domain, gpt_flags, talent_country)
        return {'status': 'no_data', 'industry': 'unknown', 'industry_score': 0}

    title = (scraped_data.get('title') or '').lower()
    desc = (scraped_data.get('description') or '').lower()
    text = (scraped_data.get('text') or '').lower()

    # Augment with deep scrape pages
    dd = deep_data.get(domain, {}) if deep_data else {}
    if dd.get('pages'):
        for page_type in ['about', 'contact', 'team', 'locations']:
            page = dd['pages'].get(page_type, {})
            if page.get('text'):
                text = text + ' ' + page['text'].lower()

    full = f"{title} {desc} {text}"

    if not talent_cities:
        talent_cities = []

    result = {
        'domain': domain,
        'status': 'analyzed',
        'title': (scraped_data.get('title') or '')[:100],
        'description': (scraped_data.get('description') or '')[:200],
        'text_length': len(text),
        'positive_signals': [],
        'negative_signals': [],
        'evidence': [],
        'red_flags': [],
    }

    # ─── PLACEHOLDER DETECTION (Red Flag #8) ─────────────────────────
    if len(text) < 100:
        result['is_placeholder'] = True
        result['industry'] = 'unknown'
        result['industry_score'] = 0
        result['red_flags'].append('placeholder_empty')
        result['negative_signals'].append('thin/empty website')
        return result

    placeholder_patterns = ['lorem ipsum', 'coming soon', 'under construction',
                           'parked domain', 'this domain', 'buy this domain',
                           'domain for sale', 'godaddy', 'squarespace.com/templates']
    if any(p in full for p in placeholder_patterns):
        result['is_placeholder'] = True
        result['industry'] = 'unknown'
        result['industry_score'] = 0
        result['red_flags'].append('placeholder_parked')
        result['negative_signals'].append('placeholder/parked website')
        return result

    result['is_placeholder'] = False

    # ─── HQ DETECTION (Red Flag #1) ──────────────────────────────────
    hq_in_talent_country = False
    hq_signals = [
        f'based in {talent_country}', f'headquartered in {talent_country}',
        f'company in {talent_country}', f'{talent_country} based',
        f'leading company in {talent_country}', f'founded in {talent_country}',
        'pvt. ltd', 'pvt ltd', '(pvt)', 'private limited',
        f'software house {talent_country}',
    ]
    for city in talent_cities:
        hq_signals.extend([
            f'based in {city}', f'headquartered in {city}', f'company in {city}',
            f'company {city}', f'agency {city}',
            f'{city}, {talent_country}',
            f'made with in {city}',
        ])

    if any(sig in full for sig in hq_signals):
        hq_in_talent_country = True

    # TLD check
    if domain:
        tld_map = {'pakistan': '.pk', 'philippines': '.ph', 'south africa': '.za'}
        talent_tld = tld_map.get(talent_country, '')
        if talent_tld and domain.lower().endswith(talent_tld):
            hq_in_talent_country = True

    # GPT override — more reliable than keyword matching
    talent_key = talent_country.replace(' ', '_')
    if gpt_flags:
        # v8 flags (flat structure)
        if gpt_flags.get(f'is_hq_in_{talent_key}', False):
            hq_in_talent_country = True
        # v7 flags (nested structure) fallback
        rf = gpt_flags.get('red_flags', {})
        if rf.get(f'hq_in_{talent_key}', False):
            hq_in_talent_country = True

    # ─── PK-HQ OVERRIDE — GPT can't distinguish PK-HQ from UAE-HQ ──
    # GPT sees "Dubai" on the website and says is_hq_in_uae=True even for PK companies
    # with a Dubai shelf office. Use hard signals from website text to detect PK-based companies.
    pk_neighborhoods = ['gulberg', 'johar town', 'dha phase', 'model town',
                        'shahrah-e-faisal', 'blue area', 'clifton',
                        'defence housing authority', 'dha karachi', 'dha lahore', 'dha islamabad',
                        'i-8', 'i-9', 'i-10', 'g-11', 'f-6', 'f-7', 'f-8',
                        'bahria town', 'askari', 'cantt', 'saddar',
                        'university road', 'mall road', 'liberty',
                        'daftarkhwan', 'arfa tower', 'nust', 'lums',
                        'national incubation center', 'plan9',
                        'garden town', 'new garden town', 'faisal town',
                        'township', 'wapda town', 'iqbal town', 'sabzazar']
    ph_neighborhoods = ['makati', 'bgc', 'bonifacio', 'quezon city', 'ortigas',
                        'alabang', 'eastwood', 'ayala', 'pasig city', 'taguig city']
    sa_neighborhoods = ['sandton', 'rosebank', 'bryanston', 'woodmead', 'midrand',
                        'century city', 'claremont', 'stellenbosch']

    neighborhood_map = {'pakistan': pk_neighborhoods, 'philippines': ph_neighborhoods, 'south africa': sa_neighborhoods}
    neighborhoods = neighborhood_map.get(talent_country, [])
    has_talent_neighborhood = any(n in full for n in neighborhoods)

    # PK phone numbers: +92 or 03xx pattern
    import re as _re
    pk_phone_patterns = [r'\+92[\s\-]?\d', r'\b03[0-9]{2}[\s\-]?[0-9]{3}', r'\b92[0-9]{10}\b']
    has_pk_phone = any(_re.search(p, full) for p in pk_phone_patterns)

    # Tech/outsourcing industry from GPT (not yet set in result at this point)
    gpt_vertical = (gpt_flags.get('company_vertical') or '').lower() if gpt_flags else ''
    tech_industries = {'outsourcing', 'software_dev', 'it_services', 'tech', 'technology',
                       'digital_agency', 'digital marketing', 'saas', 'ai_ml',
                       'staffing', 'digital agency', 'it services',
                       'marketing and advertising', 'media'}

    # Strong PK-HQ signals (override GPT's wrong is_hq_in_uae=True)
    is_likely_pk_hq = False
    pk_hq_reason = ''
    if not hq_in_talent_country:
        # PK neighborhood + tech industry = almost certainly PK dev shop
        if has_talent_neighborhood and gpt_vertical in tech_industries:
            is_likely_pk_hq = True
            pk_hq_reason = 'PK neighborhood + tech industry'
        # PK phone listed and company is tech/outsourcing
        elif has_pk_phone and gpt_vertical in tech_industries:
            is_likely_pk_hq = True
            pk_hq_reason = 'PK phone + tech industry'
        # Website text: "our team in [PK city]" or "development center in [PK city]"
        for city in talent_cities:
            for phrase in [f'our team in {city}', f'development center in {city}',
                           f'our office in {city}', f'r&d in {city}',
                           f'our headquarters in {city}', f'head office in {city}']:
                if phrase in full:
                    is_likely_pk_hq = True
                    pk_hq_reason = f'"{phrase}" in website'
                    break

    if is_likely_pk_hq:
        hq_in_talent_country = True
        result['negative_signals'].append(f'likely PK-HQ ({pk_hq_reason})')

    result['hq_in_talent_country'] = hq_in_talent_country
    if hq_in_talent_country:
        result['red_flags'].append('hq_in_talent_country')
        result['negative_signals'].append(f'HQ in {talent_country}')

    # ─── FORMAL OFFICE DETECTION (Red Flag #7) ───────────────────────
    has_formal_office = False
    if gpt_flags:
        rf = gpt_flags.get('red_flags', {})
        if rf.get(f'has_{talent_key}_office', False):
            has_formal_office = True
    # Also detect from keywords: "office in {city}"
    for city in talent_cities:
        if f'office in {city}' in full:
            has_formal_office = True
            break

    result['has_formal_office'] = has_formal_office
    if has_formal_office and not hq_in_talent_country:
        result['negative_signals'].append(f'formal office in {talent_country}')

    # ─── COMPETITOR DETECTION (NEW) ───────────────────────────────────
    is_competitor = False
    if gpt_flags:
        if gpt_flags.get('is_competitor', False):
            is_competitor = True
        # Also check competitor keywords in what_they_do
        wtd = (gpt_flags.get('what_they_do') or '').lower()
        for ck in ['employer of record', 'eor ', 'payroll provider', 'payroll solution',
                    'global payroll', 'hr outsourcing provider', 'peo ']:
            if ck in wtd:
                is_competitor = True
    # Keyword fallback
    competitor_kws = ['employer of record', 'eor service', 'payroll provider',
                      'payroll solution', 'global payroll platform', 'peo service',
                      'we process payroll', 'payroll for companies']
    if any(kw in full for kw in competitor_kws):
        is_competitor = True

    result['is_competitor'] = is_competitor
    if is_competitor:
        result['red_flags'].append('competitor')
        result['negative_signals'].append('competitor (payroll/EOR provider)')

    # ─── NON-BUYER-COUNTRY HQ DETECTION (NEW) ─────────────────────────
    # If GPT says HQ is NOT in buyer country → penalty
    buyer_key = {'pakistan': 'uae', 'philippines': 'australia', 'south africa': 'gulf'}.get(talent_country, '')
    is_hq_in_buyer = True  # assume true unless proven otherwise
    if gpt_flags:
        hq_field = f'is_hq_in_{buyer_key}'
        if hq_field in gpt_flags:
            is_hq_in_buyer = gpt_flags[hq_field]
        # Also check hq_country string
        hq_country = (gpt_flags.get('hq_country') or '').lower()
        if hq_country and buyer_key == 'uae':
            uae_names = ['uae', 'united arab emirates', 'dubai', 'abu dhabi', 'sharjah']
            if not any(n in hq_country for n in uae_names):
                is_hq_in_buyer = False
        elif hq_country and buyer_key == 'australia':
            if 'australia' not in hq_country:
                is_hq_in_buyer = False

    result['is_hq_in_buyer'] = is_hq_in_buyer
    if not is_hq_in_buyer and not hq_in_talent_country:
        result['red_flags'].append('hq_not_in_buyer_country')
        hq_str = (gpt_flags.get('hq_country') or 'unknown') if gpt_flags else 'unknown'
        result['negative_signals'].append(f'HQ not in buyer country ({hq_str})')

    # ─── OUTSOURCING PROVIDER DETECTION (NEW) ─────────────────────────
    # Company that SELLS outsourcing labor vs company that BUYS it
    is_outsourcing_provider = False
    if gpt_flags:
        if gpt_flags.get('is_outsourcing_provider', False):
            is_outsourcing_provider = True
    result['is_outsourcing_provider'] = is_outsourcing_provider
    # Outsourcing providers ARE potential customers IF they're UAE-based
    # Only flag if they're genuinely PK-based (already caught by hq_in_talent_country above)
    if is_outsourcing_provider and hq_in_talent_country:
        result['red_flags'].append('outsourcing_provider_in_talent_country')
        result['negative_signals'].append(f'outsourcing provider based in {talent_country}')

    # ─── GPT "WOULD NEED EASYSTAFF" SIGNAL ────────────────────────────
    if gpt_flags:
        result['would_need_easystaff'] = gpt_flags.get('would_need_easystaff', None)
    else:
        result['would_need_easystaff'] = None

    # ─── TALENT COUNTRY MENTIONS ──────────────────────────────────────
    pk_mentions = []
    for kw in [talent_country] + talent_cities:
        if kw in full:
            for match in re.finditer(re.escape(kw), full):
                start = max(0, match.start() - 40)
                end = min(len(full), match.end() + 40)
                context = full[start:end].strip()
                pk_mentions.append(context)

    # Country list false positive (Red Flag #6)
    country_list_pattern = False
    if pk_mentions:
        for mention in pk_mentions:
            nearby_countries = 0
            for c in ['mexico', 'brazil', 'india', 'philippines', 'poland', 'germany', 'france',
                       'spain', 'italy', 'japan', 'china', 'australia', 'canada', 'nigeria',
                       'south africa', 'egypt', 'turkey', 'thailand', 'vietnam', 'indonesia',
                       'malaysia', 'singapore', 'qatar', 'oman', 'bahrain', 'peru', 'colombia',
                       'argentina', 'chile', 'panama', 'norway', 'sweden', 'denmark', 'portugal']:
                if c in mention:
                    nearby_countries += 1
            if nearby_countries >= 3:
                country_list_pattern = True
                break

    has_talent_ops = len(pk_mentions) > 0 and not country_list_pattern and not hq_in_talent_country
    result['has_talent_ops'] = has_talent_ops

    if country_list_pattern:
        result['red_flags'].append('country_list_only')
        result['negative_signals'].append(f'{talent_country} in country list only')
    elif has_talent_ops:
        result['positive_signals'].append(f'{talent_country} mentioned {len(pk_mentions)}x')
    result['evidence'].extend(pk_mentions[:3])

    # ─── OUTSOURCING / CONTRACTOR / REMOTE SIGNALS ────────────────────
    offshore_kws = ['offshore', 'nearshore', 'outsourc', 'bpo', 'offshoring']
    contractor_kws = ['contractor', 'freelanc', 'independent professional', 'gig worker',
                      'pay your team', 'pay remote', 'remote worker', 'hire freelanc',
                      'contract workforce', 'independent talent']
    remote_kws = ['remote team', 'distributed team', 'global team', 'virtual team',
                  'work from anywhere', 'remote first', 'remote-first',
                  'hire remote', 'remote hiring', 'global workforce']

    result['has_offshore'] = any(kw in full for kw in offshore_kws)
    result['has_contractors'] = any(kw in full for kw in contractor_kws)
    result['has_remote'] = any(kw in full for kw in remote_kws)

    # GPT augmentation — GPT can catch signals keywords miss
    if gpt_flags:
        gf = gpt_flags.get('green_flags', {})
        if gf.get('mentions_outsourcing_bpo'):
            result['has_offshore'] = True
        if gf.get('mentions_contractors_freelancers'):
            result['has_contractors'] = True
        if gf.get('mentions_remote_teams'):
            result['has_remote'] = True
        if gf.get(f'has_{talent_key}_workforce'):
            result['has_talent_ops'] = True

    if result['has_offshore']:
        result['positive_signals'].append('outsourcing/BPO')
    if result['has_contractors']:
        result['positive_signals'].append('contractors/freelancers')
    if result['has_remote']:
        result['positive_signals'].append('remote teams')

    # ─── INDUSTRY CLASSIFICATION ──────────────────────────────────────
    # GPT vertical takes priority — keyword matching is fallback
    if gpt_flags and gpt_flags.get('company_vertical'):
        gpt_vertical = gpt_flags['company_vertical'].lower().strip()
        result['industry'] = gpt_vertical
        result['industry_score'] = _industry_score(gpt_vertical)

        # GPT red flag overrides for industry (Red Flag #3)
        # v8 flat flags
        is_bad_industry = gpt_flags.get('is_construction_realestate_hospitality', False)
        # v7 nested flags fallback
        rf = gpt_flags.get('red_flags', {})
        is_bad_industry = is_bad_industry or rf.get('is_construction_realestate', False) or rf.get('is_hospitality_tourism', False)

        if is_bad_industry or gpt_vertical in EXCLUDED_INDUSTRIES:
            result['industry'] = gpt_vertical
            result['industry_score'] = _industry_score(gpt_vertical)
            result['red_flags'].append('irrelevant_industry')
            result['negative_signals'].append(f'{gpt_vertical} (GPT)')
    else:
        # Keyword-based fallback
        detected_industry, industry_score = _classify_industry_keywords(full, domain)
        result['industry'] = detected_industry
        result['industry_score'] = industry_score

        if detected_industry in EXCLUDED_INDUSTRIES:
            result['red_flags'].append('irrelevant_industry')
            result['negative_signals'].append(f'{detected_industry} (keyword)')

    # ─── ENTERPRISE DETECTION from GPT (Red Flag #2 augmentation) ────
    if gpt_flags:
        # v8 flag (300+ threshold)
        if gpt_flags.get('is_enterprise_300plus', False):
            result['red_flags'].append('enterprise_gpt')
            result['negative_signals'].append('enterprise 300+ (GPT)')
        # v7 flag fallback
        rf = gpt_flags.get('red_flags', {})
        if rf.get('is_enterprise_500plus', False):
            result['red_flags'].append('enterprise_gpt')
            result['negative_signals'].append('enterprise 500+ (GPT)')

    # ─── EMPLOYEE SIZE ────────────────────────────────────────────────
    employee_estimate = None
    # GPT estimate first
    if gpt_flags and gpt_flags.get('employee_estimate'):
        try:
            employee_estimate = int(gpt_flags['employee_estimate'])
        except (ValueError, TypeError):
            pass

    # Keyword fallback
    if employee_estimate is None:
        size_patterns = [
            (r'(\d{1,5})\+?\s*(?:employees|team members|professionals|engineers|people|staff)', 1),
            (r'team of (\d{1,5})', 1),
            (r'(\d{1,5})\+?\s*(?:member|person)\s+team', 1),
            (r'over\s+(\d{1,5})\s+(?:employees|professionals|people)', 1),
            (r'(\d{1,5})\s*-\s*(\d{1,5})\s*employees', 2),
        ]
        for pattern, group_count in size_patterns:
            m = re.search(pattern, full)
            if m:
                if group_count == 2:
                    employee_estimate = (int(m.group(1)) + int(m.group(2))) // 2
                else:
                    employee_estimate = int(m.group(1))
                break

    result['employee_estimate'] = employee_estimate
    result['size_score'] = _size_score(employee_estimate)

    # ─── GPT SUMMARY FIELDS ──────────────────────────────────────────
    if gpt_flags:
        result['gpt_what_they_do'] = gpt_flags.get('what_they_do', '')
        result['gpt_reasoning'] = gpt_flags.get('reasoning', '')
    else:
        result['gpt_what_they_do'] = ''
        result['gpt_reasoning'] = ''

    # ─── BUSINESS SETUP / VISA / RECRUITMENT DETECTION ─────────────
    # GPT often labels these as "business services" or "consulting" which passes filters
    visa_biz_kws = ['company formation', 'business setup', 'free zone', 'freezone setup',
                    'pro services', 'visa services', 'work permit', 'residence visa',
                    'trade license', 'mainland company', 'offshore company setup',
                    'golden visa', 'investor visa', 'employment visa',
                    'citizenship by investment', 'second passport', 'residency program']
    if any(kw in full for kw in visa_biz_kws):
        result['red_flags'].append('irrelevant_industry')
        result['negative_signals'].append('business setup/visa/citizenship (keyword)')

    # Recruitment firms disguised as tech/consulting
    recruit_kws = ['executive search', 'headhunting', 'talent acquisition firm',
                   'recruitment agency', 'staffing firm', 'cv writing', 'resume writing',
                   'we place candidates', 'hire right the first time']
    if any(kw in full for kw in recruit_kws):
        result['red_flags'].append('irrelevant_industry')
        result['negative_signals'].append('recruitment firm (keyword)')

    # ─── FREELANCER / THIN WEBSITE DETECTION ─────────────────────────
    # Gmail/yahoo contact + minimal website = not a real company
    has_gmail = any(e in full for e in ['@gmail.com', '@yahoo.com', '@hotmail.com', '@outlook.com'])
    if has_gmail and len(text) < 500:
        result['red_flags'].append('placeholder_empty')
        result['negative_signals'].append('gmail + thin website = freelancer')

    # ─── FUZZY INDUSTRY MATCHING ─────────────────────────────────────
    # GPT verticals are free-form strings. Match against excluded industries using substring.
    # Example: GPT says "pharmaceuticals" → matches "pharmac" → excluded
    # Example: GPT says "oil & gas services" → matches "oil" → excluded
    gpt_vert_lower = (gpt_flags.get('company_vertical') or '').lower() if gpt_flags else ''
    fuzzy_exclude_patterns = [
        'pharma', 'oil', 'gas ', 'petrol', 'mining',
        'hotel', 'resort', 'restaurant', 'catering',
        'property', 'real estate', 'villa',
        'school', 'university', 'academy',
        'garment', 'textile', 'apparel',
        'travel', 'tour', 'booking',
        'news', 'journal', 'media outlet',
        'salon', 'spa', 'gym', 'fitness',
        'executive search', 'headhunt', 'cv writing', 'resume writing',
        'citizenship', 'passport', 'immigration',
        'safety', 'occupational', 'hse ',
        'elv', 'cctv', 'security installation',
        'actuarial', 'insurance consult',
    ]
    if any(p in gpt_vert_lower for p in fuzzy_exclude_patterns):
        if 'irrelevant_industry' not in result.get('red_flags', []):
            result['red_flags'].append('irrelevant_industry')
            result['negative_signals'].append(f'fuzzy industry match: {gpt_vert_lower}')

    # ─── ADDITIONAL NEGATIVE SIGNALS ──────────────────────────────────
    neg_patterns = [
        ('personal_blog', ['my blog', 'my portfolio', 'personal website', 'about me']),
        ('job_board', ['find a job', 'job listing', 'apply now', 'career opportunities']),
        ('crypto_exchange', ['buy bitcoin', 'trade crypto', 'exchange platform', 'spot trading']),
        ('interior_design', ['interior design', 'home decor', 'furniture', 'renovation']),
    ]
    for neg_type, patterns in neg_patterns:
        if any(p in full for p in patterns):
            result['negative_signals'].append(neg_type)
            if neg_type == 'interior_design':
                result['red_flags'].append('irrelevant_industry')

    return result


def _build_from_gpt_only(domain, gpt_flags, talent_country):
    """Build analysis from GPT flags when no website scrape data exists."""
    talent_key = talent_country.replace(' ', '_')
    # Support both v8 (flat) and v7 (nested) flag structures
    rf = gpt_flags.get('red_flags', {})
    gf = gpt_flags.get('green_flags', {})

    result = {
        'domain': domain,
        'status': 'gpt_only',
        'title': '',
        'description': gpt_flags.get('what_they_do', ''),
        'text_length': 0,
        'positive_signals': [],
        'negative_signals': [],
        'evidence': [],
        'red_flags': [],
        'is_placeholder': False,
        'hq_in_talent_country': gpt_flags.get(f'is_hq_in_{talent_key}', rf.get(f'hq_in_{talent_key}', False)),
        'has_formal_office': rf.get(f'has_{talent_key}_office', False),
        'has_talent_ops': gpt_flags.get(f'has_{talent_key}_workforce', gf.get(f'has_{talent_key}_workforce', False)),
        'has_offshore': gpt_flags.get('mentions_outsourcing_contractors', gf.get('mentions_outsourcing_bpo', False)),
        'has_contractors': gf.get('mentions_contractors_freelancers', False),
        'has_remote': gf.get('mentions_remote_teams', False),
        'is_competitor': gpt_flags.get('is_competitor', False),
        'is_hq_in_buyer': gpt_flags.get('is_hq_in_' + {'pakistan': 'uae', 'philippines': 'australia', 'south africa': 'gulf'}.get(talent_country, ''), True),
        'is_outsourcing_provider': gpt_flags.get('is_outsourcing_provider', False),
        'would_need_easystaff': gpt_flags.get('would_need_easystaff', None),
        'industry': gpt_flags.get('company_vertical', 'other'),
        'industry_score': _industry_score(gpt_flags.get('company_vertical', 'other')),
        'employee_estimate': gpt_flags.get('employee_estimate'),
        'gpt_what_they_do': gpt_flags.get('what_they_do', ''),
        'gpt_reasoning': gpt_flags.get('reasoning', ''),
    }
    result['size_score'] = _size_score(result['employee_estimate'])

    if result['hq_in_talent_country']:
        result['red_flags'].append('hq_in_talent_country')
    if gpt_flags.get('is_construction_realestate_hospitality') or rf.get('is_construction_realestate') or rf.get('is_hospitality_tourism'):
        result['red_flags'].append('irrelevant_industry')
    if gpt_flags.get('is_enterprise_300plus') or rf.get('is_enterprise_500plus'):
        result['red_flags'].append('enterprise_gpt')
    if result['is_competitor']:
        result['red_flags'].append('competitor')
    vert = gpt_flags.get('company_vertical', '')
    if vert in EXCLUDED_INDUSTRIES:
        result['red_flags'].append('irrelevant_industry')

    return result


def _industry_score(vertical):
    """Map industry vertical to ICP fitness score."""
    scores = {
        'outsourcing': 95, 'staffing': 90, 'tech': 80, 'saas': 82,
        'software_dev': 85, 'it_services': 80, 'ai_ml': 78,
        'digital_agency': 72, 'fintech': 65, 'ecommerce': 55,
        'education': 50, 'logistics': 45, 'consulting': 35,
        'healthcare': 30, 'trading': 20, 'manufacturing': 15,
        'retail': 12, 'construction': 10, 'real_estate': 10,
        'hospitality': 8, 'other': 30,
    }
    return scores.get(vertical, 30)


def _size_score(employee_estimate):
    """Score company size — sweet spot is 10-50 employees."""
    if not employee_estimate:
        return 50  # unknown
    try:
        n = int(employee_estimate)
    except (ValueError, TypeError):
        return 50
    if 10 <= n <= 50:
        return 100
    elif 5 <= n <= 9:
        return 85
    elif 51 <= n <= 200:
        return 80
    elif 1 <= n <= 4:
        return 50
    elif 201 <= n <= 500:
        return 40
    elif n > 500:
        return 10
    return 50


def _classify_industry_keywords(full_text, domain):
    """Fallback keyword-based industry classification."""
    industry_rules = [
        ('outsourcing', 95, ['outsourc', 'bpo', 'offshoring'], []),
        ('staffing', 90, ['staffing', 'recruitment agency', 'talent acquisition', 'headhunt'], ['job seeker']),
        ('software_dev', 85, ['software develop', 'web develop', 'app develop', 'mobile develop',
                              'custom software', 'software house', 'dev shop'], []),
        ('it_services', 80, ['it services', 'it solutions', 'managed service', 'it consulting',
                             'cloud service', 'devops', 'infrastructure'], []),
        ('saas', 82, ['saas', 'platform', 'subscription', 'cloud-based'], ['real estate', 'property']),
        ('ai_ml', 78, ['artificial intelligence', 'machine learning', 'deep learning',
                       'ai-powered', 'computer vision', 'nlp'], []),
        ('digital_agency', 72, ['digital agency', 'creative agency', 'marketing agency',
                                'design agency', 'branding agency'], []),
        ('fintech', 65, ['fintech', 'financial technology', 'digital payment',
                         'blockchain', 'crypto', 'defi'], ['banking', 'bank']),
        ('ecommerce', 55, ['ecommerce', 'e-commerce', 'online store', 'marketplace'], []),
        ('education', 50, ['edtech', 'e-learning', 'online course', 'training platform'], []),
        ('logistics', 45, ['logistics', 'freight', 'shipping', 'supply chain'], []),
        ('consulting', 35, ['consulting', 'consultancy', 'advisory'], ['outsourc', 'staffing', 'software']),
        ('real_estate', 10, ['real estate', 'property', 'realty', 'broker',
                             'apartment', 'villa', 'residential', 'commercial property'], []),
        ('hospitality', 8, ['hotel', 'restaurant', 'hospitality', 'tourism', 'travel', 'resort',
                            'catering', 'food & beverage', 'f&b'], []),
        ('construction', 12, ['construction', 'building contractor', 'civil engineering'], []),
        ('healthcare', 30, ['healthcare', 'medical', 'hospital', 'clinic', 'pharma'], []),
        ('trading', 20, ['trading company', 'import export', 'commodity', 'wholesale'], []),
        ('manufacturing', 15, ['manufacturing', 'factory', 'production line', 'industrial'], []),
        ('interior_design', 10, ['interior design', 'home decor', 'furniture', 'renovation'], []),
        ('retail', 12, ['retail store', 'shop', 'fashion brand', 'apparel'], []),
    ]

    detected = 'other'
    score = 30
    best_count = 0

    for industry, ind_score, required, exclude in industry_rules:
        if any(ex in full_text for ex in exclude):
            continue
        matches = sum(1 for kw in required if kw in full_text)
        if matches > best_count:
            detected = industry
            score = ind_score
            best_count = matches

    if best_count == 0 and domain:
        d = domain.lower()
        if any(d.endswith(ext) for ext in ['.io', '.ai', '.dev', '.tech', '.app']):
            detected = 'tech'
            score = 55

    return detected, score


# ─── ROLE SCORING ────────────────────────────────────────────────────────

def get_role_tier(title):
    if not title:
        return 7, 10
    t = title.lower()
    for anti in ANTI_TITLES:
        if anti in t:
            return 99, 0

    tiers = [
        (1, 100, ['cfo', 'chief financial', 'finance director', 'head of finance', 'vp finance',
                  'payroll', 'controller', 'treasurer', 'financial controller']),
        (2, 90, ['coo', 'chief operating', 'operations director', 'head of operations',
                 'vp operations', 'operations manager', 'chief admin']),
        (3, 85, ['hr director', 'head of hr', 'head of people', 'hr manager',
                 'people & culture', 'chief human', 'vp people', 'head of talent']),
        (4, 70, ['ceo', 'chief executive', 'founder', 'co-founder', 'owner',
                 'managing director', 'general manager', 'president', 'sole proprietor']),
        (5, 50, ['cto', 'chief technology', 'vp engineering', 'head of engineering',
                 'engineering director', 'technical director']),
        (6, 30, ['head of sales', 'sales director', 'business development',
                 'commercial director', 'chief revenue']),
    ]
    for tier, score, keywords in tiers:
        for kw in keywords:
            if kw in t:
                return tier, score
    return 7, 10


# ─── VIA NEGATIVA SCORING ────────────────────────────────────────────────

def compute_company_score(analysis, best_origin, best_role_score, clay_count):
    """
    Via Negativa scoring — 5 weighted components:

    1. Origin signal (40%): Cultural network hypothesis
    2. Role authority (20%): Decision-maker = higher conversion
    3. Survived filters (20%): Passing all red flags IS the signal
    4. Website outsourcing (10%): Explicit buying signals
    5. Clay confirmation (10%): 5-30 employees = sweet spot

    Red flags → survived_filters drops to 0
    """
    # Handle missing data
    if analysis.get('is_placeholder') or analysis.get('status') == 'no_data':
        origin_s = {10: 100, 9: 90, 8: 80}.get(best_origin, 30)
        return round(origin_s * 0.40 + best_role_score * 0.20, 2)

    # 1. Origin signal (40%)
    origin_s = {10: 100, 9: 90, 8: 80}.get(best_origin, 30)

    # 2. Role authority (20%) — already 0-100 from get_role_tier
    role_s = best_role_score

    # 3. Survived filters (20%) — ALL red flags are HARD exclusions.
    # Via negativa: if ANY exclusion criterion fires, the company is OUT.
    # No soft penalties — the plan says these are universal exclusion criteria.
    red_flags = analysis.get('red_flags', [])
    hard_flags = {
        'hq_in_talent_country',                    # Red Flag #1
        'irrelevant_industry',                     # Red Flag #3
        'enterprise_gpt',                          # Red Flag #2
        'placeholder_empty', 'placeholder_parked', # Red Flag #8
        'competitor',                              # Competitor
        'outsourcing_provider_in_talent_country',  # PK-based outsourcing shop
        'hq_not_in_buyer_country',                 # Not a UAE company
        'country_list_only',                       # Red Flag #6
    }
    has_hard_flag = bool(set(red_flags) & hard_flags)

    survived_s = 0 if has_hard_flag else 100

    # GPT says "would NOT need EasyStaff" — strong penalty but NOT hard exclude
    # because GPT can't validate the cultural hypothesis (PK-origin = likely PK contractors)
    if analysis.get('would_need_easystaff') is False:
        survived_s = max(0, survived_s - 60)

    # Formal office — not a hard exclude but reduces confidence
    if analysis.get('has_formal_office') and not analysis.get('hq_in_talent_country'):
        survived_s = max(0, survived_s - 30)

    # 4. Website outsourcing signal (10%)
    outsourcing_s = 0
    if analysis.get('has_talent_ops') and not analysis.get('hq_in_talent_country'):
        outsourcing_s = 100  # Best: mentions talent country + not HQ there
    elif analysis.get('has_offshore'):
        outsourcing_s = 70
    elif analysis.get('has_contractors'):
        outsourcing_s = 55
    elif analysis.get('has_remote'):
        outsourcing_s = 40

    # 5. Clay confirmation (10%)
    clay_s = _clay_score(clay_count)

    score = (
        origin_s * 0.40 +
        role_s * 0.20 +
        survived_s * 0.20 +
        outsourcing_s * 0.10 +
        clay_s * 0.10
    )
    return round(max(0, score), 2)


def _clay_score(clay_count):
    """Score based on Clay employee count in talent country."""
    if clay_count == 0:
        return 50  # Unknown — neutral (Clay 0 doesn't mean no contractors)
    elif 1 <= clay_count <= 4:
        return 60  # Tiny presence
    elif 5 <= clay_count <= 30:
        return 100  # Sweet spot — growing team, needs payroll
    elif 31 <= clay_count <= 99:
        return 70  # Medium — might have payroll already
    else:  # 100+
        return 10  # Enterprise — already has in-house payroll


# ─── MAIN PIPELINE ────────────────────────────────────────────────────

def run_corridor(corridor_name, sheets):
    config = CORRIDOR_CONFIG[corridor_name]
    source_tab = config['source_tab']
    output_tab = config['output_tab']
    talent_country = config['talent_country']
    talent_cities = config['talent_cities']
    buyer_signals = config['buyer_signals']
    exclude_locs = config['exclude_locations']
    select_count = config['select_count']

    print(f"\n{'='*80}")
    print(f"CORRIDOR: {corridor_name.upper()} (selecting top {select_count})")
    print(f"{'='*80}")

    # ─── PHASE 0: LOAD ALL DATA SOURCES ──────────────────────────────
    print(f"\n[Phase 0] Loading data sources...")
    scrape_data = {}
    if os.path.exists(SCRAPE_CACHE):
        scrape_data = json.load(open(SCRAPE_CACHE))
        print(f"  Scrape cache: {len(scrape_data)} domains")

    deep_data = load_deep_scrape()
    gpt_flags_all = load_gpt_flags(corridor_name)
    clay_counts = load_clay_employees()

    # ─── PHASE 1: READ + FILTER ───────────────────────────────────────
    print(f"\n[Phase 1] Reading contacts from '{source_tab}'...")
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{source_tab}'!A1:Z20000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("ERROR: No data!")
        return

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
            'clay_industry': gv(row, 'Industry'),
            'clay_size': gv(row, 'Company Size'),
            'schools_clay': gv(row, 'Schools (from Clay)'),
            'origin_score': gv(row, 'Origin Score'),
            'name_match_reason': gv(row, 'Name Match Reason'),
            'search_type': gv(row, 'Search Type'),
        })
    print(f"  Total contacts: {len(contacts)}")

    # Location filter
    filtered = []
    excl_talent = excl_other = 0
    for c in contacts:
        loc = (c['location'] or '').lower()
        if any(ex in loc for ex in exclude_locs):
            if talent_country in loc:
                excl_talent += 1
            else:
                excl_other += 1
            continue
        if not loc:
            excl_other += 1
            continue
        if any(s in loc for s in buyer_signals):
            filtered.append(c)
        else:
            excl_other += 1
    print(f"  After location filter: {len(filtered)} (excl {talent_country}={excl_talent}, other={excl_other})")

    # Normalize domains
    for c in filtered:
        if c['domain'] and c['domain'].lower().strip() in SHARED_HOSTING:
            c['domain'] = ''

    # Blacklist + role filter (Red Flags #2, #5)
    domain_counts = Counter(c['domain'].lower() for c in filtered if c['domain'])
    clean = []
    bl_d = bl_e = bl_t = bl_clay_ent = 0
    for c in filtered:
        d = c['domain'].lower().strip() if c['domain'] else ''
        if d in BLACKLIST_DOMAINS or d in VERIFIED_EXCLUDE:
            bl_d += 1; continue
        if d and domain_counts[d] >= 10:
            bl_e += 1; continue
        # Clay enterprise check (Red Flag #2): 100+ employees in talent country
        if d and clay_counts.get(d, 0) >= 100:
            bl_clay_ent += 1; continue
        tier, role_score = get_role_tier(c['title'])
        if tier == 99:
            bl_t += 1; continue
        c['role_tier'] = tier
        c['role_score'] = role_score
        clean.append(c)
    print(f"  After filters: {len(clean)} "
          f"(blacklist={bl_d}, enterprise-domain={bl_e}, enterprise-clay={bl_clay_ent}, anti-title={bl_t})")

    # Group by company
    companies = defaultdict(list)
    for c in clean:
        d = c['domain'].lower().strip() if c['domain'] else ''
        key = d if d else f"__name__{c['company'].lower().strip()}"
        companies[key].append(c)
    print(f"  Unique companies: {len(companies)}")

    # ─── PHASE 2: ANALYZE + SCORE ─────────────────────────────────────
    print(f"\n[Phase 2] Analyzing with via-negativa scoring...")
    company_analyses = []
    analysis_csv_rows = []

    for key, cc in companies.items():
        company_name = cc[0]['company']
        domain = cc[0]['domain'] if not key.startswith('__name__') else ''
        contact_count = len(cc)
        best_tier = min(c['role_tier'] for c in cc)
        best_role_score = max(c['role_score'] for c in cc)
        origin_scores = [int(c.get('origin_score') or '0') for c in cc]
        best_origin = max(origin_scores) if origin_scores else 0

        # Get data for this domain
        sd = scrape_data.get(domain, {}) if domain else {}
        gf = gpt_flags_all.get(domain, {}) if domain else {}
        clay_count = clay_counts.get(domain, 0) if domain else 0

        # Analyze website (keyword + GPT augmented)
        analysis = analyze_website(domain, sd, gf, deep_data, talent_country, talent_cities)

        # Via negativa score
        final_score = compute_company_score(analysis, best_origin, best_role_score, clay_count)

        # Add Clay data to analysis for output
        analysis['clay_employees'] = clay_count

        # Build reasoning string
        pos = '; '.join(analysis.get('positive_signals', []))
        neg = '; '.join(analysis.get('negative_signals', []))
        evidence = ' | '.join(analysis.get('evidence', []))[:100]
        origin_label = {10: 'Urdu', 9: 'PK_uni', 8: 'PK_surname'}.get(best_origin, '?')

        # Include GPT summary if available
        gpt_summary = analysis.get('gpt_what_they_do', '')
        gpt_reason = analysis.get('gpt_reasoning', '')

        reasoning = (
            f"Origin={origin_label}({best_origin}) | "
            f"Role=T{best_tier}({best_role_score}) | "
            f"RedFlags={len(analysis.get('red_flags', []))} | "
            f"Clay={clay_count} | "
            f"Outsrc={'Y' if analysis.get('has_offshore') else 'n'} | "
            f"Contr={'Y' if analysis.get('has_contractors') else 'n'} | "
            f"Remote={'Y' if analysis.get('has_remote') else 'n'} | "
            f"{'GPT: ' + gpt_reason[:60] + ' | ' if gpt_reason else ''}"
            f"{'POS: ' + pos + ' | ' if pos else ''}"
            f"{'NEG: ' + neg if neg else ''}"
        )

        company_analyses.append({
            'key': key,
            'company_name': company_name,
            'domain': domain,
            'contacts': cc,
            'contact_count': contact_count,
            'final_score': final_score,
            'analysis': analysis,
            'best_tier': best_tier,
            'best_role_score': best_role_score,
            'best_origin': best_origin,
            'clay_count': clay_count,
            'reasoning': reasoning,
        })

        analysis_csv_rows.append({
            'domain': domain,
            'company': company_name,
            'score': final_score,
            'industry': analysis.get('industry', '?'),
            'industry_score': analysis.get('industry_score', 0),
            'talent_ops': analysis.get('has_talent_ops', False),
            'offshore': analysis.get('has_offshore', False),
            'contractors': analysis.get('has_contractors', False),
            'remote': analysis.get('has_remote', False),
            'employee_est': analysis.get('employee_estimate'),
            'size_score': analysis.get('size_score', 50),
            'clay_employees': clay_count,
            'red_flags': '|'.join(analysis.get('red_flags', [])),
            'is_placeholder': analysis.get('is_placeholder', False),
            'gpt_vertical': analysis.get('industry', ''),
            'gpt_summary': gpt_summary[:100],
            'positive': pos,
            'negative': neg,
            'evidence': evidence,
            'title': analysis.get('title', ''),
            'description': analysis.get('description', ''),
            'text_length': analysis.get('text_length', 0),
        })

    # Save analysis CSV
    files = corridor_files(corridor_name)
    analysis_csv = files['analysis_csv']
    scored_json = files['scored_json']
    if analysis_csv_rows:
        with open(analysis_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=analysis_csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(analysis_csv_rows)
        print(f"  Saved analysis CSV: {analysis_csv} ({len(analysis_csv_rows)} companies)")

    # Sort by score
    company_analyses.sort(key=lambda x: -x['final_score'])

    # ─── STATS ────────────────────────────────────────────────────────
    analyzed = [c for c in company_analyses if c['analysis'].get('status') in ('analyzed', 'gpt_only')]
    print(f"\n  Analysis summary:")
    print(f"  Total companies: {len(company_analyses)}")
    print(f"  Analyzed: {len(analyzed)}")
    print(f"  With GPT flags: {sum(1 for c in company_analyses if gpt_flags_all.get(c['domain']))}")
    print(f"  With Clay data: {sum(1 for c in company_analyses if c['clay_count'] > 0)}")

    has_talent = sum(1 for c in analyzed if c['analysis'].get('has_talent_ops'))
    has_offshore = sum(1 for c in analyzed if c['analysis'].get('has_offshore'))
    has_contractor = sum(1 for c in analyzed if c['analysis'].get('has_contractors'))
    has_remote = sum(1 for c in analyzed if c['analysis'].get('has_remote'))
    print(f"  Mentions {talent_country}: {has_talent}")
    print(f"  Mentions offshore: {has_offshore}")
    print(f"  Mentions contractors: {has_contractor}")
    print(f"  Mentions remote: {has_remote}")

    # Red flag distribution
    flag_counts = Counter()
    for c in company_analyses:
        for f in c['analysis'].get('red_flags', []):
            flag_counts[f] += 1
    if flag_counts:
        print(f"\n  Red flags found:")
        for flag, cnt in flag_counts.most_common():
            print(f"    {flag:<30}: {cnt}")

    # Industry distribution
    print(f"\n  Industry distribution (top 15):")
    ind_dist = Counter(c['analysis'].get('industry', '?') for c in analyzed)
    for ind, cnt in ind_dist.most_common(15):
        print(f"    {ind:<25}: {cnt}")

    # Clay employee tiers
    clay_tiers = Counter()
    for c in company_analyses:
        cc = c['clay_count']
        if cc == 0: clay_tiers['0 (unknown)'] += 1
        elif cc <= 4: clay_tiers['1-4 (tiny)'] += 1
        elif cc <= 30: clay_tiers['5-30 (sweet)'] += 1
        elif cc <= 99: clay_tiers['31-99 (medium)'] += 1
        else: clay_tiers['100+ (enterprise)'] += 1
    print(f"\n  Clay employee tiers:")
    for tier in ['0 (unknown)', '1-4 (tiny)', '5-30 (sweet)', '31-99 (medium)', '100+ (enterprise)']:
        if tier in clay_tiers:
            print(f"    {tier:<25}: {clay_tiers[tier]}")

    print(f"\n  Top 20 companies:")
    for i, c in enumerate(company_analyses[:20]):
        a = c['analysis']
        flags = '|'.join(a.get('red_flags', []))[:15] or 'clean'
        print(f"    #{i+1:>3} {c['final_score']:>5.1f} | {c['company_name'][:30]:<30} | "
              f"Clay={c['clay_count']:>3} | T{c['best_tier']} | O={c['best_origin']} | "
              f"Flags={flags}")

    # ─── PHASE 3: SELECT TOP N ─────────────────────────────────────────
    print(f"\n[Phase 3] Selecting top {select_count} contacts...")
    selected = []
    seen_li = set()
    seen_names = set()

    # Hard-exclude companies with ANY red flag from selection entirely
    hard_exclude_flags = {
        'hq_in_talent_country', 'irrelevant_industry', 'enterprise_gpt',
        'placeholder_empty', 'placeholder_parked', 'competitor',
        'outsourcing_provider_in_talent_country', 'hq_not_in_buyer_country',
        'country_list_only',
    }
    excluded_companies = 0
    for comp in company_analyses:
        if len(selected) >= select_count:
            break
        # Skip companies with ANY hard red flag
        comp_flags = set(comp['analysis'].get('red_flags', []))
        if comp_flags & hard_exclude_flags:
            excluded_companies += 1
            continue
        # would_need_easystaff=False: use as hard gate ONLY for non-tech industries.
        # For tech/digital/consulting companies, the cultural hypothesis (PK-origin =
        # likely PK contractors) is valid even when GPT says "no need" from website alone.
        # For non-tech industries (events, training, food, shipping), "no need" is reliable.
        TECH_WHITELIST = {
            'tech', 'technology', 'saas', 'software', 'software development',
            'it services', 'digital marketing', 'digital_agency', 'digital agency',
            'outsourcing', 'consulting', 'consultancy', 'fintech',
            'data and digital marketing analytics', 'cybersecurity',
            'software quality assurance', 'ai', 'ai_ml',
            'marketing', 'marketing and communications', 'creative agency',
            'business services', 'professional services',
            'language services', 'design',
            'insurtech', 'data services', 'market research',
            # NOT in whitelist: media (news outlets), logistics (shipping),
            # editing services (freelancers), pharmaceuticals, healthcare
        }
        gpt_vert = (comp['analysis'].get('industry') or '').lower()
        gpt_no_need = comp['analysis'].get('would_need_easystaff') is False
        if gpt_no_need and gpt_vert not in TECH_WHITELIST:
            excluded_companies += 1
            continue
        # Skip companies without domain — can't verify anything about them
        if not comp['domain']:
            excluded_companies += 1
            continue
        # Skip companies with no website data (dead/empty site)
        if comp['analysis'].get('status') == 'no_data' or comp['analysis'].get('is_placeholder'):
            excluded_companies += 1
            continue
        pool = comp['contacts']
        pool.sort(key=lambda c: (c['role_tier'], -int(c.get('origin_score') or '0')))

        picked = []
        picked_tiers = set()
        for c in pool:
            if len(picked) >= 3:
                break
            li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
            name = f"{c['first_name']} {c['last_name']}".lower().strip()
            if li and li in seen_li: continue
            if name and name != ' ' and name in seen_names: continue

            tier = c['role_tier']
            if tier in picked_tiers and len(picked) < 3:
                others = [cc for cc in pool if cc['role_tier'] != tier
                          and cc['role_tier'] not in picked_tiers
                          and (cc.get('linkedin_url') or '').lower().strip().rstrip('/') not in seen_li]
                if others and len(picked) < 2:
                    continue

            picked.append(c)
            picked_tiers.add(tier)
            if li: seen_li.add(li)
            if name and name != ' ': seen_names.add(name)

        a = comp['analysis']
        for c in picked:
            origin = int(c.get('origin_score') or '0')
            origin_labels = {10: 'Urdu speaker', 9: 'PK university', 8: 'PK surname'}

            # Website summary from GPT or title
            web_summary = a.get('gpt_what_they_do', '') or a.get('title', '')[:80]

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
                'origin_signal': origin_labels.get(origin, c.get('name_match_reason', '')[:40]),
                'company_score': comp['final_score'],
                'industry': a.get('industry', '?'),
                'clay_employees': comp['clay_count'],
                'talent_ops': 'YES' if a.get('has_talent_ops') else (
                    'Offshore' if a.get('has_offshore') else (
                    'Contractors' if a.get('has_contractors') else (
                    'Remote' if a.get('has_remote') else 'No evidence'))),
                'red_flags': '|'.join(a.get('red_flags', [])) or 'none',
                'size_estimate': str(a.get('employee_estimate') or '?'),
                'web_summary': web_summary[:100],
                'evidence': ' | '.join(a.get('evidence', []))[:150],
                'reasoning': comp['reasoning'][:250],
            })

    for i, s in enumerate(selected):
        s['rank'] = i + 1

    print(f"  Selected: {len(selected)} contacts")

    # ─── PHASE 4: WRITE TO GOOGLE SHEET ────────────────────────────────
    print(f"\n[Phase 4] Writing to Google Sheet...")
    try:
        sheets.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range=f"'{output_tab}'!A1:Z3000"
        ).execute()
    except Exception:
        try:
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={'requests': [{'addSheet': {'properties': {'title': output_tab}}}]}
            ).execute()
        except Exception:
            pass

    header = [
        'Rank', 'First Name', 'Last Name', 'Email', 'Title', 'Role Tier',
        'Company', 'Domain', 'Location', 'LinkedIn URL', 'Origin Signal',
        'Company Score', 'Industry', 'Clay Employees', 'Talent Ops Signal',
        'Red Flags', 'Size Estimate', 'Website Summary',
        'Evidence', 'Reasoning'
    ]
    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([
            s['rank'], s['first_name'], s['last_name'], s['email'], s['title'],
            s['role_tier'], s['company'], s['domain'], s['location'], s['linkedin_url'],
            s['origin_signal'], s['company_score'], s['industry'], s['clay_employees'],
            s['talent_ops'], s['red_flags'], s['size_estimate'], s['web_summary'],
            s.get('evidence', ''), s['reasoning'],
        ])

    batch_size = 500
    for i in range(0, len(sheet_rows), batch_size):
        batch = sheet_rows[i:i + batch_size]
        start = i + 1
        end = start + len(batch) - 1
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{output_tab}'!A{start}:T{end}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()
        print(f"    Wrote rows {start}-{end}")

    # Save JSON
    with open(scored_json, 'w') as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    # ─── SUMMARY ──────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"RESULTS — {corridor_name.upper()}")
    print(f"{'='*80}")
    print(f"Pipeline: {len(contacts)} → {len(clean)} filtered → {len(companies)} companies → {len(selected)} contacts")

    print(f"\nData sources used:")
    print(f"  Website scrape: {sum(1 for c in company_analyses if scrape_data.get(c['domain']))}/{len(company_analyses)}")
    print(f"  GPT flags: {sum(1 for c in company_analyses if gpt_flags_all.get(c['domain']))}/{len(company_analyses)}")
    print(f"  Deep scrape: {sum(1 for c in company_analyses if deep_data.get(c['domain']))}/{len(company_analyses)}")
    print(f"  Clay employees: {sum(1 for c in company_analyses if c['clay_count'] > 0)}/{len(company_analyses)}")

    print(f"\nScore Distribution:")
    for lo, hi in [(80, 101), (60, 80), (40, 60), (20, 40), (0, 20)]:
        cnt = sum(1 for s in selected if lo <= s['company_score'] < hi)
        print(f"  {lo:>3}-{hi:<3}: {cnt:>4}")

    print(f"\nTalent Country Ops:")
    for ops, cnt in Counter(s['talent_ops'] for s in selected).most_common():
        print(f"  {ops:<15}: {cnt}")

    print(f"\nRed Flags Distribution:")
    flag_dist = Counter()
    for s in selected:
        for f in s['red_flags'].split('|'):
            if f and f != 'none':
                flag_dist[f] += 1
    if flag_dist:
        for f, cnt in flag_dist.most_common():
            print(f"  {f:<30}: {cnt}")
    else:
        print(f"  All clean (no red flags in selected)")

    print(f"\nRole Tiers:")
    tier_names = {'T1': 'Finance/Payroll', 'T2': 'Operations', 'T3': 'HR',
                  'T4': 'CEO/Founder', 'T5': 'Tech', 'T6': 'BD/Sales', 'T7': 'Other'}
    for tier in sorted(Counter(s['role_tier'] for s in selected)):
        cnt = sum(1 for s in selected if s['role_tier'] == tier)
        print(f"  {tier} ({tier_names.get(tier, '?'):<15}): {cnt}")

    print(f"\nClay Confirmation in selected:")
    clay_sel = Counter()
    for s in selected:
        cc = s['clay_employees']
        if cc == 0: clay_sel['No data'] += 1
        elif cc <= 4: clay_sel['1-4 tiny'] += 1
        elif cc <= 30: clay_sel['5-30 sweet'] += 1
        elif cc <= 99: clay_sel['31-99 medium'] += 1
        else: clay_sel['100+ enterprise'] += 1
    for k, v in clay_sel.most_common():
        print(f"  {k:<20}: {v}")

    print(f"\nFiles:")
    print(f"  Sheet: '{output_tab}'")
    print(f"  Analysis CSV: {analysis_csv}")
    print(f"  Scored JSON: {scored_json}")
    print(f"  Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}")

    return selected


def main():
    import sys
    t0 = time.time()
    sheets = get_sheets_service()

    corridors = sys.argv[1:] if len(sys.argv) > 1 else list(CORRIDOR_CONFIG.keys())
    for corridor in corridors:
        if corridor not in CORRIDOR_CONFIG:
            print(f"Unknown corridor: {corridor}")
            continue
        run_corridor(corridor, sheets)

    print(f"\nTotal time: {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
