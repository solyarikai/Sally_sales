# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_193049

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**04_edit_sequence Step 2** (edit_subject) — 3.52s
- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.73s
- Prompt: arcee.ai is actually a consulting firm, make it a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**19_reply_intelligence Step 1** (reply_summary) — 3.8s
- Prompt: How are my campaigns doing? Any replies?
- Tools called: ['replies_summary']
- missing:_links: True
- tool_error:replies_summary: Project 'Project' not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.62s
- Prompt: I need more companies — get me 10 additional IT consulting firms in Miami
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**03_add_more_targets Step 2** (process_new) — 4.11s
- Prompt: Process the new companies — blacklist, scrape, and analyze them
- Tools called: ['run_full_pipeline']
- missing_tool:tam_blacklist_check: called:['run_full_pipeline'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['run_full_pipeline'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])

**05_activate_campaign Step 2** (activate) — 4.77s
- Prompt: Activate the IT consulting Miami campaign
- Tools called: ['list_smartlead_campaigns']
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 10.14s
- Prompt: Create the SmartLead campaign
- Tools called: ['list_email_accounts']
- missing_tool:god_push_to_smartlead: called:['list_email_accounts'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.53s
- Prompt: Go ahead, launch it
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.53s
- Prompt: Generate the LinkedIn flow
- Tools called: ['check_integrations']
- missing_tool:gs_generate_flow: called:['check_integrations'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.48s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 5** (meeting_requests) — 3.75s
- Prompt: Any meetings booked?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context'])

## Other Issues (10)

**01_full_journey_easystaff Step 1** (first_contact) — 3.66s
- Prompt: Hi, I need to start gathering leads for outreach
- Tools called: ['list_projects']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 3.28s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.96s
- Prompt: Look for SmartLead campaigns with petr in the name — those are mine
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.54s
- Prompt: Find IT consulting companies in Miami and video production companies in London
- Tools called: ['list_projects']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 3.51s
- Prompt: Start gathering for IT consulting and video production
- Tools called: ['list_projects']
- missing:gathered: True
- missing:pipeline: True

**01_full_journey_easystaff Step 9** (email_accounts) — 10.03s
- Prompt: Use Eleonora's sending accounts from the petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.39s
- Prompt: Build the outreach sequence and create a SmartLead draft
- Tools called: ['check_destination']
- missing:campaign: True
- missing:check your inbox: True
- missing:approval: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 4.27s
- Prompt: Show my draft campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 4.51s
- Prompt: Let me see the email sequence
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 5.57s
- Prompt: Test email received, sequence looks great
- Tools called: ['check_integrations']
- must_contain_any: ['activate', 'launch', 'ready']

