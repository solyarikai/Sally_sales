# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_142429

## MCP Server Issues (5)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_full_journey_easystaff Step 3** (company_context) — 3.52s
- Prompt: Check out easystaff.io — that's us. I'm Eleonora
- Tools called: ['tam_gather']
- missing:created: True
- missing:scraped: True
- tool_error:tam_gather: Project not found

**04_edit_sequence Step 2** (edit_subject) — 3.15s
- Prompt: Edit step 1 subject: {{first_name}} — contractors abroad?
- Tools called: ['edit_sequence_step']
- missing:updated: True
- missing:synced: True
- tool_error:edit_sequence_step: Sequence not found

**04_edit_sequence Step 4** (override_target) — 3.22s
- Prompt: Override Arcee AI — it IS a target
- Tools called: ['override_company_target']
- tool_error:override_company_target: Company not found

**16_campaign_lifecycle Step 5** (test_email_verification) — 3.35s
- Prompt: Got it, the test email is fine
- Tools called: ['send_test_email']
- must_contain_any: ['activate', 'launch', 'ready']
- tool_error:send_test_email: No email accounts on this campaign

**17_getsales_flow Step 5** (flow_approval) — 2.59s
- Prompt: Looks good, approve the flow
- Tools called: ['gs_approve_flow']
- tool_error:gs_approve_flow: Flow not found

## GPT Tool Selection Issues (17)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**03_add_more_targets Step 1** (add_targets) — 3.09s
- Prompt: Add 10 more IT consulting targets to the pipeline
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context']
- missing:gathered: True

**04_edit_sequence Step 3** (provide_feedback) — 3.16s
- Prompt: The wording feels robotic, humanize it
- Tools called: ['get_context']
- missing_tool:provide_feedback: called:['get_context']
- missing:feedback: True
- missing:stored: True
- missing:future: True

**05_activate_campaign Step 2** (activate) — 3.36s
- Prompt: Yes, start the campaign
- Tools called: ['get_context']
- missing_tool:activate_campaign: called:['get_context']
- missing:sending: True

**16_campaign_lifecycle Step 2** (sequence_generation) — 3.19s
- Prompt: Generate the email sequence for this campaign
- Tools called: ['get_context']
- missing_tool:god_generate_sequence: called:['get_context']
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 3.08s
- Prompt: The sequence is fine, go ahead
- Tools called: ['check_destination']
- missing_tool:god_approve_sequence: called:['check_destination']
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 9.92s
- Prompt: Push to SmartLead with those email accounts
- Tools called: ['list_email_accounts']
- missing_tool:god_push_to_smartlead: called:['list_email_accounts']
- missing:DRAFT: True
- missing:inbox: True

**16_campaign_lifecycle Step 6** (campaign_activation) — 2.82s
- Prompt: Yes, activate the campaign
- Tools called: ['check_destination']
- missing_tool:activate_campaign: called:['check_destination']
- missing:activated: True

**17_getsales_flow Step 4** (flow_generation) — 3.01s
- Prompt: Generate the LinkedIn flow
- Tools called: ['get_context']
- missing_tool:gs_generate_flow: called:['get_context']
- missing:step: True

**17_getsales_flow Step 6** (push_to_getsales) — 4.42s
- Prompt: Push to GetSales
- Tools called: ['check_destination']
- missing_tool:gs_push_to_getsales: called:['check_destination']
- missing:DRAFT: True
- missing:pushed: True

**18_session_continuity Step 2** (verify_project_context) — 3.1s
- Prompt: What's in my pipeline?
- Tools called: ['get_context']
- missing_tool:pipeline_status: called:['get_context']

**19_reply_intelligence Step 1** (reply_summary) — 2.77s
- Prompt: How are my campaigns doing? Any replies?
- Tools called: ['get_context']
- missing_tool:replies_summary: called:['get_context']
- missing:_links: True

**19_reply_intelligence Step 2** (warm_leads_detail) — 3.03s
- Prompt: List the warm replies
- Tools called: ['get_context']
- missing_tool:replies_list: called:['get_context']

**19_reply_intelligence Step 3** (followups_needed) — 2.93s
- Prompt: Show me leads that need attention
- Tools called: ['get_context']
- missing_tool:replies_followups: called:['get_context']

**19_reply_intelligence Step 4** (deep_link_to_crm) — 3.34s
- Prompt: Take me to the CRM for this lead
- Tools called: ['get_context']
- missing_tool:replies_deep_link: called:['get_context']

**19_reply_intelligence Step 5** (meeting_requests) — 2.76s
- Prompt: Any meeting requests?
- Tools called: ['get_context']
- missing_tool:replies_list: called:['get_context']

**21_crm_verification Step 1** (crm_contacts_visible) — 8.86s
- Prompt: Show me my contacts in CRM
- Tools called: ['get_context']
- missing_tool:query_contacts: called:['get_context']

**22_campaigns_page_monitoring Step 1** (campaigns_list) — 4.43s
- Prompt: Show me my campaigns
- Tools called: ['get_context']
- missing_tool:list_smartlead_campaigns: called:['get_context']

## Other Issues (7)

**01_full_journey_easystaff Step 1** (first_contact) — 3.27s
- Prompt: Hey, I want to launch outreach for my company
- Tools called: ['get_context']
- missing:sign up: True
- missing:token: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 2.92s
- Prompt: Here's my token: mcp_xxx...
- Tools called: ['login']
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 4.52s
- Prompt: My campaigns have 'petr' in the name
- Tools called: ['list_smartlead_campaigns']
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 3.55s
- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: ['list_projects']
- missing:2 segment: True

**01_full_journey_easystaff Step 9** (email_accounts) — 4.16s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:email account: True
- missing:which: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 3.48s
- Prompt: What's the reply status? Who's interested?
- Tools called: ['get_context']
- missing:follow-up: True

**04_edit_sequence Step 1** (review_sequence) — 2.81s
- Prompt: Let me see the email sequence
- Tools called: ['get_context']
- missing:Email 1: True
- missing:subject: True
- missing:body: True

