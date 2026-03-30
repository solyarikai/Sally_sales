# Intent Parser Model Test Results

## Date: 2026-03-30

## Problem
User prompt → Apollo filters was the #1 bottleneck. GPT invented keywords that don't exist in Apollo's taxonomy. If initial filters are wrong, everything downstream fails.

## Fix
1. Loaded Apollo taxonomy (112 industries) into the prompt
2. Tested 40 model × prompt setups across 5 segments
3. Found winning combination and implemented it

## Winner
- **Model**: gpt-4.1-mini ($0.40/1M tokens) with gpt-4o-mini fallback
- **Prompt**: p7_coverage_maximizer (concentric circles: core → adjacent → peripheral industries)
- **Accuracy**: 94% avg across 5 test segments

## All 40 Setups Tested

### Round 1 (20 setups): 5 models × 4 prompts
| Setup | Avg |
|-------|-----|
| gpt-4o × p1_taxonomy_strict | 90% |
| gpt-4o × p2_map_then_expand | 90% |
| gpt-4.1-mini × p1_taxonomy_strict | 88% |
| gpt-4.1-mini × p2_map_then_expand | 86% |
| gpt-4.1-nano × p1_taxonomy_strict | 84% |
| gpt-4.1-nano × p2_map_then_expand | 84% |
| gpt-4o-mini × p1_taxonomy_strict | 84% |
| gpt-4o-mini × p2_map_then_expand | 84% |
| gpt-4o × p3_buyer_focused | 84% |
| gpt-4.1-nano × p3_buyer_focused | 81% |
| gpt-4.1-nano × p4_minimal | 81% |
| gpt-4o-mini × p3_buyer_focused | 80% |
| gpt-4.1-mini × p3_buyer_focused | 80% |
| gpt-4o × p4_minimal | 79% |
| gpt-4.1-mini × p4_minimal | 75% |
| gpt-4o-mini × p4_minimal | 67% |
| o3-mini × all | 0% (API error: needs max_completion_tokens) |

### Round 2 (20 setups): 5 models × 4 prompts
| Setup | Avg |
|-------|-----|
| **gpt-4o × p7_coverage_maximizer** | **94%** |
| **gpt-4.1-mini × p7_coverage_maximizer** | **94%** |
| gpt-4o × p6_linkedin_perspective | 92% |
| gpt-4o-mini × p8_structured_reasoning | 90% |
| gpt-4o × p8_structured_reasoning | 90% |
| gpt-4.1-mini × p8_structured_reasoning | 90% |
| gpt-4o × p5_taxonomy_force_3plus | 88% |
| gpt-4.1-mini × p5_taxonomy_force_3plus | 88% |
| gpt-4o-mini × p5_taxonomy_force_3plus | 88% |
| gpt-4.1-mini × p6_linkedin_perspective | 88% |
| gpt-4o-mini × p7_coverage_maximizer | 86% |
| gpt-4o-mini × p6_linkedin_perspective | 86% |
| gpt-4.1-nano × p5-p8 | 16-79% |
| o3-mini × p5-p8 | 0-18% (JSON parse failures) |

## Model Rankings
1. **gpt-4.1-mini** — 94% with p7, $0.40/1M. Best value.
2. **gpt-4o** — 94% with p7, $2.50/1M. Same quality, 6x more expensive.
3. **gpt-4o-mini** — 90% with p8, $0.15/1M. Good fallback.
4. **gpt-4.1-nano** — 79% max. Not reliable enough.
5. **o3-mini** — Not suitable for structured JSON output.

## Prompt Rankings
1. **p7_coverage_maximizer** (94%) — "concentric circles" approach (core → adjacent → peripheral)
2. **p8_structured_reasoning** (90%) — step-by-step reasoning
3. **p6_linkedin_perspective** (92% with gpt-4o only) — "what would they list on LinkedIn?"
4. **p1_taxonomy_strict** (90%) — simple but effective
5. **p4_minimal** (67-79%) — too terse, models lose context

## Key Insights
1. **Taxonomy injection is critical** — providing the 112 real Apollo industries eliminates hallucinated filter values
2. **"Concentric circles" prompt design** — asking for core + adjacent + peripheral industries gets 3-5 valid picks
3. **Keyword separation** — explicitly saying "keywords describe TARGET companies, not our product" prevents offer leakage
4. **gpt-4.1-mini > gpt-4o-mini for structured tasks** — 8% accuracy improvement for 2.6x cost increase (worth it for this step)

## Final Architecture
```
User: "I need creator platforms in UK"
         ↓
Intent Parser (gpt-4.1-mini, p7_coverage_maximizer)
         ↓
  industries: marketing & advertising, internet, media production, online media
  keywords: influencer marketing, creator economy, influencer platform
  geo: United Kingdom
         ↓
Exploration (gpt-4o-mini, v9_negativa)
  → Apollo search → scrape → classify → enrich → optimize filters
         ↓
Full Pipeline (gpt-4o-mini)
  → gather → blacklist → scrape → analyze → verify → push
```

## Files
- `tests/test_intent_models.py` — round 1 (20 setups)
- `tests/test_intent_round2.py` — round 2 (20 setups)
- `tests/test_intent_parser.py` — quick verification
- `tests/tmp/20260330_110858_intent_model_test.json` — round 1 raw results
- `tests/tmp/20260330_111307_intent_round2.json` — round 2 raw results
- `backend/app/services/intent_parser.py` — updated service
