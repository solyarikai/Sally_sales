# EasyStaff Global — Scoring & Prioritization Pipeline

## Data Flow

```
Clay People Search (language/university/surname)
    ↓
"UAE-Pakistan" tab (ALL gathered contacts, 15,867)
    ↓
CRM filters out already-contacted
    ↓
"UAE-Pakistan - New Only" (clean pool, 15,369)
    ↓
Scoring pipeline → NEW output tab "v8 Scored"
```

## Tab Structure — NEVER OVERWRITE

| Tab | What | Use |
|-----|------|-----|
| `UAE-Pakistan` | ALL contacts from Clay | Source of truth, never modify |
| `UAE-Pakistan - New Only` | Minus 498 already contacted | **Scoring input** |
| `Sheet2` | UNIQUE(Domain) = 7,602 domains | Domain inventory |
| `UAE-Pakistan v8 Scored` | Pipeline output | Always create NEW tabs |

## ICP — Who We're Looking For

EasyStaff helps companies pay remote contractors cross-border.

**Ideal contact for UAE-Pakistan corridor:**
1. Pakistani-origin decision-maker located in UAE
2. Company HQ in UAE (NOT PK-HQ with Dubai shelf office)
3. Any industry that uses remote contractors (NOT only tech — retail, real estate, services all qualify)
4. Company size 5-200
5. Not a competitor (payroll/EOR), not enterprise (300+)

**LEARNING FROM QUALIFIED LEADS:** Real estate company (Block Realty), pet companies (Petzyo, Central Park Puppies), glass hardware (IGT) all converted. Industry exclusion must be NARROW — only exclude industries that physically can't use remote workers (construction sites, hotels, oil rigs).

## Scoring Approach — Layered Via Negativa

Remove all obvious shit CHEAPLY first (regexp/keywords), then use GPT only for what's left.

### Layer 0: Cheap Deterministic Filters (FREE, instant)

Run BEFORE any GPT/scraping. Removes ~40% of contacts.

1. **No domain** → drop (can't verify, 37% of contacts)
2. **Location not in buyer country** → drop (contact in Pakistan/India = not our target)
3. **Enterprise blacklist** → drop (FAANG, Big4, airlines, banks, global agencies)
4. **Anti-title** → drop (intern, student, freelancer, driver, receptionist)
5. **Domain count >10** → drop (10+ contacts at same domain = enterprise)
6. **Clay 100+ employees** → drop (enterprise, has in-house payroll)
7. **.pk domain** → drop (PK company)

### Layer 1: Website Scraping (FREE, Apify proxy)

Scrape homepage. Cache in `/scripts/data/uae_pk_v6_scrape.json` (10,638 domains).

**What to detect from website text (regexp, no GPT needed):**
- PK-HQ: street addresses (Gulberg, Johar Town, DHA Phase, etc.) + tech industry
- PK phone: `+92`, `03xx`, `92xxxxxxxxxx`
- PK company: "Pvt. Ltd", "Private Limited"
- Competitor: "employer of record", "payroll provider", "EOR service"
- Business setup/visa: "company formation", "trade license", "golden visa"
- Recruitment: "executive search", "headhunting", "CV writing"
- Citizenship: "citizenship by investment", "second passport"
- Placeholder: "coming soon", "lorem ipsum", <100 chars
- Gmail + thin site: freelancer, not a company

### Layer 2: GPT-4o-mini Binary Flags ($0.30 per 5,000)

Run only on domains that passed Layer 0+1 and have website text.

**Prompt asks:**
- `hq_country` — where is HQ?
- `is_hq_in_uae` / `is_hq_in_pakistan` — binary
- `is_competitor` — payroll/EOR/HR provider?
- `is_outsourcing_provider` — sells outsourcing labor?
- `is_enterprise_300plus` — too big?
- `is_construction_realestate_hospitality` — hard-excluded industries only
- `would_need_easystaff` — overall fit (penalty signal, NOT hard gate)
- `company_vertical` — industry classification

**GPT's known failure:** Says `is_hq_in_uae=True` for PK companies with Dubai shelf office. Layer 1 regexp catches this.

**GPT's known limitation:** Says `would_need_easystaff=False` for 89% of companies. Can't validate cultural hypothesis (PK-origin person → likely PK contractors). Used as penalty for non-tech industries, not as gate.

### Layer 3: Verified Exclusion List

Only for companies where GPT says `would_need=True` but the company is clearly wrong (GPT misclassification). Currently 5 domains. Algorithm catches 14/19 automatically.

## Excluded Industries — NARROW LIST

**LEARNING: Keep the exclusion list NARROW.** Real estate, retail, and pet companies actually converted. Only exclude industries where remote contractors are physically impossible.

**Hard exclude:**
- Construction (physical site work)
- Hospitality (hotels, restaurants — on-site staff)
- Oil & gas (rig work)
- Aerospace (regulated, security-cleared)

**Soft exclude (via GPT would_need + non-tech whitelist):**
- Everything else goes through GPT. If GPT says `would_need=False` AND industry is not in tech whitelist → excluded from selection.

**Tech whitelist (cultural hypothesis applies):**
tech, technology, saas, software, it services, digital marketing, digital agency, outsourcing, consulting, fintech, cybersecurity, marketing, creative agency, business services, professional services, design, data services, market research

## Scoring Formula

```
Score = origin(40%) + role(20%) + survived_filters(20%) + outsourcing_signal(10%) + clay(10%)
```

## How to Maximize Output

### 1. Clay Enrichment for Target Companies
For each company in scored output, use Clay People Search (FREE, 0 credits for people without emails) to find up to 3 decision-makers:
- Filter: company domain + country=UAE + role=CFO/COO/HR/CEO/CTO
- This fills the 3-contacts-per-company cap

### 2. Fill Missing Domains
5,707 contacts have no domain. These have LinkedIn URLs. Future: extract company domain from LinkedIn → adds more companies to the analyzable pool.

### 3. Deep Scrape About/Contact Pages
About pages reveal PK addresses that homepages hide. Currently 210 domains deep-scraped, should be all target companies.

## Data Persistence — EVERYTHING CACHED

ALL data in `/scripts/data/` (mounted volume, survives Docker restarts).
NEVER use `/tmp/` in Docker containers.

| File | Contents |
|------|----------|
| `uae_pk_v6_scrape.json` | 10,638 scraped homepages |
| `deep_scrape_v7.json` | 210 about/contact/team pages |
| `uae_pakistan_v8_gpt_flags.json` | 4,996 GPT binary flags |
| `uae_pakistan_v8_company_analysis.csv` | Full company analysis |
| `uae_pakistan_v8_scored.json` | Scored output |

## Quality Verification Protocol

1. Run scoring
2. Pull ALL unique companies from output
3. Read actual website text for each — independent judgment
4. Check: is this a real UAE company? Would they plausibly use PK contractors?
5. Test against qualified leads from reference sheet — zero false negatives allowed
6. Any failure → fix algorithm (not just add to blacklist)
7. Target: 95%+ accuracy

**CRITICAL:** Verification must be INDEPENDENT of the labeling method. Don't check GPT flags against GPT flags.

## Pipeline Scripts

| Script | Purpose | Runtime | Cost |
|--------|---------|---------|------|
| `uae_pk_v7_score.py` | Full scoring pipeline | 10 seconds | $0 |
| `gpt_binary_flags.py` | GPT-4o-mini analysis | 14 min / 5K | $0.30 |
| `deep_scrape.py` | Multi-page scraper | ~80 min / 1K | $0 |
| `make_clay_remaining.py` | Domain list for Clay | 5 seconds | $0 |

## Current UAE-Pakistan Results

- Input: 15,369 contacts, 7,602 unique domains
- Scraped: 7,602/7,602 (100%)
- GPT analyzed: 4,996/6,286 analyzable (79%)
- Output: **579 contacts from 540 companies**
- Accuracy: 97-99% on 558-company review
- Zero false negatives against 30 qualified meeting companies

## Multi-Corridor Execution Plan

Same algorithm, different configs. Run in parallel.

| Corridor | Source Tab | Output Tab | Status |
|----------|-----------|------------|--------|
| UAE-Pakistan | UAE-Pakistan - New Only | UAE-Pakistan v8 Scored | Done (579 contacts) |
| AU-Philippines | AU-Philippines - New Only | AU-Philippines v8 Scored | Ready to run |
| Arabic-SouthAfrica | Arabic-SouthAfrica - New Only | Arabic-SouthAfrica v8 Scored | Ready to run |
