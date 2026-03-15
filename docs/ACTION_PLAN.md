# EasyStaff Global — Action Plan to 2,000 Contacts Per Corridor

## KPI: 2,000 ICP-matched contacts per corridor, max 3 per company, 95%+ accuracy

## Current State

| Corridor | Scored | +Clay | Total | Target | Gap |
|----------|--------|-------|-------|--------|-----|
| UAE→Pakistan | 575 | +237 | 812 | 2,000 | 1,188 |
| AU→Philippines | 310 | +306 | 616 | 2,000 | 1,384 |
| Arabic→SouthAfrica | 149 | +3 | 152 | 2,000 | 1,848 |

## The Approach

### Step 1: Gather MORE contacts (expand the pool)

**Problem:** Current source data has 15K/6.5K/8.3K contacts, but after scoring only 575/310/149 pass. We need more raw contacts, especially with correct origin signals.

**Data sources (all FREE, no credits):**

| Source | What it gets | How | Speed |
|--------|-------------|-----|-------|
| Apollo scraper | Decision-makers at ANY company | Headless Puppeteer on Hetzner, 25/page | ~3 min/page |
| Clay People Search | People at SPECIFIC companies | Puppeteer automation, 200 domains/batch | ~3 min/batch |
| Clay university search | People from SPECIFIC universities in buyer country | Language/school filter, no domains needed | ~3 min/search |
| Clay language search | People speaking SPECIFIC language in buyer country | Language filter | ~3 min/search |

**Per-corridor gathering strategy:**

#### UAE→Pakistan
- **DONE:** 15,369 contacts gathered (language: Urdu, universities: LUMS/IBA/NUST, surnames: PK)
- **TO DO:** Apollo scraper — find decision-makers at the 534 scored target companies
  - URL: filter by org domains from scored list + titles CEO/CFO/COO/HR/CTO
  - Expected: ~500-1,000 new contacts at validated companies

#### AU→Philippines
- **PROBLEM:** Current data has Pakistani-origin contacts, NOT Filipino
- **TO DO:**
  1. Clay university search: Ateneo, De La Salle, UP Diliman, UST, Mapua, AIM → filter location=Australia
  2. Clay language search: Tagalog/Filipino speakers in Australia
  3. Clay surname search: common Filipino surnames (Santos, Reyes, Cruz, Garcia, Ramos, etc.)
  4. Apollo scraper: AU-based CEOs/CFOs at companies 1-200 employees

#### Arabic→SouthAfrica
- **TO DO:**
  1. Clay university search: UCT, Wits, Stellenbosch, UP, UJ, UKZN, Rhodes → filter location=Qatar/Saudi/UAE/Bahrain/Kuwait/Oman
  2. Clay language search: Afrikaans speakers in Gulf
  3. Clay surname search: common SA surnames (van der Merwe, Botha, Naidoo, Pillay, etc.)
  4. Apollo scraper: Gulf-based decision-makers at companies 1-200 employees

### Step 2: Score ALL gathered contacts (via negativa pipeline)

Run existing `uae_pk_v7_score.py` — already handles all 3 corridors.

**Pipeline order (cheapest filters first):**
1. Location filter (free) → keeps only buyer-country contacts
2. Domain/title filter (free) → removes no-domain, anti-titles, enterprises
3. Website scraping (free, Apify) → gets company text for analysis
4. Regexp detection (free) → PK-HQ, competitor, business setup, etc.
5. GPT-4o-mini flags ($0.30/5K) → industry, HQ, competitor, need assessment
6. Selection gate → only domain-verified, no-red-flag companies pass
7. Max 3 contacts per company

### Step 3: Verify MYSELF (do-check-improve loop)

After each scoring run:
1. Pull 100 scored contacts with full website text
2. Read EACH company's website independently
3. Flag bad ones with specific reason
4. Fix the ALGORITHM (not blacklist) for each pattern
5. Re-score and re-verify
6. Repeat until 95%+ accuracy
7. THEN expand to next batch of contacts

### Step 4: Clay enrichment of scored companies

After scoring + verification:
1. Export scored company domains
2. Run Clay People Search with buyer-country + decision-maker titles
3. Get up to 3 contacts per company (free, 0 credits)
4. Add to scored output

## Execution Timeline

### Phase 1: UAE→Pakistan (mature — iterate to 2,000)
1. ✅ Scored 575 contacts, 95%+ accuracy
2. ✅ Clay enrichment: +237 contacts = 812 total
3. **NEXT:** Apollo scraper for 534 target company domains (~500 new contacts)
4. **NEXT:** Score Apollo results → verify 100 → fix → re-score
5. **NEXT:** If still <2,000, broaden Apollo search (all UAE companies 1-200 employees, CEO/CFO/COO)

### Phase 2: AU→Philippines (needs new data gathering)
1. Clay Filipino-origin searches (universities + language + surnames)
2. Apollo scraper for AU companies
3. Score all → verify 100 → iterate
4. Clay enrichment for scored companies
5. Target: 2,000 contacts

### Phase 3: Arabic→SouthAfrica (needs new data gathering)
1. Clay SA-origin searches (universities + language + surnames)
2. Apollo scraper for Gulf companies
3. Score all → verify 100 → iterate
4. Clay enrichment for scored companies
5. Target: 2,000 contacts

## Data Storage — EVERYTHING PERSISTED

ALL data in `/scripts/data/` on Hetzner (mounted volume, survives Docker restarts).

| File | What | Shared |
|------|------|--------|
| `uae_pk_v6_scrape.json` | All scraped websites (12K+) | YES |
| `deep_scrape_v7.json` | About/contact/team pages | YES |
| `{corridor}_v8_gpt_flags.json` | GPT binary flags | Per corridor |
| `{corridor}_v8_company_analysis.csv` | Full analysis | Per corridor |
| `{corridor}_v8_scored.json` | Scored output | Per corridor |
| `{corridor}_clay_enrich_domains.csv` | Domains for Clay enrichment | Per corridor |
| `apollo_{corridor}.json` | Apollo scraper results | Per corridor |
| `clay/exports/people_*.json` | Clay People Search results | Shared |

## Quality Gates

- **95%+ accuracy** required before writing to Google Sheet
- Verification: 100 companies, independent judgment (read website text)
- Validated against 30 qualified meeting companies: 0% false negatives
- Algorithm handles: PK-HQ detection, competitor detection, industry exclusion, business setup, recruitment, broken sites
- Only 5 domains in manual blacklist (GPT misclassification errors)

## Do-Check-Improve Loop

```
GATHER (Clay/Apollo) → SCORE (pipeline) → VERIFY (100 companies)
    ↑                                           ↓
    ← FIX ALGORITHM ← IDENTIFY BAD PATTERNS ←
```

Each iteration:
1. Score current data
2. Sample 100 companies across score ranges
3. Read website text for each — independent judgment
4. Identify BAD companies and their pattern
5. Fix algorithm to catch the pattern
6. Re-score
7. Verify fix didn't create false negatives (check against qualified leads)
8. If <95% → loop back to step 2
9. If 95%+ → write to Google Sheet, proceed to Clay enrichment

## Key Rules (from hard experience)

1. NEVER overwrite existing Google Sheet tabs — create new ones
2. NEVER use /tmp/ in Docker — use /scripts/data/
3. NEVER accept missing data without investigating (37% no-domain was unacceptable)
4. NEVER verify with the same method that labels (circular validation)
5. Fix algorithm, not blacklist (unless GPT misclassification)
6. Industry exclusions validated against qualified leads (0 false negatives)
7. Clay runs on HOST (not Docker) — domain files need host paths
8. Sequential Clay sessions only — never parallel (DDoS risk)
9. Store EVERYTHING — every scrape, every GPT call, every Clay result
10. Business setup companies CAN be valid customers (AR Associates converted in 5 hours)
</content>
