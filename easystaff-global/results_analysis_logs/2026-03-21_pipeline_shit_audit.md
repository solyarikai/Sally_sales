# Pipeline Shit Audit — March 21, 2026

## 1. Filters stored as text summaries, not actual values
**Severity: CRITICAL**

4 out of 7 gathering runs store "80+ company name keywords" instead of the actual 80 keywords.

| Run | What's stored | What should be stored |
|-----|--------------|----------------------|
| #4 | `"keywords": "80+ company name keywords"` | `"keywords": ["marketing agency", "digital agency", ...]` (all 80) |
| #5 | `"keywords": "55 industry-specific keywords"` | `"keywords": ["digital transformation agency", ...]` (all 55) |
| #54 | `"keywords": "50 industry-specific keywords"` | actual list |
| #55 | `"cities": "7 UAE cities"` | `"cities": ["Dubai, UAE", "Abu Dhabi, UAE", ...]` |

**Why it sucks:** Can't re-run the search. Can't compare filters between runs. Can't know what was actually searched. The filter_hash is based on the summary text, so duplicate detection is broken.

**Root cause:** Import scripts wrote manual filter dicts instead of capturing from the JS scraper config.

**Fix:** Backfill from the JS scripts. The actual keywords are in `apollo_god_search.js:50-94`, `apollo_god_search_expanded.js`, `apollo_god_search_wave2.js`.

## 2. 6,173 duplicate analysis results
**Severity: HIGH**

9,720 total analysis results for 3,547 unique companies = 6,173 duplicates (63% waste).

Same company analyzed 2-7 times across different prompt iterations (V1→V2→V3→V4→V5). Old results never cleaned up.

**Why it sucks:** Queries return wrong counts. "453 targets" includes duplicates. Wastes storage. Confusing when reviewing.

**Fix:** Keep only the latest analysis_result per discovered_company_id. Delete older duplicates. Add unique constraint or dedup query.

## 3. 25 analysis runs for gathering run #1
**Severity: HIGH**

Run #1 has 25 analysis_runs across 10 different prompts. Each prompt iteration created new analysis runs without cleaning up old ones.

**Why it sucks:** Which analysis is "current"? The `latest_analysis_run_id` on discovered_companies might point to an old one. No clear "active" analysis per run.

**Fix:** Add `is_current` flag to analysis_runs. Or just keep the latest per gathering_run and clean up.

## 4. 7,782 placeholder domains (_apollo_XXXXX)
**Severity: MEDIUM**

Companies Tab entries stored with `domain = "_apollo_6373559417c1820001a34d46"` because the Companies Tab DOM doesn't expose real domains.

**Why it sucks:** Can't scrape, can't analyze, can't find contacts. They inflate the "19,387 discovered" count to look bigger than reality. Real scrapeable companies: 11,605.

**Fix:** Either resolve domains via LinkedIn URLs, or mark these as `status=PENDING_RESOLVE` instead of `NEW`. Don't count them in "discovered" totals.

## 5. raw_output_ref is NULL for all runs
**Severity: MEDIUM**

The `raw_output_ref` field should point to the source JSON file (e.g. `easystaff-global/data/uae_god_search_companies.json`). It's NULL for all 7 runs.

**Why it sucks:** Can't trace back to the original scraper output. If the JSON files are deleted, provenance is lost.

**Fix:** Set `raw_output_ref` to the actual file paths during import.

## 6. Batch analyze script bypasses pipeline checkpoints
**Severity: MEDIUM**

`batch_analyze_easystaff.py` directly calls `re_analyze()` and `run_analysis()`, skipping the API endpoints and checkpoint gates. The whole checkpoint system was designed but never enforced during the actual gathering.

**Why it sucks:** No audit trail of operator approvals. The pipeline promises "3 mandatory checkpoints" but the real work was done by a script that ignores them all.

**Fix:** For production use, always go through the API. Scripts are OK for development/iteration but should be replaced by API calls in production workflows.

## 7. Adapters exist but were never used
**Severity: LOW**

8 source adapters were built (apollo_org_api, apollo_people_ui, etc.) but all actual gathering was done by running JS scripts manually on Hetzner and importing results with ad-hoc Python scripts.

**Why it sucks:** The adapters are untested in production. When team members try to use them via the pipeline API, they might fail.

**Fix:** Test each adapter end-to-end. The `start_gathering()` method should call the adapter, not manual scripts.

## 8. No dedup across gathering runs at analysis time
**Severity: MEDIUM**

The same company can exist in multiple gathering runs (found by Strategy A AND Strategy B). When analyzing, each run analyzes it separately → duplicate analysis results.

**Fix:** Before analyzing, check if the company already has a recent analysis result from another run. Skip if it does.

## Summary

| Issue | Severity | Effort to fix |
|-------|----------|---------------|
| Summary filters instead of actual values | CRITICAL | 1 hour (backfill from JS scripts) |
| 6,173 duplicate analysis results | HIGH | 30 min (SQL cleanup + dedup logic) |
| 25 analysis runs for 1 gathering run | HIGH | 30 min (cleanup + is_current flag) |
| 7,782 placeholder domains | MEDIUM | Needs domain resolution (separate task) |
| NULL raw_output_ref | MEDIUM | 15 min (backfill paths) |
| Scripts bypass checkpoints | MEDIUM | Process change, not code |
| Adapters untested | LOW | Test during next gathering |
| No cross-run dedup at analysis time | MEDIUM | 30 min (add check) |
