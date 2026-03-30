# Issues Found — test7@getsally.io

**Source:** automated_framework | **Time:** 20260330_210058

## MCP Server Issues (1)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 19** (5.2_push_campaign) — 0.37s
- Prompt: Create the campaign
- Tools called: ['smartlead_push_campaign']
- tool_error:smartlead_push_campaign: email_account_ids required. Call list_email_accounts first and ask the user whic

## Other Issues (3)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.0s
- Prompt: Hi there
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.62s
- Prompt: Here is my token: mcp_4c24deb0e0c01a1805f942e94bd431210c6ae636a7ba78d962f17051cdaa48c5
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 0.58s
- Prompt: Some of these aren't IT consulting firms, they're software product companies. Exclude pure software 
- Tools called: ['provide_feedback']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

