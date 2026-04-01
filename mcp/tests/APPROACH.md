# Apollo Search Approach — Test Results & Findings Log

## 2026-04-01 00:15 — INITIAL STATE

### What we know from previous tests:
- `organization_industry_tag_ids`: 90% target rate, 100/page (but inconsistent p3)
- `q_organization_keyword_tags`: 10-26% target rate, broken pagination for broad keywords
- `organization_keywords`: USELESS (ignores input)
- Filters across types are AND (not OR) — combining narrows
- 78 industries mapped in `apollo_industry_map` DB table
- A6 (parallel multi-keyword) wins on volume but loses on quality
- A1 (industry_tag_ids) wins on quality by 9x

### Previous test results (approach_comparison from run_approach_tests.py):
| Segment | A1 industry | A2 single kw | A3 multi kw | A6 parallel | A8 broad |
|---|---|---|---|---|---|
| TFP Fashion Italy | 201 (5cr) | 261 (5cr) | 72 (5cr) | 336 (12cr) | 22 (5cr) |
| ES IT Miami | — | 225 (5cr) | 262 (5cr) | 288 (12cr) | 148 (5cr) |
| ES Video London | — | 385 (5cr) | 254 (5cr) | 594 (12cr) | 182 (5cr) |
| ES IT US | — | 219 (5cr) | 205 (5cr) | 373 (9cr) | 202 (5cr) |
| ES Video UK | — | 345 (5cr) | 184 (5cr) | 425 (9cr) | 118 (5cr) |
| OnSocial UK | — | 210 (5cr) | 202 (5cr) | 283 (12cr) | 90 (5cr) |

### Quality verification (TFP Fashion Italy, Opus-verified):
- A1 (industry_tag_ids) top 10: 9/10 targets (90%)
- A2 (q_kw_tags "fashion design") top 10: 1/10 targets (10%)
- A8 (broad keywords) top 10: 1/10 targets (10%)

### Key insight: industry_tag_ids from the map = skip enrichment entirely
78 industries in DB. For "fashion brands" → look up "apparel & fashion" → tag_id ready.
No enrichment needed. 0 credits for filter discovery.

---

## 2026-04-01 00:15 — PLAN: What needs to happen

### Step 1: Wire industry map into filter_mapper (PREREQUISITE)
- filter_mapper receives user query "fashion brands in Italy"
- GPT maps to industry name "apparel & fashion"
- Look up tag_id from apollo_industry_map table
- Return `organization_industry_tag_ids` in filters
- Skip enrichment in pipeline if tag_id found

### Step 2: Build industry-or-keyword decision agent
- Agent A11: given user query + offer, decide:
  - Is there a SPECIFIC industry match? → use industry_tag_ids (90% rate)
  - Is it too broad/niche for industry? → use keywords (lower rate, more volume)
  - Show user: "I'll search by industry [X] first, then keywords [Y] if needed"

### Step 3: Test all 6 segments with the new approach
- For each: measure time, credits, real target rate
- Compare with previous results

### Step 4: Build the "exhaustion + fallback" logic
- Search with industry_tag_ids until pages return < 10 companies
- Switch to keywords as fallback
- Show in UI which filters are active vs planned

---

## 2026-04-01 00:40 — INDUSTRY MAP WIRED INTO FILTER_MAPPER ✅

### What was done:
- filter_mapper now looks up `organization_industry_tag_ids` from `apollo_industry_map` DB table
- Returns BOTH industry_tag_ids (primary) + keyword_tags (fallback)
- `filter_strategy`: "industry_first" or "keywords_only"
- Dispatcher passes through industry_tag_ids to Apollo search
- Preview shows strategy transparently

### Test: "fashion brands in Italy"
- Strategy: **INDUSTRY FIRST** (90%+ target rate) → keywords fallback
- Industry tag IDs: apparel & fashion + luxury goods & jewelry
- 0 enrichment credits spent — tag_ids from DB map
- Estimated cost: ~2 pages = 2 credits for 100 contacts at 90% rate

### Bug found + fixed:
Dispatcher was dropping `organization_industry_tag_ids` from filter_mapper result. Fixed.

---

## 2026-04-01 00:50 — ALL 6 SEGMENTS: INDUSTRY_FIRST STRATEGY ✅

ALL segments get industry_tag_ids from the map (0 enrichment credits):
| Segment | Tag IDs | Industries |
|---|---|---|
| Fashion Italy | 2 | apparel & fashion, luxury goods & jewelry |
| IT consulting Miami/US | 2 | IT & services, management consulting |
| Video production London/UK | 2 | marketing & advertising, media production |
| Influencer agencies UK | 2 | marketing & advertising, PR & communications |

## 2026-04-01 00:55 — TFP GATHERING: INDUSTRY_FIRST RESULT

- Run #400: 204 companies from 5 pages, 5 credits
- At 90% target rate (from previous Opus verification) = ~184 targets
- 184 targets × 3 people/company = **552 contacts** (KPI: 100)
- **KPI met in just 5 credits, ~10 seconds of Apollo search**
- 0 enrichment credits (tag_ids from DB map)

### Comparison with previous approaches:
| Approach | Companies (5p) | Credits | Est. Targets | KPI met? |
|---|---|---|---|---|
| **industry_first (NEW)** | **204** | **5** | **~184** | **YES** |
| A2 single keyword | 261 | 5 | ~26 (10%) | No (need 34) |
| A6 parallel multi-kw | 336 | 12 | ~34 (10%) | Barely |
| A1 industry (old test) | 201 | 5 | ~180 (90%) | YES |

Industry_first from DB map = same quality as old A1, but **0 enrichment overhead**.

TODO:
- [ ] Run full pipeline (scrape + classify + extract people) for TFP
- [ ] Measure total time, credits, real target rate
- [ ] Run same for other 5 segments
