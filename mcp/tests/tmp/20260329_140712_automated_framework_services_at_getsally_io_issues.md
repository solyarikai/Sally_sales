# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_140712

### 02_new_user_fashion Step 3 (no_campaigns_check)

- Prompt: I don't have any SmartLead campaigns yet
- Tools called: []
- **missing:gather**: True
- **missing:find**: True

### 02_new_user_fashion Step 4 (gathering)

- Prompt: Search for Italian fashion companies
- Tools called: []
- **missing_tool:parse_gathering_intent**: called:[]
- **missing_tool:tam_gather**: called:[]

### 02_new_user_fashion Step 6 (email_accounts)

- Prompt: Send from elnar@thefashionpeopletech.com
- Tools called: []
- **missing:email account**: True
- **missing:which**: True

### 02_new_user_fashion Step 7 (second_project)

- Prompt: New project for onsocial.ai — looking for influencer marketing platforms in the UK
- Tools called: []
- **missing_tool:create_project**: called:[]

### 09_multi_source_csv_first Step 1 (login)

- Prompt: Here's my token: mcp_services_test_token
- Tools called: []
- **missing_tool:login**: called:[]

### 09_multi_source_csv_first Step 2 (project_selection)

- Prompt: Let's work on Result
- Tools called: []
- **missing_tool:select_project**: called:[]
- **missing:Result**: True
- **missing:project**: True

### 09_multi_source_csv_first Step 3 (source_selection)

- Prompt: I have a CSV with LATAM fashion companies. Here: /data/take-test-100.csv. Classify them as fashion b
- Tools called: []
- **missing_tool:tam_gather**: called:[]
- **missing:CSV**: True
- **missing:companies**: True
- **missing:gathered**: True

### 09_multi_source_csv_first Step 4 (custom_prompt)

- Prompt: My segmentation: look for companies that design and produce clothing, fashion accessories, or textil
- Tools called: []
- **missing:prompt**: True
- **missing:classify**: True
- **unexpected:error**: True

### 09_multi_source_csv_first Step 7 (checkpoint2_approval)

- Prompt: Target list looks fine, proceed
- Tools called: []
- **missing_tool:tam_approve_checkpoint**: called:[]

### 10_multi_source_sheet_add_to_existing Step 1 (source_addition)

- Prompt: Here's another batch from Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBd
- Tools called: []
- **missing:existing**: True
- **missing:pipeline**: True
- **missing:new**: True
- **must_contain_any**: ['add to existing', 'create a new pipeline', 'existing run']

### 10_multi_source_sheet_add_to_existing Step 2 (user_chooses_existing)

- Prompt: Add to existing pipeline
- Tools called: []
- **missing_tool:tam_gather**: called:[]
- **missing:companies**: True
- **missing:gathered**: True
- **must_contain_any**: ['70 new', '40 duplicate', '40 already']

### 10_multi_source_sheet_add_to_existing Step 5 (checkpoint2_approval)

- Prompt: Approve targets
- Tools called: []
- **missing_tool:tam_approve_checkpoint**: called:[]

### 11_multi_source_drive_add_to_existing Step 1 (source_addition)

- Prompt: Also check this Drive folder with 3 CSV files: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7V
- Tools called: []
- **missing:existing**: True
- **missing:pipeline**: True
- **must_contain_any**: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

### 11_multi_source_drive_add_to_existing Step 2 (user_chooses_existing)

- Prompt: Add to the existing pipeline, don't create a new one
- Tools called: []
- **missing_tool:tam_gather**: called:[]
- **missing:companies**: True
- **missing:gathered**: True
- **must_contain_any**: ['35 new', '70 duplicate', '70 already']

### 11_multi_source_drive_add_to_existing Step 5 (checkpoint2_approval)

- Prompt: Approve
- Tools called: []
- **missing_tool:tam_approve_checkpoint**: called:[]

### 12_custom_prompt_chain Step 1 (user_provides_custom_prompt)

- Prompt: Re-analyze with custom prompts: First classify the industry (FASHION_BRAND, TEXTILE_PRODUCER, RETAIL
- Tools called: []
- **missing:step**: True
- **missing:classify**: True
- **missing:filter**: True

### 12_custom_prompt_chain Step 2 (user_approves_prompts)

- Prompt: Run the classification
- Tools called: []
- **missing_tool:tam_re_analyze**: called:[]
- **missing:targets**: True
- **missing:classified**: True
- **missing:segments**: True

### 12_custom_prompt_chain Step 3 (review_results)

- Prompt: What's the distribution?
- Tools called: []
- **missing:FASHION_BRAND**: True
- **missing:segment**: True

### 12_custom_prompt_chain Step 4 (approve)

- Prompt: Approve targets
- Tools called: []
- **missing_tool:tam_approve_checkpoint**: called:[]

### 13_blacklist_isolation Step 1 (verify_project_a_state)

- Prompt: How many companies do we have in the Result project?
- Tools called: []
- **missing:215**: True
- **missing:Result**: True

### 13_blacklist_isolation Step 2 (create_project_b)

- Prompt: Create a new project called TestProjectB targeting IT consulting in London
- Tools called: []
- **missing_tool:create_project**: called:[]

### 13_blacklist_isolation Step 3 (gather_for_project_b)

- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: []
- **missing_tool:tam_gather**: called:[]

### 13_blacklist_isolation Step 5 (verify_same_project_dedup)

- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['login']
- **missing_tool:tam_gather**: called:['login']
- **missing:duplicate**: True
- **missing:already**: True

### 14_source_suggestion_edge_cases Step 1 (no_source_no_key)

- Prompt: Gather fashion companies in Argentina
- Tools called: []
- **must_contain_any**: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

### 14_source_suggestion_edge_cases Step 2 (no_source_has_key)

- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: []
- **missing:Apollo**: True
- **missing:credits**: True

### 14_source_suggestion_edge_cases Step 3 (ambiguous_with_csv_mention)

- Prompt: I have a CSV file with my leads
- Tools called: []
- **must_contain_any**: ['file path', 'upload', 'where is the file']

### 14_source_suggestion_edge_cases Step 4 (google_doc_not_sheet)

- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: []
- **must_contain_any**: ['Google Doc', 'spreadsheet', 'CSV']

### 14_source_suggestion_edge_cases Step 5 (multiple_sources_in_one_message)

- Prompt: I have /data/batch1.csv and also this sheet: https://docs.google.com/spreadsheets/d/abc123/edit
- Tools called: []
- **missing:CSV**: True
- **missing:Sheet**: True

### 14_source_suggestion_edge_cases Step 6 (vague_request)

- Prompt: Hey, I need some data
- Tools called: []
- **must_contain_any**: ['What', 'which', 'CSV']

### 15_step_add_remove_iterations Step 1 (add_regex_step)

- Prompt: Classify companies by headcount into SMALL, MEDIUM, LARGE
- Tools called: []
- **missing:size**: True
- **missing:column**: True
- **missing:added**: True
- **unexpected:AI**: True

### 15_step_add_remove_iterations Step 3 (remove_step)

- Prompt: I don't need size_segment anymore, remove it
- Tools called: []
- **missing:removed**: True
- **missing:size_segment**: True

### 15_step_add_remove_iterations Step 5 (add_ai_step)

- Prompt: Add a column that classifies whether each company is a fashion BRAND (designs own clothes) or a MANU
- Tools called: []
- **missing:BRAND**: True
- **missing:MANUFACTURER**: True
- **missing:classify**: True
- **missing:prompt**: True

### 23_second_project_onsocial Step 1 (create_second_project)

- Prompt: New project: OnSocial UK, site onsocial.com, UK influencer/creator platforms
- Tools called: []
- **missing_tool:create_project**: called:[]
- **missing:OnSocial**: True
- **missing:project**: True
- **missing:created**: True

### 23_second_project_onsocial Step 2 (switch_project)

- Prompt: Switch to the Result project
- Tools called: []
- **missing_tool:select_project**: called:[]
- **missing:Result**: True

### 23_second_project_onsocial Step 3 (verify_result_data)

- Prompt: How many companies in Result?
- Tools called: []
- **must_contain_any**: ['215', 'companies']

### 23_second_project_onsocial Step 4 (switch_to_onsocial)

- Prompt: Switch to OnSocial UK
- Tools called: []
- **missing_tool:select_project**: called:[]

### 23_second_project_onsocial Step 5 (gather_for_onsocial)

- Prompt: Gather creator economy companies in the UK
- Tools called: []
- **missing_tool:tam_gather**: called:[]
- **missing:companies**: True
- **missing:gathered**: True

