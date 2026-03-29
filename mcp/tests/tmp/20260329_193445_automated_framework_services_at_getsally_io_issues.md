# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_193445

## MCP Server Issues (13)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**02_new_user_fashion Step 5** (full_pipeline) — 5.22s
- Prompt: Process the gathered companies
- Tools called: ['pipeline_status']
- missing_tool:tam_blacklist_check: called:['pipeline_status'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['pipeline_status'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['pipeline_status'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['pipeline_status'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['pipeline_status'] (acceptable: ['tam_analyze'])
- tool_error:pipeline_status: Run not found

**09_multi_source_csv_first Step 3** (source_selection) — 16.51s
- Prompt: I have a CSV with LATAM fashion companies. Here: /data/take-test-100.csv. Classify them as fashion b
- Tools called: ['tam_gather', 'tam_blacklist_check', 'tam_pre_filter', 'tam_scrape', 'tam_analyze']
- tool_error:tam_pre_filter: Run 226 is in phase 'awaiting_scope_ok', expected 'pre_filter'. Cannot skip phas
- tool_error:tam_scrape: Run 226 is in phase 'awaiting_scope_ok', expected 'scrape'. Cannot skip phases.
- tool_error:tam_analyze: Run 226 is in phase 'awaiting_scope_ok', expected 'analyze'. Cannot skip phases.

**09_multi_source_csv_first Step 4** (custom_prompt) — 4.19s
- Prompt: Here's my classification: VALID if fashion brand/clothing manufacturer in LATAM. NOT_VALID if market
- Tools called: ['tam_analyze']
- unexpected:error: True
- tool_error:tam_analyze: Run 226 is in phase 'awaiting_scope_ok', expected 'analyze'. Cannot skip phases.

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 6.71s
- Prompt: Check blacklist and approve
- Tools called: ['tam_blacklist_check', 'tam_approve_checkpoint']
- tool_error:tam_blacklist_check: Run 226 is in phase 'pre_filter', expected 'blacklist'. Cannot skip phases.

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 3.53s
- Prompt: Run blacklist check
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True
- tool_error:tam_blacklist_check: Run 226 is in phase 'pre_filter', expected 'blacklist'. Cannot skip phases.

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 5.81s
- Prompt: Custom pipeline: classify into fashion/textile/retail/other → filter out other → size segmentation
- Tools called: ['tam_analyze']
- tool_error:tam_analyze: Run 226 is in phase 'pre_filter', expected 'analyze'. Cannot skip phases.

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 3.58s
- Prompt: Perfect, analyze with these
- Tools called: ['tam_analyze']
- missing_tool:tam_re_analyze: called:['tam_analyze'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True
- tool_error:tam_analyze: Run 226 is in phase 'pre_filter', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 1** (add_regex_step) — 4.87s
- Prompt: Add a column that classifies companies by size: LARGE if 100+ employees, MEDIUM if 20-99, SMALL if u
- Tools called: ['tam_analyze']
- missing:added: True
- unexpected:AI: True
- unexpected:prompt: True
- tool_error:tam_analyze: Run 226 is in phase 'pre_filter', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 3** (remove_step) — 3.61s
- Prompt: Remove the size_segment column
- Tools called: ['edit_sequence_step']
- missing:removed: True
- tool_error:edit_sequence_step: Sequence not found

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 4.2s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_override']
- tool_error:refinement_override: Refinement run not found

**15_step_add_remove_iterations Step 5** (add_ai_step) — 4.78s
- Prompt: Classify brand vs manufacturer from website content
- Tools called: ['tam_analyze']
- tool_error:tam_analyze: Run 226 is in phase 'pre_filter', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 8** (verify_all_4_iterations) — 3.91s
- Prompt: Show me all iterations
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

**23_second_project_onsocial Step 6** (verify_isolation) — 3.87s
- Prompt: Run blacklist check for OnSocial UK and approve
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True
- tool_error:tam_blacklist_check: Run 226 is in phase 'pre_filter', expected 'blacklist'. Cannot skip phases.

## GPT Tool Selection Issues (13)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 6.7s
- Prompt: Find fashion brands in Italy, about 10 targets
- Tools called: ['list_projects']
- missing_tool:parse_gathering_intent: called:['list_projects'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**09_multi_source_csv_first Step 2** (project_selection) — 3.49s
- Prompt: I want to work on the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 5** (blacklist) — 3.51s
- Prompt: Check the blacklist for this project
- Tools called: ['list_projects']
- missing_tool:tam_blacklist_check: called:['list_projects'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['list_projects'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 3.77s
- Prompt: Run pre-filter, scrape websites, and classify
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 3.6s
- Prompt: Add to the existing one
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 3.19s
- Prompt: Scrape and analyze the new companies
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.48s
- Prompt: Add to the existing pipeline, don't create a new one
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 3.99s
- Prompt: Run the full pipeline
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**13_blacklist_isolation Step 3** (gather_for_project_b) — 3.5s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 6.56s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['list_projects', 'tam_list_sources']
- missing_tool:tam_gather: called:['list_projects', 'tam_list_sources'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:already: True

**23_second_project_onsocial Step 2** (switch_project) — 3.83s
- Prompt: Switch to the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 3.83s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 3.44s
- Prompt: Gather creator economy companies in the UK
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

## Other Issues (9)

**02_new_user_fashion Step 3** (no_campaigns_check) — 5.79s
- Prompt: We haven't set up any campaigns before
- Tools called: ['list_projects']
- missing:gather: True

**02_new_user_fashion Step 6** (email_accounts) — 4.31s
- Prompt: The email account is elnar@thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 3.42s
- Prompt: Here's another batch from Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBd
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 3.37s
- Prompt: Here's a Drive folder with more companies: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj_L
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**12_custom_prompt_chain Step 3** (review_results) — 3.84s
- Prompt: Breakdown please
- Tools called: ['get_context']
- missing:FASHION_BRAND: True
- missing:segment: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 3.55s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['list_projects']
- missing:215: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 3.55s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['list_projects']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 3.61s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 3.66s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_list_sources']
- must_contain_any: ['file path', 'upload', 'where is the file']

