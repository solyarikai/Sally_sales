# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260330_215649

## Other Issues (2)

**03_add_more_targets Step 1** (add_targets) — 91.9s
- Prompt: Gather 10 more target companies for the IT consulting segment
- Tools called: []
- missing_tool:tam_gather: called:[] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- missing_words: found 0/2: ['companies', 'gathered']

**03_add_more_targets Step 2** (process_new) — 0.25s
- Prompt: Blacklist check and analyze the additions
- Tools called: []
- missing_tool:tam_blacklist_check: called:[] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:[] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing_tool:tam_pre_filter: called:[] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:[] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:[] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])

