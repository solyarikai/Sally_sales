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
