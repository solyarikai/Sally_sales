#!/usr/bin/env python3
"""
UAE-Pakistan v4 Lead Scoring Script
Scores 15,369 contacts for EasyStaff outreach — UAE companies paying Pakistani contractors.

Fixes from v3:
1. Hard filter: UAE-only contacts (removes Pakistan/India/elsewhere)
2. No circular "Pakistan connection score" — uses website scraping for Pakistan ops signals
3. Actually visits company websites for industry/size detection
4. Clean 18-column output, no duplicates
"""

import asyncio
import json
import re
import time
import warnings
import ssl
from collections import defaultdict, Counter
from typing import Optional

warnings.filterwarnings('ignore')

# Google Sheets setup
from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-Pakistan - New Only'
OUTPUT_TAB = 'UAE-Pakistan Priority 2000'

def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

UAE_SIGNALS = [
    'dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah', 'ras al-khaimah',
    'fujairah', 'umm al quwain', 'umm al-quwain', 'uae', 'united arab emirates',
    'دبي', 'أبو ظبي', 'الإمارات العربية المتحدة', 'الشارقة', 'عجمان',
    'الإمارات', 'ابوظبي', 'ابو ظبي',
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
    'gartner.com', 'adobe.com', 'intel.com',
}

BLACKLIST_KEYWORDS = [
    'bank', 'banking', 'insurance', 'airline', 'airways', 'petroleum',
    'government', 'ministry', 'authority', 'university', 'hospital',
    'armed forces', 'military', 'police', 'central bank', 'stock exchange',
]

INDUSTRY_SCORES = {
    'outsourcing': 100, 'bpo': 100, 'staffing': 95, 'recruitment': 95,
    'software': 90, 'saas': 90, 'it services': 85, 'technology': 85,
    'consulting': 75, 'digital agency': 75, 'marketing agency': 75,
    'fintech': 70, 'ecommerce': 60, 'e-commerce': 60,
    'professional services': 55, 'logistics': 50, 'supply chain': 50,
    'trading': 45, 'import-export': 45, 'import export': 45,
    'construction': 40, 'engineering': 40,
    'real estate': 35, 'property': 35,
    'food': 30, 'hospitality': 30, 'restaurant': 30, 'hotel': 30,
    'healthcare': 25, 'medical': 25, 'pharma': 25,
    'education': 20, 'training': 20,
}

INDUSTRY_KEYWORDS = {
    'outsourcing': ['outsourc', 'bpo', 'offshoring', 'offshore team', 'nearshore'],
    'staffing': ['staffing', 'recruitment', 'hiring', 'talent acquisition', 'headhunt', 'manpower', 'workforce solution'],
    'software': ['software', 'saas', 'platform', 'app development', 'web development', 'mobile app', 'cloud'],
    'it services': ['it services', 'it solutions', 'managed services', 'it consulting', 'tech support', 'infrastructure'],
    'consulting': ['consulting', 'advisory', 'strategy', 'management consulting'],
    'digital agency': ['digital agency', 'creative agency', 'web agency', 'design agency', 'digital marketing', 'seo', 'ppc', 'social media agency'],
    'marketing agency': ['marketing agency', 'advertising', 'media agency', 'brand agency', 'pr agency'],
    'fintech': ['fintech', 'payment', 'crypto', 'blockchain', 'defi', 'neobank', 'lending'],
    'ecommerce': ['ecommerce', 'e-commerce', 'online store', 'shopify', 'marketplace', 'retail tech'],
    'professional services': ['professional services', 'legal', 'accounting', 'audit', 'law firm', 'compliance'],
    'logistics': ['logistics', 'supply chain', 'freight', 'shipping', 'warehousing', 'last mile', 'courier'],
    'trading': ['trading', 'import', 'export', 'wholesale', 'distribution', 'commodity'],
    'construction': ['construction', 'contracting', 'building', 'civil engineering', 'infrastructure project'],
    'real estate': ['real estate', 'property', 'realty', 'brokerage'],
    'food': ['food', 'restaurant', 'catering', 'f&b', 'food delivery', 'cloud kitchen'],
    'hospitality': ['hotel', 'hospitality', 'resort', 'tourism', 'travel'],
    'healthcare': ['healthcare', 'medical', 'clinic', 'hospital', 'pharma', 'biotech', 'health tech'],
    'education': ['education', 'edtech', 'training', 'academy', 'school', 'university', 'learning'],
}

ROLE_TIERS = {
    1: ['cfo', 'chief financial', 'head of finance', 'finance director', 'vp finance',
        'payroll', 'controller', 'treasurer', 'finance manager', 'financial controller',
        'director of finance', 'head of payroll', 'compensation', 'accounts payable'],
    2: ['coo', 'chief operating', 'hr director', 'head of people', 'head of hr',
        'vp hr', 'vp operations', 'procurement', 'people operations', 'chief people',
        'head of operations', 'director of operations', 'human resources director',
        'talent director', 'people director', 'admin director', 'office manager'],
    3: ['ceo', 'founder', 'co-founder', 'managing director', 'general manager',
        'country manager', 'regional manager', 'owner', 'president', 'partner',
        'director general', 'principal', 'chairman', 'chief executive', 'entrepreneur',
        'managing partner'],
    4: ['cto', 'chief technology', 'vp engineering', 'sales director', 'head of sales',
        'business development', 'commercial director', 'marketing director',
        'head of marketing', 'chief marketing', 'cmo', 'cro', 'chief revenue',
        'head of business', 'growth', 'partnerships'],
}

ANTI_TITLES = ['intern', 'student', 'freelancer', 'seeking', 'unemployed', 'looking for',
               'open to work', 'aspiring', 'trainee', 'volunteer', 'retired']


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def is_uae_location(loc: str) -> bool:
    if not loc:
        return False
    loc_lower = loc.lower().strip()
    for signal in UAE_SIGNALS:
        if signal in loc_lower:
            return True
    return False

def is_excluded_location(loc: str) -> bool:
    if not loc:
        return True
    loc_lower = loc.lower().strip()
    for ex in EXCLUDE_LOCATIONS:
        if ex in loc_lower:
            return True
    return False

def is_blacklisted_domain(domain: str) -> bool:
    if not domain:
        return False
    d = domain.lower().strip()
    if d in BLACKLIST_DOMAINS:
        return True
    if d.endswith('.gov') or '.gov.' in d:
        return True
    if d.endswith('.mil') or '.mil.' in d:
        return True
    return False

def is_blacklisted_company(company: str) -> bool:
    if not company:
        return False
    c = company.lower()
    for kw in BLACKLIST_KEYWORDS:
        if kw in c:
            return True
    return False

def get_role_tier(title: str) -> int:
    if not title:
        return 5
    t = title.lower()
    for anti in ANTI_TITLES:
        if anti in t:
            return 6  # Anti-tier
    for tier, keywords in ROLE_TIERS.items():
        for kw in keywords:
            if kw in t:
                return tier
    return 5

def role_authority_score(tier: int) -> int:
    return {1: 100, 2: 85, 3: 65, 4: 40, 5: 10, 6: 0}.get(tier, 10)

def strip_html(html: str) -> str:
    """Remove HTML tags and get visible text."""
    if not html:
        return ''
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:3000]

def detect_industry(text: str, company_name: str, domain: str) -> tuple[str, int]:
    """Detect industry from website text + company name + domain. Returns (industry, score)."""
    combined = (text + ' ' + (company_name or '') + ' ' + (domain or '')).lower()
    best_industry = 'unknown'
    best_score = 0
    best_matches = 0

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > best_matches or (matches == best_matches and INDUSTRY_SCORES.get(industry, 40) > best_score):
            if matches > 0:
                best_industry = industry
                best_score = INDUSTRY_SCORES.get(industry, 40)
                best_matches = matches

    if best_matches == 0:
        return 'unknown', 40

    return best_industry, best_score

def detect_size_from_text(text: str) -> Optional[int]:
    """Try to detect employee count from website text."""
    if not text:
        return None
    patterns = [
        r'(\d{1,5})\+?\s*(?:employees|team members|professionals|experts|people|staff|specialists)',
        r'team\s+of\s+(\d{1,5})',
        r'over\s+(\d{1,5})\s+(?:employees|people|professionals)',
        r'(\d{1,5})\s*-\s*(\d{1,5})\s*employees',
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            groups = m.groups()
            if len(groups) == 2:
                return (int(groups[0]) + int(groups[1])) // 2
            return int(groups[0])
    return None

def size_fit_score(employee_count: Optional[int], contact_count: int) -> tuple[int, str]:
    """Score based on company size. Returns (score, estimate_str)."""
    if employee_count is not None:
        n = employee_count
        if 11 <= n <= 50:
            return 100, f'{n} employees'
        elif 51 <= n <= 200:
            return 90, f'{n} employees'
        elif 1 <= n <= 10:
            return 60, f'{n} employees'
        elif 201 <= n <= 500:
            return 50, f'{n} employees'
        elif 501 <= n <= 1000:
            return 20, f'{n} employees'
        else:
            return 5, f'{n} employees'

    # Contact count proxy
    proxy_map = {1: (70, '~SMB (1 contact)'), 2: (65, '~SMB (2 contacts)'),
                 3: (55, '~mid (3 contacts)')}
    if contact_count in proxy_map:
        return proxy_map[contact_count]
    elif 4 <= contact_count <= 5:
        return 40, f'~mid ({contact_count} contacts)'
    elif 6 <= contact_count <= 9:
        return 20, f'~large ({contact_count} contacts)'
    else:
        return 5, f'~enterprise ({contact_count} contacts)'

def pakistan_ops_score(website_text: str, company_name: str, domain: str,
                      high_origin_count: int) -> tuple[int, str]:
    """Score Pakistan operations signal."""
    reasons = []
    score = 30  # base

    text = (website_text or '').lower()
    cname = (company_name or '').lower()
    dom = (domain or '').lower()

    # Website mentions Pakistan cities
    pk_cities = ['pakistan', 'karachi', 'lahore', 'islamabad', 'rawalpindi', 'faisalabad']
    if any(city in text for city in pk_cities):
        score = max(score, 90)
        reasons.append('website mentions Pakistan')

    # Website mentions offshore/remote
    offshore_kw = ['offshore', 'outsourc', 'remote team', 'distributed team', 'nearshore',
                   'remote workforce', 'global team']
    if any(kw in text for kw in offshore_kw):
        score = max(score, 70)
        reasons.append('website mentions offshore/remote')

    # Company name suggests Pakistan
    if any(city in cname for city in ['pk', 'karachi', 'lahore', 'islamabad', 'pakistan']):
        score = max(score, 60)
        reasons.append('company name suggests PK')

    # .pk domain
    if dom.endswith('.pk') or '.pk.' in dom:
        score = max(score, 80)
        reasons.append('.pk domain')

    # Multiple high-origin contacts
    if high_origin_count >= 3:
        score = max(score, 50)
        reasons.append(f'{high_origin_count} high-origin contacts')

    signal = '; '.join(reasons) if reasons else 'base (UAE+PK corridor)'
    return score, signal

def domain_quality_score(status: str) -> int:
    if status == 'ok':
        return 100
    elif status == 'thin':
        return 60
    elif status == 'none':
        return 30
    elif status == 'dead':
        return 10
    return 30

def compute_company_score(industry_score: int, size_score: int, pk_ops_score: int,
                          domain_score: int, role_score: int) -> float:
    """Weighted average: Industry 30% + Size 25% + PK Ops 20% + Domain 15% + Role 10%"""
    return (industry_score * 0.30 + size_score * 0.25 + pk_ops_score * 0.20 +
            domain_score * 0.15 + role_score * 0.10)


# ─── WEBSITE SCRAPING ────────────────────────────────────────────────────────

async def fetch_website(domain: str, semaphore: asyncio.Semaphore, client) -> dict:
    """Fetch website and extract content."""
    if not domain:
        return {'status': 'none', 'title': '', 'description': '', 'text': ''}

    domain = domain.lower().strip().rstrip('/')
    if not domain.startswith('http'):
        url = f'https://{domain}'
    else:
        url = domain

    async with semaphore:
        try:
            resp = await client.get(url, timeout=8.0, follow_redirects=True)
            if 200 <= resp.status_code < 400:
                html = resp.text
                if len(html) < 200:
                    return {'status': 'thin', 'title': '', 'description': '', 'text': strip_html(html)}

                # Extract title
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else ''

                # Extract meta description
                desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
                if not desc_match:
                    desc_match = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
                description = desc_match.group(1).strip() if desc_match else ''

                text = strip_html(html)[:2000]

                return {'status': 'ok', 'title': title[:200], 'description': description[:500], 'text': text}
            else:
                return {'status': 'dead', 'title': '', 'description': '', 'text': ''}
        except Exception:
            return {'status': 'dead', 'title': '', 'description': '', 'text': ''}


async def scrape_websites(domains: list[str]) -> dict[str, dict]:
    """Scrape up to ~400 company websites concurrently."""
    import httpx

    semaphore = asyncio.Semaphore(15)
    results = {}

    # Deduplicate
    unique_domains = list(set(d for d in domains if d))
    print(f"  Scraping {len(unique_domains)} unique domains...")

    async with httpx.AsyncClient(verify=False, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }) as client:
        tasks = {d: fetch_website(d, semaphore, client) for d in unique_domains}
        for domain, task in tasks.items():
            results[domain] = await task

    ok_count = sum(1 for v in results.values() if v['status'] == 'ok')
    thin_count = sum(1 for v in results.values() if v['status'] == 'thin')
    dead_count = sum(1 for v in results.values() if v['status'] == 'dead')
    print(f"  Results: {ok_count} ok, {thin_count} thin, {dead_count} dead")

    return results


# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    sheets = get_sheets_service()

    # ── Step 1: Read source data ──────────────────────────────────────────
    print("=" * 70)
    print("UAE-PAKISTAN v4 LEAD SCORING")
    print("=" * 70)
    print("\n[1/7] Reading source data...")

    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SOURCE_TAB}'!A1:Z20000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("ERROR: No data found!")
        return

    headers = rows[0]
    print(f"  Headers: {headers}")
    print(f"  Total rows: {len(rows) - 1}")

    # Build column index
    col_idx = {h.strip(): i for i, h in enumerate(headers)}
    data_rows = rows[1:]

    def get_val(row, col_name):
        idx = col_idx.get(col_name)
        if idx is None or idx >= len(row):
            return ''
        return (row[idx] or '').strip()

    # Parse all contacts
    contacts = []
    for row in data_rows:
        contacts.append({
            'name': get_val(row, 'Name'),
            'first_name': get_val(row, 'First Name'),
            'last_name': get_val(row, 'Last Name'),
            'title': get_val(row, 'Title'),
            'company': get_val(row, 'Company'),
            'domain': get_val(row, 'Domain'),
            'location': get_val(row, 'Location'),
            'linkedin_url': get_val(row, 'LinkedIn URL'),
            'origin_score': get_val(row, 'Origin Score'),
            'name_match_reason': get_val(row, 'Name Match Reason'),
            'search_type': get_val(row, 'Search Type'),
        })

    print(f"  Parsed {len(contacts)} contacts")

    # ── Step 2: Hard filter — UAE only ────────────────────────────────────
    print("\n[2/7] Filtering to UAE-only contacts...")

    uae_contacts = []
    excluded_pakistan = 0
    excluded_other = 0

    for c in contacts:
        loc = c['location']
        if is_excluded_location(loc):
            if any(x in loc.lower() for x in ['pakistan', 'karachi', 'lahore', 'islamabad']):
                excluded_pakistan += 1
            else:
                excluded_other += 1
            continue
        if is_uae_location(loc):
            uae_contacts.append(c)
        else:
            excluded_other += 1

    print(f"  UAE contacts: {len(uae_contacts)}")
    print(f"  Excluded Pakistan: {excluded_pakistan}")
    print(f"  Excluded other: {excluded_other}")

    # ── Step 3: Blacklist filter ──────────────────────────────────────────
    print("\n[3/7] Applying enterprise blacklist...")

    # Count contacts per domain for 10+ check
    domain_counts = Counter(c['domain'].lower() for c in uae_contacts if c['domain'])

    filtered = []
    excluded_domain_bl = 0
    excluded_company_bl = 0
    excluded_too_many = 0

    for c in uae_contacts:
        d = c['domain'].lower() if c['domain'] else ''
        if is_blacklisted_domain(d):
            excluded_domain_bl += 1
            continue
        if is_blacklisted_company(c['company']):
            excluded_company_bl += 1
            continue
        if d and domain_counts[d] >= 10:
            excluded_too_many += 1
            continue
        filtered.append(c)

    print(f"  After blacklist: {len(filtered)}")
    print(f"  Excluded by domain: {excluded_domain_bl}")
    print(f"  Excluded by company name: {excluded_company_bl}")
    print(f"  Excluded 10+ contacts at domain: {excluded_too_many}")

    # ── Step 4: Group by company ──────────────────────────────────────────
    print("\n[4/7] Grouping by company...")

    # Group by (company_lower, domain_lower) to identify unique companies
    companies = defaultdict(list)
    for c in filtered:
        key = (c['company'].lower().strip(), c['domain'].lower().strip() if c['domain'] else '')
        companies[key].append(c)

    print(f"  Unique companies: {len(companies)}")

    # Compute role tiers for all contacts
    for c in filtered:
        c['role_tier'] = get_role_tier(c['title'])

    # ── Step 5: Preliminary scoring + website scraping ────────────────────
    print("\n[5/7] Preliminary scoring + website scraping...")

    # Quick preliminary score for each company (no website data yet)
    company_prelim = {}
    for key, company_contacts in companies.items():
        company_name, domain = key
        best_tier = min(c['role_tier'] for c in company_contacts)
        contact_count = len(company_contacts)
        has_domain = 1 if domain else 0
        # Simple prelim: role + origin + domain presence
        avg_origin = sum(int(c['origin_score'] or '0') for c in company_contacts) / contact_count
        prelim = role_authority_score(best_tier) * 0.3 + avg_origin * 5 + has_domain * 20 + min(contact_count, 3) * 5
        company_prelim[key] = prelim

    # Sort by preliminary score and take top 400 for scraping
    sorted_companies = sorted(company_prelim.items(), key=lambda x: -x[1])
    top_companies_for_scraping = sorted_companies[:400]
    domains_to_scrape = [key[1] for key, _ in top_companies_for_scraping if key[1]]

    # Also add all unique domains from remaining companies for basic checks
    all_domains = list(set(d for d in domains_to_scrape if d))
    print(f"  Companies to scrape: {len(all_domains)} unique domains (from top 400)")

    # Run async scraping
    website_data = asyncio.run(scrape_websites(all_domains))

    # ── Step 6: Full scoring ──────────────────────────────────────────────
    print("\n[6/7] Computing full scores...")

    scored_companies = []
    for key, company_contacts in companies.items():
        company_name, domain = key
        contact_count = len(company_contacts)

        # Website data
        wd = website_data.get(domain, {'status': 'none', 'title': '', 'description': '', 'text': ''})
        website_text = f"{wd.get('title', '')} {wd.get('description', '')} {wd.get('text', '')}"

        # Industry
        industry, industry_score = detect_industry(website_text, company_name, domain)

        # Size
        employee_count = detect_size_from_text(website_text)
        size_score, size_estimate = size_fit_score(employee_count, contact_count)

        # Pakistan ops signal
        high_origin = sum(1 for c in company_contacts if int(c.get('origin_score', '0') or '0') >= 9)
        pk_score, pk_signal = pakistan_ops_score(website_text, company_name, domain, high_origin)

        # Domain quality
        dom_score = domain_quality_score(wd['status'])

        # Best role
        best_tier = min(c['role_tier'] for c in company_contacts)
        role_score = role_authority_score(best_tier)

        # Final weighted score
        total_score = compute_company_score(industry_score, size_score, pk_score, dom_score, role_score)

        # Website summary
        web_summary = ''
        if wd['status'] == 'ok':
            title = wd.get('title', '')[:80]
            desc = wd.get('description', '')[:120]
            web_summary = f"{title} | {desc}" if desc else title
        elif wd['status'] == 'thin':
            web_summary = 'thin content'
        elif wd['status'] == 'dead':
            web_summary = 'site unreachable'

        # Build reasoning
        reasoning_parts = [
            f"Industry={industry}({industry_score})",
            f"Size={size_estimate}({size_score})",
            f"PKops={pk_signal}({pk_score})",
            f"Domain={wd['status']}({dom_score})",
            f"BestRole=T{best_tier}({role_score})",
        ]
        reasoning = ' | '.join(reasoning_parts)

        scored_companies.append({
            'key': key,
            'company_name': company_contacts[0]['company'],  # Original case
            'domain': domain,
            'contacts': company_contacts,
            'score': round(total_score, 2),
            'industry': industry,
            'industry_score': industry_score,
            'size_estimate': size_estimate,
            'size_score': size_score,
            'pk_signal': pk_signal,
            'pk_score': pk_score,
            'domain_status': wd['status'],
            'domain_score': dom_score,
            'best_tier': best_tier,
            'role_score': role_score,
            'contact_count': contact_count,
            'web_summary': web_summary,
            'reasoning': reasoning,
        })

    # Sort by score descending
    scored_companies.sort(key=lambda x: -x['score'])

    print(f"  Scored {len(scored_companies)} companies")
    if scored_companies:
        print(f"  Top score: {scored_companies[0]['score']} ({scored_companies[0]['company_name']})")
        print(f"  Median score: {scored_companies[len(scored_companies)//2]['score']}")

    # ── Step 7: Select contacts (max 3/company, diversify roles) ──────────
    print("\n[7/7] Selecting top 2000 contacts...")

    selected = []
    seen_linkedin = set()
    seen_names = set()

    for comp in scored_companies:
        if len(selected) >= 2000:
            break

        contacts_pool = comp['contacts']

        # Sort by: role_tier asc, origin_score desc, has domain desc
        contacts_pool.sort(key=lambda c: (
            c['role_tier'],
            -int(c.get('origin_score', '0') or '0'),
            -(1 if c['domain'] else 0),
        ))

        # Pick max 3, diversify tiers
        picked = []
        picked_tiers = set()
        for c in contacts_pool:
            if len(picked) >= 3:
                break
            # Dedup
            li = c['linkedin_url'].lower().strip().rstrip('/')
            full_name = f"{c['first_name']} {c['last_name']}".lower().strip()
            if li and li in seen_linkedin:
                continue
            if full_name and full_name in seen_names and full_name != ' ':
                continue

            # Prefer different tiers
            tier = c['role_tier']
            if tier in picked_tiers and len(contacts_pool) > len(picked) + 1:
                # Skip if same tier and more candidates available (but add if last chance)
                other_tiers = [cc for cc in contacts_pool if cc['role_tier'] != tier
                               and cc['linkedin_url'].lower().strip().rstrip('/') not in seen_linkedin]
                if other_tiers and len(picked) < 2:
                    continue

            picked.append(c)
            picked_tiers.add(tier)
            if li:
                seen_linkedin.add(li)
            if full_name and full_name != ' ':
                seen_names.add(full_name)

        for c in picked:
            origin_signal = c.get('name_match_reason', '') or c.get('search_type', '')
            if c.get('origin_score'):
                origin_signal = f"Score {c['origin_score']}: {origin_signal}"

            selected.append({
                'rank': 0,  # Will be set after
                'first_name': c['first_name'],
                'last_name': c['last_name'],
                'title': c['title'],
                'role_tier': f"T{c['role_tier']}",
                'company': comp['company_name'],
                'domain': comp['domain'],
                'domain_status': comp['domain_status'],
                'location': c['location'],
                'linkedin_url': c['linkedin_url'],
                'origin_signal': origin_signal,
                'company_score': comp['score'],
                'industry': comp['industry'],
                'size_estimate': comp['size_estimate'],
                'pk_ops_signal': comp['pk_signal'],
                'contacts_at_company': comp['contact_count'],
                'website_summary': comp['web_summary'],
                'reasoning': comp['reasoning'],
            })

    # Assign ranks
    for i, s in enumerate(selected):
        s['rank'] = i + 1

    print(f"  Selected {len(selected)} contacts")

    # ── Save results ──────────────────────────────────────────────────────
    print("\nSaving results...")

    # Save detailed txt
    with open('/tmp/uae_pk_v4_results.txt', 'w') as f:
        f.write("UAE-Pakistan v4 Lead Scoring Results\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total contacts read: {len(contacts)}\n")
        f.write(f"UAE contacts: {len(uae_contacts)}\n")
        f.write(f"After blacklist: {len(filtered)}\n")
        f.write(f"Unique companies: {len(companies)}\n")
        f.write(f"Selected contacts: {len(selected)}\n\n")

        f.write("TOP 50 COMPANIES:\n")
        f.write("-" * 70 + "\n")
        for i, comp in enumerate(scored_companies[:50]):
            f.write(f"\n#{i+1} Score={comp['score']} | {comp['company_name']} | {comp['domain']}\n")
            f.write(f"   Industry: {comp['industry']} ({comp['industry_score']})\n")
            f.write(f"   Size: {comp['size_estimate']} ({comp['size_score']})\n")
            f.write(f"   PK Ops: {comp['pk_signal']} ({comp['pk_score']})\n")
            f.write(f"   Domain: {comp['domain_status']} ({comp['domain_score']})\n")
            f.write(f"   Best Role Tier: T{comp['best_tier']} ({comp['role_score']})\n")
            f.write(f"   Contacts: {comp['contact_count']}\n")
            f.write(f"   Web: {comp['web_summary'][:100]}\n")

        f.write("\n\nSCORE DISTRIBUTION:\n")
        brackets = [(80, 100), (60, 80), (40, 60), (20, 40), (0, 20)]
        for lo, hi in brackets:
            cnt = sum(1 for c in scored_companies if lo <= c['score'] < hi)
            f.write(f"  {lo}-{hi}: {cnt} companies\n")

        f.write("\n\nINDUSTRY DISTRIBUTION (top 2000):\n")
        ind_counts = Counter(s['industry'] for s in selected)
        for ind, cnt in ind_counts.most_common():
            f.write(f"  {ind}: {cnt}\n")

    # Save JSON
    with open('/tmp/uae_pk_v4_scored.json', 'w') as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    print(f"  Saved /tmp/uae_pk_v4_results.txt")
    print(f"  Saved /tmp/uae_pk_v4_scored.json")

    # ── Write to Google Sheet ─────────────────────────────────────────────
    print("\nWriting to Google Sheet...")

    # Clear the output tab
    sheets.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"'{OUTPUT_TAB}'!A1:Z3000"
    ).execute()
    print("  Cleared output tab")

    # Prepare header + rows
    header = [
        'Rank', 'First Name', 'Last Name', 'Title', 'Role Tier',
        'Company', 'Domain', 'Domain Status', 'Location', 'LinkedIn URL',
        'Origin Signal', 'Company Score', 'Industry', 'Size Estimate',
        'Pakistan Ops Signal', 'Contacts at Company', 'Website Summary', 'Reasoning'
    ]

    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([
            s['rank'],
            s['first_name'],
            s['last_name'],
            s['title'],
            s['role_tier'],
            s['company'],
            s['domain'],
            s['domain_status'],
            s['location'],
            s['linkedin_url'],
            s['origin_signal'],
            s['company_score'],
            s['industry'],
            s['size_estimate'],
            s['pk_ops_signal'],
            s['contacts_at_company'],
            s['website_summary'],
            s['reasoning'],
        ])

    # Write in batches of 500 to avoid payload limits
    batch_size = 500
    for i in range(0, len(sheet_rows), batch_size):
        batch = sheet_rows[i:i + batch_size]
        start_row = i + 1
        end_row = start_row + len(batch) - 1
        range_str = f"'{OUTPUT_TAB}'!A{start_row}:R{end_row}"
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=range_str,
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()
        print(f"  Wrote rows {start_row}-{end_row}")

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total contacts in sheet: {len(contacts)}")
    print(f"UAE contacts: {len(uae_contacts)}")
    print(f"After blacklist: {len(filtered)}")
    print(f"Unique companies scored: {len(scored_companies)}")
    print(f"Websites scraped: {len(website_data)}")
    print(f"Final selected: {len(selected)}")
    print(f"Time elapsed: {elapsed:.1f}s")

    # Score distribution
    print("\nScore distribution (selected contacts):")
    brackets = [(80, 100), (60, 80), (40, 60), (20, 40), (0, 20)]
    for lo, hi in brackets:
        cnt = sum(1 for s in selected if lo <= s['company_score'] < hi)
        print(f"  {lo}-{hi}: {cnt}")

    # Industry distribution
    print("\nIndustry distribution:")
    ind_counts = Counter(s['industry'] for s in selected)
    for ind, cnt in ind_counts.most_common(10):
        print(f"  {ind}: {cnt}")

    # Role tier distribution
    print("\nRole tier distribution:")
    tier_counts = Counter(s['role_tier'] for s in selected)
    for tier in sorted(tier_counts):
        print(f"  {tier}: {tier_counts[tier]}")

    # Top 10
    print("\nTop 10 contacts:")
    for s in selected[:10]:
        print(f"  #{s['rank']} {s['first_name']} {s['last_name']} | {s['title']} | {s['company']} | Score={s['company_score']}")

    print(f"\nDone! Output in tab '{OUTPUT_TAB}'")
    print(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == '__main__':
    main()
