# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_185300

## MCP Server Issues (5)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 3** (company_context) — 3.73s
- Prompt: Check out easystaff.io — that's us. I'm Eleonora
- Tools called: ['tam_gather']
- missing:created: True
- missing:scraped: True
- tool_error:tam_gather: Project not found

**01_full_journey_easystaff Step 5** (existing_campaigns) — 3.0s
- Prompt: All campaigns including 'petr' in their names are my campaigns
- Tools called: ['import_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True
- tool_error:import_smartlead_campaigns: Project not found

**04_edit_sequence Step 2** (edit_subject) — 3.18s
- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.17s
- Prompt: arcee.ai is actually a consulting firm, make it a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**17_getsales_flow Step 5** (flow_approval) — 2.89s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (11)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 2.87s
- Prompt: Can you find 10 more targets for the IT consulting pipeline?
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**03_add_more_targets Step 2** (process_new) — 3.6s
- Prompt: Process the new companies — blacklist, scrape, and analyze them
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**04_edit_sequence Step 3** (provide_feedback) — 3.08s
- Prompt: Emails are too stiff, relax the tone
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context'] (acceptable: ['provide_feedback'])
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 3.96s
- Prompt: Go ahead, activate the IT consulting campaign
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations'] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.05s
- Prompt: Create the outreach sequence
- Tools called: ['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 2.91s
- Prompt: The sequence is fine, go ahead
- Tools called: ['check_destination']
- missing_tool:god_approve_sequence: called:['check_destination'] (acceptable: ['god_approve_sequence'])
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 4.64s
- Prompt: Push this to SmartLead
- Tools called: ['check_destination']
- missing_tool:god_push_to_smartlead: called:['check_destination'] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:campaign: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 4.67s
- Prompt: Activate
- Tools called: ['get_context']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 2.84s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.19s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination'] (acceptable: ['gs_push_to_getsales'])
- missing:DRAFT: True
- missing:pushed: True

**19_reply_intelligence Step 1** (reply_summary) — 2.82s
- Prompt: Any warm replies?
- Tools called: ['get_context']
- missing:_links: True

## Other Issues (11)

**01_full_journey_easystaff Step 1** (first_contact) — 6.15s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 4.6s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 4** (api_keys) — 3.91s
- Prompt: Check my integrations
- Tools called: ['check_integrations']
- missing:API key: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 2.84s
- Prompt: Find IT consulting companies in Miami and video production companies in London
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 3.07s
- Prompt: Start gathering for IT consulting and video production
- Tools called: ['get_context']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 4.04s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:email account: True
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 3.22s
- Prompt: Create the sequence and campaign in SmartLead
- Tools called: ['get_context']
- missing:check your inbox: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.24s
- Prompt: Any warm leads? Who should I reply to?
- Tools called: ['get_context']
- missing:follow-up: True
- missing:interested: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 3.12s
- Prompt: Do I have any pending campaigns? What's their status?
- Tools called: ['get_context']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 2.96s
- Prompt: Let me see the email sequence
- Tools called: ['get_context']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**05_activate_campaign Step 1** (review_before_activate) — 2.89s
- Prompt: Email received, sequence looks good. What's waiting for my approval?
- Tools called: ['get_context']
- missing:pending: True

