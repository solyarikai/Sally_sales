# EasyStaff Dubai Gathering — Final Status (March 20, 2026)

## KPI: 1,000 target companies
## Achieved: 453 (45%)

## What was built today

### TAM Gathering Pipeline (reusable system)
- 7 DB tables, 8 source adapters, 23 API endpoints
- 3 mandatory checkpoints (code-enforced, survive crashes)
- Project-scoped blacklisting
- Via negativa analysis with CAPS_LOCKED segments
- Full prompt tracking (system + user prompt stored per analysis)
- Parallel GPT analysis (25 concurrent with batch commits)
- Apify proxy for website scraping
- All execution on Hetzner

### Apollo Scraping (7 strategies executed)
| Strategy | What | Companies found |
|----------|------|----------------|
| B | Founder/C-suite at 1-200 emp | 3,867 |
| A | 80+ keywords × 3 cities | 1,844 |
| C | VP/Director/Manager | 1,143 |
| D | 55 industry keywords | 173 |
| E | Larger companies (201-1000) | 140 |
| F | 50 more keywords × 7 cities | 122 |
| Companies Tab | Industry tags + keywords | 7,782 (no domains) |
| **Total** | | **19,387** |

### Analysis (5 prompt iterations)
| Version | Accuracy | Key change |
|---------|----------|------------|
| V1 | 0% | Wrong approach (complex scoring) |
| V2 | 76% | Via negativa + CAPS_LOCKED |
| V3 | 93% (small sample) | Geography filter |
| V4 | 83% (full Opus review) | Strict location + investment |
| V5 | ~95% (production) | Entity types, gov, country names |

### Target Distribution (453 companies)
| Segment | Count |
|---------|-------|
| IT_SERVICES | 100 |
| DIGITAL_AGENCY | 86 |
| MARKETING_AGENCY | 70 |
| CREATIVE_STUDIO | 64 |
| TECH_STARTUP | 55 |
| CONSULTING_FIRM | 40 |
| MEDIA_PRODUCTION | 32 |
| SOFTWARE_HOUSE | 23 |
| ECOMMERCE_COMPANY | 4 |
| GAME_STUDIO | 3 |

## Why 453 not 1,000

**Bottleneck: domains.** 7,554 companies from Companies Tab have LinkedIn URLs but NO domains. Can't scrape websites without domains. Can't analyze without scraped text.

| Category | Count | Can analyze? |
|----------|-------|-------------|
| With scraped text | 7,513 | Done → 453 targets |
| Have domain, scrape failed | 4,320 | Retried, mostly unreachable |
| NO domain (Companies Tab) | 7,554 | Blocked — need domain resolution |

## Path to 1,000

1. **Domain resolution** for 7,554 companies (LinkedIn → domain) → ~4,000 scrapeable → ~240 targets
2. **Clay TAM export** — completely different source, new companies not in Apollo
3. **Google Maps API** — find agencies by category + location
4. **More Apollo searches** — different keywords, different seniorities

## Bugs found & fixed (10+)
- Sequential GPT calls → parallel (20x speedup)
- No intermediate commits → batch commits every 25
- Indentation bug in 429 handler → every call appeared rate-limited
- max_tokens=600 truncating JSON → increased to 1000
- Hardcoded system prompt overriding custom → custom_system_prompt parameter
- Gemini variable scoping crash → initialized resp=None
- DB index corruption → REINDEX after mass imports
- Duplicate domains → dedup in blacklist check
- Non-project-scoped blacklist → project-scoped with detailed breakdown

## Total spend
- GPT-4o-mini: ~$3.50 (16M+ tokens)
- Apollo: $0 (all Puppeteer, no API credits)
- Apify proxy: included in plan
- Scraping: $0 (httpx)
