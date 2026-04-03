import os
os.environ["PYTHONUNBUFFERED"] = "1"

"""
UAE-Pakistan Priority Scoring v2 — Complete Rebuild.

Core thesis: Pakistani-origin C-levels at UAE companies = companies with Pakistan contractor ties.
More Pakistani seniors at a company → stronger Pakistan connection → more contractors → bigger deal.

Runs inside leadgen-backend container.
"""

import re
import json
import sys
import time
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials
import httpx

SHEET_ID = "1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU"
SOURCE_TAB = "UAE-Pakistan - New Only"
TARGET_TAB = "UAE-Pakistan Priority 2000"
CREDS_PATH = "/app/google-credentials.json"
IMPERSONATE = "services@getsally.io"

TARGET_COUNT = 2000
MAX_PER_COMPANY = 3
HIGH_COMPANY_THRESHOLD = 80  # Only pick 3rd contact if company score > this

# ============================================================
# STEP 1: Pakistani Origin Detection
# ============================================================

PAKISTANI_UNIVERSITIES = [
    "lums", "lahore university of management",
    "iba", "institute of business administration",
    "nust", "national university of sciences and technology",
    "giki", "gik institute", "ghulam ishaq khan",
    "uet", "university of engineering and technology",
    "ned university", "ned engineering",
    "fast", "fast-nuces", "nuces", "national university of computer",
    "comsats",
    "aga khan university",
    "bahria university",
    "szabist",
    "university of karachi",
    "university of punjab", "university of the punjab",
    "quaid-i-azam", "quaid-e-azam",
    "university of peshawar",
    "habib university",
    "forman christian college",
    "government college university",
    "lahore school of economics",
    "pieas",
    "air university",
    "ist ", "institute of space technology",
    "university of central punjab",
    "beaconhouse national",
    "kinnaird college",
    "riphah international",
    "international islamic university",
    "sukkur iba",
    "national defence university pakistan",
    "university of management and technology", "umt",
    "university of faisalabad",
]

PAKISTAN_CITIES = [
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
    "peshawar", "multan", "quetta", "sialkot", "gujranwala",
    "hyderabad pakistan",  # avoid India confusion
]

PAKISTAN_LOCATION_KEYWORDS = ["pakistan"]

# Common Pakistani first names (lowercase)
PK_FIRST_NAMES = {
    "muhammad", "ahmed", "ali", "hassan", "hussain", "usman", "bilal",
    "imran", "asad", "faisal", "kashif", "zubair", "shahid", "tariq",
    "waqas", "adeel", "amir", "syed", "rizwan", "nabeel", "sajid",
    "junaid", "hamza", "farhan", "kamran", "salman", "aamir", "arsalan",
    "shoaib", "danish", "asif", "atif", "irfan", "nadeem", "naveed",
    "raza", "saad", "tahir", "waseem", "zain", "talha", "omar", "umar",
    "owais", "qasim", "rehan", "usama", "waqar", "yasir", "zahid",
    "zeeshan", "mohsin", "babar", "jawad", "fahad", "naeem", "anwer",
    "anwar", "arshad", "azhar", "ejaz", "ghulam", "habib", "hamid",
    "haris", "ijaz", "ismail", "khalid", "maqsood", "masood", "mazhar",
    "mubashir", "murtaza", "mustafa", "nasir", "nouman", "obaid",
    "omer", "pervez", "qaiser", "rafiq", "rashid", "riaz", "sabir",
    "shahzad", "shakeel", "sharif", "shehzad", "tanveer", "taufiq",
    "waheed", "waleed", "wajid", "yousuf", "zafar", "zaheer", "zia",
}

# Common Pakistani last names (lowercase)
PK_LAST_NAMES = {
    "khan", "ahmed", "ali", "shah", "malik", "hussain", "qureshi",
    "syed", "butt", "chaudhry", "sheikh", "akhtar", "baig", "bhatti",
    "dar", "ghani", "haider", "iqbal", "javed", "kazmi", "mirza",
    "naqvi", "raza", "siddiqui", "usmani", "zaidi", "abbasi", "aslam",
    "baloch", "chaudhary", "cheema", "durrani", "farooq", "gillani",
    "hashmi", "khattak", "khawaja", "kiani", "lodhi", "mengal",
    "mughal", "niazi", "paracha", "qazi", "rajput", "rehman",
    "rizvi", "sardar", "sarwar", "shaikh", "sharif", "soomro",
    "tahir", "tanveer", "yousafzai", "zaman",
    "bhat", "bhatt",  # Kashmiri-Pakistani
}


def detect_pakistani_origin(first_name, last_name, location, schools_filter, search_type, search_batch, name_match_reason):
    """
    Detect Pakistani origin and return (score, reasons_list).

    Scoring:
    - Pakistani university confirmed: 40 points
    - Location mentions Pakistan city: 30 points
    - Pakistani first AND last name: 20 points
    - Pakistani first OR last name only: 10 points
    - No Pakistan signals: 0 points

    Signals are ADDITIVE — university + name = 60 points.
    """
    score = 0
    reasons = []
    fn = first_name.lower().strip()
    ln = last_name.lower().strip()
    loc = location.lower().strip()
    sf = schools_filter.lower().strip()
    reason_text = name_match_reason.lower().strip()
    batch = search_batch.lower().strip()
    stype = search_type.lower().strip()

    # --- University signal (STRONGEST) ---
    # Check if found via university search (search_type contains 'university' or 'extended_university')
    has_university = False

    # Direct: search_type is university-based
    if "university" in stype:
        has_university = True
        reasons.append(f"Found via university search ({batch})")

    # Schools filter was used (contains Pakistani university names)
    if sf:
        for uni in PAKISTANI_UNIVERSITIES:
            if uni in sf:
                has_university = True
                reasons.append(f"Pakistani university filter: {schools_filter[:80]}")
                break

    # Check reason text for university mentions
    if "university" in reason_text or "education:" in reason_text:
        for uni in PAKISTANI_UNIVERSITIES:
            if uni in reason_text:
                has_university = True
                reasons.append(f"University in match reason")
                break

    if has_university:
        score += 40

    # --- Location signal ---
    has_location = False
    for city in PAKISTAN_CITIES:
        if city in loc:
            has_location = True
            reasons.append(f"Location: Pakistan city ({city})")
            break
    if not has_location:
        for kw in PAKISTAN_LOCATION_KEYWORDS:
            if kw in loc:
                has_location = True
                reasons.append(f"Location mentions Pakistan")
                break
    if has_location:
        score += 30

    # --- Name signal ---
    fn_match = fn in PK_FIRST_NAMES
    ln_match = ln in PK_LAST_NAMES

    # Also check compound first names like "Muhammad Ali"
    fn_parts = fn.split()
    if not fn_match:
        for part in fn_parts:
            if part in PK_FIRST_NAMES:
                fn_match = True
                break

    if fn_match and ln_match:
        score += 20
        reasons.append(f"Pakistani first name ({first_name}) + last name ({last_name})")
    elif fn_match:
        score += 10
        reasons.append(f"Pakistani first name ({first_name})")
    elif ln_match:
        score += 10
        reasons.append(f"Pakistani last name ({last_name})")

    # --- Language signal (weaker, but still relevant) ---
    if "language=urdu" in reason_text or "language=punjabi" in reason_text or "language=pashto" in reason_text or "language=sindhi" in reason_text:
        if score == 0:
            # Only name-less language match — give baseline
            score += 10
            reasons.append(f"Language signal from profile")
        elif not has_university and not has_location:
            # Language + name but no university/location — small boost
            score += 5
            reasons.append(f"Language confirmation")

    # --- Distinctive surname signal ---
    if "distinctive surname" in reason_text:
        if score < 10:
            score = 10
            reasons.append(f"Distinctive Pakistani surname")

    return score, reasons


# ============================================================
# STEP 3: Role Authority Score
# ============================================================

# Patterns for each tier (compiled for speed)
TIER1_PATTERNS = [
    r'\bcfo\b', r'\bchief financial officer\b', r'\bfinance director\b',
    r'\bhead of finance\b', r'\bvp[, ].*finance\b', r'\bvice president.*finance\b',
    r'\bpayroll\b', r'\bcontroller\b', r'\btreasurer\b', r'\bchief accountant\b',
    r'\bdirector.*finance\b', r'\bfinancial controller\b',
]

TIER2_PATTERNS = [
    r'\bcoo\b', r'\bchief operating officer\b', r'\bvp[, ].*operations?\b',
    r'\bvice president.*operations?\b', r'\boperations? director\b',
    r'\bhead of operations?\b', r'\bdirector.*operations?\b',
    r'\bhr director\b', r'\bhead of hr\b', r'\bhead of people\b',
    r'\bchief people officer\b', r'\bchief human resources\b',
    r'\bpeople operations?\b.*director\b', r'\bdirector.*human resources\b',
    r'\bvp[, ].*hr\b', r'\bvp[, ].*human resources\b', r'\bvp[, ].*people\b',
    r'\bprocurement director\b', r'\bhead of procurement\b',
    r'\bdirector.*people\b', r'\bchro\b',
]

TIER3_PATTERNS = [
    r'\bceo\b', r'\bchief executive officer\b',
    r'\bfounder\b', r'\bco-founder\b', r'\bcofounder\b',
    r'\bowner\b', r'\bmanaging director\b', r'\bpresident\b',
    r'\bgeneral manager\b', r'\bcountry manager\b', r'\bregional director\b',
    r'\bpartner\b', r'\bprincipal\b',
    r'\bchairman\b', r'\bchairperson\b',
    r'\bmanaging partner\b',
]

TIER4_PATTERNS = [
    r'\bcto\b', r'\bchief technology officer\b', r'\bchief technical officer\b',
    r'\bvp[, ].*engineering\b', r'\bvp[, ].*technology\b', r'\bvp[, ].*tech\b',
    r'\bhead of technology\b', r'\bhead of engineering\b',
    r'\bdirector.*technology\b', r'\bdirector.*engineering\b',
    r'\bbd director\b', r'\bhead of sales\b', r'\bhead of business\b',
    r'\bcommercial director\b', r'\bchief commercial officer\b',
    r'\bchief marketing officer\b', r'\bcmo\b',
    r'\bdirector.*sales\b', r'\bdirector.*marketing\b',
    r'\bdirector.*business\b', r'\bhead of marketing\b',
    r'\bvp[, ].*sales\b', r'\bvp[, ].*marketing\b', r'\bvp[, ].*business\b',
    r'\bdirector\b', r'\bhead of\b', r'\bvp\b', r'\bvice president\b',
    r'\bchief\b.*\bofficer\b',
]

ANTI_PATTERNS = [
    r'\bdeveloper\b', r'\bengineer\b(?!.*director|.*head|.*vp|.*chief)',
    r'\bdesigner\b', r'\banalyst\b', r'\bassistant\b', r'\bcoordinator\b',
    r'\breceptionist\b', r'\bsecretary\b', r'\bintern\b', r'\bstudent\b',
    r'\blooking for\b', r'\bseeking\b', r'\bopen to work\b',
    r'\bjunior\b', r'\btrainee\b', r'\bfreshers?\b',
]


def get_role_authority(title):
    """Return (score, tier_name) for a title."""
    t = title.lower().strip()
    if not t:
        return 3, "Unknown"

    # Check anti-patterns first
    for pat in ANTI_PATTERNS:
        if re.search(pat, t):
            return -50, "Anti-authority"

    # Check tiers in order
    for pat in TIER1_PATTERNS:
        if re.search(pat, t):
            return 30, "Tier 1 — Payment Authority"

    for pat in TIER2_PATTERNS:
        if re.search(pat, t):
            return 25, "Tier 2 — Operational Authority"

    for pat in TIER3_PATTERNS:
        if re.search(pat, t):
            return 20, "Tier 3 — Executive Authority"

    for pat in TIER4_PATTERNS:
        if re.search(pat, t):
            return 10, "Tier 4 — Influence Authority"

    # Catch-all: manager, senior, etc.
    if re.search(r'\bmanager\b|\bsenior\b|\blead\b|\bteam lead\b', t):
        return 3, "Tier 5 — Low Authority"

    return 3, "Tier 5 — Low Authority"


# ============================================================
# STEP 4: Industry Fit Score
# ============================================================

INDUSTRY_KEYWORDS = {
    15: [
        "software", "technology", "tech", "it services", "it consulting",
        "saas", "cloud", "digital", "artificial intelligence", "ai ",
        "machine learning", "data", "platform", "app development",
        "web development", "mobile app", "cyber", "blockchain",
        "outsourc", "bpo", "staffing", "recruitment", "talent",
        "nearshore", "offshore", "remote team", "augmentation",
    ],
    12: [
        "consulting", "advisory", "professional services", "management consult",
        "marketing", "digital agency", "creative agency", "media",
        "advertising", "pr agency", "design agency",
    ],
    10: [
        "financial", "fintech", "payment", "banking", "insurance",
        "invest", "trading", "forex", "crypto",
    ],
    8: [
        "e-commerce", "ecommerce", "retail", "marketplace", "commerce",
        "logistics", "supply chain", "freight", "shipping",
    ],
    5: [
        "construction", "real estate", "property", "engineering",
        "oil", "gas", "energy", "mining", "manufacturing",
        "healthcare", "pharma", "medical", "hospital",
    ],
    3: [
        "food", "restaurant", "hotel", "hospitality", "travel",
        "education", "school", "university",
    ],
}


def get_industry_score(company_name, title, domain):
    """Estimate industry from company name + title + domain keywords."""
    text = f"{company_name} {title} {domain}".lower()
    for score, keywords in sorted(INDUSTRY_KEYWORDS.items(), key=lambda x: -x[0]):
        for kw in keywords:
            if kw in text:
                return score, kw
    return 3, "unknown"


# ============================================================
# STEP 4b: Company Size Estimation
# ============================================================

def estimate_company_size_score(num_contacts_at_domain):
    """Estimate company size from number of contacts we found at same domain."""
    # More contacts in our dataset = bigger company (rough proxy)
    if num_contacts_at_domain >= 5:
        return 10, "201-500 (est: 5+ contacts)"
    elif num_contacts_at_domain >= 3:
        return 13, "51-200 (est: 3-4 contacts)"
    elif num_contacts_at_domain >= 2:
        return 15, "11-50 (est: 2 contacts)"
    else:
        return 8, "1-10 or unknown (1 contact)"


# ============================================================
# STEP 4c: Domain Quality Score
# ============================================================

def get_domain_score(domain):
    """Score domain quality."""
    if not domain or not domain.strip():
        return 0, "No domain"
    d = domain.lower().strip()
    # Known bad domains
    if d in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com"):
        return 0, "Personal email domain"
    if d in ("linkedin.com", "google.com", "facebook.com", "microsoft.com", "apple.com", "amazon.com"):
        return 3, "Major corp (unlikely target)"
    return 7, "Has domain"


# ============================================================
# Website verification for top domains
# ============================================================

def _check_single_domain(domain):
    """Check a single domain. Returns (domain, result_dict)."""
    d = domain.strip().lower()
    try:
        url = f"https://{d}"
        with httpx.Client(timeout=3.0, follow_redirects=True, verify=False) as client:
            resp = client.get(url)
            body = resp.text[:3000].lower()

            industry = "unknown"
            for score_val, keywords in sorted(INDUSTRY_KEYWORDS.items(), key=lambda x: -x[0]):
                for kw in keywords:
                    if kw in body:
                        industry = kw
                        break
                if industry != "unknown":
                    break

            return d, {
                "status": "verified",
                "industry": industry,
                "score": 10 if industry != "unknown" else 7,
            }
    except Exception:
        return d, {
            "status": "unreachable",
            "industry": "unknown",
            "score": 3,
        }


def verify_domains_batch(domains, max_count=800):
    """
    Check domain accessibility and extract industry keywords.
    Uses ThreadPoolExecutor for parallel requests (20 workers).
    Returns dict of domain -> {status, industry, score_adjustment}.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    unique_domains = []
    seen = set()
    for domain in domains[:max_count]:
        if not domain or not domain.strip():
            continue
        d = domain.strip().lower()
        if d not in seen:
            unique_domains.append(d)
            seen.add(d)

    print(f"\n=== Verifying {len(unique_domains)} unique domains (20 parallel workers) ===")
    sys.stdout.flush()

    results = {}
    checked = 0

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_check_single_domain, d): d for d in unique_domains}
        for future in as_completed(futures):
            d, result = future.result()
            results[d] = result
            checked += 1
            if checked % 100 == 0:
                print(f"  Checked {checked}/{len(unique_domains)} domains...")
                sys.stdout.flush()

    verified = sum(1 for v in results.values() if v["status"] == "verified")
    print(f"  Done: {checked} domains checked, {verified} verified")
    sys.stdout.flush()
    return results


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    start_time = time.time()

    # Auth
    print("=== UAE-Pakistan Priority Scoring v2 — COMPLETE REBUILD ===\n")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    creds = creds.with_subject(IMPERSONATE)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # Read source data
    print(f"Reading {SOURCE_TAB}...")
    ws = sh.worksheet(SOURCE_TAB)
    all_values = ws.get_all_values()
    header = all_values[0]
    rows = all_values[1:]
    print(f"  Loaded {len(rows)} contacts, {len(header)} columns")

    # Column indices
    COL = {h: i for i, h in enumerate(header)}
    print(f"  Columns: {list(COL.keys())}")

    # ========================================
    # STEP 1: Score Pakistani origin per contact
    # ========================================
    print("\n=== STEP 1: Pakistani Origin Detection ===")

    contacts = []
    for i, row in enumerate(rows):
        def g(col_name):
            idx = COL.get(col_name)
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        first_name = g("First Name")
        last_name = g("Last Name")
        title = g("Title")
        company = g("Company")
        domain = g("Domain")
        location = g("Location")
        linkedin = g("LinkedIn URL")
        phone = g("Phone")
        email = g("Email")
        schools_filter = g("Schools Filter Used")
        search_type = g("Search Type")
        search_batch = g("Search Batch")
        name_match_reason = g("Name Match Reason")
        schools_clay = g("Schools (from Clay)")

        pk_score, pk_reasons = detect_pakistani_origin(
            first_name, last_name, location,
            schools_filter, search_type, search_batch, name_match_reason
        )

        role_score, role_tier = get_role_authority(title)

        contacts.append({
            "idx": i,
            "first_name": first_name,
            "last_name": last_name,
            "title": title,
            "company": company,
            "domain": domain.lower().strip() if domain else "",
            "location": location,
            "linkedin": linkedin,
            "phone": phone,
            "email": email,
            "schools": schools_clay or schools_filter,
            "pk_score": pk_score,
            "pk_reasons": pk_reasons,
            "role_score": role_score,
            "role_tier": role_tier,
            "search_type": search_type,
            "search_batch": search_batch,
        })

    # Stats
    pk_score_dist = defaultdict(int)
    for c in contacts:
        pk_score_dist[c["pk_score"]] += 1

    print("\n  Pakistan Origin Score Distribution:")
    for score in sorted(pk_score_dist.keys(), reverse=True):
        label = {
            70: "University + Location + Names",
            60: "University + Names",
            50: "University + Name(single)",
            45: "University + Language",
            40: "University confirmed",
            35: "Location + Names + Language",
            30: "Location + Name",
            25: "Names + Language",
            20: "Both names match",
            15: "Name + Language",
            10: "Single name/language/surname",
            5: "Language only boost",
            0: "No Pakistan signals",
        }.get(score, f"Score {score}")
        print(f"    {score:3d} pts: {pk_score_dist[score]:6d} contacts — {label}")

    has_university = sum(1 for c in contacts if c["pk_score"] >= 40)
    has_names = sum(1 for c in contacts if c["pk_score"] >= 20 and c["pk_score"] < 40)
    has_weak = sum(1 for c in contacts if 0 < c["pk_score"] < 20)
    has_none = sum(1 for c in contacts if c["pk_score"] == 0)
    print(f"\n  Summary:")
    print(f"    University confirmed: {has_university}")
    print(f"    Name-based (no uni): {has_names}")
    print(f"    Weak signals: {has_weak}")
    print(f"    No signals: {has_none}")

    # Role distribution
    role_dist = defaultdict(int)
    for c in contacts:
        role_dist[c["role_tier"]] += 1
    print(f"\n  Role Authority Distribution:")
    for tier, count in sorted(role_dist.items()):
        print(f"    {tier}: {count}")

    # ========================================
    # STEP 2: Group by company (domain)
    # ========================================
    print("\n=== STEP 2: Group by Company (Domain) ===")

    # Group contacts by domain (or company name if no domain)
    company_groups = defaultdict(list)
    skipped_anti = 0
    for c in contacts:
        # Skip anti-authority contacts entirely
        if c["role_score"] < 0:
            skipped_anti += 1
            continue

        key = c["domain"] if c["domain"] else f"__nodomain__{c['company'].lower().strip()}"
        company_groups[key].append(c)

    print(f"  {len(company_groups)} unique companies/domains (before filtering)")
    print(f"  {sum(len(v) for v in company_groups.values())} contacts after anti-authority filter ({skipped_anti} skipped)")

    # ---- CRITICAL: Filter out non-target companies ----
    # 1. Non-company entries (Self-employed, Freelance, Confidential, empty)
    # 2. Pakistan-based organizations (domains .pk, government of Pakistan)
    # 3. Mega-corps unlikely to be EasyStaff targets

    EXCLUDE_COMPANY_PATTERNS = [
        "self-employed", "self employed", "freelance", "confidential",
        "unemployed", "independent", "not employed", "n/a",
        "looking for", "seeking", "open to",
    ]

    EXCLUDE_DOMAINS = {
        # Pakistan government/state domains
        "sbp.org.pk", "kp.gov.pk", "ppl.com.pk", "nbp.com.pk", "uop.edu.pk",
        "umt.edu.pk", "secp.gov.pk", "bok.com.pk", "sngpl.com.pk", "nastp.gov.pk",
        "faysalbank.com", "bankalfalah.com",
        # Generic/misleading
        "selfemployed.com", "freelanceinsider.net", "confidential.careers",
        "vercel.app", "github.io", "wordpress.com", "wixsite.com", "blogspot.com",
    }

    # Pakistan TLDs
    PK_TLDS = {".pk", ".com.pk", ".org.pk", ".edu.pk", ".gov.pk", ".net.pk"}

    # Mega-corps (too large for EasyStaff, but don't fully exclude — just deprioritize)
    MEGA_CORPS = {
        "google.com", "microsoft.com", "apple.com", "amazon.com", "meta.com",
        "facebook.com", "linkedin.com", "oracle.com", "ibm.com", "accenture.com",
    }

    PAKISTAN_ORG_KEYWORDS = [
        "government of pakistan", "government of khyber", "government of sindh",
        "government of punjab", "government of balochistan",
        "pakistan civil aviation", "pakistan railways", "pakistan army",
        "pakistan navy", "pakistan air force", "state bank of pakistan",
        "national bank of pakistan", "pakistan petroleum",
        "pakistan telecommunication", "pakistan international airlines",
    ]

    filtered_groups = {}
    excluded_reasons = defaultdict(int)

    for key, group in company_groups.items():
        company_name_lower = group[0]["company"].lower().strip()
        domain = key if not key.startswith("__nodomain__") else ""

        # Check 1: Non-company entries
        skip = False
        if key.startswith("__nodomain__"):
            for pat in EXCLUDE_COMPANY_PATTERNS:
                if pat in company_name_lower:
                    skip = True
                    excluded_reasons[f"Non-company: {pat}"] += len(group)
                    break
            if not company_name_lower or len(company_name_lower) < 3:
                skip = True
                excluded_reasons["Empty/short company name"] += len(group)

        if skip:
            continue

        # Check 2: Excluded domains
        if domain in EXCLUDE_DOMAINS:
            excluded_reasons[f"Excluded domain: {domain}"] += len(group)
            continue

        # Check 3: Pakistan TLD (.pk domains) — these are Pakistan-based companies
        if domain:
            for tld in PK_TLDS:
                if domain.endswith(tld):
                    excluded_reasons[f"Pakistan TLD: {tld}"] += len(group)
                    skip = True
                    break
        if skip:
            continue

        # Check 4: Pakistan government/organization keywords in company name
        for kw in PAKISTAN_ORG_KEYWORDS:
            if kw in company_name_lower:
                excluded_reasons[f"Pakistan org: {kw}"] += len(group)
                skip = True
                break
        if skip:
            continue

        # Check 5: Location-based filtering — if ALL contacts are in Pakistan, skip
        pakistan_located = sum(1 for c in group if any(
            pk_city in c["location"].lower() for pk_city in PAKISTAN_CITIES + ["pakistan"]
        ))
        uae_located = sum(1 for c in group if any(
            uae_kw in c["location"].lower()
            for uae_kw in ["dubai", "abu dhabi", "sharjah", "ajman", "uae",
                          "united arab emirates", "ras al", "fujairah", "الإمارات"]
        ))
        if pakistan_located > 0 and uae_located == 0 and len(group) > 1:
            excluded_reasons["All contacts in Pakistan (no UAE presence)"] += len(group)
            continue

        filtered_groups[key] = group

    print(f"\n  After filtering: {len(filtered_groups)} companies ({len(company_groups) - len(filtered_groups)} excluded)")
    print(f"  Exclusion reasons:")
    for reason, count in sorted(excluded_reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason}: {count} contacts")
    sys.stdout.flush()

    company_groups = filtered_groups

    # ========================================
    # STEP 3: Compute company scores
    # ========================================
    print("\n=== STEP 3: Company Scoring ===")

    company_scores = {}
    for key, group in company_groups.items():
        # Pakistan connection = sum of all contacts' pk_scores
        pk_connection = sum(c["pk_score"] for c in group)

        # Best role authority in this company
        best_role = max(c["role_score"] for c in group)

        # Industry score from company name + titles
        best_industry_score = 3
        best_industry_kw = "unknown"
        for c in group:
            iscore, ikw = get_industry_score(c["company"], c["title"], c["domain"])
            if iscore > best_industry_score:
                best_industry_score = iscore
                best_industry_kw = ikw

        # Size estimation from contact count
        size_score, size_label = estimate_company_size_score(len(group))

        # Domain quality
        domain = key if not key.startswith("__nodomain__") else ""
        domain_score, domain_label = get_domain_score(domain)

        # Mega-corp penalty — too big for EasyStaff SMB offer
        mega_penalty = 0
        if domain in MEGA_CORPS:
            mega_penalty = -30

        total = pk_connection + best_role + best_industry_score + size_score + domain_score + mega_penalty

        company_scores[key] = {
            "pk_connection": pk_connection,
            "best_role": best_role,
            "industry_score": best_industry_score,
            "industry_kw": best_industry_kw,
            "size_score": size_score,
            "size_label": size_label,
            "domain_score": domain_score,
            "domain_label": domain_label,
            "mega_penalty": mega_penalty,
            "total": total,
            "contacts": group,
            "domain": domain,
            "pk_contacts_count": sum(1 for c in group if c["pk_score"] > 0),
            "total_contacts": len(group),
        }

    # ========================================
    # STEP 3b: Verify top domains
    # ========================================
    # Sort companies by score, get top 800 unique domains for verification
    sorted_companies = sorted(company_scores.items(), key=lambda x: -x[1]["total"])
    top_domains = []
    seen_domains = set()
    for key, cs in sorted_companies:
        d = cs["domain"]
        if d and d not in seen_domains:
            top_domains.append(d)
            seen_domains.add(d)
        if len(top_domains) >= 800:
            break

    print(f"\n=== Verifying top {len(top_domains)} domains ===")
    domain_verification = verify_domains_batch(top_domains, max_count=800)

    # Update scores with verification results
    for key, cs in company_scores.items():
        d = cs["domain"]
        if d and d in domain_verification:
            v = domain_verification[d]
            # Update domain score
            cs["domain_score"] = v["score"]
            cs["domain_label"] = v["status"]
            cs["website_industry"] = v["industry"]

            # If website reveals better industry, update
            if v["industry"] != "unknown":
                for iscore, keywords in sorted(INDUSTRY_KEYWORDS.items(), key=lambda x: -x[0]):
                    if v["industry"] in keywords:
                        if iscore > cs["industry_score"]:
                            cs["industry_score"] = iscore
                            cs["industry_kw"] = v["industry"]
                        break

            # Penalize dead domains
            if v["status"] == "unreachable":
                cs["domain_score"] = 3
                cs["domain_label"] = "unreachable"

            # Recalculate total
            cs["total"] = (cs["pk_connection"] + cs["best_role"] +
                          cs["industry_score"] + cs["size_score"] + cs["domain_score"])
        else:
            cs["website_industry"] = ""

    # Company score distribution
    score_ranges = defaultdict(int)
    for cs in company_scores.values():
        bucket = (cs["total"] // 20) * 20
        score_ranges[bucket] += 1

    print(f"\n  Company Score Distribution:")
    for bucket in sorted(score_ranges.keys(), reverse=True):
        print(f"    {bucket:3d}-{bucket+19}: {score_ranges[bucket]} companies")

    # Pakistan connection score distribution
    pk_ranges = defaultdict(int)
    for cs in company_scores.values():
        pk_ranges[cs["pk_connection"]] = pk_ranges.get(cs["pk_connection"], 0) + 1

    print(f"\n  Pakistan Connection Score Distribution (top 20):")
    for score in sorted(pk_ranges.keys(), reverse=True)[:20]:
        print(f"    {score:4d}: {pk_ranges[score]} companies")

    # ========================================
    # STEP 4: Print top 50 companies
    # ========================================
    sorted_companies = sorted(company_scores.items(), key=lambda x: -x[1]["total"])

    print(f"\n=== TOP 50 COMPANIES ===")
    for i, (key, cs) in enumerate(sorted_companies[:50], 1):
        company_name = cs["contacts"][0]["company"]
        pk_names = [f"{c['first_name']} {c['last_name']} ({c['title'][:40]}, pk={c['pk_score']})"
                    for c in sorted(cs["contacts"], key=lambda x: -x["pk_score"])[:5]]
        print(f"\n  #{i}: {company_name} ({cs['domain'] or 'no domain'})")
        print(f"    Total: {cs['total']} | PK Connection: {cs['pk_connection']} | "
              f"Best Role: {cs['best_role']} | Industry: {cs['industry_score']} ({cs['industry_kw']}) | "
              f"Size: {cs['size_score']} ({cs['size_label']}) | Domain: {cs['domain_score']} ({cs['domain_label']})")
        print(f"    {cs['pk_contacts_count']} Pakistani-origin contacts of {cs['total_contacts']} total:")
        for pn in pk_names:
            print(f"      - {pn}")

    # ========================================
    # STEP 5: Select top 2000 contacts
    # ========================================
    print(f"\n=== STEP 5: Selecting Top {TARGET_COUNT} Contacts ===")

    selected = []
    companies_used = 0

    for key, cs in sorted_companies:
        if len(selected) >= TARGET_COUNT:
            break

        # Sort contacts: best role first, then highest pk_score
        sorted_contacts = sorted(
            cs["contacts"],
            key=lambda c: (-c["role_score"], -c["pk_score"])
        )

        # Pick up to MAX_PER_COMPANY
        picked = 0
        seen_tiers = set()
        for c in sorted_contacts:
            if picked >= MAX_PER_COMPANY:
                break
            if picked >= 2 and cs["total"] <= HIGH_COMPANY_THRESHOLD:
                break  # Only pick 3rd if company is high-scoring

            # Try to pick diverse roles
            if c["role_tier"] in seen_tiers and picked > 0 and len(sorted_contacts) > picked:
                continue

            # Compute final contact score
            final_score = cs["total"]  # Company score is the base

            # Build reasoning
            pk_connection_desc = "No Pakistan signals"
            if cs["pk_connection"] >= 80:
                pk_connection_desc = f"VERY STRONG ({cs['pk_contacts_count']} Pakistani-origin executives)"
            elif cs["pk_connection"] >= 40:
                pk_connection_desc = f"STRONG ({cs['pk_contacts_count']} Pakistani-origin executives, university confirmed)"
            elif cs["pk_connection"] >= 20:
                pk_connection_desc = f"MODERATE ({cs['pk_contacts_count']} contacts with Pakistani names)"
            elif cs["pk_connection"] >= 10:
                pk_connection_desc = f"WEAK ({cs['pk_contacts_count']} contacts with some Pakistan signals)"
            elif cs["pk_connection"] > 0:
                pk_connection_desc = f"MINIMAL ({cs['pk_contacts_count']} contacts with weak signals)"

            pk_detail = "; ".join(c["pk_reasons"]) if c["pk_reasons"] else "No direct Pakistan signals"

            reasoning = (
                f"COMPANY: {cs['domain'] or c['company']} (score {cs['total']}) — "
                f"{cs['pk_contacts_count']} Pakistani-origin of {cs['total_contacts']} contacts, "
                f"{'verified' if cs.get('website_industry') else 'unverified'} "
                f"{cs['industry_kw']} domain, {cs['size_label']}. "
                f"PAKISTAN CONNECTION: {pk_connection_desc} "
                f"(connection score {cs['pk_connection']}). "
                f"CONTACT: {pk_detail}. "
                f"ROLE: {c['title'][:50]} ({c['role_tier']}, +{c['role_score']}). "
                f"WHY: {'High-authority' if c['role_score'] >= 20 else 'Relevant'} role at "
                f"{'strongly' if cs['pk_connection'] >= 40 else 'moderately' if cs['pk_connection'] >= 20 else 'potentially'} "
                f"Pakistan-connected company."
            )

            selected.append({
                "rank": 0,  # Will be set later
                "first_name": c["first_name"],
                "last_name": c["last_name"],
                "title": c["title"],
                "role_tier": c["role_tier"],
                "company": c["company"],
                "domain": cs["domain"],
                "domain_status": cs.get("domain_label", ""),
                "website_industry": cs.get("website_industry", cs["industry_kw"]),
                "location": c["location"],
                "linkedin": c["linkedin"],
                "email": c["email"],
                "phone": c["phone"],
                "schools": c["schools"],
                "company_score": cs["total"],
                "pk_connection_score": cs["pk_connection"],
                "contacts_at_company": cs["total_contacts"],
                "role_authority_score": c["role_score"],
                "final_score": final_score,
                "reasoning": reasoning,
            })

            picked += 1
            seen_tiers.add(c["role_tier"])
            companies_used += 1

    # Assign ranks
    for i, s in enumerate(selected, 1):
        s["rank"] = i

    print(f"  Selected {len(selected)} contacts from {companies_used} company slots")

    # Stats on selected
    tier_dist = defaultdict(int)
    pk_dist = defaultdict(int)
    for s in selected:
        tier_dist[s["role_tier"]] += 1
        bucket = (s["pk_connection_score"] // 20) * 20
        pk_dist[bucket] += 1

    print(f"\n  Selected contacts by Role Tier:")
    for tier, count in sorted(tier_dist.items()):
        print(f"    {tier}: {count}")

    print(f"\n  Selected contacts by Company PK Connection Score:")
    for bucket in sorted(pk_dist.keys(), reverse=True):
        print(f"    {bucket}-{bucket+19}: {pk_dist[bucket]} contacts")

    domain_filled = sum(1 for s in selected if s["domain"])
    print(f"\n  Contacts with domain: {domain_filled}/{len(selected)}")

    # ========================================
    # STEP 6: Write to Google Sheet
    # ========================================
    print(f"\n=== STEP 6: Writing to '{TARGET_TAB}' ===")

    output_header = [
        "Rank", "First Name", "Last Name", "Title", "Role Tier",
        "Company", "Domain", "Domain Status", "Website Industry",
        "Location", "LinkedIn URL", "Email", "Phone", "Schools",
        "Company Score", "Pakistan Connection Score", "Contacts at Company",
        "Role Authority Score", "Final Score", "Reasoning"
    ]

    output_rows = [output_header]
    for s in selected:
        output_rows.append([
            s["rank"],
            s["first_name"],
            s["last_name"],
            s["title"],
            s["role_tier"],
            s["company"],
            s["domain"],
            s["domain_status"],
            s["website_industry"],
            s["location"],
            s["linkedin"],
            s["email"],
            s["phone"],
            s["schools"],
            s["company_score"],
            s["pk_connection_score"],
            s["contacts_at_company"],
            s["role_authority_score"],
            s["final_score"],
            s["reasoning"],
        ])

    # Get or create target tab
    try:
        target_ws = sh.worksheet(TARGET_TAB)
        target_ws.clear()
        print(f"  Cleared existing tab '{TARGET_TAB}'")
    except gspread.exceptions.WorksheetNotFound:
        target_ws = sh.add_worksheet(
            title=TARGET_TAB,
            rows=len(output_rows) + 5,
            cols=len(output_header)
        )
        print(f"  Created new tab '{TARGET_TAB}'")

    # Resize if needed
    if target_ws.row_count < len(output_rows):
        target_ws.resize(rows=len(output_rows) + 5, cols=len(output_header))

    # Write in batches to avoid API limits
    BATCH_SIZE = 1000
    for batch_start in range(0, len(output_rows), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(output_rows))
        batch = output_rows[batch_start:batch_end]
        cell = f"A{batch_start + 1}"
        target_ws.update(range_name=cell, values=batch)
        print(f"  Wrote rows {batch_start + 1}-{batch_end}")
        if batch_end < len(output_rows):
            time.sleep(2)  # Rate limit

    # Format header
    target_ws.format(f"A1:{chr(64 + len(output_header))}1", {
        "textFormat": {"bold": True},
    })

    # Freeze header row
    target_ws.freeze(rows=1)

    elapsed = time.time() - start_time
    print(f"\n=== DONE in {elapsed:.0f}s ===")
    print(f"  Output: {len(selected)} contacts in '{TARGET_TAB}'")
    print(f"  Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")

    # Save full output for review
    with open("/tmp/uae_pk_v2_results.txt", "w") as f:
        f.write(f"UAE-Pakistan Priority Scoring v2 Results\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"Total contacts scored: {len(contacts)}\n")
        f.write(f"Companies analyzed: {len(company_scores)}\n")
        f.write(f"Selected: {len(selected)}\n\n")

        f.write(f"Pakistan Origin Score Distribution:\n")
        for score in sorted(pk_score_dist.keys(), reverse=True):
            f.write(f"  {score:3d} pts: {pk_score_dist[score]:6d} contacts\n")

        f.write(f"\nTop 50 Companies:\n")
        for i, (key, cs) in enumerate(sorted_companies[:50], 1):
            company_name = cs["contacts"][0]["company"]
            f.write(f"\n#{i}: {company_name} ({cs['domain'] or 'no domain'}) — Score: {cs['total']}\n")
            f.write(f"  PK Connection: {cs['pk_connection']} | Role: {cs['best_role']} | "
                   f"Industry: {cs['industry_score']} | Size: {cs['size_score']} | Domain: {cs['domain_score']}\n")
            for c in sorted(cs["contacts"], key=lambda x: -x["pk_score"])[:5]:
                f.write(f"  - {c['first_name']} {c['last_name']} ({c['title'][:50]}) pk={c['pk_score']} role={c['role_score']}\n")

        f.write(f"\n\nFull Selected Contacts:\n")
        f.write(f"{'='*60}\n")
        for s in selected[:100]:
            f.write(f"\n#{s['rank']}: {s['first_name']} {s['last_name']} | {s['title']}\n")
            f.write(f"  Company: {s['company']} ({s['domain']})\n")
            f.write(f"  Scores: Company={s['company_score']} PK={s['pk_connection_score']} Role={s['role_authority_score']}\n")
            f.write(f"  {s['reasoning'][:200]}\n")

    print(f"  Full results saved to /tmp/uae_pk_v2_results.txt")


if __name__ == "__main__":
    main()
