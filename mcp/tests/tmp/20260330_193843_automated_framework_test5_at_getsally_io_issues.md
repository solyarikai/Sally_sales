# Issues Found — test5@getsally.io

**Source:** automated_framework | **Time:** 20260330_193843

## MCP Server Issues (10)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 15.97s
- Prompt: Start gathering
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 16.15s
- Prompt: Go ahead
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**01_default_smartlead_flow Step 10** (4.1_blacklist_check) — 0.37s
- Prompt: How is gathering going?
- Tools called: ['pipeline_status']
- must_contain_any: ['blacklist', 'checkpoint', 'approve']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 0.35s
- Prompt: Approved
- Tools called: ['tam_approve_checkpoint']
- must_contain_any: ['approved', 'scraping', 'analyzing']
- tool_error:tam_approve_checkpoint: Gate not found

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 0.35s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 13** (4.4_exploration) — 0.37s
- Prompt: Yes, explore to find better filters
- Tools called: ['tam_explore']
- tool_error:tam_explore: Run not found

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 0.43s
- Prompt: Show the pipeline results
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'filter']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 0.46s
- Prompt: How did the re-analysis go?
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'improved']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 17** (7.6_scale) — 18.53s
- Prompt: Good, now find more companies with these filters
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**01_default_smartlead_flow Step 19** (5.2_approve_push) — 0.52s
- Prompt: Looks good, push to SmartLead
- Tools called: ['smartlead_push_campaign']
- tool_error:smartlead_push_campaign: Sequence must be approved first

## Other Issues (3)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.0s
- Prompt: Help me find leads
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.61s
- Prompt: Here is my token: mcp_de643cb61ca69142d54cbd555739795a9fc3c8876a71040c7273191683c911b8
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 0.61s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['provide_feedback']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

