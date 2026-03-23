# Australia-Philippines Corridor — Gathering & Scoring Plan

## Strategy

Find Filipino-origin people working in Australia using Clay's **language** and **university** filters (proven origin detection — see `CLAY_ORIGIN_DETECTION.md`). Then score through a 6-layer pipeline, cheapest/fastest first, persisting every result for reuse.

**Target**: Gather ~20,000 raw contacts → score down to ~2,000-3,000 campaign-ready leads.

---

## CRITICAL CONSTRAINT: Clay 5,000 Results Cap

Clay People Search returns **max 5,000 results per search**. If a search has more, the extra are silently dropped. You CANNOT paginate past 5,000.

**Rule**: If any search returns exactly 5,000 → it's capped → you're missing people → MUST split by adding another filter to get sub-5K slices.

**Detection**: Result count shown at bottom of Clay UI (e.g., "Showing 50 of 5,000 results" = capped).

---

## Phase 1: Clay Gathering (Manual in Browser)

### 1A: TAM Scan — State-Level Language Searches

Run Tagalog × each Australian state FIRST to measure volumes and identify which need splitting.

| # | Language | State | Expected Volume | Likely Capped? |
|---|----------|-------|----------------|----------------|
| 1 | Tagalog | New South Wales | 10,000-20,000 | YES — split by city |
| 2 | Tagalog | Victoria | 5,000-10,000 | LIKELY — split by city |
| 3 | Tagalog | Queensland | 3,000-6,000 | MAYBE — check |
| 4 | Tagalog | Western Australia | 1,000-3,000 | Probably not |
| 5 | Tagalog | South Australia | 500-1,500 | No |
| 6 | Tagalog | ACT | 300-800 | No |
| 7 | Tagalog | Tasmania | 100-300 | No |
| 8 | Tagalog | Northern Territory | 200-500 | No |

**Process**:
1. Run search #1 (Tagalog + NSW). Note the result count.
2. If count = 5,000 → mark NSW for city-level splitting (Step 1B).
3. If count < 5,000 → export directly. Move to next state.
4. Repeat for all 8 states.

For uncapped states (WA, SA, ACT, TAS, NT) — export immediately. For capped states → proceed to 1B.

### 1B: Splitting Capped States by City

For each state that hit 5,000, run the same language filter with **city** instead of state.

**NSW cities** (if NSW capped):
| # | Language | City | Expected | If still capped? |
|---|----------|------|----------|-------------------|
| 1 | Tagalog | Sydney | 5,000-12,000 | Split further (1C) |
| 2 | Tagalog | Parramatta | 500-2,000 | Export |
| 3 | Tagalog | Blacktown | 500-1,500 | Export |
| 4 | Tagalog | Liverpool | 300-1,000 | Export |
| 5 | Tagalog | Wollongong | 200-500 | Export |
| 6 | Tagalog | Newcastle | 200-500 | Export |
| 7 | Tagalog | Central Coast | 100-300 | Export |
| 8 | Tagalog | Campbelltown | 200-500 | Export |
| 9 | Tagalog | Penrith | 100-300 | Export |

**VIC cities** (if VIC capped):
| # | Language | City | Expected | If still capped? |
|---|----------|------|----------|-------------------|
| 1 | Tagalog | Melbourne | 4,000-8,000 | Split further (1C) |
| 2 | Tagalog | Geelong | 200-500 | Export |
| 3 | Tagalog | Ballarat | 50-200 | Export |
| 4 | Tagalog | Bendigo | 50-200 | Export |

**QLD cities** (if QLD capped):
| # | Language | City | Expected | If still capped? |
|---|----------|------|----------|-------------------|
| 1 | Tagalog | Brisbane | 2,000-4,000 | Probably fine |
| 2 | Tagalog | Gold Coast | 500-1,500 | Export |
| 3 | Tagalog | Sunshine Coast | 200-500 | Export |
| 4 | Tagalog | Townsville | 100-300 | Export |
| 5 | Tagalog | Cairns | 100-300 | Export |

### 1C: Splitting Capped Cities by Cross-Filter

If a CITY also hits 5,000 (likely Sydney, possibly Melbourne), split using a second filter dimension. Best options in Clay:

**Option A — Split by education presence** (preferred):
- Search 1: Tagalog + Sydney + Education filter = any of the 20 Filipino universities listed below
- Search 2: Tagalog + Sydney + NO education filter (catches everyone NOT matched by Search 1)
- Dedup between them. Search 1 is a subset of Search 2, so only new contacts from Search 2 matter.

**Option B — Split by excluding already-captured cities**:
- If surrounding suburb cities (Parramatta, Blacktown, Liverpool) are run separately, use "Cities to exclude" = [Parramatta, Blacktown, Liverpool, ...] on the Sydney search to narrow it.

**Option C — Split by company headcount** (if Clay supports it):
- Search 1: Tagalog + Sydney + Company headcount 1-50
- Search 2: Tagalog + Sydney + Company headcount 51-200
- Search 3: Tagalog + Sydney + Company headcount 201-1000
- Search 4: Tagalog + Sydney + Company headcount 1001+
- Bonus: gives you company size data for free (useful for enterprise filtering later).

**Decision**: Try Option A first (education cross-filter). If still capped, fall back to Option C.

### 1D: Secondary Language Searches

After all Tagalog searches complete, run secondary languages to catch people who listed a different language:

| Language | Where to run | Why |
|----------|-------------|-----|
| Filipino | ALL capped states/cities (same splits as Tagalog) | "Filipino" is the official name; some list this instead of "Tagalog" |
| Cebuano | NSW, VIC, QLD only (largest Filipino populations) | Visayas-origin people; distinct from Tagalog speakers |
| Ilocano | NSW, VIC only | Northern Luzon origin; smaller population |
| Bisaya | NSW, VIC only | Alternative name for Cebuano/Visayan languages |

**Important**: Filipino/Tagalog overlap will be ~60-80%. Cebuano/Ilocano/Bisaya overlap with Tagalog is ~10-20%. All deduped by LinkedIn URL in merge step — no wasted effort, only new contacts added.

**Expected secondary yield**: 3,000-5,000 additional unique contacts after dedup.

### 1E: University Searches

Run across all of Australia (no geo filter needed — volume per university is well under 5,000).

| # | University | Expected in AU | Notes |
|---|-----------|---------------|-------|
| 1 | University of the Philippines | 500-1,500 | Top state uni. Covers UP Diliman, Manila, Los Baños, Visayas, Mindanao. |
| 2 | Ateneo de Manila University | 300-800 | Elite private. Strong business/law alumni. |
| 3 | De La Salle University | 300-700 | Business-heavy. Corporate alumni. |
| 4 | University of Santo Tomas | 400-1,000 | Oldest university in Asia. Huge alumni network. |
| 5 | Polytechnic University of the Philippines | 300-800 | Massive enrollment. Tech/engineering grads. |
| 6 | Far Eastern University | 200-500 | Manila-based, broad programs. |
| 7 | Mapua University | 200-500 | Engineering/IT graduates. |
| 8 | Adamson University | 100-300 | Manila, engineering. |
| 9 | University of the East | 100-300 | Business/accounting focus. |
| 10 | Saint Louis University | 100-300 | Baguio, strong IT/CS. |
| 11 | Silliman University | 100-300 | Visayas, internationally known. |
| 12 | Xavier University | 50-200 | Cagayan de Oro, Mindanao. |
| 13 | Central Philippine University | 50-150 | Visayas. |
| 14 | Technological University of the Philippines | 100-300 | Tech-focused state uni. |
| 15 | Mindanao State University | 50-200 | Southern PH origin signal. |
| 16 | University of San Carlos | 100-300 | Cebu, strong engineering. |
| 17 | San Beda University | 50-150 | Law/business. |
| 18 | Lyceum of the Philippines | 50-200 | Multiple campuses. |
| 19 | AMA Computer University | 50-150 | IT-specific, many overseas alumni. |
| 20 | STI College | 50-150 | IT/tech chain, many branches. |

**If any university returns 5,000**: split by state (NSW / VIC / QLD / rest). Unlikely but handle it.

**Expected university yield**: 2,000-5,000 unique contacts (many overlap with language results — that's fine, it enriches the origin signal).

### 1F: Search Execution Tracker

Keep a live log of every search run. Save as `easystaff-global/data/au_ph_search_log.json`:

```json
[
  {
    "search_id": "au_ph_001",
    "timestamp": "2026-03-17T14:30:00",
    "filter_type": "language",
    "filter_value": "Tagalog",
    "geo_type": "state",
    "geo_value": "New South Wales",
    "result_count": 5000,
    "capped": true,
    "exported": false,
    "split_into": ["au_ph_002", "au_ph_003", ...],
    "export_file": null,
    "notes": "Capped — splitting by city"
  },
  {
    "search_id": "au_ph_002",
    "timestamp": "2026-03-17T14:35:00",
    "filter_type": "language",
    "filter_value": "Tagalog",
    "geo_type": "city",
    "geo_value": "Sydney",
    "result_count": 5000,
    "capped": true,
    "exported": false,
    "split_into": ["au_ph_010", "au_ph_011"],
    "export_file": null,
    "notes": "Still capped — splitting by education cross-filter"
  },
  {
    "search_id": "au_ph_003",
    "timestamp": "2026-03-17T14:40:00",
    "filter_type": "language",
    "filter_value": "Tagalog",
    "geo_type": "city",
    "geo_value": "Parramatta",
    "result_count": 1247,
    "capped": false,
    "exported": true,
    "split_into": null,
    "export_file": "clay_exports/au_ph_tagalog_parramatta_0317.csv",
    "notes": ""
  }
]
```

**Rules**:
- Every search gets a log entry BEFORE export
- If capped → log it, note the split plan, DON'T export (you'd lose contacts)
- If not capped → export immediately, log the file path
- Never run the same search twice (check log first)

### 1G: Merge & Dedup

After all exports collected:
1. Load all CSVs from `clay_exports/`
2. Normalize LinkedIn URLs (lowercase, strip trailing `/`)
3. Dedup by LinkedIn URL (primary key). If no LinkedIn URL, dedup by `first_name + last_name + company` (lowercase)
4. Tag each contact with ALL origin signals found across all searches:
   - `language:tagalog`, `language:cebuano`, `language:filipino`, `language:ilocano`, `language:bisaya`
   - `university:University of the Philippines`, `university:Ateneo de Manila University`, etc.
   - Contacts found in MULTIPLE searches = higher confidence
5. Record `search_ids` list on each contact (which searches found this person)
6. Save merged dataset: `easystaff-global/data/au_ph_merged_MMDD.json`
7. Write to master Google Sheet new tab: `AU-PH Raw Merged MMDD`

**Expected yield after merge+dedup**: 12,000-20,000 unique contacts.

### 1H: Estimated Search Count

| Category | Searches | Notes |
|----------|----------|-------|
| Tagalog × 8 states (scan) | 8 | Some will cap |
| Tagalog × capped state city splits | ~15-20 | NSW ~9 cities, VIC ~4, QLD ~5 |
| Tagalog × capped city cross-filter splits | ~4-6 | Sydney, maybe Melbourne |
| Filipino × states/cities (same splits) | ~15-25 | Mirrors Tagalog splits for capped areas |
| Cebuano × top 3 states | 3-6 | NSW, VIC, QLD; split if capped |
| Ilocano × top 2 states | 2-4 | NSW, VIC only |
| Bisaya × top 2 states | 2-4 | NSW, VIC only |
| University × 20 universities | 20 | All Australia, no geo filter |
| **Total** | **~70-90 searches** | ~2 min per search = ~2.5-3 hours manual |

---

## Phase 2: 6-Layer Scoring Pipeline

Each layer is cheaper/faster than the next. Each layer reduces the dataset, so expensive layers process fewer contacts. Every result persisted.

### Layer 0: Title & Company Regex (FREE, <1 sec, runs on ALL contacts)

Pure regex. No AI. Catches 40-60% of junk instantly.

**Title EXCLUDE patterns** (case-insensitive):
```python
TITLE_EXCLUDE = [
    # Government
    r'\bgovernment\b', r'\bpublic serv', r'\bdepartment of\b', r'\bministry\b',
    r'\bcouncil\b', r'\bcommission(er)?\b', r'\bmunicipal\b', r'\bfederal\b',
    r'\bstate government\b', r'\bpublic sector\b',
    # Education
    r'\bprofessor\b', r'\blecturer\b', r'\bacademic\b', r'\bresearch(er)?\b',
    r'\bstudent\b', r'\bgraduate\b', r'\bteach(er|ing)\b', r'\btutor\b',
    r'\bpostdoc\b', r'\bscholar\b', r'\bphd\b', r'\bdean\b',
    # Medical
    r'\bphysician\b', r'\bnurs(e|ing)\b', r'\bsurgeon\b', r'\bdentist\b',
    r'\bpharmac', r'\btherapist\b', r'\bpatholog', r'\bclinician\b',
    r'\bFRACGP\b', r'\bMBBS\b', r'\bmedical officer\b', r'\bmidwi(fe|very)\b',
    r'\bregistered nurse\b', r'\bRN\b',
    # Military / Emergency
    r'\barmy\b', r'\bnavy\b', r'\bdefence\b', r'\bmilitary\b', r'\bair force\b',
    r'\bfire\s*(fight|service|brigade)', r'\bpolic(e|ing)\b', r'\bambulance\b',
    # Anti-title (junior / non-decision-maker)
    r'\bintern\b', r'\btrainee\b', r'\bassistant to\b', r'\breceptionist\b',
    r'\bdata entry\b', r'\bvirtual assistant\b', r'\bcashier\b', r'\bdriver\b',
    r'\bsecurity guard\b', r'\bcleaner\b', r'\bwarehouse\b',
    # Freelancer / self-employed
    r'\bfreelanc', r'\bself-employed\b', r'\bindependent consult',
    # Trade / manual labor
    r'\belectrician\b', r'\bplumber\b', r'\bcarpenter\b', r'\bmechanic\b',
    r'\bwelder\b', r'\btechnician\b', r'\bfitter\b',
    # Migration / social services (common for Filipino diaspora, not ICP)
    r'\bmigration\s*(agent|consult|advis)', r'\bsocial worker\b',
    r'\bcommunity\s*(worker|officer|develop)', r'\bcase manager\b',
    r'\bsupport worker\b', r'\bcare\s*(worker|giver|coordinator)\b',
    r'\bdisability\b', r'\baged care\b',
]
```

**Company EXCLUDE patterns** (case-insensitive):
```python
COMPANY_EXCLUDE = [
    # Government
    r'\bdepartment of\b', r'\bgovernment\b', r'\bpublic serv', r'\bcouncil\b',
    r'\bauthority\b', r'\bcommission\b', r'\bministry\b', r'\bfederal\b',
    r'\bstate of\b', r'\bcommonwealth\b', r'\bATO\b',
    # Education
    r'\buniversity\b', r'\binstitute of tech', r'\bTAFE\b', r'\bpolytechnic\b',
    r'\bcollege of\b', r'\bschool\s+of\b', r'\bacademy\b',
    # Healthcare (large public health systems)
    r'\bhospital\b', r'\bhealth service\b', r'\bmedical cent(re|er)\b',
    r'\bhealth district\b', r'\bhealth network\b', r'\bpathology\b',
    # Military / Emergency
    r'\bdefence\b', r'\bmilitary\b', r'\bpolice\b', r'\bfire (service|brigade)\b',
    # Migration services (they help migrants, not a payroll buyer)
    r'\bmigration\b', r'\bvisa\b', r'\bimmigration\b',
]
```

**Output**: `au_ph_layer0_passed.json` + `au_ph_layer0_removed.json` (with removal reason per contact)

### Layer 1: Domain Blacklist (FREE, <1 sec)

Apply `enterprise_blacklist.json` (1000+ domains) PLUS AU-PH-specific additions:

**AU government/education domains** (suffix match):
```python
AU_DOMAIN_EXCLUDE_SUFFIXES = [
    '.gov.au',      # All AU government
    '.edu.au',      # All AU education
]
```

**Filipino-HQ company domains** (company is based IN Philippines):
```python
PH_DOMAIN_SUFFIXES = ['.ph', '.com.ph']
```

**BPO companies** (Philippines-based outsourcing shops — #1 noise source for AU-PH):
```python
BPO_DOMAINS = [
    # Global BPO giants with massive PH operations
    'concentrix.com', 'teleperformance.com', 'alorica.com', 'ttec.com',
    'taskus.com', 'foundever.com', 'sitel.com', 'transcom.com',
    'sutherlandglobal.com', 'webhelp.com', 'telusinternational.com',
    'iqor.com', 'conduent.com', 'majorel.com', 'teamhgs.com',
    'resultscx.com', 'startek.com', 'csg.com',
    # PH-origin BPOs
    'supportninja.com', 'boldr.com', 'acquirebpo.com', 'staffdomain.com',
    'outsourced.ph', 'kmcsolutions.co', 'boothandpartners.com',
    'infinit-o.com', 'sourcefit.com', 'mcvotalent.com',
    'yempo.com.au', 'microsourcing.com', 'auxillis.com',
    # AU-PH staffing/outsourcing companies
    'deployed.com.au', 'cloudstaff.com', 'remotestaff.com',
    'offshored.com.au', 'boomhiring.com',
]
```

**Recruitment/staffing companies** (add AU-specific to existing list):
```python
AU_RECRUITMENT_DOMAINS = [
    'hays.com.au', 'roberthalf.com.au', 'adecco.com.au', 'hudson.com',
    'randstad.com.au', 'michaelpage.com.au', 'manpower.com.au',
    'seek.com.au', 'talent.com.au', 'peoplebank.com.au',
    'modis.com', 'chandlermacleod.com',
]
```

**Domain count check**: if a single domain has 10+ contacts in our dataset → flag as enterprise (even if not in blacklist). These get logged to `au_ph_enterprise_candidates.json` for manual review and blacklist addition.

**Output**: `au_ph_layer1_passed.json` + `au_ph_layer1_removed.json`

### Layer 2: Role Tier Scoring (FREE, instant)

Same proven tiers from `score_uae_pk_god.py`:

| Tier | Pattern | Score | Rationale |
|------|---------|-------|-----------|
| T1 | CFO, Chief Financial, VP Finance, Head of Finance, Payroll, Finance Director, Controller | 10 | Direct payroll budget holder |
| T2 | COO, Chief Operating, VP Operations, Head of Operations | 9 | Controls ops spending |
| T3 | CHRO, Chief People, VP HR, Head of HR, Head of People, HR Director, Talent | 8 | Manages contractor onboarding |
| T4 | CEO, Founder, Co-Founder, Managing Director, GM, Owner, President, Partner, Principal | 7 | Final decision maker at SMBs |
| T5 | CTO, VP Engineering, Head of Technology, Engineering Director, IT Director | 6 | Manages tech contractors |
| T6 | Director, Head of, VP, Vice President (general) | 5 | Mid-senior, can influence |
| T7 | Manager, Lead, Senior | 3 | Operational, less authority |
| T8 | All others (that passed Layer 0) | 1 | Low priority but not excluded |

Contacts scored, not removed. T7-T8 stay in dataset but rank lower.

**Output**: role_tier added to each contact record

### Layer 3: Per-Company Cap & Dedup (FREE, instant)

1. Group contacts by domain (fallback: company name if no domain)
2. Sort within each company by role_tier (best first), then by origin signal count (more signals = better)
3. Keep top 3 per company
4. Dedup by LinkedIn URL (catch any remaining duplicates)
5. Dedup by name+company (catch no-LinkedIn duplicates)

**Output**: `au_ph_layer3_capped.json`

After layers 0-3, expected dataset size: ~5,000-8,000 contacts (from ~20,000 raw).

### Layer 4: Website Validation (FREE via proxy, ~200 domains/min)

For each unique domain in the remaining contacts:

1. **HTTP check**: does homepage resolve? (timeout 10s)
   - Dead domain / timeout / parked page → flag `no_website`
   - Contacts with `no_website` NOT removed, just deprioritized (company may still exist)

2. **Homepage text extraction** (3000 chars max):
   - Store in `au_ph_website_cache.json` keyed by domain
   - This cache is ADDITIVE — never re-scrape already-cached domains
   - Reuse any domains already cached from UAE-PK pipeline

3. **Regex detection on website text**:

   **PH-HQ signals** (company is based in Philippines, not AU):
   ```python
   PH_HQ_PATTERNS = [
       r'(?:based|located|headquartered)\s+in\s+(?:manila|cebu|makati|quezon|davao|philippines)',
       r'(?:office|team)\s+in\s+(?:manila|cebu|makati|bgc|quezon city)',
       r'\+63[\s\-]?\d',          # PH phone numbers
       r'(?:makati|bgc|ortigas|ayala)\s+(?:ave|avenue|center|city)',  # PH business districts
       r'philippine\s+(?:based|company|firm)',
   ]
   ```

   **Enterprise signals**:
   ```python
   ENTERPRISE_PATTERNS = [
       r'(?:\d{1,3},\d{3}|\d{4,})\+?\s*employees',  # "5,000+ employees"
       r'(?:offices|locations)\s+(?:in|across)\s+\d{2,}\s+countries',
       r'fortune\s+\d{3}',
       r'(?:nasdaq|nyse|asx)\s*[:\-]?\s*[A-Z]{2,5}',  # Stock ticker = public company
   ]
   ```

   **BPO/outsourcing provider signals** (they SELL outsourcing, not BUY it):
   ```python
   BPO_PROVIDER_PATTERNS = [
       r'(?:business process|BPO)\s+outsourc',
       r'(?:offshore|nearshore)\s+(?:staffing|team|talent)',
       r'dedicated\s+(?:offshore|remote)\s+(?:team|staff)',
       r'(?:virtual|remote)\s+(?:assistant|employee|staff)\s+(?:service|solution|provider)',
       r'hire\s+(?:filipino|philippine|offshore)\s+(?:talent|staff|team)',
   ]
   ```

   **Positive signals** (boost):
   ```python
   BUYER_SIGNALS = [
       r'(?:we|our)\s+(?:team|people|staff)\s+(?:in|across)\s+(?:multiple|several|different)\s+countries',
       r'(?:remote|distributed)\s+team',
       r'(?:contractor|freelancer)\s+(?:payment|management|onboarding)',
   ]
   ```

**Output**: `au_ph_website_cache.json` (domain → {status, text, flags}) + website flags added to contact records

### Layer 5: GPT-4o-mini Binary Flags (~$0.0002/domain, ~$0.50-1.00 total)

Only for domains that passed Layer 4 AND don't have definitive regex results. ~2,000-3,000 unique domains.

**Prompt** (same proven binary-only pattern as UAE-PK):
```
Given this company's homepage text, answer YES or NO only:
1. is_au_company: Is this company headquartered or primarily based in Australia?
2. is_ph_company: Is this company headquartered in the Philippines?
3. is_bpo_provider: Does this company provide outsourcing/BPO services?
4. is_enterprise_500plus: Does this company have 500+ employees?
5. is_competitor: Does this company provide payroll, EOR, or HR services?
6. is_construction_hospitality: Is this company in construction, real estate, hospitality, or restaurants?
7. would_need_contractor_payroll: Would this company plausibly need to pay contractors in other countries?

Company: {company_name}
Domain: {domain}
Homepage text: {text[:2000]}
```

**NO numerical scores** — binary only (87% hallucination rate on GPT numerical scores, proven in UAE-PK).

**Output**: `au_ph_gpt_flags.json` (domain → {is_au_company, is_ph_company, ...})

### Layer 6: Final Scoring & Ranking

```python
def final_score(contact):
    score = 0

    # Origin signal strength (40%)
    signals = contact['origin_signals']
    has_university = any(s.startswith('university:') for s in signals)
    has_language = any(s.startswith('language:') for s in signals)
    if has_university and has_language:
        score += 40  # Both = definitive
    elif has_university:
        score += 38  # University alone = very strong
    elif has_language:
        score += 34  # Language alone = strong

    # Role tier (20%)
    role_pct = {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 6, 8: 2}
    score += role_pct.get(contact['role_tier'], 2)

    # Survived all filters (20%)
    if not contact.get('any_red_flag'):
        score += 20

    # Company signals (20%)
    flags = contact.get('gpt_flags', {})
    website = contact.get('website_flags', {})
    if flags.get('is_au_company') == 'YES':
        score += 8
    if flags.get('would_need_contractor_payroll') == 'YES':
        score += 6
    if website.get('has_buyer_signal'):
        score += 4
    if contact.get('domain') and not contact.get('no_website'):
        score += 2  # Has reachable website

    return score
```

Sort descending by score. Top 2,000-3,000 → Opus review.

**Output**: `au_ph_final_scored.json` + Google Sheet tab `AU-PH Scored MMDD`

---

## Phase 3: Opus Quality Review

Same proven pattern as UAE-PK (8 iterations, <1% removal rate):

1. Take top 3,000 scored contacts
2. Split into 5 batches of 600
3. Launch 5 parallel Opus agents
4. Each agent reviews every contact, flags:
   - Enterprise >500 employees (missed by blacklist)
   - Filipino-HQ company (BPO shop based in PH that somehow passed)
   - Junk data (fake names, placeholder companies)
   - Non-decision-maker that slipped through regex
5. Aggregate removals → add new domains to blacklist → re-run Layers 1-6 → repeat
6. Stop when removal rate < 1%

**New blacklist entries** from each iteration logged in `au_ph_blacklist_additions.json` and merged into `enterprise_blacklist.json`.

---

## Phase 4: Approval Gate → FindyMail + Campaign

**STOP HERE AND WAIT FOR APPROVAL.** Do NOT proceed to FindyMail until the scored list is reviewed and explicitly approved.

### 4A: Present for Approval
1. Write final scored contacts to Google Sheet tab: `AU-PH FINAL REVIEW MMDD`
2. Include columns: Rank, Name, Title, Company, Domain, Location, Origin Signals, Role Tier, Score, Website Status, Red Flags
3. Notify operator with: total count, top 20 sample, score distribution, removal stats per layer
4. **WAIT for explicit approval** before spending FindyMail credits

### 4B: After Approval
1. FindyMail enrichment: `findymail_and_upload.py` (~50-60% hit rate expected for AU)
2. Create SmartLead campaign
3. Set sequence (adapt from UAE-PK for Filipino corridor context)
4. Upload enriched leads
5. Launch from UI only

---

## Data Persistence Map

Every step saves its output. Nothing is ever lost. Re-runs start from cached data.

```
easystaff-global/data/
├── au_ph_search_log.json              # Every Clay search: filters, count, capped?, file
├── clay_exports/                      # Raw Clay CSVs (NEVER modify)
│   ├── au_ph_tagalog_nsw_0317.csv
│   ├── au_ph_tagalog_sydney_0317.csv
│   ├── au_ph_tagalog_parramatta_0317.csv
│   ├── au_ph_filipino_nsw_0317.csv
│   ├── au_ph_cebuano_nsw_0317.csv
│   ├── au_ph_uni_UP_0317.csv
│   ├── au_ph_uni_ateneo_0317.csv
│   └── ...
├── au_ph_merged_MMDD.json             # Merged + deduped, with origin signals
├── au_ph_layer0_passed.json           # After title/company regex
├── au_ph_layer0_removed.json          # Removed by regex (with reasons)
├── au_ph_layer1_passed.json           # After blacklist
├── au_ph_layer1_removed.json          # Removed by blacklist (with reasons)
├── au_ph_layer3_capped.json           # After per-company cap
├── au_ph_website_cache.json           # Domain → {status, text, flags} (ADDITIVE)
├── au_ph_gpt_flags.json               # Domain → GPT binary flags (ADDITIVE)
├── au_ph_final_scored.json            # Final scored contacts
├── au_ph_enterprise_candidates.json   # Domains with 10+ contacts (review needed)
├── au_ph_blacklist_additions.json     # New blacklist entries from Opus review
└── au_ph_bpo_blacklist.json           # BPO-specific exclusion list
```

**Reusability**:
- `website_cache` and `gpt_flags` are keyed by domain — reusable across corridors
- `enterprise_blacklist.json` is shared across ALL corridors
- BPO blacklist is AU-PH specific but may apply to other APAC corridors
- Scoring script is parameterized by corridor — same code, different configs
- `search_log.json` prevents duplicate Clay searches — never re-run what's already exported

---

## Execution Timeline

| Step | What | Duration | Cost |
|------|------|----------|------|
| Clay TAM scan (8 state searches) | Manual in browser | ~15 min | $0 |
| Clay city splits (~20-30 searches) | Manual in browser | ~1 hour | $0 |
| Clay secondary languages (~15-25 searches) | Manual in browser | ~45 min | $0 |
| Clay university searches (20 searches) | Manual in browser | ~40 min | $0 |
| Merge + dedup | Script | <1 min | $0 |
| Layer 0: Title/Company regex | Script | <1 sec | $0 |
| Layer 1: Blacklist | Script | <1 sec | $0 |
| Layer 2: Role scoring | Script | <1 sec | $0 |
| Layer 3: Per-company cap | Script | <1 sec | $0 |
| Layer 4: Website scraping (~3,000 domains) | Script on Hetzner | ~15 min | $0 (Apify proxy) |
| Layer 5: GPT-4o-mini (~2,000 domains) | Script on Hetzner | ~10 min | ~$0.50 |
| Layer 6: Final scoring | Script | <1 sec | $0 |
| Opus review (5 iterations × 5 agents) | Automated | ~2 hours | ~$5-10 |
| FindyMail enrichment | Script on Hetzner | ~30 min | ~$0.01/email |
| **Total** | | **~5-6 hours** | **~$10-15** |

---

## AU-PH Specific Challenges vs UAE-PK

| Challenge | UAE-PK | AU-PH | Mitigation |
|-----------|--------|-------|------------|
| **Clay cap** | Had existing sheet | Cap at 5,000/search — must split | Hierarchical geo splits + cross-filters |
| **BPO industry** | Not a factor | Massive — PH is #1 BPO destination globally | Dedicated BPO blacklist (30+ domains) + regex |
| **Government** | Small issue | Large — many Filipinos in AU public sector | Regex on title + company + `.gov.au` suffix |
| **Healthcare** | Minor | Significant — many Filipino nurses/doctors/carers | Title regex: nurse, physician, FRACGP, aged care |
| **Education** | Minor | Moderate — Filipino academics at AU universities | Company regex + `.edu.au` suffix |
| **Care/social work** | Not a factor | Very common — Filipino care workers in AU | Title regex: support worker, care worker, disability |
| **Origin ambiguity** | PK names overlap with Arabic | Filipino names distinctive, language signal clean | High confidence from Tagalog/Cebuano filters |
| **Company HQ confusion** | PK companies disguised as UAE | Less common — PH companies usually identifiable | `.ph` domain + PH address regex on website |

---

## Key Decisions Made

1. **State-level scan first** — measure TAM before splitting; don't guess which states need splitting
2. **Hierarchical splits**: state → city → cross-filter. Only split what's actually capped.
3. **All languages**: Tagalog + Filipino + Cebuano + Ilocano + Bisaya — maximize coverage, dedup handles overlaps
4. **Care/social work regex** — unique to AU-PH corridor: many Filipino care workers, aged care, disability support workers. Not ICP.
5. **Migration services regex** — many Filipino migration agents/consultants in AU. They help migrants, don't need EasyStaff.
6. **BPO blacklist is critical** — #1 unique noise source
7. **Search log as truth** — every Clay search logged with count, cap status, export file. Prevents duplicate work.
8. **Score T7-T8, don't remove** — a Manager at a 20-person AU tech company is better than a CEO at a BPO
9. **Website scraping AFTER regex+blacklist** — only ~3,000 domains instead of ~20,000
10. **GPT AFTER website regex** — only flag ambiguous companies. Saves 60% of API cost.
