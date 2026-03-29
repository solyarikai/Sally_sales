# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_173121

## GPT Tool Selection Issues (3)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**00_qwe_test_framework_validation Step 1** (context_check) — 3.09s
- Prompt: What projects do I have? Show me my current state.
- Tools called: ['login']
- missing_tool:get_context: called:['login']

**00_qwe_test_framework_validation Step 3** (check_integrations) — 2.95s
- Prompt: Show my API keys
- Tools called: ['get_context']
- missing_tool:check_integrations: called:['get_context']
- must_contain_any: ['integration', 'connected', 'SmartLead']

**00_qwe_test_framework_validation Step 6** (reply_summary) — 2.86s
- Prompt: Reply status for my project?
- Tools called: ['get_context']
- missing_tool:replies_summary: called:['get_context']

