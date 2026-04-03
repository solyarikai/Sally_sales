# Exploration Classification Test Results

## Date: 2026-03-30

## Summary
Tested 35 model × prompt setups across 3 segments. Found winning combination.

## Winner
- **Model**: gpt-4o (with gpt-4o-mini fallback)
- **Prompt**: v9_negativa_refined (via negativa approach)
- **Accuracy**: 96% overall (100%/100%/90%)

## Test History

### Round 1: 20 setups (4 models × 5 prompts)
Models: gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1-nano
Prompts: v1-v5

Results:
- gpt-4.1-nano: ELIMINATED (0-37% — fundamentally misunderstands buyer vs seller)
- Best round 1: gpt-4o-mini × v3_via_negativa (87% avg, but measures target rate not accuracy)

### Round 2: 15 setups (3 models × 5 prompts) — with ground truth
Models: gpt-4o-mini, gpt-4.1-mini, gpt-4o
Prompts: v6-v10

Results:
| Setup | EasyStaff | Fashion | OnSocial | Avg |
|-------|-----------|---------|----------|-----|
| gpt-4o-mini × v9_negativa_refined | 100% | 100% | 90% | **97%** |
| gpt-4o-mini × v10_minimal_precise | 100% | 100% | 90% | **97%** |
| gpt-4o × v9_negativa_refined | 100% | 100% | 90% | **97%** |
| gpt-4o × v10_minimal_precise | 100% | 100% | 90% | **97%** |

### Final Round: 6 setups (2 models × 3 prompts) — v11/v12 variants
Attempting to fix the inthestyle.com miss.

Result: v11/v12 introduce regressions on EasyStaff (synergybc.com misclassified).
v9 remains best overall.

### E2E Test (actual service code)
| Segment | Accuracy | Details |
|---------|----------|---------|
| EasyStaff IT consulting Miami | 100% (8/8) | All IT firms correctly classified as buyers |
| TFP Fashion brands Italy | 100% (10/10) | soeur.fr correctly rejected (French, not Italian) |
| OnSocial Creator platforms UK | 90% (9/10) | inthestyle.com missed (data limitation) |
| **Overall** | **96% (27/28)** | |

## Known Limitation
inthestyle.com (fast fashion brand) is missed because its scraped website text contains
only product catalog (clothing names, prices). No mention of influencer marketing.
In reality, In The Style is known for influencer collaborations, but this info isn't
on their homepage. This is a data limitation, not a prompt limitation.

## Models Tested
1. gpt-4o-mini ($0.15/1M input) — good, slight inconsistency on edge cases
2. gpt-4o ($2.50/1M input) — most consistent, chosen as primary
3. gpt-4.1-mini ($0.40/1M input) — similar to gpt-4o-mini
4. gpt-4.1-nano ($0.10/1M input) — terrible, doesn't understand buyer vs seller

## Prompt Versions Tested (10 total)
1. v1_simple_buyer_seller — basic
2. v2_chain_of_thought — two-step reasoning
3. v3_via_negativa_strict — exclude-only approach
4. v4_role_play_sales — sales strategist persona
5. v5_explicit_examples — with worked examples per offer type
6. v6_two_step_structured — step 1: what does company do, step 2: would they buy
7. v7_ecosystem_buyer — ecosystem membership test
8. v8_pain_point — pain point matching
9. v9_negativa_refined (**WINNER**) — refined via negativa with explicit exclusion rules
10. v10_minimal_precise — minimal prompt, precise rules

## Key Insights
- Via negativa (exclude bad, keep everything else) > positive classification
- gpt-4o is more consistent than gpt-4o-mini for classification
- Explicit exclusion rules (recruitment ≠ buyer, PPC/SEO ≠ buyer) reduce false positives
- The buyer/seller distinction is the #1 challenge: "adjacent to market" ≠ "competitor"
