# Reply Classification: Model Comparison

**Date**: March 2026
**Task**: Classify email/LinkedIn replies into 8 categories (interested, not_interested, question, meeting_request, wrong_person, out_of_office, unsubscribe, other).
**Current model**: GPT-4o-mini
**Volume**: ~50-100 classifications/day
**Tokens per call**: ~500 input (system prompt + message), ~50 output (JSON with category/confidence/reasoning)
**Languages**: Russian, English, Spanish, Arabic, others

---

## Pricing Table

| Model | Input $/1M | Output $/1M | Cost per call | Monthly (100/day) | vs Current |
|---|---|---|---|---|---|
| **GPT-4o-mini** (current) | $0.15 | $0.60 | $0.000105 | **$0.32** | baseline |
| **GPT-4.1-nano** | $0.10 | $0.40 | $0.000070 | **$0.21** | -33% |
| **GPT-4.1-mini** | $0.40 | $1.60 | $0.000280 | **$0.84** | +163% |
| **GPT-4o** | $2.50 | $10.00 | $0.001750 | **$5.25** | +1540% |
| **GPT-5.4-nano** (new, Mar 17) | $0.20 | $1.25 | $0.000163 | **$0.49** | +53% |
| **GPT-5.4-mini** (new, Mar 17) | $0.75 | $4.50 | $0.000600 | **$1.80** | +463% |

**Cost per call** = (500 tokens x input rate) + (50 tokens x output rate).
**Monthly** = cost per call x 100 calls/day x 30 days.

At 100 calls/day, the entire classification pipeline costs $0.21-$5.25/month depending on model. Cost is irrelevant at this scale -- even GPT-4o would be fine. The real question is quality.

---

## Quality Assessment

### GPT-4o-mini (current) -- MMLU 82.0

Works well in production. Known issues:
- Occasionally classifies short positive replies ("ok", "da") as "other" instead of "interested"
- Good at Russian, decent at Spanish/Arabic
- Our custom prompt with detailed category descriptions compensates for edge cases
- Reliable JSON output with `response_format: json_object`

### GPT-4.1-nano -- MMLU 80.1

Cheapest option. Designed specifically for classification and extraction tasks.
- Slightly below GPT-4o-mini on MMLU (80.1 vs 82.0) -- a 2-point gap
- 1M token context window (overkill for this task, but no drawback)
- Sub-second latency
- Multilingual performance is weaker than GPT-4o-mini (GPT-4.1 family has better multilingual than 4o family at the full model tier, but nano variant cuts corners here)
- Risk: may struggle with ambiguous short Russian replies ("ну давайте", "ок, скиньте") where GPT-4o-mini already sometimes fails

**Verdict**: Probably works for 90% of cases. The 10% where it may fail are the same edge cases GPT-4o-mini sometimes gets wrong. Not worth the switch -- savings are $0.11/month.

### GPT-4.1-mini -- MMLU 87.0

Significant upgrade over GPT-4o-mini in reasoning quality.
- Better instruction following than GPT-4o-mini
- Better at nuanced classification (distinguishing "polite decline" from "needs more info")
- Reliable multilingual performance
- 2.7x more expensive, but still under $1/month

**Verdict**: Best quality-per-dollar for classification. Would reduce the edge-case misclassifications.

### GPT-4o -- MMLU 88.7

The expensive baseline.
- Marginally better than GPT-4.1-mini on benchmarks
- For a simple 8-category classification task, the improvement over 4.1-mini is negligible
- $5.25/month is still cheap in absolute terms, but there is zero reason to use this

**Verdict**: Overkill. No practical advantage over GPT-4.1-mini for this task.

### GPT-5.4-nano (released March 17, 2026)

Brand new, just released yesterday.
- Benchmarks not fully published yet, but positioned as a major leap over GPT-4.1-nano
- $0.20/$1.25 pricing -- more expensive than GPT-4.1-nano, cheaper than GPT-4.1-mini
- Designed for high-volume subagent workloads
- Too early to assess reliability for production classification

**Verdict**: Worth testing in a few weeks once benchmarks and real-world reports stabilize. Could be the sweet spot if it matches GPT-4.1-mini quality at lower cost.

### GPT-5.4-mini (released March 17, 2026)

Also brand new.
- $0.75/$4.50 -- significantly more expensive than current setup
- Likely excellent quality, but overkill for 8-category classification
- Makes more sense for complex reasoning tasks, not simple bucketing

**Verdict**: Skip for classification. Use for draft generation if needed.

---

## Recommendation

**Stay on GPT-4o-mini.** Here is why:

1. **Cost is irrelevant at this volume.** The difference between the cheapest (GPT-4.1-nano at $0.21/mo) and most expensive (GPT-4o at $5.25/mo) option is $5/month. Not worth the migration risk.

2. **GPT-4o-mini works.** Classification accuracy is good enough in production. The edge cases it gets wrong (short ambiguous replies) would likely also trip up GPT-4.1-nano.

3. **No code change needed.** The model is hardcoded in `reply_processor.py:636` as `model="gpt-4o-mini"`. Switching requires a code change + deploy + monitoring period.

4. **If we want to improve quality**, the move is GPT-4.1-mini (not nano). It costs $0.84/month vs $0.32/month -- a $0.52/month increase -- but has meaningfully better instruction following. This would help with the "interested vs other" edge cases.

### If we do switch (optional quality improvement)

Change line 636 in `backend/app/services/reply_processor.py`:
```python
# From:
model="gpt-4o-mini",  # Fast and cheap for classification
# To:
model="gpt-4.1-mini",  # Better classification quality, still <$1/mo
```

Also update `OPENAI_PRICING` in `backend/app/services/usage_logger.py` to add the 4.1-mini rate.

### Future action

Revisit GPT-5.4-nano in April 2026 once benchmarks and production reports are available. If it matches GPT-4.1-mini quality at $0.49/month, it becomes the best option.

---

## Sources

- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [GPT-4.1 Announcement](https://openai.com/index/gpt-4-1/)
- [GPT-4.1-nano Model Card](https://platform.openai.com/docs/models/gpt-4.1-nano)
- [GPT-5.4 Mini and Nano Announcement](https://openai.com/index/introducing-gpt-5-4-mini-and-nano/)
- [GPT-4o-mini vs GPT-4.1-nano Comparison](https://docsbot.ai/models/compare/gpt-4o-mini/gpt-4-1-nano)
- [OpenAI API Pricing -- All Models (2026)](https://pricepertoken.com/pricing-page/provider/openai)
