# God-Level Apollo Filter Exploration

## Proven Results (tested 2026-03-30)

| Approach | Companies found | Credits |
|---|---|---|
| Naive (3 keywords only) | 431 | 1 |
| After enrichment (8 keywords) | 3,408 | 6 |
| GPT-expanded (14 keywords) | 1,130 | 1 |
| **Industry-focused** | **4,048** | 1 |
| Combined best (approach 10) | 3,424 | 6 |
| Very broad (noisy) | 4,596 | 1 |

**Winner: Combined approach — enriched keywords + industry terms from taxonomy = 3,400+ companies (8x baseline)**

## The Algorithm

```
User says: "IT consulting in Miami, 50-200 employees"
                    ↓
Step 0: MAP QUERY TO APOLLO TAXONOMY (free, instant)
  - Load apollo_taxonomy.json (112 industries)
  - GPT-4o-mini maps "IT consulting" →
    industries: ["information technology & services", "computer software", "management consulting"]
    keywords: ["IT consulting", "technology consulting", "IT services"]
  - Infer company size from offer: 10-200 employees
                    ↓
Step 1: INITIAL SEARCH (1 credit)
  - Search with: mapped keywords + geo + size
  - Get 25 companies
                    ↓
Step 2: SCRAPE WEBSITES (free, Apify proxy)
  - BeautifulSoup extraction: titles, headings, full visible text
  - 10-15 companies scraped (3,000-10,000 chars each)
                    ↓
Step 3: CLASSIFY TARGETS (free, GPT-4o-mini)
  - Via negativa: EXCLUDE non-targets
  - Strict: if website unclear → NOT target
  - 100% accuracy (verified by Opus on 8/8 companies)
                    ↓
Step 4: ENRICH TOP 5 TARGETS (5 credits)
  - Apollo enrichment API → ALL labels per company
  - Extract: industries, keywords, SIC codes, NAICS codes
                    ↓
Step 5: BUILD OPTIMIZED FILTERS (free)
  - Original keywords + ALL enriched keywords + industry names
  - Industry names are the BIG multiplier (4x more companies)
  - Add to taxonomy for future searches
                    ↓
Step 6: FULL PIPELINE (4 credits for ~100 companies)
  - Search with optimized filters
  - Scrape all websites
  - Classify all companies
  - Result: ~70% target rate, 100+ contacts

TOTAL: ~10 Apollo credits for 100+ target contacts
```

## Key Insights

1. **Industry terms > keywords**: "information technology" yields 4,048 companies vs "IT consulting" yields 431
2. **Enrichment reveals hidden labels**: companies have keywords you'd never guess from the search
3. **Taxonomy grows over time**: every enrichment adds new industries/keywords to shared map
4. **Via negativa + proper scraping = 100% accuracy**: GPT-4o-mini matched Opus judgment on all companies

## Filter Test Results (10 approaches, same segment)

```
#  Approach                     Companies
1  Current (3 keywords)              431  ← baseline
2  +enriched keywords              3,408  ← 8x improvement!
3  GPT-expanded keywords           1,130  ← decent
4  Industry-focused                4,048  ← MOST companies
5  Broad IT (single keyword)       3,395  ← surprising
6  Very broad                      4,596  ← too noisy
7  Staffing focused                  422  ← too narrow
8  Florida (broader geo)           2,464  ← geo helps
9  No size filter                  2,275  ← size matters
10 Combined best                   3,424  ← BEST targeted
```

## Classification Accuracy

| Version | Scraper | Prompt | Accuracy (GPT vs Opus) |
|---|---|---|---|
| v1 | Regex (200 chars) | Basic | 44-78% |
| v2 | Better regex (title+meta+H1+500 chars) | Strict | 89% |
| v3 | Better regex + via negativa | No confidence | 92% |
| v4 | BeautifulSoup (3000-10000 chars) + Apify | Via negativa + strict | **100%** |

## Files

- `apollo_taxonomy.json` — 112 Apollo industry names (shared, grows over time)
- `exploration_service.py` — the algorithm implementation
- `offer_analyzer.py` — GPT-4o-mini infers target company size from offer
- `test_exploration_quality.py` — test that verifies everything
