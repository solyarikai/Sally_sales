# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_192130

## MCP Server Issues (4)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**03_add_more_targets Step 2** (process_new) — 3.55s
- Prompt: Blacklist check and analyze the additions
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['tam_blacklist_check'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['tam_blacklist_check'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['tam_blacklist_check'] (acceptable: ['tam_analyze'])
- tool_error:tam_blacklist_check: Run not found

**04_edit_sequence Step 2** (edit_subject) — 3.93s
- Prompt: Edit step 1 subject: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 4.48s
- Prompt: Arcee AI should be a target — they do consulting too, not just AI
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.66s
- Prompt: LGTM, approve
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

## GPT Tool Selection Issues (7)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.55s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**05_activate_campaign Step 2** (activate) — 4.67s
- Prompt: Go ahead, activate the IT consulting campaign
- Tools called: ['list_smartlead_campaigns']
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 3.67s
- Prompt: Let's create the campaign in SmartLead
- Tools called: ['check_integrations']
- missing_tool:god_push_to_smartlead: called:['check_integrations'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.44s
- Prompt: Go ahead, launch it
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.7s
- Prompt: Generate the LinkedIn flow
- Tools called: ['list_projects']
- missing_tool:gs_generate_flow: called:['list_projects'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.86s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 5** (meeting_requests) — 3.54s
- Prompt: Any meeting requests?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context'])

## Other Issues (14)

**01_full_journey_easystaff Step 1** (first_contact) — 4.19s
- Prompt: I want to set up lead generation campaigns
- Tools called: ['list_projects']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 3.84s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 4** (api_keys) — 4.01s
- Prompt: Show my API connections
- Tools called: ['check_integrations']
- missing:API key: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.99s
- Prompt: My campaigns have 'petr' in the name
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.49s
- Prompt: Gather leads — IT consulting Miami + video production London
- Tools called: ['list_projects']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 3.79s
- Prompt: Launch the pipeline for both segments
- Tools called: ['list_projects']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 13.18s
- Prompt: Use the Eleonora accounts, the ones from petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.69s
- Prompt: Create the sequence and campaign in SmartLead
- Tools called: ['check_destination']
- missing:DRAFT: True
- missing:check your inbox: True
- missing:approval: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 4.35s
- Prompt: Any warm leads? Who should I reply to?
- Tools called: ['replies_list']
- missing:follow-up: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 3.52s
- Prompt: Do I have any pending campaigns? What's their status?
- Tools called: ['get_context']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 4.89s
- Prompt: Let me see the email sequence
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 3.37s
- Prompt: I got the test email, looks good
- Tools called: ['check_integrations']
- must_contain_any: ['activate', 'launch', 'ready']

**17_getsales_flow Step 1** (destination_clarification) — 5.07s
- Prompt: Create campaign for the pipeline targets
- Tools called: ['list_projects']
- must_contain_any: ['SmartLead', 'GetSales', 'destination']

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 4.76s
- Prompt: Don't track replies for that campaign
- Tools called: ['list_smartlead_campaigns']
- must_contain_any: ['monitoring', 'disabled', 'stopped']

