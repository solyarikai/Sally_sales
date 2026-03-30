# Prompt Tuning Findings — Best Model Setup
**Date**: 2026-03-30
**Test**: 12 model combinations for prompt adjustment loop

## The Problem
User agent (Opus) reviews 25 scraped companies and tells MCP which are targets.
MCP must adjust the GPT classification prompt until it matches the agent's verdicts.
Goal: converge in minimum iterations (ideally 1-2) so the pipeline is fast.

## Test Setup
- Segment: OnSocial Creator platforms UK (hardest case — 40% of companies are borderline)
- 10 companies with cached website text
- Agent verdicts: 4 targets, 6 non-targets
- Two GPT roles tested independently:
  - **Classifier**: classifies companies with current prompt
  - **Improver**: generates better prompt based on mismatches

## Results (12 combinations)

| Classifier | Improver | Accuracy | Iterations | Time | Status |
|------------|----------|----------|------------|------|--------|
| **gpt-4.1-mini** | **gpt-4.1-mini** | **100%** | **2** | **29s** | ⭐ BEST |
| gpt-4o-mini | gpt-4.1-mini | 100% | 2 | 39s | ✅ |
| gpt-4o-mini | gpt-4o | 100% | 3 | 50s | ✅ |
| gpt-4o-mini | gpt-4o-mini | 100% | 4 | 67s | ✅ |
| gpt-4.1-mini | gpt-4o-mini | 90% | 5 | 78s | ⚠️ didn't converge |
| gpt-4.1-nano | gpt-4o | 80% | 5 | 52s | ❌ |
| gpt-4.1-mini | gpt-4o | 70% | 5 | 70s | ❌ |
| gpt-4.1-nano | gpt-4o-mini | 70% | 5 | 54s | ❌ |
| gpt-4.1-nano | gpt-4.1-mini | 70% | 5 | 62s | ❌ |
| * | gpt-4.1-nano | 0% | 2 | ~20s | ❌ generates garbage |

## Key Findings

### 1. gpt-4.1-mini is the best for BOTH roles
- As classifier: understands nuanced segment boundaries
- As improver: generates precise, non-hardcoded prompt improvements
- 2 iterations = iteration 0 (initial) + iteration 1 (improved) = fast pipeline

### 2. gpt-4.1-mini as improver is the key differentiator
- With gpt-4.1-mini improving: 2-2 iterations to 100%
- With gpt-4o-mini improving: 4-5 iterations to 90-100%
- With gpt-4o improving: 3-5 iterations, sometimes WORSE (70%)
- gpt-4.1-mini writes more precise exclusion rules from mismatch patterns

### 3. gpt-4.1-nano is eliminated
- As classifier: too weak, misclassifies even with a perfect prompt (70-80% ceiling)
- As improver: generates broken prompts that cause 0% accuracy
- Not usable for any role in prompt tuning

### 4. gpt-4o as improver is surprisingly bad
- Over-complicates the prompt, adds too many rules
- Sometimes the "improved" prompt is WORSE than the original
- gpt-4.1-mini is simpler and more effective

### 5. The initial prompt matters less than the improver model
- Same initial prompt with different improvers: 0% to 100% spread
- The improver's ability to extract the RIGHT lesson from mismatches is everything

## Implementation
- `prompt_tuner.py` now uses `gpt-4.1-mini` for both classifier and improver
- Default `max_iterations=5` but typically converges in 2
- No hardcoded domains or industry names in any generated prompt (verified by test)

## Cost
- 2 iterations × (~2000 tokens classify + ~1500 tokens improve) = ~7000 tokens
- At gpt-4.1-mini pricing ($0.40/1M input, $1.60/1M output): ~$0.005 per tuning cycle
- Negligible vs Apollo credits ($0.01+ per enrichment)
