# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_134839

### 00_qwe_test_framework_validation Step 2 (create_project)

- Prompt: Set up project QWE-TestProject, website easystaff.io
- Tools called: ['list_projects']
- **missing_tool:create_project**: called:['list_projects']

### 00_qwe_test_framework_validation Step 3 (check_integrations)

- Prompt: Show my API keys
- Tools called: []
- **missing_tool:check_integrations**: called:[]
- **must_contain_any**: ['integration', 'connected', 'SmartLead']

### 00_qwe_test_framework_validation Step 4 (list_sources)

- Prompt: What sources can I use?
- Tools called: []
- **missing_tool:tam_list_sources**: called:[]
- **must_contain_any**: ['Apollo', 'CSV', 'Google']

### 00_qwe_test_framework_validation Step 5 (list_email_accounts)

- Prompt: List sending accounts
- Tools called: []
- **missing_tool:list_email_accounts**: called:[]
- **must_contain_any**: ['email', 'account', 'available']

### 00_qwe_test_framework_validation Step 6 (reply_summary)

- Prompt: Any warm replies?
- Tools called: []
- **missing_tool:replies_summary**: called:[]

### 00_qwe_test_framework_validation Step 7 (estimate_cost)

- Prompt: Estimate Apollo credits for 50 companies
- Tools called: []
- **missing_tool:estimate_cost**: called:[]
- **must_contain_any**: ['credit', 'cost', 'estimate']

