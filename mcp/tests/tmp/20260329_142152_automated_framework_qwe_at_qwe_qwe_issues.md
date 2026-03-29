# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_142152

## GPT Tool Selection Issues (2)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**00_qwe_test_framework_validation Step 1** (context_check) — 4.52s
- Prompt: Show my projects
- Tools called: ['list_projects']
- missing_tool:get_context: called:['list_projects']

**00_qwe_test_framework_validation Step 4** (list_sources) — 3.17s
- Prompt: How can I gather companies?
- Tools called: ['get_context']
- missing_tool:tam_list_sources: called:['get_context']
- must_contain_any: ['Apollo', 'CSV', 'Google']

