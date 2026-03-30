# Issues Found — test1@getsally.io

**Source:** automated_framework | **Time:** 20260330_193218

## MCP Server Issues (9)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 0.74s
- Prompt: Start gathering
- Tools called: ['tam_gather']
- tool_error:tam_gather: offer_unknown

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 0.64s
- Prompt: Go ahead
- Tools called: ['tam_gather']
- tool_error:tam_gather: offer_unknown

**01_default_smartlead_flow Step 10** (4.1_blacklist_check) — 0.4s
- Prompt: How is gathering going?
- Tools called: ['pipeline_status']
- must_contain_any: ['blacklist', 'checkpoint', 'approve']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 0.38s
- Prompt: Approved
- Tools called: ['tam_approve_checkpoint']
- must_contain_any: ['approved', 'scraping', 'analyzing']
- tool_error:tam_approve_checkpoint: Gate not found

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 0.35s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 0.37s
- Prompt: Show the pipeline results
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'filter']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 0.5s
- Prompt: How did the re-analysis go?
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'improved']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 17** (7.6_scale) — 0.62s
- Prompt: Scale up
- Tools called: ['tam_gather']
- tool_error:tam_gather: offer_unknown

**01_default_smartlead_flow Step 19** (5.2_approve_push) — 6.83s
- Prompt: Looks good, push to SmartLead
- Tools called: ['smartlead_push_campaign']
- tool_error:smartlead_push_campaign: Sequence must be approved first

## Other Issues (3)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.0s
- Prompt: Hi there
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.71s
- Prompt: Here is my token: mcp_df8748d67f4d3734682a01c0ab9df1932df0308d4279ffeb5446a94863308110
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 10.9s
- Prompt: Remove software product companies, keep only consulting
- Tools called: ['provide_feedback']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

