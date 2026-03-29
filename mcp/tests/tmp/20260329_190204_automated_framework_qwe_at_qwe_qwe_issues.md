# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_190204

## GPT Tool Selection Issues (1)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**00_qwe_test_framework_validation Step 4** (list_sources) — 4.21s
- Prompt: How can I gather companies?
- Tools called: ['get_context']
- must_contain_any: ['Apollo', 'CSV', 'Google']

