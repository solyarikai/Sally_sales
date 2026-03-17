#!/usr/bin/env python3
"""
AU-PH Algorithmic Scoring v2 — No GPT, pure signals.

Scoring layers:
  1. HARD REJECT (score=0, removed):
     - No domain
     - Truncated last name (single letter + period: "Bob S.")
     - Title regex: government, education, medical, military, trades, junior, care worker
     - Company regex: government, university, hospital, military, recruitment
     - Blacklisted domain (enterprise, competitor, India outsourcing, BPO)
     - Blocked domain suffix (.gov.au, .edu.au, .ph, etc.)
     - Location NOT in Australia

  2. SCORING (0-100):
     a. Domain quality (0-25):
        - .com.au = 25 (Australian company)
        - .au (other) = 20
        - .com/.io/.co/.net = 15
        - .com.ph/.ph = 5 (Philippine company, probably not AU-based)
        - other = 10
     b. Title/role tier (0-25):
        - T1 CFO/Finance = 25
        - T2 COO/Ops = 22
        - T3 CHRO/HR/People = 20
        - T4 CEO/Founder/MD = 18
        - T5 CTO/Engineering = 15
        - T6 Director/Head/VP = 12
        - T7 Manager/Lead = 8
        - T8 Other = 3
     c. Search signal strength (0-25):
        - university_people_first (PH uni) + language = 25
        - university_people_first (PH uni) = 23
        - extended_university (AU uni) = 22
        - extended_university (PH uni) = 20
        - language only = 12 (weakest — many false positives)
     d. Company size signal (0-15):
        - company_size field populated = +5
        - industry field populated = +5
        - Has phone = +5
     e. Name penalty (0 to -10):
        - Truncated name: -10
        - Very short last name (1-2 chars): -5

  3. Per-company cap: max 3 contacts per domain
  4. Dedup: by LinkedIn URL

Usage:
  # Score first 100 (test)
  docker exec leadgen-backend python3 /app/easystaff-global/score_au_ph_v2.py --limit 100

  # Score all
  docker exec leadgen-backend python3 /app/easystaff-global/score_au_ph_v2.py

  # Dry run (no sheet write)
  docker exec leadgen-backend python3 /app/easystaff-global/score_au_ph_v2.py --limit 100 --dry-run
"""
import sys, os, re, json, argparse, logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/app')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger('score_v2')

# ─── Sheet config ────────────────────────────────────────────────────────────
SOURCE_SHEET = '1D__hmuskt6AsCakhZaRS8zaQy2cYCldHii3_VsyoiEY'
SOURCE_TAB = 'AU-Philippines'
OUTPUT_SHEET = SOURCE_SHEET  # write scored tab to same sheet

# ─── Hard reject: title patterns ─────────────────────────────────────────────
TITLE_REJECT = [
    # Government
    r'\bgovernment\b', r'\bpublic serv', r'\bdepartment of\b', r'\bministry\b',
    r'\bcouncil\b', r'\bcommission(er)?\b', r'\bmunicipal\b', r'\bfederal\b',
    r'\bcommonwealth\b', r'\bpublic sector\b',
    # Education
    r'\bprofessor\b', r'\blecturer\b', r'\bacademic\b', r'\bresearch(er)?\b',
    r'\bstudent\b', r'\bgraduate\b', r'\bteach(er|ing)\b', r'\btutor\b',
    r'\bpostdoc\b', r'\bscholar\b', r'\bphd\b', r'\bdean\b',
    # Medical / wellness
    r'\bphysician\b', r'\bnurs(e|ing)\b', r'\bsurgeon\b', r'\bdentist\b',
    r'\bpharmac', r'\btherapist\b', r'\bpatholog', r'\bclinician\b',
    r'\bFRACGP\b', r'\bMBBS\b', r'\bmedical officer\b', r'\bmidwi(fe|very)\b',
    r'\bregistered nurse\b', r'\bRN\b', r'\bdoctor\b',
    r'\bwellness\b', r'\bchiropr',
    # Military / Emergency
    r'\barmy\b', r'\bnavy\b', r'\bdefence\b', r'\bmilitary\b', r'\bair force\b',
    r'\bfire\s*(fight|service|brigade)', r'\bpolic(e|ing)\b', r'\bambulance\b',
    # Junior / non-decision-maker
    r'\bintern\b', r'\btrainee\b', r'\bassistant to\b', r'\breceptionist\b',
    r'\bdata entry\b', r'\bvirtual assistant\b', r'\bcashier\b', r'\bdriver\b',
    r'\bsecurity guard\b', r'\bcleaner\b', r'\bwarehouse\b',
    # Freelancer / self-employed
    r'\bfreelanc', r'\bself-employed\b', r'\bindependent consult',
    # Trade / manual
    r'\belectrician\b', r'\bplumber\b', r'\bcarpenter\b', r'\bmechanic\b',
    r'\bwelder\b', r'\btechnician\b', r'\bfitter\b',
    # Social / care
    r'\bmigration\s*(agent|consult|advis)', r'\bsocial worker\b',
    r'\bcommunity\s*(worker|officer|develop)', r'\bcase manager\b',
    r'\bsupport worker\b', r'\bcare\s*(worker|giver|coordinator)\b',
    r'\bdisability\b', r'\baged care\b',
    # Executive assistant (not decision maker)
    r'\bexecutive assistant\b',
]
TITLE_REJECT_RE = [re.compile(p, re.I) for p in TITLE_REJECT]

# ─── Hard reject: company patterns ───────────────────────────────────────────
COMPANY_REJECT = [
    r'\bdepartment of\b', r'\bgovernment\b', r'\bpublic serv', r'\bcouncil\b',
    r'\bauthority\b', r'\bcommission\b', r'\bministry\b', r'\bfederal\b',
    r'\bstate of\b', r'\bcommonwealth\b',
    r'\buniversity\b', r'\binstitute of tech', r'\bTAFE\b', r'\bpolytechnic\b',
    r'\bcollege of\b', r'\bschool\s+of\b', r'\bacademy\b',
    r'\bhospital\b', r'\bhealth service\b', r'\bmedical cent(re|er)\b',
    r'\bhealth district\b', r'\bhealth network\b', r'\bpathology\b',
    r'\bwellness\s+cent', r'\bhealthcare\b',
    r'\bdefence\b', r'\bmilitary\b', r'\bpolice\b', r'\bfire (service|brigade)\b',
    r'\bmetro\b',  # Government infrastructure (Sydney Metro, etc.)
    r'\bmigration\b', r'\bvisa\b', r'\bimmigration\b',
    r'\brecruitment\b', r'\bstaffing\b', r'\brecruiter\b', r'\btalent acqui',
    r'\btalent\s+formula\b',
    r'\bschool\b', r'\bgrammar\b',  # Schools
    r'\bcrc\b',  # Cooperative research centres
]
COMPANY_REJECT_RE = [re.compile(p, re.I) for p in COMPANY_REJECT]

# ─── AU location keywords ────────────────────────────────────────────────────
AU_LOCATIONS = [
    'australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide',
    'canberra', 'gold coast', 'hobart', 'darwin', 'new south wales',
    'victoria', 'queensland', 'western australia', 'south australia',
    'tasmania', 'northern territory', 'act,',
]

# ─── Role tier scoring ───────────────────────────────────────────────────────
def role_tier(title: str) -> tuple[int, int]:
    t = title.lower()
    if any(k in t for k in ['cfo', 'chief financial', 'vp finance', 'head of finance',
                             'finance director', 'payroll', 'finance manager', 'controller']):
        return 1, 25
    if any(k in t for k in ['coo', 'chief operating', 'vp operations', 'head of operations',
                             'operations director', 'operations manager']):
        return 2, 22
    if any(k in t for k in ['chro', 'chief hr', 'chief people', 'vp hr', 'head of hr',
                             'head of people', 'hr director', 'talent', 'human resources director']):
        return 3, 20
    if any(k in t for k in ['ceo', 'founder', 'co-founder', 'cofounder', 'managing director',
                             'general manager', 'owner', 'president', 'partner', 'principal']):
        return 4, 18
    if any(k in t for k in ['cto', 'vp engineering', 'head of technology', 'head of engineering',
                             'engineering director', 'tech lead', 'it director']):
        return 5, 15
    if any(k in t for k in ['director', 'head of', 'vp ', 'vice president']):
        return 6, 12
    if any(k in t for k in ['manager', 'lead', 'senior']):
        return 7, 8
    return 8, 3


def domain_score(domain: str) -> int:
    if not domain:
        return 0
    d = domain.lower()
    if d.endswith('.com.au'):
        return 25
    if d.endswith('.au'):
        return 20
    if d.endswith('.com.ph') or d.endswith('.ph'):
        return 5
    if any(d.endswith(s) for s in ['.com', '.io', '.co', '.net', '.org', '.app', '.dev']):
        return 15
    return 10


def search_signal_score(search_type: str, search_batch: str) -> int:
    if search_type == 'university_people_first':
        return 23
    if search_type == 'extended_university':
        if 'au_' in search_batch:
            return 22  # AU university = strong AU signal
        return 20
    if search_type == 'language_city_split':
        return 13
    if search_type == 'language':
        return 12  # weakest — many false positives
    if search_type == 'surname':
        return 15
    return 10


CREDENTIAL_SUFFIXES = {
    'cpeng', 'gaicd', 'faicd', 'maicd', 'cpa', 'cfa', 'mba', 'phd',
    'fracs', 'fracp', 'frcpa', 'fracgp', 'mbbs', 'rn', 'pmp', 'mrics',
    'mba', 'llb', 'llm', 'bsc', 'msc', 'dba', 'cma', 'cia', 'cisa',
    'fcpa', 'fgia', 'ca', 'fca',
}

# Name looks like a domain or placeholder
JUNK_NAME_PATTERNS = [
    re.compile(r'\b\w+\.(com|au|org|net|io)\b', re.I),  # domain in name
    re.compile(r'^dr\s+', re.I),  # Dr prefix (medical/academic)
]

def is_truncated_name(last_name: str) -> bool:
    """Detect truncated names like 'S.', 'C.', 'O.' and credential suffixes as names."""
    ln = last_name.strip()
    if not ln:
        return True
    if len(ln) <= 2 and ln.endswith('.'):
        return True
    if len(ln) == 1:
        return True
    # Credential suffix used as last name
    if ln.lower().replace('.', '').replace(',', '') in CREDENTIAL_SUFFIXES:
        return True
    return False


def data_completeness_score(contact: dict) -> int:
    """Score based on available data fields."""
    score = 0
    if contact.get('company_size'):
        score += 5
    if contact.get('industry'):
        score += 5
    if contact.get('phone'):
        score += 5
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Limit rows to score (0=all)')
    parser.add_argument('--dry-run', action='store_true', help='Skip sheet write')
    parser.add_argument('--sheet-id', default=SOURCE_SHEET, help='Source sheet ID')
    parser.add_argument('--from-raw', action='store_true', help='Load from raw JSON files instead of sheet')
    args = parser.parse_args()

    from app.services.diaspora_service import _get_sheets_service
    sheets_svc, drive_svc = _get_sheets_service()

    # ── Load contacts ──
    if args.from_raw:
        # Load from raw JSON files — gets ALL contacts, not just sheet subset
        import csv as csv_mod
        from pathlib import Path as P
        raw_dir = P("/scripts/data/raw_contacts")
        files = sorted(raw_dir.glob("australia-philippines_*.json"))
        log.info(f'Loading from {len(files)} raw JSON files...')
        # AU university files — these have NO Filipino signal, must be excluded
        AU_UNI_FILE_PATTERNS = ['ph_uni_au_go8', 'ph_uni_au_tech', 'ph_uni_au_regional']

        raw_contacts = []
        seen_li = set()
        skipped_au_uni = 0
        for f in files:
            # Skip AU university files entirely — they return all alumni, not just Filipinos
            fname = f.name
            is_au_uni = any(p in fname for p in AU_UNI_FILE_PATTERNS)
            if is_au_uni:
                try:
                    skipped_au_uni += len(json.load(open(f)))
                except:
                    pass
                continue

            # Tag source from filename
            if 'language' in fname:
                src = 'language'
            elif 'university' in fname or 'extended_university' in fname:
                src = 'ph_university'
            elif 'surname' in fname:
                src = 'surname'
            elif 'industry' in fname:
                src = 'industry'
            elif 'title_split' in fname:
                src = 'title_split'
            else:
                src = 'other'

            try:
                data = json.load(open(f))
                for c in data:
                    li = (c.get("linkedin_url") or "").lower().rstrip("/")
                    if li and li in seen_li:
                        continue
                    if li:
                        seen_li.add(li)
                    c['_source'] = src
                    raw_contacts.append(c)
            except:
                pass
        log.info(f'Skipped {skipped_au_uni} contacts from AU university files (no Filipino signal)')
        log.info(f'Loaded {len(raw_contacts)} unique contacts from raw JSONs')

        # Map raw JSON fields to sheet column names
        FIELD_MAP = {
            'Name': lambda c: c.get('name', ''),
            'First Name': lambda c: c.get('first_name', ''),
            'Last Name': lambda c: c.get('last_name', ''),
            'Title': lambda c: c.get('title', ''),
            'Company': lambda c: c.get('company', ''),
            'Domain': lambda c: c.get('company_domain', '') or c.get('domain', ''),
            'Location': lambda c: c.get('location', ''),
            'LinkedIn URL': lambda c: c.get('linkedin_url', ''),
            'Phone': lambda c: c.get('phone', ''),
            'Industry': lambda c: c.get('industry', ''),
            'Company Size': lambda c: c.get('company_size', ''),
            'Schools (from Clay)': lambda c: c.get('schools', ''),
            'Search Type': lambda c: c.get('_source', c.get('_search_type', '')),
            'Search Batch': lambda c: c.get('_search_batch', ''),
        }
        headers_list = list(FIELD_MAP.keys())
        col = {h: i for i, h in enumerate(headers_list)}
        rows = [headers_list]
        for c in raw_contacts:
            rows.append([str(fn(c) or '') for fn in FIELD_MAP.values()])
        if args.limit:
            rows = rows[:args.limit + 1]
        log.info(f'Rows: {len(rows) - 1}')

        def gv(row, name):
            idx = col.get(name, -1)
            return (row[idx] if idx >= 0 and idx < len(row) else '').strip()
    else:
        log.info(f'Reading from sheet: {args.sheet_id} tab: {SOURCE_TAB}')
        limit_range = f"!A1:W{args.limit + 1}" if args.limit else "!A1:W30000"
        data = sheets_svc.spreadsheets().values().get(
            spreadsheetId=args.sheet_id,
            range=f"'{SOURCE_TAB}'{limit_range}",
        ).execute()
        rows = data.get('values', [])
        if not rows:
            log.error('No data'); return
        headers = rows[0]
        col = {h.strip(): i for i, h in enumerate(headers)}
        log.info(f'Headers: {list(col.keys())}')
        log.info(f'Rows: {len(rows) - 1}')

        def gv(row, name):
            idx = col.get(name, -1)
            return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    # ── Load blacklist ──
    bl_paths = ['/app/scripts/data/enterprise_blacklist.json',
                '/app/easystaff-global/enterprise_blacklist.json']
    bl = {}
    for p in bl_paths:
        if os.path.exists(p):
            bl = json.load(open(p))
            log.info(f'Blacklist loaded: {p}')
            break

    ent_domains = set(d.lower() for d in bl.get('enterprise_domains', []))
    comp_domains = set(d.lower() for d in bl.get('competitor_domains', []))
    india_domains = set(d.lower() for d in bl.get('india_outsourcing_domains', []))
    bpo_domains = set(d.lower() for d in bl.get('bpo_domains', []))
    blocked_suffixes = bl.get('blocked_domain_suffixes', [])
    gov_suffixes = bl.get('government_domains_suffix', [])
    fake_domains = set(d.lower() for d in bl.get('junk_patterns', {}).get('fake_domains', []))
    ent_names = [n.lower() for n in bl.get('enterprise_names_contains', [])]
    gov_names = [n.lower() for n in bl.get('government_names_contains', [])]
    rec_names = [n.lower() for n in bl.get('recruitment_names_contains', [])]

    # ── Score all contacts ──
    scored = []
    rejected = []
    reject_reasons = Counter()

    for row in rows[1:]:
        c = {
            'name': gv(row, 'Name'),
            'first_name': gv(row, 'First Name'),
            'last_name': gv(row, 'Last Name'),
            'title': gv(row, 'Title'),
            'company': gv(row, 'Company'),
            'domain': gv(row, 'Domain'),
            'location': gv(row, 'Location'),
            'linkedin_url': gv(row, 'LinkedIn URL'),
            'phone': gv(row, 'Phone'),
            'industry': gv(row, 'Industry'),
            'company_size': gv(row, 'Company Size'),
            'schools': gv(row, 'Schools (from Clay)'),
            'search_type': gv(row, 'Search Type'),
            'search_batch': gv(row, 'Search Batch'),
        }

        domain = c['domain'].lower()
        company_lower = c['company'].lower()
        title = c['title']
        location = c['location'].lower()
        last_name = c['last_name']

        # ── HARD REJECTS ──
        reject = None

        # 1. No domain
        if not domain:
            reject = 'no_domain'

        # 2. Truncated name
        if not reject and is_truncated_name(last_name):
            reject = 'truncated_name'

        # 3. Not in Australia
        if not reject and location and not any(kw in location for kw in AU_LOCATIONS):
            reject = 'not_in_australia'

        # 4. Title regex
        if not reject:
            for pat in TITLE_REJECT_RE:
                if pat.search(title):
                    reject = f'title:{pat.pattern}'
                    break

        # 5. Company regex
        if not reject:
            for pat in COMPANY_REJECT_RE:
                if pat.search(c['company']):
                    reject = f'company:{pat.pattern}'
                    break

        # 6. Bad domains: Philippine, edu, gov
        if not reject and (domain.endswith('.ph') or domain.endswith('.com.ph')):
            reject = 'ph_domain'
        if not reject and (domain.endswith('.edu.au') or domain.endswith('.edu')):
            reject = 'edu_domain'
        if not reject and (domain.endswith('.gov.au') or domain.endswith('.gov')):
            reject = 'gov_domain'

        # 6b. Junk name (domain as name, Dr prefix)
        if not reject:
            full_name = c.get('name', '') or (c.get('first_name', '') + ' ' + c.get('last_name', ''))
            for pat in JUNK_NAME_PATTERNS:
                if pat.search(full_name):
                    reject = 'junk_name'
                    break

        # 7. Blacklisted domain
        if not reject and domain:
            if domain in ent_domains:
                reject = 'bl:enterprise'
            elif domain in comp_domains:
                reject = 'bl:competitor'
            elif domain in india_domains:
                reject = 'bl:india_outsource'
            elif domain in bpo_domains:
                reject = 'bl:bpo'
            elif domain in fake_domains:
                reject = 'bl:fake_domain'
            elif any(domain.endswith(s) for s in blocked_suffixes):
                reject = 'bl:blocked_suffix'
            elif any(domain.endswith(s) for s in gov_suffixes):
                reject = 'bl:gov_suffix'

        # 8. Blacklisted company name
        if not reject and company_lower:
            for n in ent_names:
                if n in company_lower:
                    reject = f'bl:ent_name:{n}'
                    break
        if not reject and company_lower:
            for n in gov_names:
                if n in company_lower:
                    reject = f'bl:gov_name:{n}'
                    break
        if not reject and company_lower:
            for n in rec_names:
                if n in company_lower:
                    reject = f'bl:rec_name:{n}'
                    break

        # 9. Empty title
        if not reject and not title.strip():
            reject = 'empty_title'

        if reject:
            c['reject_reason'] = reject
            rejected.append(c)
            reject_reasons[reject.split(':')[0] if ':' in reject else reject] += 1
            continue

        # ── SCORING ──
        tier, tier_score = role_tier(title)
        d_score = domain_score(domain)
        signal_score = search_signal_score(c['search_type'], c['search_batch'])
        completeness = data_completeness_score(c)

        # Name penalty
        name_penalty = 0
        if len(last_name) <= 2:
            name_penalty = -5

        total = tier_score + d_score + signal_score + completeness + name_penalty
        total = max(0, min(100, total))

        c['score'] = total
        c['role_tier'] = tier
        c['score_detail'] = f"role={tier_score} dom={d_score} signal={signal_score} data={completeness} name={name_penalty}"
        scored.append(c)

    # ── Dedup by LinkedIn URL ──
    seen_li = set()
    deduped = []
    dupes = 0
    for c in scored:
        li = c['linkedin_url'].lower().rstrip('/')
        if li and li in seen_li:
            dupes += 1
            continue
        if li:
            seen_li.add(li)
        deduped.append(c)

    # ── Per-company cap (3) ──
    companies = defaultdict(list)
    for c in deduped:
        key = c['domain'].lower() or c['company'].lower()
        companies[key].append(c)

    final = []
    for key, cc in companies.items():
        cc.sort(key=lambda x: (-x['score'], x['role_tier']))
        final.extend(cc[:3])

    # Sort by score desc
    final.sort(key=lambda x: (-x['score'], x['role_tier']))
    for i, c in enumerate(final):
        c['rank'] = i + 1

    # ── Summary ──
    log.info(f'\n{"="*60}')
    log.info(f'SCORING SUMMARY')
    log.info(f'{"="*60}')
    log.info(f'Raw input:        {len(rows)-1:>6}')
    log.info(f'Hard rejected:    {len(rejected):>6}')
    for reason, cnt in reject_reasons.most_common(15):
        log.info(f'  {reason:25} {cnt:>5}')
    log.info(f'Scored:           {len(scored):>6}')
    log.info(f'Dedup removed:    {dupes:>6}')
    log.info(f'After dedup:      {len(deduped):>6}')
    log.info(f'After 3/co cap:   {len(final):>6}')

    # Score distribution
    buckets = Counter()
    for c in final:
        s = c['score']
        if s >= 80: buckets['80-100'] += 1
        elif s >= 60: buckets['60-79'] += 1
        elif s >= 40: buckets['40-59'] += 1
        elif s >= 20: buckets['20-39'] += 1
        else: buckets['0-19'] += 1
    log.info(f'\nScore distribution:')
    for b in ['80-100', '60-79', '40-59', '20-39', '0-19']:
        log.info(f'  {b}: {buckets.get(b, 0):>5}')

    # Role tier distribution
    tier_counts = Counter(c['role_tier'] for c in final)
    log.info(f'\nRole tiers:')
    for t in sorted(tier_counts):
        log.info(f'  T{t}: {tier_counts[t]:>5}')

    # Search type distribution
    type_counts = Counter(c['search_type'] for c in final)
    log.info(f'\nSearch types:')
    for st, cnt in type_counts.most_common():
        log.info(f'  {st:30} {cnt:>5}')

    # Top 20 preview
    log.info(f'\n{"="*60}')
    log.info(f'TOP 20')
    log.info(f'{"="*60}')
    for c in final[:20]:
        log.info(f"  #{c['rank']:>3} {c['score']:>3} T{c['role_tier']} {c['first_name'][:10]:10} {c['last_name'][:12]:12} {c['title'][:30]:30} {c['company'][:20]:20} {c['domain'][:20]}")

    # Bottom 20 preview
    log.info(f'\nBOTTOM 20')
    for c in final[-20:]:
        log.info(f"  #{c['rank']:>3} {c['score']:>3} T{c['role_tier']} {c['first_name'][:10]:10} {c['last_name'][:12]:12} {c['title'][:30]:30} {c['company'][:20]:20} {c['domain'][:20]}")

    # ── Write to sheet ──
    if not args.dry_run:
        ts = datetime.now().strftime('%m%d_%H%M')
        tab_name = f'AU-PH Scored v2 {ts}'
        header = [
            'Rank', 'Score', 'Score Detail', 'Role Tier',
            'First Name', 'Last Name', 'Title',
            'Company', 'Domain', 'Location', 'LinkedIn URL',
            'Phone', 'Industry', 'Company Size', 'Schools',
            'Search Type', 'Search Batch',
        ]
        sheet_rows = [header]
        for c in final:
            sheet_rows.append([
                c['rank'], c['score'], c['score_detail'], f"T{c['role_tier']}",
                c['first_name'], c['last_name'], c['title'],
                c['company'], c['domain'], c['location'], c['linkedin_url'],
                c.get('phone', ''), c.get('industry', ''), c.get('company_size', ''),
                c.get('schools', ''), c['search_type'], c['search_batch'],
            ])

        log.info(f'\nWriting {len(final)} rows to tab: {tab_name}')
        try:
            sheets_svc.spreadsheets().batchUpdate(
                spreadsheetId=args.sheet_id,
                body={'requests': [{'addSheet': {'properties': {
                    'title': tab_name,
                    'gridProperties': {'rowCount': max(len(final) + 100, 10000), 'columnCount': 20},
                }}}]}
            ).execute()
        except Exception as e:
            log.warning(f'Tab create: {e}')

        for i in range(0, len(sheet_rows), 500):
            batch = sheet_rows[i:i+500]
            sheets_svc.spreadsheets().values().update(
                spreadsheetId=args.sheet_id,
                range=f"'{tab_name}'!A{i+1}",
                valueInputOption='RAW',
                body={'values': batch}
            ).execute()
        log.info(f'Done: https://docs.google.com/spreadsheets/d/{args.sheet_id}')

    # Save scored to CSV (always — don't depend on Sheets)
    import csv as csv_mod
    csv_path = '/tmp/au_ph_scored.csv'
    with open(csv_path, 'w', newline='') as f:
        w = csv_mod.writer(f)
        w.writerow(['Rank', 'Score', 'Score Detail', 'Role Tier',
                     'First Name', 'Last Name', 'Title',
                     'Company', 'Domain', 'Location', 'LinkedIn URL',
                     'Phone', 'Industry', 'Company Size', 'Schools',
                     'Search Type', 'Search Batch'])
        for c in final:
            w.writerow([
                c['rank'], c['score'], c['score_detail'], f"T{c['role_tier']}",
                c['first_name'], c['last_name'], c['title'],
                c['company'], c['domain'], c['location'], c['linkedin_url'],
                c.get('phone', ''), c.get('industry', ''), c.get('company_size', ''),
                c.get('schools', ''), c['search_type'], c['search_batch'],
            ])
    log.info(f'CSV scored: {csv_path} ({len(final)} rows)')

    # Save rejected to JSON
    json.dump(
        [{'name': c['name'], 'title': c['title'], 'company': c['company'],
          'domain': c['domain'], 'reason': c['reject_reason']}
         for c in rejected[:200]],
        open('/tmp/au_ph_rejected_sample.json', 'w'), indent=2, ensure_ascii=False
    )
    log.info(f'Rejected sample: /tmp/au_ph_rejected_sample.json')


if __name__ == '__main__':
    main()
