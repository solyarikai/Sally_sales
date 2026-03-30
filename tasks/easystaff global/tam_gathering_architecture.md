# TAM Gathering Machine — Architecture & Plan

## Goal
5,000+ C-level decision-maker contacts per geographic corridor for EasyStaff Global (project_id=9).

## Corridors

| Corridor Key | Employer Countries | Target Country | Sheet Tab |
|---|---|---|---|
| `uae-pakistan` | UAE | Pakistan | UAE-Pakistan |
| `australia-philippines` | Australia | Philippines | AU-Philippines |
| `arabic-south-africa` | UAE, Saudi Arabia, Qatar, Bahrain, Kuwait, Oman | South Africa | Arabic-SouthAfrica |

## Google Sheet (ONE sheet, all corridors)

**Master Sheet**: https://docs.google.com/spreadsheets/d/1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU

Tabs:
- **UAE-Pakistan** — contacts with full provenance
- **AU-Philippines** — contacts with full provenance
- **Arabic-SouthAfrica** — contacts with full provenance
- **Approaches Log** — every search attempt across ALL corridors, including zero-result ones

API: `POST /api/diaspora/gather-all` creates master sheet + launches all corridors in parallel.

Previous separate sheets (archived, data preserved):
- UAE-PK: `16ArK2XldNVKPjF-VxKZTguJQffFgNx2ybmvPtguyKfA` (~3,102 contacts)
- AU-PH: `1WvUlu3nb4eUBEjEtZ5irjET8HJ0a37v4JT7LmqpXihc` (~1,629 contacts)
- Arabic-SA: `18td81wAFFjRs4zxa7jkNDHxDfMydaJdkMruMHUKnmGA` (~1,329 contacts)

---

## Approach Execution Order (cheapest first)

### Cost Model

| Classification Method | Cost per Contact | Speed |
|---|---|---|
| Surname auto-accept (name in country list) | **$0** | instant |
| Distinctive surname search auto-accept | **$0** | instant |
| GPT-4o-mini classification | **~$0.001** | ~2s per batch of 50 |
| Clay People Search (Puppeteer) | **$0** (scraping) | ~60-90s per batch |

**Key insight**: the ONLY cost variable is GPT classification. Clay scraping is free. So the optimization is: minimize the number of contacts sent to GPT.

### Execution Pipeline

```
Phase 1: University Search (HIGH yield, CHEAP)
  ├─ For each university batch (4 batches per country):
  │   ├─ Clay search: schools=X, countries=Y, titles=C-level
  │   ├─ DEDUP: skip contacts already found
  │   ├─ AUTO-ACCEPT: surname in country name list → score=9, $0
  │   └─ GPT: only classify remaining unknowns
  │
Phase 2: Extended University Search (MEDIUM yield, CHEAP)
  ├─ Same as Phase 1 with 2 more university batches per country
  │   (smaller/regional universities, lower hit rate but still cheap)
  │
Phase 3: Surname Search (MEDIUM yield, CHEAPEST per new contact)
  ├─ For each surname batch (6-8 batches per country):
  │   ├─ Clay search: name=Surname, countries=Y, titles=C-level
  │   ├─ DEDUP: skip contacts already found (most will be dupes)
  │   ├─ DISTINCTIVE surname (in country list) → auto-accept ALL, $0
  │   └─ AMBIGUOUS surname → GPT classify only new contacts
  │
Phase 4: Title-Split Search (LOW yield of NEW contacts, MEDIUM cost)
  ├─ For each C-level title individually (12 titles):
  │   ├─ Clay search: job_title=X, countries=Y (no school/name filter)
  │   ├─ DEDUP: skip already found (heavy overlap expected)
  │   ├─ AUTO-ACCEPT: surname match → $0
  │   └─ GPT: classify remaining unknowns
  │
Phase 5: Industry Search (LOWEST yield, MOST EXPENSIVE)
  ├─ For each industry batch (12 industries):
  │   ├─ Step A: Clay Company Search → get domains
  │   ├─ Step B: Clay People Search at those domains
  │   ├─ DEDUP + AUTO-ACCEPT + GPT classify
  │   └─ TWO Clay calls per batch = slowest approach
```

### Title Splits (Phase 4)

| Label | Title Filter |
|---|---|
| ceo | CEO |
| founder | Founder |
| cto | CTO |
| cfo | CFO |
| coo | COO |
| managing_director | Managing Director |
| vp | VP |
| director | Director |
| head_of | Head of |
| partner | Partner |
| general_manager | General Manager |
| country_manager | Country Manager |

### Industry Batches (Phase 5)

| Label | Industries |
|---|---|
| tech_it | IT Services, Software Development, Technology |
| fintech_finance | Financial Services, Banking, Investment Banking |
| ecommerce_retail | E-commerce, Retail, Consumer Services |
| construction_realestate | Construction, Real Estate, Civil Engineering |
| trading_logistics | International Trade, Wholesale, Transportation |
| consulting_professional | Business Consulting, Management Consulting |
| marketing_media | Marketing Services, Advertising, Media |
| healthcare_pharma | Healthcare, Pharmaceutical, Medical Devices |
| education_hr | Education, E-Learning, Human Resources |
| hospitality_tourism | Hospitality, Travel, Food & Beverage |
| gaming_entertainment | Computer Games, Entertainment, Online Gaming |
| energy_manufacturing | Oil & Gas, Renewable Energy, Manufacturing |

---

## Dedup-Before-Classify Architecture

Every phase follows the same pattern:

```
Clay Search → Raw Contacts
    │
    ▼
DEDUP against all_matched_contacts (in-memory set)
  key = linkedin_url OR "name|company"
    │
    ├─ ALREADY FOUND → skip entirely ($0, 0 time)
    │
    └─ NEW CONTACTS
         │
         ├─ SURNAME MATCH (name part in country name list) → auto-accept, score=9, $0
         │
         └─ UNKNOWN → send to GPT-4o-mini classification
              │
              ├─ _origin_match=True, score≥6 → accept
              └─ _origin_match=False → reject
```

### Surname Pre-Filter

`_build_surname_set()` builds a lowercase set from `COUNTRY_NAME_PROFILES[country]`:
- All first_names (comma-separated list)
- All last_names (comma-separated list)
- Total: ~130-180 names per country

A contact auto-accepts if ANY part of their full name (split by spaces/hyphens) appears in this set.

### GPT Classification

`classify_names_by_origin()`:
- Model: GPT-4o-mini
- Batch size: 50 contacts per API call
- Input: name, title, company + country-specific disambiguation rules
- Output: score 1-10 + match boolean
- Threshold: score ≥ 6 = match
- Cost: ~$0.001 per batch = ~$0.00002 per contact

---

## Per-Contact Provenance (Contacts Tab Columns)

Every contact in the Google Sheet carries full provenance:

| Column | Description | Example |
|---|---|---|
| `_search_type` | Which phase found this contact | `university_people_first`, `extended_university`, `surname_search`, `title_split`, `industry` |
| `_search_batch` | Specific batch label | `pk_top_business`, `ph_surname_2`, `ceo` |
| `_schools_filter` | Universities used as filter | `LUMS, IBA Karachi, NUST` |
| `_location_filter` | Countries searched in | `United Arab Emirates` |
| `_title_filter` | Title filter applied | `C-level/VP/Director/Head` or `CEO` |
| `_corridor` | Corridor key | `uae-pakistan` |
| `_found_at` | ISO timestamp | `2026-03-13T12:34:56` |
| `_match_reason` | How the match was determined | `auto-accepted (surname+university). Education: LUMS. In UAE.` |
| `_origin_score` | Classification confidence | `9` (auto-accept) or `7` (GPT) |
| `_origin_match` | Boolean: is from target country | `True` |

### Match Reason Values

| Score | Method | Meaning |
|---|---|---|
| 9 | `auto-accepted (surname+university)` | Known surname + target country university |
| 9 | `auto-accepted (surname)` | Known surname in title-split search |
| 8 | `auto-accepted (distinctive surname)` | Searched by distinctive surname, auto-accept all |
| 8 | fallback on GPT failure | University/surname signal strong, GPT errored |
| 6-10 | `GPT score=X/10` | GPT-4o-mini classified this contact |

---

## Approaches Log (every search tracked)

The Approaches Log tab records EVERY search attempt with 17 columns:

| Column | Description |
|---|---|
| timestamp | When this search ran |
| search_type | `university_people_first`, `extended_university`, `surname_search`, `title_split`, `industry` |
| batch_name | Batch label (e.g., `pk_top_business`, `ph_surname_3`) |
| schools_filter | Universities used (empty for non-university searches) |
| location_filter | Countries searched |
| title_filter | Title filter applied |
| name_filter | Surname filter (surname search only) |
| contacts_found | Raw contacts from Clay |
| decision_makers | After C-level title filter |
| prefilter_candidates | After dedup (new contacts only) |
| matched | Contacts that passed classification |
| hit_rate | matched / classified as percentage |
| new_unique | Net new contacts added (after global dedup) |
| total_so_far | Running total of all contacts |
| cost_estimate | GPT cost for this batch |
| assessment | Human-readable summary |
| next_action | What pipeline does next |

**Zero-result searches are logged too** — so you always know what was tried.

---

## University Batches Per Country

### Pakistan (4 main + 2 extended = 6 total)
| Batch | Schools |
|---|---|
| pk_top_business | LUMS, IBA Karachi, NUST |
| pk_engineering | NED University, GIK Institute, FAST-NUCES, COMSATS, UET Lahore |
| pk_general | University of Punjab, Quaid-i-Azam, Aga Khan, University of Karachi, PIEAS, Bahria |
| pk_other | University of Peshawar, Habib University, GIK, Air University, NDU Pakistan, Sukkur IBA |
| pk_uni_ext_1 | SZABIST, UMT, Forman Christian College, Uni of Faisalabad, GCU |
| pk_uni_ext_2 | Beaconhouse National, UCP, Riphah International, IIUI, FAST Lahore |

### Philippines (4 main + 2 extended = 6 total)
| Batch | Schools |
|---|---|
| ph_top | UP, Ateneo de Manila, De La Salle, UST, AIM |
| ph_other | Mapua, Adamson, FEU, USC, Silliman, Xavier |
| ph_more | PUP, UE, NU Philippines, Lyceum, Centro Escolar, San Beda |
| ph_tech | TUP, Mindanao State, San Agustin, PLM, CPU |
| ph_uni_ext_1 | UP Diliman, Philippine Normal, Manila Central, Perpetual Help, PWU |
| ph_uni_ext_2 | Cebu Tech, MSU, WMSU, Batangas State, Bulacan State |

### South Africa (3 main + 2 extended = 5 total)
| Batch | Schools |
|---|---|
| za_top | UCT, Wits, Stellenbosch, UP, UJ |
| za_other | UKZN, Rhodes, UFS, NWU, Nelson Mandela |
| za_more | UNISA, DUT, CPUT, TUT, Walter Sisulu |
| za_uni_ext_1 | Monash SA, UL, Univen, MUT, CUT |
| za_uni_ext_2 | UniZulu, Sol Plaatje, SMU, Fort Hare, UWC |

## Surname Batches Per Country

### Pakistan (8 batches, 41 surnames)
- Tier 1 (very distinctive): Malik, Butt, Chaudhry, Rana, Rajput, Akhtar, Bhatti, Gill, Cheema, Awan, Virk, Warraich, Gondal, Bajwa, Afridi, Khattak, Siddiqui, Qureshi, Sethi, Khawaja, Memon, Paracha, Arain, Minhas, Lodhi, Mughal, Niazi, Baloch, Durrani, Leghari
- Tier 2 (common): Khan (solo batch — massive volume), Rizvi, Naqvi, Bukhari, Gilani, Pirzada

### Philippines (6 batches, 28 surnames)
- Main: Santos, Reyes, Cruz, Bautista, Ocampo, Mendoza, Villanueva, Ramos, Aquino, Castillo, Tolentino, Pangilinan, Dizon, Cunanan, Manalo, Soriano, Mercado, Aguilar, Enriquez, Magno
- Chinese-Filipino: Tan, Chua, Go, Ong, Sy
- Compound: dela Cruz, de los Santos, del Rosario

### South Africa (8 batches, 40 surnames)
- Afrikaans: Botha, du Plessis, van der Merwe, Pretorius, Joubert, Steyn, Coetzee, Venter, Swanepoel, Kruger, Erasmus, du Toit, Vermeulen, Fourie, le Roux, van Zyl, Visser, Viljoen, Louw, Marais
- Zulu/Xhosa/Sotho: Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo, Ngcobo, Sithole, Mthembu, Radebe, Molefe
- SA Indian: Naidoo, Govender, Pillay, Chetty, Moodley
- Business: Motsepe, Wiese, Bekker, Sobrato, Dippenaar

---

## API

### Start pipeline
```
POST /api/diaspora/gather
{
  "corridor": "uae-pakistan",        // or null for all
  "project_id": 9,
  "target_count": 5000,
  "mode": "full_tam",               // "university" | "full" | "full_tam"
  "existing_sheet_id": "16ArK2X..." // append to existing sheet
}
```

### Check progress
```
GET /api/diaspora/status
→ { pipelines: { "uae-pakistan": { status, progress[], result } } }
```

### Infrastructure
- **Clay Puppeteer**: `scripts/clay/clay_people_search.js` — automates Clay.com People Search UI
  - `--countries` — location filter
  - `--schools` — university filter
  - `--name` — surname/name filter
  - `--job-title` — single title filter
  - `--titles` — use standard C-level title set
- **Clay Service**: `backend/app/services/clay_service.py` — Python↔Node.js bridge with live progress streaming
- **Diaspora Service**: `backend/app/services/diaspora_service.py` — main pipeline orchestrator
- **Google Sheets**: service account auth, shared drive, incremental export after every batch

---

## Expected Yields Per Phase

Based on initial runs (March 13, 2026):

| Phase | Contacts per batch | Hit rate | New unique rate | GPT cost per batch |
|---|---|---|---|---|
| University | 500-5000 | 15-50% | HIGH (first pass) | LOW (most auto-accepted) |
| Extended Uni | 200-2000 | 10-30% | MEDIUM (overlap with Phase 1) | LOW |
| Surname (distinctive) | 500-5000 | 100% auto-accept | LOW (heavy overlap) | **$0** |
| Surname (ambiguous) | 500-5000 | 5-20% GPT | LOW (heavy overlap) | MEDIUM |
| Title-split | 2000-5000 | 3-15% | LOW (most already found) | MEDIUM-HIGH |
| Industry | 100-1000 | 5-25% | MEDIUM (different companies) | HIGH (2 Clay calls) |

### Key Observations
- AU-PH has highest surname auto-accept rate (~926/4893 = 19% from first batch alone)
- UAE-PK surname overlap is massive — "Arain" batch: 4936 classified, only 2 new unique
- Arabic-SA has lowest hit rate (~7.8%) — many surnames don't appear in Gulf region
- University batches are the best ROI: high yield, many auto-accepts, new unique contacts

---

## What's Running Now (March 13, 2026)

All 3 corridors restarted with **optimized dedup-first code** on production.
Mode: `full_tam` with `existing_sheet_id` to append to existing sheets.

Previous run totals (before restart):
- UAE-PK: ~3,102 contacts
- AU-PH: ~1,629 contacts
- Arabic-SA: ~1,329 contacts

Target: 5,000 per corridor = 15,000 total.
