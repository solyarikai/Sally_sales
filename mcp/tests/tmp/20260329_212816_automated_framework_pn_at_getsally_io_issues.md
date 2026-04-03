# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_212816

## GPT Tool Selection Issues (14)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 19.29s
- Prompt: Can you find 10 more targets for the IT consulting pipeline?
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**03_add_more_targets Step 2** (process_new) — 20.51s
- Prompt: Process the new companies — blacklist, scrape, and analyze them
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**04_edit_sequence Step 2** (edit_subject) — 20.1s
- Prompt: Update the first email subject to: {{first_name}} — contractors abroad?
- Tools called: ['get_context']
- missing_tool:edit_sequence_step: called:['get_context'] (acceptable: ['edit_sequence_step'])
- missing:updated: True
- missing:synced: True

**04_edit_sequence Step 4** (override_target) — 20.11s
- Prompt: arcee.ai is actually a consulting firm, make it a target
- Tools called: ['get_context']
- missing_tool:override_company_target: called:['get_context'] (acceptable: ['override_company_target'])
- missing:override: True

**05_activate_campaign Step 2** (activate) — 4.41s
- Prompt: Go ahead, activate the IT consulting campaign
- Tools called: ['get_context']
- missing:sending: True

**16_campaign_lifecycle Step 1** (email_account_selection) — 21.55s
- Prompt: Same email accounts as my petr campaigns — the eleonora ones
- Tools called: ['list_smartlead_campaigns']
- missing_tool:list_email_accounts: called:['list_smartlead_campaigns'] (acceptable: ['list_email_accounts'])

**16_campaign_lifecycle Step 2** (sequence_generation) — 4.23s
- Prompt: Build the email sequence based on our best practices
- Tools called: ['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 19.92s
- Prompt: The sequence is fine, go ahead
- Tools called: ['get_context']
- missing_tool:god_approve_sequence: called:['get_context'] (acceptable: ['god_approve_sequence'])
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 3.99s
- Prompt: Push to SmartLead with those email accounts
- Tools called: ['get_context']
- missing_tool:god_push_to_smartlead: called:['get_context'] (acceptable: ['god_push_to_smartlead'])
- missing:inbox: True
- unexpected:ACTIVE: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 19.88s
- Prompt: Activate
- Tools called: ['get_context']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 19.36s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context'] (acceptable: ['gs_generate_flow'])
- missing:step: True

**17_getsales_flow Step 5** (flow_approval) — 19.43s
- Prompt: Looks good, approve the flow
- Tools called: ['get_context']
- missing_tool:gs_approve_flow: called:['get_context'] (acceptable: ['gs_approve_flow'])

**17_getsales_flow Step 6** (push_to_getsales) — 4.04s
- Prompt: Push to GetSales
- Tools called: ['get_context']
- missing_tool:gs_push_to_getsales: called:['get_context'] (acceptable: ['gs_push_to_getsales'])
- missing:pushed: True

**19_reply_intelligence Step 1** (reply_summary) — 5.45s
- Prompt: How are my campaigns doing? Any replies?
- Tools called: ['get_context']
- missing:_links: True

## Other Issues (9)

**01_full_journey_easystaff Step 1** (first_contact) — 3.31s
- Prompt: I want to set up lead generation campaigns
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 19.01s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 20.04s
- Prompt: All campaigns including 'petr' in their names are my campaigns
- Tools called: ['get_context']
- missing:found: True
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.87s
- Prompt: Find IT consulting companies in Miami and video production companies in London
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 7** (gathering_execution) — 19.97s
- Prompt: Launch the pipeline for both segments
- Tools called: ['get_context']
- missing:gathered: True

**01_full_journey_easystaff Step 9** (email_accounts) — 11.16s
- Prompt: Use the Eleonora accounts, the ones from petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**01_full_journey_easystaff Step 10** (sequence_and_campaign) — 4.35s
- Prompt: Create the sequence and campaign in SmartLead
- Tools called: ['get_context']
- missing:check your inbox: True

**01_full_journey_easystaff Step 12** (pending_campaigns_check) — 4.58s
- Prompt: Do I have any pending campaigns? What's their status?
- Tools called: ['get_context']
- missing:ready: True
- missing:launch: True

**04_edit_sequence Step 1** (review_sequence) — 4.67s
- Prompt: Show me the sequence for the IT consulting campaign
- Tools called: ['get_context']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

