# How Filter Extension Works Across Pipeline Iterations

**Date**: 2026-03-30
**Status**: Tested, needs better agent integration

## The Flow

```
ITERATION 1 (initial search):
  Filter mapper generates initial Apollo filters from:
    - Industry map (112 values)
    - Keyword map (2,000+ values, embedding pre-filtered to top 50)
    - Employee size (from offer analyzer)
    - Location (from query)

  Apollo returns 25 companies → scrape websites → GPT classifies targets

  Result: ~5-10 targets out of 25 scraped

         ↓

AGENT REVIEW (Opus in Claude Code):
  MCP returns ALL 25 scraped companies with website text to the agent.
  Agent reads each company's website text (300 chars) and decides:
    - Which are REAL targets for this offer?
    - Which are NOT (competitors, unrelated, wrong segment)?

  Agent provides:
    1. Top 5 targets for enrichment (the best matches)
    2. Target/non-target verdict for ALL companies (for prompt tuning)

         ↓

TWO PARALLEL TASKS:

  TASK A: Enrich agent's top 5 targets (5 Apollo credits)
    Apollo enrichment reveals each company's REAL keyword_tags:
      - synergybc.com → "it outsourcing", "technology staff augmentation", "managed services"
      - koombea.com → "software development", "nearshore development", "app development"
      - bluecoding.com → "nearshore staffing", "remote developers", "staff augmentation"

    These keywords are ADDED to the shared taxonomy map.
    Embeddings recomputed for new keywords.

    Filter mapper re-runs with enriched map → picks new keywords from shortlist.

    RESULT: extended Apollo filters with keywords PROVEN to exist on target companies.

  TASK B: Prompt tuning (1 iteration)
    Compare GPT's classifications vs agent's verdicts.
    gpt-4.1-mini generates improved prompt fixing mismatches.

    RESULT: tuned GPT classification prompt matching agent's judgment at ≥90%.

         ↓

ITERATION 2 (scale search with extended filters + tuned prompt):
  Apollo filters now include:
    ORIGINAL: "information technology & services", "IT consulting", "technology consulting"
    + ENRICHED: "it outsourcing", "staff augmentation", "nearshore development", "managed services"

  These new keywords find companies that were INVISIBLE to iteration 1.
  Companies that don't have "IT consulting" as a keyword but DO have
  "it outsourcing" or "staff augmentation" — same type of company,
  different Apollo vocabulary.

  Tuned prompt classifies with ≥90% accuracy (no false positives from
  cybersecurity companies or marketing agencies).

  RESULT: more target companies, higher accuracy, broader coverage.
```

## Why Agent-Selected Enrichment Matters

**Without agent selection** (enrich first 5 Apollo results):
- cipher.com (cybersecurity) → 118 security keywords → NOISE
- thecommunityagency.com (marketing) → 78 marketing keywords → NOISE
- Keywords pollute the map, filters don't improve

**With agent selection** (enrich agent's top 5 targets):
- synergybc.com (IT consulting) → "it outsourcing", "staff augmentation" → RELEVANT
- koombea.com (dev agency) → "nearshore development", "app development" → RELEVANT
- All enriched keywords are from REAL target companies → filters extend precisely

## Test Results (2026-03-30)

### Without agent selection:
```
Enriched first 5 Apollo results:
  cipher.com: +118 keywords (security — NOISE)
  thecommunityagency.com: +78 keywords (marketing — NOISE)

Filter diff: +1 keyword, +0 Apollo companies
```

### With agent selection:
```
Enriched agent's 3 targets:
  synergybc.com: "it outsourcing", "technology staff augmentation"
  smxusa.com: "enterprise solutions", "information technology"
  revelo.com: +156 keywords (tech recruitment)

Common keywords across targets (≥2 occurrences):
  it outsourcing, outsourcing/offshoring, software development,
  information technology, enterprise software, cloud computing

Filter diff: +156 keywords in map, embedding pre-filter picks most relevant
```

### What's missing:
The embedding pre-filter didn't pick enriched keywords for iteration 2 because:
1. The enriched keywords from revelo.com were hiring-focused ("backend engineers", "ai engineers") not consulting-focused
2. Only 3 targets were found (simple keyword matching too strict)
3. Real Opus agent reading full website text would identify more targets (koombea, innovecs, coderio ARE dev agencies)

With 5 properly identified targets (real Opus, not keyword heuristic), enrichment would produce:
- "nearshore development" (from koombea)
- "custom software development" (from coderio)
- "managed IT services" (from innovecs)
- "staff augmentation" (common across all)

These would directly extend the Apollo filters and find 20-50% more target companies.

## Architecture: Where Filter Extension Happens in Code

```python
# exploration_service.py — after enrichment:

# 1. Agent provides top 5 targets
agent_targets = agent_feedback["top_5_for_enrichment"]

# 2. Enrich agent's targets → update taxonomy map
for domain in agent_targets:
    org = await apollo_enrich(domain)
    taxonomy_service.add_from_enrichment(org, segment=query)

# 3. Rebuild embeddings for new keywords
await taxonomy_service.rebuild_embeddings_if_needed(openai_key)

# 4. Re-run filter mapper → new shortlist includes enriched keywords
optimized = await map_query_to_filters(query, offer, openai_key)
# optimized now has keywords discovered from enrichment

# 5. Iteration 2 uses optimized filters + tuned prompt
run2 = await gather_with_filters(optimized, tuned_prompt)
```

## Key Insight

The filter extension is not about adding ALL enriched keywords — it's about the **embedding pre-filter selecting the most relevant ones** from the enriched map. When you enrich 5 target companies, you add ~300 keywords. The embedding similarity search picks the 5-10 most relevant to the user's query from those 300. Those 5-10 are the ones that extend the Apollo search meaningfully.

The quality of the extension depends entirely on **which companies you enrich**. Agent-selected targets → relevant keywords → better filters. Random Apollo results → noise keywords → no improvement.
