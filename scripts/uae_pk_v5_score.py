#!/usr/bin/env python3
"""
UAE-Pakistan v5 Lead Scoring Pipeline
4-phase pipeline: Pre-score -> Apify proxy scrape top 500 -> GPT-4o-mini top 200 -> Final score + output

Improvements over v4:
1. Apify residential proxy for IP rotation (no blocks)
2. GPT-4o-mini website analysis for top 200 companies (~$0.30)
3. Two-tier scoring: GPT-analyzed companies scored separately from pre-score-only
4. Crash recovery via JSON caches
"""

import asyncio
import json
import os
import re
import time
import warnings
from collections import Counter, defaultdict
from typing import Optional

warnings.filterwarnings('ignore')

# Google Sheets setup
from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-Pakistan - New Only'
OUTPUT_TAB = 'UAE-Pakistan Priority 2000'

SCRAPE_CACHE = '/tmp/uae_pk_v5_scrape.json'
GPT_CACHE = '/tmp/uae_pk_v5_gpt.json'

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
    '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a \u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u0627\u0644\u0645\u062a\u062d\u062f\u0629', '\u0627\u0644\u0634\u0627\u0631\u0642\u0629', '\u0639\u062c\u0645\u0627\u0646',
    '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u0627\u0628\u0648\u0638\u0628\u064a', '\u0627\u0628\u0648 \u0638\u0628\u064a',
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
}

INDUSTRY_KEYWORDS = {
    'outsourcing': ['outsourc', 'bpo', 'offshoring', 'nearshoring'],
    'staffing': ['staffing', 'recruitment', 'talent acqui', 'headhunt', 'hiring'],
    'software': ['software', 'saas', 'app develop', 'web develop', 'mobile develop'],
    'technology': ['technology', 'tech company', 'it company', 'information tech'],
    'it_services': ['it services', 'it solutions', 'managed services', 'it consult'],
    'consulting': ['consulting', 'consultancy', 'advisory', 'management consult'],
    'digital_agency': ['digital agency', 'creative agency', 'design agency', 'web agency'],
    'fintech': ['fintech', 'financial tech', 'payment', 'crypto', 'blockchain'],
    'ecommerce': ['ecommerce', 'e-commerce', 'online retail', 'marketplace'],
    'logistics': ['logistics', 'freight', 'shipping', 'supply chain', 'courier'],
    'trading': ['trading', 'import', 'export', 'commodit'],
    'professional_services': ['professional service', 'legal', 'accounting', 'audit'],
    'construction': ['construction', 'building', 'contracting'],
    'real_estate': ['real estate', 'property', 'realty', 'broker'],
}

INDUSTRY_SCORES = {
    'outsourcing': 100, 'staffing': 95, 'software': 90, 'it_services': 85,
    'technology': 85, 'consulting': 75, 'digital_agency': 75, 'fintech': 70,
    'ecommerce': 60, 'professional_services': 55, 'logistics': 50, 'trading': 40,
    'construction': 35, 'real_estate': 30, 'other': 45,
}

ROLE_TIERS = {
    1: ['cfo', 'chief financial', 'finance director', 'head of finance', 'vp finance',
        'payroll', 'controller', 'treasurer', 'financial controller', 'head of payments'],
    2: ['coo', 'chief operating', 'operations director', 'head of operations',
        'hr director', 'head of hr', 'head of people', 'chief people',
        'procurement', 'people operations'],
    3: ['ceo', 'chief executive', 'founder', 'co-founder', 'owner',
        'managing director', 'general manager', 'president', 'country manager',
        'regional director', 'managing partner'],
    4: ['cto', 'chief technology', 'vp engineering', 'head of engineering',
        'bd director', 'head of sales', 'sales director', 'commercial director'],
}

ROLE_SCORES = {1: 100, 2: 85, 3: 65, 4: 40, 5: 10, 6: 0}

ANTI_TITLES = ['intern', 'student', 'freelanc', 'looking for', 'seeking',
               'unemployed', 'open to work', 'trainee', 'apprentice']

SIZE_PROXY = {1: 70, 2: 65, 3: 55}

ORIGIN_LABELS = {10: 'Urdu speaker', 9: 'Pakistani university', 8: 'Pakistani surname'}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def is_uae_location(loc: str) -> bool:
    if not loc:
        return False
    loc_lower = loc.lower().strip()
    return any(s in loc_lower for s in UAE_SIGNALS)

def is_excluded_location(loc: str) -> bool:
    if not loc:
        return True
    loc_lower = loc.lower().strip()
    return any(ex in loc_lower for ex in EXCLUDE_LOCATIONS)

def is_blacklisted_domain(domain: str) -> bool:
    if not domain:
        return False
    d = domain.lower().strip()
    if d in BLACKLIST_DOMAINS:
        return True
    if d.endswith('.gov') or '.gov.' in d or d.endswith('.mil') or '.mil.' in d:
        return True
    return False

def is_blacklisted_company(company: str) -> bool:
    if not company:
        return False
    c = company.lower()
    return any(kw in c for kw in BLACKLIST_KEYWORDS)

def is_shared_hosting(domain: str) -> bool:
    if not domain:
        return True
    return domain.lower().strip() in SHARED_HOSTING

def get_role_tier(title: str) -> int:
    if not title:
        return 5
    t = title.lower()
    for anti in ANTI_TITLES:
        if anti in t:
            return 6
    for tier, keywords in ROLE_TIERS.items():
        for kw in keywords:
            if kw in t:
                return tier
    return 5

def detect_industry_from_keywords(company_name: str, domain: str) -> tuple:
    combined = f"{(company_name or '')} {(domain or '')}".lower()
    best_industry = 'other'
    best_score = INDUSTRY_SCORES['other']
    best_matches = 0
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > best_matches:
            best_industry = industry
            best_score = INDUSTRY_SCORES.get(industry, 45)
            best_matches = matches
    if best_matches == 0 and domain:
        d = domain.lower()
        if any(d.endswith(ext) for ext in ['.io', '.ai', '.dev', '.tech', '.app']):
            return 'technology', INDUSTRY_SCORES['technology']
    return best_industry, best_score

def get_size_proxy_score(contact_count: int, has_domain: bool) -> int:
    if not has_domain:
        return 50
    if contact_count in SIZE_PROXY:
        return SIZE_PROXY[contact_count]
    if 4 <= contact_count <= 5:
        return 40
    if 6 <= contact_count <= 9:
        return 20
    return 50

def get_origin_label(origin_score: int) -> str:
    return ORIGIN_LABELS.get(origin_score, '')

def strip_html(html: str) -> str:
    if not html:
        return ''
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ─── PHASE 1: PRE-SCORE ─────────────────────────────────────────────────────

def phase1_prescore(sheets):
    print("=" * 70)
    print("UAE-PAKISTAN v5 LEAD SCORING PIPELINE")
    print("=" * 70)
    print("\n[Phase 1] Reading source data & pre-scoring...")

    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{SOURCE_TAB}'!A1:Z20000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("ERROR: No data found!")
        return None, None, None

    headers = rows[0]
    print(f"  Headers: {headers}")
    col_idx = {h.strip(): i for i, h in enumerate(headers)}
    data_rows = rows[1:]

    def get_val(row, col_name):
        idx = col_idx.get(col_name)
        if idx is None or idx >= len(row):
            return ''
        return (row[idx] or '').strip()

    contacts = []
    for row in data_rows:
        contacts.append({
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
    print(f"  Total contacts: {len(contacts)}")

    # Hard filter: UAE only
    uae_contacts = []
    excluded_pk = 0
    excluded_other = 0
    for c in contacts:
        loc = c['location']
        if is_excluded_location(loc):
            if any(x in (loc or '').lower() for x in ['pakistan', 'karachi', 'lahore', 'islamabad']):
                excluded_pk += 1
            else:
                excluded_other += 1
            continue
        if is_uae_location(loc):
            uae_contacts.append(c)
        else:
            excluded_other += 1
    print(f"  UAE contacts: {len(uae_contacts)}")
    print(f"  Excluded Pakistan: {excluded_pk}, other: {excluded_other}")

    # Normalize shared hosting domains to empty
    for c in uae_contacts:
        if c['domain'] and is_shared_hosting(c['domain']):
            c['domain'] = ''

    # Blacklist + 10+ contacts per domain
    domain_counts = Counter(c['domain'].lower() for c in uae_contacts if c['domain'])
    filtered = []
    bl_domain = bl_company = bl_toomany = anti_title = 0
    for c in uae_contacts:
        d = c['domain'].lower() if c['domain'] else ''
        if is_blacklisted_domain(d):
            bl_domain += 1; continue
        if is_blacklisted_company(c['company']):
            bl_company += 1; continue
        if d and domain_counts[d] >= 10:
            bl_toomany += 1; continue
        tier = get_role_tier(c['title'])
        c['role_tier'] = tier
        if tier == 6:
            anti_title += 1; continue
        filtered.append(c)
    print(f"  After blacklist: {len(filtered)} (domain={bl_domain}, company={bl_company}, 10+={bl_toomany}, anti-title={anti_title})")

    # Group by company: domain if available, else company name
    companies = defaultdict(list)
    for c in filtered:
        d = c['domain'].lower().strip() if c['domain'] else ''
        key = d if d else f"__name__{c['company'].lower().strip()}"
        companies[key].append(c)
    print(f"  Unique companies: {len(companies)}")

    # Pre-score each company
    scored = []
    for key, cc in companies.items():
        company_name = cc[0]['company']
        domain = cc[0]['domain'] if not key.startswith('__name__') else ''
        contact_count = len(cc)
        best_tier = min(c['role_tier'] for c in cc)
        role_score = ROLE_SCORES.get(best_tier, 10)
        industry, industry_score = detect_industry_from_keywords(company_name, domain)
        size_score = get_size_proxy_score(contact_count, bool(domain))
        origin_scores = [int(c.get('origin_score') or '0') for c in cc]
        best_origin = max(origin_scores) if origin_scores else 0
        origin_signal_score = {10: 100, 9: 90, 8: 80}.get(best_origin, 30)
        tld_score = 50
        if domain:
            d = domain.lower()
            if any(d.endswith(ext) for ext in ['.io', '.ai', '.tech', '.dev']):
                tld_score = 80
            elif d.endswith('.pk'):
                tld_score = 70
            elif any(d.endswith(ext) for ext in ['.com', '.ae', '.co']):
                tld_score = 60
            else:
                tld_score = 40
        else:
            tld_score = 20

        pre_score = (
            industry_score * 0.30 +
            size_score * 0.25 +
            role_score * 0.20 +
            origin_signal_score * 0.15 +
            tld_score * 0.10
        )

        scored.append({
            'key': key,
            'company_name': company_name,
            'domain': domain,
            'contacts': cc,
            'contact_count': contact_count,
            'pre_score': round(pre_score, 2),
            'industry_kw': industry,
            'industry_kw_score': industry_score,
            'size_proxy_score': size_score,
            'role_score': role_score,
            'best_tier': best_tier,
            'origin_signal_score': origin_signal_score,
            'best_origin': best_origin,
            'tld_score': tld_score,
        })

    scored.sort(key=lambda x: -x['pre_score'])
    print(f"  Top pre-score: {scored[0]['pre_score']} ({scored[0]['company_name']})")
    print(f"  Median pre-score: {scored[len(scored)//2]['pre_score']}")
    for i, s in enumerate(scored[:10]):
        print(f"    #{i+1} {s['pre_score']:.1f} | {s['company_name']} | {s['domain']} | {s['industry_kw']}")

    return scored, filtered, contacts


# ─── PHASE 2: SCRAPE TOP 500 ────────────────────────────────────────────────

async def fetch_website(domain: str, semaphore: asyncio.Semaphore, client) -> dict:
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
                description = desc_m.group(1).strip()[:500] if desc_m else ''
                text = strip_html(html)[:3000]
                return {'status': 'ok', 'title': title, 'description': description, 'text': text}
            else:
                return {'status': 'dead', 'title': '', 'description': '', 'text': ''}
        except Exception:
            return {'status': 'dead', 'title': '', 'description': '', 'text': ''}


async def phase2_scrape(companies_sorted: list) -> dict:
    import httpx

    # Load cache
    cache = {}
    if os.path.exists(SCRAPE_CACHE):
        try:
            with open(SCRAPE_CACHE, 'r') as f:
                cache = json.load(f)
            print(f"  Loaded scrape cache: {len(cache)} domains")
        except Exception:
            pass

    from app.core.config import settings
    proxy_password = settings.APIFY_PROXY_PASSWORD
    if not proxy_password:
        print("  WARNING: No APIFY_PROXY_PASSWORD, scraping without proxy")
        proxy_url = None
    else:
        proxy_url = f'http://auto:{proxy_password}@proxy.apify.com:8000'
        print("  Using Apify residential proxy")

    # Collect top 500 domains not in cache
    domains_to_scrape = []
    for comp in companies_sorted[:500]:
        d = comp['domain']
        if d and d not in cache and d not in domains_to_scrape:
            domains_to_scrape.append(d)
    print(f"  Need to scrape: {len(domains_to_scrape)} domains (top 500 minus cache)")

    if not domains_to_scrape:
        print("  All domains cached, skipping scrape")
        return cache

    semaphore = asyncio.Semaphore(10)
    client_kwargs = {
        'verify': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    if proxy_url:
        client_kwargs['proxy'] = proxy_url

    results = dict(cache)
    scraped = 0

    async with httpx.AsyncClient(**client_kwargs) as client:
        tasks = [(d, fetch_website(d, semaphore, client)) for d in domains_to_scrape]
        for d, task in tasks:
            result = await task
            results[d] = result
            scraped += 1
            if scraped % 50 == 0:
                print(f"    Scraped {scraped}/{len(domains_to_scrape)}...")
                # Intermediate cache save
                with open(SCRAPE_CACHE, 'w') as f:
                    json.dump(results, f, ensure_ascii=False)

    with open(SCRAPE_CACHE, 'w') as f:
        json.dump(results, f, ensure_ascii=False)

    ok = sum(1 for v in results.values() if v.get('status') == 'ok')
    thin = sum(1 for v in results.values() if v.get('status') == 'thin')
    dead = sum(1 for v in results.values() if v.get('status') == 'dead')
    print(f"  Saved scrape cache: {len(results)} domains")
    print(f"  Results: {ok} ok, {thin} thin, {dead} dead")
    return results


# ─── PHASE 3: GPT-4O-MINI ANALYSIS ──────────────────────────────────────────

async def gpt_analyze_company(company_name: str, domain: str, scraped_text: str,
                               semaphore: asyncio.Semaphore, client) -> dict:
    prompt = f"""Analyze this company website for a B2B sales tool that helps UAE companies pay Pakistani/remote contractors.

COMPANY: {company_name}
DOMAIN: {domain}
WEBSITE CONTENT:
{scraped_text[:3000]}

Respond in JSON:
{{
  "industry": "outsourcing|staffing|software|it_services|consulting|digital_agency|fintech|ecommerce|logistics|trading|construction|real_estate|professional_services|other",
  "what_they_do": "1 sentence",
  "employee_estimate": "number or range",
  "has_pakistan_operations": true/false,
  "has_offshore_teams": true/false,
  "contractor_friendly": true/false,
  "fit_score": 0-100,
  "fit_reason": "1 sentence why they might need contractor payment service"
}}"""

    async with semaphore:
        try:
            response = await client.chat.completions.create(
                model='gpt-4o-mini',
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            return {'error': str(e), 'fit_score': 0}


async def phase3_gpt_analyze(companies_sorted: list, scrape_data: dict) -> dict:
    import openai

    # Load cache
    cache = {}
    if os.path.exists(GPT_CACHE):
        try:
            with open(GPT_CACHE, 'r') as f:
                cache = json.load(f)
            print(f"  Loaded GPT cache: {len(cache)} companies")
        except Exception:
            pass

    from app.core.config import settings
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Select companies with meaningful scraped content, target 200 total
    to_analyze = []
    for comp in companies_sorted[:500]:
        d = comp['domain']
        if not d or d in cache:
            continue
        sd = scrape_data.get(d, {})
        text = f"{sd.get('title', '')} {sd.get('description', '')} {sd.get('text', '')}"
        if len(text.strip()) < 100:
            continue
        to_analyze.append((comp, text))
        if len(to_analyze) + len(cache) >= 200:
            break

    print(f"  Need to GPT-analyze: {len(to_analyze)} companies (target 200 minus {len(cache)} cached)")

    if not to_analyze:
        print("  All companies cached or insufficient content")
        return cache

    semaphore = asyncio.Semaphore(15)
    results = dict(cache)
    analyzed = 0

    tasks = [(comp['domain'], gpt_analyze_company(
        comp['company_name'], comp['domain'], text, semaphore, client
    )) for comp, text in to_analyze]

    for domain, task in tasks:
        result = await task
        results[domain] = result
        analyzed += 1
        if analyzed % 25 == 0:
            print(f"    GPT analyzed {analyzed}/{len(to_analyze)}...")
            with open(GPT_CACHE, 'w') as f:
                json.dump(results, f, ensure_ascii=False)

    with open(GPT_CACHE, 'w') as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"  Saved GPT cache: {len(results)} companies")
    errors = sum(1 for v in results.values() if 'error' in v)
    if errors:
        print(f"  GPT errors: {errors}")
    return results


# ─── PHASE 4: FINAL SCORING & OUTPUT ────────────────────────────────────────

def gpt_industry_score(industry: str) -> int:
    return INDUSTRY_SCORES.get(industry, 45)

def gpt_size_score(estimate) -> int:
    if not estimate:
        return 50
    text = str(estimate).replace(',', '').replace('~', '').replace('+', '')
    nums = re.findall(r'\d+', text)
    if not nums:
        return 50
    n = int(nums[0])
    if len(nums) >= 2:
        n = (int(nums[0]) + int(nums[1])) // 2
    if 11 <= n <= 50:
        return 100
    elif 51 <= n <= 200:
        return 90
    elif 1 <= n <= 10:
        return 60
    elif 201 <= n <= 500:
        return 50
    elif 501 <= n <= 1000:
        return 20
    else:
        return 5

def gpt_pakistan_offshore_score(gpt_data: dict) -> int:
    score = 30
    if gpt_data.get('has_pakistan_operations'):
        score = max(score, 100)
    if gpt_data.get('has_offshore_teams'):
        score = max(score, 80)
    if gpt_data.get('contractor_friendly'):
        score = max(score, 60)
    return score


def phase4_score_and_output(companies_sorted: list, scrape_data: dict, gpt_data: dict,
                             sheets, all_contacts: list, filtered_contacts: list):
    print("\n[Phase 4] Final scoring & output...")

    final_scored = []
    for comp in companies_sorted:
        domain = comp['domain']
        gpt = gpt_data.get(domain) if domain else None
        has_gpt = gpt is not None and 'error' not in gpt

        if has_gpt:
            gpt_fit = gpt.get('fit_score', 0)
            gpt_ind = gpt_industry_score(gpt.get('industry', 'other'))
            gpt_sz = gpt_size_score(gpt.get('employee_estimate'))
            gpt_pk = gpt_pakistan_offshore_score(gpt)
            role_auth = comp['role_score']
            final = (
                gpt_fit * 0.40 +
                gpt_ind * 0.20 +
                gpt_sz * 0.15 +
                gpt_pk * 0.15 +
                role_auth * 0.10
            )
            industry = gpt.get('industry', comp['industry_kw'])
            size_est = str(gpt.get('employee_estimate', ''))
            pk_ops = 'Yes' if gpt.get('has_pakistan_operations') else 'No'
            contractor_sig = 'Yes' if gpt.get('contractor_friendly') else ('Offshore' if gpt.get('has_offshore_teams') else 'No')
            web_summary = gpt.get('what_they_do', '')[:150]
            fit_reason = gpt.get('fit_reason', '')[:150]
            reasoning_parts = [
                f"GPT_fit={gpt_fit}",
                f"Ind={industry}({gpt_ind})",
                f"Size={size_est}({gpt_sz})",
                f"PKops={pk_ops}({gpt_pk})",
                f"Role=T{comp['best_tier']}({role_auth})",
            ]
            if fit_reason:
                reasoning_parts.append(f"Why: {fit_reason}")
        else:
            final = comp['pre_score']
            industry = comp['industry_kw']
            size_est = f"~{comp['contact_count']} contacts"
            pk_ops = ''
            contractor_sig = ''
            sd = scrape_data.get(domain, {}) if domain else {}
            if sd.get('status') == 'ok':
                web_summary = f"{sd.get('title', '')[:80]} | {sd.get('description', '')[:120]}"
            elif sd.get('status') == 'thin':
                web_summary = 'thin content'
            elif sd.get('status') == 'dead':
                web_summary = 'site unreachable'
            else:
                web_summary = ''
            fit_reason = ''
            reasoning_parts = [
                f"PreScore",
                f"Ind={industry}({comp['industry_kw_score']})",
                f"SizeProxy=({comp['size_proxy_score']})",
                f"Role=T{comp['best_tier']}({comp['role_score']})",
                f"Origin=({comp['origin_signal_score']})",
                f"TLD=({comp['tld_score']})",
            ]

        final_scored.append({
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
            'role_score': comp['role_score'],
            'web_summary': web_summary,
            'reasoning': ' | '.join(reasoning_parts),
        })

    # Sort: GPT-analyzed first by score, then non-GPT by score
    gpt_companies = sorted([c for c in final_scored if c['has_gpt']], key=lambda x: -x['final_score'])
    non_gpt_companies = sorted([c for c in final_scored if not c['has_gpt']], key=lambda x: -x['final_score'])
    all_companies = gpt_companies + non_gpt_companies

    print(f"  GPT-analyzed companies: {len(gpt_companies)}")
    print(f"  Pre-score-only companies: {len(non_gpt_companies)}")
    if gpt_companies:
        print(f"  Top GPT score: {gpt_companies[0]['final_score']} ({gpt_companies[0]['company_name']})")

    # Select contacts: max 3 per company, diversify roles, dedup
    selected = []
    seen_linkedin = set()
    seen_names = set()

    for comp in all_companies:
        if len(selected) >= 2000:
            break
        pool = comp['contacts']
        pool.sort(key=lambda c: (c['role_tier'], -int(c.get('origin_score') or '0')))
        picked = []
        picked_tiers = set()
        for c in pool:
            if len(picked) >= 3:
                break
            li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
            full_name = f"{c['first_name']} {c['last_name']}".lower().strip()
            if li and li in seen_linkedin:
                continue
            if full_name and full_name != ' ' and full_name in seen_names:
                continue
            tier = c['role_tier']
            if tier in picked_tiers and len(pool) > len(picked) + 1:
                others = [cc for cc in pool if cc['role_tier'] != tier
                          and (cc.get('linkedin_url') or '').lower().strip().rstrip('/') not in seen_linkedin]
                if others and len(picked) < 2:
                    continue
            picked.append(c)
            picked_tiers.add(tier)
            if li:
                seen_linkedin.add(li)
            if full_name and full_name != ' ':
                seen_names.add(full_name)

        for c in picked:
            origin_score = int(c.get('origin_score') or '0')
            origin_label = get_origin_label(origin_score)
            origin_signal = origin_label or c.get('name_match_reason', '') or c.get('search_type', '')
            selected.append({
                'rank': 0,
                'first_name': c['first_name'],
                'last_name': c['last_name'],
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
    print(f"  Selected {len(selected)} contacts")

    # Write to Google Sheet
    print("\n  Writing to Google Sheet...")
    sheets.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"'{OUTPUT_TAB}'!A1:Z3000"
    ).execute()
    print("    Cleared output tab A1:Z3000")

    header = [
        'Rank', 'First Name', 'Last Name', 'Title', 'Role Tier',
        'Company', 'Domain', 'Location', 'LinkedIn URL', 'Origin Signal',
        'Company Score', 'Industry', 'Size Estimate', 'Pakistan Ops',
        'Contractor Signal', 'Contacts at Company', 'Website Summary', 'Reasoning'
    ]
    sheet_rows = [header]
    for s in selected:
        sheet_rows.append([
            s['rank'], s['first_name'], s['last_name'], s['title'], s['role_tier'],
            s['company'], s['domain'], s['location'], s['linkedin_url'], s['origin_signal'],
            s['company_score'], s['industry'], s['size_estimate'], s['pk_ops'],
            s['contractor_signal'], s['contacts_at_company'], s['web_summary'], s['reasoning'],
        ])

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
        print(f"    Wrote rows {start_row}-{end_row}")

    # Save local JSON
    with open('/tmp/uae_pk_v5_scored.json', 'w') as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total contacts in sheet: {len(all_contacts)}")
    print(f"After filters: {len(filtered_contacts)}")
    print(f"Companies scored: {len(all_companies)}")
    print(f"  GPT-analyzed: {len(gpt_companies)}")
    print(f"  Pre-score only: {len(non_gpt_companies)}")
    print(f"Final selected: {len(selected)}")

    print("\nScore distribution (selected contacts):")
    for lo, hi in [(80, 101), (60, 80), (40, 60), (20, 40), (0, 20)]:
        cnt = sum(1 for s in selected if lo <= s['company_score'] < hi)
        print(f"  {lo}-{hi}: {cnt}")

    print("\nIndustry distribution:")
    ind_counts = Counter(s['industry'] for s in selected)
    for ind, cnt in ind_counts.most_common(15):
        print(f"  {ind}: {cnt}")

    print("\nRole tier distribution:")
    tier_counts = Counter(s['role_tier'] for s in selected)
    for tier in sorted(tier_counts):
        print(f"  {tier}: {tier_counts[tier]}")

    print("\nTop 50 companies:")
    shown = set()
    rank = 0
    for s in selected:
        if s['company'] in shown:
            continue
        shown.add(s['company'])
        rank += 1
        if rank > 50:
            break
        print(f"  #{rank} Score={s['company_score']} | {s['company']} | {s['domain']} | {s['industry']} | {s['reasoning'][:80]}")

    print(f"\nOutput tab: '{OUTPUT_TAB}'")
    print(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    return selected


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def async_main():
    start_time = time.time()
    sheets = get_sheets_service()

    # Phase 1
    companies_sorted, filtered_contacts, all_contacts = phase1_prescore(sheets)
    if not companies_sorted:
        return
    print(f"  Phase 1 done in {time.time() - start_time:.1f}s")

    # Phase 2
    t2 = time.time()
    print(f"\n[Phase 2] Scraping top 500 company websites via Apify proxy...")
    scrape_data = await phase2_scrape(companies_sorted)
    print(f"  Phase 2 done in {time.time() - t2:.1f}s")

    # Phase 3
    t3 = time.time()
    print(f"\n[Phase 3] GPT-4o-mini analysis of top 200 companies...")
    gpt_data = await phase3_gpt_analyze(companies_sorted, scrape_data)
    print(f"  Phase 3 done in {time.time() - t3:.1f}s")

    # Phase 4
    phase4_score_and_output(companies_sorted, scrape_data, gpt_data,
                            sheets, all_contacts, filtered_contacts)
    print(f"\nTotal pipeline time: {time.time() - start_time:.1f}s")


def main():
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
