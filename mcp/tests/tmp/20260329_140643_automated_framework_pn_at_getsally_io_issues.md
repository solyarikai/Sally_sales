# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260329_140643

### 01_full_journey_easystaff Step 1 (first_contact)

- Prompt: Hi, I need to start gathering leads for outreach
- Tools called: []
- **missing:sign up**: True
- **missing:setup**: True

### 01_full_journey_easystaff Step 2 (auth)

- Prompt: Here's my token: mcp_xxx...
- Tools called: []
- **missing:welcome**: True
- **missing:website**: True
- **missing:what do you**: True

### 01_full_journey_easystaff Step 3 (company_context)

- Prompt: Check out easystaff.io — that's us. I'm Eleonora
- Tools called: []
- **missing:project**: True
- **missing:created**: True
- **missing:scraped**: True

### 01_full_journey_easystaff Step 5 (existing_campaigns)

- Prompt: All campaigns including 'petr' in their names are my campaigns
- Tools called: []
- **missing:campaigns**: True
- **missing:found**: True
- **missing:blacklist**: True
- **missing:contacts**: True

### 01_full_journey_easystaff Step 6 (gathering_multi_segment_multi_geo)

- Prompt: I need IT consulting firms in Miami, and also video production companies in London UK
- Tools called: []
- **missing:2 segment**: True
- **missing:video**: True
- **missing:Miami**: True
- **missing:London**: True

### 01_full_journey_easystaff Step 9 (email_accounts)

- Prompt: Use all email accounts from my petr campaigns that have Eleonora in the name
- Tools called: []
- **missing:email account**: True
- **missing:which**: True

### 01_full_journey_easystaff Step 11 (reply_intelligence)

- Prompt: Any warm leads? Who should I reply to?
- Tools called: []
- **missing:warm**: True
- **missing:follow-up**: True
- **missing:interested**: True

### 03_add_more_targets Step 1 (add_targets)

- Prompt: Add 10 more IT consulting targets to the pipeline
- Tools called: []
- **missing_tool:tam_gather**: called:[]
- **missing:companies**: True
- **missing:gathered**: True

### 04_edit_sequence Step 1 (review_sequence)

- Prompt: Show me the sequence for the IT consulting campaign
- Tools called: []
- **missing:Email 1**: True
- **missing:subject**: True
- **missing:body**: True

### 04_edit_sequence Step 2 (edit_subject)

- Prompt: Change email 1 subject to: {{first_name}} — contractors abroad?
- Tools called: []
- **missing_tool:edit_sequence_step**: called:[]
- **missing:updated**: True
- **missing:synced**: True

### 04_edit_sequence Step 3 (provide_feedback)

- Prompt: The tone is too formal, make it more casual and friendly
- Tools called: []
- **missing_tool:provide_feedback**: called:[]
- **missing:feedback**: True
- **missing:stored**: True
- **missing:future**: True

### 04_edit_sequence Step 4 (override_target)

- Prompt: Override Arcee AI — it IS a target
- Tools called: []
- **missing_tool:override_company_target**: called:[]
- **missing:target**: True
- **missing:override**: True

### 05_activate_campaign Step 1 (review_before_activate)

- Prompt: I checked the test email, looks good. What campaigns are pending?
- Tools called: []
- **missing:campaign**: True
- **missing:DRAFT**: True
- **missing:pending**: True

### 05_activate_campaign Step 2 (activate)

- Prompt: Activate the IT consulting Miami campaign
- Tools called: []
- **missing_tool:activate_campaign**: called:[]
- **missing:ACTIVE**: True
- **missing:campaign**: True
- **missing:sending**: True

### 16_campaign_lifecycle Step 1 (email_account_selection)

- Prompt: For email accounts, use eleonora's accounts from the campaigns with petr in name
- Tools called: []
- **missing_tool:list_email_accounts**: called:[]
- **unexpected:error**: True
- **must_contain_any**: ['eleonora', 'email account', 'found']

### 16_campaign_lifecycle Step 2 (sequence_generation)

- Prompt: Create the outreach sequence
- Tools called: []
- **missing_tool:god_generate_sequence**: called:[]
- **missing:sequence**: True
- **missing:email**: True
- **missing:step**: True

### 16_campaign_lifecycle Step 3 (sequence_approval)

- Prompt: Looks good, approve the sequence
- Tools called: []
- **missing_tool:god_approve_sequence**: called:[]
- **unexpected:error**: True
- **must_contain_any**: ['approved', 'ready']

### 16_campaign_lifecycle Step 4 (smartlead_push)

- Prompt: Create the SmartLead campaign
- Tools called: []
- **missing_tool:god_push_to_smartlead**: called:[]
- **missing:DRAFT**: True
- **missing:campaign**: True
- **missing:SmartLead**: True
- **missing:inbox**: True
- **unexpected:error**: True

### 16_campaign_lifecycle Step 5 (test_email_verification)

- Prompt: Got it, the test email is fine
- Tools called: []
- **must_contain_any**: ['activate', 'launch', 'ready']

### 16_campaign_lifecycle Step 6 (campaign_activation)

- Prompt: Yes, activate the campaign
- Tools called: ['login']
- **missing_tool:activate_campaign**: called:['login']
- **missing:activated**: True

### 17_getsales_flow Step 1 (destination_clarification)

- Prompt: Launch outreach for the targets we found
- Tools called: []
- **must_contain_any**: ['SmartLead', 'GetSales', 'destination']

### 17_getsales_flow Step 4 (flow_generation)

- Prompt: Generate the LinkedIn flow
- Tools called: []
- **missing_tool:gs_generate_flow**: called:[]
- **missing:flow**: True
- **missing:LinkedIn**: True
- **missing:step**: True

### 17_getsales_flow Step 5 (flow_approval)

- Prompt: Looks good, approve the flow
- Tools called: []
- **missing_tool:gs_approve_flow**: called:[]

### 17_getsales_flow Step 6 (push_to_getsales)

- Prompt: Push to GetSales
- Tools called: []
- **missing_tool:gs_push_to_getsales**: called:[]
- **missing:GetSales**: True
- **missing:DRAFT**: True
- **missing:pushed**: True

### 18_session_continuity Step 1 (reconnect)

- Prompt: Continue where I left off
- Tools called: []
- **missing_tool:get_context**: called:[]
- **must_contain_any**: ['project', 'pipeline', 'Welcome back']

### 18_session_continuity Step 2 (verify_project_context)

- Prompt: Show pipeline status
- Tools called: []
- **missing_tool:pipeline_status**: called:[]
- **must_contain_any**: ['companies', 'pipeline', 'targets']

### 19_reply_intelligence Step 1 (reply_summary)

- Prompt: Any warm replies?
- Tools called: []
- **missing_tool:replies_summary**: called:[]
- **missing:_links**: True
- **must_contain_any**: ['replies', 'warm', 'interested']

### 19_reply_intelligence Step 2 (warm_leads_detail)

- Prompt: Which leads are interested?
- Tools called: []
- **missing_tool:replies_list**: called:[]
- **must_contain_any**: ['lead', 'reply', 'interested']

### 19_reply_intelligence Step 3 (followups_needed)

- Prompt: Which leads need follow-ups?
- Tools called: []
- **missing_tool:replies_followups**: called:[]
- **must_contain_any**: ['follow', 'reply', 'need']

### 19_reply_intelligence Step 4 (deep_link_to_crm)

- Prompt: Open this lead in CRM
- Tools called: []
- **missing_tool:replies_deep_link**: called:[]
- **missing:crm**: True
- **missing:http**: True

### 19_reply_intelligence Step 5 (meeting_requests)

- Prompt: Any meeting requests?
- Tools called: []
- **missing_tool:replies_list**: called:[]

### 20_apollo_credits_performance Step 1 (cost_estimation)

- Prompt: What's the Apollo cost for 50 targets?
- Tools called: []
- **missing_tool:estimate_cost**: called:[]
- **must_contain_any**: ['credit', 'cost', 'page']

### 20_apollo_credits_performance Step 2 (credit_spending_history)

- Prompt: Apollo spending this month?
- Tools called: []
- **must_contain_any**: ['credit', 'spent', 'usage']

### 21_crm_verification Step 1 (crm_contacts_visible)

- Prompt: Open CRM
- Tools called: []
- **missing_tool:query_contacts**: called:[]
- **must_contain_any**: ['contact', 'company', 'total']

### 21_crm_verification Step 2 (filter_by_project)

- Prompt: Show me only EasyStaff-Global contacts
- Tools called: []
- **missing:EasyStaff**: True

### 22_campaigns_page_monitoring Step 1 (campaigns_list)

- Prompt: What campaigns do I have?
- Tools called: []
- **missing_tool:list_smartlead_campaigns**: called:[]
- **must_contain_any**: ['campaign', 'SmartLead', 'status']

### 22_campaigns_page_monitoring Step 2 (toggle_monitoring_off)

- Prompt: Disable monitoring for the petr campaign
- Tools called: []
- **must_contain_any**: ['monitoring', 'disabled', 'stopped']

