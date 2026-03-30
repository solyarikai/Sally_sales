# Issues Found — test6@getsally.io

**Source:** automated_framework | **Time:** 20260330_194124

## MCP Server Issues (2)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 0.5s
- Prompt: Looks good
- Tools called: ['tam_approve_checkpoint']
- must_contain_any: ['approved', 'scraping', 'analyzing']
- tool_error:tam_approve_checkpoint: Gate not found

**01_default_smartlead_flow Step 19** (5.2_approve_push) — 0.49s
- Prompt: Create the campaign
- Tools called: ['smartlead_push_campaign']
- tool_error:smartlead_push_campaign: Sequence must be approved first

## Other Issues (3)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.0s
- Prompt: Help me find leads
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.62s
- Prompt: Here is my token: mcp_2640f23d2756010ffaaa1a6ff2fbf801d45214743a58353524bb44867a2fbd5c
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 0.68s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['provide_feedback']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

