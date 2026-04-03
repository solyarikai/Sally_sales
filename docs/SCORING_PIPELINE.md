# EasyStaff Global — Scoring & Prioritization Pipeline

## Data Flow

```
Clay People Search (language/university/surname)
    ↓
"UAE-Pakistan" tab (ALL gathered contacts)
    ↓
CRM filters out already-contacted
    ↓
"UAE-Pakistan - New Only" (clean pool)
    ↓
Scoring pipeline → NEW output tab "v8 Scored"
    ↓
Clay enrichment: get 3 decision-makers per target company (FREE)
```

## Tab Structure — NEVER OVERWRITE

| Tab | What | Use |
|-----|------|-----|
| `{Corridor}` | ALL contacts from Clay | Source of truth, never modify |
| `{Corridor} - New Only` | Minus already contacted | **Scoring input** |
| `Sheet2` | UNIQUE(Domain) | Domain inventory |
| `{Corridor} v8 Scored` | Pipeline output | Always create NEW tabs |

## ICP — Who We're Looking For

EasyStaff helps companies pay remote contractors cross-border.

**Contact criteria:**
1. Origin from talent country (Urdu speaker / PK university / PK surname)
2. Located in buyer country (UAE / Australia / Gulf)
3. Decision-maker role (CFO, COO, HR, CEO, CTO)

**Company criteria:**
1. HQ in buyer country (NOT talent-country-HQ with buyer-country shelf office)
2. Size 5-200 employees
3. NOT a competitor (payroll/EOR provider)
4. NOT enterprise (300+)
5. Has a working website

**ANY industry can qualify.** Validated against 30 qualified meeting companies:
- Real estate (Block Realty) → has remote admin/marketing contractors
- Pet products (Petzyo, Central Park Puppies) → has remote ecommerce team
- Glass hardware (IGT) → has remote team
- Business setup consultancy (AR Associates) → converted in 5 hours
- Biotech, edtech, fintech, nonprofit → all converted

**Only hard-excluded industries:** construction (physical sites), hospitality (on-site staff), oil & gas (rigs), mining, government.

## Scoring Approach — Layered Via Negativa

**Principle:** Remove shit cheaply FIRST, use GPT only for what's left.

### Layer 0: Cheap Deterministic Filters (FREE, instant, removes ~40%)

Run BEFORE any scraping or GPT. Pure data quality.

| Filter | What it removes | Cost |
|--------|-----------------|------|
| No domain | 37% of contacts — can't verify anything | $0 |
| Location not in buyer country | Contacts in Pakistan/India/other | $0 |
| Enterprise blacklist | FAANG, Big4, airlines, banks, global agencies (90 domains) | $0 |
| Anti-title | Intern, student, freelancer, driver, receptionist | $0 |
| Domain count >10 | 10+ contacts = enterprise | $0 |
| Clay 100+ employees | Enterprise with in-house payroll | $0 |
| .pk/.ph/.za domain | Talent-country company | $0 |

### Layer 1: Website Scraping + Regexp (FREE, Apify proxy)

Scrape homepage. Detect hard signals with regexp.

| Detection | What it catches | Method |
|-----------|-----------------|--------|
| PK-HQ | PK companies with buyer-country office | PK neighborhoods + PK phone + tech industry |
| Competitor | Payroll/EOR providers | "employer of record", "payroll provider" keywords |
| Citizenship programs | Passport sellers | "citizenship by investment", "second passport" |
| Placeholder/dead | Empty, parked, "coming soon" | Text length < 100, known patterns |
| Gmail + thin site | Freelancer, not a company | @gmail.com + <500 chars |

### Layer 2: GPT-4o-mini Binary Flags ($0.30 per 5,000 companies)

Run only on domains that passed Layers 0+1 AND have website text >100 chars.

**Prompt asks:** `hq_country`, `is_hq_in_{buyer}`, `is_hq_in_{talent}`, `is_competitor`, `is_outsourcing_provider`, `is_enterprise_300plus`, `is_construction_realestate_hospitality`, `would_need_easystaff`, `company_vertical`

**GPT failure modes:**
- Says `is_hq_in_uae=True` for PK companies with Dubai address → Layer 1 regexp catches this
- Says `would_need_easystaff=False` for 89% → used as penalty for non-tech, NOT hard gate

**Selection gate:** `would_need=False` AND industry NOT in tech whitelist → excluded from output. This catches training companies, event planners, equipment sellers — but lets through tech/consulting/digital/services where the cultural hypothesis applies.

### Layer 3: Verified Exclusion List (5 domains)

Only for GPT misclassification errors (`would_need=True` for clearly wrong companies). Algorithm catches 14/19 automatically.

## Scoring Formula

```
Score = origin(40%) + role(20%) + survived_filters(20%) + outsourcing_signal(10%) + clay(10%)
```

| Component | Weight | 100 points | 0 points |
|-----------|--------|------------|----------|
| Origin | 40% | Urdu speaker | No PK origin signal |
| Role | 20% | CFO/Payroll | Anti-title |
| Survived filters | 20% | Zero red flags | Any red flag |
| Outsourcing signal | 10% | Website mentions PK ops | No evidence |
| Clay confirmation | 10% | 5-30 PK employees | 100+ (enterprise) |

## Maximizing Output — Clay Enrichment

After scoring, target companies have ~1.1 contacts per company (most have just 1). Clay People Search (FREE, 0 credits for people without emails) can find up to 3 decision-makers per company.

**Process:**
1. Export scored company domains to CSV
2. Run `clay_people_search.js --domains-file {csv} --countries "Pakistan" --headless --auto`
3. Clay finds PK-origin people at these companies in UAE
4. Import new contacts back into scoring pipeline
5. Result: ~3x more contacts from the same target companies

**Why this works:** We already validated the COMPANY is ICP. Now we just need more contacts at that company. Clay searches by company domain + country = finds employees.

## Algorithm Validation

### Against 30 Qualified Meeting Companies

Scraped their websites, ran through exact same algorithm.

| Result | Count | Rate |
|--------|-------|------|
| Correctly passes | 25 | 93% |
| No website (can't test) | 3 | — |
| False negative (fixed) | 2 | 7% → 0% after fix |

**What we learned and fixed:**
- Business setup companies (arassociates.ae) ARE valid customers → removed visa/business-setup keyword exclusion
- Real estate, retail, pet companies convert → narrowed excluded industries to only physical-labor industries
- Any company can have remote contractors for marketing/admin/dev regardless of primary industry

### Against 558 Scored Companies (manual review)

Read website text for every company in output. Independent judgment.

| Result | Count | Rate |
|--------|-------|------|
| GOOD | ~540 | 97% |
| Algorithm-fixable BAD | 14 | 2.5% → fixed |
| GPT misclassification BAD | 5 | 0.9% → blacklisted |

## Data Persistence — EVERYTHING CACHED

ALL data in `/scripts/data/` (mounted volume from repo, survives Docker restarts).

| File | Contents | Shared across corridors |
|------|----------|------------------------|
| `uae_pk_v6_scrape.json` | 10,638 scraped homepages | YES — all corridors share one cache |
| `deep_scrape_v7.json` | 210 about/contact/team pages | YES |
| `{corridor}_v8_gpt_flags.json` | GPT binary flags per corridor | NO — per corridor |
| `{corridor}_v8_company_analysis.csv` | Full company analysis | NO — per corridor |
| `{corridor}_v8_scored.json` | Scored output | NO — per corridor |

## Pipeline Scripts

| Script | What | Time | Cost |
|--------|------|------|------|
| `uae_pk_v7_score.py {corridor}` | Full scoring pipeline | 10s | $0 |
| `gpt_binary_flags.py {corridor}` | GPT analysis | 14 min/5K | $0.30 |
| `deep_scrape.py` | Multi-page scraper | 80 min/1K | $0 |
| `make_clay_remaining.py {corridor}` | Domain list for Clay | 5s | $0 |
| `clay/clay_people_search.js` | Clay People Search | 3 min/200 | $0 |

## Multi-Corridor Execution

Same algorithm, different corridor configs. Website scrape cache shared.

| Corridor | Source Tab | Output Tab | Buyer Signals | Talent Country |
|----------|-----------|------------|---------------|----------------|
| `uae-pakistan` | UAE-Pakistan - New Only | UAE-Pakistan v8 Scored | Dubai, Abu Dhabi, UAE | Pakistan |
| `au-philippines` | AU-Philippines - New Only | AU-Philippines v8 Scored | Sydney, Melbourne, AU | Philippines |
| `arabic-southafrica` | Arabic-SouthAfrica - New Only | Arabic-SouthAfrica v8 Scored | Qatar, Saudi, Bahrain | South Africa |

```bash
# Run all corridors
docker exec leadgen-backend python3 /scripts/uae_pk_v7_score.py uae-pakistan au-philippines arabic-southafrica
```

## Iteration Protocol

1. Score corridor
2. Scrape missing domains
3. GPT-analyze new domains
4. Re-score
5. Verify 100 companies (read website text, independent judgment)
6. Fix algorithm (NOT blacklist) for any failures
7. Re-validate against qualified leads (0 false negatives required)
8. Repeat until 95%+ accuracy
9. Clay enrichment: find 3 contacts per target company
10. Write to new output tab

## Current Results

### UAE-Pakistan (done)
- Input: 15,369 contacts, 7,602 unique domains
- Scraped: 7,602/7,602 (100%)
- GPT analyzed: 4,996 domains
- Output: **672 contacts from ~620 companies**
- Validated: 97%+ accuracy, 0% false negatives against qualified leads
- Next: Clay enrichment → ~1,800 contacts (3 per company)

### AU-Philippines (in progress)
- Input: 6,494 contacts
- Status: scraping + GPT analysis running

### Arabic-SouthAfrica (in progress)
- Input: 8,312 contacts
- Status: scraping + GPT analysis running
