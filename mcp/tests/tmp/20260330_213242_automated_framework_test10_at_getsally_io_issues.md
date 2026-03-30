# Issues Found — test10@getsally.io

**Source:** automated_framework | **Time:** 20260330_213242

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 8.52s
- Prompt: Start gathering IT consulting Miami
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**01_default_smartlead_flow Step 19** (5.2_push_campaign) — 50.54s
- Prompt: Push to SmartLead
- Tools called: ['smartlead_push_campaign']
- tool_error:smartlead_push_campaign: email_account_ids required. Call list_email_accounts first and ask the user whic

**01_default_smartlead_flow Step 21** (6.1_warm_replies) — 62.39s
- Prompt: Any warm replies?
- Tools called: ['replies_summary']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

## GPT Tool Selection Issues (6)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 4.51s
- Prompt: Looks good, start
- Tools called: ['get_context']
- must_contain_any: ['run_id', 'gathering', 'companies']

**01_default_smartlead_flow Step 9** (3.3_email_accounts) — 35.81s
- Prompt: Use Eleonora accounts from the petr campaigns for both
- Tools called: ['import_smartlead_campaigns']
- missing_tool:list_email_accounts: called:['import_smartlead_campaigns'] (acceptable: ['list_email_accounts'])

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 6.0s
- Prompt: Looks good
- Tools called: ['provide_feedback']
- missing_tool:tam_approve_checkpoint: called:['provide_feedback'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- must_contain_any: ['approved', 'approved', 'pre-filter']

**01_default_smartlead_flow Step 11b** (4.2b_run_remaining_phases) — 4.71s
- Prompt: Continue the pipeline
- Tools called: ['get_context']
- must_contain_any: ['target', 'classified', 'analyzed']

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 5.12s
- Prompt: Show the pipeline results
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 20.57s
- Prompt: How did the re-analysis go?
- Tools called: ['get_context']
- must_contain_any: ['iteration', 'target', 'improved']

## Other Issues (4)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 3.71s
- Prompt: I need to start campaigns
- Tools called: ['get_context']
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 6.48s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']

**01_default_smartlead_flow Step 13** (4.4_exploration) — 21.91s
- Prompt: Run exploration
- Tools called: ['tam_explore']
- must_contain_any: ['enrich', 'keyword', 'filter']

**01_default_smartlead_flow Step 20** (5.3_activate) — 19.73s
- Prompt: Checked inbox, looks good. Activate the campaign.
- Tools called: ['activate_campaign']
- must_contain_any: ['activated', 'launched', 'monitoring']

