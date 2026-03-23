#!/usr/bin/env python3
"""
Australia-Philippines 6-Layer Scoring Pipeline

Reads merged AU-PH contacts from Google Sheet or local JSON, runs layers 0-3 + 6 (instant),
outputs scored contacts to Google Sheet + JSON.

Layers 4-5 (website scraping + GPT) run separately on Hetzner.

Usage:
  # From Google Sheet (default tab: AU-PH Raw Merged)
  python3 score_au_ph.py

  # Specify source tab
  python3 score_au_ph.py --source-tab "AU-PH Raw Merged 0318"

  # From local JSON
  python3 score_au_ph.py --input data/au_ph_merged_0318.json

  # Dry run (no Google Sheet write)
  python3 score_au_ph.py --dry-run

  # On Hetzner
  docker exec leadgen-backend python3 /app/easystaff-global/score_au_ph.py
"""
import sys
import os
import re
import json
import argparse
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Allow import from /app when running in Docker
sys.path.insert(0, '/app')

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('score_au_ph')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
DEFAULT_SOURCE_TAB = 'AU-PH Raw Merged'

# Resolve data dir relative to this script (works both locally and in Docker)
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / 'data'

# Enterprise blacklist path — try Docker first, then local repo
BLACKLIST_CANDIDATES = [
    Path('/app/scripts/data/enterprise_blacklist.json'),
    SCRIPT_DIR / 'enterprise_blacklist.json',
    SCRIPT_DIR.parent / 'scripts' / 'data' / 'enterprise_blacklist.json',
]

ENTERPRISE_DOMAIN_THRESHOLD = 10  # Flag domains with 10+ contacts

# ═══════════════════════════════════════════════════════════════════════════
# LAYER 0 — Title & Company Regex Patterns
# ═══════════════════════════════════════════════════════════════════════════

TITLE_EXCLUDE = [
    # Government
    re.compile(r'\bgovernment\b', re.I),
    re.compile(r'\bpublic serv', re.I),
    re.compile(r'\bdepartment of\b', re.I),
    re.compile(r'\bministry\b', re.I),
    re.compile(r'\bcouncil\b', re.I),
    re.compile(r'\bcommission(er)?\b', re.I),
    re.compile(r'\bmunicipal\b', re.I),
    re.compile(r'\bfederal\b', re.I),
    re.compile(r'\bstate government\b', re.I),
    re.compile(r'\bpublic sector\b', re.I),
    re.compile(r'\bcommonwealth\b', re.I),
    # Education
    re.compile(r'\bprofessor\b', re.I),
    re.compile(r'\blecturer\b', re.I),
    re.compile(r'\bacademic\b', re.I),
    re.compile(r'\bresearch(er)?\b', re.I),
    re.compile(r'\bstudent\b', re.I),
    re.compile(r'\bgraduate\b', re.I),
    re.compile(r'\bteach(er|ing)\b', re.I),
    re.compile(r'\btutor\b', re.I),
    re.compile(r'\bpostdoc\b', re.I),
    re.compile(r'\bscholar\b', re.I),
    re.compile(r'\bphd\b', re.I),
    re.compile(r'\bdean\b', re.I),
    # Medical
    re.compile(r'\bphysician\b', re.I),
    re.compile(r'\bnurs(e|ing)\b', re.I),
    re.compile(r'\bsurgeon\b', re.I),
    re.compile(r'\bdentist\b', re.I),
    re.compile(r'\bpharmac', re.I),
    re.compile(r'\btherapist\b', re.I),
    re.compile(r'\bpatholog', re.I),
    re.compile(r'\bclinician\b', re.I),
    re.compile(r'\bFRACGP\b', re.I),
    re.compile(r'\bMBBS\b', re.I),
    re.compile(r'\bmedical officer\b', re.I),
    re.compile(r'\bmidwi(fe|very)\b', re.I),
    re.compile(r'\bregistered nurse\b', re.I),
    re.compile(r'\bRN\b'),  # Case-sensitive — avoid matching "born" etc.
    # Military / Emergency
    re.compile(r'\barmy\b', re.I),
    re.compile(r'\bnavy\b', re.I),
    re.compile(r'\bdefence\b', re.I),
    re.compile(r'\bmilitary\b', re.I),
    re.compile(r'\bair force\b', re.I),
    re.compile(r'\bfire\s*(fight|service|brigade)', re.I),
    re.compile(r'\bpolic(e|ing)\b', re.I),
    re.compile(r'\bambulance\b', re.I),
    # Anti-title (junior / non-decision-maker)
    re.compile(r'\bintern\b', re.I),
    re.compile(r'\btrainee\b', re.I),
    re.compile(r'\bassistant to\b', re.I),
    re.compile(r'\breceptionist\b', re.I),
    re.compile(r'\bdata entry\b', re.I),
    re.compile(r'\bvirtual assistant\b', re.I),
    re.compile(r'\bcashier\b', re.I),
    re.compile(r'\bdriver\b', re.I),
    re.compile(r'\bsecurity guard\b', re.I),
    re.compile(r'\bcleaner\b', re.I),
    re.compile(r'\bwarehouse\b', re.I),
    # Freelancer / self-employed
    re.compile(r'\bfreelanc', re.I),
    re.compile(r'\bself-employed\b', re.I),
    re.compile(r'\bindependent consult', re.I),
    # Trade / manual labor
    re.compile(r'\belectrician\b', re.I),
    re.compile(r'\bplumber\b', re.I),
    re.compile(r'\bcarpenter\b', re.I),
    re.compile(r'\bmechanic\b', re.I),
    re.compile(r'\bwelder\b', re.I),
    re.compile(r'\btechnician\b', re.I),
    re.compile(r'\bfitter\b', re.I),
    # Migration / social services (common for Filipino diaspora, not ICP)
    re.compile(r'\bmigration\s*(agent|consult|advis)', re.I),
    re.compile(r'\bsocial worker\b', re.I),
    re.compile(r'\bcommunity\s*(worker|officer|develop)', re.I),
    re.compile(r'\bcase manager\b', re.I),
    re.compile(r'\bsupport worker\b', re.I),
    re.compile(r'\bcare\s*(worker|giver|coordinator)\b', re.I),
    re.compile(r'\bdisability\b', re.I),
    re.compile(r'\baged care\b', re.I),
]

COMPANY_EXCLUDE = [
    # Government
    re.compile(r'\bdepartment of\b', re.I),
    re.compile(r'\bgovernment\b', re.I),
    re.compile(r'\bpublic serv', re.I),
    re.compile(r'\bcouncil\b', re.I),
    re.compile(r'\bauthority\b', re.I),
    re.compile(r'\bcommission\b', re.I),
    re.compile(r'\bministry\b', re.I),
    re.compile(r'\bfederal\b', re.I),
    re.compile(r'\bstate of\b', re.I),
    re.compile(r'\bcommonwealth\b', re.I),
    re.compile(r'\bATO\b'),  # Australian Tax Office — case-sensitive
    # Education
    re.compile(r'\buniversity\b', re.I),
    re.compile(r'\binstitute of tech', re.I),
    re.compile(r'\bTAFE\b', re.I),
    re.compile(r'\bpolytechnic\b', re.I),
    re.compile(r'\bcollege of\b', re.I),
    re.compile(r'\bschool\s+of\b', re.I),
    re.compile(r'\bacademy\b', re.I),
    # Healthcare (large public health systems)
    re.compile(r'\bhospital\b', re.I),
    re.compile(r'\bhealth service\b', re.I),
    re.compile(r'\bmedical cent(re|er)\b', re.I),
    re.compile(r'\bhealth district\b', re.I),
    re.compile(r'\bhealth network\b', re.I),
    re.compile(r'\bpathology\b', re.I),
    # Military / Emergency
    re.compile(r'\bdefence\b', re.I),
    re.compile(r'\bmilitary\b', re.I),
    re.compile(r'\bpolice\b', re.I),
    re.compile(r'\bfire (service|brigade)\b', re.I),
    # Migration services
    re.compile(r'\bmigration\b', re.I),
    re.compile(r'\bvisa\b', re.I),
    re.compile(r'\bimmigration\b', re.I),
]


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2 — Role Tier Scoring
# ═══════════════════════════════════════════════════════════════════════════

def get_role_tier(title: str) -> tuple[int, int]:
    """Return (tier_number, tier_score) for a title. Lower tier = better."""
    t = title.lower()

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
    # T8: All others
    return 8, 1


# ═══════════════════════════════════════════════════════════════════════════
# Google Sheets helpers
# ═══════════════════════════════════════════════════════════════════════════

def get_sheets_service():
    """Build Google Sheets API service using service account credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = '/app/google-credentials.json'
    if not os.path.exists(creds_path):
        # Fallback for local development
        alt = os.path.expanduser('~/google-credentials.json')
        if os.path.exists(alt):
            creds_path = alt
        else:
            raise FileNotFoundError(
                f'Google credentials not found at {creds_path} or {alt}. '
                'Use --input flag for local JSON input or --dry-run to skip Sheet write.'
            )

    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=['https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


def read_sheet_tab(sheets, tab_name: str) -> list[dict]:
    """Read all rows from a Google Sheet tab and return as list of dicts."""
    log.info(f'Reading Google Sheet tab: {tab_name}')
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A1:AZ50000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        log.error(f'Tab "{tab_name}" is empty or not found')
        return []

    headers = [h.strip() for h in rows[0]]
    col = {h: i for i, h in enumerate(headers)}
    log.info(f'  Headers: {headers}')
    log.info(f'  Rows: {len(rows) - 1}')

    def gv(row, name):
        idx = col.get(name, -1)
        if idx < 0 or idx >= len(row):
            return ''
        return (row[idx] or '').strip()

    contacts = []
    for row in rows[1:]:
        c = {
            'first_name': gv(row, 'First Name'),
            'last_name': gv(row, 'Last Name'),
            'title': gv(row, 'Title'),
            'company': gv(row, 'Company'),
            'domain': gv(row, 'Domain'),
            'location': gv(row, 'Location'),
            'linkedin_url': gv(row, 'LinkedIn URL'),
            'industry': gv(row, 'Industry'),
            'schools': gv(row, 'Schools') or gv(row, 'Schools (from Clay)'),
            'search_sources': gv(row, 'Search Sources') or gv(row, 'Search IDs'),
        }
        # Parse origin_signals — could be JSON list or comma-separated string
        raw_signals = gv(row, 'Origin Signals')
        if raw_signals:
            try:
                c['origin_signals'] = json.loads(raw_signals)
            except (json.JSONDecodeError, ValueError):
                c['origin_signals'] = [s.strip() for s in raw_signals.split(',') if s.strip()]
        else:
            c['origin_signals'] = []

        contacts.append(c)

    return contacts


def write_sheet_tab(sheets, tab_name: str, header: list[str], rows_data: list[list]) -> None:
    """Create a new tab and write rows to it (batched in 500-row chunks)."""
    all_rows = [header] + rows_data
    log.info(f'Writing {len(rows_data)} rows to tab: {tab_name}')

    # Create tab
    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{
                'addSheet': {
                    'properties': {
                        'title': tab_name,
                        'gridProperties': {
                            'rowCount': max(10000, len(all_rows) + 100),
                            'columnCount': len(header) + 5,
                        }
                    }
                }
            }]}
        ).execute()
    except Exception as e:
        log.warning(f'Tab creation: {e}')

    # Write in 500-row batches
    for i in range(0, len(all_rows), 500):
        batch = all_rows[i:i + 500]
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{i + 1}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()
        log.info(f'  Wrote rows {i + 1}-{i + len(batch)}')


# ═══════════════════════════════════════════════════════════════════════════
# Blacklist loader
# ═══════════════════════════════════════════════════════════════════════════

def load_blacklist() -> dict:
    """Load enterprise_blacklist.json from first available path."""
    for path in BLACKLIST_CANDIDATES:
        if path.exists():
            log.info(f'Loaded blacklist from: {path}')
            with open(path) as f:
                return json.load(f)
    log.warning('enterprise_blacklist.json not found — Layer 1 will be limited')
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline layers
# ═══════════════════════════════════════════════════════════════════════════

def layer0_title_company_regex(contacts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Layer 0: Remove contacts matching title/company exclusion regex patterns."""
    log.info(f'--- Layer 0: Title & Company Regex ({len(contacts)} input) ---')
    passed = []
    removed = []
    reason_counts = Counter()

    for c in contacts:
        title = c.get('title', '')
        company = c.get('company', '')
        removal_reason = None

        # Empty title — can't assess role, remove
        if not title.strip():
            removal_reason = 'empty_title'
        else:
            # Check title patterns
            for pattern in TITLE_EXCLUDE:
                if pattern.search(title):
                    removal_reason = f'title_regex:{pattern.pattern}'
                    break

        # Check company patterns (even if title passed)
        if not removal_reason and company.strip():
            for pattern in COMPANY_EXCLUDE:
                if pattern.search(company):
                    removal_reason = f'company_regex:{pattern.pattern}'
                    break

        if removal_reason:
            c['removal_reason'] = removal_reason
            c['removal_layer'] = 0
            removed.append(c)
            # Track top-level category for summary
            category = removal_reason.split(':')[0]
            reason_counts[category] += 1
        else:
            passed.append(c)

    log.info(f'  Passed: {len(passed)}  |  Removed: {len(removed)}')
    for reason, count in reason_counts.most_common(15):
        log.info(f'    {reason}: {count}')

    return passed, removed


def layer1_domain_blacklist(contacts: list[dict], blacklist: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Layer 1: Remove contacts with blacklisted domains/companies.

    Returns (passed, removed, enterprise_candidates).
    Enterprise candidates are NOT removed, just flagged for review.
    """
    log.info(f'--- Layer 1: Domain Blacklist ({len(contacts)} input) ---')

    # Extract blacklist sets
    enterprise_domains = set(d.lower() for d in blacklist.get('enterprise_domains', []))
    competitor_domains = set(d.lower() for d in blacklist.get('competitor_domains', []))
    india_outsourcing = set(d.lower() for d in blacklist.get('india_outsourcing_domains', []))
    bpo_domains = set(d.lower() for d in blacklist.get('bpo_domains', []))
    au_recruitment = set(d.lower() for d in blacklist.get('au_recruitment_domains', []))
    blocked_suffixes = blacklist.get('blocked_domain_suffixes', [])
    gov_suffixes = blacklist.get('government_domains_suffix', [])

    # Name-based patterns from blacklist
    enterprise_names = [n.lower() for n in blacklist.get('enterprise_names_contains', [])]
    government_names = [n.lower() for n in blacklist.get('government_names_contains', [])]
    recruitment_names = [n.lower() for n in blacklist.get('recruitment_names_contains', [])]
    anti_titles = [t.lower() for t in blacklist.get('anti_titles', [])]

    # Junk patterns
    junk = blacklist.get('junk_patterns', {})
    placeholder_companies = [p.lower() for p in junk.get('placeholder_companies', [])]
    fake_domains = set(d.lower() for d in junk.get('fake_domains', []))

    passed = []
    removed = []
    reason_counts = Counter()

    # Pre-count domains for enterprise candidate detection
    domain_counts = Counter()
    for c in contacts:
        d = (c.get('domain') or '').lower().strip()
        if d:
            domain_counts[d] += 1

    # Flag enterprise candidates (10+ contacts per domain)
    enterprise_candidates = []
    flagged_domains = set()
    for domain, count in domain_counts.items():
        if count >= ENTERPRISE_DOMAIN_THRESHOLD:
            flagged_domains.add(domain)
            enterprise_candidates.append({
                'domain': domain,
                'count': count,
                'sample_companies': [],
            })

    # Collect sample company names for enterprise candidates
    for c in contacts:
        d = (c.get('domain') or '').lower().strip()
        if d in flagged_domains:
            for ec in enterprise_candidates:
                if ec['domain'] == d and len(ec['sample_companies']) < 3:
                    ec['sample_companies'].append(c.get('company', ''))

    if enterprise_candidates:
        log.info(f'  Enterprise candidates (10+ contacts): {len(enterprise_candidates)} domains')
        for ec in sorted(enterprise_candidates, key=lambda x: -x['count'])[:10]:
            log.info(f'    {ec["domain"]}: {ec["count"]} contacts ({", ".join(ec["sample_companies"][:2])})')

    for c in contacts:
        d = (c.get('domain') or '').lower().strip()
        company_lower = (c.get('company') or '').lower().strip()
        removal_reason = None

        # --- Domain-based checks ---
        if d:
            # Enterprise domains (exact match)
            if d in enterprise_domains:
                removal_reason = 'enterprise_domain'
            # Competitor domains
            elif d in competitor_domains:
                removal_reason = 'competitor_domain'
            # India outsourcing
            elif d in india_outsourcing:
                removal_reason = 'india_outsourcing_domain'
            # BPO domains
            elif d in bpo_domains:
                removal_reason = 'bpo_domain'
            # AU recruitment
            elif d in au_recruitment:
                removal_reason = 'au_recruitment_domain'
            # Fake domains
            elif d in fake_domains:
                removal_reason = 'fake_domain'
            # Blocked suffixes (includes .ph, .gov.au, .edu.au, .pk, etc.)
            elif any(d.endswith(suffix) for suffix in blocked_suffixes):
                matching_suffix = next(s for s in blocked_suffixes if d.endswith(s))
                removal_reason = f'blocked_suffix:{matching_suffix}'
            # Government domain suffixes
            elif any(d.endswith(suffix) for suffix in gov_suffixes):
                matching_suffix = next(s for s in gov_suffixes if d.endswith(s))
                removal_reason = f'gov_suffix:{matching_suffix}'

        # --- Company name checks ---
        if not removal_reason and company_lower:
            # Enterprise names
            for pattern in enterprise_names:
                if pattern in company_lower:
                    removal_reason = f'enterprise_name:{pattern}'
                    break

        if not removal_reason and company_lower:
            # Government names
            for pattern in government_names:
                if pattern in company_lower:
                    removal_reason = f'government_name:{pattern}'
                    break

        if not removal_reason and company_lower:
            # Recruitment names
            for pattern in recruitment_names:
                if pattern in company_lower:
                    removal_reason = f'recruitment_name:{pattern}'
                    break

        if not removal_reason and company_lower:
            # Placeholder companies
            for pattern in placeholder_companies:
                if company_lower == pattern or company_lower.startswith(pattern):
                    removal_reason = f'placeholder_company:{pattern}'
                    break

        # --- Anti-titles from blacklist ---
        if not removal_reason:
            title_lower = (c.get('title') or '').lower()
            for at in anti_titles:
                if at in title_lower:
                    removal_reason = f'blacklist_anti_title:{at}'
                    break

        if removal_reason:
            c['removal_reason'] = removal_reason
            c['removal_layer'] = 1
            removed.append(c)
            category = removal_reason.split(':')[0]
            reason_counts[category] += 1
        else:
            passed.append(c)

    log.info(f'  Passed: {len(passed)}  |  Removed: {len(removed)}')
    for reason, count in reason_counts.most_common(15):
        log.info(f'    {reason}: {count}')

    return passed, removed, enterprise_candidates


def layer2_role_scoring(contacts: list[dict]) -> list[dict]:
    """Layer 2: Assign role tier and score to each contact. No removals."""
    log.info(f'--- Layer 2: Role Tier Scoring ({len(contacts)} input) ---')
    tier_counts = Counter()

    for c in contacts:
        tier, score = get_role_tier(c.get('title', ''))
        c['role_tier'] = tier
        c['role_score'] = score
        tier_counts[tier] += 1

    for tier in sorted(tier_counts):
        log.info(f'  T{tier}: {tier_counts[tier]}')

    return contacts


def layer3_per_company_cap(contacts: list[dict]) -> tuple[list[dict], int]:
    """Layer 3: Cap to top 3 per company, dedup by LinkedIn URL and name+company.

    Returns (capped_contacts, total_before_cap).
    """
    log.info(f'--- Layer 3: Per-Company Cap & Dedup ({len(contacts)} input) ---')

    # Group by domain (fallback: company name)
    companies = defaultdict(list)
    for c in contacts:
        d = (c.get('domain') or '').lower().strip()
        key = d if d else f"__name__{(c.get('company') or '').lower().strip()}"
        companies[key].append(c)

    log.info(f'  Unique companies: {len(companies)}')

    selected = []
    seen_li = set()
    seen_name_company = set()

    for key, cc in companies.items():
        # Sort: best role tier first, then by number of origin signals (more = better)
        cc.sort(key=lambda c: (
            c.get('role_tier', 8),
            -len(c.get('origin_signals', [])),
        ))

        picked = 0
        for c in cc:
            if picked >= 3:
                break

            # Dedup by LinkedIn URL
            li = (c.get('linkedin_url') or '').lower().strip().rstrip('/')
            if li and li in seen_li:
                continue

            # Dedup by name+company (for contacts without LinkedIn)
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".lower().strip()
            company_key = (c.get('company') or '').lower().strip()
            name_co = f"{name}||{company_key}"
            if not li and name and name != ' ' and name_co in seen_name_company:
                continue

            selected.append(c)
            picked += 1
            if li:
                seen_li.add(li)
            if name and name != ' ':
                seen_name_company.add(name_co)

    log.info(f'  After cap+dedup: {len(selected)}')

    # Distribution of per-company contact counts
    co_sizes = Counter()
    co_groups = defaultdict(int)
    for key, cc in companies.items():
        co_sizes[min(len(cc), 3)] += 1
        co_groups[key] = len(cc)
    for size in sorted(co_sizes):
        log.info(f'    Companies with {size} contact(s) kept: {co_sizes[size]}')

    return selected, len(contacts)


def layer6_final_scoring(contacts: list[dict]) -> list[dict]:
    """Layer 6: Calculate final composite score for each contact."""
    log.info(f'--- Layer 6: Final Scoring ({len(contacts)} input) ---')

    for c in contacts:
        origin_signals = c.get('origin_signals', [])
        has_university = any(
            s.startswith('university:') for s in origin_signals
        )
        has_language = any(
            s.startswith('language:') for s in origin_signals
        )

        # Origin (40%)
        if has_university and has_language:
            origin_score = 40
        elif has_university:
            origin_score = 38
        elif has_language:
            origin_score = 34
        else:
            origin_score = 0

        # Role (20%)
        role_pct = {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 6, 8: 2}
        role_score = role_pct.get(c.get('role_tier', 8), 2)

        # Survived filters (20%) — passed layers 0-3 = no red flag in this version
        filter_score = 20 if not c.get('any_red_flag') else 0

        # Company signals (20%) — basic version without website/GPT
        company_score = 0
        domain = c.get('domain') or ''
        if domain and not domain.endswith(('.ph', '.com.ph')):
            company_score += 10  # Has non-PH domain
        if '.com.au' in domain:
            company_score += 10  # AU domain = strong AU company signal

        total = origin_score + role_score + filter_score + company_score

        c['score'] = total
        c['score_breakdown'] = {
            'origin': origin_score,
            'role': role_score,
            'filter': filter_score,
            'company': company_score,
        }

    # Sort by score descending, then by role tier ascending
    contacts.sort(key=lambda c: (-c['score'], c.get('role_tier', 8)))

    # Assign ranks
    for i, c in enumerate(contacts):
        c['rank'] = i + 1

    # Score distribution
    score_ranges = Counter()
    for c in contacts:
        s = c['score']
        if s >= 80:
            score_ranges['80-100'] += 1
        elif s >= 60:
            score_ranges['60-79'] += 1
        elif s >= 40:
            score_ranges['40-59'] += 1
        elif s >= 20:
            score_ranges['20-39'] += 1
        else:
            score_ranges['0-19'] += 1

    for bucket in ['80-100', '60-79', '40-59', '20-39', '0-19']:
        log.info(f'  Score {bucket}: {score_ranges.get(bucket, 0)}')

    return contacts


# ═══════════════════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════════════════

def save_json(data: list | dict, filename: str) -> None:
    """Save data to JSON file in DATA_DIR."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    log.info(f'  Saved: {path} ({len(data) if isinstance(data, list) else "dict"})')


def main():
    parser = argparse.ArgumentParser(description='AU-PH 6-Layer Scoring Pipeline')
    parser.add_argument('--source-tab', default=DEFAULT_SOURCE_TAB,
                        help=f'Google Sheet tab to read from (default: {DEFAULT_SOURCE_TAB})')
    parser.add_argument('--input', type=str, default=None,
                        help='Local JSON file to read instead of Google Sheet')
    parser.add_argument('--dry-run', action='store_true',
                        help='Skip Google Sheet write (print results only)')
    args = parser.parse_args()

    start_time = datetime.now()
    log.info('=' * 70)
    log.info('AU-PH SCORING PIPELINE — START')
    log.info('=' * 70)

    sheets = None

    # ── Load contacts ──
    if args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = SCRIPT_DIR / input_path
        log.info(f'Reading from local JSON: {input_path}')
        with open(input_path) as f:
            contacts = json.load(f)
        # Ensure origin_signals is a list
        for c in contacts:
            if isinstance(c.get('origin_signals'), str):
                try:
                    c['origin_signals'] = json.loads(c['origin_signals'])
                except (json.JSONDecodeError, ValueError):
                    c['origin_signals'] = [s.strip() for s in c['origin_signals'].split(',') if s.strip()]
            elif not c.get('origin_signals'):
                c['origin_signals'] = []
    else:
        sheets = get_sheets_service()
        contacts = read_sheet_tab(sheets, args.source_tab)

    if not contacts:
        log.error('No contacts loaded. Exiting.')
        sys.exit(1)

    log.info(f'Total raw contacts: {len(contacts)}')

    # ── Layer 0: Title & Company Regex ──
    l0_passed, l0_removed = layer0_title_company_regex(contacts)
    save_json(l0_removed, 'au_ph_layer0_removed.json')

    # ── Layer 1: Domain Blacklist ──
    blacklist = load_blacklist()
    l1_passed, l1_removed, enterprise_candidates = layer1_domain_blacklist(l0_passed, blacklist)
    save_json(l1_removed, 'au_ph_layer1_removed.json')
    if enterprise_candidates:
        save_json(enterprise_candidates, 'au_ph_enterprise_candidates.json')

    # ── Layer 2: Role Tier Scoring ──
    l2_scored = layer2_role_scoring(l1_passed)

    # ── Layer 3: Per-Company Cap & Dedup ──
    l3_capped, l3_before = layer3_per_company_cap(l2_scored)
    save_json(l3_capped, 'au_ph_layer3_capped.json')

    # ── Layers 4-5: Website + GPT ──
    log.info('')
    log.info('--- Layers 4-5: Website Scraping + GPT Flags ---')
    log.info('  These layers need to run separately on Hetzner:')
    log.info('    Layer 4: Website validation (~200 domains/min)')
    log.info('    Layer 5: GPT-4o-mini binary flags (~$0.50 total)')
    log.info('  Scoring below uses basic company signals without website/GPT data.')
    log.info('')

    # ── Layer 6: Final Scoring ──
    final_scored = layer6_final_scoring(l3_capped)
    save_json(final_scored, 'au_ph_final_scored.json')

    # ── Write to Google Sheet ──
    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f'AU-PH Scored {ts}'

    header = [
        'Rank', 'First Name', 'Last Name', 'Title', 'Role Tier',
        'Company', 'Domain', 'Location', 'LinkedIn URL',
        'Origin Signals', 'Score', 'Schools', 'Search Sources',
    ]

    sheet_rows = []
    for c in final_scored:
        signals_str = ', '.join(c.get('origin_signals', []))
        sheet_rows.append([
            c.get('rank', ''),
            c.get('first_name', ''),
            c.get('last_name', ''),
            c.get('title', ''),
            f"T{c.get('role_tier', 8)}",
            c.get('company', ''),
            c.get('domain', ''),
            c.get('location', ''),
            c.get('linkedin_url', ''),
            signals_str,
            c.get('score', 0),
            c.get('schools', ''),
            c.get('search_sources', ''),
        ])

    if not args.dry_run:
        if not sheets:
            sheets = get_sheets_service()
        write_sheet_tab(sheets, tab_name, header, sheet_rows)
    else:
        log.info(f'  DRY RUN — skipping Google Sheet write (would create tab: {tab_name})')

    # ── Pipeline Summary ──
    elapsed = (datetime.now() - start_time).total_seconds()

    # Top contacts preview
    log.info('')
    log.info('=' * 70)
    log.info('TOP 20 CONTACTS')
    log.info('=' * 70)
    for c in final_scored[:20]:
        signals_short = ', '.join(c.get('origin_signals', []))[:40]
        log.info(
            f"  #{c['rank']:>4}  {c['score']:>3}  T{c['role_tier']}  "
            f"{c.get('first_name', '')[:10]:10} {c.get('last_name', '')[:12]:12}  "
            f"{c.get('title', '')[:30]:30}  {c.get('company', '')[:25]:25}  "
            f"{signals_short}"
        )

    # Role tier distribution
    tier_counts = Counter(c.get('role_tier', 8) for c in final_scored)
    # Location distribution
    loc_counts = Counter((c.get('location') or 'Unknown')[:40] for c in final_scored)
    # Domain suffix distribution
    suffix_counts = Counter()
    for c in final_scored:
        d = c.get('domain', '')
        if '.com.au' in d:
            suffix_counts['.com.au'] += 1
        elif '.au' in d:
            suffix_counts['.au (other)'] += 1
        elif d:
            suffix_counts['other'] += 1
        else:
            suffix_counts['no domain'] += 1

    log.info('')
    log.info('=' * 70)
    log.info('PIPELINE SUMMARY')
    log.info('=' * 70)
    log.info(f'  Raw input:           {len(contacts):>6}')
    log.info(f'  Layer 0 removed:     {len(l0_removed):>6}  (title & company regex)')
    log.info(f'  Layer 0 passed:      {len(l0_passed):>6}')
    log.info(f'  Layer 1 removed:     {len(l1_removed):>6}  (domain blacklist)')
    log.info(f'  Layer 1 passed:      {len(l1_passed):>6}')
    log.info(f'  Layer 2 scored:      {len(l2_scored):>6}  (role tiers assigned)')
    log.info(f'  Layer 3 capped:      {len(l3_capped):>6}  (top 3/company + dedup)')
    log.info(f'  Layer 6 final:       {len(final_scored):>6}  (scored & ranked)')
    log.info(f'')
    log.info(f'  Role distribution:')
    for tier in sorted(tier_counts):
        log.info(f'    T{tier}: {tier_counts[tier]:>5}')
    log.info(f'')
    log.info(f'  Location (top 5):')
    for loc, cnt in loc_counts.most_common(5):
        log.info(f'    {cnt:>5}  {loc}')
    log.info(f'')
    log.info(f'  Domain suffixes:')
    for suffix, cnt in suffix_counts.most_common():
        log.info(f'    {cnt:>5}  {suffix}')
    log.info(f'')
    if enterprise_candidates:
        log.info(f'  Enterprise candidates (10+ contacts): {len(enterprise_candidates)} domains')
        log.info(f'    Saved to: data/au_ph_enterprise_candidates.json (review manually)')
    log.info(f'')
    if not args.dry_run:
        log.info(f'  Output tab:          {tab_name}')
    log.info(f'  Output JSON:         data/au_ph_final_scored.json')
    log.info(f'  Elapsed:             {elapsed:.1f}s')
    log.info('=' * 70)


if __name__ == '__main__':
    main()
