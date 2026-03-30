# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260330_213546

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 11** (reply_intelligence) — 5.11s
- Prompt: Any warm leads? Who should I reply to?
- Tools called: ['replies_summary']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

**03_add_more_targets Step 1** (add_targets) — 7.96s
- Prompt: Gather 10 more target companies for the IT consulting segment
- Tools called: ['tam_gather']
- tool_error:tam_gather: missing_essential_filters

**19_reply_intelligence Step 1** (reply_summary) — 20.74s
- Prompt: Show me the reply summary
- Tools called: ['replies_summary']
- missing_words: found 0/1: ['_links']
- tool_error:replies_summary: Project '<UNKNOWN>' not found

## GPT Tool Selection Issues (1)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**16_campaign_lifecycle Step 3** (sequence_approval) — 4.29s
- Prompt: Looks good, approve the sequence
- Tools called: ['get_context']
- must_contain_any: ['approved', 'ready']

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 90.97s
- Prompt: Help me find companies to reach out to
- Tools called: []
- missing_words: found 0/3: ['sign up', 'token', 'setup']

**01_full_journey_easystaff Step 2** (auth) — 14.46s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing_words: found 0/3: ['welcome', 'website', 'what do you']

**04_edit_sequence Step 1** (review_sequence) — 19.8s
- Prompt: Let me see the email sequence
- Tools called: ['get_context']
- missing_words: found 0/3: ['Email 1', 'subject', 'body']

**16_campaign_lifecycle Step 4** (smartlead_push) — 91.02s
- Prompt: Push this to SmartLead
- Tools called: []
- missing_tool:smartlead_push_campaign: called:[] (acceptable: ['smartlead_push_campaign', 'get_context', 'smartlead_generate_sequence'])
- missing_words: found 0/4: ['DRAFT', 'campaign', 'SmartLead']
- unexpected:error: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 19.77s
- Prompt: Yes, activate the campaign
- Tools called: ['activate_campaign']
- unexpected:error: True

**17_getsales_flow Step 5** (flow_approval) — 90.91s
- Prompt: Looks good, approve the flow
- Tools called: []
- missing_tool:gs_approve_flow: called:[] (acceptable: ['gs_approve_flow', 'get_context'])

**19_reply_intelligence Step 4** (deep_link_to_crm) — 90.83s
- Prompt: Take me to the CRM for this lead
- Tools called: []
- missing_tool:replies_deep_link: called:[] (acceptable: ['replies_deep_link', 'get_context', 'query_contacts', 'replies_list'])
- missing_words: found 0/2: ['crm', 'http']

**22_campaigns_page_monitoring Step 1** (campaigns_list) — 15.78s
- Prompt: Show me my campaigns
- Tools called: []
- missing_tool:list_smartlead_campaigns: called:[] (acceptable: ['list_smartlead_campaigns', 'get_context', 'check_integrations'])
- must_contain_any: ['campaign', 'SmartLead', 'status']

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 0.29s
- Prompt: Disable monitoring for the petr campaign
- Tools called: []
- must_contain_any: ['monitoring', 'disabled', 'stopped']

