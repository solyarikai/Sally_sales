# Cost Analysis: Processing 1,000,000 Companies Through the Pipeline

> **THIS IS RESEARCH ONLY. DO NOT USE AS A GUIDE TO EXECUTE.**
> Need to understand pricing before committing to any large-scale gathering.
> Created: 2026-03-21

---

## Pipeline Phases & Cost Per Phase

```
Phase 1: GATHER+DEDUP ─── find companies
Phase 2: BLACKLIST ─────── filter known/existing
Phase 3: PRE-FILTER ────── remove junk
Phase 4: SCRAPE ─────────── get website text
Phase 5: ANALYZE ────────── AI classification
Phase 6: VERIFY ─────────── FindyMail email verification
Phase 7: PUSH ───────────── push to campaigns
```

---

## Apollo MCP vs Puppeteer vs API — The Real Comparison

Apollo MCP servers ([multiple implementations on GitHub](https://github.com/Chainscore/apollo-io-mcp)) wrap the Apollo.io REST API into MCP tools. **MCP = API underneath. Same credits, same rate limits, same pricing.** The only difference is the interface — MCP lets Claude/Cursor call Apollo directly instead of running scripts.

### What Each Apollo Endpoint Costs (CONFIRMED from Apollo dashboard)

| Endpoint / MCP Tool | Credits | What it returns | Notes |
|---------------------|---------|-----------------|-------|
| `/mixed_people/api_search` | **0 (FREE)** | Partial profile: first name, obfuscated last name, title, company name | **NO domain, NO email, NO phone** |
| `/mixed_companies/search` | **1 credit per PAGE** (up to 100 results/page) | Full company data: domain, name, size, industry, revenue, address | **ALWAYS use per_page=100** |
| `/people/match` | **1 credit/email + 1/firmographic + 5/phone** | Full person profile | Only charged for NET-NEW data |
| `/people/bulk_match` | Same as above | Batched version | |
| `/organizations/enrich` | **1 credit per result** | Full company profile by domain | |
| `/organizations/bulk_enrich` | **1 credit per company** | Batched, max 10/page | |
| `/organizations/{id}/job_postings` | **1 credit per result** | Job listings | Max 10,000/page |

**Key insight: Company search = 1 credit per PAGE of up to 100 results. That's $0.00079 per company on Professional plan. Absurdly cheap.**

Sources: [Apollo API Pricing](https://docs.apollo.io/docs/api-pricing), [People API Search](https://docs.apollo.io/reference/people-api-search), [Chainscore MCP](https://github.com/Chainscore/apollo-io-mcp)

### Three Ways to Get Data from Apollo

| Method | Companies | People (names) | People (emails) | Speed | Cloudflare risk |
|--------|-----------|----------------|-----------------|-------|-----------------|
| **Puppeteer UI** | FREE | FREE | FREE (visible on page) | Slow (~2,500/hr) | HIGH (blocks after 2-3 cities) |
| **API / MCP** | 1 credit/page | FREE (search) | 1 credit/person (enrich) | Fast (50K/day) | None |
| **Hybrid** | Puppeteer first, API when blocked | Free search | FindyMail instead of Apollo | Best of both | Managed |

---

## Apollo Plans & Credit Math

| Plan | Price | Credits/mo | Org search pages | People enriched | $/credit |
|------|-------|-----------|------------------|-----------------|----------|
| Free | $0 | 100 | 100 pages = 2,500 cos | 100 emails | N/A |
| Basic | $49/user/mo | 5,000 | 5,000 pages = 125K cos | 5,000 emails | $0.0098 |
| Professional | $79/user/mo | 10,000 | 10,000 pages = 250K cos | 10,000 emails | $0.0079 |
| Organization | $119/user/mo | 15,000 | 15,000 pages = 375K cos | 15,000 emails | $0.0079 |
| Overage | +$0.20/credit | — | — | — | $0.20 |

**Credits DO NOT roll over.** Unused credits expire at end of billing cycle.

**Rate limits:** Free = 50 req/min, 600/day. Paid = 200 req/min, 2,000/day.

Sources: [Apollo Pricing](https://www.apollo.io/pricing), [Persana Analysis](https://persana.ai/blogs/apollo-io-pricing), [SmartePro Analysis](https://www.smarte.pro/blog/apollo-io-pricing)

---

## Phase 1: GATHER — Finding 1M Companies

### Via MCP/API: `search_organizations` (1 credit per PAGE of 100 results)

| Volume | Pages needed (at 100/page) | Credits | On Professional ($79/mo, 10K credits) | On Overage ($0.20/credit) |
|--------|---------------------------|---------|---------------------------------------|---------------------------|
| 10,000 cos | 100 | 100 | 1 month ($79) | $20 |
| 100,000 cos | 1,000 | 1,000 | 1 month ($79) | $200 |
| 500,000 cos | 5,000 | 5,000 | 1 month ($79) | $1,000 |
| 1,000,000 cos | 10,000 | 10,000 | **1 month ($79)** | $2,000 |

**1 MILLION companies for $79.** Always use `per_page=100` to maximize value.

### Via Puppeteer (current method): FREE

| Volume | Time | Cloudflare blocks? | Proxy cost |
|--------|------|-------------------|-----------|
| 10,000 cos | 4 hours | No | $0 |
| 50,000 cos | 20 hours | Yes, after 2-3 cities | $10-20 proxy |
| 100,000 cos | 40 hours | Severe | $50-100 proxy |
| 1,000,000 cos | 400 hours (17 days) | Unmanageable | Not feasible |

### Via MCP People Search (FREE but SEVERELY LIMITED)

`search_people` is **FREE** (0 credits) and filters DO work:
- `person_titles` ✅ (CEO, Founder, etc.)
- `person_locations` ✅ (city, state, country)
- `organization_num_employees_ranges` ✅ (e.g. "11,50")
- `organization_industry_tag_ids` ✅

**TESTED LIVE (2026-03-21):**
```
CEO/Founder + NYC + no filters     = 98,411 results
CEO/Founder + NYC + 11-50 employees = 19,389 results
CEO/Founder + NYC + 11-50 + industry = 3,711 results
```

**BUT the response data is a TEASER — almost everything is hidden:**

| Field | Returned? | Example |
|-------|-----------|---------|
| First name | ✅ YES | `Liz` |
| Last name | ❌ OBFUSCATED | `Ry***n` |
| Title | ✅ YES | `Founder and CEO` |
| Company name | ✅ YES | `Human Workplace` |
| **Company domain** | ❌ NO | — |
| **Email** | ❌ NO | just `has_email: True` |
| **Phone** | ❌ NO | just `has_direct_phone: Yes` |
| **Location details** | ❌ NO | just `has_city: True` |
| **Industry** | ❌ NO | just `has_industry: True` |
| **Employee count** | ❌ NO | just `has_employee_count: True` |
| Apollo person ID | ✅ YES | `66f2dc5c33a7be0001a2ebbe` |

**Without company domain, this endpoint is USELESS for our pipeline.** We need domains to scrape websites (Phase 4) and run AI analysis (Phase 5). Company name alone isn't enough — "Human Workplace" could be anything.

**To get domain/email/phone, you MUST use `enrich_person` (1 credit per person).**

**Verdict: `search_people` is free but returns teaser data. You can use it to COUNT how many targets exist in a city (useful for scoping), but NOT to actually gather company data for the pipeline.**

### What `search_people` IS useful for

1. **Scoping/sizing** — "How many CEO/Founders in NYC agencies with 11-50 employees?" → 19,389. Worth scraping.
2. **Getting Apollo person IDs** — can then selectively enrich only the most relevant ones (1 credit each).
3. **Company name discovery** — if you Google the company name, you might find the domain. But that's manual/hacky.

### The real MCP cost for company discovery

Since `search_people` doesn't return domains, you MUST either:

**Option A: `search_organizations`** (1 credit/page, 25 results)
- Returns full company data including domain
- 1M companies = 40,000 credits

**Option B: `search_people` (free) → `enrich_person` (1 credit each)**
- Free search to find people, then enrich to get company domain
- But 1 credit per person is WORSE than 1 credit per 25 companies
- 1M companies ≈ 1.25M people = 1.25M credits = **$250,000 in overage** 💀

**Option C: `search_people` (free) → Google company names → find domains**
- Hacky, slow, unreliable
- Not scalable to 1M

**Conclusion: `search_organizations` at 1 credit/page is the cheapest API path for company discovery.**

---

## Phase 2-3: BLACKLIST + PRE-FILTER

**Cost: $0** — Database lookups, rule-based filtering. Removes 30-50%.

---

## Phase 4: SCRAPE — Website Text

**Cost: $0-200** — httpx with rotating user agents. 70-80% success rate. ~36K/hour.

---

## Phase 5: ANALYZE — AI Classification (GPT-4o-mini)

**Observed cost from Dubai V4 run: $0.005/company** (includes full ICP prompt + website text)

| Volume | Cost |
|--------|------|
| 10,000 | **$50** |
| 100,000 | **$500** |
| 500,000 | **$2,500** |
| 1,000,000 | **$5,000** |

Target rate: ~10% → 1M companies = ~100K targets

Source: [OpenAI Pricing](https://openai.com/api/pricing/) — GPT-4o-mini: $0.15/1M input, $0.60/1M output

---

## Phase 6: PEOPLE + VERIFY — Getting Emails for Targets

This is where MCP vs Puppeteer matters most.

### Option A: Apollo MCP `search_people` + `enrich_person`

| Step | Tool | Credits | Cost (Professional plan) |
|------|------|---------|--------------------------|
| Find decision-makers | `search_people` | **0** | $0 |
| Reveal emails | `enrich_person` | 1/person | 1 credit = ~$0.008 |

For 10K targets × 3 people = 30,000 enrichments = 30,000 credits

| Plan | Months to get 30K credits | Total cost |
|------|--------------------------|-----------|
| Professional ($79/mo, 10K credits) | 3 months | **$237** |
| Organization ($119/mo, 15K credits) | 2 months | **$238** |
| Overage ($0.20/credit) | Instant | **$6,000** |

### Option B: Apollo MCP `search_people` (free) + FindyMail (verify)

| Step | Tool | Credits | Cost |
|------|------|---------|------|
| Find decision-makers with names | `search_people` | **0** | $0 |
| Find + verify emails | FindyMail | N/A | $0.01-0.05/email |

For 30,000 lookups, ~50-60% hit rate = 15K-18K billed:

| FindyMail Plan | Credits/mo | Months | Total cost |
|----------------|-----------|--------|-----------|
| Scale ($249/mo, 25K) | 25,000 | 1 month | **$249** |
| Business ($149/mo, 10K) | 10,000 | 2 months | **$298** |
| Growth ($99/mo, 5K) | 5,000 | 3-4 months | **$300-400** |

### Option C: Puppeteer People Tab (FREE but slow)

| Targets | Time | Cost |
|---------|------|------|
| 1,000 | 10 hours | $0 |
| 10,000 | 100 hours (4 days) | $0 |
| 50,000 | 500 hours (21 days) | $0 |

Source: [FindyMail Pricing](https://www.findymail.com/pricing/)

---

## TOTAL COST — ALL SCENARIOS

### Scenario 1: 1,000 targets (realistic first batch)

| Phase | MCP Path | Puppeteer Path |
|-------|----------|---------------|
| GATHER (15K cos) | $0 (search_people free) | $0 (Puppeteer) |
| FILTER | $0 | $0 |
| SCRAPE | $0 | $0 |
| ANALYZE (10K cos) | $50 | $50 |
| PEOPLE (1K targets) | $0 (search_people free) | $0 (Puppeteer, 10hrs) |
| EMAILS | $50-150 (FindyMail) | $50-150 (FindyMail) |
| **TOTAL** | **$50-200** | **$50-200** |
| **Time** | **1-2 days** | **3-4 days** |

### Scenario 2: 10,000 targets (ambitious, 10 cities)

| Phase | MCP Path | Puppeteer Path |
|-------|----------|---------------|
| GATHER (100K cos) | $0 (search_people) | $0-100 (Puppeteer + proxy) |
| FILTER | $0 | $0 |
| SCRAPE | $0-50 | $0-50 |
| ANALYZE (70K cos) | $350 | $350 |
| PEOPLE (10K targets) | $0 (search_people) | $0 (100 hours) |
| EMAILS (30K lookups) | $250-400 (FindyMail) | $250-400 (FindyMail) |
| **TOTAL** | **$600-800** | **$600-900** |
| **Time** | **1-2 weeks** | **3-4 weeks** |

### Scenario 3: 100,000 targets (1M companies)

| Phase | MCP Path | Puppeteer Path | MCP + Apollo Emails |
|-------|----------|---------------|---------------------|
| GATHER (1M cos) | $0 (search_people, 25 days) | Not feasible | $0 |
| FILTER | $0 | — | $0 |
| SCRAPE (700K) | $100-200 | — | $100-200 |
| ANALYZE (500K) | $2,500 | — | $2,500 |
| PEOPLE (100K targets) | $0 (search free) | — | $0 (search free) |
| EMAILS (300K lookups) | $1,000-1,500 (FindyMail) | — | $2,400 (Apollo enrich, 30 months!) |
| **TOTAL** | **$3,600-4,200** | **Not feasible** | **$5,000-5,100** |
| **Time** | **5-6 weeks** | — | **30+ months (credit gated)** |

---

## MCP vs Puppeteer — Decision Matrix

| Factor | MCP (API) | Puppeteer |
|--------|-----------|-----------|
| **Company discovery** | search_organizations: 1 credit/page ❌ | FREE ✅ |
| **People discovery** | search_people: FREE ✅ | FREE ✅ |
| **Email reveal** | enrich_person: 1 credit ❌ | FREE (if visible on page) ✅ |
| **Speed** | Fast (50K/day) ✅ | Slow (5-10K/day) ❌ |
| **Cloudflare blocks** | None ✅ | After 2-3 cities ❌ |
| **Scale to 1M** | Yes (25 days via search_people) ✅ | No (blocks at ~50K) ❌ |
| **Needs Apollo plan** | Free plan works for search_people | No plan needed |
| **Email quality** | Apollo emails (not always verified) | FindyMail (verified only) |

### Optimal Strategy: Puppeteer for discovery, MCP for scoping, FindyMail for emails

1. **Use MCP `search_people`** (FREE) to **scope** cities — count how many targets exist before committing to a full scrape
2. **Use Puppeteer** (FREE) for actual company+people discovery (returns full data including domains and visible emails)
3. **Fall back to `search_organizations`** (1 credit/page) only when Puppeteer gets Cloudflare-blocked
4. **Use FindyMail** for email verification — cheaper than Apollo `enrich_person`

---

## Corrected Bottom Line (After Dashboard Pricing Confirmed)

**Game changer: `/mixed_companies/search` = 1 credit per PAGE of 100 results.**

At `per_page=100`: 1M companies = 10,000 credits = **$79 on Professional plan**.

| Goal | Apollo API (companies) | GPT cost | FindyMail | TOTAL |
|------|----------------------|----------|-----------|-------|
| **1K targets** (15K cos) | $79 (150 credits, but plan minimum) | $50 | $50-150 | **$179-279** |
| **10K targets** (100K cos) | $79 (1,000 credits) | $350 | $250-400 | **$679-829** |
| **100K targets** (1M cos) | $79 (10,000 credits) | $2,500 | $1,000-1,500 | **$3,579-4,079** |

**API is now CHEAPER than Puppeteer** when you factor in proxy costs, Cloudflare blocks, and time. Puppeteer takes days/weeks; API takes hours.

**`search_people` (free) is valuable for SCOPING ONLY** — tells you "19,389 CEO/Founders at 11-50 person companies in NYC" so you know the city is worth scraping. But it doesn't return domains.

---

## Why Not Just Enrich via MCP?

The tempting path: `search_people` (free) → get Apollo IDs → `enrich_person` (1 credit) → get emails.

| Volume | Enrichment credits | On Professional ($79/mo) | On Overage |
|--------|-------------------|--------------------------|-----------|
| 3,000 people (1K targets) | 3,000 | 1 month ($79) | $600 |
| 30,000 people (10K targets) | 30,000 | 3 months ($237) | $6,000 |
| 300,000 people (100K targets) | 300,000 | 30 months ($2,370) | $60,000 |

**vs FindyMail for the same volumes:**
| Volume | FindyMail cost |
|--------|---------------|
| 3,000 lookups | $49-150 |
| 30,000 lookups | $250-400 |
| 300,000 lookups | $1,000-1,500 |

**FindyMail is 3-40× cheaper than Apollo enrichment for emails.** And FindyMail only charges on success (verified emails), while Apollo charges regardless.

---

## Sources

- [Apollo API Pricing](https://docs.apollo.io/docs/api-pricing) — credits per endpoint
- [Apollo People Search — 0 credits](https://docs.apollo.io/reference/people-api-search) — confirmed free
- [Apollo Organization Search — 1 credit/page](https://docs.apollo.io/reference/organization-search) — confirmed costs credits
- [Apollo Rate Limits](https://docs.apollo.io/reference/rate-limits) — 50-200 req/min by plan
- [Apollo Plans](https://www.apollo.io/pricing) — $49-119/user/mo (annual)
- [Chainscore Apollo MCP](https://github.com/Chainscore/apollo-io-mcp) — 27 tools, full API coverage
- [thevgergroup Apollo MCP](https://github.com/thevgergroup/apollo-io-mcp) — 9 tools implementation
- [FindyMail Pricing](https://www.findymail.com/pricing/) — $49-249/mo, $0.01-0.05/email
- [OpenAI GPT-4o-mini](https://openai.com/api/pricing/) — $0.15/1M input, $0.60/1M output
- [Apollo Credits Warning](APOLLO_CREDITS_WARNING.md) — incident with accidental credit burn
- [Persana Apollo Hidden Costs](https://persana.ai/blogs/apollo-io-pricing) — credit expiration, overage traps
- [SmartePro Apollo Pricing](https://www.smarte.pro/blog/apollo-io-pricing) — plan comparison
- [Salesmotion Apollo Breakdown](https://salesmotion.io/blog/apollo-pricing) — real costs analysis
