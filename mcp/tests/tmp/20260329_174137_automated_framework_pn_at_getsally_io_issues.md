# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_174137

## MCP Server Issues (4)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**04_edit_sequence Step 2** (edit_subject) — 3.21s
- Prompt: I want email 1 to have subject: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.08s
- Prompt: Mark Arcee AI as target, they're relevant
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 3** (sequence_approval) — 2.86s
- Prompt: LGTM, approve
- Tools called: ['tam_approve_checkpoint']
- missing_tool:god_approve_sequence: called:['tam_approve_checkpoint'] (acceptable: ['god_approve_sequence'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']
- tool_error:tam_approve_checkpoint: Gate not found

**17_getsales_flow Step 5** (flow_approval) — 2.86s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (9)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 2.88s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**04_edit_sequence Step 3** (provide_feedback) — 2.85s
- Prompt: Can you make the sequence more conversational? Less corporate-speak
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context'] (acceptable: ['provide_feedback'])
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 3.86s
- Prompt: Go ahead, activate the IT consulting campaign
- Tools called: ['list_smartlead_campaigns']
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.32s
- Prompt: Generate the email sequence for this campaign
- Tools called: ['get_context']
- missing:step: True

**16_campaign_lifecycle Step 4** (smartlead_push) — 3.12s
- Prompt: Let's create the campaign in SmartLead
- Tools called: ['check_integrations']
- missing_tool:god_push_to_smartlead: called:['check_integrations'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 2.9s
- Prompt: Start the campaign
- Tools called: ['get_context']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.1s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 2.99s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 1** (reply_summary) — 2.9s
- Prompt: Any warm replies?
- Tools called: ['get_context']
- missing:_links: True

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 3.0s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 3.51s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 5.97s
- Prompt: Campaigns matching petr are for this project
- Tools called: ['list_projects']
- missing:found: True
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 4.82s
- Prompt: Find IT consulting companies in Miami and video production companies in London
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 9** (email_accounts) — 4.4s
- Prompt: Use all email accounts from my petr campaigns that have Eleonora in the name
- Tools called: ['list_smartlead_campaigns']
- missing:which: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.09s
- Prompt: What's the reply status? Who's interested?
- Tools called: ['get_context']
- missing:follow-up: True

**04_edit_sequence Step 1** (review_sequence) — 2.85s
- Prompt: Show me the sequence for the IT consulting campaign
- Tools called: ['list_projects']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**05_activate_campaign Step 1** (review_before_activate) — 2.84s
- Prompt: Email received, sequence looks good. What's waiting for my approval?
- Tools called: ['get_context']
- missing:pending: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 3.06s
- Prompt: I got the test email, looks good
- Tools called: ['check_integrations']
- must_contain_any: ['activate', 'launch', 'ready']

