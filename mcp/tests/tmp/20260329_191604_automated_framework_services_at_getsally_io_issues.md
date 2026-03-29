# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_191604

## MCP Server Issues (17)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**09_multi_source_csv_first Step 4** (custom_prompt) — 4.09s
- Prompt: Use this prompt to classify: Companies that make fashion clothes in Latin America = VALID. Marketing
- Tools called: ['tam_analyze']
- unexpected:error: True
- tool_error:tam_analyze: Run not found

**09_multi_source_csv_first Step 5** (blacklist) — 4.76s
- Prompt: Run blacklist check and approve
- Tools called: ['tam_blacklist_check', 'tam_approve_checkpoint']
- missing:approved: True
- tool_error:tam_blacklist_check: Run not found
- tool_error:tam_approve_checkpoint: Gate not found

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 3.23s
- Prompt: Looks good, approve the targets
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**10_multi_source_sheet_add_to_existing Step 5** (checkpoint2_approval) — 2.72s
- Prompt: Approve targets
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 2.66s
- Prompt: Run blacklist check
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True
- tool_error:tam_blacklist_check: Run not found

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 4.84s
- Prompt: Scrape and analyze
- Tools called: ['tam_scrape', 'tam_analyze']
- missing_tool:tam_pre_filter: called:['tam_scrape', 'tam_analyze'] (acceptable: ['tam_pre_filter'])
- tool_error:tam_scrape: Run not found
- tool_error:tam_analyze: Run not found

**11_multi_source_drive_add_to_existing Step 5** (checkpoint2_approval) — 3.0s
- Prompt: Approve
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 3.34s
- Prompt: Re-analyze with custom prompts: First classify the industry (FASHION_BRAND, TEXTILE_PRODUCER, RETAIL
- Tools called: ['tam_re_analyze']
- missing:step: True
- missing:filter: True
- tool_error:tam_re_analyze: Run not found

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 2.82s
- Prompt: Perfect, analyze with these
- Tools called: ['tam_analyze']
- missing_tool:tam_re_analyze: called:['tam_analyze'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True
- tool_error:tam_analyze: Run not found

**12_custom_prompt_chain Step 3** (review_results) — 3.05s
- Prompt: How many in each segment?
- Tools called: ['replies_summary']
- missing:FASHION_BRAND: True
- tool_error:replies_summary: Project 'Project' not found

**12_custom_prompt_chain Step 4** (approve) — 2.62s
- Prompt: Approve targets
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**15_step_add_remove_iterations Step 2** (verify_iteration_1) — 3.61s
- Prompt: Show me the pipeline
- Tools called: ['pipeline_status']
- tool_error:pipeline_status: Run not found

**15_step_add_remove_iterations Step 3** (remove_step) — 3.82s
- Prompt: I don't need size_segment anymore, remove it
- Tools called: ['provide_feedback']
- missing:removed: True
- tool_error:provide_feedback: Project not found

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 3.35s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_override']
- tool_error:refinement_override: Refinement run not found

**15_step_add_remove_iterations Step 5** (add_ai_step) — 5.41s
- Prompt: Add business_model column: BRAND if they sell own brand, MANUFACTURER if they produce for others
- Tools called: ['provide_feedback']
- missing:classify: True
- missing:prompt: True
- tool_error:provide_feedback: Project not found

**15_step_add_remove_iterations Step 7** (remove_ai_step) — 5.02s
- Prompt: Actually remove business_model, I don't need it
- Tools called: ['provide_feedback']
- tool_error:provide_feedback: Project not found

**15_step_add_remove_iterations Step 8** (verify_all_4_iterations) — 3.3s
- Prompt: Show me all iterations
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

## GPT Tool Selection Issues (16)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 2** (project_setup) — 2.98s
- Prompt: I'm from The Fashion People (thefashionpeople.com), need to find fashion brands in Italy
- Tools called: ['list_projects']
- missing_tool:create_project: called:['list_projects'] (acceptable: ['create_project'])
- missing:created: True

**02_new_user_fashion Step 4** (gathering) — 2.78s
- Prompt: Find fashion brands in Italy, about 10 targets
- Tools called: ['list_projects']
- missing_tool:parse_gathering_intent: called:['list_projects'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**02_new_user_fashion Step 5** (full_pipeline) — 2.67s
- Prompt: Run the full pipeline — blacklist, scrape, analyze
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**02_new_user_fashion Step 7** (second_project) — 3.14s
- Prompt: I also need to find influencer platforms in UK for https://onsocial.ai/
- Tools called: ['list_projects']
- missing_tool:create_project: called:['list_projects'] (acceptable: ['create_project'])

**09_multi_source_csv_first Step 2** (project_selection) — 2.76s
- Prompt: Let's work on Result
- Tools called: ['get_context']
- missing_tool:select_project: called:['get_context'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 3** (source_selection) — 2.57s
- Prompt: Run pipeline on this CSV file /data/take-test-100.csv — looking for fashion and apparel brands in La
- Tools called: ['tam_list_sources']
- missing_tool:tam_gather: called:['tam_list_sources'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- unexpected:Apollo: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 2.62s
- Prompt: Process the pipeline — scrape and analyze
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 2.86s
- Prompt: Add to existing pipeline
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 2.55s
- Prompt: Blacklist check for the sheet import
- Tools called: ['tam_list_sources']
- missing_tool:tam_blacklist_check: called:['tam_list_sources'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['tam_list_sources'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 2.46s
- Prompt: Scrape and analyze the new companies
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.02s
- Prompt: Yep, same project, just add these files
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**13_blacklist_isolation Step 3** (gather_for_project_b) — 3.61s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**23_second_project_onsocial Step 2** (switch_project) — 3.66s
- Prompt: Switch to the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 3.41s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 7.94s
- Prompt: Gather creator economy companies in the UK
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**23_second_project_onsocial Step 6** (verify_isolation) — 3.49s
- Prompt: Blacklist check for this project
- Tools called: ['list_projects']
- missing_tool:tam_blacklist_check: called:['list_projects'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['list_projects'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

## Other Issues (11)

**02_new_user_fashion Step 3** (no_campaigns_check) — 2.89s
- Prompt: We haven't set up any campaigns before
- Tools called: ['list_projects']
- missing:gather: True

**02_new_user_fashion Step 6** (email_accounts) — 3.17s
- Prompt: The email account is elnar@thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 2.67s
- Prompt: Here's another batch from Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBd
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 2.52s
- Prompt: Also check this Drive folder with 3 CSV files: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7V
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**13_blacklist_isolation Step 1** (verify_project_a_state) — 2.96s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['list_projects']
- missing:215: True

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 6.89s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['list_projects', 'tam_gather']
- missing:duplicate: True
- missing:already: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 3.48s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['list_projects']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 3.47s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 3.21s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_list_sources']
- must_contain_any: ['file path', 'upload', 'where is the file']

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 3.43s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['check_integrations']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

**15_step_add_remove_iterations Step 1** (add_regex_step) — 3.26s
- Prompt: Classify companies by headcount into SMALL, MEDIUM, LARGE
- Tools called: ['tam_list_sources']
- missing:added: True
- unexpected:AI: True

