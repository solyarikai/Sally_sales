# Issues Found — test1@getsally.io

**Source:** automated_framework | **Time:** 20260330_192700

## MCP Server Issues (2)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 4** (1.5_segments_before_offer) — 4.68s
- Prompt: Find IT consulting companies in Miami and video production agencies in London
- Tools called: ['parse_gathering_intent']
- tool_error:parse_gathering_intent: Project not found

**01_default_smartlead_flow Step 21** (6.1_warm_replies) — 24.28s
- Prompt: Show warm replies and follow-ups
- Tools called: ['replies_summary', 'replies_followups']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

## GPT Tool Selection Issues (10)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 20.09s
- Prompt: Launch pipelines
- Tools called: ['login']
- missing_tool:tam_gather: called:['login'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['filter', 'keyword', 'available']

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 20.19s
- Prompt: Yes, proceed
- Tools called: ['tam_approve_checkpoint']
- missing_tool:tam_gather: called:['tam_approve_checkpoint'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**01_default_smartlead_flow Step 10** (4.1_blacklist_check) — 5.33s
- Prompt: How is gathering going?
- Tools called: ['get_context']
- must_contain_any: ['blacklist', 'checkpoint', 'approve']

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 19.71s
- Prompt: Approved
- Tools called: ['pipeline_status']
- missing_tool:tam_approve_checkpoint: called:['pipeline_status'] (acceptable: ['tam_approve_checkpoint', 'get_context'])

**01_default_smartlead_flow Step 13** (4.4_exploration) — 20.0s
- Prompt: Run exploration
- Tools called: ['get_context']
- missing_tool:tam_explore: called:['get_context'] (acceptable: ['tam_explore'])
- must_contain_any: ['enrich', 'keyword', 'filter']

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 4.52s
- Prompt: Show the pipeline results
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 19.8s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['get_context']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 20.23s
- Prompt: How did the re-analysis go?
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'improved']

**01_default_smartlead_flow Step 17** (7.6_scale) — 19.42s
- Prompt: Scale up
- Tools called: ['get_context']
- must_contain_any: ['more', 'companies', 'page']

**01_default_smartlead_flow Step 20** (5.3_activate) — 20.37s
- Prompt: Approved, activate
- Tools called: ['login']
- missing_tool:activate_campaign: called:['login'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- must_contain_any: ['activated', 'launched', 'monitoring']

## Other Issues (3)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 11.42s
- Prompt: Hi there
- Tools called: ['get_context']
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 4.28s
- Prompt: Here is my token: mcp_df8748d67f4d3734682a01c0ab9df1932df0308d4279ffeb5446a94863308110
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 20.49s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']

