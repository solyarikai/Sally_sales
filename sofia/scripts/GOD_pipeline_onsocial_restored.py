#!/usr/bin/env python3
"""
OnSocial Enrichment & Segmentation Pipeline — серверная версия (Hetzner)

Что делает:
  Берёт CSV с компаниями (Apollo, Clay экспорты) и классифицирует каждую
  компанию по сегментам ICP: INFLUENCER_PLATFORMS, IM_FIRST_AGENCIES,
  AFFILIATE_PERFORMANCE или OTHER. На выходе — targets.json с готовыми
  компаниями для аутрича и Google Sheets с результатами.

Шаги:
  0. Load Blacklist   — читает список доменов которые не нужно таргетить
  1. Load & Normalize — загружает CSV, нормализует домены
  2. Deduplicate      — убирает дубли по домену внутри одного прогона
  3. Blacklist Filter  — убирает домены из blacklist (уже в кампаниях/клиенты)
  4. Deterministic Filter — отсеивает по размеру, индустрии, FSA паттернам
  5. DNS Pre-check    — проверяет что домены живые
  6. Website Scraping — скрапит homepage для контекста
  6.5 Regexp Pre-filter — фильтрует парковочные домены и FSA до GPT
  6.7 Deep Scrape     — дополнительные страницы для пограничных компаний
  7. AI Classification — GPT-4o-mini классифицирует по сегментам ICP
  8. Output           — targets.json, rejects.json, CSV, Google Sheets

Два механизма защиты от повторной обработки:
  - Blacklist (campaign_blacklist.json) — домены в аутриче, клиенты, баны.
    Пополняется через findymail_to_smartlead.py после заливки лидов.
  - Dedup cache (classifications.json) — все классифицированные домены.
    Step 7 пропускает домены которые уже в кеше. Это защита между прогонами.

Usage:
  python pipeline_onsocial.py                      # все шаги (input CSV из state/input/)
  python pipeline_onsocial.py --from-step 6        # с шага 6
  python pipeline_onsocial.py --step 4             # только шаг 4
  python pipeline_onsocial.py --limit 20           # стоп после 20 таргетов
  python pipeline_onsocial.py --force              # пересчитать даже если есть кеш
  python pipeline_onsocial.py --validate 20        # показать 20 случайных таргетов для ревью

Requires: httpx, beautifulsoup4
Optional: OPENAI_API_KEY (GPT-4o-mini) или ANTHROPIC_API_KEY (Claude Haiku 4.5)
"""

import argparse
import asyncio
import csv
import json
import os
import re
import socket
import subprocess  # used by filter_existing_contacts
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Для доступа к google_sheets_service внутри Docker на Hetzner
sys.path.insert(0, str(Path(os.environ.get("REPO_DIR", "/app"))))

# ── PATHS ──────────────────────────────────────────────────────────────────────
# На Hetzner: REPO_DIR=/app, state хранится между запусками.
# Локально: auto-detect от расположения скрипта.
REPO_DIR = Path(os.environ.get("REPO_DIR", str(Path(__file__).parent.parent.parent)))
STATE_DIR = Path(
    os.environ.get("ONSOCIAL_STATE_DIR", str(REPO_DIR / "state" / "onsocial"))
)
INPUT_DIR = STATE_DIR / "input"  # сюда Claude заливает CSV через scp

# Общий кеш скрапинга между проектами (OnSocial, ArchiStruct и др.)
# Один домен скрапится один раз — переиспользуется везде.
SHARED_CACHE_DIR = REPO_DIR / "state" / "shared"
WEBSITE_CACHE_DIR = SHARED_CACHE_DIR / "website_cache"

# Версионирование промптов — для воспроизводимости результатов
PROMPT_VERSIONS_DIR = STATE_DIR / "prompt_versions"

for _d in [
    STATE_DIR,
    INPUT_DIR,
    SHARED_CACHE_DIR,
    WEBSITE_CACHE_DIR,
    PROMPT_VERSIONS_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)

# ── STATE FILES ───────────────────────────────────────────────────────────────
# Все state файлы живут в state/onsocial/ и сохраняются между запусками.
# Каждый шаг проверяет наличие своего файла — если есть, пропускает (кеш).
# --force пересчитывает всё с нуля.
BLACKLIST_FILE = STATE_DIR / "campaign_blacklist.json"  # домены в аутриче + клиенты
ALL_COMPANIES = STATE_DIR / "all_companies.json"  # Step 1: все загруженные компании
AFTER_BLACKLIST = STATE_DIR / "after_blacklist.json"  # Step 3: после blacklist фильтра
PRIORITY_FILE = (
    STATE_DIR / "priority.json"
)  # Step 4: компании с положительными сигналами
NORMAL_FILE = STATE_DIR / "normal.json"  # Step 4: компании без сигналов
DISQUALIFIED = (
    STATE_DIR / "disqualified.json"
)  # Step 4: отсеянные (размер, индустрия, FSA)
CLASSIFICATIONS = (
    STATE_DIR / "classifications.json"
)  # Step 7: DEDUP CACHE — все классифицированные
TARGETS_FILE = STATE_DIR / "targets.json"  # Step 8: финальные таргеты для аутрича
REJECTS_FILE = STATE_DIR / "rejects.json"  # Step 8: OTHER — не наш ICP
STATS_FILE = STATE_DIR / "pipeline_stats.json"  # Step 8: статистика прогона

# ── SHEET FILES ───────────────────────────────────────────────────────────────
# Входные данные: CSV из Apollo/Clay, загруженные через scp в INPUT_DIR.
# Также поддерживает legacy формат sheet_*.json (headers + rows).
SHEET_FILES = {
    "us": INPUT_DIR / "sheet_us.json",
    "uk_eu": INPUT_DIR / "sheet_uk_eu.json",
    "latam": INPUT_DIR / "sheet_latam.json",
    "india": INPUT_DIR / "sheet_india.json",
    "mixed": INPUT_DIR / "sheet_mixed.json",
}

# ── CSV EXPORT ────────────────────────────────────────────────────────────────
# Naming convention: [PROJECT] | [TYPE] | [SEGMENT] — [DATE]
# На сервере CSV сохраняется как backup; основной результат → Google Sheets.
PROJECT_CODE = "OS"
CSV_OUTPUT_DIR = STATE_DIR / "output"
CSV_TARGETS_DIR = CSV_OUTPUT_DIR / "Targets"
CSV_ARCHIVE_DIR = CSV_OUTPUT_DIR / "Archive"

for _d in [CSV_OUTPUT_DIR, CSV_TARGETS_DIR, CSV_ARCHIVE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


def _date_tag() -> str:
    """Короткая метка даты для именования файлов, например 'Mar 24'."""
    return datetime.now().strftime("%b %d")


def _csv_name(type_: str, segment: str = "", suffix: str = "") -> str:
    """Стандартизированное имя CSV. Пример: 'OS | Targets | INFPLAT — Mar 24.csv'"""
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
    """Сохраняет list of dicts в CSV."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → saved CSV: {path.name} ({len(rows)} rows)")


# ── AI CONFIG ─────────────────────────────────────────────────────────────────
# Версия промпта — при изменении промпта нужно увеличить версию,
# иначе старые и новые классификации смешаются в кеше.
PROMPT_VERSION = "v1"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # основной: GPT-4o-mini
ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY", ""
)  # fallback: Claude Haiku 4.5

# ── API KEYS (Steps 9-11) ────────────────────────────────────────────────────
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")  # Step 9: People Search
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")  # Step 10: Email enrichment
SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")  # Step 11: Campaign upload

APOLLO_BASE = "https://api.apollo.io/api/v1"
FINDYMAIL_BASE = "https://app.findymail.com"
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

# State files for Steps 9-11
CONTACTS_FILE = STATE_DIR / "contacts.json"  # Step 9: найденные контакты
ENRICHED_FILE = STATE_DIR / "enriched_contacts.json"  # Step 10: контакты с email

# SmartLead email accounts (OnSocial #C persona set)
DEFAULT_EMAIL_ACCOUNTS = [
    2718958,
    2718959,
    2718960,
    2718961,
    2718962,
    2718963,
    2718964,
    2718965,
    2718966,
    2718967,
    2718968,
    2718969,
    2718970,
    2718971,
]

MAX_CONTACTS_PER_COMPANY = 3
DEFAULT_TITLES = [
    "CEO",
    "CTO",
    "CMO",
    "COO",
    "Founder",
    "Co-Founder",
    "VP Marketing",
    "VP Partnerships",
    "VP Growth",
    "VP Sales",
    "Head of Marketing",
    "Head of Partnerships",
    "Head of Growth",
    "Director of Marketing",
    "Director of Partnerships",
]
DEFAULT_SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]

# ── FILTER CONSTANTS ──────────────────────────────────────────────────────────

# Положительные сигналы — если слово есть в keywords/description,
# компания попадает в priority queue (обрабатывается первой).
POSITIVE_KEYWORDS = [
    "influencer",
    "creator",
    "ugc",
    "affiliate",
    "social media marketing",
    "talent management",
    "content creator",
    "brand ambassador",
    "influencer marketing",
    "creator economy",
    "mcn",
    "creator marketplace",
    "influencer analytics",
    "influencer platform",
    "creator monetization",
    "social commerce",
    "live shopping",
    "influencer agency",
    "creator campaigns",
    "affiliate network",
    "performance marketing",
    "cpa network",
]

# Индустрии-дисквалификаторы — компании из этих индустрий отсеиваются в Step 4.
# Исключение: если у компании есть положительный сигнал (influencer + staffing = ок).
DISQUALIFY_INDUSTRIES = [
    "staffing",
    "recruitment",
    "real estate",
    "construction",
    "mining",
    "oil & gas",
    "legal services",
    "law firm",
    "accounting",
    "banking",
    "government",
    "military",
    "defense",
    "utilities",
    "agriculture",
    "farming",
    "food production",
    "insurance",
    "logistics",
    "shipping",
    "transportation",
    "civil engineering",
    "pharmaceuticals",
    "veterinary",
    "dairy",
    "fishery",
    "forestry",
    "ranching",
]

# FSA (Full-Service Agency) паттерны — агентства которые делают всё
# (SEO + PPC + web design + social media). Не наш ICP — нужны агентства
# где influencer marketing = основной бизнес, а не одна из 8 услуг.
FSA_PATTERNS = [
    r"\bseo\b.*\bppc\b",
    r"\bppc\b.*\bseo\b",
    r"\bseo\b.*\bweb design\b",
    r"\bfull.?service\b.*\bagency\b",
    r"\bdigital marketing agency\b.*\bseo\b",
    r"\bpr agency\b",
    r"\bpublic relations\b.*\bagency\b",
]

# Паттерны парковочных/мёртвых доменов — проверяются ПОСЛЕ скрапинга,
# ДО GPT. Экономит ~10-15% вызовов GPT.
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

# FSA паттерны на уровне сайта — сильнее чем проверка Apollo-данных в Step 4.
# Если на сайте упоминается SEO+PPC+web design вместе → full-service agency → OTHER.
FSA_WEBSITE_PATTERNS = [
    r"\bseo\b.*\bppc\b.*\b(web design|social media)\b",
    r"\bfull.?service\b.*\b(digital|marketing|creative)\b.*\bagency\b",
    r"\b(seo|ppc|web design|email marketing|social media)\b.*\b(seo|ppc|web design|email marketing|social media)\b.*\b(seo|ppc|web design|email marketing)\b",
]

# Порог для пропуска скрапинга — если у компании 3+ положительных сигнала
# и описание длиннее 100 символов, можно классифицировать без скрапинга сайта.
# Экономит время на компаниях где и так всё понятно.
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
- If website_content is present, ALWAYS use it for classification
  even if other fields (employees, industry, keywords) are empty.
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
    print(
        f"  → saved {path.name} ({len(data) if isinstance(data, (list, dict)) else ''})"
    )


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


def self_check(
    step_name: str,
    value: int,
    total: int,
    expected_min_pct: float,
    expected_max_pct: float,
    metric_name: str,
):
    """Print warning if metric is outside expected range."""
    if total == 0:
        return
    pct = value * 100 / total
    if pct < expected_min_pct:
        print(
            f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — below expected {expected_min_pct}%"
        )
        print(f"       ({value}/{total}). Check pipeline logic or input data.")
    elif pct > expected_max_pct:
        print(
            f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — above expected {expected_max_pct}%"
        )
        print(f"       ({value}/{total}). Check if filters are too broad/narrow.")


# ── STEP 0: LOAD BLACKLIST ─────────────────────────────────────────────────────
# Загружает существующий campaign_blacklist.json. НЕ формирует — только читает.
# Если файла нет — pipeline останавливается (нужно создать начальный blacklist).
#
# Blacklist = домены которые НЕ НУЖНО ТАРГЕТИТЬ (бизнес-логика):
#   - Домены компаний уже в SmartLead кампаниях (аутрич идёт)
#   - Платные клиенты OnSocial (191 домен — не продаём клиентам)
#   - Конкуренты, ручные баны
#
# Кто пополняет blacklist:
#   findymail_to_smartlead.py → sync_blacklist() — после каждой заливки лидов.
#
# Blacklist ≠ dedup. Dedup делает classifications.json кеш в Step 7.


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
# Загружает компании из sheet_*.json (экспорты Apollo, Clay и других источников).
# Нормализует домены, обрезает длинные поля.
# Результат кешируется в all_companies.json — при повторном запуске не перечитывает.


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

        ci_name = col(["Company Name"])
        ci_emp = col(["# Employees"])
        ci_industry = col(["Industry"])
        ci_website = col(["Website"])
        ci_linkedin = col(["Company Linkedin Url"])
        ci_country = col(["Company Country"])
        ci_keywords = col(["Keywords"])
        ci_short = col(["Short Description"])
        ci_desc = col(["Description"])
        ci_tech = col(["Technologies"])
        ci_founded = col(["Founded Year"])

        def get(row, idx):
            if idx < 0 or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] else ""

        for row in rows:
            website = get(row, ci_website)
            domain = norm_domain(website)
            if not domain:
                continue

            companies.append(
                {
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
                }
            )

        print(f"  {sheet_key}: {len(rows)} rows → loaded")

    print(f"  Total loaded: {len(companies)}")
    # Self-check: expect 20,000-100,000 companies from Apollo
    if len(companies) < 5000:
        print(
            f"  ⚠️  ALERT [Step 1]: Only {len(companies)} companies loaded — expected 20,000+. Check input files."
        )
    elif len(companies) < 20000:
        print(
            f"  ℹ️  NOTE [Step 1]: {len(companies)} companies loaded — slightly below typical 20,000+"
        )
    save_json(ALL_COMPANIES, companies)
    return companies


# ── STEP 2: DEDUPLICATE ────────────────────────────────────────────────────────
# Удаляет дубли по домену внутри одного прогона (один CSV может содержать
# одну компанию несколько раз из разных источников/фильтров).
# Это dedup на уровне ВХОДНЫХ ДАННЫХ, не путать с classifications cache
# который предотвращает повторную КЛАССИФИКАЦИЮ между прогонами.


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
# Убирает компании, домены которых уже в blacklist (= уже в аутриче или клиенты).
# Это БИЗНЕС-фильтр: "не таргетить тех, кого уже таргетим".
# Ожидаемый процент отсева: 1-15%.


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
        print(
            "  ⚠️  ALERT [Step 3]: 0 removed — check domain normalization (www, trailing /)"
        )
    # Self-check: blacklist should remove 1-10%
    self_check("Step 3", removed, len(companies), 0.5, 15, "Blacklist removal rate")
    save_json(AFTER_BLACKLIST, passed)
    return passed


# ── STEP 4: DETERMINISTIC FILTER ──────────────────────────────────────────────
# Бесплатная фильтрация БЕЗ AI по правилам:
#   - Размер: <5 или >5000 сотрудников → disqualified
#   - Индустрия: staffing, construction, mining и т.д. → disqualified
#   - FSA (full-service agency): SEO+PPC+web design → disqualified
#   - Положительные сигналы (influencer, creator, affiliate) → priority queue
# Разделяет на три очереди: priority (есть сигналы), normal (нет сигналов), disqualified.
# Priority обрабатывается первым — экономит время на лучших кандидатах.


def step4_filter(companies: list, force: bool = False):
    print("\n=== STEP 4: Deterministic Filter ===")

    if (
        PRIORITY_FILE.exists()
        and NORMAL_FILE.exists()
        and DISQUALIFIED.exists()
        and not force
    ):
        priority = load_json(PRIORITY_FILE)
        normal = load_json(NORMAL_FILE)
        disq = load_json(DISQUALIFIED)
        print(
            f"  already exists: {len(priority)} priority, {len(normal)} normal, {len(disq)} disqualified (skip)"
        )
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
            combined_text = f"{c.get('keywords', '')} {c.get('short_description', '')} {c.get('description', '')}".lower()
            if is_fsa(combined_text) and not has_positive_signal(combined_text):
                disq_reason = "Full-service agency (FSA filter)"

        if disq_reason:
            c["disqualify_reason"] = disq_reason
            disq_list.append(c)
        else:
            # 4d. Positive signal detection → priority queue
            signal_text = f"{c.get('keywords', '')} {c.get('short_description', '')} {c.get('description', '')}"
            n_signals = count_positive_signals(
                c.get("keywords", ""),
                c.get("short_description", "") + " " + c.get("description", ""),
            )
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
    print(
        f"  Total:                       {len(priority) + len(normal) + len(disq_list)}"
    )

    # Self-checks from ENRICHMENT_PIPELINE.md best practices
    total_processed = len(priority) + len(normal) + len(disq_list)
    self_check("Step 4", len(priority), total_processed, 5, 25, "Priority queue %")
    self_check("Step 4", len(disq_list), total_processed, 2, 30, "Disqualified %")
    if len(normal) == 0 and len(priority) == 0:
        print(
            "  ⚠️  ALERT [Step 4]: No companies passed filtering! Check input data or relax filters."
        )

    save_json(PRIORITY_FILE, priority)
    save_json(NORMAL_FILE, normal)
    save_json(DISQUALIFIED, disq_list)
    return priority, normal, disq_list


# ── STEP 5: DNS PRE-CHECK ──────────────────────────────────────────────────────
# Быстрая проверка: домен вообще существует? Если DNS не резолвится —
# нет смысла скрапить и классифицировать. Экономит время на мёртвых доменах.
# Результаты кешируются в dns_cache.json.


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
    print(
        f"  {len(companies)} domains → {len(alive)} alive, {len(dead)} dead ({new_checks} new checks)"
    )
    return alive


# ── STEP 6: WEBSITE SCRAPING ───────────────────────────────────────────────────
# Скрапит homepage каждой компании. Извлекает текст (без nav/footer/script).
# Ограничение: 5000 символов на домен. Кешируется по файлам в website_cache/.
# Кеш общий между проектами (OnSocial, ArchiStruct) — один скрап на домен.
# Стоимость: $0 (httpx запросы). Согласование не требуется.


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
        response = await client.get(
            url, headers=headers, timeout=15.0, follow_redirects=True
        )
        result["status_code"] = response.status_code

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove noise tags
            for tag in soup(
                ["nav", "footer", "script", "style", "noscript", "header", "aside"]
            ):
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
    cached = sum(
        1 for c in companies if (WEBSITE_CACHE_DIR / f"{c['domain']}.json").exists()
    )
    to_scrape = [
        c for c in companies if not (WEBSITE_CACHE_DIR / f"{c['domain']}.json").exists()
    ]
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
                    print(
                        f"    {done}/{len(to_scrape)} scraped ({rate:.1f}/s, ~{remaining:.0f}s remaining)"
                    )
                return result

        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=concurrency * 2)
        ) as client:
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
            if s == "success":
                success += 1
            elif s == "timeout":
                timeout += 1
            elif s == "blocked":
                blocked += 1
            else:
                error += 1

    total = success + error + timeout + blocked
    if total > 0:
        print(
            f"  Results: {success} success ({success * 100 // total}%), {error} error, {timeout} timeout, {blocked} blocked"
        )
    # Self-check: success rate should be 50-90%
    self_check("Step 6", success, max(total, 1), 30, 95, "Scrape success rate")

    return results


# ── STEP 6.5: REGEXP PRE-FILTER (Improvement A) ──────────────────────────────
# Фильтрует ПЕРЕД GPT с помощью regexp:
#   - Парковочные/мёртвые домены ("domain is for sale", "godaddy", "coming soon")
#   - FSA на уровне сайта (SEO+PPC+web design в тексте)
# Экономит ~10-15% вызовов GPT. Результаты сохраняются в classifications.json
# как "classified_by: regexp_prefilter" — не пересчитываются при повторном запуске.


def step6b_prefilter(companies: list, website_cache: dict) -> tuple[list, dict]:
    """Pre-filter companies using regexp on scraped content. Returns (filtered_companies, auto_classifications)."""
    print("\n=== STEP 6.5: Regexp Pre-filter (before GPT) ===")

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
        content = (
            cache_entry.get("content", "")
            if cache_entry.get("status") == "success"
            else ""
        )

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
    print(
        f"  Passed to GPT: {len(passed) - already_done} new + {already_done} cached = {len(passed)} total"
    )

    # Merge auto-classifications into the cache file
    if auto_classified:
        existing.update(auto_classified)
        save_json(CLASSIFICATIONS, existing)
        print(
            f"  → saved {len(auto_classified)} auto-classifications (saved ~${len(auto_classified) * 0.00012:.2f} GPT cost)"
        )

    return passed, auto_classified


# ── STEP 6.7: DEEP SCRAPE (Improvement D) ────────────────────────────────────
# Для пограничных компаний (homepage есть, но сигналов нет) — скрапим
# дополнительные страницы: /about, /team, /services, /contact.
# Даёт GPT больше контекста для точной классификации.
# Лимит: 200 компаний за раз, concurrency=4 (щадящий режим).

DEEP_SCRAPE_PATHS = [
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/services",
    "/contact",
]


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
                for tag in soup(
                    ["nav", "footer", "script", "style", "noscript", "header", "aside"]
                ):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:  # Skip if page is basically empty
                    extra_texts.append(f"[{path}] {text[:2000]}")
        except Exception:
            continue

    return "\n".join(extra_texts)


async def step6c_deep_scrape(
    companies: list, website_cache: dict, classifications: dict, concurrency: int = 4
) -> dict:
    """Deep scrape borderline companies — only those with homepage but unclear signal."""
    print("\n=== STEP 6.7: Deep Scrape (borderline companies) ===")

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
        if (
            content
            and len(content) > 200
            and c.get("signal_count", 0) == 0
            and not has_positive_signal(content)
        ):
            borderline.append(c)

    # Limit to most promising (sort by employee count in target range)
    borderline = borderline[:200]  # Cap at 200 to avoid excessive scraping

    if not borderline:
        print("  No borderline companies found — skipping deep scrape")
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
                    website_cache[domain]["content"] = (
                        existing_content + "\n" + extra[:3000]
                    )
                    website_cache[domain]["deep_scraped"] = True
            done += 1
            if done % 20 == 0:
                print(f"    Deep scrape: {done}/{len(borderline)} done")

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=concurrency * 2)
    ) as client:
        await asyncio.gather(*[deep_scrape_with_sem(c) for c in borderline])

    save_json(deep_cache_file, deep_cache)
    enriched = sum(1 for v in deep_cache.values() if v)
    print(f"  Deep scrape done: {enriched}/{len(borderline)} got extra content")

    return deep_cache


# ── STEP 7: AI CLASSIFICATION ──────────────────────────────────────────────────
# GPT-4o-mini (основной) или Claude Haiku 4.5 (fallback) классифицируют компании
# по сегментам: INFLUENCER_PLATFORMS, AFFILIATE_PERFORMANCE, IM_FIRST_AGENCIES, OTHER.
#
# Стоимость: ~$0.00012 за компанию (gpt-4o-mini).
# Результаты кешируются в classifications.json — это и есть DEDUP CACHE.
# При повторном запуске уже классифицированные домены ПРОПУСКАЮТСЯ.
# Это главный механизм защиты от повторной обработки между прогонами.

VALID_SEGMENTS = {
    "INFLUENCER_PLATFORMS",
    "AFFILIATE_PERFORMANCE",
    "IM_FIRST_AGENCIES",
    "OTHER",
}


def _parse_classification_response(text: str) -> tuple[str, str]:
    """Parse 'SEGMENT | reasoning' from model response.
    Validates segment against known values; falls back to OTHER if GPT
    returned garbage (e.g. 'Please provide details...')."""
    if "|" in text:
        segment, reasoning = text.split("|", 1)
        segment = segment.strip()
        if segment in VALID_SEGMENTS:
            return segment, reasoning.strip()
    # Try to find a valid segment anywhere in the response
    for seg in VALID_SEGMENTS - {"OTHER"}:
        if seg in text:
            return seg, text[:200]
    return "OTHER", text[:200]


async def _classify_openai(
    client: httpx.AsyncClient, prompt: str
) -> tuple[str, str, int, str]:
    """Call OpenAI GPT-4o-mini. Returns (text, model_name, tokens, error_or_empty)."""
    response = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0,
        },
        timeout=30.0,
    )
    if response.status_code == 200:
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return text, "gpt-4o-mini", tokens, ""
    return (
        "",
        "gpt-4o-mini",
        0,
        f"API error {response.status_code}: {response.text[:100]}",
    )


async def _classify_anthropic(
    client: httpx.AsyncClient, prompt: str
) -> tuple[str, str, int, str]:
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
        tokens = data.get("usage", {}).get("input_tokens", 0) + data.get(
            "usage", {}
        ).get("output_tokens", 0)
        return text, "claude-haiku-4.5", tokens, ""
    return (
        "",
        "claude-haiku-4.5",
        0,
        f"API error {response.status_code}: {response.text[:100]}",
    )


async def classify_company(
    client: httpx.AsyncClient, company: dict, website_cache: dict
) -> dict:
    """Classify one company. Uses OpenAI (primary) or Anthropic (fallback)."""
    domain = company["domain"]
    cache_entry = website_cache.get(domain, {})
    website_content = (
        cache_entry.get("content", "") if cache_entry.get("status") == "success" else ""
    )

    description = company.get("description", "") or company.get("short_description", "")

    # Fill empty fields with explicit markers so GPT doesn't trigger "no data"
    employees = company.get("employees", "") or "unknown"
    industry = company.get("industry", "") or "not specified"
    keywords = company.get("keywords", "")[:200] or "not specified"
    desc = description[:800] or (
        "see website content below" if website_content else "none"
    )

    prompt = CLASSIFICATION_PROMPT.format(
        company_name=company.get("company_name", domain),
        employees=employees,
        industry=industry,
        keywords=keywords,
        description=desc,
        website_content=website_content[:3000],
    )

    try:
        if OPENAI_API_KEY:
            text, model_name, tokens, error = await _classify_openai(client, prompt)
        elif ANTHROPIC_API_KEY:
            text, model_name, tokens, error = await _classify_anthropic(client, prompt)
        else:
            return {
                "domain": domain,
                "segment": "ERROR",
                "reasoning": "No API key (OPENAI_API_KEY or ANTHROPIC_API_KEY)",
                "classified_by": "none",
                "prompt_version": PROMPT_VERSION,
                "classified_at": ts(),
            }

        if error:
            return {
                "domain": domain,
                "segment": "ERROR",
                "reasoning": error,
                "classified_by": model_name,
                "prompt_version": PROMPT_VERSION,
                "classified_at": ts(),
            }

        segment, reasoning = _parse_classification_response(text)
        return {
            "domain": domain,
            "segment": segment,
            "reasoning": reasoning,
            "tokens_used": tokens,
            "classified_by": model_name,
            "prompt_version": PROMPT_VERSION,
            "classified_at": ts(),
            "model": model_name,
        }

    except Exception as e:
        return {
            "domain": domain,
            "segment": "ERROR",
            "reasoning": str(e)[:100],
            "classified_by": "unknown",
            "prompt_version": PROMPT_VERSION,
            "classified_at": ts(),
        }


async def step7_classify(
    companies: list, website_cache: dict, limit_targets: int = 0, concurrency: int = 20
) -> dict:
    """Classify companies. Returns updated classifications dict."""
    print("\n=== STEP 7: AI Classification ===")

    # Load existing classifications
    classifications = load_json(CLASSIFICATIONS) or {}
    to_classify = [c for c in companies if c["domain"] not in classifications]

    targets_found = sum(
        1
        for v in classifications.values()
        if v.get("segment", "OTHER") != "OTHER"
        and not v.get("segment", "").startswith("ERROR")
    )

    print(
        f"  {len(companies)} companies: {len(classifications)} cached, {len(to_classify)} to classify"
    )
    print(f"  Existing targets in cache: {targets_found}")

    if limit_targets and targets_found >= limit_targets:
        print(
            f"  Already have {targets_found} targets >= limit {limit_targets}, skipping classification"
        )
        return classifications

    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        print("  WARN: No API key set — skipping classification")
        print("  Set OPENAI_API_KEY or ANTHROPIC_API_KEY env var to enable")
        return classifications

    provider = (
        "OpenAI (gpt-4o-mini)" if OPENAI_API_KEY else "Anthropic (claude-haiku-4.5)"
    )
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
            if result["segment"] not in ("OTHER", "ERROR") and not result[
                "segment"
            ].startswith("ERROR"):
                targets_found += 1
                print(
                    f"  ★ TARGET: {company['domain']} → {result['segment']} | {result['reasoning'][:80]}"
                )

            if done % 100 == 0:
                elapsed = time.time() - t0
                save_json(CLASSIFICATIONS, classifications)
                print(
                    f"    {done}/{len(to_classify)} classified ({elapsed:.0f}s), {targets_found} targets"
                )

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
    errors = sum(
        1 for v in classifications.values() if v.get("segment", "").startswith("ERROR")
    )
    self_check("Step 7", others, max(total_cls, 1), 50, 95, "OTHER classification rate")
    self_check("Step 7", errors, max(total_cls, 1), 0, 5, "ERROR rate")
    if targets_found == 0 and done > 100:
        print(
            "  ⚠️  ALERT [Step 7]: 0 targets found after 100+ classifications — prompt may be too strict"
        )

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
    run_files = sorted(STATE_DIR.glob("pipeline_results_run*.json"))
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
# Формирует финальные файлы:
#   - targets.json — компании для аутрича (INFLUENCER_PLATFORMS, IM_FIRST_AGENCIES, ...)
#   - rejects.json — OTHER (не наш ICP)
#   - pipeline_stats.json — статистика прогона
#   - CSV по сегментам в output/OnSocial/Targets/
#
# ВАЖНО: Step 8 НЕ пополняет blacklist.
# Blacklist пополняется только когда лиды реально отправлены в кампанию
# (findymail_to_smartlead.py → sync_blacklist()).
# Защита от повторной обработки — через classifications.json кеш (Step 7).


def step8_output(companies_map: dict, classifications: dict, website_cache: dict):
    """Generate targets.json, rejects.json, pipeline_stats.json."""
    print("\n=== STEP 8: Output ===")

    targets = []
    rejects = []
    segment_counts = {}

    # Only output classifications for domains in THIS run (not old cached ones)
    run_domains = set(companies_map.keys())
    skipped_old = 0

    for domain, cls in classifications.items():
        if domain not in run_domains:
            skipped_old += 1
            continue
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

    if skipped_old:
        print(f"  (skipped {skipped_old} classifications from previous runs)")
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


# ══════════════════════════════════════════════════════════════════════════════
# ★ CHECKPOINT: РУЧНАЯ ВЕРИФИКАЦИЯ ОПЕРАТОРОМ
# ══════════════════════════════════════════════════════════════════════════════
# Steps 9-11 запускаются ТОЛЬКО после того как оператор (через Claude Code):
#   1. Проверил таргеты из Step 8 (accuracy ≥90%)
#   2. При необходимости — прогнал prompt iteration loop (Steps 7→verify→adjust→repeat)
#   3. Подтвердил что таргеты корректны
#
# Запуск: python pipeline_onsocial.py --from-step 9 --campaign-name "c-OnSocial_SEGMENT #C"
#
# Без --campaign-name Steps 10-11 не запустятся (только people search).
# ══════════════════════════════════════════════════════════════════════════════


# ── STEP 9: PEOPLE SEARCH (Apollo) ────────────────────────────────────────────
# Ищет ЛПР (CEO, VP, Head of) в компаниях-таргетах через Apollo People Search API.
# Поиск БЕСПЛАТНЫЙ (search_people). Обогащение email ПЛАТНОЕ (enrich_person, 1 кредит).
# По умолчанию --skip-enrich: ищем людей без траты кредитов, email добьём через FindyMail.
# Кеш: contacts_cache.json — домены которые уже обработаны не повторяются.
# Код взят из targets_to_contacts.py.


def search_people(
    domain: str, titles: list[str], seniorities: list[str], per_page: int = 25
) -> list[dict]:
    """Search Apollo for people at a company domain. FREE — no credits consumed."""
    try:
        r = httpx.post(
            f"{APOLLO_BASE}/mixed_people/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": APOLLO_API_KEY,
                "q_organization_domains": domain,
                "person_titles": titles,
                "person_seniorities": seniorities,
                "page": 1,
                "per_page": per_page,
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("people", [])
        elif r.status_code == 429:
            print("  Rate limit on search — waiting 60s...")
            time.sleep(60)
            return search_people(domain, titles, seniorities, per_page)
        else:
            print(f"  WARN search {domain}: {r.status_code}")
            return []
    except Exception as e:
        print(f"  ERROR search {domain}: {e}")
        return []


def enrich_person(
    person_id: str = None,
    linkedin_url: str = None,
    first_name: str = None,
    last_name: str = None,
    domain: str = None,
) -> dict:
    """Enrich a person to get email + full details. COSTS 1 Apollo credit."""
    payload = {"api_key": APOLLO_API_KEY}
    if person_id:
        payload["id"] = person_id
    elif linkedin_url:
        payload["linkedin_url"] = linkedin_url
    elif first_name and last_name and domain:
        payload["first_name"] = first_name
        payload["last_name"] = last_name
        payload["domain"] = domain
    else:
        return {}

    try:
        r = httpx.post(
            f"{APOLLO_BASE}/people/match",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            person = r.json().get("person", {})
            return person if person else {}
        elif r.status_code == 429:
            print("  Rate limit on enrich — waiting 60s...")
            time.sleep(60)
            return enrich_person(person_id, linkedin_url, first_name, last_name, domain)
        else:
            return {}
    except Exception as e:
        print(f"  ERROR enrich: {e}")
        return {}


def step9_people_search(
    targets: list, skip_enrich: bool = True, force: bool = False
) -> list[dict]:
    """Find decision-maker contacts for target companies via Apollo."""
    print("\n=== STEP 9: People Search (Apollo) ===")

    if CONTACTS_FILE.exists() and not force:
        contacts = load_json(CONTACTS_FILE)
        print(f"  already exists: {len(contacts)} contacts (skip)")
        return contacts

    if not APOLLO_API_KEY:
        print("  ERROR: APOLLO_API_KEY not set")
        sys.exit(1)

    cache = load_json(STATE_DIR / "contacts_cache.json") or {}
    print(f"  Contacts cache: {len(cache)} domains already processed")
    all_contacts = []
    new_processed = 0

    for i, target in enumerate(targets, 1):
        domain = target["domain"]
        segment = target.get("segment", "UNKNOWN")
        company_name = target.get("company_name", domain)

        if domain in cache:
            all_contacts.extend(cache[domain])
            continue

        print(f"[{i}/{len(targets)}] {domain} ({segment})")

        people = search_people(domain, DEFAULT_TITLES, DEFAULT_SENIORITIES)
        if not people:
            cache[domain] = []
            new_processed += 1
            if new_processed % 50 == 0:
                save_json(STATE_DIR / "contacts_cache.json", cache)
            time.sleep(0.3)
            continue

        people = people[:MAX_CONTACTS_PER_COMPANY]
        domain_contacts = []

        for person in people:
            first_name = person.get("first_name", "")
            last_name = person.get("last_name", "")
            title = person.get("title", "")
            linkedin_url = person.get("linkedin_url", "")
            email = person.get("email", "")

            # Обогащение email через Apollo (ПЛАТНОЕ) — только если --no-skip-enrich
            if not skip_enrich and not email:
                enriched = enrich_person(
                    person_id=person.get("id"),
                    linkedin_url=linkedin_url,
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                )
                if enriched:
                    email = enriched.get("email", "")
                    linkedin_url = linkedin_url or enriched.get("linkedin_url", "")
                    first_name = enriched.get("first_name", first_name)
                    last_name = enriched.get("last_name", last_name)
                    title = enriched.get("title", title)
                time.sleep(0.5)

            contact = {
                "Name": f"{first_name} {last_name}".strip(),
                "Email": email or "",
                "Title": title,
                "Company": company_name,
                "Company Domain": domain,
                "Segment": segment,
                "Profile URL": linkedin_url or "",
                "Location": person.get("city", ""),
                "Country": target.get("country", ""),
                "Employees": target.get("employees", ""),
            }
            domain_contacts.append(contact)
            all_contacts.append(contact)

            if email:
                print(f"    ✓ {first_name} {last_name} ({title}) → {email}")
            else:
                print(f"    ○ {first_name} {last_name} ({title}) — no email")

        cache[domain] = domain_contacts
        new_processed += 1
        if new_processed % 50 == 0:
            save_json(STATE_DIR / "contacts_cache.json", cache)
        time.sleep(0.3)

    save_json(STATE_DIR / "contacts_cache.json", cache)
    save_json(CONTACTS_FILE, all_contacts)

    with_email = sum(1 for c in all_contacts if c.get("Email"))
    companies_hit = len(set(c["Company Domain"] for c in all_contacts))
    print(f"\n  Companies with contacts: {companies_hit}/{len(targets)}")
    print(
        f"  Total contacts: {len(all_contacts)} ({with_email} with email, "
        f"{len(all_contacts) - with_email} without → Step 10 FindyMail)"
    )

    return all_contacts


# ── STEP 10: FINDYMAIL ENRICHMENT ─────────────────────────────────────────────
# Ищет email по LinkedIn URL через FindyMail API.
# Стоимость: ~$0.01/email. Async, 5 параллельных запросов, батчи по 20.
# Progress кеш: findymail_progress.json — при падении продолжает с места остановки.
# При 402 (кончились кредиты) — останавливается, сохраняет результат.
# Код взят из findymail_to_smartlead.py → enrich().
#
# ★ CHECKPOINT: Перед этим шагом оператор подтверждает расход.
#   Claude Code покажет: "Step 10: {N} контактов к обогащению, ~${cost}. Запускать?"

FINDYMAIL_CONCURRENT = 5


def fm_headers():
    return {
        "Authorization": f"Bearer {FINDYMAIL_API_KEY}",
        "Content-Type": "application/json",
    }


async def find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    """Find email by LinkedIn URL via FindyMail API."""
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers=fm_headers(),
            json={"linkedin_url": url},
            timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            email = data.get("email") or contact.get("email")
            verified = data.get("verified", False) or contact.get("verified", False)
            return {"email": email or "", "verified": verified}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        elif r.status_code == 404:
            return {"email": "", "verified": False}
        else:
            print(f"  WARN {r.status_code}: {r.text[:100]}")
            return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"email": "", "verified": False}


async def step10_findymail(
    contacts: list, max_contacts: int = 1500, force: bool = False
) -> list[dict]:
    """Enrich contacts with email via FindyMail."""
    print("\n=== STEP 10: FindyMail Enrichment ===")

    if ENRICHED_FILE.exists() and not force:
        enriched = load_json(ENRICHED_FILE)
        print(f"  already exists: {len(enriched)} enriched contacts (skip)")
        return enriched

    if not FINDYMAIL_API_KEY:
        print("  ERROR: FINDYMAIL_API_KEY not set")
        sys.exit(1)

    # Контакты без email но с LinkedIn URL → к обогащению
    to_enrich = [c for c in contacts if not c.get("Email") and c.get("Profile URL")]
    already_have = [c for c in contacts if c.get("Email")]
    no_linkedin = [
        c for c in contacts if not c.get("Email") and not c.get("Profile URL")
    ]
    print(f"  {len(already_have)} already have email")
    print(f"  {len(to_enrich)} to enrich via FindyMail")
    print(f"  {len(no_linkedin)} without LinkedIn URL (skipped)")

    to_enrich = to_enrich[:max_contacts]

    # Progress кеш — при падении продолжает с места остановки
    progress_file = STATE_DIR / "findymail_progress.json"
    done = load_json(progress_file) or {}
    if done:
        print(f"  Resuming: {len(done)} already processed")

    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)
    found = not_found = skipped = 0
    out_of_credits = False

    async def process_one(row):
        nonlocal found, not_found, skipped, out_of_credits
        if out_of_credits:
            return

        li_url = row.get("Profile URL", "").strip()
        if not li_url:
            skipped += 1
            return

        if li_url in done:
            res = done[li_url]
            row["Email"] = res.get("email", "")
            row["Verified"] = str(res.get("verified", False))
            if res.get("email"):
                found += 1
            else:
                not_found += 1
            skipped += 1
            return

        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await find_email(client, li_url)
                except RuntimeError:
                    out_of_credits = True
                    return

            row["Email"] = res.get("email", "")
            row["Verified"] = str(res.get("verified", False))
            done[li_url] = res

            if res.get("email"):
                found += 1
                print(f"  ✓ {row.get('Name', '')} → {res['email']}")
            else:
                not_found += 1

    t0 = time.time()
    batch_size = 20

    for i in range(0, len(to_enrich), batch_size):
        if out_of_credits:
            print("\n  OUT OF CREDITS — stopping")
            break
        batch = to_enrich[i : i + batch_size]
        await asyncio.gather(*[process_one(r) for r in batch])
        progress_file.write_text(json.dumps(done))
        processed = found + not_found + skipped
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed else 0
        eta = (len(to_enrich) - processed) / rate if rate else 0
        print(
            f"[{processed}/{len(to_enrich)}] found={found} not_found={not_found} "
            f"rate={rate:.1f}/s ETA={eta:.0f}s"
        )

    progress_file.write_text(json.dumps(done))

    all_enriched = already_have + to_enrich + no_linkedin
    with_email = [c for c in all_enriched if c.get("Email", "").strip()]
    without_email = [c for c in all_enriched if not c.get("Email", "").strip()]
    save_json(ENRICHED_FILE, all_enriched)

    # CSV backup
    save_csv(
        CSV_OUTPUT_DIR / f"enriched_{_date_tag().replace(' ', '_')}.csv", with_email
    )
    save_csv(
        CSV_OUTPUT_DIR / f"without_email_{_date_tag().replace(' ', '_')}.csv",
        [c for c in without_email if c.get("Profile URL")],
    )

    elapsed = time.time() - t0
    print(f"\n  FindyMail done in {elapsed:.0f}s")
    print(f"  Found: {found} ({found / max(1, found + not_found) * 100:.1f}% hit rate)")
    print(f"  Total with email: {len(with_email)}/{len(all_enriched)}")

    return all_enriched


# ── STEP 11: SMARTLEAD UPLOAD ─────────────────────────────────────────────────
# Создаёт кампанию в SmartLead (DRAFT), загружает лидов с email.
# Кампания создаётся БЕЗ sequences — добавляются вручную в SmartLead UI.
# После загрузки: sync_blacklist() — домены загруженных лидов → blacklist.
# Код взят из findymail_to_smartlead.py.
#
# ★ CHECKPOINT: Перед этим шагом оператор подтверждает создание кампании.
#   Claude Code покажет: "Step 11: {N} лидов с email. Создать кампанию '{name}'?"


def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}


def create_campaign(campaign_name: str) -> int:
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/create",
        params=sl_params(),
        json={
            "name": campaign_name,
            "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
            "send_as_plain_text": True,
            "stop_lead_settings": "REPLY_TO_AN_EMAIL",
        },
        timeout=30,
    )
    r.raise_for_status()
    campaign_id = r.json()["id"]
    print(f"  Created campaign: {campaign_id} — {campaign_name}")
    return campaign_id


def add_email_accounts(campaign_id: int, account_ids: list[int]):
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/email-accounts",
        params=sl_params(),
        json={"emailAccountIDs": account_ids},
        timeout=30,
    )
    r.raise_for_status()
    print(f"  Email accounts added: {len(account_ids)}")


def set_schedule(campaign_id: int, timezone: str = "America/New_York"):
    r = httpx.post(
        f"{SMARTLEAD_BASE}/campaigns/{campaign_id}/schedule",
        params=sl_params(),
        json={
            "timezone": timezone,
            "days_of_the_week": [1, 2, 3, 4, 5],
            "start_hour": "08:00",
            "end_hour": "18:00",
            "min_time_btw_emails": 10,
            "max_new_leads_per_day": 1000,
        },
        timeout=30,
    )
    r.raise_for_status()
    print(f"  Schedule: Mon-Fri 08:00-18:00 ({timezone})")


def filter_existing_contacts(emails: list[str], project_id: int = 42) -> dict:
    """Check emails against contacts DB. Returns {email: status} for existing contacts.

    Blocks: replied, meeting_booked, not_qualified, sent.
    Works on Hetzner (docker exec) or locally (ssh hetzner).
    """
    if not emails:
        return {}
    BLOCK_STATUSES = ("replied", "meeting_booked", "not_qualified", "sent")
    sanitized = [e.replace("'", "''").lower().strip() for e in emails if e and "@" in e]
    if not sanitized:
        return {}
    existing = {}
    for i in range(0, len(sanitized), 500):
        batch = sanitized[i : i + 500]
        email_list = ",".join(f"'{e}'" for e in batch)
        sql = (
            f"SELECT lower(email), status FROM contacts "
            f"WHERE project_id = {project_id} "
            f"AND lower(email) IN ({email_list})"
        )
        psql_cmd = (
            "docker exec leadgen-postgres psql -U leadgen -d leadgen "
            f"-t -A -F'|' -c \"{sql}\""
        )
        is_hetzner = os.path.exists("/root/magnum-opus-project")
        if is_hetzner:
            run_args = ["bash", "-c", psql_cmd]
        else:
            run_args = ["ssh", "hetzner", psql_cmd]
        try:
            result = subprocess.run(
                run_args, capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|")
                    existing[parts[0].strip()] = parts[1].strip()
        except Exception as e:
            print(f"  WARNING: contact DB check failed: {e}")
    blocked = {e: s for e, s in existing.items() if s in BLOCK_STATUSES}
    if blocked:
        print(f"  CONTACT DEDUP: {len(blocked)} emails blocked (already in DB)")
        by_status = {}
        for e, s in blocked.items():
            by_status.setdefault(s, []).append(e)
        for status, emails_list in sorted(by_status.items()):
            print(
                f"    {status}: {len(emails_list)} ({', '.join(emails_list[:3])}{'...' if len(emails_list) > 3 else ''})"
            )
    return blocked


def upload_leads(campaign_id: int, rows: list[dict]) -> int:
    # Contact-level dedup: check DB before uploading
    all_emails = [
        r.get("Email", r.get("email", "")).strip().lower()
        for r in rows
        if r.get("Email") or r.get("email")
    ]
    blocked_emails = filter_existing_contacts(all_emails)
    if blocked_emails:
        before = len(rows)
        rows = [
            r
            for r in rows
            if r.get("Email", r.get("email", "")).strip().lower() not in blocked_emails
        ]
        print(
            f"  Filtered: {before} -> {len(rows)} (removed {before - len(rows)} existing contacts)"
        )
    leads = []
    for r in rows:
        name = r.get("Name", "").strip()
        parts = name.split(" ", 1)
        leads.append(
            {
                "email": r.get("Email", "").strip(),
                "first_name": parts[0] if parts else "",
                "last_name": parts[1] if len(parts) > 1 else "",
                "company_name": normalize_company(r.get("Company", "")),
                "linkedin_profile": r.get("Profile URL", "").strip(),
                "custom_fields": {
                    "title": r.get("Title", "").strip(),
                    "location": r.get("Location", "").strip(),
                },
            }
        )

    batch_size = 100
    total_ok = 0
    for i in range(0, len(leads), batch_size):
        batch = leads[i : i + batch_size]
        r = httpx.post(
            f"{SMARTLEAD_BASE}/leads",
            params={**sl_params(), "campaign_id": campaign_id},
            json={"lead_list": batch},
            timeout=60,
        )
        if r.status_code == 200:
            total_ok += len(batch)
            print(
                f"  Batch {i // batch_size + 1}: {len(batch)} leads (total {total_ok})"
            )
        elif r.status_code == 429:
            print("  Rate limit — waiting 70s...")
            time.sleep(70)
            r2 = httpx.post(
                f"{SMARTLEAD_BASE}/leads",
                params={**sl_params(), "campaign_id": campaign_id},
                json={"lead_list": batch},
                timeout=60,
            )
            if r2.status_code == 200:
                total_ok += len(batch)
                print(f"  Batch {i // batch_size + 1} (retry): {len(batch)} leads")
            else:
                print(f"  WARN batch {i // batch_size + 1} retry: {r2.status_code}")
        else:
            print(f"  WARN batch {i // batch_size + 1}: {r.status_code}")
        time.sleep(1)

    print(f"\n  Uploaded: {total_ok}/{len(leads)} leads")
    return total_ok


def sync_blacklist(rows: list[dict]):
    """Add uploaded lead domains to blacklist — prevents re-targeting in future pipeline runs."""
    domains = set()
    for r in rows:
        email = r.get("Email", "").strip()
        if email and "@" in email:
            d = email.split("@", 1)[1].lower().strip()
            if d:
                domains.add(d)
        company = r.get("Company Domain", "").strip()
        if company:
            domains.add(norm_domain(company))
    if not domains:
        return

    bl = load_json(BLACKLIST_FILE)
    if not bl:
        bl = {"domains": [], "count": 0}
    bl_set = set(bl.get("domains", []))
    new_domains = domains - bl_set
    if not new_domains:
        print(f"\n  Blacklist: all {len(domains)} domains already present")
        return
    bl_set.update(new_domains)
    bl["domains"] = sorted(bl_set)
    bl["count"] = len(bl_set)
    bl["last_updated_at"] = ts()
    save_json(BLACKLIST_FILE, bl)
    print(f"\n  Blacklist: +{len(new_domains)} domains (total: {len(bl_set)})")


def step11_smartlead(
    contacts: list, campaign_name: str, campaign_id: int | None = None
) -> int | None:
    """Create SmartLead campaign (DRAFT) and upload leads with email."""
    print("\n=== STEP 11: SmartLead Upload ===")

    if not SMARTLEAD_API_KEY:
        print("  ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    with_email = [c for c in contacts if c.get("Email", "").strip()]
    if not with_email:
        print("  No contacts with email — nothing to upload")
        return None

    print(f"  {len(with_email)} leads with email to upload")

    if not campaign_id:
        campaign_id = create_campaign(campaign_name)
    else:
        print(f"  Using existing campaign: {campaign_id}")

    add_email_accounts(campaign_id, DEFAULT_EMAIL_ACCOUNTS)
    set_schedule(campaign_id)
    upload_leads(campaign_id, with_email)
    sync_blacklist(with_email)

    print(f"\n  Campaign {campaign_id}: DRAFTED")
    print("  Next: add sequences in SmartLead UI, then activate")
    return campaign_id


# ── MAIN ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="OnSocial Enrichment Pipeline (v2 — improved)"
    )
    parser.add_argument("--step", type=int, help="Run only this step (0-8)")
    parser.add_argument("--from-step", type=int, default=0, help="Start from this step")
    parser.add_argument(
        "--limit", type=int, default=0, help="Stop after N targets found"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-run even if output exists"
    )
    parser.add_argument(
        "--import-existing",
        action="store_true",
        help="Import legacy pipeline_results_run*.json",
    )
    parser.add_argument("--concurrency-scrape", type=int, default=8)
    parser.add_argument("--concurrency-classify", type=int, default=20)
    parser.add_argument(
        "--no-prefilter", action="store_true", help="Skip Step 6.5 regexp pre-filter"
    )
    parser.add_argument(
        "--no-deep-scrape", action="store_true", help="Skip Step 6.7 deep scrape"
    )
    parser.add_argument(
        "--no-skip-scrape",
        action="store_true",
        help="Don't skip scraping for high-signal companies",
    )
    parser.add_argument(
        "--validate",
        type=int,
        metavar="N",
        help="Show N random targets for manual review (no pipeline run)",
    )
    parser.add_argument(
        "--finalize-rejects",
        action="store_true",
        help="Move OTHER domains from classifications to blacklist",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this run (saved in state/onsocial/runs/)",
    )
    # Steps 9-11 arguments
    parser.add_argument(
        "--campaign-name",
        type=str,
        default=None,
        help="SmartLead campaign name (required for Step 11)",
    )
    parser.add_argument(
        "--campaign-id",
        type=int,
        default=None,
        help="Existing SmartLead campaign ID (skip creation)",
    )
    parser.add_argument(
        "--max-contacts",
        type=int,
        default=1500,
        help="Max contacts to enrich in Step 10 (default: 1500)",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        default=True,
        help="Step 9: skip Apollo email enrichment, rely on FindyMail (default: True)",
    )
    parser.add_argument(
        "--no-skip-enrich",
        action="store_true",
        help="Step 9: DO enrich via Apollo (costs credits)",
    )
    parser.add_argument(
        "--timezone",
        default="America/New_York",
        help="SmartLead campaign timezone (default: America/New_York)",
    )
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
            print(
                f"  ⚠️  WARNING: CLASSIFICATION_PROMPT changed but PROMPT_VERSION is still '{PROMPT_VERSION}'!"
            )
            print(
                "       Bump PROMPT_VERSION to avoid mixing results from different prompts."
            )

    # ── --validate N: show random targets for manual review, then exit ──
    if args.validate:
        import random

        classifications = load_json(CLASSIFICATIONS) or {}
        website_cache_data = {}  # lazy load
        targets_list = [
            (domain, info)
            for domain, info in classifications.items()
            if info.get("segment", "OTHER") not in ("OTHER", "ERROR")
            and not info.get("segment", "").startswith("ERROR")
        ]
        if not targets_list:
            print("No targets found in classifications.json")
            sys.exit(0)
        n = min(args.validate, len(targets_list))
        sample = random.sample(targets_list, n)
        print(f"\n{'=' * 80}")
        print(f"VALIDATION: {n} random targets (out of {len(targets_list)} total)")
        print(f"{'=' * 80}")
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
        print(f"\n{'=' * 80}")
        print("Review each domain: open the URL, compare with segment/reasoning.")
        print("If accuracy < 90% → revise prompt and re-run classification.")
        sys.exit(0)

    # ── --finalize-rejects: move OTHER domains to blacklist ──
    if args.finalize_rejects:
        classifications = load_json(CLASSIFICATIONS) or {}
        blacklist = load_json(BLACKLIST_FILE)
        if not blacklist:
            print("ERROR: blacklist not found. Run step 0 first.")
            sys.exit(1)
        bl_set = set(blacklist.get("domains", []))
        others = [
            d
            for d, info in classifications.items()
            if info.get("segment") == "OTHER" and d not in bl_set
        ]
        if not others:
            print("No new OTHER domains to add to blacklist.")
            sys.exit(0)
        bl_set.update(others)
        blacklist["domains"] = sorted(bl_set)
        blacklist["count"] = len(bl_set)
        blacklist["finalized_at"] = ts()
        blacklist["finalized_others"] = len(others)
        save_json(BLACKLIST_FILE, blacklist)
        print(
            f"✅ Added {len(others)} OTHER domains to blacklist (total: {len(bl_set)})"
        )
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
    blacklist = (
        step0_blacklist(force=args.force)
        if should_run(0)
        else load_json(BLACKLIST_FILE)
    )
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
            print(
                f"\n[Step 3] Loaded {len(companies)} after-blacklist companies from cache"
            )
    elif AFTER_BLACKLIST.exists():
        companies = load_json(AFTER_BLACKLIST)
        print(
            f"\n[Step 3] Loaded {len(companies)} after-blacklist companies from cache"
        )

    # Step 4 (deterministic filter)
    if should_run(4):
        priority, normal, disq = step4_filter(companies, force=args.force)
    elif PRIORITY_FILE.exists():
        priority = load_json(PRIORITY_FILE)
        normal = load_json(NORMAL_FILE)
        disq = load_json(DISQUALIFIED)
        print(
            f"\n[Step 4] Loaded: {len(priority)} priority, {len(normal)} normal, {len(disq)} disqualified"
        )
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
            print(
                f"\n  [Skip-scrape] {len(skip_scraped)} companies have 3+ signals + Apollo description → classify without scraping"
            )
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
        asyncio.run(
            step6c_deep_scrape(
                process_queue,
                website_cache,
                classifications_so_far,
                concurrency=min(args.concurrency_scrape, 4),
            )
        )

    # Step 7 (classification)
    if should_run(7):
        classifications = asyncio.run(
            step7_classify(
                process_queue,
                website_cache,
                limit_targets=args.limit,
                concurrency=args.concurrency_classify,
            )
        )
    else:
        classifications = load_json(CLASSIFICATIONS) or {}
        print(f"\n[Step 7] Loaded {len(classifications)} cached classifications")

    # Step 8 (output)
    if should_run(8):
        targets, rejects = step8_output(companies_map, classifications, website_cache)
        print(f"\nDone. {len(targets)} targets → {TARGETS_FILE.name}")
    else:
        # Still show current stats
        targets = [
            v
            for v in classifications.values()
            if v.get("segment", "OTHER") not in ("OTHER", "ERROR")
        ]
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
        "provider": "openai"
        if OPENAI_API_KEY
        else ("anthropic" if ANTHROPIC_API_KEY else "none"),
        "args": {
            "step": args.step,
            "from_step": args.from_step,
            "limit": args.limit,
            "force": args.force,
            "no_prefilter": args.no_prefilter,
            "no_deep_scrape": args.no_deep_scrape,
            "no_skip_scrape": args.no_skip_scrape,
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

    # ══════════════════════════════════════════════════════════════════════════
    # Steps 9-11: ТОЛЬКО после ручной верификации оператором.
    # Оператор (через Claude Code) проверяет таргеты, прогоняет prompt
    # iteration loop если нужно, и запускает: --from-step 9
    # ══════════════════════════════════════════════════════════════════════════

    # Step 9 (people search)
    if should_run(9):
        if not isinstance(targets, list) or not targets:
            targets = load_json(TARGETS_FILE) or []
        if not targets:
            print("ERROR: no targets. Run steps 0-8 first.")
            sys.exit(1)
        skip_enrich = args.skip_enrich and not args.no_skip_enrich
        contacts = step9_people_search(
            targets, skip_enrich=skip_enrich, force=args.force
        )
    elif CONTACTS_FILE.exists():
        contacts = load_json(CONTACTS_FILE)
        print(f"\n[Step 9] Loaded {len(contacts)} contacts from cache")
    else:
        contacts = []

    # Step 10 (FindyMail)
    if should_run(10):
        if not contacts:
            contacts = load_json(CONTACTS_FILE) or []
        if not contacts:
            print("ERROR: no contacts. Run step 9 first.")
            sys.exit(1)
        contacts = asyncio.run(
            step10_findymail(
                contacts,
                max_contacts=args.max_contacts,
                force=args.force,
            )
        )
    elif ENRICHED_FILE.exists() and should_run(11):
        contacts = load_json(ENRICHED_FILE)
        print(f"\n[Step 10] Loaded {len(contacts)} enriched contacts from cache")

    # Step 11 (SmartLead)
    if should_run(11):
        if not args.campaign_name and not args.campaign_id:
            print("\nStep 11 skipped: --campaign-name or --campaign-id required")
        else:
            if not contacts:
                contacts = load_json(ENRICHED_FILE) or load_json(CONTACTS_FILE) or []
            if not contacts:
                print("ERROR: no contacts. Run steps 9-10 first.")
                sys.exit(1)
            campaign_name = args.campaign_name or f"c-OnSocial_{_date_tag()}"
            step11_smartlead(contacts, campaign_name, campaign_id=args.campaign_id)

    # Итоговая сводка
    if should_run(8) and not should_run(9):
        print("\n   Next: verify targets, then --from-step 9 --campaign-name '...'")


if __name__ == "__main__":
    main()
