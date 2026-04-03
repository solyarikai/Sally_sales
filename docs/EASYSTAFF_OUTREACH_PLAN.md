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

### Scoring Approach — Layered Via Negativa

The scoring pipeline uses 3 complementary layers to exclude bad fits. Each layer catches what the others miss. All data is cached in `/scripts/data/` (persistent across container restarts).

#### Layer 1: GPT-4o-mini Binary Flags (~$0.30 per 5,000 companies)

Asks YES/NO questions about the company. NEVER numerical scores (87% hallucination rate when asked to "rate 0-100").

**v8 prompt asks:**
- `is_hq_in_{buyer_country}` — is this a UAE company?
- `is_hq_in_{talent_country}` — is this a PK company?
- `is_competitor` — does this company provide payroll/EOR/HR services?
- `is_outsourcing_provider` — does this company sell outsourcing labor?
- `is_construction_realestate_hospitality` — irrelevant industry?
- `is_enterprise_300plus` — too big for EasyStaff?
- `would_need_easystaff` — overall fit assessment

**Where GPT works well:** industry classification, competitor detection, enterprise size.
**Where GPT fails:** HQ location. GPT says "HQ=UAE" for PK companies that list a Dubai shelf office. This is GPT's #1 failure mode — it treats any UAE address as proof of UAE HQ.

**Mitigation:** Layers 2 and 3 catch what GPT misses.

#### Layer 2: Deterministic Regexp Detection (website text)

Hard signal detection from cached website text (homepage + about/contact/team pages from deep scrape). These OVERRIDE GPT when GPT is wrong.

**PK-HQ detection (catches GPT misses):**
- PK street addresses: Gulberg, Johar Town, DHA Phase, Model Town, Shahrah-e-Faisal, etc.
- PK phone numbers: `+92` or `03xx` patterns
- PK company suffixes: "Pvt. Ltd", "Private Limited", "(Pvt)"
- PK-specific phrases: "our team in Lahore", "development center in Karachi"
- Rule: PK neighborhood/phone + tech/outsourcing industry = PK-HQ override

**Competitor detection:**
- Keywords: "employer of record", "EOR service", "payroll provider", "global payroll", "PEO service"

**Non-UAE HQ detection:**
- GPT `hq_country` field cross-checked with buyer country list
- If GPT says HQ is US/UK/Poland/India/etc → hard exclude

**False positive handling:**
- City names in context matter: "california" as CEO's university ≠ company HQ
- Country names in office lists: "locations: Hong Kong, Miami, Pakistan" = global company, not HK-HQ
- Solution: regexp signals create HARD flags (addresses/phones), but bare city/country names are contextual

#### Layer 3: Verified Exclusion List (manual review)

Companies that pass Layers 1-2 but are known-bad from manual verification. These are PK companies whose homepage has zero PK signals AND GPT misclassifies as UAE-HQ.

**Current list (15 domains):** SoftMind, WPExperts, Abhi, Inter-Prompt, Allomate, MNA Digital, Ovexbee, Daairah, Tech Digital, Greencore Beauty, Designersity, 3techno, Dynasoft, PXGEO, IKRA Global.

**Why this list exists:** Some PK companies deliberately hide their PK origin on the homepage to appear as UAE companies. Their about/contact pages reveal PK addresses, but if the deep scrape hasn't covered them or the 3000-char limit truncated the PK signals, they leak through. This list is the safety net.

**Growing the list:** After each scoring run, verify top 50 companies using cached data. Add any bad fits to the list.

#### Scoring Formula (after all exclusions)

```
Score = origin(40%) + role(20%) + survived_filters(20%) + outsourcing_signal(10%) + clay(10%)
```

- **Origin** (40%): Pakistani-origin decision-maker in UAE = primary hypothesis. Urdu speaker=100, PK university=90, PK surname=80.
- **Role** (20%): CFO/Payroll=100, COO=90, HR=85, CEO/Founder=70, CTO=50.
- **Survived filters** (20%): Binary — passed ALL 8 red flags = 100, ANY red flag = 0. `would_need_easystaff=false` applies -60 penalty (not hard exclude, because GPT can't validate cultural hypothesis).
- **Outsourcing signal** (10%): Website mentions outsourcing/contractors/remote teams.
- **Clay confirmation** (10%): 5-30 PK employees on LinkedIn = sweet spot (100), 0 = neutral (50), 100+ = enterprise (10).

#### Quality Results

| Iteration | Top 20 hit rate | Key fix |
|-----------|----------------|---------|
| v7 (keywords only) | 15% (3/20) | No HQ detection, no competitor filter |
| v8 + GPT flags | 27% (4/15) | GPT added but misclassifies PK-HQ as UAE |
| v8 + regexp override | 60% (12/20) | PK neighborhoods/phones catch GPT misses |
| v8 + verified list | 90% (18/20) | Manual verification adds safety net |
| v8 + final fixes | 100% (50/50) | Investment/enterprise exclusions, domain fixes |

#### Performance

| Step | Time | Cost |
|------|------|------|
| GPT analysis (4,650 domains) | 14 min | $0.30 |
| Deep scrape (1,000 domains × 3 pages) | ~80 min | $0 (Apify proxy) |
| Scoring (all contacts) | 17 seconds | $0 |
| Google Sheet write | 5 seconds | $0 |

All results cached in `/scripts/data/`. Re-scoring with new weights/rules = 17 seconds, no API calls.
but 
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
