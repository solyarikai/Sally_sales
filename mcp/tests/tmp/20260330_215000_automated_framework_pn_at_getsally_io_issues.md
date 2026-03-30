# Issues Found — pn@getsally.io

**Source:** automated_framework | **Time:** 20260330_215000

## GPT Tool Selection Issues (1)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**16_campaign_lifecycle Step 1** (email_account_selection) — 4.7s
- Prompt: Use the eleonora email accounts from the petr campaigns
- Tools called: ['list_smartlead_campaigns']
- missing_tool:list_email_accounts: called:['list_smartlead_campaigns'] (acceptable: ['list_email_accounts'])

## Other Issues (3)

**16_campaign_lifecycle Step 3** (sequence_approval) — 90.85s
- Prompt: Looks good, approve the sequence
- Tools called: []
- missing_tool:smartlead_approve_sequence: called:[] (acceptable: ['smartlead_approve_sequence', 'get_context'])
- unexpected:error: True
- must_contain_any: ['approved', 'ready']

**16_campaign_lifecycle Step 4** (smartlead_push) — 90.93s
- Prompt: Let's create the campaign in SmartLead
- Tools called: []
- missing_tool:smartlead_push_campaign: called:[] (acceptable: ['smartlead_push_campaign', 'get_context', 'smartlead_generate_sequence'])
- missing_words: found 0/4: ['DRAFT', 'campaign', 'SmartLead']
- unexpected:error: True

**16_campaign_lifecycle Step 5** (test_email_verification) — 4.59s
- Prompt: Test email received, sequence looks great
- Tools called: ['smartlead_approve_sequence']
- must_contain_any: ['activate', 'launch', 'ready']

