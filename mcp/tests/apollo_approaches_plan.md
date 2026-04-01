# Apollo Search Approaches — God-Level Testing Plan

## Goal
Find the BEST approach to reach 100 target people (3 max/company ≈ 34 target companies) FASTEST across different segments.

## KPIs per approach
1. **Speed**: time to reach 100 target people
2. **Real target count**: verified by Opus (not GPT-4o-mini)
3. **Credits spent**
4. **Target rate**: real targets / total companies from Apollo

## Approaches to test (10+)

### A1: industry_tag_ids ONLY
- Enrich 3 example companies → get industry_tag_id
- Search with organization_industry_tag_ids only
- Pro: 55% target rate proven. Con: needs enrichment first (5 credits)

### A2: q_organization_keyword_tags — single specific keyword
- Use ONE specific keyword from enrichment (e.g. "leather goods", "fashion design")
- Pro: good pagination for specific keywords. Con: limited pool

### A3: q_organization_keyword_tags — multiple specific keywords
- Use 3-5 specific keywords from enrichment
- Keywords are OR within the array
- Pro: broader pool. Con: lower target rate?

### A4: industry_tag_ids + q_kw_tags combined (AND)
- Use both — narrows results but higher precision
- Pro: highest precision. Con: fewer results

### A5: Sequential keyword exhaustion
- Start with most specific keyword, exhaust it
- Move to next keyword, exhaust it
- Dedup across keywords
- Pro: maximizes unique companies. Con: more credits

### A6: Parallel multi-keyword
- Run 5 keywords in PARALLEL (5 separate searches)
- Dedup results
- Pro: fastest wall-clock time. Con: 5x credits per page

### A7: industry_tag_ids first, then keywords
- Start with industry (high quality)
- When industry pages exhausted or target rate drops, switch to keywords
- Pro: best quality first, then broader. Con: complexity

### A8: No enrichment — direct keywords from filter_mapper
- Skip enrichment, use GPT-generated keywords directly
- Pro: 0 enrichment credits, faster start. Con: possibly lower quality keywords

### A9: Broad keyword + aggressive GPT classification
- Use broad keyword ("fashion"), get tons of companies
- Rely on GPT classification to find targets in the noise
- Pro: maximum companies. Con: low target rate, more GPT costs

### A10: Hybrid — enrich 3 examples, extract BOTH industry_tag_id AND keywords, use best
- Enrich → get industry + keywords
- Test both on page 1 (2 credits)
- Use whichever gives better results for scale
- Pro: data-driven decision. Con: 2 extra credits for testing

## Test segments

| # | Company | Segment | Geo | Size |
|---|---------|---------|-----|------|
| 1 | TFP (thefashionpeople.com) | Fashion brands | Italy | 1-200 |
| 2 | EasyStaff (easystaff.io) | IT consulting | Miami | 1-200 |
| 3 | EasyStaff | Video production | London | 1-200 |
| 4 | EasyStaff | IT consulting | US (broad) | 1-200 |
| 5 | EasyStaff | Video production | UK (broad) | 1-200 |
| 6 | OnSocial (onsocial.ai) | Social media influencer agencies | UK | 1-200 |

## For each (segment × approach):
1. Fetch 10 pages
2. Count unique companies
3. Opus-verify 50 random companies → real target rate
4. Estimate: pages needed for 34 targets → credits → time
5. Log everything to file

## Output files
- `tests/tmp/approach_{A1-A10}_{segment}_{timestamp}.json`
- Final comparison: `tests/tmp/approach_comparison_final.json`
