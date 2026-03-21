# Apollo API Strategy — Credit-Efficient Company Discovery

## Key Facts
- **1 credit = 1 API call = up to 100 companies** (per_page=100)
- **10,182 credits remaining** this billing cycle (resets Mar 22)
- **Budget: max 100 credits per city** = 10,000 companies per city
- **6 cities researched** with 168 credits (28 keywords × 6 cities)

## Filter Research Results (March 21, 2026)

### Companies available per keyword per city

| Keyword | Miami | Riyadh | London | Singapore | Sydney | Austin |
|---------|-------|--------|--------|-----------|--------|--------|
| e-commerce | 4,888 | 2,479 | 24,844 | 7,945 | 8,829 | 4,179 |
| software development | 2,736 | 2,066 | 17,986 | 5,229 | 4,685 | 4,394 |
| IT services | 1,715 | 2,135 | 12,403 | 4,565 | 4,806 | 2,317 |
| data analytics | 1,561 | 1,281 | 11,517 | 3,744 | 3,247 | 1,992 |
| SaaS | 1,558 | 842 | 9,721 | 2,845 | 2,917 | 2,249 |
| web design | 1,368 | 604 | 6,821 | 1,255 | 2,249 | 1,334 |
| video production | 868 | 442 | 6,135 | 1,150 | 1,593 | 896 |
| cybersecurity | 735 | 850 | 4,314 | 1,551 | 1,540 | 976 |
| app development | 682 | 771 | 4,273 | 1,416 | 1,271 | 984 |
| fintech | 511 | 333 | 4,717 | 1,666 | 657 | 388 |
| creative agency | 277 | 186 | 2,617 | 429 | 576 | 232 |
| marketing agency | 240 | 131 | 969 | 224 | 270 | 154 |
| digital agency | 106 | 33 | 631 | 132 | 180 | 60 |

### Target rate estimates (from Dubai experience)

| Keyword category | Expected target rate | Why |
|-----------------|---------------------|-----|
| digital agency, creative agency, marketing agency | 10-15% | Direct ICP match |
| web design, video production, design agency | 5-10% | Adjacent ICP |
| software development, app development, SaaS | 3-5% | Mixed — many product companies, not agencies |
| IT services, cybersecurity, DevOps | 2-4% | Many are hardware/support, not freelancer hirers |
| e-commerce, data analytics, fintech | 1-2% | Very broad — most are product companies |

### Smart credit allocation per city (100 credits budget)

**Strategy: prioritize high-target-rate keywords first, then fill with volume**

| Priority | Keywords | Credits | Expected companies | Expected targets |
|----------|----------|---------|-------------------|-----------------|
| 1 (HIGH) | digital agency, creative agency, marketing agency, design agency, branding agency, PR agency, media agency | 7 | 700 | 70-100 |
| 2 (MEDIUM) | web design, video production, animation studio, production house, SEO agency | 5 | 500 | 25-50 |
| 3 (MEDIUM) | software development, app development, mobile development, software house | 4-10 | 400-1000 | 15-40 |
| 4 (LOW) | IT services, SaaS, tech startup, consulting firm, game studio | 5-10 | 500-1000 | 10-30 |
| 5 (FILL) | cybersecurity, cloud consulting, DevOps, fintech, edtech, healthtech | 5-10 | 500-1000 | 5-20 |
| **TOTAL** | | **~40-50** | **2,600-4,200** | **125-240** |

**Note:** Remaining 50-60 credits per city saved for page 2+ of high-performing keywords.

## Execution Plan

### Phase 1: Get page 1 for ALL keywords (28 credits per city)
- Already done for 6 cities during research (168 credits)
- Already got ~4,000 companies from the research calls
- Need to: import these into pipeline DB, scrape websites, analyze

### Phase 2: Get pages 2-5 for TOP keywords (30-40 credits per city)
- Only for keywords with >200 total_entries
- Skip keywords with <50 results (already got all on page 1)

### Phase 3: Deep dive top 3 keywords (20-30 credits per city)
- "creative agency", "marketing agency", "digital agency"
- Get ALL pages (these are the highest target rate)

## Critical Rules
1. **ALWAYS per_page=100** — same cost, 10× more data
2. **NEVER use Puppeteer for Apollo** — Cloudflare blocks, account gets locked
3. **Research before bulk** — 1 credit to check total_entries, then decide how many pages
4. **Import results into pipeline DB immediately** — don't lose data
5. **Max 100 credits per city** — budget discipline
