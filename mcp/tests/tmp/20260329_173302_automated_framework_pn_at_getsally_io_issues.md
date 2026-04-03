# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_173302

## Other Issues (35)

**01_full_journey_easystaff Step 1** (first_contact) — 0.41s
- Prompt: Help me find companies to reach out to
- Tools called: []
- missing:sign up: True
- missing:setup: True

**01_full_journey_easystaff Step 2** (auth) — 0.34s
- Prompt: Here's my token: mcp_xxx...
- Tools called: []
- missing:welcome: True
- missing:website: True
- missing:what do you: True

**01_full_journey_easystaff Step 3** (company_context) — 0.27s
- Prompt: Our company is EasyStaff, website easystaff.io. My name is Eleonora, I'm BDM
- Tools called: []
- missing:project: True
- missing:created: True
- missing:scraped: True

**01_full_journey_easystaff Step 5** (existing_campaigns) — 0.3s
- Prompt: Look for SmartLead campaigns with petr in the name — those are mine
- Tools called: []
- missing:campaigns: True
- missing:found: True
- missing:blacklist: True
- missing:contacts: True

**01_full_journey_easystaff Step 6** (gathering_multi_segment_multi_geo) — 0.44s
- Prompt: Two segments: 1) IT consulting, Miami 2) video production, London
- Tools called: []
- missing:2 segment: True
- missing:video: True
- missing:Miami: True
- missing:London: True

**01_full_journey_easystaff Step 9** (email_accounts) — 0.36s
- Prompt: Pick accounts with eleonora in the email from my existing campaigns
- Tools called: []
- missing:email account: True
- missing:which: True

**01_full_journey_easystaff Step 11** (reply_intelligence) — 2.97s
- Prompt: Which leads need follow-ups? And which replies are warm?
- Tools called: ['get_context']
- missing:interested: True

**03_add_more_targets Step 1** (add_targets) — 0.26s
- Prompt: I need more companies — get me 10 additional IT consulting firms in Miami
- Tools called: []
- missing_tool:tam_gather: called:[] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:companies: True
- missing:gathered: True

**04_edit_sequence Step 1** (review_sequence) — 0.33s
- Prompt: Let me see the email sequence
- Tools called: []
- missing:Email 1: True
- missing:subject: True
- missing:body: True

**04_edit_sequence Step 2** (edit_subject) — 0.32s
- Prompt: Edit step 1 subject: {{first_name}} — contractors abroad?
- Tools called: []
- missing_tool:edit_sequence_step: called:[] (acceptable: ['edit_sequence_step'])
- missing:updated: True
- missing:synced: True

**04_edit_sequence Step 3** (provide_feedback) — 0.48s
- Prompt: Emails are too stiff, relax the tone
- Tools called: []
- missing_tool:provide_feedback: called:[] (acceptable: ['provide_feedback'])
- missing:feedback: True
- missing:stored: True
- missing:future: True

**04_edit_sequence Step 4** (override_target) — 0.26s
- Prompt: Mark Arcee AI as target, they're relevant
- Tools called: []
- missing_tool:override_company_target: called:[] (acceptable: ['override_company_target'])
- missing:target: True
- missing:override: True

**05_activate_campaign Step 1** (review_before_activate) — 0.76s
- Prompt: Received the test email, all good. Any campaigns ready to launch?
- Tools called: []
- missing:campaign: True
- missing:DRAFT: True
- missing:pending: True

**05_activate_campaign Step 2** (activate) — 0.3s
- Prompt: Activate the IT consulting Miami campaign
- Tools called: []
- missing_tool:activate_campaign: called:[] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:ACTIVE: True
- missing:campaign: True
- missing:sending: True

**16_campaign_lifecycle Step 1** (email_account_selection) — 0.25s
- Prompt: Same email accounts as my petr campaigns — the eleonora ones
- Tools called: []
- missing_tool:list_email_accounts: called:[] (acceptable: ['list_email_accounts'])
- unexpected:error: True
- must_contain_any: ['eleonora', 'email account', 'found']

**16_campaign_lifecycle Step 2** (sequence_generation) — 0.3s
- Prompt: Create the outreach sequence
- Tools called: []
- missing_tool:god_generate_sequence: called:[] (acceptable: ['god_generate_sequence', 'get_context', 'god_score_campaigns'])
- missing:sequence: True
- missing:email: True
- missing:step: True

**16_campaign_lifecycle Step 3** (sequence_approval) — 0.29s
- Prompt: Looks good, approve the sequence
- Tools called: []
- missing_tool:god_approve_sequence: called:[] (acceptable: ['god_approve_sequence'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 0.29s
- Prompt: Push to SmartLead with those email accounts
- Tools called: []
- missing_tool:god_push_to_smartlead: called:[] (acceptable: ['god_push_to_smartlead'])
- missing:DRAFT: True
- missing:campaign: True
- missing:SmartLead: True
- missing:inbox: True
- unexpected:error: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 0.25s
- Prompt: Test email received, sequence looks great
- Tools called: []
- must_contain_any: ['activate', 'launch', 'ready']

**16_campaign_lifecycle Step 6** (campaign_activation) — 0.27s
- Prompt: Yes, activate the campaign
- Tools called: []
- missing_tool:activate_campaign: called:[] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- missing:activated: True
- missing:campaign: True
- unexpected:error: True

**17_getsales_flow Step 4** (flow_generation) — 0.34s
- Prompt: Generate the LinkedIn flow
- Tools called: []
- missing_tool:gs_generate_flow: called:[] (acceptable: ['gs_generate_flow'])
- missing:flow: True
- missing:LinkedIn: True
- missing:step: True

**17_getsales_flow Step 5** (flow_approval) — 0.31s
- Prompt: Looks good, approve the flow
- Tools called: []
- missing_tool:gs_approve_flow: called:[] (acceptable: ['gs_approve_flow'])

**17_getsales_flow Step 6** (push_to_getsales) — 0.37s
- Prompt: Push to GetSales
- Tools called: []
- missing_tool:gs_push_to_getsales: called:[] (acceptable: ['gs_push_to_getsales'])
- missing:GetSales: True
- missing:DRAFT: True
- missing:pushed: True

**18_session_continuity Step 1** (reconnect) — 0.29s
- Prompt: Show me my status
- Tools called: []
- missing_tool:get_context: called:[] (acceptable: ['get_context', 'list_projects', 'check_integrations', 'pipeline_status'])
- must_contain_any: ['project', 'pipeline', 'Welcome back']

**18_session_continuity Step 2** (verify_project_context) — 0.39s
- Prompt: What's in my pipeline?
- Tools called: []
- missing_tool:pipeline_status: called:[] (acceptable: ['pipeline_status', 'get_context'])
- must_contain_any: ['companies', 'pipeline', 'targets']

**19_reply_intelligence Step 1** (reply_summary) — 0.78s
- Prompt: Any warm replies?
- Tools called: []
- missing_tool:replies_summary: called:[] (acceptable: ['replies_summary', 'get_context', 'replies_list'])
- missing:_links: True
- must_contain_any: ['replies', 'warm', 'interested']

**19_reply_intelligence Step 2** (warm_leads_detail) — 0.5s
- Prompt: List the warm replies
- Tools called: []
- missing_tool:replies_list: called:[] (acceptable: ['replies_list', 'replies_summary', 'get_context'])
- must_contain_any: ['lead', 'reply', 'interested']

**19_reply_intelligence Step 3** (followups_needed) — 0.33s
- Prompt: Show me leads that need attention
- Tools called: []
- missing_tool:replies_followups: called:[] (acceptable: ['replies_followups', 'replies_list', 'replies_summary', 'get_context'])
- must_contain_any: ['follow', 'reply', 'need']

**19_reply_intelligence Step 4** (deep_link_to_crm) — 0.27s
- Prompt: Take me to the CRM for this lead
- Tools called: []
- missing_tool:replies_deep_link: called:[] (acceptable: ['replies_deep_link', 'get_context', 'query_contacts'])
- missing:crm: True
- missing:http: True

**19_reply_intelligence Step 5** (meeting_requests) — 0.36s
- Prompt: Any meeting requests?
- Tools called: []
- missing_tool:replies_list: called:[] (acceptable: ['replies_list', 'replies_summary', 'get_context'])

**20_apollo_credits_performance Step 1** (cost_estimation) — 0.42s
- Prompt: How many credits will I spend?
- Tools called: []
- missing_tool:estimate_cost: called:[] (acceptable: ['estimate_cost', 'get_context', 'suggest_apollo_filters'])
- must_contain_any: ['credit', 'cost', 'page']

**21_crm_verification Step 1** (crm_contacts_visible) — 0.25s
- Prompt: Show me my contacts in CRM
- Tools called: []
- missing_tool:query_contacts: called:[] (acceptable: ['query_contacts', 'get_context', 'crm_stats'])
- must_contain_any: ['contact', 'company', 'total']

**21_crm_verification Step 2** (filter_by_project) — 0.32s
- Prompt: Show me only EasyStaff-Global contacts
- Tools called: []
- missing:EasyStaff: True

**22_campaigns_page_monitoring Step 1** (campaigns_list) — 0.36s
- Prompt: List campaigns
- Tools called: []
- missing_tool:list_smartlead_campaigns: called:[] (acceptable: ['list_smartlead_campaigns', 'get_context', 'check_integrations'])
- must_contain_any: ['campaign', 'SmartLead', 'status']

**22_campaigns_page_monitoring Step 2** (toggle_monitoring_off) — 0.26s
- Prompt: Disable monitoring for the petr campaign
- Tools called: []
- must_contain_any: ['monitoring', 'disabled', 'stopped']

