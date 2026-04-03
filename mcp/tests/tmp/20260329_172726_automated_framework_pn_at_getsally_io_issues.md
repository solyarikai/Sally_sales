# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_172726

## MCP Server Issues (3)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**04_edit_sequence Step 2** (edit_subject) — 3.15s
- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.75s
- Prompt: Arcee AI should be a target — they do consulting too, not just AI
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**17_getsales_flow Step 5** (flow_approval) — 3.11s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (17)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.02s
- Prompt: Get me more leads, 10 more IT consulting companies
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context']
- missing:gathered: True

**04_edit_sequence Step 3** (provide_feedback) — 4.23s
- Prompt: The wording feels robotic, humanize it
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context']
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 3.89s
- Prompt: Go ahead, activate the IT consulting campaign
- Tools called: ['list_smartlead_campaigns']
- missing_tool:activate_campaign: called:['list_smartlead_campaigns']
- missing:ACTIVE: True
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 2.99s
- Prompt: Create the outreach sequence
- Tools called: ['get_context']
- missing_tool:god_generate_sequence: called:['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.04s
- Prompt: Approve it
- Tools called: ['get_context']
- missing_tool:god_approve_sequence: called:['get_context']
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 3.12s
- Prompt: Push this to SmartLead
- Tools called: ['check_destination']
- missing_tool:god_push_to_smartlead: called:['check_destination']
- missing:DRAFT: True
- missing:campaign: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 3.29s
- Prompt: Start the campaign
- Tools called: ['check_integrations']
- missing_tool:activate_campaign: called:['check_integrations']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 2.94s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context']
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 3.16s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination']
- missing:DRAFT: True
- missing:pushed: True

**18_session_continuity Step 2** (verify_project_context) — 6.01s
- Prompt: What's in my pipeline?
- Tools called: ['get_context']
- missing_tool:pipeline_status: called:['get_context']

**19_reply_intelligence Step 1** (reply_summary) — 4.21s
- Prompt: What's the reply situation?
- Tools called: ['get_context']
- missing_tool:replies_summary: called:['get_context']
- missing:_links: True

**19_reply_intelligence Step 2** (warm_leads_detail) — 3.34s
- Prompt: Which leads are interested?
- Tools called: ['get_context']
- missing_tool:replies_list: called:['get_context']

**19_reply_intelligence Step 3** (followups_needed) — 3.06s
- Prompt: Any leads I should follow up with?
- Tools called: ['get_context']
- missing_tool:replies_followups: called:['get_context']

**19_reply_intelligence Step 4** (deep_link_to_crm) — 3.19s
- Prompt: Open in CRM
- Tools called: ['get_context']
- missing_tool:replies_deep_link: called:['get_context']

**19_reply_intelligence Step 5** (meeting_requests) — 3.31s
- Prompt: Did anyone ask for a meeting?
- Tools called: ['get_context']
- missing_tool:replies_list: called:['get_context']

**21_crm_verification Step 1** (crm_contacts_visible) — 3.18s
- Prompt: List my contacts
- Tools called: ['get_context']
- missing_tool:query_contacts: called:['get_context']

**22_campaigns_page_monitoring Step 1** (campaigns_list) — 2.93s
- Prompt: Show me my campaigns
- Tools called: ['get_context']
- missing_tool:list_smartlead_campaigns: called:['get_context']

## Other Issues (8)

**01_full_journey_easystaff Step 1** (first_contact) — 2.94s
- Prompt: Hi, I need to start gathering leads for outreach
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 2.96s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.13s
- Prompt: Look for SmartLead campaigns with petr in the name — those are mine
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.14s
- Prompt: Two segments: 1) IT consulting, Miami 2) video production, London
- Tools called: ['get_context']
- missing:2 segment: True

**01_full_journey_easystaff Step 9** (email_accounts) — 9.81s
- Prompt: Use the Eleonora accounts, the ones from petr campaigns
- Tools called: ['list_email_accounts']
- missing:which: True

**04_edit_sequence Step 1** (review_sequence) — 4.42s
- Prompt: What emails will be sent in the IT consulting campaign?
- Tools called: ['list_smartlead_campaigns']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**05_activate_campaign Step 1** (review_before_activate) — 3.12s
- Prompt: Received the test email, all good. Any campaigns ready to launch?
- Tools called: ['check_integrations']
- missing:DRAFT: True
- missing:pending: True

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 2.89s
- Prompt: Don't track replies for that campaign
- Tools called: ['get_context']
- must_contain_any: ['monitoring', 'disabled', 'stopped']

