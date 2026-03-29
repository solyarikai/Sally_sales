# Issues Found — qwe@qwe.qwe

**Source:** automated_framework | **Time:** 20260329_140609

### 00_qwe_test_framework_validation Step 1 (context_check)

- Prompt: Show my projects
- Tools called: ['list_projects']
- **missing_tool:get_context**: called:['list_projects']

### 00_qwe_test_framework_validation Step 2 (create_project)

- Prompt: Create a project called QWE-TestProject. My website is easystaff.io
- Tools called: []
- **missing_tool:create_project**: called:[]

### 00_qwe_test_framework_validation Step 4 (list_sources)

- Prompt: What data sources are available for gathering?
- Tools called: []
- **missing_tool:tam_list_sources**: called:[]
- **must_contain_any**: ['Apollo', 'CSV', 'Google']

### 00_qwe_test_framework_validation Step 5 (list_email_accounts)

- Prompt: Show me available email accounts for campaigns
- Tools called: []
- **missing_tool:list_email_accounts**: called:[]
- **must_contain_any**: ['email', 'account', 'available']

### 00_qwe_test_framework_validation Step 6 (reply_summary)

- Prompt: Reply status for my project?
- Tools called: []
- **missing_tool:replies_summary**: called:[]

### 00_qwe_test_framework_validation Step 7 (estimate_cost)

- Prompt: How much would it cost to find 50 IT consulting companies in Miami via Apollo?
- Tools called: []
- **missing_tool:estimate_cost**: called:[]
- **must_contain_any**: ['credit', 'cost', 'estimate']

