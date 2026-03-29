# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_214040

## MCP Server Issues (9)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.58s
- Prompt: What's the reply status? Who's interested?
- Tools called: ['replies_summary']
- missing:warm: True
- missing:follow-up: True
- tool_error:replies_summary: Project 'Project' not found

**03_add_more_targets Step 2** (process_new) — 3.63s
- Prompt: Blacklist check and analyze the additions
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['tam_blacklist_check'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['tam_blacklist_check'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['tam_blacklist_check'] (acceptable: ['tam_analyze'])
- tool_error:tam_blacklist_check: Run not found

**04_edit_sequence Step 2** (edit_subject) — 4.64s
- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.95s
- Prompt: Override Arcee AI — it IS a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.56s
- Prompt: LGTM, approve
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

**17_getsales_flow Step 1** (destination_clarification) — 3.36s
- Prompt: Launch outreach for the targets we found
- Tools called: ['pipeline_status']
- must_contain_any: ['SmartLead', 'GetSales', 'destination']
- tool_error:pipeline_status: Run not found

**17_getsales_flow Step 5** (flow_approval) — 3.61s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

**18_session_continuity Step 2** (verify_project_context) — 3.8s
- Prompt: How many companies did we find?
- Tools called: ['pipeline_status']
- tool_error:pipeline_status: Run not found

**19_reply_intelligence Step 1** (reply_summary) — 4.61s
- Prompt: Show me the reply summary
- Tools called: ['replies_summary']
- missing:_links: True
- tool_error:replies_summary: Project 'Project' not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.67s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**05_activate_campaign Step 2** (activate) — 3.86s
- Prompt: Yes, start the campaign
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 4.05s
- Prompt: Generate sequence for the IT consulting targets
- Tools called: ['list_projects']
- missing_tool:god_generate_sequence: called:['list_projects'] (acceptable: ['god_generate_sequence', 'get_context', 'god_score_campaigns'])
- missing:email: True
- missing:step: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 11.02s
- Prompt: Create the SmartLead campaign
- Tools called: ['list_email_accounts']
- missing_tool:god_push_to_smartlead: called:['list_email_accounts'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 4.31s
- Prompt: Start the campaign
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.9s
- Prompt: Generate the LinkedIn flow
- Tools called: ['check_integrations']
- missing_tool:gs_generate_flow: called:['check_integrations'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.67s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 5** (meeting_requests) — 3.6s
- Prompt: Any meeting requests?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context'])

## Other Issues (11)

**01_full_journey_easystaff Step 1** (first_contact) — 3.4s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['list_projects']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 2.98s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 4** (api_keys) — 3.77s
- Prompt: Which services are connected?
- Tools called: ['check_integrations']
- missing:API key: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.51s
- Prompt: Look for SmartLead campaigns with petr in the name — those are mine
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 16.53s
- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: ['parse_gathering_intent', 'parse_gathering_intent']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 7.39s
- Prompt: Start gathering for IT consulting and video production
- Tools called: ['list_projects']
- missing:gathered: True
- missing:pipeline: True

**01_full_journey_easystaff Step 9** (email_accounts) — 12.21s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.58s
- Prompt: Create the sequence and campaign in SmartLead
- Tools called: ['check_destination']
- missing:DRAFT: True
- missing:check your inbox: True
- missing:approval: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 4.66s
- Prompt: Any campaigns waiting to launch?
- Tools called: ['list_smartlead_campaigns']
- missing:ready: True

**04_edit_sequence Step 1** (review_sequence) — 4.0s
- Prompt: Show the campaign sequence for review
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 3.51s
- Prompt: Checked my inbox, email looks good
- Tools called: ['check_integrations']
- must_contain_any: ['activate', 'launch', 'ready']

