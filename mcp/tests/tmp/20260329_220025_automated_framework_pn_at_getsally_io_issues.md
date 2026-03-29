# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_220025

## MCP Server Issues (6)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**03_add_more_targets Step 2** (process_new) — 3.56s
- Prompt: Blacklist check and analyze the additions
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing_tool:tam_pre_filter: called:['tam_blacklist_check'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:['tam_blacklist_check'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['tam_blacklist_check'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])
- tool_error:tam_blacklist_check: Run not found

**04_edit_sequence Step 2** (edit_subject) — 3.66s
- Prompt: Edit step 1 subject: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing_words: found 0/2: ['updated', 'synced']
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 4.19s
- Prompt: Mark Arcee AI as target, they're relevant
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.24s
- Prompt: LGTM, approve
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence', 'get_context'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

**17_getsales_flow Step 5** (flow_approval) — 3.55s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

**19_reply_intelligence Step 1** (reply_summary) — 3.48s
- Prompt: Show me the reply summary
- Tools called: ['replies_summary']
- missing_words: found 0/1: ['_links']
- tool_error:replies_summary: Project 'Project' not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 9.63s
- Prompt: Can you find 10 more targets for the IT consulting pipeline?
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**05_activate_campaign Step 2** (activate) — 3.39s
- Prompt: Yes, start the campaign
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])

**16_campaign_lifecycle Step 2** (sequence_generation) — 4.59s
- Prompt: Build the email sequence based on our best practices
- Tools called: ['check_destination']
- missing_tool:god_generate_sequence: called:['check_destination'] (acceptable: ['god_generate_sequence', 'get_context', 'god_score_campaigns'])

**16_campaign_lifecycle Step 4** (smartlead_push) — 4.67s
- Prompt: Create the SmartLead campaign
- Tools called: ['list_smartlead_campaigns']
- missing_tool:god_push_to_smartlead: called:['list_smartlead_campaigns'] (acceptable: ['god_push_to_smartlead', 'get_context', 'god_generate_sequence'])
- unexpected:ACTIVE: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.86s
- Prompt: Go ahead, launch it
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing_words: found 0/2: ['activated', 'campaign']

**17_getsales_flow Step 4** (flow_generation) — 3.59s
- Prompt: Generate the LinkedIn flow
- Tools called: ['check_integrations']
- missing_tool:gs_generate_flow: called:['check_integrations'] (acceptable: ['gs_generate_flow', 'get_context', 'god_generate_sequence'])

**17_getsales_flow Step 6** (push_to_getsales) — 3.74s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales', 'get_context'])

**19_reply_intelligence Step 5** (meeting_requests) — 4.11s
- Prompt: Any meetings booked?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context', 'replies_followups'])

## Other Issues (5)

**01_full_journey_easystaff Step 1** (first_contact) — 3.24s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['list_projects']
- missing_words: found 0/3: ['sign up', 'token', 'setup']

**01_full_journey_easystaff Step 2** (auth) — 2.96s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing_words: found 0/3: ['welcome', 'website', 'what do you']

**04_edit_sequence Step 1** (review_sequence) — 7.28s
- Prompt: Let me see the email sequence
- Tools called: ['list_smartlead_campaigns']
- missing_words: found 0/3: ['Email 1', 'subject', 'body']

**16_campaign_lifecycle Step 5** (test_email_verification) — 7.85s
- Prompt: I got the test email, looks good
- Tools called: ['check_integrations']
- must_contain_any: ['activate', 'launch', 'ready']

**17_getsales_flow Step 1** (destination_clarification) — 3.91s
- Prompt: I want to start reaching out to these companies
- Tools called: ['list_projects']
- must_contain_any: ['SmartLead', 'GetSales', 'destination']

