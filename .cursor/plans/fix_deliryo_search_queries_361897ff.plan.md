---
name: Fix Deliryo Search Queries
overview: Stop the junk template pipeline. Skip template cartesian product. Launch searches using the 1,128 curated doc keywords. Get real results per segment. Iterate.
todos:
  - id: stop-pipeline
    content: "Stop running pipeline, cancel job #111"
    status: completed
  - id: skip-templates
    content: "One-line fix in run_segment_search: skip build_segment_queries(), use only build_doc_keyword_queries()"
    status: completed
  - id: deploy-launch
    content: Deploy, launch 7 per-segment searches (Yandex, search+analyze)
    status: in_progress
isProject: false
---

# Launch Doc Keywords Search Now

## Steps

1. **Stop current pipeline**, cancel job #111 (template garbage)
2. **One-line fix**: skip `build_segment_queries()` in `run_segment_search()` -- use only `build_doc_keyword_queries()` (1,128 curated phrases)
3. **Deploy and launch 7 per-segment searches** (Yandex, search+analyze, no extraction/push)
4. **Watch results** by segment in UI (progress bars + column filters already built)

## Files to Change

- **[backend/app/services/company_search_service.py](backend/app/services/company_search_service.py)** -- skip template queries, doc keywords only

