#!/usr/bin/env python3
"""
OnSocial Enrichment & Segmentation Pipeline — unified script
Steps 0-8: Blacklist → Load → Dedup → Filter → DNS → Scrape → Classify → Output

Usage:
  python pipeline_onsocial.py                      # run all steps
  python pipeline_onsocial.py --from-step 6        # start from step 6
  python pipeline_onsocial.py --step 4             # run only step 4
  python pipeline_onsocial.py --limit 20           # stop after 20 targets (first run)
  python pipeline_onsocial.py --force              # re-run even if output exists
  python pipeline_onsocial.py --import-existing    # import pipeline_results_run*.json into cache

Requires: httpx, beautifulsoup4
Optional: OPENAI_API_KEY env var for GPT-4o-mini classification
"""

import argparse
import asyncio
import csv
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ── PATHS ──────────────────────────────────────────────────────────────────────
SOFIA_DIR = Path(__file__).parent.parent
REPO_DIR = SOFIA_DIR.parent
INPUT_DIR = SOFIA_DIR / "input"
STATE_DIR = REPO_DIR / "state" / "onsocial"
# IMPROVEMENT E: Shared website cache across projects (OnSocial, ArchiStruct, etc.)
# Scraping the same domain for different projects wastes time and bandwidth.
# Shared cache means: scraped once → reused everywhere.
SHARED_CACHE_DIR = REPO_DIR / "state" / "shared"
WEBSITE_CACHE_DIR = SHARED_CACHE_DIR / "website_cache"
PROMPT_VERSIONS_DIR = STATE_DIR / "prompt_versions"

STATE_DIR.mkdir(parents=True, exist_ok=True)
SHARED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
WEBSITE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROMPT_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

# State files
BLACKLIST_FILE   = STATE_DIR / "campaign_blacklist.json"
ALL_COMPANIES    = STATE_DIR / "all_companies.json"
AFTER_BLACKLIST  = STATE_DIR / "after_blacklist.json"
PRIORITY_FILE    = STATE_DIR / "priority.json"
NORMAL_FILE      = STATE_DIR / "normal.json"
DISQUALIFIED     = STATE_DIR / "disqualified.json"
CLASSIFICATIONS  = STATE_DIR / "classifications.json"
TARGETS_FILE     = STATE_DIR / "targets.json"
REJECTS_FILE     = STATE_DIR / "rejects.json"
STATS_FILE       = STATE_DIR / "pipeline_stats.json"

# Source sheet files (already downloaded)
SHEET_FILES = {
    "us":     INPUT_DIR / "sheet_us.json",
    "uk_eu":  INPUT_DIR / "sheet_uk_eu.json",
    "latam":  INPUT_DIR / "sheet_latam.json",
    "india":  INPUT_DIR / "sheet_india.json",
    "mixed":  INPUT_DIR / "sheet_mixed.json",
}

# ── CSV EXPORT CONFIG ─────────────────────────────────────────────────────────
# Naming convention: [PROJECT] | [TYPE] | [SEGMENT] — [DATE]
# Folder structure: OnSocial/{Leads,Targets,Import,Archive}/
PROJECT_CODE = "OS"  # Short code for naming: OS = OnSocial
CSV_OUTPUT_DIR = SOFIA_DIR / "output" / "OnSocial"
CSV_TARGETS_DIR = CSV_OUTPUT_DIR / "Targets"
CSV_ARCHIVE_DIR = CSV_OUTPUT_DIR / "Archive"

for _d in [CSV_OUTPUT_DIR, CSV_TARGETS_DIR, CSV_ARCHIVE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

def _date_tag() -> str:
    """Return short date tag for file naming, e.g. 'Mar 24'."""
    return datetime.now().strftime("%b %d")

def _csv_name(type_: str, segment: str = "", suffix: str = "") -> str:
    """Build standardized CSV filename. E.g. 'OS | Targets | INFPLAT — Mar 24.csv'"""
    parts = [PROJECT_CODE, type_]
    if segment:
        parts.append(segment)
    name = " | ".join(parts)
    if suffix:
        name += f" — {suffix}"
    else:
        name += f" — {_date_tag()}"
    return f"{name}.csv"

def save_csv(path: Path, rows: list[dict]):
    """Save list of dicts to CSV."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → saved CSV: {path.name} ({len(rows)} rows)")

PROMPT_VERSION = "v1"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
POSITIVE_KEYWORDS = [
    "influencer", "creator", "ugc", "affiliate", "social media marketing",
    "talent management", "content creator", "brand ambassador",
    "influencer marketing", "creator economy", "mcn", "creator marketplace",
    "influencer analytics", "influencer platform", "creator monetization",
    "social commerce", "live shopping", "influencer agency", "creator campaigns",
    "affiliate network", "performance marketing", "cpa network",
]

DISQUALIFY_INDUSTRIES = [
    "staffing", "recruitment", "real estate", "construction", "mining",
    "oil & gas", "legal services", "law firm", "accounting", "banking",
    "government", "military", "defense", "utilities", "agriculture",
    "farming", "food production", "insurance", "logistics", "shipping",
    "transportation", "civil engineering", "pharmaceuticals",
    "veterinary", "dairy", "fishery", "forestry", "ranching",
]

# Full-service agency signals (FSA filter — removed before GPT)
FSA_PATTERNS = [
    r"\bseo\b.*\bppc\b", r"\bppc\b.*\bseo\b",
    r"\bseo\b.*\bweb design\b", r"\bfull.?service\b.*\bagency\b",
    r"\bdigital marketing agency\b.*\bseo\b",
    r"\bpr agency\b", r"\bpublic relations\b.*\bagency\b",
]

# ── IMPROVEMENT A: Regexp pre-filter patterns for dead/parked sites ───────────
# Applied AFTER scraping, BEFORE GPT — saves ~10-15% GPT calls
PARKED_DOMAIN_PATTERNS = [
    r"this domain is for sale",
    r"domain is parked",
    r"buy this domain",
    r"domain expired",
    r"this page is under construction",
    r"coming soon",
    r"parked by",
    r"godaddy",
    r"hugedomains",
    r"dan\.com",
    r"sedo\.com",
    r"afternic",
    r"undeveloped\.com",
    r"is available for purchase",
    r"this website is for sale",
]

# FSA patterns on full website text (stronger than Apollo-only check in Step 4)
FSA_WEBSITE_PATTERNS = [
    r"\bseo\b.*\bppc\b.*\b(web design|social media)\b",
    r"\bfull.?service\b.*\b(digital|marketing|creative)\b.*\bagency\b",
    r"\b(seo|ppc|web design|email marketing|social media)\b.*\b(seo|ppc|web design|email marketing|social media)\b.*\b(seo|ppc|web design|email marketing)\b",
]

# ── IMPROVEMENT B: Skip-scrape threshold ──────────────────────────────────────
# Companies with strong Apollo signals can be classified without scraping
SKIP_SCRAPE_MIN_SIGNALS = int(os.environ.get("SKIP_SCRAPE_MIN_SIGNALS", "3"))
SKIP_SCRAPE_MIN_DESC_LEN = int(os.environ.get("SKIP_SCRAPE_MIN_DESC_LEN", "100"))

CLASSIFICATION_PROMPT = """\
You classify companies as potential customers of OnSocial — a B2B API
that provides creator/influencer data for Instagram, TikTok, and YouTube
(audience demographics, engagement analytics, fake follower detection,
creator search).

Companies that need OnSocial are those whose CORE business involves
working with social media creators.

══ STEP 1: INSTANT DISQUALIFIERS ══
- website_content is EMPTY and apollo_description is EMPTY
  → "OTHER | No data available"
- Domain is parked / for sale / dead → "OTHER | Domain inactive"
- 5000+ employees → "OTHER | Enterprise, too large"
- <10 employees → "OTHER | Too small"

If none triggered → continue to Step 2.

══ STEP 2: SEGMENTS ══

INFLUENCER_PLATFORMS
  Builds SaaS / software / tools for influencer marketing: analytics,
  creator discovery, campaign management, creator CRM, UGC content
  platforms, creator marketplaces, creator monetization tools, social
  commerce, live shopping platforms, social listening with creator focus.
  KEY TEST: they have a PRODUCT (software/platform/API) that brands or
  agencies use to find, analyze, manage, or pay creators.

AFFILIATE_PERFORMANCE
  Affiliate network, performance marketing platform, CPA/CPS/CPL network,
  partner/referral platforms that connect advertisers with publishers/
  creators and pay per conversion.
  KEY TEST: they monetize based on conversions/actions, connecting
  advertisers with publishers or creators.

IM_FIRST_AGENCIES
  Agency where influencer/creator campaigns are THE primary business,
  not a side service. 10–500 employees. Includes: influencer-first
  agencies, MCN (multi-channel networks), creator talent management,
  gaming influencer agencies, UGC production agencies.
  KEY TEST: 60%+ of their visible offering (homepage, case studies,
  team titles) is about creator/influencer work.
  NOT THIS: "full-service digital agency" that lists influencers as one
  of many equal services.

OTHER
  Everything that does NOT fit the three segments above: brands,
  media/publishers, PR agencies, generic digital agencies, ad tech
  without creator focus, unrelated SaaS, consulting, staffing,
  e-commerce stores. Also OTHER if influencer work is a minor add-on
  (< ~30% of visible offering).

NEW SEGMENTS (dynamic discovery):
  If a company does NOT fit the three segments above, but you notice it
  belongs to a RECURRING business type that could be a separate
  meaningful category (e.g., "SOCIAL_COMMERCE_BRANDS", "GAMING_STUDIOS",
  "CREATOR_ECONOMY_INFRA"), classify as:
  NEW:CATEGORY_NAME | reason
  Only use NEW: when the company clearly belongs to a distinct, nameable
  business type — not for random one-offs.

══ STEP 3: FIND EVIDENCE ══
Companies use marketing language, not technical descriptions.
Look for MEANING, not exact keywords.

Signals → INFLUENCER_PLATFORMS:
  "dashboard", "creator discovery", "book a demo", "start free trial",
  "integrations", "analytics for creators", "brand-creator matching",
  "content marketplace", "amplify your brand", "connect brands with
  creators", "UGC at scale", "creator content engine", "shoppable content"

Signals → AFFILIATE_PERFORMANCE:
  "affiliate", "CPA", "CPS", "publisher network", "advertiser",
  "conversion tracking", "partner payouts", "referral platform",
  "performance-driven", "cost per action"

Signals → IM_FIRST_AGENCIES:
  "influencer agency", "creator campaigns", "talent management", "MCN",
  "we connect brands with creators", case studies dominated by influencer
  work, "talent management for digital creators"

Signals → OTHER:
  No mention of creators/influencers/UGC. OR influencer is one bullet
  point among SEO, PPC, PR, web design, etc. OR company is a brand that
  USES influencers (not a service provider).

══ STEP 4: CONFLICT RESOLUTION ══
- WEBSITE CONTENT outweighs apollo_description (more reliable).
- If mixed signals (agency + platform) → choose based on PRIMARY revenue
  model.
- "Social media marketing" alone without creator-specific features → OTHER.
- "Digital marketing agency" with influencer-dominated homepage → check
  ratio → IM_FIRST_AGENCIES or OTHER.
- If genuinely ambiguous after all evidence → OTHER.

══ INPUT ══
Company: {company_name}
Employees: {employees}
Industry: {industry}
Keywords: {keywords}
Apollo description: {description}
Website content: {website_content}

══ OUTPUT ══
SEGMENT | one-sentence evidence from website/apollo

Examples:
INFLUENCER_PLATFORMS | Homepage offers a creator discovery dashboard with audience analytics and brand matching tools
AFFILIATE_PERFORMANCE | Operates a CPA network connecting advertisers with influencer-publishers
IM_FIRST_AGENCIES | Agency specializing in TikTok creator campaigns, all 6 case studies are influencer activations
OTHER | Generic digital agency offering SEO, PPC, email, and influencer as one of 8 services
NEW:SOCIAL_COMMERCE_TOOLS | Builds shoppable video tools for e-commerce brands, not influencer-focused but creator-adjacent
"""

# ── HELPERS ────────────────────────────────────────────────────────────────────

def norm_domain(raw: str) -> str:
    """Normalize domain: strip protocol, www, port, trailing slash."""
    if not raw:
        return ""
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0]
    d = d.split("?")[0]
    d = d.split("#")[0]
    d = d.split(":")[0]  # strip port
    return d.strip()

def has_positive_signal(text: str) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in POSITIVE_KEYWORDS)

def is_fsa(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in FSA_PATTERNS)

def count_positive_signals(keywords: str, description: str) -> int:
    combined = f"{keywords} {description}".lower()
    return sum(1 for kw in POSITIVE_KEYWORDS if kw in combined)

def load_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → saved {path.name} ({len(data) if isinstance(data, (list, dict)) else ''})")

def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_parked_or_dead(content: str) -> str | None:
    """Check if website content indicates parked/dead domain. Returns reason or None."""
    if not content:
        return None
    t = content.lower()
    if len(t) < 100:
        return f"Placeholder site ({len(t)} chars)"
    for pattern in PARKED_DOMAIN_PATTERNS:
        if re.search(pattern, t):
            return f"Parked/dead domain (matched: {pattern[:30]})"
    return None


def is_fsa_website(content: str) -> bool:
    """Check if website text shows full-service agency pattern (stronger than Apollo-only)."""
    if not content:
        return False
    t = content.lower()
    return any(re.search(p, t) for p in FSA_WEBSITE_PATTERNS)


def can_skip_scraping(company: dict) -> bool:
    """Check if company has enough Apollo data to classify without scraping."""
    signals = company.get("signal_count", 0)
    desc = company.get("description", "") or company.get("short_description", "")
    return signals >= SKIP_SCRAPE_MIN_SIGNALS and len(desc) >= SKIP_SCRAPE_MIN_DESC_LEN


# ── IMPROVEMENT C: Self-check helpers ─────────────────────────────────────────

def self_check(step_name: str, value: int, total: int, expected_min_pct: float,
               expected_max_pct: float, metric_name: str):
    """Print warning if metric is outside expected range."""
    if total == 0:
        return
    pct = value * 100 / total
    if pct < expected_min_pct:
        print(f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — below expected {expected_min_pct}%")
        print(f"       ({value}/{total}). Check pipeline logic or input data.")
    elif pct > expected_max_pct:
        print(f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — above expected {expected_max_pct}%")
        print(f"       ({value}/{total}). Check if filters are too broad/narrow.")

# ── STEP 0: BUILD BLACKLIST ────────────────────────────────────────────────────

def step0_blacklist(force: bool = False):
    print("\n=== STEP 0: Blacklist ===")
    if BLACKLIST_FILE.exists() and not force:
        bl = load_json(BLACKLIST_FILE)
        print(f"  already exists: {bl['count']} domains (skip, use --force to rebuild)")
        return bl

    # Copy from input if exists
    src = INPUT_DIR / "campaign_blacklist.json"
    if src.exists():
        bl = load_json(src)
        save_json(BLACKLIST_FILE, bl)
        print(f"  copied from input: {bl['count']} domains")
        return bl

    print("  ERROR: campaign_blacklist.json not found in input/")
    sys.exit(1)


# ── STEP 1: LOAD & NORMALIZE ───────────────────────────────────────────────────

def step1_load(force: bool = False):
    print("\n=== STEP 1: Load & Normalize ===")
    if ALL_COMPANIES.exists() and not force:
        companies = load_json(ALL_COMPANIES)
        print(f"  already exists: {len(companies)} companies (skip)")
        return companies

    companies = []
    for sheet_key, sheet_path in SHEET_FILES.items():
        if not sheet_path.exists():
            print(f"  WARN: {sheet_path.name} not found, skipping")
            continue
        data = load_json(sheet_path)
        headers = [h.strip() for h in data["headers"]]
        rows = data["rows"]

        # Column mapping
        def col(name_variants):
            for v in name_variants:
                for i, h in enumerate(headers):
                    if h.lower() == v.lower():
                        return i
            return -1

        ci_name     = col(["Company Name"])
        ci_emp      = col(["# Employees"])
        ci_industry = col(["Industry"])
        ci_website  = col(["Website"])
        ci_linkedin = col(["Company Linkedin Url"])
        ci_country  = col(["Company Country"])
        ci_keywords = col(["Keywords"])
        ci_short    = col(["Short Description"])
        ci_desc     = col(["Description"])
        ci_tech     = col(["Technologies"])
        ci_founded  = col(["Founded Year"])

        def get(row, idx):
            if idx < 0 or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] else ""

        for row in rows:
            website = get(row, ci_website)
            domain = norm_domain(website)
            if not domain:
                continue

            companies.append({
                "domain": domain,
                "company_name": get(row, ci_name),
                "employees": get(row, ci_emp),
                "industry": get(row, ci_industry),
                "website": website,
                "linkedin_url": get(row, ci_linkedin),
                "country": get(row, ci_country),
                "keywords": get(row, ci_keywords)[:500],
                "short_description": get(row, ci_short)[:500],
                "description": get(row, ci_desc)[:1000],
                "technologies": get(row, ci_tech)[:300],
                "founded_year": get(row, ci_founded),
                "source_sheet": sheet_key,
            })

        print(f"  {sheet_key}: {len(rows)} rows → loaded")

    print(f"  Total loaded: {len(companies)}")
    # Self-check: expect 20,000-100,000 companies from Apollo
    if len(companies) < 5000:
        print(f"  ⚠️  ALERT [Step 1]: Only {len(companies)} companies loaded — expected 20,000+. Check input files.")
    elif len(companies) < 20000:
        print(f"  ℹ️  NOTE [Step 1]: {len(companies)} companies loaded — slightly below typical 20,000+")
    save_json(ALL_COMPANIES, companies)
    return companies


# ── STEP 2: DEDUPLICATE ────────────────────────────────────────────────────────

def step2_dedup(companies: list, force: bool = False):
    print("\n=== STEP 2: Deduplicate ===")
    if AFTER_BLACKLIST.exists() and not force:
        # already did 2+3 combined, skip
        data = load_json(AFTER_BLACKLIST)
        print(f"  after_blacklist already exists: {len(data)} companies (skip)")
        return companies  # return raw for next step that will check file

    seen = {}
    dupes = 0
    for c in companies:
        d = c["domain"]
        if d not in seen:
            seen[d] = c
        else:
            dupes += 1

    deduped = list(seen.values())
    print(f"  {len(companies)} → {len(deduped)} unique (removed {dupes} dupes)")
    # Self-check: dupe rate typically 1-30%
    self_check("Step 2", dupes, len(companies), 0, 40, "Duplicate rate")
    return deduped


# ── STEP 3: BLACKLIST FILTER ───────────────────────────────────────────────────

def step3_blacklist_filter(companies: list, blacklist: dict, force: bool = False):
    print("\n=== STEP 3: Blacklist Filter ===")
    if AFTER_BLACKLIST.exists() and not force:
        data = load_json(AFTER_BLACKLIST)
        print(f"  already exists: {len(data)} companies (skip)")
        return data

    bl_set = set(blacklist["domains"])
    passed = []
    removed = 0
    for c in companies:
        if c["domain"] in bl_set:
            removed += 1
        else:
            passed.append(c)

    print(f"  {len(companies)} → {len(passed)} (removed {removed} blacklisted)")
    if removed == 0:
        print("  ⚠️  ALERT [Step 3]: 0 removed — check domain normalization (www, trailing /)")
    # Self-check: blacklist should remove 1-10%
    self_check("Step 3", removed, len(companies), 0.5, 15, "Blacklist removal rate")
    save_json(AFTER_BLACKLIST, passed)
    return passed


# ── STEP 4: DETERMINISTIC FILTER ──────────────────────────────────────────────

def step4_filter(companies: list, force: bool = False):
    print("\n=== STEP 4: Deterministic Filter ===")

    if PRIORITY_FILE.exists() and NORMAL_FILE.exists() and DISQUALIFIED.exists() and not force:
        priority = load_json(PRIORITY_FILE)
        normal = load_json(NORMAL_FILE)
        disq = load_json(DISQUALIFIED)
        print(f"  already exists: {len(priority)} priority, {len(normal)} normal, {len(disq)} disqualified (skip)")
        return priority, normal, disq

    priority = []
    normal = []
    disq_list = []

    for c in companies:
        # 4a. Employee filter
        emp_str = c.get("employees", "").replace(",", "").strip()
        emp = None
        if emp_str.isdigit():
            emp = int(emp_str)

        disq_reason = None
        if emp is not None:
            if emp < 5:
                disq_reason = f"Too small ({emp} employees)"
            elif emp > 5000:
                disq_reason = f"Enterprise ({emp} employees)"

        # 4b. Industry disqualifier (only if no positive override)
        if not disq_reason:
            industry_lower = c.get("industry", "").lower()
            keywords_lower = c.get("keywords", "").lower()
            combined = f"{industry_lower} {keywords_lower}"

            # Check positive override first
            has_positive = has_positive_signal(combined)

            if not has_positive:
                for bad in DISQUALIFY_INDUSTRIES:
                    if bad in industry_lower:
                        disq_reason = f"Industry: {c['industry']}"
                        break

        # 4c. FSA filter (full-service agency)
        if not disq_reason:
            combined_text = f"{c.get('keywords','')} {c.get('short_description','')} {c.get('description','')}".lower()
            if is_fsa(combined_text) and not has_positive_signal(combined_text):
                disq_reason = "Full-service agency (FSA filter)"

        if disq_reason:
            c["disqualify_reason"] = disq_reason
            disq_list.append(c)
        else:
            # 4d. Positive signal detection → priority queue
            signal_text = f"{c.get('keywords','')} {c.get('short_description','')} {c.get('description','')}"
            n_signals = count_positive_signals(c.get("keywords",""), c.get("short_description","") + " " + c.get("description",""))
            c["has_positive_signal"] = n_signals > 0
            c["signal_count"] = n_signals

            if n_signals > 0:
                priority.append(c)
            else:
                normal.append(c)

    # Sort priority by signal count descending (strongest first)
    priority.sort(key=lambda x: x.get("signal_count", 0), reverse=True)

    print(f"  Priority (positive signals): {len(priority)}")
    print(f"  Normal (no signals):         {len(normal)}")
    print(f"  Disqualified:                {len(disq_list)}")
    print(f"  Total:                       {len(priority)+len(normal)+len(disq_list)}")

    # Self-checks from ENRICHMENT_PIPELINE.md best practices
    total_processed = len(priority) + len(normal) + len(disq_list)
    self_check("Step 4", len(priority), total_processed, 5, 25, "Priority queue %")
    self_check("Step 4", len(disq_list), total_processed, 2, 30, "Disqualified %")
    if len(normal) == 0 and len(priority) == 0:
        print("  ⚠️  ALERT [Step 4]: No companies passed filtering! Check input data or relax filters.")

    save_json(PRIORITY_FILE, priority)
    save_json(NORMAL_FILE, normal)
    save_json(DISQUALIFIED, disq_list)
    return priority, normal, disq_list


# ── STEP 5: DNS PRE-CHECK ──────────────────────────────────────────────────────

def step5_dns(companies: list, force: bool = False) -> list:
    """DNS check on priority companies. Updates in-place and returns alive subset."""
    print("\n=== STEP 5: DNS Pre-check ===")

    # Load existing DNS results from classification cache (to avoid re-checking)
    classifications = load_json(CLASSIFICATIONS) or {}
    dns_cache_file = STATE_DIR / "dns_cache.json"
    dns_cache = load_json(dns_cache_file) or {}

    alive = []
    dead = []
    new_checks = 0

    for c in companies:
        domain = c["domain"]

        if domain in dns_cache:
            c["dns_alive"] = dns_cache[domain]
        elif domain in classifications:
            # Already classified = was reachable at some point
            c["dns_alive"] = True
            dns_cache[domain] = True
        else:
            try:
                socket.setdefaulttimeout(3)
                socket.getaddrinfo(domain, None)
                c["dns_alive"] = True
                dns_cache[domain] = True
            except (socket.gaierror, OSError):
                c["dns_alive"] = False
                dns_cache[domain] = False
            new_checks += 1
            if new_checks % 100 == 0:
                print(f"    DNS: {new_checks} checked...")
                save_json(dns_cache_file, dns_cache)

        if c["dns_alive"]:
            alive.append(c)
        else:
            dead.append(c)

    save_json(dns_cache_file, dns_cache)
    print(f"  {len(companies)} domains → {len(alive)} alive, {len(dead)} dead ({new_checks} new checks)")
    return alive


# ── STEP 6: WEBSITE SCRAPING ───────────────────────────────────────────────────

async def scrape_domain(client: httpx.AsyncClient, domain: str) -> dict:
    """Scrape a single domain. Returns cache entry."""
    cache_file = WEBSITE_CACHE_DIR / f"{domain}.json"

    if cache_file.exists():
        return load_json(cache_file)

    result = {
        "domain": domain,
        "status": "error",
        "content": "",
        "status_code": None,
        "scraped_at": ts(),
        "error": None,
    }

    try:
        url = f"https://{domain}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        response = await client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        result["status_code"] = response.status_code

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove noise tags
            for tag in soup(["nav", "footer", "script", "style", "noscript", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()
            result["content"] = text[:5000]
            result["status"] = "success"
        elif response.status_code in (403, 429):
            result["status"] = "blocked"
        else:
            result["status"] = "error"
            result["error"] = f"HTTP {response.status_code}"

    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["error"] = "timeout"
    except httpx.ConnectError as e:
        result["status"] = "error"
        result["error"] = f"connect: {str(e)[:100]}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:100]

    save_json(cache_file, result)
    return result


async def step6_scrape(companies: list, concurrency: int = 8) -> dict:
    """Scrape all companies. Returns {domain: cache_entry}."""
    print(f"\n=== STEP 6: Website Scraping (concurrency={concurrency}) ===")

    # Check how many are already cached
    cached = sum(1 for c in companies if (WEBSITE_CACHE_DIR / f"{c['domain']}.json").exists())
    to_scrape = [c for c in companies if not (WEBSITE_CACHE_DIR / f"{c['domain']}.json").exists()]
    print(f"  {len(companies)} companies: {cached} cached, {len(to_scrape)} to scrape")

    if to_scrape:
        sem = asyncio.Semaphore(concurrency)
        done = 0
        t0 = time.time()

        async def scrape_with_sem(c):
            nonlocal done
            async with sem:
                result = await scrape_domain(client, c["domain"])
                done += 1
                if done % 50 == 0:
                    elapsed = time.time() - t0
                    rate = done / elapsed
                    remaining = (len(to_scrape) - done) / rate if rate > 0 else 0
                    print(f"    {done}/{len(to_scrape)} scraped ({rate:.1f}/s, ~{remaining:.0f}s remaining)")
                return result

        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=concurrency * 2)) as client:
            await asyncio.gather(*[scrape_with_sem(c) for c in to_scrape])

    # Load all cache results
    results = {}
    success = error = timeout = blocked = 0
    for c in companies:
        cache_file = WEBSITE_CACHE_DIR / f"{c['domain']}.json"
        if cache_file.exists():
            entry = load_json(cache_file)
            results[c["domain"]] = entry
            s = entry.get("status", "error")
            if s == "success": success += 1
            elif s == "timeout": timeout += 1
            elif s == "blocked": blocked += 1
            else: error += 1

    total = success + error + timeout + blocked
    if total > 0:
        print(f"  Results: {success} success ({success*100//total}%), {error} error, {timeout} timeout, {blocked} blocked")
    # Self-check: success rate should be 50-90%
    self_check("Step 6", success, max(total, 1), 30, 95, "Scrape success rate")

    return results


# ── STEP 6.5: REGEXP PRE-FILTER (Improvement A) ──────────────────────────────
# Filters out parked/dead sites and obvious FSAs from website text BEFORE GPT.
# This saves ~10-15% of GPT API calls.

def step6b_prefilter(companies: list, website_cache: dict) -> tuple[list, dict]:
    """Pre-filter companies using regexp on scraped content. Returns (filtered_companies, auto_classifications)."""
    print(f"\n=== STEP 6.5: Regexp Pre-filter (before GPT) ===")

    # Load existing classifications to avoid re-filtering already classified
    existing = load_json(CLASSIFICATIONS) or {}

    passed = []
    auto_classified = {}
    parked = fsa_caught = too_short = already_done = 0

    for c in companies:
        domain = c["domain"]

        # Skip already classified
        if domain in existing:
            already_done += 1
            passed.append(c)
            continue

        cache_entry = website_cache.get(domain, {})
        content = cache_entry.get("content", "") if cache_entry.get("status") == "success" else ""

        # Check 1: Parked/dead domain
        parked_reason = is_parked_or_dead(content)
        if parked_reason:
            auto_classified[domain] = {
                "domain": domain,
                "segment": "OTHER",
                "reasoning": parked_reason,
                "tokens_used": 0,
                "classified_by": "regexp_prefilter",
                "prompt_version": "prefilter_v1",
                "classified_at": ts(),
            }
            parked += 1
            continue

        # Check 2: Full-service agency on website text (stronger than Step 4 Apollo-only check)
        if content and is_fsa_website(content) and not has_positive_signal(content):
            auto_classified[domain] = {
                "domain": domain,
                "segment": "OTHER",
                "reasoning": "Full-service agency detected from website text (SEO+PPC+web design+social media)",
                "tokens_used": 0,
                "classified_by": "regexp_prefilter",
                "prompt_version": "prefilter_v1",
                "classified_at": ts(),
            }
            fsa_caught += 1
            continue

        passed.append(c)

    print(f"  Filtered out: {parked} parked/dead, {fsa_caught} FSA websites")
    print(f"  Already classified: {already_done}")
    print(f"  Passed to GPT: {len(passed) - already_done} new + {already_done} cached = {len(passed)} total")

    # Merge auto-classifications into the cache file
    if auto_classified:
        existing.update(auto_classified)
        save_json(CLASSIFICATIONS, existing)
        print(f"  → saved {len(auto_classified)} auto-classifications (saved ~${len(auto_classified) * 0.00012:.2f} GPT cost)")

    return passed, auto_classified


# ── STEP 6.7: DEEP SCRAPE (Improvement D) ────────────────────────────────────
# For borderline companies where homepage alone is ambiguous, scrape /about, /team, /contact.

DEEP_SCRAPE_PATHS = ["/about", "/about-us", "/team", "/our-team", "/services", "/contact"]

async def deep_scrape_domain(client: httpx.AsyncClient, domain: str) -> str:
    """Scrape additional pages for borderline companies. Returns concatenated extra text."""
    extra_texts = []
    for path in DEEP_SCRAPE_PATHS:
        url = f"https://{domain}{path}"
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html",
                },
                timeout=10.0,
                follow_redirects=True,
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["nav", "footer", "script", "style", "noscript", "header", "aside"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:  # Skip if page is basically empty
                    extra_texts.append(f"[{path}] {text[:2000]}")
        except Exception:
            continue

    return "\n".join(extra_texts)


async def step6c_deep_scrape(companies: list, website_cache: dict,
                              classifications: dict, concurrency: int = 4) -> dict:
    """Deep scrape borderline companies — only those with homepage but unclear signal."""
    print(f"\n=== STEP 6.7: Deep Scrape (borderline companies) ===")

    deep_cache_file = STATE_DIR / "deep_scrape_cache.json"
    deep_cache = load_json(deep_cache_file) or {}

    # Find borderline companies: have homepage content but no positive signals AND not yet classified
    borderline = []
    for c in companies:
        domain = c["domain"]
        if domain in classifications or domain in deep_cache:
            continue
        cache_entry = website_cache.get(domain, {})
        content = cache_entry.get("content", "")
        # Borderline = has content but no clear signal from keywords AND homepage is ambiguous
        if (content and len(content) > 200
            and c.get("signal_count", 0) == 0
            and not has_positive_signal(content)):
            borderline.append(c)

    # Limit to most promising (sort by employee count in target range)
    borderline = borderline[:200]  # Cap at 200 to avoid excessive scraping

    if not borderline:
        print(f"  No borderline companies found — skipping deep scrape")
        return deep_cache

    print(f"  Found {len(borderline)} borderline companies for deep scraping")

    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def deep_scrape_with_sem(c):
        nonlocal done
        domain = c["domain"]
        if domain in deep_cache:
            return
        async with sem:
            extra = await deep_scrape_domain(client, domain)
            if extra:
                deep_cache[domain] = extra
                # Append extra text to website cache
                if domain in website_cache:
                    existing_content = website_cache[domain].get("content", "")
                    website_cache[domain]["content"] = existing_content + "\n" + extra[:3000]
                    website_cache[domain]["deep_scraped"] = True
            done += 1
            if done % 20 == 0:
                print(f"    Deep scrape: {done}/{len(borderline)} done")

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=concurrency * 2)) as client:
        await asyncio.gather(*[deep_scrape_with_sem(c) for c in borderline])

    save_json(deep_cache_file, deep_cache)
    enriched = sum(1 for v in deep_cache.values() if v)
    print(f"  Deep scrape done: {enriched}/{len(borderline)} got extra content")

    return deep_cache


# ── STEP 7: AI CLASSIFICATION ──────────────────────────────────────────────────

def _parse_classification_response(text: str) -> tuple[str, str]:
    """Parse 'SEGMENT | reasoning' from model response."""
    if "|" in text:
        segment, reasoning = text.split("|", 1)
        return segment.strip(), reasoning.strip()
    return text.strip(), ""


async def _classify_openai(client: httpx.AsyncClient, prompt: str) -> tuple[str, str, int, str]:
    """Call OpenAI GPT-4o-mini. Returns (text, model_name, tokens, error_or_empty)."""
    response = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 100, "temperature": 0},
        timeout=30.0,
    )
    if response.status_code == 200:
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return text, "gpt-4o-mini", tokens, ""
    return "", "gpt-4o-mini", 0, f"API error {response.status_code}: {response.text[:100]}"


async def _classify_anthropic(client: httpx.AsyncClient, prompt: str) -> tuple[str, str, int, str]:
    """Call Anthropic Claude (haiku-4.5 for cost parity with gpt-4o-mini). Returns (text, model_name, tokens, error_or_empty)."""
    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30.0,
    )
    if response.status_code == 200:
        data = response.json()
        text = data["content"][0]["text"].strip()
        tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
        return text, "claude-haiku-4.5", tokens, ""
    return "", "claude-haiku-4.5", 0, f"API error {response.status_code}: {response.text[:100]}"


async def classify_company(client: httpx.AsyncClient, company: dict, website_cache: dict) -> dict:
    """Classify one company. Uses OpenAI (primary) or Anthropic (fallback)."""
    domain = company["domain"]
    cache_entry = website_cache.get(domain, {})
    website_content = cache_entry.get("content", "") if cache_entry.get("status") == "success" else ""

    description = company.get("description", "") or company.get("short_description", "")

    prompt = CLASSIFICATION_PROMPT.format(
        company_name=company.get("company_name", domain),
        employees=company.get("employees", "unknown"),
        industry=company.get("industry", ""),
        keywords=company.get("keywords", "")[:200],
        description=description[:800],
        website_content=website_content[:3000],
    )

    try:
        if OPENAI_API_KEY:
            text, model_name, tokens, error = await _classify_openai(client, prompt)
        elif ANTHROPIC_API_KEY:
            text, model_name, tokens, error = await _classify_anthropic(client, prompt)
        else:
            return {
                "domain": domain, "segment": "ERROR",
                "reasoning": "No API key (OPENAI_API_KEY or ANTHROPIC_API_KEY)",
                "classified_by": "none", "prompt_version": PROMPT_VERSION, "classified_at": ts(),
            }

        if error:
            return {
                "domain": domain, "segment": "ERROR", "reasoning": error,
                "classified_by": model_name, "prompt_version": PROMPT_VERSION, "classified_at": ts(),
            }

        segment, reasoning = _parse_classification_response(text)
        return {
            "domain": domain, "segment": segment, "reasoning": reasoning,
            "tokens_used": tokens, "classified_by": model_name,
            "prompt_version": PROMPT_VERSION, "classified_at": ts(), "model": model_name,
        }

    except Exception as e:
        return {
            "domain": domain, "segment": "ERROR", "reasoning": str(e)[:100],
            "classified_by": "unknown", "prompt_version": PROMPT_VERSION, "classified_at": ts(),
        }


async def step7_classify(companies: list, website_cache: dict,
                          limit_targets: int = 0, concurrency: int = 20) -> dict:
    """Classify companies. Returns updated classifications dict."""
    print(f"\n=== STEP 7: AI Classification ===")

    # Load existing classifications
    classifications = load_json(CLASSIFICATIONS) or {}
    to_classify = [c for c in companies if c["domain"] not in classifications]

    targets_found = sum(1 for v in classifications.values()
                        if v.get("segment", "OTHER") != "OTHER" and not v.get("segment","").startswith("ERROR"))

    print(f"  {len(companies)} companies: {len(classifications)} cached, {len(to_classify)} to classify")
    print(f"  Existing targets in cache: {targets_found}")

    if limit_targets and targets_found >= limit_targets:
        print(f"  Already have {targets_found} targets >= limit {limit_targets}, skipping classification")
        return classifications

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        print("  WARN: No API key set — skipping classification")
        print("  Set OPENAI_API_KEY or ANTHROPIC_API_KEY env var to enable")
        return classifications

    provider = "OpenAI (gpt-4o-mini)" if OPENAI_API_KEY else "Anthropic (claude-haiku-4.5)"
    print(f"  Provider: {provider}")

    if not to_classify:
        print("  All companies already classified")
        return classifications

    # Sort: companies with more signals first
    to_classify.sort(key=lambda x: x.get("signal_count", 0), reverse=True)

    sem = asyncio.Semaphore(concurrency)
    done = 0
    t0 = time.time()

    async def classify_with_sem(company):
        nonlocal done, targets_found
        async with sem:
            if limit_targets and targets_found >= limit_targets:
                return
            result = await classify_company(client, company, website_cache)
            classifications[company["domain"]] = result
            done += 1
            if result["segment"] not in ("OTHER", "ERROR") and not result["segment"].startswith("ERROR"):
                targets_found += 1
                print(f"  ★ TARGET: {company['domain']} → {result['segment']} | {result['reasoning'][:80]}")

            if done % 100 == 0:
                elapsed = time.time() - t0
                save_json(CLASSIFICATIONS, classifications)
                print(f"    {done}/{len(to_classify)} classified ({elapsed:.0f}s), {targets_found} targets")

            if limit_targets and targets_found >= limit_targets:
                print(f"\n  STOP: Reached {limit_targets} targets limit")
                raise StopAsyncIteration()

    async with httpx.AsyncClient() as client:
        try:
            await asyncio.gather(*[classify_with_sem(c) for c in to_classify])
        except StopAsyncIteration:
            pass

    save_json(CLASSIFICATIONS, classifications)
    print(f"  Done: {done} classified, {targets_found} total targets")

    # Self-checks from ENRICHMENT_PIPELINE.md
    total_cls = len(classifications)
    others = sum(1 for v in classifications.values() if v.get("segment") == "OTHER")
    errors = sum(1 for v in classifications.values() if v.get("segment", "").startswith("ERROR"))
    self_check("Step 7", others, max(total_cls, 1), 50, 95, "OTHER classification rate")
    self_check("Step 7", errors, max(total_cls, 1), 0, 5, "ERROR rate")
    if targets_found == 0 and done > 100:
        print("  ⚠️  ALERT [Step 7]: 0 targets found after 100+ classifications — prompt may be too strict")

    # Estimate GPT cost
    total_tokens = sum(v.get("tokens_used", 0) for v in classifications.values())
    est_cost = total_tokens * 0.15 / 1_000_000  # gpt-4o-mini input price
    print(f"  💰 Estimated GPT cost: ~${est_cost:.2f} ({total_tokens:,} tokens)")

    return classifications


# ── STEP 7b: IMPORT EXISTING RESULTS ──────────────────────────────────────────

def import_existing_results():
    """Import pipeline_results_run*.json into classifications.json cache."""
    print("\n=== IMPORT: Loading existing pipeline results ===")

    classifications = load_json(CLASSIFICATIONS) or {}
    before = len(classifications)

    # Find all run files
    run_files = sorted(SOFIA_DIR.glob("pipeline_results_run*.json"))
    print(f"  Found {len(run_files)} run files")

    for run_file in run_files:
        data = load_json(run_file)
        if not isinstance(data, list):
            continue
        imported = 0
        for item in data:
            domain = item.get("domain", "")
            if not domain or domain in classifications:
                continue
            classifications[domain] = {
                "domain": domain,
                "segment": item.get("segment", "OTHER"),
                "reasoning": item.get("reasoning", ""),
                "tokens_used": item.get("tokens_used", 0),
                "classified_by": item.get("classified_by", "gpt-4o-mini"),
                "prompt_version": item.get("prompt_version", "legacy"),
                "classified_at": ts(),
            }
            imported += 1
        print(f"  {run_file.name}: imported {imported} new")

    save_json(CLASSIFICATIONS, classifications)
    print(f"  Total: {before} → {len(classifications)} classifications")
    return classifications


# ── STEP 8: OUTPUT ─────────────────────────────────────────────────────────────

def step8_output(companies_map: dict, classifications: dict, website_cache: dict):
    """Generate targets.json, rejects.json, pipeline_stats.json."""
    print("\n=== STEP 8: Output ===")

    targets = []
    rejects = []
    segment_counts = {}

    for domain, cls in classifications.items():
        segment = cls.get("segment", "OTHER")
        if segment.startswith("ERROR"):
            continue

        company = companies_map.get(domain, {"domain": domain})
        cache_entry = website_cache.get(domain, {})

        row = {
            "domain": domain,
            "company_name": company.get("company_name", ""),
            "segment": segment,
            "reasoning": cls.get("reasoning", ""),
            "confidence": cls.get("confidence", ""),
            "employees": company.get("employees", ""),
            "country": company.get("country", ""),
            "industry": company.get("industry", ""),
            "keywords": company.get("keywords", "")[:200],
            "short_description": company.get("short_description", "")[:300],
            "website_content_preview": (cache_entry.get("content", "") or "")[:500],
            "linkedin_url": company.get("linkedin_url", ""),
            "founded_year": company.get("founded_year", ""),
            "technologies": company.get("technologies", "")[:200],
            "source_sheet": company.get("source_sheet", ""),
            "scrape_status": cache_entry.get("status", "not_scraped"),
            "prompt_version": cls.get("prompt_version", ""),
            "classified_at": cls.get("classified_at", ""),
            "classified_by": cls.get("classified_by", ""),
            "has_positive_signal": company.get("has_positive_signal", False),
            "signal_count": company.get("signal_count", 0),
            "disqualify_reason": company.get("disqualify_reason", ""),
            "blacklisted_by": company.get("blacklisted_by", ""),
            "dns_alive": company.get("dns_alive", None),
        }

        segment_counts[segment] = segment_counts.get(segment, 0) + 1

        if segment == "OTHER":
            rejects.append(row)
        else:
            targets.append(row)

    targets.sort(key=lambda x: x.get("signal_count", 0), reverse=True)

    save_json(TARGETS_FILE, targets)
    save_json(REJECTS_FILE, rejects)

    stats = {
        "generated_at": ts(),
        "targets": len(targets),
        "rejects": len(rejects),
        "total_classified": len(targets) + len(rejects),
        "segments": segment_counts,
    }
    save_json(STATS_FILE, stats)

    print(f"\n  TARGETS: {len(targets)}")
    for seg, cnt in sorted(segment_counts.items(), key=lambda x: -x[1]):
        if seg != "OTHER":
            print(f"    {seg}: {cnt}")
    print(f"  REJECTS: {len(rejects)}")

    # ── CSV Export with naming convention ──
    # All targets combined
    all_csv = CSV_TARGETS_DIR / _csv_name("Targets", "ALL")
    save_csv(all_csv, targets)

    # Per-segment CSVs
    segments_in_targets = set(t["segment"] for t in targets)
    for seg in sorted(segments_in_targets):
        seg_rows = [t for t in targets if t["segment"] == seg]
        seg_short = seg.replace("_", "")[:8]  # INFLUENCER_PLATFORMS → INFLUENC
        seg_csv = CSV_TARGETS_DIR / _csv_name("Targets", seg)
        save_csv(seg_csv, seg_rows)

    # Rejects → Archive
    rejects_csv = CSV_ARCHIVE_DIR / _csv_name("Archive", "Rejects")
    save_csv(rejects_csv, rejects)

    print(f"\n  📁 CSVs saved to: {CSV_TARGETS_DIR}")

    return targets, rejects


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OnSocial Enrichment Pipeline (v2 — improved)")
    parser.add_argument("--step", type=int, help="Run only this step (0-8)")
    parser.add_argument("--from-step", type=int, default=0, help="Start from this step")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N targets found")
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists")
    parser.add_argument("--import-existing", action="store_true", help="Import legacy pipeline_results_run*.json")
    parser.add_argument("--concurrency-scrape", type=int, default=8)
    parser.add_argument("--concurrency-classify", type=int, default=20)
    parser.add_argument("--no-prefilter", action="store_true", help="Skip Step 6.5 regexp pre-filter")
    parser.add_argument("--no-deep-scrape", action="store_true", help="Skip Step 6.7 deep scrape")
    parser.add_argument("--no-skip-scrape", action="store_true", help="Don't skip scraping for high-signal companies")
    parser.add_argument("--validate", type=int, metavar="N", help="Show N random targets for manual review (no pipeline run)")
    parser.add_argument("--finalize-rejects", action="store_true", help="Move OTHER domains from classifications to blacklist")
    parser.add_argument("--run-name", type=str, default=None, help="Name for this run (saved in state/onsocial/runs/)")
    args = parser.parse_args()

    print(f"OnSocial Pipeline v2 | {ts()}")
    print(f"State dir: {STATE_DIR}")

    # ── Prompt Versioning: save prompt text for reproducibility ──
    prompt_file = PROMPT_VERSIONS_DIR / f"{PROMPT_VERSION}.txt"
    if not prompt_file.exists():
        prompt_file.write_text(CLASSIFICATION_PROMPT, encoding="utf-8")
        print(f"  📝 Saved prompt version: {PROMPT_VERSION} → {prompt_file.name}")
    else:
        # Check if prompt changed but version not bumped
        existing = prompt_file.read_text(encoding="utf-8")
        if existing != CLASSIFICATION_PROMPT:
            print(f"  ⚠️  WARNING: CLASSIFICATION_PROMPT changed but PROMPT_VERSION is still '{PROMPT_VERSION}'!")
            print(f"       Bump PROMPT_VERSION to avoid mixing results from different prompts.")

    # ── --validate N: show random targets for manual review, then exit ──
    if args.validate:
        import random
        classifications = load_json(CLASSIFICATIONS) or {}
        website_cache_data = {}  # lazy load
        targets_list = [
            (domain, info) for domain, info in classifications.items()
            if info.get("segment", "OTHER") not in ("OTHER", "ERROR")
            and not info.get("segment", "").startswith("ERROR")
        ]
        if not targets_list:
            print("No targets found in classifications.json")
            sys.exit(0)
        n = min(args.validate, len(targets_list))
        sample = random.sample(targets_list, n)
        print(f"\n{'='*80}")
        print(f"VALIDATION: {n} random targets (out of {len(targets_list)} total)")
        print(f"{'='*80}")
        for i, (domain, info) in enumerate(sample, 1):
            cache_file = WEBSITE_CACHE_DIR / f"{domain}.json"
            if cache_file.exists():
                wc = load_json(cache_file)
                preview = (wc.get("content", "") or "")[:300]
            else:
                preview = "(no cached content)"
            print(f"\n── [{i}/{n}] {domain} ──")
            print(f"  Segment:   {info.get('segment')}")
            print(f"  Reasoning: {info.get('reasoning', '')[:120]}")
            print(f"  Prompt:    {info.get('prompt_version', '?')}")
            print(f"  By:        {info.get('classified_by', '?')}")
            print(f"  Website:   {preview}")
            print(f"  Check:     https://{domain}")
        print(f"\n{'='*80}")
        print(f"Review each domain: open the URL, compare with segment/reasoning.")
        print(f"If accuracy < 90% → revise prompt and re-run classification.")
        sys.exit(0)

    # ── --finalize-rejects: move OTHER domains to blacklist ──
    if args.finalize_rejects:
        classifications = load_json(CLASSIFICATIONS) or {}
        blacklist = load_json(BLACKLIST_FILE)
        if not blacklist:
            print("ERROR: blacklist not found. Run step 0 first.")
            sys.exit(1)
        bl_set = set(blacklist.get("domains", []))
        others = [d for d, info in classifications.items()
                  if info.get("segment") == "OTHER" and d not in bl_set]
        if not others:
            print("No new OTHER domains to add to blacklist.")
            sys.exit(0)
        bl_set.update(others)
        blacklist["domains"] = sorted(bl_set)
        blacklist["count"] = len(bl_set)
        blacklist["finalized_at"] = ts()
        blacklist["finalized_others"] = len(others)
        save_json(BLACKLIST_FILE, blacklist)
        print(f"✅ Added {len(others)} OTHER domains to blacklist (total: {len(bl_set)})")
        sys.exit(0)

    # Import existing results first if requested
    if args.import_existing:
        import_existing_results()
        if args.step is None and args.from_step == 0:
            return

    run_step = args.step
    from_step = args.from_step if run_step is None else run_step

    def should_run(n):
        if run_step is not None:
            return n == run_step
        return n >= from_step

    # Step 0
    blacklist = step0_blacklist(force=args.force) if should_run(0) else load_json(BLACKLIST_FILE)
    if blacklist is None:
        print("ERROR: blacklist not found. Run step 0 first.")
        sys.exit(1)

    # Step 1
    if should_run(1):
        companies = step1_load(force=args.force)
    elif ALL_COMPANIES.exists():
        companies = load_json(ALL_COMPANIES)
        print(f"\n[Step 1] Loaded {len(companies)} companies from cache")
    else:
        print("ERROR: all_companies.json not found. Run step 1 first.")
        sys.exit(1)

    # Step 2 (dedup)
    if should_run(2):
        companies = step2_dedup(companies, force=args.force)

    # Step 3 (blacklist filter)
    if should_run(3):
        if not AFTER_BLACKLIST.exists() or args.force:
            # Need deduped companies
            if len(companies) > 27000 and not args.force:
                companies = step2_dedup(companies, force=False)
            companies = step3_blacklist_filter(companies, blacklist, force=args.force)
        else:
            companies = load_json(AFTER_BLACKLIST)
            print(f"\n[Step 3] Loaded {len(companies)} after-blacklist companies from cache")
    elif AFTER_BLACKLIST.exists():
        companies = load_json(AFTER_BLACKLIST)
        print(f"\n[Step 3] Loaded {len(companies)} after-blacklist companies from cache")

    # Step 4 (deterministic filter)
    if should_run(4):
        priority, normal, disq = step4_filter(companies, force=args.force)
    elif PRIORITY_FILE.exists():
        priority = load_json(PRIORITY_FILE)
        normal = load_json(NORMAL_FILE)
        disq = load_json(DISQUALIFIED)
        print(f"\n[Step 4] Loaded: {len(priority)} priority, {len(normal)} normal, {len(disq)} disqualified")
    else:
        print("ERROR: priority.json not found. Run step 4 first.")
        sys.exit(1)

    # Build companies map for output
    companies_map = {c["domain"]: c for c in priority + normal + (disq or [])}

    # Process priority + normal combined for steps 5-7
    process_queue = priority + normal

    # Step 5 (DNS)
    if should_run(5):
        process_queue = step5_dns(process_queue, force=args.force)

    # ── IMPROVEMENT B: Skip scraping for companies with strong Apollo signals ──
    skip_scraped = []
    if should_run(6) and not args.no_skip_scrape:
        scrape_queue = []
        for c in process_queue:
            if can_skip_scraping(c):
                skip_scraped.append(c)
            else:
                scrape_queue.append(c)
        if skip_scraped:
            print(f"\n  [Skip-scrape] {len(skip_scraped)} companies have 3+ signals + Apollo description → classify without scraping")
    else:
        scrape_queue = process_queue

    # Step 6 (scraping)
    if should_run(6):
        website_cache = asyncio.run(step6_scrape(scrape_queue, args.concurrency_scrape))
    else:
        # Load all cached results
        website_cache = {}
        for c in process_queue:
            cache_file = WEBSITE_CACHE_DIR / f"{c['domain']}.json"
            if cache_file.exists():
                website_cache[c["domain"]] = load_json(cache_file)
        print(f"\n[Step 6] Loaded {len(website_cache)} cached scrape results")

    # ── IMPROVEMENT A: Step 6.5 — Regexp pre-filter before GPT ────────────────
    if should_run(7) and not args.no_prefilter:
        process_queue, auto_cls = step6b_prefilter(process_queue, website_cache)

    # ── IMPROVEMENT D: Step 6.7 — Deep scrape borderline companies ────────────
    if should_run(6) and not args.no_deep_scrape:
        classifications_so_far = load_json(CLASSIFICATIONS) or {}
        asyncio.run(step6c_deep_scrape(
            process_queue, website_cache, classifications_so_far,
            concurrency=min(args.concurrency_scrape, 4),
        ))

    # Step 7 (classification)
    if should_run(7):
        classifications = asyncio.run(step7_classify(
            process_queue, website_cache,
            limit_targets=args.limit,
            concurrency=args.concurrency_classify,
        ))
    else:
        classifications = load_json(CLASSIFICATIONS) or {}
        print(f"\n[Step 7] Loaded {len(classifications)} cached classifications")

    # Step 8 (output)
    if should_run(8):
        targets, rejects = step8_output(companies_map, classifications, website_cache)
        print(f"\nDone. {len(targets)} targets → {TARGETS_FILE.name}")
    else:
        # Still show current stats
        targets = [v for v in classifications.values()
                   if v.get("segment", "OTHER") not in ("OTHER", "ERROR")]
        rejects = []
        print(f"\nCurrent targets in cache: {len(targets)}")

    # ── Run Protocol: save run metadata ──
    runs_dir = STATE_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_name = args.run_name
    if not run_name:
        existing_runs = sorted(runs_dir.glob("run_*.json"))
        run_num = len(existing_runs) + 1
        run_name = f"run_{run_num:03d}"
    run_meta = {
        "run_name": run_name,
        "started_at": ts(),
        "prompt_version": PROMPT_VERSION,
        "provider": "openai" if OPENAI_API_KEY else ("anthropic" if ANTHROPIC_API_KEY else "none"),
        "args": {
            "step": args.step, "from_step": args.from_step, "limit": args.limit,
            "force": args.force, "no_prefilter": args.no_prefilter,
            "no_deep_scrape": args.no_deep_scrape, "no_skip_scrape": args.no_skip_scrape,
        },
        "results": {
            "targets": len(targets) if isinstance(targets, list) else 0,
            "rejects": len(rejects) if isinstance(rejects, list) else 0,
            "total_classifications": len(classifications),
        },
    }
    run_file = runs_dir / f"{run_name}.json"
    save_json(run_file, run_meta)
    print(f"\n📋 Run saved: {run_file.name}")
    print(f"   Next step: python pipeline_onsocial.py --validate 20")


if __name__ == "__main__":
    main()
