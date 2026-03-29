# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_220433

## MCP Server Issues (6)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 3.53s
- Prompt: Approve
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 6.81s
- Prompt: Scrape and analyze
- Tools called: ['tam_scrape', 'tam_analyze']
- missing_tool:tam_pre_filter: called:['tam_scrape', 'tam_analyze'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- tool_error:tam_scrape: Run 235 is in phase 'awaiting_scope_ok', expected 'scrape'. Cannot skip phases.
- tool_error:tam_analyze: Run 235 is in phase 'awaiting_scope_ok', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 1** (add_regex_step) — 9.18s
- Prompt: I want a size_segment column: large = 100+, medium = 20-99, small = <20 employees
- Tools called: ['tam_analyze']
- unexpected:AI: True
- unexpected:prompt: True
- tool_error:tam_analyze: Run 238 is in phase 'blacklist', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 3.87s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

**15_step_add_remove_iterations Step 5** (add_ai_step) — 5.42s
- Prompt: Classify brand vs manufacturer from website content
- Tools called: ['tam_analyze']
- tool_error:tam_analyze: Run 238 is in phase 'blacklist', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 8** (verify_all_4_iterations) — 4.01s
- Prompt: Show me all iterations
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

## GPT Tool Selection Issues (11)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 3.64s
- Prompt: Find fashion brands in Italy, about 10 targets
- Tools called: ['list_projects']
- missing_tool:parse_gathering_intent: called:['list_projects'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters', 'get_context'])
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**02_new_user_fashion Step 5** (full_pipeline) — 3.32s
- Prompt: Run blacklist and analysis
- Tools called: ['run_full_pipeline']
- missing_tool:tam_blacklist_check: called:['run_full_pipeline'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['run_full_pipeline'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])

**09_multi_source_csv_first Step 5** (blacklist) — 3.84s
- Prompt: Check the blacklist for this project
- Tools called: ['list_projects']
- missing_tool:tam_blacklist_check: called:['list_projects'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['list_projects'] (acceptable: ['tam_approve_checkpoint', 'get_context'])

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 4.03s
- Prompt: Now scrape and analyze all the companies
- Tools called: ['get_context']
- missing_words: found 0/3: ['targets', 'checkpoint', 'review']

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 3.85s
- Prompt: Add to the existing one
- Tools called: ['get_context']
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 3.69s
- Prompt: Run the pipeline on the new batch
- Tools called: ['get_context']
- missing_words: found 0/2: ['targets', 'checkpoint']

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 4.63s
- Prompt: Add to the existing pipeline, don't create a new one
- Tools called: ['get_context']
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 4.2s
- Prompt: Run blacklist check
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint', 'get_context'])

**13_blacklist_isolation Step 3** (gather_for_project_b) — 4.36s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 4.41s
- Prompt: Gather creator economy companies in the UK
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**23_second_project_onsocial Step 6** (verify_isolation) — 4.41s
- Prompt: Check blacklist and approve for OnSocial
- Tools called: ['list_projects']
- missing_tool:tam_blacklist_check: called:['list_projects'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['list_projects'] (acceptable: ['tam_approve_checkpoint', 'get_context'])

## Other Issues (9)

**02_new_user_fashion Step 3** (no_campaigns_check) — 4.23s
- Prompt: No existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing_words: found 0/2: ['gather', 'find']

**09_multi_source_csv_first Step 4** (custom_prompt) — 3.92s
- Prompt: My segmentation: look for companies that design and produce clothing, fashion accessories, or textil
- Tools called: ['list_projects']
- missing_words: found 0/2: ['prompt', 'classify']

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 4.1s
- Prompt: I have more leads in Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgm
- Tools called: ['tam_list_sources']
- missing_words: found 0/3: ['existing', 'pipeline', 'new']
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 5.13s
- Prompt: Last batch — files in this folder: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj_LATAM_bat
- Tools called: ['tam_gather']
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 8.23s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['list_projects', 'tam_gather']
- missing_words: found 0/2: ['duplicate', 'already']

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 7.27s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['list_projects']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 3.54s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_list_sources']
- must_contain_any: ['file path', 'upload', 'where is the file']

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 3.68s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['check_integrations']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

**15_step_add_remove_iterations Step 3** (remove_step) — 4.38s
- Prompt: Delete the size classification
- Tools called: ['provide_feedback']
- missing_words: found 0/2: ['removed', 'size_segment']

