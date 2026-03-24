# EasyStaff Global — Exact Apollo Filter Sets for Gathering

**Date**: 2026-03-25
**Source**: Reverse-engineered from 27 qualified leads + Apollo enrichment
**Prompt**: V12 (catches all 4 target segments)
**Method**: `apollo.companies.emulator` (Puppeteer, free — no API credits)

---

## Available Apollo Filters (from adapter)

| Filter | Field Name | Type | Description |
|--------|-----------|------|-------------|
| **Location** | `organization_locations` | List[str] | Country or city names |
| **Industry tags** | `organization_industry_tag_ids` | List[str] | Apollo industry IDs |
| **Keywords** | `keywords` | List[str] | Free-text keyword search |
| **Employee size** | `organization_num_employees_ranges` | List[str] | Ranges like "11,50" |
| **Funding stage** | `organization_latest_funding_stage_cd` | List[str] | seed, series_a, etc. |
| **Sort** | `sort_by_field` | str | Default: recommendations_score |
| **Pages** | `max_pages` | int | Max pages to scrape (25 results/page) |

---

## FILTER SET 1: Tech/SaaS/Fintech (P1 — highest priority)

### 1A: SaaS & Software Companies

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["saas", "software development", "b2b software", "enterprise software", "cloud platform"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,500"],
    "max_pages": 50
  }
}
```

**Run in cities**: San Francisco, New York, London, Berlin, Amsterdam, Tel Aviv, Toronto, Singapore, Bangalore, Sydney

### 1B: Fintech & Payments

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["fintech", "payments", "banking technology", "financial services software", "payment processing"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,500"],
    "max_pages": 50
  }
}
```

**Run in cities**: London, New York, San Francisco, Singapore, Berlin, Dubai, Tel Aviv, Zurich

### 1C: EdTech & HealthTech

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["edtech", "healthtech", "biotech", "medtech", "education technology", "health technology"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,500"],
    "max_pages": 30
  }
}
```

**Run in cities**: San Francisco, Boston, New York, London, Berlin, Bangalore

### 1D: AI & Data Companies

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["artificial intelligence", "machine learning", "data analytics", "AI platform", "computer vision"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,500"],
    "max_pages": 30
  }
}
```

**Run in cities**: San Francisco, New York, London, Berlin, Tel Aviv, Toronto, Bangalore

### 1E: Crypto & Web3

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["cryptocurrency", "blockchain", "web3", "defi", "crypto exchange", "digital assets"],
    "organization_num_employees_ranges": ["3,10", "11,50", "51,200"],
    "max_pages": 30
  }
}
```

**Run in cities**: Dubai, Singapore, London, Zurich, Lisbon, Miami, Berlin

---

## FILTER SET 2: Gaming/iGaming (P2 — highest revenue per lead)

### 2A: Game Studios

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["game development", "mobile games", "game studio", "video games", "indie games", "casual games"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,1000"],
    "max_pages": 50
  }
}
```

**Run in cities**: Copenhagen, Stockholm, Helsinki, London, LA, Montreal, Berlin, Kyiv, Warsaw, Tokyo

### 2B: iGaming & Casino Tech

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["igaming", "online casino", "sports betting", "gambling technology", "real money gaming", "casino platform"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,1000"],
    "max_pages": 50
  }
}
```

**Run in cities**: Malta, London, Stockholm, Gibraltar, Isle of Man, Tallinn, Limassol (Cyprus), Dublin

### 2C: Esports & Gaming Services

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["esports", "gaming marketing", "game QA", "game localization", "gaming community", "twitch"],
    "organization_num_employees_ranges": ["3,10", "11,50", "51,200"],
    "max_pages": 30
  }
}
```

**Run in cities**: LA, London, Berlin, Seoul, Singapore

---

## FILTER SET 3: Agencies/Consulting (P3 — expand existing)

### 3A: Digital/Creative Agencies (already proven — expand cities)

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["digital agency", "creative agency", "marketing agency", "design agency", "branding agency"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200"],
    "max_pages": 50
  }
}
```

**NEW cities**: Manchester, Edinburgh, Copenhagen, Munich, Hamburg, Warsaw, Prague, Vienna, Lisbon, Barcelona, Brisbane, Perth, Delhi, Hyderabad, Chennai, Pune

### 3B: IT Consulting & CRM Partners

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["IT consulting", "CRM implementation", "Salesforce partner", "Zoho partner", "HubSpot partner", "ERP consulting", "business automation"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200"],
    "max_pages": 30
  }
}
```

**Run in cities**: Dubai, London, New York, Bangalore, Singapore, Sydney

### 3C: Affiliate & Performance Marketing

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["affiliate marketing", "performance marketing", "user acquisition", "growth marketing", "demand generation"],
    "organization_num_employees_ranges": ["3,10", "11,50", "51,200"],
    "max_pages": 30
  }
}
```

**Run in cities**: London, New York, Berlin, Barcelona, Dubai, Tel Aviv

---

## FILTER SET 4: Media/Creative (P4)

### 4A: Media Production & Video

```json
{
  "source_type": "apollo.companies.emulator",
  "filters": {
    "organization_locations": ["CITY"],
    "keywords": ["media production", "video production", "animation studio", "post production", "broadcast media", "content studio"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200"],
    "max_pages": 30
  }
}
```

**Run in cities**: LA, London, New York, Dubai, Berlin, Mumbai, Sydney, Toronto

---

## Execution Summary

| Set | Sub | Keywords | Cities | Est. Pages | Est. Companies |
|-----|-----|----------|--------|-----------|---------------|
| 1A | SaaS/Software | 5 | 10 | 500 | 12,500 |
| 1B | Fintech | 5 | 8 | 400 | 10,000 |
| 1C | EdTech/HealthTech | 6 | 6 | 180 | 4,500 |
| 1D | AI/Data | 5 | 7 | 210 | 5,250 |
| 1E | Crypto/Web3 | 6 | 7 | 210 | 5,250 |
| 2A | Game Studios | 6 | 10 | 500 | 12,500 |
| 2B | iGaming | 6 | 8 | 400 | 10,000 |
| 2C | Esports | 6 | 5 | 150 | 3,750 |
| 3A | Agencies (new cities) | 5 | 16 | 800 | 20,000 |
| 3B | IT Consulting | 7 | 6 | 180 | 4,500 |
| 3C | Affiliate Marketing | 5 | 6 | 180 | 4,500 |
| 4A | Media Production | 6 | 8 | 240 | 6,000 |
| **TOTAL** | | | | **3,950** | **~98,750** |

After dedup + V12 analysis + Opus verification: expect **15,000-25,000 new targets** (15-25% target rate across segments).

All free via Puppeteer emulator (no Apollo credits). Cost: website scraping (free) + GPT-4o-mini analysis (~$5 for 100K companies) + Opus verification (~$10).

---

## People Search Filters (after targets verified)

For each verified target company, find decision-makers:

```json
{
  "source_type": "apollo.people.emulator",
  "filters": {
    "person_seniorities": ["founder", "c_suite", "vp", "director", "owner"],
    "person_titles": ["CEO", "CFO", "COO", "CTO", "VP Operations", "VP Finance", "Head of Finance", "Director of Operations"],
    "organization_num_employees_ranges": ["5,10", "11,50", "51,200", "201,500"],
    "limit_per_company": 3
  }
}
```

Target: up to 3 decision-makers per company.
Then FindyMail verification for emails Apollo doesn't provide.
