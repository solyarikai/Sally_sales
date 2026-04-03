# Issues Found — test8@getsally.io

**Source:** automated_framework | **Time:** 20260330_210712

## MCP Server Issues (4)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 4.99s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_targets) — 27.58s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['tam_re_analyze']
- missing_tool:provide_feedback: called:['tam_re_analyze'] (acceptable: ['provide_feedback', 'get_context'])
- tool_error:tam_re_analyze: Run not found

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 2.37s
- Prompt: How did the re-analysis go?
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'improved']
- tool_error:get_context: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)

**01_default_smartlead_flow Step 21** (6.1_warm_replies) — 27.15s
- Prompt: Show warm replies and follow-ups
- Tools called: ['replies_summary', 'replies_list', 'replies_followups']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

## GPT Tool Selection Issues (7)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 20.22s
- Prompt: Yes, proceed
- Tools called: ['tam_approve_checkpoint']
- missing_tool:tam_gather: called:['tam_approve_checkpoint'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['run_id', 'gathering', 'companies']

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 21.15s
- Prompt: Looks good
- Tools called: ['get_context']
- must_contain_any: ['approved', 'approved', 'pre-filter']

**01_default_smartlead_flow Step 11b** (4.2b_run_remaining_phases) — 24.93s
- Prompt: Continue the pipeline
- Tools called: ['get_context']
- must_contain_any: ['target', 'classified', 'analyzed']

**01_default_smartlead_flow Step 13** (4.4_exploration) — 20.79s
- Prompt: Run exploration
- Tools called: ['get_context']
- missing_tool:tam_explore: called:['get_context'] (acceptable: ['tam_explore'])
- must_contain_any: ['enrich', 'keyword', 'filter']

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 19.78s
- Prompt: Show the pipeline results
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 17** (7.6_scale) — 19.72s
- Prompt: Scale up
- Tools called: ['get_context']
- must_contain_any: ['more', 'companies', 'page']

**01_default_smartlead_flow Step 20** (5.3_activate) — 20.21s
- Prompt: Approved, activate
- Tools called: ['get_context']
- must_contain_any: ['activated', 'launched', 'monitoring']

## Other Issues (1)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 3.9s
- Prompt: Hi there
- Tools called: ['get_context']
- must_contain_any: ['sign up', 'token', 'mcp_']

