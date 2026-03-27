# Apollo Filter Intelligence — Plan

## Problem

User says: "find IT consulting businesses in London"
System needs to produce EXACT Apollo filters:
```json
{
  "organization_locations": ["London"],
  "q_organization_keyword_tags": ["it services", "it consulting", "digital transformation", "business automation", "software development"],
  "organization_num_employees_ranges": ["1,10", "11,50", "51,200"]
}
```

Apollo has its OWN taxonomy of ~200 industries and thousands of keywords. The system can't guess — it must use Apollo's actual vocabulary.

## Why hardcoding fails

- "IT consulting" maps to "information technology & services" in Apollo — NOT "IT consulting"
- Keywords like "crm implementation", "business automation" appear frequently for this segment but are NOT obvious from the query
- Different segments have completely different keyword distributions
- Apollo's taxonomy changes over time

## Approach: Probe + Extract (ZERO hardcoding)

### Step 1: LLM generates CANDIDATE filters from natural language

GPT-4o-mini translates user query → initial Apollo filter guess:
```
User: "IT consulting businesses in London"
GPT: {
  locations: ["London, United Kingdom"],
  keywords: ["IT consulting", "IT services", "technology consulting"],
  employee_ranges: ["1,10", "11,50", "51,200"]
}
```

This is a ROUGH guess. Many keywords will be wrong or missing.

### Step 2: Probe search (1 page = 25 results, 1 credit)

Run a SMALL Apollo search with the candidate filters. Get 25 real companies back.

### Step 3: Extract Apollo's ACTUAL taxonomy from results

Each returned company has Apollo's real labels:
- `industry`: "information technology & services" (6 of 25)
- `keywords`: ["it services & it consulting", "software development", "digital transformation"]
- `employee_count`: distribution

Count frequency of each industry and keyword across the 25 results.

### Step 4: Build REFINED filters from real Apollo data

Take the TOP industries (≥20% frequency) and TOP keywords (≥10% frequency). These ARE Apollo's vocabulary for this segment.

### Step 5: Show user the refined filters + ask to confirm

```
Based on a test search of 25 companies matching "IT consulting in London":

Industries found: information technology & services (88%), management consulting (12%)
Top keywords: it services & it consulting (4), software development (3), digital transformation (2)

Suggested filters:
  keywords: ["it services", "it consulting", "digital transformation", "software development"]
  industries: ["information technology & services"]

Shall I search with these filters?
```

### Step 6 (Optional): Background taxonomy cache

A background cron populates a cache of Apollo's industry/keyword taxonomy:
- Periodically runs searches for common segments
- Stores industry→keyword mappings
- Future queries can skip the probe step if the segment is cached

## Architecture

```
User query: "IT consulting in London"
        │
        ▼
┌─────────────────────┐
│ GPT-4o-mini         │ ← Generates candidate filters from NL
│ "Translate to Apollo │
│  filter JSON"       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Apollo Probe Search  │ ← 1 page, 25 results, 1 credit
│ /mixed_companies/    │
│ search               │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Taxonomy Extractor   │ ← Count industries, keywords, sizes from results
│ Frequency analysis   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Refined Filters      │ ← Top industries + keywords from REAL Apollo data
│ Show to user         │
└────────┬────────────┘
         │
         ▼
   User confirms → Full gathering with refined filters
```

## Cost: 1 extra Apollo credit per query (probe search)

## Implementation

### New MCP tool: `suggest_apollo_filters`

```json
{
  "name": "suggest_apollo_filters",
  "description": "Translate natural language query into optimal Apollo filters. Runs a probe search (1 credit) to extract Apollo's actual taxonomy.",
  "arguments": {
    "query": "IT consulting businesses in London",
    "target_count": 10
  }
}
```

Returns:
```json
{
  "suggested_filters": {
    "organization_locations": ["London, United Kingdom"],
    "q_organization_keyword_tags": ["it services", "it consulting", "digital transformation"],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,200"]
  },
  "probe_results": {
    "companies_found": 25,
    "top_industries": {"information technology & services": 22, "management consulting": 3},
    "top_keywords": {"it services & it consulting": 12, "software development": 8},
    "size_distribution": {"1-10": 8, "11-50": 12, "51-200": 5}
  },
  "message": "Probe search found 25 companies. Suggested filters based on Apollo's actual taxonomy."
}
```

### Flow integration

Current: User says "find IT consulting in London" → system asks for filters → user provides → gather
New: User says "find IT consulting in London" → system runs `suggest_apollo_filters` (1 credit) → shows refined filters → user confirms → gather

### Background taxonomy cron (future optimization)

- Stores probe results in `apollo_taxonomy_cache` table
- Key: normalized segment description hash
- Value: industries, keywords, sizes from probe
- TTL: 30 days
- If cache hit: skip probe, use cached taxonomy (0 credits)

## Test methodology

### Test set: "IT consulting businesses in London"

Expected filters (from KEYWORDS_EXAMPLE.png):
- Industries: information technology & services, management consulting
- Keywords: it services & it consulting, information technology & services, software development, business automation, digital transformation, consulting / consultancy

### Evaluation metric

```
Error = |expected_keywords - suggested_keywords| / |expected_keywords|
```

Target: error < 30% (miss at most 2 of 7 expected keywords)

### Testing steps

1. Run `suggest_apollo_filters("IT consulting businesses in London")`
2. Compare output keywords vs expected keywords
3. Calculate error rate
4. If error > 30%: adjust probe analysis (e.g., lower frequency threshold, expand synonyms)

## Files

```
mcp/apollo_filters/
├── PLAN.md                    ← This file
├── filter_intelligence.py     ← suggest_apollo_filters implementation
└── taxonomy_cache.py          ← Background cron (future)

mcp/backend/app/services/
└── filter_intelligence.py     ← Service: LLM + probe + extract

mcp/backend/app/mcp/
├── tools.py                   ← New tool definition
└── dispatcher.py              ← Tool handler
```
