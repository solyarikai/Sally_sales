# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_212555

## Other Issues (3)

**00_qwe_test_framework_validation Step 5** (list_email_accounts) — 0.26s
- Prompt: List sending accounts
- Tools called: []
- missing_tool:list_email_accounts: called:[] (acceptable: ['list_email_accounts'])
- must_contain_any: ['email', 'account', 'available']

**00_qwe_test_framework_validation Step 6** (reply_summary) — 0.24s
- Prompt: Reply status for my project?
- Tools called: []
- missing_tool:replies_summary: called:[] (acceptable: ['replies_summary', 'get_context', 'replies_list'])
- must_contain_any: ['reply', 'replies', 'warm']

**00_qwe_test_framework_validation Step 7** (estimate_cost) — 0.25s
- Prompt: What is the cost estimate?
- Tools called: []
- missing_tool:estimate_cost: called:[] (acceptable: ['estimate_cost', 'get_context', 'suggest_apollo_filters'])
- must_contain_any: ['credit', 'cost', 'estimate']

