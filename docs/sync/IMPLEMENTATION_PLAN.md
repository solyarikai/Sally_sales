# Sync & Pipeline — Implementation Plan

---

## PHASE 1: Fix Pipeline Shit (before any new gathering)

### 1.1 SmartLead sync: detect changed campaigns via analytics endpoint
**Problem:** SmartLead API `lead_count` on campaign list is broken (returns 0). Diff check compares our own stale numbers.
**Solution:** Call `GET /campaigns/{id}/analytics` → `campaign_lead_stats.total` for each campaign. Compare with `synced_leads_count`. Only CSV-export campaigns with diff.
**Cost:** 152 calls × 0.5s = ~76s for check. Then export only 5-20 changed ones.

### 1.2 Backfill real filters into gathering_runs
**Problem:** 4/7 runs store "80+ keywords" instead of actual keyword arrays. Filter hash is wrong. Can't re-run searches.
**Solution:** Extract actual keyword lists from JS scripts, update `filters` JSONB and `filter_hash` for runs #4, #5, #54, #55.

### 1.3 Dedup analysis results
**Problem:** 6,173 duplicate analysis results (63% waste). Same company analyzed 2-7 times.
**Solution:** For each `discovered_company_id`, keep only the latest `analysis_result`. Delete older ones. Add dedup check before analyzing.

### 1.4 Clean up analysis runs
**Problem:** 25 analysis runs for gathering run #1. No "current" marker.
**Solution:** Mark latest analysis_run per gathering_run as `is_current`. Archive old ones.

### 1.5 Handle placeholder domains
**Problem:** 7,782 entries with `_apollo_XXXXX` domains. Inflate counts, can't analyze.
**Solution:** Set `status=PENDING_RESOLVE`. Don't count in pipeline metrics. Separate domain resolution task.

### 1.6 Set raw_output_ref
**Problem:** NULL for all 7 runs.
**Solution:** Backfill file paths: `easystaff-global/data/uae_god_search_companies.json` etc.

### 1.7 Cross-run dedup at analysis time
**Problem:** Same company in runs #1 and #4 gets analyzed twice.
**Solution:** Before analyzing, check if `discovered_company_id` already has analysis_result from another run with same prompt. Skip if yes.

---

## PHASE 2: City Expansion — 5,000 targets per city

### KPI: 5,000 target companies per city
### ICP: Service businesses up to 100 employees with remote contractors, NOT competitors

### Cities (from CITY_EXPANSION_STRATEGY.md)

**Tier 1 (run first, in parallel):**
| City | Apollo location filter | Scrape estimate |
|------|----------------------|-----------------|
| New York | `New York, New York, United States` | 2,000-3,000 |
| Los Angeles | `Los Angeles, California, United States` | 1,500-2,000 |
| Dubai (continue) | `Dubai, United Arab Emirates` | Already running |

**Tier 2 (run after Tier 1):**
| City | Apollo location filter | Scrape estimate |
|------|----------------------|-----------------|
| Riyadh | `Riyadh, Saudi Arabia` | 500-800 |
| London | `London, England, United Kingdom` | 2,000-2,500 |
| Singapore | `Singapore` | 800-1,200 |
| Miami | `Miami, Florida, United States` | 600-1,000 |

**Tier 3 (run after Tier 2):**
| City | Apollo location filter | Scrape estimate |
|------|----------------------|-----------------|
| Sydney | `Sydney, New South Wales, Australia` | 800-1,000 |
| Melbourne | `Melbourne, Victoria, Australia` | 500-700 |
| Berlin | `Berlin, Germany` | 500-700 |
| Austin | `Austin, Texas, United States` | 400-600 |
| Doha | `Doha, Qatar` | 150-300 |
| Jeddah | `Jeddah, Saudi Arabia` | 200-400 |
| Abu Dhabi | `Abu Dhabi, United Arab Emirates` | 300-500 |
| Amsterdam | `Amsterdam, Netherlands` | 400-600 |

### Per-city pipeline execution (ALL run via pipeline, ALL saved to DB)

For EACH city:

1. **GATHER** — Apollo People emulator with:
   - Location: city-specific
   - Seniorities: founder, c_suite, owner, vp, director, manager
   - Size ranges: 1-10, 11-20, 21-50, 51-100
   - Keywords: full list (NOT summary text — actual array stored in `filters`)
   - Multiple strategies: seniority search + keyword search + industry tags
   - Max pages: 10-50 depending on city density

2. **DEDUP** — normalize domains, check against existing discovered_companies

3. **BLACKLIST** — check against project 9 CRM (55K+ domains), enterprise blacklist
   - CP1: operator confirms project scope

4. **PRE-FILTER** — offline industries, junk domains, solo consultants

5. **SCRAPE** — httpx + Apify proxy, root page + /about

6. **ANALYZE** — V6 via negativa prompt (adapted per city: geography check = city, not just UAE)
   - CP2: operator reviews targets
   - Store full prompt + response + segment

7. **CONTACTS** — Extract from Apollo source data (up to 3 decision-makers per company)

### Parallel execution architecture

Each city = independent `GatheringRun` with its own `project_id=9`. Multiple cities can run Apollo scrapers sequentially (same Apollo account) but analysis + scraping run in parallel.

```
Apollo scraper:    NYC → LA → Miami → Riyadh → London → ... (sequential, same account)
Website scraping:  [NYC batch] [LA batch] [Miami batch]        (parallel, httpx+Apify)
GPT analysis:      [NYC batch] [LA batch] [Miami batch]        (parallel, 25 concurrent)
```

### Keywords (FULL LIST — stored in DB as array, NOT summary)

```json
{
  "keywords": [
    "marketing agency", "digital agency", "creative agency", "advertising agency",
    "design agency", "branding agency", "PR agency", "social media agency",
    "SEO agency", "content agency", "web design", "web development",
    "software development", "IT services", "app development", "e-commerce",
    "video production", "film production", "animation studio", "production house",
    "game studio", "SaaS", "tech startup", "fintech", "edtech", "healthtech",
    "UX agency", "UI design", "product design", "mobile development",
    "cloud consulting", "DevOps", "cybersecurity", "data analytics",
    "AI consulting", "machine learning", "blockchain", "IoT",
    "digital marketing", "performance marketing", "growth agency",
    "influencer agency", "podcast production", "content creation",
    "recruitment agency", "HR consultancy", "staffing solutions",
    "management consulting", "strategy consulting", "business consulting",
    "translation services", "localization", "QA company", "testing company",
    "media agency", "communications agency", "event production",
    "photography studio", "motion graphics", "post production",
    "innovation lab", "digital transformation", "technology company"
  ]
}
```

### V6 prompt adaptation per city

Each city needs a modified geography check in the prompt:
- NYC/LA/Miami/Austin: "Company must be based in [city], [state], United States"
- London: "Company must be based in London, UK or Greater London area"
- Riyadh/Jeddah: "Company must be based in [city], Saudi Arabia"
- Singapore: "Company must be based in Singapore"
- Sydney/Melbourne: "Company must be based in [city], Australia"
- Berlin/Amsterdam: "Company must be based in [city], [country]"
- Doha: "Company must be based in Doha, Qatar"

### Success metrics per city

| Metric | Target |
|--------|--------|
| Raw companies gathered | 10,000+ (Tier 1), 3,000+ (Tier 2), 1,000+ (Tier 3) |
| Scraped with text | 60%+ of companies with domains |
| Analysis accuracy | 90%+ (Opus review) |
| Target companies | **5,000 per city** |
| Contacts found | 3 per target company |
| All filters stored in DB | Yes — actual arrays, not summaries |
| All prompts stored in DB | Yes — with effectiveness tracking |
| All results in DB | Yes — analysis_results with full GPT output |

### Iteration loop per city

```
1. Gather (Apollo scraper)
2. Pipeline: dedup → blacklist → CP1 → pre-filter → scrape → analyze → CP2
3. Opus review: check 100% of targets
4. If accuracy < 90%: adjust prompt, re-analyze
5. If targets < 5,000: expand keywords/seniorities/size ranges, gather more
6. Loop until 5,000 verified targets
```
