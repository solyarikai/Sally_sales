# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_190238

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**04_edit_sequence Step 2** (edit_subject) — 4.78s
- Prompt: Update the first email subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.99s
- Prompt: Arcee AI should be a target — they do consulting too, not just AI
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**17_getsales_flow Step 5** (flow_approval) — 3.58s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (11)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.64s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**03_add_more_targets Step 2** (process_new) — 3.99s
- Prompt: Run the pipeline on the new batch
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**04_edit_sequence Step 3** (provide_feedback) — 3.54s
- Prompt: The wording feels robotic, humanize it
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context'] (acceptable: ['provide_feedback'])
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 3.9s
- Prompt: Launch it
- Tools called: ['get_context']
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.87s
- Prompt: Create the outreach sequence
- Tools called: ['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.65s
- Prompt: The sequence is fine, go ahead
- Tools called: ['check_destination']
- missing_tool:god_approve_sequence: called:['check_destination'] (acceptable: ['god_approve_sequence'])
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 3.61s
- Prompt: Push this to SmartLead
- Tools called: ['check_destination']
- missing_tool:god_push_to_smartlead: called:['check_destination'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:campaign: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.61s
- Prompt: Yes, activate the campaign
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.9s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.6s
- Prompt: Push to GetSales
- Tools called: ['check_integrations']
- missing_tool:gs_push_to_getsales: called:['check_integrations'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 1** (reply_summary) — 3.43s
- Prompt: Any warm replies?
- Tools called: ['get_context']
- missing:_links: True

## Other Issues (13)

**01_full_journey_easystaff Step 1** (first_contact) — 2.83s
- Prompt: Hi, I need to start gathering leads for outreach
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 3.86s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 4** (api_keys) — 3.8s
- Prompt: Which services are connected?
- Tools called: ['check_integrations']
- missing:API key: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.93s
- Prompt: Look for SmartLead campaigns with petr in the name — those are mine
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.67s
- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 3.9s
- Prompt: Start gathering for IT consulting and video production
- Tools called: ['get_context']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 10.61s
- Prompt: Use Eleonora's sending accounts from the petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 5.04s
- Prompt: Generate the email sequence and push it to SmartLead as a draft campaign
- Tools called: ['get_context']
- missing:check your inbox: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.65s
- Prompt: Any warm leads? Who should I reply to?
- Tools called: ['get_context']
- missing:follow-up: True
- missing:interested: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 3.8s
- Prompt: Any campaigns waiting to launch?
- Tools called: ['get_context']
- missing:ready: True

**04_edit_sequence Step 1** (review_sequence) — 4.32s
- Prompt: Let me see the email sequence
- Tools called: ['get_context']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**16_campaign_lifecycle Step 1** (email_account_selection) — 3.03s
- Prompt: For email accounts, use eleonora's accounts from the campaigns with petr in name
- Tools called: ['list_email_accounts']
- unexpected:error: True

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 3.84s
- Prompt: Don't track replies for that campaign
- Tools called: ['get_context']
- must_contain_any: ['monitoring', 'disabled', 'stopped']

