# Dubai Digital Services Segment — New ICP

## Discovery (Mar 18, 2026)

**Origin case**: Frizzon Studios (frizzonstudios.ae)
- Founder: Achal Manglik (Indian), based in Dubai
- Apollo knows them as **"Frizzon Productions"** — 41 employees, ALL in Mumbai, India
- Dubai entity = client-facing front; production team 100% in India
- Pain: paying contractors to **Lebanon + EU** (not India — bank transfers there are cheap)
- Qualified lead, call booked with Eleonora

**Key sales feedback (Eleonora, Mar 17)**:
> "основатель и сотрудники индусы, сидят в дубаи, платить надо то в Ливан, то в ЕС, сталкивались со сложностями выплат через банк в разные страны"
>
> "если брать частый кейс ОАЭ - Индия/Пакистан, то там простой банковский дешевый перевод и поэтому мы там не нужны"

## Validation Against Qualified Leads

Analyzed 25 qualified leads from the master sheet (`17O43ThvMNB5ToqsRjwNn81MYe2tjrNql5W93-H3x008`, Leads tab).

**44% are service/digital businesses** — the exact segment we're targeting:

| Lead | Company | Type | Hypothesis |
|------|---------|------|-----------|
| Achal Gupt | Frizzon Studios | media production | UAE-India |
| Surya Palli | 10xBrand | branding agency | Sigma (conference) |
| Rashid Shaikh | ScentStrategy | marketing agency | UAE-India |
| Diksha Mulani | Zopreneurs | agency/consulting | UAE-Pakistan |
| Alexander Booth | Huckleberry | consulting | US-Mex |
| Johannes Lotter | Thomas Lotter | consulting | WW_ENG |
| Martins Lielbardis | DoingBusiness | consulting | ICE |
| Kirshen Naidoo | GigEngineer | tech/gig platform | Websummit |
| Ramon Elias | SAM Labs | edtech SaaS | US-Latam |
| Karla Sanchez | MedTrainer | healthtech SaaS | US-MX |
| Cinzia Donato | Herabiotech | biotech | US-Mex |

**4 of 25 qualified leads are from UAE corridors** — and ALL are service businesses:
- Frizzon Studios (media production)
- Zopreneurs (agency/consulting)
- ScentStrategy (marketing)
- MyZambeel (ecommerce)

**Conclusion**: Service/agency/digital businesses are the proven ICP across ALL corridors. The UAE corridor specifically converts service businesses paying to diverse countries.

## Segment Definition

**Target**: All small digital service businesses in Dubai
- Up to 100 employees (sweet spot: up to 50)
- Digital, NOT offline
- HQ or client-facing site in a business hub (Dubai, Australia, etc.)
- "Sells to Dubai → not broke" (Petr's filter)
- Last-mile qualification: employees in Apollo are all from one country (India, Pakistan, etc.) but the .ae site sells to Dubai → remote team model confirmed

**Why this works better than geo-corridors**:
- Previous approach: find people by diaspora origin (Pakistani in UAE, Filipino in AU)
- New approach: find by BUSINESS MODEL (service agency with remote team)
- Geo-corridors sent tens of thousands of emails — this is a fresh, untested angle
- Stanislav: "раньше попытки не давали результата. Но объем не сопоставим. По связкам гео мы уже десятки тысяч уже выслали"

## Step 1: Exhaust All Dubai Agencies

### Apollo People Search (UI scraper — no credits spent)

**Script**: `scripts/apollo_full_agency.js`
**Method**: `qOrganizationName` filter + `personLocations[]=Dubai` URL params

| Query | People | Companies (est) |
|-------|--------|----------------|
| marketing agency | 532 | ~50 |
| digital agency | 385 | ~40 |
| media production | 157 | ~20 |
| staffing agency | 137 | ~15 |
| creative agency | 135 | ~15 |
| advertising agency | 100 | ~12 |
| event production | 84 | ~10 |
| branding agency | 48 | ~8 |
| consulting firm | 46 | ~8 |
| design agency | 41 | ~6 |
| production house | 39 | ~6 |
| film production | 25 | ~4 |
| video production | 24 | ~4 |
| animation studio | 17 | ~3 |
| PR agency | 16 | ~3 |
| social media agency | 12 | ~2 |
| UX agency | 9 | ~2 |
| content agency | 7 | ~2 |
| post production | 7 | ~2 |
| **Scraped so far** | **393 unique** | **199 companies** |

**Current data**: `easystaff-global/data/dubai_agency_people_apollo.json`

### Technical Approach

- **Company NAME search** (`qOrganizationName=`) works for small companies
- **Domain search** (`organizationDomains[]=`) fails for small companies — returns junk
 ab instead, extract company data from person records
- **Full pagination**: scrape up to 10 pages per query (250 people/query max)

### Results (Mar 18, 2026 — full scrape)

**Script**: `scripts/apollo_companies_god.js` (35 query keywords × up to 10 pages each)
**Output**: `easystaff-global/data/dubai_agency_companies_full.json`

- **295 unique companies** (287 after cleaning junk)
- **51 companies with 3+ people** indexed in Apollo
- Top companies: Studio 52 (26 ppl), Formulate Creative (8), Wild Planet Event Production (8), SKYFRAME Animation (7), TCE Influencer Agency (7)

### Clay People Search

- Clay requires **company domains** as input — can't search by city+title alone
- Next step: extract domains from Apollo company names → feed to Clay for additional employees and location data

## Step 2: Score & Qualify

1. **Title filter**: keep Founder/CEO/MD/CFO/COO/VP Ops/HR Director — drop Specialist/Designer/Editor
2. **Company size**: prefer 5-50 employees
3. **Digital filter**: exclude offline (construction, hospitality, F&B, real estate)
4. **Dedupe** against existing campaigns and blacklist

## Step 3: Enrich & Launch

1. FindyMail for email discovery
2. Upload to SmartLead campaign (use existing 3048388 or create new)
3. Sequence: geography-neutral, trust examples ("helped a Dubai agency paying 50 contractors across 8 countries")
4. Need 100 more email inboxes — Artem to create 50 on Sally, 50 on EasyStaff domains

## Step 4: Expand to Other Hubs

After Dubai is exhausted, repeat for:
- **Australia** (Sydney, Melbourne) — already have AU-PH corridor data
- **Singapore**
- **London**
- **Berlin**
- Any business hub where small digital agencies operate with remote teams
