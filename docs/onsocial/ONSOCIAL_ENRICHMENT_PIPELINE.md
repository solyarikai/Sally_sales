# OnSocial Enrichment & Segmentation Pipeline

> Автоматизированный пайплайн: Google Sheets (Apollo export) → Blacklist → Website Scraping → AI Classification → Target Companies
>
> Дата: 2026-03-18 | Проект: OnSocial (project_id=42)

---

## Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC STEPS (быстро, бесплатно)          │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │ 5 Google     │───▶│ Normalize    │───▶│ Blacklist Filter     │   │
│  │ Sheets       │    │ domains      │    │ (SmartLead +         │   │
│  │ (Apollo CSV) │    │ deduplicate  │    │  GetSales +          │   │
│  └──────────────┘    └──────────────┘    │  Google Sheet +      │   │
│                                          │  OnSocial clients +  │   │
│                                          │  Pipeline rejects)   │   │
│                                          └──────────┬───────────┘   │
│                                                     │               │
│  ┌──────────────┐    ┌──────────────┐              │               │
│  │ Employee     │───▶│ Industry     │◀─────────────┘               │
│  │ filter       │    │ keyword      │                               │
│  │ (10-5000)    │    │ disqualify   │                               │
│  └──────────────┘    └──────────────┘                               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ clean companies (new, right size)
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SCRAPING STEP (Apify actors, cached)              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Website Scraper (Apify actor / httpx+BS4 fallback)          │   │
│  │ Pages: homepage, /about, /pricing, /product                  │   │
│  │ Cache: PostgreSQL website_cache table (persistent)           │   │
│  │ Skip: already scraped domains                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ companies + website_content
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AI CLASSIFICATION (GPT-4o-mini, cached)           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Classify: INFLUENCER_PLATFORMS | AFFILIATE_PERFORMANCE |     │   │
│  │           IM_FIRST_AGENCIES | OTHER | NEW:CATEGORY           │   │
│  │ Cache: PostgreSQL company_classifications table              │   │
│  │ Skip: already classified domains                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────┬───────────────────────────┘
                      │                   │
              ┌───────▼───────┐   ┌───────▼───────┐
              │ TARGET        │   │ REJECTED      │
              │ (fit=true)    │   │ (fit=false)   │
              │ → Output CSV  │   │ → Add to      │
              │ → Review      │   │   blacklist   │
              └───────────────┘   └───────────────┘
```

---

## Источники данных

### 5 Google Sheets (Apollo company exports)

| # | Sheet ID | Tab | Region | Rows (approx) |
|---|----------|-----|--------|----------------|
| 1 | `143uzjue-mI8MQ2XyHmyZDExPQevahFKA-agEtyXtA6M` | Apollo | US 15-5000 | ~9,348 |
| 2 | `17-jTs2kXvj5Sf141WGyfIy9roFa90dCYQySVGWaNW5g` | UK Europe 15-5000 | UK/EU | TBD |
| 3 | `1BiCsC13HwblxT7VeieBeVtjoSlOKdoptpdflEv5giT0` | LATAM MENA ASIA 10-5000 | LATAM/MENA/ASIA | TBD |
| 4 | `1pagfkj-P7ZocnjA5e2YmAqEMkXGK48LZTHUppwTlU5Q` | INDIA 15-5000 | India | TBD |
| 5 | `1NoXE9mDoz1Zz8xRf-bdGVqtSrkcti1nPjKfUTC8lSQk` | apollo-accounts-export | Mixed | TBD |

**Общие колонки:** Company Name, # Employees, Industry, Website, Company Linkedin Url, Company Country, Company Address, Keywords, Short Description, Founded Year, Technologies, Description

### Blacklist Sources

| Source | What | How to get |
|--------|------|-----------|
| **SmartLead campaigns** | Компании уже в email-кампаниях OnSocial | API: `GET /campaigns` → filter by OnSocial → `GET /campaigns/{id}/leads` |
| **GetSales campaigns** | Компании уже в LinkedIn-кампаниях | DB: `contacts` table where `project_id=42` |
| **Google Sheet BLACKLIST** | 700+ доменов (OnSocial master sheet) | Sheet ID: `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E`, tab: BLACKLIST |
| **OnSocial paid clients** | 191 домен (текущие клиенты) | Hardcoded in `scripts/onsocial_blacklist_and_lookalike.py` |
| **Pipeline rejects** | Компании, отмеченные как OTHER/дичь в прошлых прогонах | DB: `enrichment_results` table where `segment='OTHER'` |

**SmartLead OnSocial campaigns:**
- `Marketing agencies — Global`
- `IM platfroms & SaaS — Global`
- `Generic — Global`

---

## Шаги пайплайна (детально)

### Step 0: Initialize & Load Blacklist (один раз, кешировать)

**Цель:** Собрать единый blacklist из всех источников. Скачать один раз, сохранить на диск.

```python
# Persistence: /app/state/onsocial/blacklist.json
# Format: {"domains": ["domain1.com", ...], "updated_at": "2026-03-18T...", "sources": {...}}
```

**Алгоритм:**
1. Если `/app/state/onsocial/blacklist.json` существует и < 24h — использовать кеш
2. Иначе:
   a. SmartLead API → get campaigns → filter OnSocial → get all leads → extract domains
   b. DB query → contacts where project_id=42 → extract company domains
   c. Google Sheet → BLACKLIST tab → extract domains
   d. Hardcoded CLIENT_DOMAINS (191 domain)
   e. DB → enrichment_results where segment='OTHER' → extract domains
   f. Merge all → deduplicate → save to file

**Estimated blacklist size:** ~2,000-3,000 domains

### Step 1: Download & Normalize Companies (deterministic)

**Цель:** Скачать все 5 листов, нормализовать, дедуплицировать.

**Persistence:** `/app/state/onsocial/raw_companies.jsonl` (append-only, каждая компания = одна строка)

**Алгоритм:**
1. Для каждого Sheet:
   - Download all rows via Google Sheets MCP
   - Parse into structured dicts
2. Normalize domains:
   - Strip protocol (`http://`, `https://`)
   - Strip `www.`
   - Lowercase
   - Strip trailing `/`
3. Deduplicate by domain (keep first occurrence, note source sheet)
4. Save to JSONL with metadata: `{source_sheet, original_row, normalized_domain, ...}`

**Output columns:**
```
company_name, domain, employees, industry, country, address,
keywords, short_description, description, technologies,
founded_year, linkedin_url, source_sheet
```

### Step 2: Blacklist Filter (deterministic, instant)

**Цель:** Убрать все компании, которые уже есть в blacklist.

**Алгоритм:**
1. Load blacklist set (from Step 0)
2. For each company: check `normalized_domain in blacklist_set`
3. Log stats: total → filtered → remaining

**Output:** Filtered companies list + stats

### Step 3: Deterministic Disqualifiers (no AI, instant)

**Цель:** Убрать очевидно не подходящие компании БЕЗ AI.

**Rules:**
1. **Employee count:**
   - `< 10` → DISQUALIFY ("Too small")
   - `> 5000` → DISQUALIFY ("Enterprise, too large")
   - Missing → KEEP (will check via website)
2. **Industry keyword disqualifiers** (case-insensitive substring match in `industry` + `keywords`):
   - `staffing`, `recruitment`, `real estate`, `construction`, `mining`,
   - `oil & gas`, `hospital`, `healthcare` (unless also has `influencer`/`creator`),
   - `legal services`, `law firm`, `accounting`, `banking`,
   - `government`, `military`, `defense`, `utilities`,
   - `agriculture`, `farming`, `food production`,
   - `manufacturing` (unless also `social media`/`influencer`),
   - `education` (unless `edtech` or `creator`),
   - `insurance`, `logistics`, `shipping`, `transportation`
3. **Domain disqualifiers:**
   - Parked domain patterns: domain ends with known parking services
   - Domain is IP address
   - Domain is localhost/internal
4. **Positive signal boost** (mark for priority scraping):
   - Keywords contain: `influencer`, `creator`, `ugc`, `affiliate`, `social media marketing`,
   - `talent management`, `content creator`, `brand ambassador`, `influencer marketing`
   - Industry contains: `marketing & advertising`, `social media`
   - Short description mentions creators/influencers

**Output:** Companies split into:
- `priority_scrape` (has positive signals) — scrape first
- `normal_scrape` (neutral) — scrape second
- `disqualified` (deterministic reject) — add to blacklist, skip

### Step 4: Website Scraping (Apify actor, cached)

**Цель:** Получить контент сайтов для AI-классификации.

**Persistence:** PostgreSQL table `website_cache` OR `/app/state/onsocial/website_cache/` (one file per domain)

```sql
CREATE TABLE IF NOT EXISTS website_cache (
    domain TEXT PRIMARY KEY,
    homepage_content TEXT,
    about_content TEXT,
    scraped_at TIMESTAMP DEFAULT NOW(),
    status TEXT,  -- 'success', 'error', 'timeout', 'blocked'
    error_message TEXT
);
```

**Алгоритм:**
1. Check cache: skip already scraped domains
2. For new domains:
   a. **Primary:** Apify Website Content Crawler actor (JS rendering, reliable)
   b. **Fallback:** httpx + BeautifulSoup (existing `scraper_service.py`)
3. Scrape pages: homepage + /about (if exists)
4. Extract: title, meta description, main text content (strip boilerplate)
5. Save to cache immediately (crash-tolerant)
6. Rate limit: 10 concurrent, respect robots.txt

**Apify Actor Config:**
```json
{
    "startUrls": [{"url": "https://example.com"}],
    "maxCrawlPages": 3,
    "crawlerType": "cheerio",
    "maxConcurrency": 5,
    "proxyConfiguration": {"useApifyProxy": true}
}
```

**Batch size:** 50 domains per Apify run (cost-effective)

### Step 5: AI Classification (GPT-4o-mini, cached)

**Цель:** Классифицировать компании по сегментам OnSocial ICP.

**Persistence:** PostgreSQL table `enrichment_results` OR `/app/state/onsocial/classifications.jsonl`

```sql
CREATE TABLE IF NOT EXISTS enrichment_results (
    domain TEXT PRIMARY KEY,
    company_name TEXT,
    segment TEXT,          -- INFLUENCER_PLATFORMS, AFFILIATE_PERFORMANCE, IM_FIRST_AGENCIES, OTHER, NEW:*
    reasoning TEXT,        -- one-sentence evidence
    confidence TEXT,       -- high, medium, low
    employees INTEGER,
    country TEXT,
    industry TEXT,
    keywords TEXT,
    website_content_preview TEXT,  -- first 500 chars
    source_sheet TEXT,
    classified_at TIMESTAMP DEFAULT NOW(),
    prompt_version TEXT,   -- track which prompt version produced this
    model TEXT DEFAULT 'gpt-4o-mini',
    tokens_used INTEGER
);
```

**Алгоритм:**
1. Check cache: skip already classified domains
2. Build prompt with company data + website content
3. Call GPT-4o-mini (existing `openai_service.enrich_batch()`)
4. Parse response → segment + reasoning
5. Save to cache immediately
6. If segment = OTHER → add domain to blacklist for future runs

**Prompt (v1 — based on user's proven prompt):**

See classification prompt in `CLASSIFICATION_PROMPT_V1` section below.

**Cost estimate:**
- ~500 tokens input per company, ~50 tokens output
- GPT-4o-mini: $0.15/1M input + $0.60/1M output
- 1000 companies ≈ $0.11 total

### Step 6: Output & Review

**Output format:** JSONL + CSV with all debug columns:

```
domain, company_name, segment, reasoning, confidence,
employees, country, industry, keywords,
short_description, website_content_preview,
source_sheet, linkedin_url, founded_year, technologies,
prompt_version, classified_at, scrape_status
```

**Target:** Stop at 20 target companies (segment != OTHER), review with Opus.

---

## Persistence & Reusability Strategy

### File-based cache (Docker-tolerant)

```
/app/state/onsocial/
├── blacklist.json              # unified blacklist (refreshed daily)
├── raw_companies.jsonl          # all downloaded companies
├── filtered_companies.jsonl     # after blacklist + deterministic filter
├── website_cache/
│   ├── example.com.json        # {homepage_content, about_content, scraped_at, status}
│   └── ...
├── classifications.jsonl        # AI classification results
├── targets.csv                  # current target companies (human-readable)
├── rejects.csv                  # rejected companies (for blacklist update)
├── pipeline_state.json          # {last_run, step, progress, stats}
└── prompt_versions/
    └── v1.txt                   # classification prompt version history
```

### Docker volume mount (already configured):
```yaml
# docker-compose.yml
volumes:
  - ./state:/app/state:rw
```

### Restart tolerance:
- Each step checks cache before processing
- JSONL = append-only, crash-safe
- `pipeline_state.json` tracks progress: which domains are processed at each step
- On restart: resume from last unprocessed domain

---

## Output Columns (полный набор)

| Column | Source | Purpose |
|--------|--------|---------|
| `domain` | Normalized from Sheet | Primary key, dedup |
| `company_name` | Sheet | Display |
| `segment` | AI classification | **Target segment** |
| `reasoning` | AI classification | **Why this segment** |
| `confidence` | AI classification | high/medium/low |
| `employees` | Sheet | Size filter |
| `country` | Sheet | Geo targeting |
| `industry` | Sheet | Context |
| `keywords` | Sheet | Apollo keywords |
| `short_description` | Sheet | Quick overview |
| `website_content_preview` | Scraper | First 500 chars |
| `linkedin_url` | Sheet | Manual check |
| `founded_year` | Sheet | Company age |
| `technologies` | Sheet | Tech stack |
| `source_sheet` | Pipeline | Which Sheet |
| `scrape_status` | Scraper | success/error/timeout |
| `prompt_version` | Pipeline | Debug: which prompt |
| `classified_at` | Pipeline | When classified |
| `pipeline_run_id` | Pipeline | Batch tracking |
| `blacklisted_by` | Pipeline | If rejected, which source |
| `disqualify_reason` | Pipeline | If deterministic reject, why |

---

## Optimizations (deterministic first)

### Порядок фильтрации (от дешевого к дорогому):

```
Input: ~30,000 companies (5 sheets)
  ↓ Step 1: Deduplicate by domain          → ~25,000 (est. 15% dups)
  ↓ Step 2: Blacklist filter               → ~22,000 (est. 3,000 blacklisted)
  ↓ Step 3: Employee + industry filter     → ~15,000 (est. 30% obvious rejects)
  ↓ Step 4: Scrape websites (only new)     → ~15,000 (cached = skip)
  ↓ Step 5: AI classify (only new)         → ~15,000 (cached = skip)
  ↓ Step 6: Target extraction              → ~1,500-3,000 targets (est. 10-20%)
```

**Cost:** ~$1.65 total for GPT-4o-mini on 15,000 companies

### Priority queue:
- Companies with positive signals (Step 3) → process first
- Companies with website content in Apollo `Description` field → can skip scraping for initial pass
- **Apollo Description as pre-filter:** If `Short Description` or `Description` mentions influencer/creator → classify WITHOUT scraping (save time/cost)

### Batching:
- Google Sheets: download once, cache locally
- Scraping: batch 50 domains per Apify run
- GPT-4o-mini: batch 25 concurrent requests
- Blacklist refresh: once per 24h

---

## Classification Prompt V1

```
You classify companies as potential customers of OnSocial — a B2B API that provides creator/influencer data for Instagram, TikTok, and YouTube (audience demographics, engagement analytics, fake follower detection, creator search).

Companies that need OnSocial are those whose CORE business involves working with social media creators.

══ STEP 1: INSTANT DISQUALIFIERS ══
- website_content is EMPTY → "OTHER | No website data"
- Domain is parked / for sale / dead → "OTHER | Domain inactive"
- 5000+ employees → "OTHER | Enterprise, too large"
- <10 employees → "OTHER | Too small"

If none triggered → continue to Step 2.

══ STEP 2: SEGMENTS ══

INFLUENCER_PLATFORMS
  Builds SaaS / software / tools for influencer marketing: analytics, creator discovery, campaign management, creator CRM, UGC content platforms, creator marketplaces, creator monetization tools, social commerce, live shopping platforms, social listening with creator focus.
  KEY TEST: they have a PRODUCT (software/platform/API) that brands or agencies use to find, analyze, manage, or pay creators.

AFFILIATE_PERFORMANCE
  Affiliate network, performance marketing platform, CPA/CPS/CPL network, partner/referral platforms that connect advertisers with publishers/creators and pay per conversion.
  KEY TEST: they monetize based on conversions/actions, connecting advertisers with publishers or creators.

IM_FIRST_AGENCIES
  Agency where influencer/creator campaigns are THE primary business, not a side service. 10-500 employees. Includes: influencer-first agencies, MCN (multi-channel networks), creator talent management, gaming influencer agencies, UGC production agencies.
  KEY TEST: 60%+ of their visible offering (homepage, case studies, team titles) is about creator/influencer work.
  NOT THIS: "full-service digital agency" that lists influencers as one of many equal services.

OTHER
  Everything that does NOT fit the three segments above.

NEW SEGMENTS (dynamic discovery):
  If a company does NOT fit the three segments above, but belongs to a RECURRING business type that could be meaningful (e.g., "SOCIAL_COMMERCE_BRANDS", "GAMING_STUDIOS"), classify as:
  NEW:CATEGORY_NAME | reason

══ STEP 3: EVIDENCE ══
Look for MEANING, not exact keywords. Companies use marketing language.

Signals → INFLUENCER_PLATFORMS: "dashboard", "creator discovery", "book a demo", "analytics for creators", "brand-creator matching", "content marketplace"
Signals → AFFILIATE_PERFORMANCE: "affiliate", "CPA", "CPS", "publisher network", "conversion tracking", "partner payouts"
Signals → IM_FIRST_AGENCIES: "influencer agency", "creator campaigns", "talent management", "MCN", case studies dominated by influencer work
Signals → OTHER: No mention of creators/influencers/UGC. OR influencer is one bullet among SEO, PPC, PR, web design, etc.

══ STEP 4: CONFLICT RESOLUTION ══
- WEBSITE CONTENT outweighs apollo description (more reliable).
- If mixed signals (agency + platform) → choose based on PRIMARY revenue model.
- "Social media marketing" alone without creator-specific features → OTHER.
- If genuinely ambiguous → OTHER.

══ INPUT ══
Company: {company_name}
Employees: {employees}
Industry: {industry}
Keywords: {keywords}
Apollo description: {short_description}
Website content: {website_content}

══ OUTPUT ══
Respond with EXACTLY one line:
SEGMENT | one-sentence evidence

Examples:
INFLUENCER_PLATFORMS | Homepage offers a creator discovery dashboard with audience analytics and brand matching tools
AFFILIATE_PERFORMANCE | Operates a CPA network connecting advertisers with influencer-publishers
IM_FIRST_AGENCIES | Agency specializing in TikTok creator campaigns, all 6 case studies are influencer activations
OTHER | Generic digital agency offering SEO, PPC, email, and influencer as one of 8 services
NEW:SOCIAL_COMMERCE_TOOLS | Builds shoppable video tools for e-commerce brands, not influencer-focused but creator-adjacent
```

---

## Метрики и мониторинг

### На каждый прогон фиксировать:
- Total input companies
- Dedup removed
- Blacklist removed (by source breakdown)
- Deterministic disqualified (by reason breakdown)
- Scraped (new + cached)
- Scrape errors (timeout, blocked, parked)
- Classified (new + cached)
- **Segments breakdown**: count per segment
- **Target companies found** (non-OTHER)
- **Cost**: API calls, tokens, Apify credits

### Quality metrics (after manual review):
- Precision: true targets / (true targets + false positives)
- Recall: true targets / (true targets + false negatives)
- Prompt version that produced the result

---

## Execution Plan

### Run 1: Find first 20 targets
1. Download all 5 sheets
2. Build blacklist
3. Deterministic filter
4. **Optimization:** Use Apollo `Short Description` + `Keywords` for companies with positive signals — classify without scraping first
5. Scrape priority companies (with positive signals)
6. Classify with GPT-4o-mini
7. Stop at 20 targets
8. **Opus reviews all 20** — validates segments, catches false positives
9. Update prompt based on findings

### Run 2: Improve and find next 20
1. Apply prompt improvements from Run 1 review
2. Continue processing remaining companies
3. Stop at next 20 targets
4. Wait for user feedback

### Run 3+: Scale
- Process all remaining companies
- Build final target list
- Export for people search (Apollo) → email enrichment (Clay) → campaign push (SmartLead)

---

## Implementation

Script location: `scripts/onsocial_enrichment_pipeline.py`

Runs inside Docker container (access to DB, Redis, API keys).

Can also run locally with direct Google Sheets MCP access + OpenAI API key.

**Dependencies:**
- Google Sheets MCP (download data)
- SmartLead API (blacklist from campaigns)
- OpenAI API (classification)
- Apify API or httpx+BS4 (scraping)
- PostgreSQL (persistent cache) OR file-based (`/app/state/onsocial/`)

**For local run (this session):**
- Use Google Sheets MCP directly
- Use file-based persistence in `state/onsocial/`
- Call OpenAI API via existing backend service OR direct API call
- Scrape via httpx+BS4 (no Docker needed)
