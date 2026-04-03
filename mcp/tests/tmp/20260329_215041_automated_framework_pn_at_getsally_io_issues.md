# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_215041

## MCP Server Issues (9)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 8** (pipeline_processing) — 7.69s
- Prompt: Run blacklist check and analysis
- Tools called: ['tam_blacklist_check', 'tam_analyze']
- tool_error:tam_blacklist_check: Run not found
- tool_error:tam_analyze: Run not found

**03_add_more_targets Step 2** (process_new) — 3.55s
- Prompt: Blacklist check and analyze the additions
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing_tool:tam_pre_filter: called:['tam_blacklist_check'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:['tam_blacklist_check'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['tam_blacklist_check'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])
- tool_error:tam_blacklist_check: Run not found

**04_edit_sequence Step 2** (edit_subject) — 8.83s
- Prompt: I want email 1 to have subject: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step', 'send_test_email']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found
- tool_error:send_test_email: No email accounts on this campaign

**04_edit_sequence Step 4** (override_target) — 4.09s
- Prompt: Override Arcee AI — it IS a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**05_activate_campaign Step 1** (review_before_activate) — 3.79s
- Prompt: Email received, sequence looks good. What's waiting for my approval?
- Tools called: ['replies_summary']
- missing:campaign: True
- missing:DRAFT: True
- missing:pending: True
- tool_error:replies_summary: Project 'Project' not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.95s
- Prompt: Approve it
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence', 'get_context'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

**16_campaign_lifecycle Step 5** (test_email_verification) — 5.31s
- Prompt: Got it, the test email is fine
- Tools called: ['send_test_email']
- must_contain_any: ['activate', 'launch', 'ready']
- tool_error:send_test_email: No email accounts on this campaign

**17_getsales_flow Step 5** (flow_approval) — 3.93s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

**19_reply_intelligence Step 1** (reply_summary) — 4.0s
- Prompt: What's the reply situation?
- Tools called: ['replies_summary']
- missing:_links: True
- tool_error:replies_summary: Project 'Project' not found

## GPT Tool Selection Issues (8)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 4.83s
- Prompt: Can you find 10 more targets for the IT consulting pipeline?
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- missing:gathered: True

**05_activate_campaign Step 2** (activate) — 3.88s
- Prompt: Yes, start the campaign
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.68s
- Prompt: Create the outreach sequence
- Tools called: ['list_projects']
- missing_tool:god_generate_sequence: called:['list_projects'] (acceptable: ['god_generate_sequence', 'get_context', 'god_score_campaigns'])
- missing:email: True
- missing:step: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 10.98s
- Prompt: Create the SmartLead campaign
- Tools called: ['list_email_accounts']
- missing_tool:god_push_to_smartlead: called:['list_email_accounts'] (acceptable: ['god_push_to_smartlead', 'get_context', 'god_generate_sequence'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 6.25s
- Prompt: Yes, activate the campaign
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.64s
- Prompt: Generate the LinkedIn flow
- Tools called: ['check_integrations']
- missing_tool:gs_generate_flow: called:['check_integrations'] (acceptable: ['gs_generate_flow', 'get_context', 'god_generate_sequence'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.6s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales', 'get_context'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 5** (meeting_requests) — 3.79s
- Prompt: Any meetings booked?
- Tools called: ['query_contacts']
- missing_tool:replies_list: called:['query_contacts'] (acceptable: ['replies_list', 'replies_summary', 'get_context', 'replies_followups'])

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 4.15s
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

**01_full_journey_easystaff Step 5** (existing_campaigns) — 5.09s
- Prompt: My campaigns have 'petr' in the name
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 4.22s
- Prompt: Gather leads — IT consulting Miami + video production London
- Tools called: ['list_projects']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 4.09s
- Prompt: Launch the pipeline for both segments
- Tools called: ['list_projects']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 10.52s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.64s
- Prompt: Build the outreach sequence and create a SmartLead draft
- Tools called: ['list_projects']
- missing:campaign: True
- missing:check your inbox: True
- missing:approval: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 5.13s
- Prompt: Do I have any pending campaigns? What's their status?
- Tools called: ['get_context']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 4.32s
- Prompt: Let me see the email sequence
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

