# Issues Found — test9@getsally.io

**Source:** automated_framework | **Time:** 20260330_212244

## MCP Server Issues (1)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_targets) — 20.0s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['provide_feedback']
- tool_error:provide_feedback: Project not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 20.57s
- Prompt: Yes, proceed
- Tools called: ['tam_approve_checkpoint']
- missing_tool:tam_gather: called:['tam_approve_checkpoint'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['run_id', 'gathering', 'companies']

**01_default_smartlead_flow Step 9** (3.3_email_accounts) — 21.11s
- Prompt: Use Eleonora accounts from the petr campaigns for both
- Tools called: ['edit_campaign_accounts']
- missing_tool:list_email_accounts: called:['edit_campaign_accounts'] (acceptable: ['list_email_accounts'])

**01_default_smartlead_flow Step 11b** (4.2b_run_remaining_phases) — 6.75s
- Prompt: Continue the pipeline
- Tools called: ['get_context']
- must_contain_any: ['target', 'classified', 'analyzed']

**01_default_smartlead_flow Step 13** (4.4_exploration) — 4.08s
- Prompt: Run exploration
- Tools called: ['get_context']
- missing_tool:tam_explore: called:['get_context'] (acceptable: ['tam_explore'])
- must_contain_any: ['enrich', 'keyword', 'filter']

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 18.94s
- Prompt: Show the pipeline results
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 3.81s
- Prompt: How did the re-analysis go?
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'improved']

**01_default_smartlead_flow Step 17** (7.6_scale) — 19.35s
- Prompt: Scale up
- Tools called: ['get_context']
- must_contain_any: ['more', 'companies', 'page']

**01_default_smartlead_flow Step 22** (6.3_session_continuity) — 19.7s
- Prompt: What was I working on?
- Tools called: ['login']
- missing_tool:get_context: called:['login'] (acceptable: ['get_context', 'list_projects', 'check_integrations', 'pipeline_status', 'list_smartlead_campaigns'])
- must_contain_any: ['EasyStaff', 'project', 'campaign']

## Other Issues (2)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 3.93s
- Prompt: Help me find leads
- Tools called: ['list_projects']
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 16.33s
- Prompt: Pipeline status?
- Tools called: []
- missing_tool:pipeline_status: called:[] (acceptable: ['pipeline_status', 'get_context'])
- must_contain_any: ['target', 'classified', 'segment']

