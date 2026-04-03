# EasyStaff Global — Apollo Labels for ALL 27 Qualified Leads

**Date**: 2026-03-24
**Source**: Apollo Organization Enrich API on 25 domains (2 gmail-only skipped)
**Purpose**: Reverse-engineer Apollo filters to find MORE companies like our qualified leads

---

## 4 Target Segments (priority order)

### SEGMENT 1: Tech/SaaS Product Companies + Fintech (9 leads)

| Company | Domain | Apollo Industry | Employees | Country | Key Keywords |
|---------|--------|----------------|-----------|---------|-------------|
| MedTrainer | medtrainer.com | information technology & services | 390 | US | osha compliance, credentialing, elearning, healthcare compliance |
| Tactile Games | tactilegames.com | computer games | 250 | Denmark | casual games, mobile games, f2p, puzzle games |
| Tazahtech | tazahtech.com | information technology & services | 67 | Pakistan | agri logistics, market access platform, agri marketplace |
| SAM Labs | samlabs.com | primary/secondary education | 42 | US | edtech, steam, electronics, software, development |
| Puzzle.tech | puzzle.tech | staffing & recruiting | 62 | US | tech recruiting, engineers, headhunting |
| Amaiz | amaiz.com | banking | 20 | UK | swift, startup, making tax digital, mass card issuing |
| Herabiotech | herabiotech.com | research | 11 | US | diagnostics, reproductive health, biotechnology |
| BetterThings | betterthin.gs | information technology & services | 4 | Estonia | product design, it system design |
| FirstByt | firstbyt.com | financial services | 5 | Lithuania | trading platform, cryptocurrency, decentralized exchange |

**Apollo filters for this segment:**
```json
{
  "q_organization_keyword_tags": ["information technology & services", "computer software", "software development", "fintech", "edtech", "saas"],
  "organization_num_employees_ranges": ["1,10", "11,50", "51,200", "201,500"],
  "organization_locations": ["United States", "United Kingdom", "Denmark", "Estonia", "Lithuania", "Germany", "Netherlands"]
}
```

### SEGMENT 2: Gaming/iGaming (4 leads)

| Company | Domain | Apollo Industry | Employees | Country | Key Keywords |
|---------|--------|----------------|-----------|---------|-------------|
| Tactile Games | tactilegames.com | computer games | 250 | Denmark | casual games, mobile games, f2p |
| Gaming Audiences | gamingaudiences.com | marketing & advertising | 5 | US | social casino, mobile user acquisition, real money gaming |
| iGaming RealTalk | igamingrealtalk.com | gambling & casinos | 1 | — | igaming, podcast, gambling |
| Frizzon Studios | frizzonstudios.ae | media production | 3 | UAE | broadcast media, digital media, sports coverage |

**Apollo filters for this segment:**
```json
{
  "q_organization_keyword_tags": ["computer games", "mobile games", "igaming", "gambling", "casino", "gaming", "esports"],
  "organization_num_employees_ranges": ["1,10", "11,50", "51,200", "201,1000"],
  "organization_locations": ["United States", "United Kingdom", "Denmark", "Malta", "Cyprus", "United Arab Emirates", "Sweden", "Finland"]
}
```

### SEGMENT 3: Agencies/Consulting (4 leads)

| Company | Domain | Apollo Industry | Employees | Country | Key Keywords |
|---------|--------|----------------|-----------|---------|-------------|
| Huckleberry | consulthuckleberry.com | management consulting | 2 | US | business consulting, management consulting |
| Zopreneurs | zopreneurs.com | information technology & services | 19 | UAE | crm, business automation, it consulting, workflow automation |
| DoingBusiness | doingbusiness.live | management consulting | 2 | Latvia | project management, sales consultancy, corporate training |
| AffilROI | affilroi.com | internet | 6 | Italy | affiliate tracking, sales analytics, affiliate management |

**Apollo filters for this segment:**
```json
{
  "q_organization_keyword_tags": ["management consulting", "business consulting", "it consulting", "digital agency", "creative agency", "marketing agency"],
  "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
  "organization_locations": ["United States", "United Arab Emirates", "United Kingdom", "Germany", "Italy", "Latvia", "Australia"]
}
```

### SEGMENT 4: Media/Creative (2 leads)

| Company | Domain | Apollo Industry | Employees | Country | Key Keywords |
|---------|--------|----------------|-----------|---------|-------------|
| LotterMedia | lottermedia.com | (no Apollo data) | ~50 | Germany | music royalties, media production (SIGNED CONTRACT) |
| Frizzon Studios | frizzonstudios.ae | media production | 3 | UAE | broadcast media, digital media, sports coverage |

**Apollo filters for this segment:**
```json
{
  "q_organization_keyword_tags": ["media production", "broadcast media", "video production", "content creation", "animation"],
  "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
  "organization_locations": ["United States", "United Arab Emirates", "United Kingdom", "Germany", "Australia"]
}
```

---

## Other Qualified Leads (lower priority — don't build segments for these)

| Company | Domain | Industry | Emp | Country | Notes |
|---------|--------|----------|-----|---------|-------|
| H2O Allegiant | h2oallegiant.com | environmental services | 2 | US | Water recycling, 4-5 MX contractors |
| ComingOut | comingoutspb.org | nonprofit | 5 | Lithuania | SIGNED, 30+ people — nonprofit, not a segment |
| IGT Glass | igt-glasshardware.com | building materials | 42 | US | Glass hardware, Deel user — manufacturing |
| RIVIA Fragrances | riviafragrances.com | health/wellness | 15 | UAE | Scent branding — retail |
| SaviorHire | saviorhire.com | IT services | 2 | Armenia | HR consulting — too small |
| Moviton | moviton.com | logistics | 4 | — | UAE→CO, logistics |
| PetPos | petpos.com | (no data) | — | — | Pet business |
| Gig Engineer | gigengineer.io | IT services | 11 | South Africa | Gig work platform |

---

## Aggregate Apollo Label Frequencies (all 23 enriched)

### Industries
| Industry | Count | Priority |
|----------|-------|----------|
| information technology & services | 6 | **P1** |
| management consulting | 2 | P3 |
| computer games | 1 | **P2** |
| gambling & casinos | 1 | **P2** |
| media production | 1 | P4 |
| banking | 1 | P1 (fintech) |
| financial services | 1 | P1 (fintech) |
| marketing & advertising | 1 | P2/P3 |
| staffing & recruiting | 1 | P1 (talent platform) |
| primary/secondary education | 1 | P1 (edtech) |
| research | 1 | P1 (biotech) |

### Top Keywords (3+ occurrences across all qualified)
| Keyword | Count | Use in Apollo Search |
|---------|-------|---------------------|
| b2b | 16 | YES |
| information technology & services | 16 | YES |
| services | 13 | context |
| internet | 8 | YES |
| computer software | 7 | YES |
| consulting | 7 | YES |
| consumers | 7 | context |
| marketing & advertising | 6 | YES |
| e-commerce | 5 | YES |
| consumer internet | 5 | context |
| enterprise software | 4 | YES |
| financial services | 4 | YES |
| operational efficiency | 4 | context |
| software development | 3 | YES |
| finance technology | 3 | YES |

### Employee Size Distribution
```
1-10:   12 companies (52%)
11-50:   5 companies (22%)
51-200:  4 companies (17%)
200+:    2 companies (9%)

Median: 6 employees
Range: 1-390
Sweet spot: 5-200 (covers 78% of qualified)
```

### Countries
| Country | Count |
|---------|-------|
| United States | 8 |
| United Arab Emirates | 3 |
| Lithuania | 2 |
| South Africa, Latvia, Pakistan, Italy, Estonia, Armenia, UK, Denmark | 1 each |

---

## Recommended Apollo Search Queries

### Query 1: Tech/SaaS + Fintech (P1 — largest segment)
```json
{
  "q_organization_keyword_tags": ["b2b", "saas", "software development", "fintech", "edtech", "enterprise software", "finance technology"],
  "organization_num_employees_ranges": ["5,50", "51,200", "201,500"],
  "organization_locations": ["United States", "United Kingdom", "Germany", "Netherlands", "Denmark", "Estonia"],
  "per_page": 100
}
```

### Query 2: Gaming/iGaming (P2 — highest revenue per lead)
```json
{
  "q_organization_keyword_tags": ["mobile games", "igaming", "casino", "gaming", "game development", "esports"],
  "organization_num_employees_ranges": ["5,50", "51,200", "201,1000"],
  "organization_locations": ["United States", "United Kingdom", "Denmark", "Malta", "Cyprus", "Sweden", "Finland", "United Arab Emirates"],
  "per_page": 100
}
```

### Query 3: Agencies (P3 — already well-covered)
```json
{
  "q_organization_keyword_tags": ["digital agency", "creative agency", "marketing agency", "it consulting", "management consulting"],
  "organization_num_employees_ranges": ["5,50", "51,200"],
  "organization_locations": ["United States", "United Arab Emirates", "United Kingdom", "Australia", "Germany"],
  "per_page": 100
}
```

### Query 4: Media/Creative (P4)
```json
{
  "q_organization_keyword_tags": ["media production", "video production", "content creation", "broadcast media", "animation studio"],
  "organization_num_employees_ranges": ["5,50", "51,200"],
  "organization_locations": ["United States", "United Arab Emirates", "United Kingdom", "Germany"],
  "per_page": 100
}
```
