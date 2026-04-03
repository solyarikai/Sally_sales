# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_173626

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**04_edit_sequence Step 2** (edit_subject) — 3.16s
- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 2.98s
- Prompt: Override Arcee AI — it IS a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**17_getsales_flow Step 5** (flow_approval) — 2.79s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (10)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 2.78s
- Prompt: Add 10 more IT consulting targets to the pipeline
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**04_edit_sequence Step 3** (provide_feedback) — 3.97s
- Prompt: The tone is too formal, make it more casual and friendly
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context'] (acceptable: ['provide_feedback'])
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 4.14s
- Prompt: Activate the IT consulting Miami campaign
- Tools called: ['list_smartlead_campaigns']
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 2.93s
- Prompt: Build the email sequence based on our best practices
- Tools called: ['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.13s
- Prompt: The sequence is fine, go ahead
- Tools called: ['check_destination']
- missing_tool:god_approve_sequence: called:['check_destination'] (acceptable: ['god_approve_sequence'])
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 2.77s
- Prompt: Create the SmartLead campaign
- Tools called: ['check_destination']
- missing_tool:god_push_to_smartlead: called:['check_destination'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.91s
- Prompt: Go ahead, launch it
- Tools called: ['get_context']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.0s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.33s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 1** (reply_summary) — 3.84s
- Prompt: Any warm replies?
- Tools called: ['get_context']
- missing:_links: True

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 4.33s
- Prompt: I want to set up lead generation campaigns
- Tools called: ['list_projects']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 3.56s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 3.68s
- Prompt: Campaigns matching petr are for this project
- Tools called: ['list_projects']
- missing:found: True
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.2s
- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 9** (email_accounts) — 5.24s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:email account: True
- missing:which: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.18s
- Prompt: What's the reply status? Who's interested?
- Tools called: ['get_context']
- missing:follow-up: True

**04_edit_sequence Step 1** (review_sequence) — 3.35s
- Prompt: Show the campaign sequence for review
- Tools called: ['get_context']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 2.9s
- Prompt: Test email received, sequence looks great
- Tools called: ['check_destination']
- must_contain_any: ['activate', 'launch', 'ready']

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 2.84s
- Prompt: Don't track replies for that campaign
- Tools called: ['get_context']
- must_contain_any: ['monitoring', 'disabled', 'stopped']

