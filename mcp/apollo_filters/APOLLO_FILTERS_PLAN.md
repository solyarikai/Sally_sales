# Apollo `/mixed_companies/search` — All Available Filters & Fill Plan

## Endpoint
`POST https://api.apollo.io/api/v1/mixed_companies/search`
Auth: `X-Api-Key` header
Cost: 1 credit per page returned (max 100/page)

---

## ALL FILTERS

### 1. Keywords (free-text)
```
q_organization_keyword_tags: ["IT consulting", "software development"]
```
- **What it does**: Searches company keyword tags (free-text labels companies self-assign on their profiles)
- **How Apollo uses it**: OR logic — matches companies that have ANY of these keywords
- **Currently used**: YES
- **Fill from user request**: Intent parser extracts segment keywords
- **Problem**: Keywords are free-text, no fixed vocabulary. GPT might generate keywords that no company uses. The same concept has many spellings ("IT consulting" vs "information technology consulting" vs "IT services & consulting")
- **Fix plan**: After initial search, extract ACTUAL keywords from returned companies → use those for refined search

### 2. Locations
```
organization_locations: ["Miami, Florida, United States"]
```
- **What it does**: Filters by company HQ location
- **Format**: Free-text, but Apollo expects "City, State, Country" or "Country"
- **Currently used**: YES
- **Fill from user request**: Intent parser extracts geo from query ("in Miami" → "Miami, Florida, United States")
- **Problem**: Format matters. "UK" might not match, "United Kingdom" does. "Miami" alone might work differently than "Miami, Florida, United States"
- **Fix plan**: Normalize geo in intent parser (always expand abbreviations: UK→United Kingdom, UAE→United Arab Emirates)

### 3. Employee Count
```
organization_num_employees_ranges: ["11,50", "51,200", "201,500"]
```
- **What it does**: Filters by company size (employee count ranges)
- **Available ranges**: "1,10", "11,50", "51,200", "201,500", "501,1000", "1001,5000", "5001,10000", "10001,"
- **Currently used**: YES
- **Fill from user request**: `offer_analyzer.py` infers target company size from offer text (e.g., payroll → 10-200 employees)
- **Problem**: Works well, tested at 100% for EasyStaff/Fashion/OnSocial
- **Fix plan**: None needed — current approach is solid

### 4. Industry (THE MISSING FILTER)
```
organization_industry_tag_ids: ["5567cd4773696439b10b0000"]
```
- **What it does**: Filters by Apollo's industry taxonomy (112 industries)
- **Format**: Array of Apollo industry TAG IDS (not human-readable names!)
- **Currently used**: NO ← THIS IS THE GAP
- **Fill from user request**: Intent parser already generates `apollo_industries` from the taxonomy, but we need the TAG IDS not the names
- **Problem**: We have industry NAMES ("information technology & services") but Apollo wants TAG IDS ("5567cd4773696439b10b0000"). Need a name→ID mapping.
- **Fix plan**:
  1. Build industry name→ID map by making one API call and parsing the response
  2. OR: Use `q_organization_industry_tag_ids` which might accept names (need to test)
  3. OR: Apollo might have an endpoint to search industries by name

### 5. Revenue Range
```
revenue_range: {"min": 1000000, "max": 50000000}
organization_revenue_ranges: ["1,10000000", "10000001,50000000"]
```
- **What it does**: Filters by annual revenue
- **Currently used**: NO
- **Fill from user request**: Could infer from offer (enterprise SaaS → target companies with $10M+ revenue) but usually redundant with employee count
- **Fix plan**: Low priority — employee count is a better proxy for most B2B segments

### 6. Funding Stage
```
organization_latest_funding_stage_cd: ["seed", "series_a", "series_b"]
```
- **What it does**: Filters by latest funding round
- **Available values**: "seed", "angel", "series_a", "series_b", "series_c", "series_d", "series_e", "series_f", "ipo", "private_equity", "debt_financing", "grant", "other"
- **Currently used**: In `search_organizations()` signature but never passed
- **Fill from user request**: Only relevant if user explicitly mentions ("funded startups", "series A+"). Most B2B queries don't need this.
- **Fix plan**: Add to intent parser when user mentions funding context

### 7. Technologies Used
```
currently_using_any_of_technology_uids: ["5c1038e07261a02e940dd839"]
```
- **What it does**: Filters by technologies on company's website (detected by Apollo/BuiltWith)
- **Examples**: React, WordPress, Shopify, HubSpot, Salesforce
- **Currently used**: NO
- **Fill from user request**: Relevant for specific segments ("Shopify stores", "companies using HubSpot"). Requires technology UID mapping.
- **Fix plan**: Medium priority — useful for tech-specific segments. Need tech name→UID map.

### 8. Company Founded Year
```
organization_founded_year_min: 2015
organization_founded_year_max: 2023
```
- **What it does**: Filters by founding year
- **Currently used**: NO
- **Fill from user request**: Only if user says "startups founded after 2020" or similar
- **Fix plan**: Low priority — rarely needed

### 9. Domain / Website
```
q_organization_domains: "example.com\nexample2.com"
```
- **What it does**: Searches for specific domains (newline-separated)
- **Currently used**: In `enrich_by_domain()` for people search
- **Fill from user request**: Not applicable for exploration (we're discovering companies, not looking up known ones)

### 10. Organization Name
```
q_organization_name: "Acme Corp"
```
- **What it does**: Text search on company name
- **Currently used**: NO
- **Fill from user request**: Not useful for segment-based exploration

### 11. SIC Codes
```
organization_sic_codes: ["7371", "7372"]
```
- **What it does**: Filters by Standard Industrial Classification codes
- **Currently used**: NO (but we extract them from enrichment in exploration step 5)
- **Fill from user request**: Could be useful after enrichment — common SIC codes from target companies can improve precision
- **Fix plan**: Wire into optimized filters in exploration step 6

### 12. NAICS Codes
```
organization_naics_codes: ["511210", "541511"]
```
- **What it does**: Filters by North American Industry Classification System codes
- **Currently used**: NO
- **Fill from user request**: Same as SIC — useful after enrichment
- **Fix plan**: Same as SIC codes

### 13. Company Type
```
organization_type: ["privately_held", "public_company"]
```
- **What it does**: Filters by ownership type
- **Available values**: "privately_held", "public_company", "government_agency", "nonprofit", "education", "self_employed", "partnership"
- **Currently used**: NO
- **Fill from user request**: Rarely needed. Could infer (most B2B targets are privately_held)
- **Fix plan**: Low priority

---

## PRIORITY FIX ORDER

### P0: Industry filter (biggest impact)
The 112 industries in `apollo_taxonomy.json` should be used as REAL filters, not just prompt decoration.
1. Get Apollo industry tag IDs (make one search, parse response industries)
2. Build name→ID map
3. Wire `organization_industry_tag_ids` into `_apollo_search`
4. Test: does industry filter INCREASE or DECREASE result count vs keywords-only?

**Key question**: Does Apollo industry filter use AND or OR with keyword filter?
- If AND: industry + keywords = narrower but more precise
- If OR: industry + keywords = broader coverage
- Need to test both

### P1: Keyword vocabulary alignment
Current keywords are GPT-invented. Real Apollo keywords are different.
1. After first search, extract actual `keyword_tags` from returned companies
2. Use those as refined keywords for the optimized search
3. This is what the exploration enrichment step already does — but for KEYWORDS not just industries

### P2: Location normalization
"UK" → "United Kingdom", "UAE" → "United Arab Emirates"
Simple mapping, high impact.

### P3: SIC/NAICS codes from enrichment
Already extracted in exploration step 5, just not wired into the optimized filters.

---

## CURRENT STATE vs TARGET STATE

### Current (what `_apollo_search` sends)
```json
{
  "q_organization_keyword_tags": ["IT consulting", "technology consulting"],
  "organization_locations": ["Miami, Florida, United States"],
  "organization_num_employees_ranges": ["11,50", "51,200"]
}
```
3 filters. Keywords are GPT-guessed.

### Target (what it SHOULD send)
```json
{
  "q_organization_keyword_tags": ["IT consulting", "technology consulting", "IT services"],
  "organization_industry_tag_ids": ["5567cd4773696439b10b0000"],
  "organization_locations": ["Miami, Florida, United States"],
  "organization_num_employees_ranges": ["11,50", "51,200"],
  "organization_sic_codes": ["7371"]
}
```
5 filters. Keywords from real Apollo data. Industry from taxonomy. SIC from enrichment.

---

## HOW TO FILL EACH FILTER FROM USER REQUEST

| Filter | Source | When | How |
|--------|--------|------|-----|
| `q_organization_keyword_tags` | Intent parser → probe → refine | Always | GPT initial guess → Apollo probe (1 credit) → extract real keywords from results → refined search |
| `organization_industry_tag_ids` | Intent parser → taxonomy map | Always | GPT maps user query to industry names → lookup tag IDs from map → apply |
| `organization_locations` | Intent parser | Always | GPT extracts geo → normalize format |
| `organization_num_employees_ranges` | Offer analyzer | Always | GPT infers target company size from offer/product |
| `organization_latest_funding_stage_cd` | Intent parser | When user mentions funding | Only if "funded", "startup", "series A" in query |
| `currently_using_any_of_technology_uids` | Intent parser | When user mentions tech | Only if "Shopify stores", "using HubSpot" in query |
| `organization_sic_codes` | Enrichment step | After exploration | Extract from top 5 enriched targets, add to optimized filters |
| `organization_revenue_ranges` | Offer analyzer | Rarely | Only if user specifies revenue explicitly |
| `organization_founded_year_min/max` | Intent parser | When user mentions age | Only if "founded after 2020" in query |
