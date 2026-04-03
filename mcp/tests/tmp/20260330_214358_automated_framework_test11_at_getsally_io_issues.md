# Issues Found — test11@getsally.io

**Source:** automated_framework | **Time:** 20260330_214358

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 4** (1.5_segments_before_offer) — 50.46s
- Prompt: Two segments: IT consulting Miami, video production London
- Tools called: ['parse_gathering_intent']
- tool_error:parse_gathering_intent: Project not found

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 7.13s
- Prompt: Start gathering IT consulting Miami
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**01_default_smartlead_flow Step 21** (6.1_warm_replies) — 51.85s
- Prompt: Any warm replies?
- Tools called: ['replies_summary']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

## GPT Tool Selection Issues (6)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 21.23s
- Prompt: Go ahead
- Tools called: ['login']
- missing_tool:tam_gather: called:['login'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['run_id', 'gathering', 'companies']

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 21.72s
- Prompt: Approved
- Tools called: ['provide_feedback']
- missing_tool:tam_approve_checkpoint: called:['provide_feedback'] (acceptable: ['tam_approve_checkpoint', 'get_context'])

**01_default_smartlead_flow Step 11b** (4.2b_run_remaining_phases) — 20.95s
- Prompt: Continue the pipeline
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'analyzed']

**01_default_smartlead_flow Step 13** (4.4_exploration) — 52.01s
- Prompt: Yes, explore to find better filters
- Tools called: ['get_context']
- missing_tool:tam_explore: called:['get_context'] (acceptable: ['tam_explore'])

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 20.08s
- Prompt: Show the pipeline results
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 50.57s
- Prompt: How did the re-analysis go?
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'improved']

## Other Issues (4)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 3.99s
- Prompt: I need to start campaigns
- Tools called: ['list_projects']
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 10** (4.1_run_blacklist) — 91.87s
- Prompt: Run the blacklist check
- Tools called: []
- missing_tool:tam_blacklist_check: called:[] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- must_contain_any: ['blacklist', 'gate', 'checked']

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 49.9s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']

**01_default_smartlead_flow Step 20** (5.3_activate) — 20.44s
- Prompt: Approved, activate
- Tools called: ['activate_campaign']
- must_contain_any: ['activated', 'launched', 'monitoring']

