# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_191157

## MCP Server Issues (11)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 7.36s
- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: ['parse_gathering_intent', 'parse_gathering_intent']
- missing:2 segment: True
- tool_error:parse_gathering_intent: Project not found

**01_full_journey_easystaff Step 8** (pipeline_processing) — 6.19s
- Prompt: Run blacklist check and analysis
- Tools called: ['tam_blacklist_check', 'tam_analyze']
- tool_error:tam_blacklist_check: Run not found
- tool_error:tam_analyze: Run not found

**04_edit_sequence Step 2** (edit_subject) — 3.76s
- Prompt: Update the first email subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 3** (provide_feedback) — 5.8s
- Prompt: The tone is too formal, make it more casual and friendly
- Tools called: ['provide_feedback']
- missing:stored: True
- missing:future: True
- tool_error:provide_feedback: Project not found

**04_edit_sequence Step 4** (override_target) — 3.74s
- Prompt: Override Arcee AI — it IS a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.76s
- Prompt: Generate sequence for the IT consulting targets
- Tools called: ['god_generate_sequence']
- missing:email: True
- missing:step: True
- tool_error:god_generate_sequence: Project not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.35s
- Prompt: Approve it
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

**16_campaign_lifecycle Step 5** (test_email_verification) — 3.94s
- Prompt: Checked my inbox, email looks good
- Tools called: ['send_test_email']
- must_contain_any: ['activate', 'launch', 'ready']
- tool_error:send_test_email: No email accounts on this campaign

**17_getsales_flow Step 5** (flow_approval) — 3.43s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

**19_reply_intelligence Step 1** (reply_summary) — 5.89s
- Prompt: Show me the reply summary
- Tools called: ['replies_summary']
- missing:_links: True
- tool_error:replies_summary: Project 'Project' not found

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 3.46s
- Prompt: Disable monitoring for the petr campaign
- Tools called: ['import_smartlead_campaigns']
- tool_error:import_smartlead_campaigns: Project not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.79s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**03_add_more_targets Step 2** (process_new) — 5.46s
- Prompt: Process the new companies — blacklist, scrape, and analyze them
- Tools called: ['run_full_pipeline']
- missing_tool:tam_blacklist_check: called:['run_full_pipeline'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['run_full_pipeline'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])

**05_activate_campaign Step 2** (activate) — 4.18s
- Prompt: Let's go live with it
- Tools called: ['gs_activate_flow']
- missing_tool:activate_campaign: called:['gs_activate_flow'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:campaign: True
- missing:sending: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 10.68s
- Prompt: Let's create the campaign in SmartLead
- Tools called: ['list_email_accounts']
- missing_tool:god_push_to_smartlead: called:['list_email_accounts'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 4.02s
- Prompt: Go ahead, launch it
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True
- missing:campaign: True

**17_getsales_flow Step 4** (flow_generation) — 4.0s
- Prompt: Generate the LinkedIn flow
- Tools called: ['check_integrations']
- missing_tool:gs_generate_flow: called:['check_integrations'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.49s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 5** (meeting_requests) — 8.34s
- Prompt: Did anyone ask for a meeting?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context'])

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 3.34s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['list_projects']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 2.97s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 4** (api_keys) — 3.36s
- Prompt: Show my API connections
- Tools called: ['check_integrations']
- missing:API key: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 5.45s
- Prompt: My campaigns have 'petr' in the name
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 3.66s
- Prompt: Launch the pipeline for both segments
- Tools called: ['list_projects']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 10.84s
- Prompt: Use Eleonora's sending accounts from the petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.73s
- Prompt: Build the outreach sequence and create a SmartLead draft
- Tools called: ['list_projects']
- missing:campaign: True
- missing:check your inbox: True
- missing:approval: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 5.48s
- Prompt: Show my draft campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 4.37s
- Prompt: Let me see the email sequence
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

