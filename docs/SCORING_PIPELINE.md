# EasyStaff Global — Scoring Pipeline Documentation

## Data Flow

```
Clay People Search (language/university/surname searches)
    ↓
Google Sheet "UAE-Pakistan" tab (ALL gathered contacts, 15,867)
    ↓
CRM loads SmartLead + GetSales contacts, filters out already-contacted
    ↓
Google Sheet "UAE-Pakistan - New Only" tab (clean pool, 15,369)
    ↓
Scoring pipeline reads from "New Only", writes to NEW tab "v8 Scored"
```

## What Each Tab Contains

| Tab | Contents | Row count | Use |
|-----|----------|-----------|-----|
| `UAE-Pakistan` | ALL contacts gathered from Clay | 15,867 | Source of truth — never modify |
| `UAE-Pakistan - New Only` | All minus 498 already contacted | 15,369 | **Scoring input** |
| `Sheet2` | UNIQUE(Domain) from all corridors | 7,900 | Reference — domain inventory |
| `UAE-Pakistan v8 Scored` | Scoring output | variable | **Pipeline output** — always create NEW tab |
| `UAE-Pakistan Priority 2000` | Old output (DO NOT overwrite) | 2,100 | Legacy — operator may reference |

## ICP Definition — Who We're Looking For

EasyStaff helps companies in UAE pay remote contractors in Pakistan.

**Ideal contact:**
1. **Person**: Pakistani-origin (Urdu speaker / PK university / PK surname) decision-maker
2. **Located in**: Dubai / Abu Dhabi / Sharjah / UAE (NOT in Pakistan, India, etc.)
3. **Role**: CFO, COO, HR Director, CEO/Founder, CTO (decision-maker for payments)
4. **Company HQ**: UAE (NOT Pakistan — PK companies pay locally, don't need EasyStaff)
5. **Company size**: 5-200 employees (too small = no contractors, too big = in-house payroll)
6. **Company type**: Tech, consulting, digital agency, SaaS, fintech, outsourcing BUYER
7. **NOT**: PK-HQ company with Dubai shelf office, competitor (payroll/EOR provider), enterprise

## The Core Challenge

Contractors are INVISIBLE. They don't list the company on LinkedIn. Companies don't advertise contractor relationships. Clay and website scraping can't confirm "this company has PK contractors."

**Solution: Via Negativa** — score by EXCLUDING bad fits, not confirming good ones.

The cultural hypothesis: Pakistani-origin decision-maker in UAE → likely has contractors from home country. This can't be validated before outreach. It IS the outreach.

## 3-Layer Exclusion System

### Layer 1: GPT-4o-mini Binary Flags ($0.30 per 5,000 companies)

One prompt per company, asks YES/NO questions on website text. NEVER numerical scores.

**Fields:**
- `hq_country` — where company is headquartered
- `is_hq_in_uae` / `is_hq_in_pakistan` — binary HQ check
- `is_competitor` — provides payroll/EOR/HR services?
- `is_outsourcing_provider` — sells outsourcing labor?
- `is_construction_realestate_hospitality` — irrelevant industry?
- `is_enterprise_300plus` — too big?
- `would_need_easystaff` — overall fit (used as penalty for non-tech, NOT hard gate)
- `company_vertical` — industry classification

**GPT's #1 failure mode:** Says `is_hq_in_uae=True` for PK companies that list a Dubai address. Layers 2 and 3 catch this.

### Layer 2: Deterministic Regexp (website text)

Runs on cached website text. Overrides GPT when GPT is wrong.

**PK-HQ detection (combined with tech industry = PK-HQ override):**
- PK street addresses: Gulberg, Johar Town, DHA Phase, Model Town, Shahrah-e-Faisal, etc.
- PK phone numbers: `+92` or `03xx` patterns
- PK company suffixes: "Pvt. Ltd", "Private Limited"
- PK-specific phrases: "our team in Lahore", "development center in Karachi"

**Non-buyer-country HQ:** GPT `hq_country` not matching UAE → hard exclude

**Competitor keywords:** "employer of record", "payroll provider", etc.

### Layer 3: Verified Exclusion List

Companies that pass Layers 1-2 but are known-bad from manual verification. PK companies whose homepage hides PK origin. Currently 15 domains.

## Scoring Formula

```
Score = origin(40%) + role(20%) + survived_filters(20%) + outsourcing_signal(10%) + clay(10%)
```

- **Origin** (40%): Urdu speaker=100, PK university=90, PK surname=80
- **Role** (20%): CFO/Payroll=100, COO=90, HR=85, CEO/Founder=70, CTO=50
- **Survived filters** (20%): Passed ALL red flags = 100, ANY red flag = 0
- **Outsourcing signal** (10%): Website mentions outsourcing/contractors/remote
- **Clay confirmation** (10%): 5-30 PK employees = 100, 0 = 50 (neutral), 100+ = 10

## Selection Gates (hard exclusions from output)

A company is EXCLUDED from the scored output if ANY of these is true:

1. **No domain** — can't verify anything
2. **No website data** — dead/placeholder site
3. **Any red flag fired** — hq_in_talent_country, irrelevant_industry, enterprise, competitor, hq_not_in_buyer, country_list_only
4. **GPT says would_need=False AND industry is NOT in tech whitelist** — catches training, events, food, shipping, equipment while preserving tech/consulting/digital
5. **In VERIFIED_EXCLUDE list** — manually confirmed bad

## Excluded Industries

```
construction, real_estate, hospitality, interior_design,
food, trading, manufacturing, retail,
insurance, banking, legal, law,
government, public sector,
car rental, transportation, automotive,
events and exhibitions, event planning,
oil and gas, energy, aerospace,
sports, beauty, fashion,
education, training, coaching,
recruitment, hr services,
shipping, broadcast equipment, private equity
```

## Tech Whitelist (would_need=False penalty only, not exclusion)

```
tech, technology, saas, software, it services,
digital marketing, digital agency, outsourcing,
consulting, consultancy, fintech, cybersecurity,
software quality assurance, ai, marketing,
business services, professional services,
language services, editing services, media, design,
insurtech, pharmaceuticals, healthcare,
logistics, data services, market research
```

## Data Persistence

ALL data lives in `/scripts/data/` (mounted from repo, survives Docker restarts).
NEVER use `/tmp/` inside Docker containers.

| File | Contents | Size |
|------|----------|------|
| `uae_pk_v6_scrape.json` | Website homepages (10,371 domains) | ~25MB |
| `deep_scrape_v7.json` | About/contact/team pages | growing |
| `uae_pakistan_v8_gpt_flags.json` | GPT binary flags (4,995 domains) | ~8MB |
| `uae_pakistan_v8_company_analysis.csv` | Full company analysis | ~2MB |
| `uae_pakistan_v8_scored.json` | Scored contact output | ~1MB |

## Pipeline Scripts

| Script | Purpose | Runtime | Cost |
|--------|---------|---------|------|
| `scripts/gpt_binary_flags.py` | GPT-4o-mini binary flag analysis | 14 min / 5K domains | $0.30 |
| `scripts/deep_scrape.py` | Multi-page website scraper | ~80 min / 1K domains | $0 |
| `scripts/uae_pk_v7_score.py` | Scoring + Google Sheet output | 17 seconds | $0 |
| `scripts/make_clay_remaining.py` | Domain list for Clay automation | 5 seconds | $0 |
| `scripts/clay/clay_people_search.js` | Clay People Search automation | ~3 min / 200 domains | $0 |

## How to Re-Score

```bash
# All data is cached — re-scoring is instant (17 seconds)
docker exec leadgen-backend python3 /scripts/uae_pk_v7_score.py uae-pakistan

# To re-analyze with GPT (only analyzes uncached domains):
docker exec leadgen-backend python3 /scripts/gpt_binary_flags.py uae-pakistan --model gpt

# To deep-scrape more about/contact pages:
docker exec leadgen-backend python3 /scripts/deep_scrape.py --limit 500
```

## Quality Verification Protocol

1. Run scoring
2. Take top 100 unique companies from scored output
3. For EACH company, read the actual website text from cache
4. Make INDEPENDENT judgment: is this a real UAE company that could plausibly need EasyStaff?
5. Check: PK-origin contact + UAE location + UAE-HQ company + tech/service industry
6. Any failure → investigate why filters missed it → add to exclusion list or fix filter
7. Target: 98%+ accuracy on 100 companies before using output

**CRITICAL: Verification must be independent of the labeling method.**
Don't check GPT flags against GPT flags. Read the raw website text yourself.
