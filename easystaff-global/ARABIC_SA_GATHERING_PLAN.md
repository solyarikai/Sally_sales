# Arabic → South Africa Corridor — Gathering & Scoring Plan

## Strategy

Find **South African-origin decision-makers** working in **Arabic/Gulf countries** (UAE, Qatar, Saudi Arabia, Bahrain, Kuwait, Oman) using the **automated Clay Puppeteer pipeline** (`diaspora_service.py`). This corridor has **proven 18.2% conversion rate** from Qatar→SA campaign.

**Target**: 20,000 raw contacts → score down to ~3,000-5,000 campaign-ready leads.

---

## Automation Infrastructure

### How Gathering Works — NO MANUAL BROWSER WORK

The system automates Clay searches via Puppeteer browser emulation:

```
POST /api/diaspora/gather
├── diaspora_service.py (orchestrator — 2500 lines)
│   ├── Phase 0: Language search (Afrikaans, Zulu, Xhosa) — $0 cost, auto-accept
│   ├── Phase 1: University search (5 SA university batches)
│   ├── Phase 2: Extended university search (2 more batches)
│   ├── Phase 3: Surname search (8 batches — Afrikaans, Bantu, Indian)
│   ├── Phase 4: Title-split search (12 individual titles)
│   └── Phase 5: Industry search (12 industry batches)
├── clay_service.py (Python↔Puppeteer bridge)
│   └── scripts/clay/clay_people_search.js (45KB Puppeteer automation)
├── Google Sheets export (incremental, after every batch)
└── Pipeline state checkpoint (resume on failure)
```

**Launch command** (production):
```bash
curl -X POST http://localhost:8000/api/diaspora/gather \
  -H "Content-Type: application/json" -H "X-Company-ID: 1" \
  -d '{"corridor": "arabic-south-africa", "project_id": 9, "target_count": 20000, "mode": "full_tam", "existing_sheet_id": "1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU"}'
```

**Check progress**:
```bash
curl http://localhost:8000/api/diaspora/status -H "X-Company-ID: 1"
```

### Corridor Configuration (in `diaspora_service.py`)

```python
CORRIDORS = {
    "arabic-south-africa": {
        "employer_countries": ["United Arab Emirates", "Saudi Arabia", "Qatar",
                               "Bahrain", "Kuwait", "Oman"],
        "contractor_country": "South Africa",
        "label": "Arabic Countries → South Africa",
        "sheet_name": "Arabic-SouthAfrica",
    },
}

LANGUAGE_BATCHES["South Africa"] = [
    {"label": "za_lang_afrikaans", "languages": ["Afrikaans"], "auto_accept": True},
    {"label": "za_lang_zulu", "languages": ["Zulu"], "auto_accept": True},
    {"label": "za_lang_xhosa", "languages": ["Xhosa"], "auto_accept": True},
]

CITY_SPLITS["arabic-south-africa"] = {
    "languages": ["Afrikaans", "Zulu"],
    "cities": ["Dubai", "Abu Dhabi", "Riyadh", "Jeddah", "Doha",
               "Kuwait City", "Manama", "Muscat"],
}
```

### Pipeline Execution Order (cheapest first)

| Phase | Method | Cost | Hit Rate | Best For |
|-------|--------|------|----------|----------|
| 0 | Language (Afrikaans/Zulu/Xhosa) | $0 | Auto-accept ALL | Definitive SA origin |
| 0b | Language city splits | $0 | Auto-accept ALL | If country search caps at 5K |
| 1 | University (5 batches: UCT, Wits, etc.) | ~$0.001/batch | 15-50% | High confidence |
| 2 | Extended university (2 batches) | ~$0.001/batch | 10-30% | Broader net |
| 3 | Surname (8 batches: Afrikaans, Bantu, Indian) | ~$0.001/batch | 5-20% | Fill remaining |
| 4 | Title-split (12 titles × 6 countries) | ~$0.001/batch | 3-15% | Marginal new contacts |
| 5 | Industry (12 batches) | ~$0.002/batch | 0.5-5% | Different company types |

### Data Persistence (automatic)

- Raw contacts: `/scripts/data/raw_contacts/arabic-south-africa_*.json`
- Pipeline state: `/scripts/data/pipeline_state/diaspora_arabic-south-africa_interim.json`
- Google Sheet: incremental export to master sheet `Arabic-SouthAfrica` tab
- Approaches Log: every search tracked in master sheet `Approaches Log` tab

---

## Current State (March 17, 2026)

### Gathering Status
| Metric | Value |
|--------|-------|
| Contacts gathered | **9,654** (from previous runs) |
| Target | 20,000 |
| Current phase | Language search — Afrikaans |
| Pipeline status | **RUNNING** |

### What Exists — DO NOT OVERWRITE
| Asset | Location | Status |
|-------|----------|--------|
| Archived Arabic-SA sheet | `18td81wAFFjRs4zxa7jkNDHxDfMydaJdkMruMHUKnmGA` (~1,329) | Preserved — quality issues noted |
| Master sheet Arabic-SouthAfrica tab | `1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU` | Being appended to (not overwritten) |
| Strategy doc | `tasks/easystaff global/strategy_dubai_south_africa_clevel.md` | Reference |
| Algo scorer | `score_corridors_algo.py` | Handles Arabic-SA filtering |

### Known Issues (discovered March 17, 2026)
1. **Location inversion**: University search doesn't filter by Gulf location → 1,800+ contacts in SA/India/UK
2. **City split bug**: Puppeteer city filter fails silently → 4,652 contacts with worldwide locations (Bryan Habana in Cape Town labeled as "Afrikaans in Dubai")
3. **Surname garbage**: 1,351 contacts from surname search — auto-accepts Arabic/Pakistani names (Siddiqui, Alanezi, Mroueh) as "South African"
4. **Enterprise contamination**: Accenture, Discovery, Standard Bank, TransUnion in data

### Quality Breakdown (9,720 raw contacts)
| Source | Count | In Gulf | Quality |
|--------|-------|---------|---------|
| `language` (country-level) | 1,583 | **1,583** | **EXCELLENT** — Afrikaans/Zulu speakers verified in Gulf |
| `language_city_split` | 4,652 | ~35 | **BROKEN** — city filter not applied, worldwide results |
| `university_people_first` | 1,802 | ~29 | **BAD** — no Gulf location filter |
| `surname_search` | 1,351 | ~1,244 | **GARBAGE** — non-SA names accepted |
| `extended_university` | 332 | ~2 | **BAD** — same as university |
| **After Gulf location filter** | | **~2,900** | Only 30% of raw data is usable |

### What WORKS
- **Language search at country level** is the only reliable approach (1,583 genuine contacts)
- Enterprise blacklist (1,004+ domains) filters correctly
- `score_corridors_algo.py` filters by Gulf location, removing wrong-location garbage
- Pipeline resumes from Google Sheet after container restart

---

## Why Arabic → South Africa

- **18.2% conversion rate** from Qatar→SA campaign (6 qualified from 33 replies) — BEST corridor
- ~100,000+ South Africans in UAE alone
- Afrikaans professionals dominate Dubai's finance, tech, consulting, real estate
- SA Indian community (Durban/KZN origin) huge in Dubai business
- ZAR weakness = SA contractors extremely affordable for AED/QAR-paying companies
- 2-hour timezone overlap (GMT+4 vs GMT+2) = real-time collaboration
- English as shared business language
- Existing wins: NEOM cluster (4 contacts), Digital Bridge, Pioneers Consulting

---

## CRITICAL CONSTRAINT: Clay 5,000 Results Cap

Clay People Search returns **max 5,000 results per search**. If a search returns exactly 5,000 → it's capped → you're missing people → MUST split.

**For Arabic-SA this is LESS of a problem** than AU-PH because:
- SA diaspora in Gulf is smaller than Filipino diaspora in Australia
- Afrikaans/Zulu speakers in Gulf countries = low volume per search
- Most searches will return <5,000. Only UAE-wide Afrikaans might cap.

---

## Phase 1: Clay Gathering (AUTOMATED via Puppeteer)

**Everything below runs automatically via `POST /api/diaspora/gather`.** No manual browser work.

### 1A: Language Searches — Afrikaans (Primary Signal)

Afrikaans speakers in Gulf = almost certainly South African. Very high precision.

| # | Language | Country | Expected | Capped? |
|---|----------|---------|----------|---------|
| 1 | Afrikaans | United Arab Emirates | 2,000-5,000 | MAYBE — check |
| 2 | Afrikaans | Saudi Arabia | 500-2,000 | No |
| 3 | Afrikaans | Qatar | 300-1,000 | No |
| 4 | Afrikaans | Bahrain | 100-400 | No |
| 5 | Afrikaans | Kuwait | 100-400 | No |
| 6 | Afrikaans | Oman | 100-300 | No |

**If UAE caps at 5,000** → split by city:
| # | Language | City | Expected |
|---|----------|------|----------|
| 1a | Afrikaans | Dubai | 1,500-3,500 |
| 1b | Afrikaans | Abu Dhabi | 500-1,500 |
| 1c | Afrikaans | Sharjah | 100-300 |
| 1d | Afrikaans | Ajman / RAK / Fujairah | 50-200 |

**Expected Afrikaans yield**: 3,000-7,000 raw contacts across all Gulf.

### 1B: Language Searches — Zulu (High Precision)

Zulu speakers in Gulf = uniquely South African. Smaller volume but very high quality.

| # | Language | Country | Expected | Capped? |
|---|----------|---------|----------|---------|
| 7 | Zulu | United Arab Emirates | 200-800 | No |
| 8 | Zulu | Saudi Arabia | 50-300 | No |
| 9 | Zulu | Qatar | 30-150 | No |
| 10 | Zulu | Bahrain + Kuwait + Oman | 20-100 | No (combine) |

**Expected Zulu yield**: 300-1,300 raw contacts.

### 1C: Language Searches — Xhosa (High Precision)

| # | Language | Country | Expected | Capped? |
|---|----------|---------|----------|---------|
| 11 | Xhosa | United Arab Emirates | 100-500 | No |
| 12 | Xhosa | Saudi Arabia | 30-200 | No |
| 13 | Xhosa | Qatar + Bahrain + Kuwait + Oman | 20-100 | No (combine) |

**Expected Xhosa yield**: 150-800 raw contacts.

### 1D: Language Searches — Secondary SA Languages

| # | Language | Countries | Expected | Notes |
|---|----------|-----------|----------|-------|
| 14 | Sotho | UAE + Saudi | 50-300 | Sesotho speakers |
| 15 | Tswana | UAE + Saudi | 30-200 | Setswana speakers |
| 16 | Swazi / siSwati | UAE + Saudi | 20-100 | Small but unique |

**Expected secondary yield**: 100-600 raw contacts (heavy overlap with primary languages).

### 1E: University Searches

Run across ALL Gulf countries at once (volume per university in Gulf well under 5,000).

**Location filter**: United Arab Emirates, Saudi Arabia, Qatar, Bahrain, Kuwait, Oman

| # | University Batch | Schools | Expected in Gulf |
|---|-----------------|---------|-----------------|
| 17 | za_top | UCT, Wits, Stellenbosch, UP, UJ | 500-2,000 |
| 18 | za_other | UKZN, Rhodes, UFS, NWU, Nelson Mandela | 300-1,000 |
| 19 | za_more | UNISA, DUT, CPUT, TUT, Walter Sisulu | 200-800 |
| 20 | za_business | GSB, GIBS, Wits Business School, USB, Henley Africa, Milpark | 200-600 |
| 21 | za_uni_ext_1 | Monash SA, UL, Univen, MUT, CUT | 100-400 |
| 22 | za_uni_ext_2 | UniZulu, Sol Plaatje, SMU, Fort Hare, UWC | 50-200 |

**Expected university yield**: 1,000-4,000 raw contacts (overlap with language results — enriches origin signal).

### 1F: Surname Searches (If Needed — Phase 2)

Only run these IF Phase 1 (language + university) yields <3,000 unique contacts. Surnames are noisier.

**Afrikaans surname batches** (highest volume in Gulf):
| Batch | Surnames | Notes |
|-------|----------|-------|
| za_afr_1 | Botha, du Plessis, van der Merwe, Pretorius, Joubert, Steyn | Top 6 by frequency |
| za_afr_2 | Coetzee, Venter, Swanepoel, Kruger, Erasmus, du Toit | Next 6 |
| za_afr_3 | Vermeulen, Fourie, le Roux, van Zyl, Visser, Viljoen | Next 6 |
| za_afr_4 | Louw, Marais, Lombard, de Beer, van Wyk, Malan | Next 6 |

**Zulu/Xhosa/Sotho surname batches** (highest precision — uniquely SA):
| Batch | Surnames | Notes |
|-------|----------|-------|
| za_bantu_1 | Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo | Top 5 |
| za_bantu_2 | Ngcobo, Sithole, Mthembu, Radebe, Molefe | Next 5 |

**SA Indian surname batches** (combine with SA university to disambiguate from Indian-Indian):
| Batch | Surnames | Notes |
|-------|----------|-------|
| za_indian | Naidoo, Govender, Pillay, Chetty, Moodley | MUST cross with university |

**Business surname batch**:
| Batch | Surnames | Notes |
|-------|----------|-------|
| za_biz | Motsepe, Wiese, Bekker, Dippenaar | SA billionaire/business family names |

### 1G: Search Execution Tracker

Save as `easystaff-global/data/arabic_sa_search_log.json`:

```json
[
  {
    "search_id": "arabic_sa_001",
    "timestamp": "2026-03-17T14:00:00",
    "filter_type": "language",
    "filter_value": "Afrikaans",
    "geo_type": "country",
    "geo_value": "United Arab Emirates",
    "result_count": null,
    "capped": null,
    "exported": false,
    "split_into": null,
    "export_file": null,
    "notes": "First search — check if capped"
  }
]
```

### 1H: Merge & Dedup

After all exports:
1. Load all CSVs from `data/clay_exports/arabic_sa_*.csv`
2. Normalize LinkedIn URLs
3. Dedup by LinkedIn URL (primary) or `first_name + last_name + company` (secondary)
4. Tag each contact with ALL origin signals: `language:afrikaans`, `university:UCT`, etc.
5. Record `search_ids` per contact
6. Save merged dataset: `easystaff-global/data/arabic_sa_merged_MMDD.json`
7. Write to **NEW** Google Sheet tab: `Arabic-SA Clay MMDD` (DO NOT overwrite existing Arabic-SouthAfrica tab)

**Expected yield after merge+dedup**: 3,000-8,000 unique contacts.

### 1I: Estimated Search Count

| Category | Searches | Notes |
|----------|----------|-------|
| Afrikaans × 6 countries | 6-10 | UAE may need city split |
| Zulu × 3-4 groups | 3-4 | Combine small countries |
| Xhosa × 2-3 groups | 2-3 | Combine small countries |
| Secondary languages (Sotho, Tswana, Swazi) | 3 | Combined country searches |
| University × 6 batches | 6 | All Gulf as single location |
| **Total Phase 1** | **~20-30 searches** | **~1 hour manual** |
| Surname batches (Phase 2, if needed) | ~10-12 | Only if Phase 1 < 3K unique |

---

## Phase 2: 6-Layer Scoring Pipeline

Same proven architecture as AU-PH. Each layer cheaper/faster than the next.

### Layer 0: Title & Company Regex (FREE, <1 sec)

**Title EXCLUDE patterns** (same as AU-PH + Arabic-SA specific):
```python
TITLE_EXCLUDE = [
    # Government (Gulf-specific)
    r'\bgovernment\b', r'\bpublic serv', r'\bministry\b', r'\bmunicipal\b',
    r'\bfederal\b', r'\bauthority\b', r'\bpublic sector\b',
    r'\bemirates\s+authority', r'\bsaudi\s+(?:aramco|government)',
    # Education
    r'\bprofessor\b', r'\blecturer\b', r'\bacademic\b', r'\bresearch(er)?\b',
    r'\bstudent\b', r'\bteach(er|ing)\b', r'\btutor\b', r'\bdean\b',
    # Medical
    r'\bphysician\b', r'\bnurs(e|ing)\b', r'\bsurgeon\b', r'\bdentist\b',
    r'\bpharmac', r'\btherapist\b',
    # Military / Emergency
    r'\barmy\b', r'\bnavy\b', r'\bdefence\b', r'\bmilitary\b',
    r'\bpolice\b', r'\bambulance\b',
    # Anti-title (junior / non-decision-maker)
    r'\bintern\b', r'\btrainee\b', r'\bassistant to\b', r'\breceptionist\b',
    r'\bdata entry\b', r'\bvirtual assistant\b', r'\bcashier\b', r'\bdriver\b',
    r'\bsecurity guard\b', r'\bcleaner\b', r'\bwarehouse\b',
    # Freelancer / self-employed
    r'\bfreelanc', r'\bself-employed\b', r'\bindependent consult',
    # Trade / manual labor
    r'\belectrician\b', r'\bplumber\b', r'\bcarpenter\b', r'\bmechanic\b',
    r'\bwelder\b', r'\btechnician\b', r'\bfitter\b',
    # Gulf-specific non-ICP
    r'\bproperty\s+consult', r'\breal\s+estate\s+agent\b',
    r'\bvisa\s+(?:consult|officer|agent)\b',
    r'\bimmigration\s+(?:consult|officer|agent)\b',
]
```

**Company EXCLUDE patterns**:
```python
COMPANY_EXCLUDE = [
    # Government
    r'\bgovernment\b', r'\bministry\b', r'\bauthority\b', r'\bcommission\b',
    # Education
    r'\buniversity\b', r'\bcollege\b', r'\bacademy\b', r'\binstitute\b',
    # Healthcare
    r'\bhospital\b', r'\bhealth\s+(?:service|care|center)\b', r'\bclinic\b',
    # Gulf mega-projects (enterprise — cool but >500 employees)
    r'\bNEOM\b', r'\bAramco\b', r'\bQatar\s+Airways\b', r'\bEtihad\b',
    r'\bEmirates\s+(?:Airlines|Group|NBD)\b', r'\bDubai\s+Holding\b',
    # SA-HQ companies (person is IN South Africa, wrong direction)
    r'\bbased\s+in\s+(?:south\s+africa|johannesburg|cape\s+town|durban|pretoria)\b',
]
```

### Layer 1: Domain Blacklist (FREE, <1 sec)

Apply shared `enterprise_blacklist.json` PLUS Arabic-SA specific:

**SA-HQ domain suffixes** (company is based IN South Africa — wrong direction):
```python
SA_DOMAIN_SUFFIXES = ['.za', '.co.za']
```

**Gulf government/education domains**:
```python
GULF_DOMAIN_EXCLUDE_SUFFIXES = [
    '.gov.ae', '.gov.sa', '.gov.qa', '.gov.bh', '.gov.kw', '.gov.om',
    '.edu.ae', '.edu.sa', '.edu.qa',
    '.ac.ae',  # UAE academic
]
```

**SA enterprise companies often found in Gulf** (already in blacklist but verify):
```python
SA_ENTERPRISE_DOMAINS = [
    'discovery.co.za', 'standardbank.com', 'firstrand.co.za', 'absa.co.za',
    'investec.com', 'nedbank.co.za', 'sasol.com', 'angloamerican.com',
    'vodacom.com', 'mtn.com', 'multichoice.com', 'naspers.com',
    'woolworths.co.za', 'shoprite.co.za', 'bidvest.com',
]
```

**EOR/Payroll competitors** (they sell what we sell):
```python
COMPETITOR_DOMAINS_SA = [
    'deel.com', 'remote.com', 'oysterhr.com', 'papaya-global.com',
    'letsdeel.com', 'velocityglobal.com', 'globalization-partners.com',
    'payoneer.com', 'paypal.com',
]
```

### Layer 2: Role Tier Scoring (FREE, instant)

Same as UAE-PK/AU-PH:

| Tier | Pattern | Score | Rationale |
|------|---------|-------|-----------|
| T1 | CFO, VP Finance, Head of Finance, Payroll, Controller | 10 | Direct payroll budget |
| T2 | COO, VP Operations, Head of Operations | 9 | Controls ops spending |
| T3 | CHRO, VP HR, Head of People, HR Director, Talent | 8 | Manages contractors |
| T4 | CEO, Founder, MD, Owner, Partner, Principal | 7 | Final decision at SMBs |
| T5 | CTO, VP Engineering, Head of Tech | 6 | Manages tech contractors |
| T6 | Director, Head of, VP (general) | 5 | Can influence |
| T7 | Manager, Lead, Senior | 3 | Operational |
| T8 | Other | 1 | Low priority |

### Layer 3: Per-Company Cap (FREE, instant)

1. Group by domain (fallback: company name)
2. Sort by role_tier then origin signal count
3. Keep top 3 per company
4. Dedup by LinkedIn URL + name+company

### Layer 4: Website Validation (FREE via proxy)

Same as AU-PH pipeline. Reuse `website_cache` from other corridors.

**SA-HQ detection** (company is headquartered in SA, not Gulf):
```python
SA_HQ_PATTERNS = [
    r'(?:based|located|headquartered)\s+in\s+(?:south africa|johannesburg|cape town|durban|pretoria)',
    r'(?:office|team)\s+in\s+(?:sandton|rosebank|waterfall|century city|bellville)',
    r'\+27[\s\-]?\d',              # SA phone numbers
    r'(?:sandton|rosebank|waterfall|century city)\s+(?:drive|road|ave)',
]
```

**Enterprise signals** (same as other corridors):
```python
ENTERPRISE_PATTERNS = [
    r'(?:\d{1,3},\d{3}|\d{4,})\+?\s*employees',
    r'(?:offices|locations)\s+(?:in|across)\s+\d{2,}\s+countries',
    r'fortune\s+\d{3}',
    r'(?:nasdaq|nyse|lse|dfm|adx|tadawul)\s*[:\-]?\s*[A-Z]{2,5}',
]
```

**Positive signals (boost)**:
```python
BUYER_SIGNALS = [
    r'(?:we|our)\s+(?:team|people|staff)\s+(?:in|across)\s+(?:south africa|cape town|johannesburg)',
    r'(?:remote|distributed)\s+team',
    r'(?:contractor|freelancer)\s+(?:payment|management)',
    r'(?:south african|ZAR)\s+(?:team|operations|office)',
]
```

### Layer 5: GPT-4o-mini Binary Flags (~$0.50 total)

Only for ambiguous domains. Same binary-only pattern:

```
Given this company's homepage text, answer YES or NO only:
1. is_gulf_company: Is this company headquartered in UAE/Saudi/Qatar/Bahrain/Kuwait/Oman?
2. is_sa_company: Is this company headquartered in South Africa?
3. is_enterprise_500plus: Does this company have 500+ employees?
4. is_competitor: Does this company provide payroll, EOR, or HR services?
5. is_recruitment: Is this company a recruitment/staffing agency?
6. would_need_contractor_payroll: Would this company plausibly need to pay contractors in South Africa?

Company: {company_name}
Domain: {domain}
Homepage text: {text[:2000]}
```

### Layer 6: Final Scoring

```python
def final_score(contact):
    score = 0

    # Origin signal strength (40%)
    signals = contact['origin_signals']
    has_university = any(s.startswith('university:') for s in signals)
    has_language = any(s.startswith('language:') for s in signals)
    if has_university and has_language:
        score += 40  # Both = definitive SA origin
    elif has_university:
        score += 38  # University alone = very strong
    elif has_language:
        score += 34  # Afrikaans/Zulu/Xhosa alone = strong

    # Role tier (20%)
    role_pct = {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 6, 8: 2}
    score += role_pct.get(contact['role_tier'], 2)

    # Survived all filters (20%)
    if not contact.get('any_red_flag'):
        score += 20

    # Company signals (20%)
    flags = contact.get('gpt_flags', {})
    website = contact.get('website_flags', {})
    if flags.get('is_gulf_company') == 'YES':
        score += 8
    if flags.get('would_need_contractor_payroll') == 'YES':
        score += 6
    if website.get('has_buyer_signal'):
        score += 4
    if contact.get('domain') and not contact.get('no_website'):
        score += 2

    return score
```

---

## Phase 3: Opus Quality Review

Same pattern as UAE-PK (8 iterations):

1. Top 2,000 scored contacts → 5 batches of 400
2. Launch 5 parallel Opus agents
3. Each agent flags: enterprise >500, SA-HQ company, junk, non-decision-maker, PK-origin (not SA-origin)
4. **NEW check for Arabic-SA**: verify person is SA-origin, not just working in Gulf. Look for:
   - SA university in education field
   - Afrikaans/Zulu/Xhosa in languages
   - SA surname patterns (Afrikaans compounds like "van der", "du", "le")
   - Previous SA company experience
   - NOT: Arabic names without SA education (these are local Gulf nationals)
5. Aggregate removals → add domains to blacklist → re-run → repeat until <1% removal rate

---

## Phase 4: Approval Gate → FindyMail + Campaign

**STOP AND WAIT FOR APPROVAL.**

### 4A: Present for Approval
1. Write to **NEW** Google Sheet: `Arabic-SA FINAL REVIEW MMDD`
2. Columns: Rank, Name, Title, Company, Domain, Location, Origin Signals, Role Tier, Score, SA Indicators
3. Notify with: total count, top 20 sample, score distribution, per-layer removal stats
4. **WAIT for explicit go-ahead** before spending FindyMail credits

### 4B: After Approval
1. FindyMail enrichment (~60-70% hit rate expected for Gulf — better than AU)
2. Create SmartLead campaign: `EasyStaff - Arabic Gulf - SA Diaspora Mar26`
3. Set sequence adapted for SA→Gulf context (see Messaging section below)
4. Upload enriched leads
5. Launch from UI only

---

## Corridor-Specific Challenges vs UAE-PK and AU-PH

| Challenge | UAE-PK | AU-PH | Arabic-SA | Mitigation |
|-----------|--------|-------|-----------|------------|
| **Diaspora size** | Large (500K+ in UAE) | Large (300K+ in AU) | Medium (~100K in UAE, smaller elsewhere) | Cast wider net: ALL 6 Gulf countries |
| **Language signal** | Urdu = clean | Tagalog = very clean | Afrikaans = clean, but Zulu/Xhosa smaller | Multi-language: Afr + Zulu + Xhosa + Sotho |
| **Origin ambiguity** | PK names overlap Arabic | Filipino names distinctive | SA Indian overlaps with Indian-Indian | Cross with SA university for Indian surnames |
| **Enterprise noise** | Moderate | BPO heavy | SA mega-corps in Gulf (Investec, Standard Bank alumni) | Aggressive blacklist + past company filter |
| **Gulf nationals** | Not an issue (PK is separate) | Not an issue | Arabic names ≠ SA origin | Language/university filter eliminates this |
| **SA-HQ leak** | PK-HQ was issue | PH-HQ was issue | SA companies' Gulf offices (Discovery, MTN) | `.za`/`.co.za` domain suffix filter |
| **BPO noise** | Minimal | #1 issue | Not an issue for SA corridor | N/A |
| **Hit rate** | ~15-25% | ~15-50% (language) | ~8-15% (lower SA diaspora density) | Language searches have higher hit rate than surname |
| **Multi-country** | UAE only | AU only | 6 Gulf countries → 6x more searches | Most are small — combine Bahrain+Kuwait+Oman |

---

## Arabic-SA Specific Enrichment: SA Past Company Signal

Unlike other corridors, Arabic-SA benefits from a **past company** origin signal. Many SA expats in Gulf worked at iconic SA companies:

**Banks/Finance** (huge Dubai presence):
- Investec, Standard Bank, FirstRand/FNB, Absa, Nedbank, Allan Gray, Old Mutual, Sanlam, Discovery, Capitec

**Tech**:
- Naspers/Prosus, Dimension Data (NTT), Clickatell, Luno, JUMO, Takealot

**Telecom**:
- Vodacom, MTN Group, Multichoice/DSTV

**Consulting feeder** (SA offices → Dubai transfer):
- Accenture SA, Deloitte SA, PwC SA, KPMG SA, EY SA

**Mining/Engineering → Gulf infrastructure**:
- Anglo American, Sasol, Aurecon, WSP Africa, Murray & Roberts

**Action**: After scoring, add `has_sa_company_experience` flag by checking title history / LinkedIn summary for these company names. This is a **bonus origin signal** (score boost), not a requirement.

---

## Messaging Strategy (Arabic-SA Specific)

### Primary: Cost + Speed
> "Paying contractors in South Africa from [Dubai/Doha/Riyadh]? Deel charges $49/person/month + hidden FX markups on ZAR conversions. We do same-day ZAR payouts with transparent fees and a dedicated account manager."

### Secondary: Fellow SA Expat Connection
> "As a fellow South African building in the Gulf, I know the challenge of keeping your [Cape Town/JHB] team paid efficiently. We help 200+ companies manage contractor payroll across 150 countries — with special expertise in SA compliance and ZAR settlements."

### Tertiary: Scale-Up
> "Your SA team is growing? Whether it's 3 freelancers or 30, we handle SARS compliance, invoicing, and payouts — so you can focus on your [Dubai/Riyadh/Doha] business."

### Personalization Hooks
- SA university: "Fellow [UCT/Wits/Stellenbosch] grad here..."
- SA company: "I see you were at [Investec/Naspers/Discovery]..."
- SA team: "Noticed your company has a team in [Cape Town/Johannesburg]..."
- NEOM cluster: "We're already working with several companies on NEOM projects who keep tech teams in SA..."
- Gulf free zone: "Running from [DIFC/DMCC/Dubai Internet City]? We specialize in..."

---

## Data Persistence Map

```
easystaff-global/data/
├── arabic_sa_search_log.json              # Every Clay search: filters, count, capped?, file
├── clay_exports/                          # Raw Clay CSVs (NEVER modify, NEVER overwrite)
│   ├── arabic_sa_afrikaans_uae_0317.csv
│   ├── arabic_sa_afrikaans_dubai_0317.csv   (if UAE split)
│   ├── arabic_sa_afrikaans_saudi_0317.csv
│   ├── arabic_sa_afrikaans_qatar_0317.csv
│   ├── arabic_sa_zulu_uae_0317.csv
│   ├── arabic_sa_xhosa_uae_0317.csv
│   ├── arabic_sa_uni_za_top_0317.csv
│   ├── arabic_sa_uni_za_other_0317.csv
│   └── ...
├── arabic_sa_merged_MMDD.json             # Merged + deduped, with origin signals
├── arabic_sa_layer0_passed.json           # After title/company regex
├── arabic_sa_layer0_removed.json          # Removed by regex (with reasons)
├── arabic_sa_layer1_passed.json           # After blacklist
├── arabic_sa_layer1_removed.json          # Removed by blacklist
├── arabic_sa_layer3_capped.json           # After per-company cap
├── arabic_sa_website_cache.json           # ADDITIVE — reuse from other corridors
├── arabic_sa_gpt_flags.json              # Domain → GPT binary flags (ADDITIVE)
├── arabic_sa_final_scored.json           # Final scored contacts
├── arabic_sa_enterprise_candidates.json   # Domains with 10+ contacts
└── arabic_sa_blacklist_additions.json     # New entries from Opus review
```

**Reusability from other corridors**:
- `website_cache` — keyed by domain, shared across all corridors
- `enterprise_blacklist.json` — shared, grows with each corridor
- Scoring architecture — same 6-layer code, different config

---

## Google Sheets Strategy — NO OVERWRITES

| Sheet | Purpose | Action |
|-------|---------|--------|
| `18td81wAFFjRs4zxa7jkNDHxDfMydaJdkMruMHUKnmGA` | Original Arabic-SA (archived) | **DO NOT TOUCH** |
| `1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU` tab `Arabic-SouthAfrica` | Master sheet existing data | **DO NOT OVERWRITE** |
| **NEW** `Arabic-SA Clay Raw MMDD` tab on master sheet | Raw merged contacts from Clay | Create new tab |
| **NEW** `Arabic-SA Scored MMDD` sheet | Algo-scored contacts | Create via `score_corridors_algo.py` |
| **NEW** `Arabic-SA FINAL REVIEW MMDD` sheet | For operator approval | Create after Opus review |

---

## Execution Timeline

| Step | What | Duration | Cost |
|------|------|----------|------|
| Afrikaans × 6 countries | Manual Clay searches | ~15 min | $0 |
| Afrikaans UAE city splits (if capped) | Manual | ~10 min | $0 |
| Zulu × 3-4 groups | Manual | ~10 min | $0 |
| Xhosa × 2-3 groups | Manual | ~5 min | $0 |
| Secondary languages (Sotho, Tswana, Swazi) | Manual | ~5 min | $0 |
| University × 6 batches | Manual | ~15 min | $0 |
| Merge + dedup | Script | <1 min | $0 |
| Layer 0: Title/Company regex | Script | <1 sec | $0 |
| Layer 1: Blacklist | Script | <1 sec | $0 |
| Layer 2: Role scoring | Script | <1 sec | $0 |
| Layer 3: Per-company cap | Script | <1 sec | $0 |
| Layer 4: Website scraping (~1,500 domains) | Hetzner | ~10 min | $0 |
| Layer 5: GPT-4o-mini (~1,000 domains) | Hetzner | ~5 min | ~$0.50 |
| Layer 6: Final scoring | Script | <1 sec | $0 |
| Opus review (5 iterations × 5 agents) | Automated | ~1.5 hours | ~$5-8 |
| **Approval gate** | **WAIT** | — | — |
| FindyMail enrichment | Hetzner | ~20 min | ~$0.01/email |
| **Total** | | **~3-4 hours** | **~$8-12** |

---

## Comparison: All 3 Corridors

| Dimension | UAE-Pakistan | AU-Philippines | Arabic-South Africa |
|-----------|-------------|----------------|---------------------|
| Status | ✅ LIVE (2,000+ leads) | Ready for FindyMail | 📋 THIS PLAN |
| Conversion rate | ~12% | Untested | **18.2%** (proven) |
| Diaspora size in buyer | ~500K+ in UAE | ~300K+ in AU | ~100K+ across Gulf |
| Language signals | Urdu | Tagalog, Filipino, Cebuano | Afrikaans, Zulu, Xhosa |
| Unique challenge | PK-HQ companies | BPO industry | Multi-country buyer (6 Gulf states) |
| Expected campaign size | ~2,000 | ~2,000-3,000 | ~1,000-1,500 |
| Email hit rate | ~55% | ~50-60% | ~60-70% |
| Key advantage | Large diaspora | Clean language signal | Highest conversion rate |

---

## Decision Log

1. **Language-first, not surname-first**: Language searches (Afrikaans/Zulu/Xhosa) have much higher precision than surname searches for SA origin in Gulf. Surnames were the primary strategy in the old gathering — switching to language-first.
2. **All 6 Gulf countries**: Unlike UAE-PK (UAE only), Arabic-SA covers Qatar, Saudi, Bahrain, Kuwait, Oman too. More searches but larger TAM.
3. **SA Indian disambiguation**: SA Indian surnames (Naidoo, Govender) overlap with Indian-Indian. MUST cross-reference with SA university to confirm origin. Language signal insufficient (no unique SA Indian language).
4. **No overwrite**: All existing sheets preserved. New data goes to new tabs/sheets.
5. **Combine small countries**: Bahrain + Kuwait + Oman combined in single searches (expected <500 results each).
6. **Past company as bonus signal**: SA company experience (Investec, Standard Bank, etc.) is a unique enrichment for this corridor — not available for UAE-PK or AU-PH.
7. **NEOM cluster strategy**: 4+ contacts already found at NEOM. Account-based approach for mega-projects that hire SA talent.
