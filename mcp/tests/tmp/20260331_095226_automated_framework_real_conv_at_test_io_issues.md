# Issues Found — real_conv@test.io

**Source:** automated_framework | **Time:** 20260331_095226

## Other Issues (24)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.38s
- Prompt: Hi there
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.25s
- Prompt: Here is my token: mcp_641d6c46cbcef28fdcc35e9209a7f20e6343a2b5b167c3f168dfda74ba57f538
- Tools called: []
- missing_tool:login: called:[] (acceptable: ['login'])

**01_default_smartlead_flow Step 3** (1.4_keys_configured) — 0.77s
- Prompt: Keys are configured now
- Tools called: []
- missing_tool:check_integrations: called:[] (acceptable: ['check_integrations', 'get_context'])
- must_contain_any: ['ready', 'segment', 'launch']

**01_default_smartlead_flow Step 4** (1.5_segments_before_offer) — 0.73s
- Prompt: Two segments: IT consulting Miami, video production London
- Tools called: []
- must_contain_any: ['offer', 'website', 'what do you sell']

**01_default_smartlead_flow Step 5** (2.1_provide_website) — 0.27s
- Prompt: easystaff.io
- Tools called: []
- missing_tool:create_project: called:[] (acceptable: ['create_project', 'get_context'])
- must_contain_any: ['project', 'EasyStaff', 'created']

**01_default_smartlead_flow Step 6** (2.2_previous_campaigns) — 0.21s
- Prompt: Yes, campaigns with petr in the name were launched before
- Tools called: []
- missing_tool:import_smartlead_campaigns: called:[] (acceptable: ['import_smartlead_campaigns', 'list_smartlead_campaigns', 'get_context', 'set_campaign_rules'])
- must_contain_any: ['campaign', 'blacklist', 'contact']

**01_default_smartlead_flow Step 7** (3.1_filter_preview) — 0.3s
- Prompt: Find IT consulting companies in Miami
- Tools called: []
- missing_tool:tam_gather: called:[] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**01_default_smartlead_flow Step 8** (3.2_confirm_filters) — 0.3s
- Prompt: Looks good, start
- Tools called: []
- missing_tool:tam_gather: called:[] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['run_id', 'gathering', 'companies']

**01_default_smartlead_flow Step 9** (3.3_email_accounts) — 0.62s
- Prompt: Use Eleonora accounts from the petr campaigns for both
- Tools called: []
- missing_tool:list_email_accounts: called:[] (acceptable: ['list_email_accounts'])
- must_contain_any: ['eleonora', 'email', 'account']

**01_default_smartlead_flow Step 10** (4.1_run_blacklist) — 0.24s
- Prompt: Check blacklist
- Tools called: []
- missing_tool:tam_blacklist_check: called:[] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- must_contain_any: ['blacklist', 'gate', 'checked']

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 0.23s
- Prompt: Approved
- Tools called: []
- missing_tool:tam_approve_checkpoint: called:[] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- must_contain_any: ['approved', 'approved', 'pre-filter']

**01_default_smartlead_flow Step 11b** (4.2b_run_remaining_phases) — 0.22s
- Prompt: Continue the pipeline
- Tools called: []
- missing_tool:tam_pre_filter: called:[] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:[] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:[] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])
- must_contain_any: ['target', 'classified', 'analyzed']

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 0.36s
- Prompt: Pipeline status?
- Tools called: []
- missing_tool:pipeline_status: called:[] (acceptable: ['pipeline_status', 'get_context'])
- must_contain_any: ['target', 'classified', 'segment']

**01_default_smartlead_flow Step 13** (4.4_exploration) — 0.27s
- Prompt: Run exploration
- Tools called: []
- missing_tool:tam_explore: called:[] (acceptable: ['tam_explore'])
- must_contain_any: ['enrich', 'keyword', 'filter']

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 0.21s
- Prompt: Show the pipeline results
- Tools called: []
- missing_tool:pipeline_status: called:[] (acceptable: ['pipeline_status', 'get_context'])
- must_contain_any: ['iteration', 'target', 'filter']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_targets) — 0.22s
- Prompt: Remove software product companies, keep only consulting
- Tools called: []
- missing_tool:provide_feedback: called:[] (acceptable: ['provide_feedback', 'get_context'])
- must_contain_any: ['stored', 'feedback', 'target']

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 0.25s
- Prompt: How did the re-analysis go?
- Tools called: []
- missing_tool:pipeline_status: called:[] (acceptable: ['pipeline_status', 'get_context'])
- must_contain_any: ['iteration', 'target', 'improved']

**01_default_smartlead_flow Step 17** (7.6_scale) — 0.23s
- Prompt: Gather more
- Tools called: []
- missing_tool:tam_gather: called:[] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- must_contain_any: ['more', 'companies', 'page']

**01_default_smartlead_flow Step 18** (5.1_sequence_generation) — 0.33s
- Prompt: Generate the email sequence
- Tools called: []
- missing_tool:smartlead_generate_sequence: called:[] (acceptable: ['smartlead_generate_sequence', 'get_context', 'smartlead_score_campaigns'])
- must_contain_any: ['sequence', 'email', 'subject']

**01_default_smartlead_flow Step 18b** (5.1b_approve_sequence) — 0.35s
- Prompt: Sequence looks good, approve it
- Tools called: []
- missing_tool:smartlead_approve_sequence: called:[] (acceptable: ['smartlead_approve_sequence', 'get_context'])
- must_contain_any: ['approved', 'sequence', 'push']

**01_default_smartlead_flow Step 19** (5.2_push_campaign) — 0.22s
- Prompt: Push to SmartLead
- Tools called: []
- missing_tool:smartlead_push_campaign: called:[] (acceptable: ['smartlead_push_campaign', 'get_context', 'smartlead_generate_sequence'])
- must_contain_any: ['DRAFT', 'campaign', 'SmartLead']

**01_default_smartlead_flow Step 20** (5.3_activate) — 0.26s
- Prompt: Checked inbox, looks good. Activate the campaign.
- Tools called: []
- missing_tool:activate_campaign: called:[] (acceptable: ['activate_campaign', 'list_smartlead_campaigns', 'get_context'])
- must_contain_any: ['activated', 'launched', 'monitoring']

**01_default_smartlead_flow Step 21** (6.1_warm_replies) — 0.26s
- Prompt: Show warm replies and follow-ups
- Tools called: []
- missing_tool:replies_summary: called:[] (acceptable: ['replies_summary', 'get_context', 'replies_list', 'replies_followups'])
- must_contain_any: ['warm', 'reply', 'follow']

**01_default_smartlead_flow Step 22** (6.3_session_continuity) — 0.22s
- Prompt: What was I working on?
- Tools called: []
- missing_tool:get_context: called:[] (acceptable: ['get_context', 'list_projects', 'check_integrations', 'pipeline_status', 'list_smartlead_campaigns'])
- must_contain_any: ['EasyStaff', 'project', 'campaign']

