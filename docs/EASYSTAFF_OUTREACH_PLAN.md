# EasyStaff Global Outreach — Monday Launch Plan

## Context

4,000 contacts need to be ready for Monday morning outreach across 3 payout corridors. 33 email inboxes × 50 emails/day = 1,650/day. 2-email sequence (Mon + Wed). Split: 2,000 UAE→Pakistan + 1,000 AU→Philippines + 1,000 Arabic→South Africa.

The core challenge: identifying companies in the BUYER country (UAE/AU/Gulf) that pay CONTRACTORS in the TALENT country (Pakistan/Philippines/SA). Contractors are invisible to both Clay and website scraping — they don't list the company on LinkedIn and companies don't advertise contractor relationships. So we score by **excluding bad fits** (via negativa), not confirming good ones.

---

## Red Flags — Universal Exclusion Criteria

Every contact is evaluated against these. Any red flag = excluded or heavily penalized.

| # | Red Flag | How to detect | Why it's bad |
|---|----------|---------------|-------------|
| 1 | **Company HQ in talent country** | `.pk`/`.ph`/`.za` domain; website says "based in Karachi/Manila/Johannesburg"; `(Pvt) Ltd` suffix | They pay locally — don't need cross-border payroll |
| 2 | **Enterprise** | Clay shows 100+ employees in talent country; blacklisted domain (74 domains: banks, Big4, FAANG, airlines); 10+ contacts from same domain in our data | Already has in-house payroll/HR |
| 3 | **Irrelevant industry** | Website text: construction, real estate, property, hotel, restaurant, hospitality, tourism, interior design | These industries don't use remote tech contractors |
| 4 | **Contact NOT from talent country origin** | Origin score < 8 (not Urdu/Filipino/SA-origin); no name match reason | No cultural network = no reason to have PK/PH/SA contractors |
| 5 | **Anti-title** | intern, student, freelancer, assistant, driver, receptionist, security guard | Not a decision-maker |
| 6 | **Talent country in country list only** | Website lists 20+ countries including Pakistan — just a global company listing | No actual operations there |
| 7 | **Company already has formal talent-country office** | Website says "office in Karachi/Manila"; Clay shows 50-100 PK employees | Formal office = already has payroll set up |
| 8 | **Placeholder/empty website** | Lorem ipsum, "coming soon", parked domain, < 100 chars text | Can't verify anything about the company |

---

## Positive Signals — Boosting Criteria

After excluding red flags, rank remaining contacts by:

| Signal | Weight | Source | Why |
|--------|--------|--------|-----|
| **Pakistani/Filipino/SA-origin decision-maker in buyer country** | 40% | Clay origin data (Urdu speaker=100, PK university=90, surname=80) | The PRIMARY hypothesis — cultural network = likely has contractors from home country |
| **Role authority** | 20% | Contact title | CFO/Payroll=100, COO=90, HR=85, CEO/Founder=70, CTO=50 |
| **Company NOT excluded** (passed all red flags) | 20% | Website + Clay combined | Via negativa — surviving all filters IS the signal |
| **Website mentions outsourcing/contractors** | 10% | Website keyword | Explicit buying signal |
| **Clay confirms 5-30 talent-country employees** | 10% | Clay People Search | Confirmed growing team, may need payroll |

---

## Data Sources — What Each Tells Us (and what it CAN'T)

### Clay People Search (FREE, 0 credits)

**How it works**: Puppeteer opens Clay UI, types up to 200 company domains into Companies filter, sets country=Pakistan/Philippines/SA, creates a table, reads results via internal API.

**One batch = one session**: types domains → applies filter → saves table → reads data → closes tab. ~2-3.5 min per 200 domains.

**Safety**: stealth plugin, randomized typing (15-55ms/char), humanDelay (800-2500ms between actions), fresh tab per batch, session cookie persistence. **NEVER run parallel sessions** — one at a time, sequential.

**What it finds**: People on LinkedIn who list this company AND are located in the talent country = formal employees, NOT contractors.

**Key insight**: Clay 0 ≠ no contractors. It means no LinkedIn-visible employees. Contractors are invisible to Clay.

**Useful for**: EXCLUDING enterprises (100+ employees) and CONFIRMING sweet spot (5-30 employees).

**Tested**: 500 UAE-PK domains → 30 companies had PK employees, 470 had zero. Of 190 website-PK-mentions, only 14 (7%) confirmed by Clay. Clay found 16 companies website missed entirely.

### Website Scraping (FREE, Apify proxy)

**How it works**: httpx async with Apify residential proxy, 20 concurrent, 10s timeout. Extracts title, meta description, body text (3000 chars max).

**Pages scraped per domain**:

| Page | URL patterns | What we find |
|------|-------------|-------------|
| **Homepage** | `https://{domain}` | Company overview, industry keywords |
| **About** | `/about`, `/about-us`, `/about-us/` | HQ location, team size, founding story |
| **Contact** | `/contact`, `/contact-us` | Physical addresses, office locations, phone numbers |
| **Team** | `/team`, `/our-team`, `/people` | Employee count, team structure |
| **Locations** | `/locations`, `/offices`, `/global` | Office locations by country |

**Speed**: Homepage only: ~200 domains/min. Multi-page (5 pages): ~20 domains/min.

**Key insight**: 93% of "Pakistan mentioned on website" is noise (country lists, blogs). Only explicit office/ops mentions matter. Contact/About pages are far more reliable than homepage for HQ detection.

**Useful for**: EXCLUDING PK-HQ companies, irrelevant industries, detecting "outsourcing/contractor" buying signals.

### What NEITHER source can confirm

- Whether company has **contractors** in talent country (invisible to both — contractors don't list company on LinkedIn, companies don't advertise contractor relationships)
- Whether company currently uses Deel/Wise/Upwork for payments (only revealed on sales calls)
- The **cultural hypothesis** (Pakistani CEO → PK contractors) cannot be validated before outreach

### How they correspond to each other

| Website says | Clay finds | Interpretation for EasyStaff |
|-------------|-----------|------------------------------|
| "Based in Pakistan" | 50+ PK employees | **EXCLUDE** — PK company, pays locally |
| "Office in Dubai AND Pakistan" | 20-50 PK employees | **CAUTION** — formal PK office, might have payroll |
| "Outsourcing to Pakistan" | 5-20 PK employees | **GOOD** — active PK ops, growing, needs payroll |
| No PK mention | 5-30 PK employees | **BEST** — hidden PK workforce, likely contractors |
| No PK mention | 0 PK employees | **NEUTRAL** — unknown, rely on cultural hypothesis |
| PK in country list | 0 PK employees | **IGNORE** — noise, no signal |

---

## Timing Estimates (based on measured performance)

| Step | Duration | Notes |
|------|----------|-------|
| **Website scraping** (homepage, new domains) | 25 min per 5,000 | Apify proxy, 20 concurrent |
| **Website deep-scrape** (5 pages, top 300) | 15 min | Sequential per domain |
| **Clay People Search** (per batch of 200) | ~2.5-3.5 min | Human-like, sequential |
| **Clay total** (5,000 domains, one corridor) | ~70 min | 25 batches, sequential only |
| **Scoring** (all contacts, one corridor) | 15 seconds | Deterministic, no API calls |
| **Google Sheet write** | 30 seconds per corridor | Batch 500 rows at a time |

### Cost: ~$0.50-1.00
- Website scraping: Apify proxy (existing plan) — $0
- Clay: 0 credits (people without emails are free) — $0
- GPT-4o-mini: binary flag detection on ~3,000-5,000 websites — ~$0.50-1.00

### GPT-4o-mini — Binary Flag Detection (not scoring!)

**What went wrong before**: Asked "rate fit 0-100" → GPT hallucinated (87% scored >=70). NEVER ask for numerical scores.

**What works**: Ask BINARY YES/NO questions. GPT-4o-mini is excellent at classification when constrained.

**1 prompt (not 2)** — all questions about same website text, no need to split:

```
Classify this company. Answer in JSON:
{
  "red_flags": {
    "hq_in_{talent_country}": true/false,
    "has_{talent_country}_office": true/false,
    "is_construction_realestate": true/false,
    "is_hospitality_tourism": true/false,
    "is_enterprise_500plus": true/false
  },
  "green_flags": {
    "mentions_outsourcing_bpo": true/false,
    "mentions_contractors_freelancers": true/false,
    "mentions_remote_teams": true/false,
    "has_{talent_country}_workforce": true/false
  },
  "company_vertical": "tech|fintech|saas|staffing|outsourcing|...|other",
  "what_they_do": "1 sentence",
  "employee_estimate": number or null,
  "reasoning": "1 sentence why they would/wouldn't need EasyStaff"
}
```

**Why 1 prompt**: all questions reference the same website text. Splitting doubles cost for zero quality gain.

**Why binary works**: "Is this construction?" = YES for ALEC (keyword matching said "fintech" because "payment" appeared). No room for hallucination.

**Cost**: ~$0.0002/company. 5,000 companies = **$1.00**. 25 concurrent, ~2 min.

**Results cached** in `/tmp/{corridor}_v7_gpt_flags.json` — survives re-runs.

---

## Capacity Plan

| Metric | Value |
|--------|-------|
| Email accounts | 33 |
| Sends per account per day | 50 |
| Daily capacity | 1,650 contacts |
| Sequence length | 2 emails (Day 1 + Day 3) |
| Mon-Wed unique touches | ~3,300 |
| Mon-Fri unique touches | ~4,000 (follow-ups use slots) |

### Corridor Split

| Corridor | Contacts | % of capacity | Rationale |
|----------|----------|--------------|-----------|
| **UAE → Pakistan** | 2,000 | 50% | Strongest corridor: 18% interest rate, fastest close (5h), proven ICP |
| **AU → Philippines** | 1,000 | 25% | Solid corridor: 4% reply rate, outsourcing culture strong in AU |
| **Arabic → South Africa** | 1,000 | 25% | Testing corridor: 26% interest in Qatar→SA (from conversation data) |

---

## Execution Steps

### PHASE 1: UAE-Pakistan only (validate quality before other corridors)

#### Step 1a: Scale Clay for UAE-PK remaining domains (~70 min)
Already searched 500 domains. Need remaining ~4,500.
- 23 batches × 200 domains × ~3 min = ~70 min
- **SEQUENTIAL ONLY** — never parallel Clay sessions (DDoS risk)
- Each batch: open tab → type domains → filter Pakistan → save table → read → close tab
- Human-like delays already built in (15-55ms typing, 800-2500ms between actions)
- Expected additional finds: ~20-30 companies (6% hit rate × lower-scored domains)

#### Step 1b: Website deep-scrape for top 300 UAE-PK companies (~15 min)
5 pages per domain: homepage, about, contact, team, locations.
1,500 requests total. Sequential per domain, 20 domains concurrent. ~15 min.

#### Step 1c: GPT-4o-mini binary flag analysis (~5 min, ~$0.50)
Run binary flag detection on all companies with website text:
```
python3 scripts/gpt_binary_flags.py uae-pakistan
```
- Classifies each company: red flags + green flags + vertical + reasoning
- 25 concurrent, ~$0.0002/company, results cached in `/tmp/uae_pakistan_v7_gpt_flags.json`
- Survives re-runs — change scoring weights without re-analyzing

#### Step 1d: Rebuild scoring with via-negativa approach (~15 sec)
```
python3 scripts/uae_pk_v7_score.py uae-pakistan
```
- Loads all data sources: scrape cache + deep scrape + GPT flags + Clay employees
- Applies all 8 red flags using GPT flags + Clay data + keyword fallback
- Scores by: origin (40%) + role (20%) + survived-filters (20%) + website outsourcing (10%) + Clay confirmation (10%)
- Writes to "UAE-Pakistan Priority 2000" tab in Google Sheet

#### Step 1e: Quality review (~10 min)
- Manually verify top 20 contacts
- Check no excluded companies leaked through
- Count contacts per confidence tier
- **Decision gate**: if quality looks good → proceed to AU-PH and Arabic-SA

### PHASE 2: Other corridors (only after Phase 1 quality validated)

#### Step 2a: Clay for AU-PH domains (~60 min)
~3,700 domains, 19 batches, sequential. **AFTER UAE-PK Clay is fully done.**

#### Step 2b: Clay for Arabic-SA domains (~60 min)
~3,800 domains, 19 batches, sequential. **AFTER AU-PH Clay is fully done.**

#### Step 2c: Score + select AU-PH and Arabic-SA (~10 min)
AU-PH: top 1,000. Arabic-SA: top 1,000.

### Step 3: Upload to SmartLead campaigns (manual, not automated)
User will review sheets and trigger campaign creation through the platform UI.

---

## What we're NOT doing (and why)

| Skipped | Why |
|---------|-----|
| GPT-4o-mini **fit scores** | Hallucinated — 87% scored >=70. Binary flags only. |
| Keyword-only industry classification | "payment" on construction sites = false fintech label. GPT vertical replaces this. |
| Parallel Clay sessions | DDoS risk — always sequential, one corridor at a time |
| Apollo enrichment | No credits |
| CRM upload | User explicitly said don't upload until told |

---

## Files

| File | Purpose |
|------|---------|
| `scripts/uae_pk_v7_score.py` | Main scoring pipeline — via negativa, integrates Clay + GPT + deep scrape |
| `scripts/deep_scrape.py` | Multi-page website scraper (5 pages per domain) |
| `scripts/gpt_binary_flags.py` | GPT-4o-mini binary flag analyzer (~$0.0002/company) |
| `scripts/make_clay_remaining.py` | Generates domain list for Clay (remaining unsearched) |
| `scripts/clay/clay_people_search.js` | Clay People Search automation (Puppeteer) |
| `docs/EASYSTAFF_GLOBAL_SEQUENCE.md` | Strategy documentation |
| `docs/EASYSTAFF_OUTREACH_PLAN.md` | This plan |
| `/tmp/uae_pk_v6_scrape.json` (server) | 8,564 scraped websites (19MB) |
| `/tmp/deep_scrape_v7.json` (server) | Multi-page scrape cache |
| `/tmp/{corridor}_v7_gpt_flags.json` (server) | GPT binary flags cache per corridor |
| `/tmp/{corridor}_v7_company_analysis.csv` (server) | Per-company analysis with signals |
| `/tmp/{corridor}_v7_scored.json` (server) | Selected contacts per corridor |
| `scripts/clay/exports/people_*.json` (server) | Clay PK/PH/SA employee data |
| Google Sheet `1pivHqk...` | Output: "Priority 2000/1000" tabs per corridor |

---

## Data Accumulation — Track Everything for Reuse

Every analysis result is persisted so future runs start from accumulated knowledge, not from scratch.

| Data | Location | Format | Size | Reuse |
|------|----------|--------|------|-------|
| **Website scrape cache** | server `/tmp/uae_pk_v6_scrape.json` | `{domain: {status, title, desc, text}}` | 19MB, 8,564 domains | New runs load cache first, only scrape uncached domains |
| **Deep scrape (multi-page)** | server `/tmp/deep_scrape_v7.json` | `{domain: {pages: {/about: text, /contact: text, ...}}}` | Per-page text | Richer HQ/address detection from about/contact pages |
| **Clay PK employees** | server `scripts/clay/exports/people_*.json` | `[{Full Name, Company Domain, Location, Job Title}]` | 10,048 records | Aggregate by domain → PK employee count per company |
| **Company analysis CSV** | server `/tmp/{corridor}_v7_company_analysis.csv` | 18 columns per company | 9,838 companies (UAE-PK) | ALL companies analyzed, not just selected 2,000 — re-filter without re-analyzing |
| **Scored contacts JSON** | server `/tmp/{corridor}_v7_scored.json` | Selected contacts with full reasoning | 2,000 per corridor | Full audit trail per contact |
| **Google Sheets output** | `1pivHqk...` Priority tabs | Score, signals, evidence, reasoning per contact | 2,000/1,000 rows | Operator-facing, auditable |

### What makes re-runs efficient
1. Website cache is **additive** — new domains get scraped, existing ones read from cache
2. Clay results **accumulate** — each batch adds to knowledge base
3. Scoring is **deterministic** (15 seconds) — change weights/red flags, re-score instantly
4. Analysis CSV has **ALL companies** — re-filter without re-analyzing
5. Evidence column preserves **raw website snippets** — re-evaluate without re-scraping

### Future data to accumulate
- **Outreach results**: which contacts replied, bounced, booked meetings
- **Feedback loop**: contacts that converted → their company profile = training data for scoring
- **Per-company "contacted" flag**: avoid re-outreaching same company across corridors

---

## Verification

1. Check top 20 contacts per corridor — are they real Pakistani/Filipino/SA decision-makers in buyer country?
2. Check that NO excluded companies appear (no .pk domains, no enterprises, no construction)
3. Verify Clay data merged correctly (companies with Clay PK employees get boost)
4. Count contacts per tier: how many have Clay confirmation vs website signal vs origin-only?
5. Spot-check 5 random companies: visit their website, verify the scoring makes sense
