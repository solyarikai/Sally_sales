# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260330_011405

## MCP Server Issues (1)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 12** (approve_launch) — 2.77s
- Prompt: Approved, activate
- Tools called: ['tam_approve_checkpoint']
- missing_tool:activate_campaign: called:['tam_approve_checkpoint'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- must_contain_any: ['activated', 'launched', 'monitoring']
- tool_error:tam_approve_checkpoint: Gate not found

## GPT Tool Selection Issues (5)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**01_default_smartlead_flow Step 2** (login) — 3.25s
- Prompt: Here is my token: TOKEN_PLACEHOLDER
- Tools called: ['login']
- missing_tool:check_integrations: called:['login'] (acceptable: ['check_integrations', 'get_context'])
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 5** (offer_from_website) — 3.13s
- Prompt: Our website is easystaff.io
- Tools called: ['login']
- missing_tool:create_project: called:['login'] (acceptable: ['create_project', 'get_context'])

**01_default_smartlead_flow Step 7** (filter_alignment) — 3.04s
- Prompt: Go ahead, what are the filters?
- Tools called: ['tam_list_sources']
- missing_tool:parse_gathering_intent: called:['tam_list_sources'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters', 'get_context'])

**01_default_smartlead_flow Step 8** (pipeline_launch) — 3.16s
- Prompt: Start gathering
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**01_default_smartlead_flow Step 11** (campaign_creation) — 2.91s
- Prompt: Push to SmartLead
- Tools called: ['check_destination']
- missing_tool:smartlead_push_campaign: called:['check_destination'] (acceptable: ['smartlead_push_campaign', 'get_context', 'smartlead_generate_sequence'])

## Other Issues (1)

**01_default_smartlead_flow Step 1** (greeting_no_token) — 4.56s
- Prompt: Hi there
- Tools called: ['get_context']
- must_contain_any: ['sign up', 'token', 'mcp_']

