# EasyStaff Global — Action Plan

## KPI: 2,000 ICP-matched contacts per corridor, max 3 per company, 95%+ accuracy

---

## Core Hypothesis

**People originally from the talent country, now holding C-level positions in the buyer country, likely have contractors from their home country.** This is the cultural network hypothesis — the basis for all contact gathering.

---

## Approach 1: Origin-Based Contact Search (PRIMARY — exhaust first)

Find decision-makers who are ORIGINALLY FROM the talent country but NOW LOCATED in the buyer country.

### Search Dimensions

| Dimension | UAE→Pakistan | AU→Philippines | Arabic→SouthAfrica |
|-----------|-------------|----------------|-------------------|
| **Language** | Urdu ✅ (specific) | Tagalog ✅ (specific) | Afrikaans ✅ (specific, not English) |
| **Universities** | LUMS, IBA Karachi, NUST, FAST, GIK, NED, Quaid-i-Azam, COMSATS, UET Lahore, Lahore Uni of Mgmt Sciences | Ateneo de Manila, De La Salle, UP Diliman, UST, Mapua, AIM, Adamson, FEU, DLSU | UCT, Wits, Stellenbosch, UP, UJ, UKZN, Rhodes, UWC, UNISA, Durban UT |
| **Surnames** | Khan, Ahmed, Ali, Hussain, Sheikh, Malik, Butt, Iqbal, Chaudhry, Qureshi, Rehman, Syed, Zafar, Ashraf, Mirza | Santos, Reyes, Cruz, Garcia, Ramos, Aquino, Torres, Flores, Villanueva, Bautista, Del Rosario, Gonzales, Mendoza | Van der Merwe, Botha, Naidoo, Pillay, Govender, Singh, Patel, Moodley, Ndlovu, Zulu, Dlamini, Joubert |
| **Buyer location** | UAE, Dubai, Abu Dhabi, Sharjah | Australia, Sydney, Melbourne, Brisbane, Perth | Qatar, Saudi Arabia, UAE, Bahrain, Kuwait, Oman |
| **Titles** | CEO, CFO, COO, CTO, Founder, VP, Director, Head, Managing Director, Owner, Partner | Same | Same |

### Why This Works
- Language filter: Urdu/Tagalog/Afrikaans speakers are RARE in buyer countries → high signal
- University filter: alumnus of PK/PH/SA university + in UAE/AU/Gulf → strong origin signal
- Surname filter: backup signal when language/university not available
- C-level filter: only decision-makers who can approve EasyStaff

### Where It Doesn't Work
- English as language → useless (everyone speaks English)
- Very common surnames that overlap with other origins → noise
- People who went to buyer-country universities (no origin signal)

### Execution: 2 parallel streams per corridor

**Stream A: Clay People Search** (FREE, 0 credits for people without emails)
- Sequential batches of 200 domains or filter-based searches
- Runs on Hetzner host: `node scripts/clay/clay_people_search.js`
- ~3 min per batch
- Output: JSON with name, title, company, domain, location, LinkedIn

**Stream B: Apollo Scraper** (FREE, no credits for viewing search results)
- Headless Puppeteer on Hetzner: `node scripts/apollo_scraper.js`
- 25 contacts per page, ~3 min per page
- Can filter by: location, title, company size, keywords
- Output: JSON with name, title, company, location

**Parallel execution:** Clay and Apollo CAN run simultaneously (different services). But only ONE Clay session at a time (DDoS risk). Apollo can run independently.

---

## Approach 2: Company-Based Search (BACKLOG — after Approach 1 exhausted)

Find companies in buyer country that have employees in talent country (using Clay TAM search), then find decision-makers at those companies.

**Why backlog:** Approach 1 directly finds the right PEOPLE. Approach 2 finds companies first, then needs a second step to find people. More steps = more time. But useful for expanding the pool after Approach 1 is exhausted.

---

## Approach 3: Apollo Broad Search + Scoring (BACKLOG)

Search Apollo for ALL decision-makers in buyer country at companies 1-200 employees. Don't filter by origin. Let the scoring pipeline prioritize based on company website analysis.

**Why backlog:** No origin signal = lower precision. But massive volume (22K+ results for UAE alone). Good for filling remaining gaps after Approaches 1-2.

---

## Prioritization Pipeline (applied to ALL gathered contacts)

Already built and validated at 95%+ accuracy. 10-second scoring, $0 for re-runs.

### Layer 0: Cheap deterministic filters (instant, $0)
- No domain → drop
- Location not in buyer country → drop
- Enterprise blacklist (90+ domains) → drop
- Anti-title (intern, student, freelancer) → drop
- .pk/.ph/.za domain → drop

### Layer 1: Website scraping + regexp ($0, Apify proxy)
- PK-HQ: neighborhoods + phone + company suffix + tech industry
- Competitor: "employer of record", "payroll provider" keywords
- Business setup: title/above-fold detection
- Recruitment: text keywords
- Broken/placeholder sites

### Layer 2: GPT-4o-mini binary flags ($0.30 per 5,000)
- HQ country, competitor, enterprise, industry, would_need_easystaff
- Only for domains with website text that passed Layer 0+1

### Layer 3: Selection gate
- ANY red flag → excluded from output
- No domain → excluded
- No website → excluded
- Non-tech industry + GPT no-need → excluded
- Max 3 contacts per company

### Scoring formula
```
origin(40%) + role(20%) + survived_filters(20%) + outsourcing_signal(10%) + clay(10%)
```

---

## Do-Check-Improve Loop

```
GATHER (Clay + Apollo)
    ↓
SCORE (pipeline, 10 seconds)
    ↓
VERIFY (I read 100 companies' website text myself)
    ↓
 95%+ ? → YES → WRITE TO SHEET → CLAY ENRICHMENT (3/company)
    ↓ NO
FIX ALGORITHM (not blacklist)
    ↓
RE-SCORE → back to VERIFY
```

**Rules:**
- Verification is INDEPENDENT of scoring method (no circular checking)
- Fix algorithm for patterns, not individual domains
- Check against qualified leads after each fix (0 false negatives required)
- Store EVERYTHING — every scrape, GPT call, Clay result, Apollo result

---

## Execution Plan

### Phase 1: UAE→Pakistan (812/2,000)

**Already done:**
- 575 scored contacts from 15,369 source
- +237 Clay enrichment = 812 total
- 95%+ accuracy after 3 iterations

**Next steps:**
1. Apollo scraper: decision-makers at 534 scored target companies
   - URL with org domains filter + CEO/CFO/COO/CTO/VP/Director
   - Expected: ~500 new contacts at validated companies
2. Score new contacts → verify 100 → fix → iterate
3. If <2,000: Apollo broad search (all UAE, 1-200 employees)
4. Score → verify → iterate
5. Clay enrichment for final scored companies (3/company)

### Phase 2: AU→Philippines (616/2,000, NEEDS NEW DATA)

**Problem:** Current data has PK-origin contacts (wrong corridor)

**Steps:**
1. **Clay searches** (run on Hetzner, sequential):
   - University search: Ateneo, De La Salle, UP Diliman, UST, Mapua, AIM → location=Australia
   - Language search: Tagalog speakers → location=Australia
   - Surname search: Santos, Reyes, Cruz, Garcia → location=Australia, title=CEO/CFO/COO/etc.
2. **Apollo scraper** (parallel with Clay):
   - Filter: location=Australia, titles=CEO/CFO/COO, company size=1-200
   - Keyword in title: "Filipino" or search by Filipino surnames
3. Import all contacts to Google Sheet new tab: `AU-Philippines v9 Raw`
4. Score → verify 100 → fix → iterate
5. Clay enrichment (3/company)

### Phase 3: Arabic→SouthAfrica (152/2,000, NEEDS NEW DATA)

**Steps:**
1. **Clay searches:**
   - University search: UCT, Wits, Stellenbosch, UP, UJ → location=Qatar/Saudi/UAE/Bahrain/Kuwait/Oman
   - Language search: Afrikaans speakers → location=Gulf
   - Surname search: van der Merwe, Botha, Naidoo, Pillay → location=Gulf, title=CEO/CFO/COO
2. **Apollo scraper** (parallel with Clay):
   - Filter: location=Gulf states, titles=decision-makers, company size=1-200
3. Import → Score → verify → iterate → Clay enrichment

### Parallel Execution Strategy

```
TIME →
     ┌─ Clay: UAE-PK university search ──┐
     │  Apollo: UAE-PK target companies   │
     ├─ Clay: AU-PH university search ───┤
     │  Apollo: AU-PH broad search       │
     ├─ Clay: Arabic-SA university search┤
     │  Apollo: Arabic-SA broad search   │
     └───────────────────────────────────┘

Rule: 1 Clay + 1 Apollo at same time = OK
      2 Clay sessions = NOT OK (DDoS risk)
      2 Apollo sessions = probably OK (different browser instances)
```

**Sequence:**
1. Start Apollo UAE-PK + Clay UAE-PK university → wait for both
2. Score UAE-PK → verify → fix
3. Start Apollo AU-PH + Clay AU-PH university → wait for both
4. Score AU-PH → verify → fix
5. Start Apollo Arabic-SA + Clay Arabic-SA university → wait for both
6. Score Arabic-SA → verify → fix
7. Clay enrichment for all scored companies (sequential)

---

## Data Persistence

ALL in `/scripts/data/` on Hetzner:

| File | What |
|------|------|
| `uae_pk_v6_scrape.json` | Website cache (12K+ domains, shared) |
| `deep_scrape_v7.json` | Multi-page scrape cache (shared) |
| `{corridor}_v8_gpt_flags.json` | GPT flags per corridor |
| `{corridor}_v8_scored.json` | Scored output per corridor |
| `{corridor}_v8_company_analysis.csv` | Full analysis per corridor |
| `apollo_{corridor}.json` | Apollo scraper results per corridor |
| `{corridor}_clay_enrich_domains.csv` | Domains for Clay enrichment |
| `clay/exports/people_*.json` | Clay results (shared, append-only) |

---

## Quality Gates

- 95%+ accuracy on 100 companies before writing to Google Sheet
- Verification: read website text myself, independent of scoring
- 0% false negatives against 30 qualified meeting companies
- Algorithm handles patterns, blacklist only for GPT misclassification (5 domains)
- Each corridor verified independently
