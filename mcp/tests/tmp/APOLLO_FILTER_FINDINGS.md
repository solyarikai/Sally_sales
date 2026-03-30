# Apollo Filter Test Findings — 2026-03-30

## Test: 23 API calls across 8 test categories

## KEY FINDINGS

### 1. KEYWORDS ARE OR
```
'IT consulting' alone:          172,869
'software development' alone:   236,946
Both together:                  376,007  ← MORE than either alone
```
**Multiple keywords = OR = broader search. Adding keywords INCREASES results.**

### 2. Industry names WORK as keyword tags
```
"IT consulting" as keyword:                   2,063 (narrow)
"information technology & services" as keyword: 17,617 (8.5x MORE)
"apparel & fashion" as keyword:               15,182
"marketing & advertising" as keyword:         117,337
```
**Apollo industry names are valid keyword tags and return WAY more companies than specific keywords.**
This means: the 112 industry names in apollo_taxonomy.json CAN be used directly as `q_organization_keyword_tags`. No tag IDs needed.

### 3. Industry filter parameter
```
organization_industry_tag_ids (with string names): 0 results ← DOESN'T WORK with names
q_organization_industry_tag_ids (with string names): 8,286,840 ← WORKS but returns everything
industry_tag_ids (with string names): 8,286,840 ← Same, too broad
```
**`q_organization_industry_tag_ids` accepts string names but seems to return ALL companies. Not useful as a filter — it's a different parameter than what we need. The real parameter needs actual tag IDs which aren't exposed in the search response.**

### 4. Companies DON'T return keywords or industry in search results
```
Top industries from search results: {} (empty)
Top keywords from search results: {} (empty)
```
**The `/mixed_companies/search` endpoint does NOT return `keywords` or `industry` fields on each company. These fields are only available via the `/organizations/enrich` endpoint (1 credit each).**

This means: the probe approach (search → extract vocabulary from results) WON'T WORK for search results. It only works after enrichment.

### 5. Location format
```
"UK" = "United Kingdom" = 150,816 (same)
"London" = "London, United Kingdom" = "London, England, United Kingdom" = 50,275 (same)
```
**Apollo normalizes location format internally. "UK" and "United Kingdom" give identical results.**

### 6. More keywords ≠ always more results
```
"fashion" alone:              19,829
"fashion brand", "apparel", "clothing": 16,972 (LESS!)
```
**More specific keywords can REDUCE results because Apollo might AND within a single tag. "fashion" matches broadly, "fashion brand" is more restrictive.**

### 7. Size filter is multiplicative (AND with keywords)
```
No size: 172,869
11-50:    24,318
11-200:   31,318
```
**Size filter is AND — it reduces results. The ranges within size filter are OR (11-50 OR 51-200 = 31,318 which is more than just 11-50).**

---

## IMPLICATIONS FOR THE EXPLORATION PIPELINE

### Strategy: Use industry names as keywords
Since `"information technology & services"` returns 17,617 vs `"IT consulting"` returns 2,063 — **industry names are the best keywords**. They're Apollo's own vocabulary.

### Optimal initial filter construction:
```
User: "IT consulting companies in Miami"
         ↓
Intent parser generates:
  apollo_industries: ["information technology & services", "management consulting", "computer software"]
  apollo_keywords: ["IT consulting", "technology consulting"]
         ↓
Apollo API call:
  q_organization_keyword_tags: [
    "information technology & services",  ← industry name AS keyword (broad)
    "management consulting",              ← industry name AS keyword (broad)
    "IT consulting",                      ← specific keyword (narrow)
  ]
  organization_locations: ["Miami"]
  organization_num_employees_ranges: ["11,50", "51,200"]
```

### Why this works:
- Industry names as keywords give 8-50x more results than specific keywords
- Keywords are OR so mixing industry names + specific terms = broad coverage
- No need for the industry tag ID mapping at all

### What WON'T work:
- `organization_industry_tag_ids` — needs actual tag IDs not available in search response
- Probe-then-extract vocabulary — search results don't include keyword/industry fields
- Only enrichment returns those fields (costs 1 credit each)
