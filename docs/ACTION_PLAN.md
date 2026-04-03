# EasyStaff Global — Contact Prioritization Action Plan

**This document is the SINGLE SOURCE OF TRUTH for any agent working on this task.**

Read `docs/suck.md` BEFORE doing anything. It contains critical rules from past failures.

---

## KPI

2,000 target priority contacts per corridor, max 3 per company, 95%+ self-verified accuracy.

## Corridors

| Corridor | Buyer country | Talent country | Origin signal |
|----------|--------------|----------------|---------------|
| UAE→Pakistan | UAE (Dubai, Abu Dhabi, Sharjah) | Pakistan | Urdu language, PK universities, PK surnames |
| AU→Philippines | Australia (Sydney, Melbourne, Brisbane, Perth) | Philippines | Tagalog language, PH universities, Filipino surnames |
| Arabic→SouthAfrica | Gulf (Qatar, Saudi, UAE, Bahrain, Kuwait, Oman) | South Africa | Afrikaans language, SA universities, SA surnames |

## Current State (Mar 16, 2026)

| Corridor | Source tab | Scored | Verified accuracy | Output tab |
|----------|-----------|--------|-------------------|------------|
| UAE→PK | `UAE-Pakistan - New Only` | 569 | 98.5% (530 companies checked) | `UAE-Pakistan v8 Scored 0315_2311` |
| AU→PH | `AU-Philippines Clay Filipino` | 253 | 94% (50 companies checked) | `AU-Philippines v9 Scored` |
| Arabic→SA | `Arabic-SouthAfrica - New Only` | 141 | 86% → fixed | `Arabic-SouthAfrica v8 Scored` |

**AU-PH and Arabic-SA source tabs have WRONG origin data** (Pakistani contacts, not Filipino/SA). Only the Clay Filipino tab and new Clay SA searches have correct origin.

## Data on Hetzner Server

All in `/scripts/data/` (mounted Docker volume, survives restarts):

| File | What | Size |
|------|------|------|
| `uae_pk_v6_scrape.json` | Website scrape cache, 12,686 domains | 28MB |
| `deep_scrape_v7.json` | About/contact/team pages | 2.9MB |
| `{corridor}_v8_gpt_flags.json` | GPT binary flags per corridor | ~2MB each |
| `{corridor}_v8_scored.json` | Scored output per corridor | ~500KB each |
| `{corridor}_v8_company_analysis.csv` | Full company analysis | ~2MB each |
| `apollo_uae_pk_v2.json` | 2,000 UAE contacts with LinkedIn | new |
| `apollo_au_ph_v2.json` | 850 AU contacts with LinkedIn | partial |
| `{corridor}_clay_all.json` | Consolidated Clay contacts | ~5MB each |
| `backup_before_rescore_*/` | Timestamped backups | varies |

---

## CRITICAL RULES (from docs/suck.md)

### NEVER overwrite Google Sheet tabs
- Every scoring run creates a NEW tab: `{Corridor} Scored {MMDD_HHMM}`
- The scoring script (`uae_pk_v7_score.py`) now enforces this with timestamps
- **NEVER clear existing tab data**
- Check `File → Version history` to verify no data was lost

### NEVER trust output without reading websites yourself
- After scoring, read website text for 100 companies (sample across ALL score ranges)
- Verification must be INDEPENDENT — don't check GPT flags against GPT flags
- Report honest accuracy: "82% — here are the 18 bad ones" not "95%+"

### Fix the ALGORITHM, not the blacklist
- Enterprise companies: blacklist is OK (per user)
- Everything else: find the PATTERN, add detection to the algorithm
- Test fix against qualified leads (reference sheet `17O43ThvMNB5ToqsRjwNn81MYe2tjrNql5W93-H3x008`, tab `Leads`, 58 meetings)
- 0 false negatives required

### Store EVERYTHING
- `/scripts/data/` only, NEVER `/tmp/` in Docker
- Backup before every Clay/Apollo run (timestamped directory)
- Consolidate Clay after every run (`python3 scripts/consolidate_clay.py all`)
- Scored JSON backed up automatically by scoring script

### Verify source data before scoring
- Check origin signal matches the corridor (Urdu for UAE-PK, Tagalog for AU-PH, Afrikaans for Arabic-SA)
- Check 5 sample contacts before full run
- 37% of contacts have no domain — these are excluded from scoring

---

## Gathering Approach: Origin-Based Search

**Core hypothesis:** People originally from the talent country, now C-level in the buyer country, likely have contractors from home country.

### Search dimensions per corridor

| Dimension | UAE→PK | AU→PH | Arabic→SA |
|-----------|--------|-------|-----------|
| Language | Urdu ✅ | Tagalog ✅ | Afrikaans ✅ |
| Universities | LUMS, IBA, NUST, FAST, GIK, NED, Quaid-i-Azam, COMSATS, UET | Ateneo, De La Salle, UP Diliman, UST, Mapua, AIM | UCT, Wits, Stellenbosch, UP, UJ, UKZN, Rhodes |
| Surnames | Khan, Ahmed, Ali, Hussain, Sheikh, Malik, Butt, Iqbal | Santos, Reyes, Cruz, Garcia, Ramos, Aquino, Torres | van der Merwe, Botha, Naidoo, Pillay, Govender |
| Titles | CEO, CFO, COO, CTO, Founder, VP, Director, Head, MD, Owner | Same | Same |

### Tools

**Clay People Search** (FREE, 0 credits for people without emails):
- Runs on Hetzner HOST: `node scripts/clay/clay_people_search.js`
- Flags: `--countries "..." --schools "...|..." --titles --headless --auto`
- Or: `--language "Urdu" --countries "United Arab Emirates"`
- 200 domains per batch, ~3 min per batch
- **SEQUENTIAL ONLY — never parallel Clay sessions**
- After each run: `python3 scripts/consolidate_clay.py all`

**Apollo Scraper** (FREE, no credits for viewing):
- Runs on Hetzner HOST: `node scripts/apollo_scraper.js --url "..." --max-pages 80 --output file.json`
- Login: `danila@getsally.io` / `UQdzDShCjAi5Nil!!`
- Use Apollo UI to set filters, copy URL, pass to scraper
- Gets: name, title, company, LinkedIn URL, orgId
- Does NOT get: company domain, email (need to match domain separately)
- **Can run parallel with Clay** (different service)

### Company size from Clay/Apollo
- Clay and Apollo provide employee counts — use DETERMINISTICALLY
- Don't rely on GPT for enterprise detection when you have actual numbers
- `Company Size` column in sheet, or Clay export `Company Size` field
- >300 employees = enterprise = exclude

---

## Scoring Pipeline

Script: `docker exec leadgen-backend python3 /scripts/uae_pk_v7_score.py {corridor}`

### Layer 0: Cheap deterministic filters (instant, $0)
- No domain → drop
- Location not in buyer country → drop
- Enterprise blacklist (100+ domains) → drop
- Anti-title → drop
- Domain count >10 → drop
- Clay 100+ employees → drop
- .pk/.ph/.za domain → drop

### Layer 1: Website regexp ($0)
- PK-HQ: neighborhoods + phone + company suffix + tech industry → exclude
- Competitor: "employer of record", "payroll provider" → exclude
- Business setup: above-fold "business setup", "company formation" → exclude
- Government: "sovereign", "government entity", "free zone authority" → exclude
- Nonprofit: "not for profit", "nonprofit" → exclude
- Freelancer platform: "hire freelancers", "freelancer platform" → exclude
- Placeholder: "coming soon", broken encoding → exclude

### Layer 2: GPT-4o-mini binary flags ($0.30 per 5,000)
- HQ country, competitor, enterprise, industry, would_need_easystaff
- Run: `docker exec leadgen-backend python3 /scripts/gpt_binary_flags.py {corridor} --model gpt`

### Layer 3: Selection gate
- ANY red flag → excluded from output entirely
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
1. GATHER contacts (Clay + Apollo)
2. Upload to NEW Google Sheet tab
3. SCORE (pipeline, 10 seconds)
4. VERIFY: read website text for 100 companies myself
5. 95%+ accuracy?
   YES → done for this batch
   NO → identify BAD patterns → fix algorithm → re-score → go to step 4
6. Clay enrichment: 3 contacts per scored company
7. Write final output to NEW timestamped Sheet tab
```

**Between each step:**
- Backup all data
- Consolidate Clay exports
- Check source data origin is correct

---

## Execution Order

### Phase 1: UAE→Pakistan
1. ✅ Scored 569 contacts from existing source (98.5% verified)
2. Apollo v2 gathered 2,000 contacts with LinkedIn — 550 matched to domains
3. **TO DO:** Upload 550 Apollo contacts to new tab → score → verify
4. **TO DO:** If <2,000, run more Clay searches (language, surname)
5. **TO DO:** Clay enrichment for scored companies (3 per company)

### Phase 2: AU→Philippines
1. ✅ Clay Filipino university search done (4,190 contacts, 253 scored)
2. **TO DO:** Clay Tagalog language search
3. **TO DO:** Clay Filipino surname search
4. **TO DO:** Apollo AU broad search (re-run, previous killed by OOM)
5. Score all → verify 100 → iterate
6. Clay enrichment

### Phase 3: Arabic→SouthAfrica
1. ✅ Clay SA university search done (102 Gulf-based contacts)
2. **TO DO:** Clay Afrikaans language search (failed to start previously)
3. **TO DO:** Clay SA surname search
4. **TO DO:** Apollo Gulf broad search (re-run, previous killed by OOM)
5. Score all → verify 100 → iterate
6. Clay enrichment

### Parallel execution
```
At any moment: 1 Clay + 1 Apollo running simultaneously = OK
               2 Clay sessions = NOT OK (DDoS risk)

Corridor order: UAE-PK first (most data), then AU-PH, then Arabic-SA
```

---

## Reference: Qualified Leads That Converted

From sheet `17O43ThvMNB5ToqsRjwNn81MYe2tjrNql5W93-H3x008`, tab `Leads`:
- 58 meetings total across all corridors
- Key learnings: real estate, pet companies, business setup consultancies ALL converted
- Only hard-exclude: construction, hospitality, oil & gas, mining, government
- `arassociates.ae` (business setup) converted in 5 hours — don't blanket-exclude business setup
- Company sizes that converted: 1 to 40+ employees (sweet spot 5-50)

---

## Scripts Reference

| Script | What | Where to run |
|--------|------|-------------|
| `scripts/uae_pk_v7_score.py` | Scoring pipeline | Docker: `docker exec leadgen-backend python3 /scripts/uae_pk_v7_score.py {corridor}` |
| `scripts/gpt_binary_flags.py` | GPT analysis | Docker: `docker exec leadgen-backend python3 /scripts/gpt_binary_flags.py {corridor} --model gpt` |
| `scripts/deep_scrape.py` | Multi-page website scraper | Docker |
| `scripts/consolidate_clay.py` | Merge & dedup Clay exports | Host: `python3 scripts/consolidate_clay.py all` |
| `scripts/clay_enrich_targets.py` | Generate domain list for Clay enrichment | Docker |
| `scripts/clay/clay_people_search.js` | Clay People Search automation | Host: `node scripts/clay/clay_people_search.js` |
| `scripts/apollo_scraper.js` | Apollo UI scraper | Host: `node scripts/apollo_scraper.js --url "..." --max-pages N --output file.json` |

---

## Google Sheet Structure

**Sheet ID:** `1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU`

| Tab | What | DO NOT TOUCH |
|-----|------|-------------|
| `UAE-Pakistan` | All gathered contacts | ✅ |
| `UAE-Pakistan - New Only` | Minus already contacted | ✅ source for scoring |
| `UAE-Pakistan Priority 2000` | Original operator list | ✅ DESTROYED by mistake, restore from version history |
| `AU-Philippines` / `- New Only` | All / clean pool | ✅ but WRONG ORIGIN (PK not Filipino) |
| `Arabic-SouthAfrica` / `- New Only` | All / clean pool | ✅ but WRONG ORIGIN (PK not SA) |
| `AU-Philippines Clay Filipino` | Filipino-origin contacts from Clay | ✅ correct origin for AU-PH |
| `Sheet2` | UNIQUE(Domain) | ✅ |
| `* v8 Scored *` | Pipeline output | Created by scoring script |

**New tabs from scoring always have timestamp:** `{Corridor} Scored {MMDD_HHMM}`
