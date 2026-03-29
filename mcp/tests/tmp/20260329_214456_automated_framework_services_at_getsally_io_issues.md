# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_214456

## MCP Server Issues (11)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**02_new_user_fashion Step 5** (full_pipeline) — 3.49s
- Prompt: Process the gathered companies
- Tools called: ['pipeline_status']
- missing_tool:tam_blacklist_check: called:['pipeline_status'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['pipeline_status'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['pipeline_status'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['pipeline_status'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['pipeline_status'] (acceptable: ['tam_analyze'])
- tool_error:pipeline_status: Run not found

**09_multi_source_csv_first Step 4** (custom_prompt) — 3.8s
- Prompt: Here's my classification: VALID if fashion brand/clothing manufacturer in LATAM. NOT_VALID if market
- Tools called: ['tam_analyze']
- unexpected:error: True
- tool_error:tam_analyze: Run not found

**09_multi_source_csv_first Step 5** (blacklist) — 3.59s
- Prompt: Blacklist check please
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True
- tool_error:tam_blacklist_check: Run not found

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 3.65s
- Prompt: Looks good, approve the targets
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 3.86s
- Prompt: Blacklist check please
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True
- tool_error:tam_blacklist_check: Run 227 is in phase 'pre_filter', expected 'blacklist'. Cannot skip phases.

**15_step_add_remove_iterations Step 1** (add_regex_step) — 5.56s
- Prompt: Add a column that classifies companies by size: LARGE if 100+ employees, MEDIUM if 20-99, SMALL if u
- Tools called: ['tam_analyze']
- missing:added: True
- unexpected:AI: True
- unexpected:prompt: True
- tool_error:tam_analyze: Run 227 is in phase 'prepare_verification', expected 'analyze'. Cannot skip phas

**15_step_add_remove_iterations Step 3** (remove_step) — 4.32s
- Prompt: Drop the size column
- Tools called: ['edit_sequence_step']
- missing:removed: True
- missing:size_segment: True
- tool_error:edit_sequence_step: Sequence not found

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 3.7s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_override']
- tool_error:refinement_override: Refinement run not found

**15_step_add_remove_iterations Step 5** (add_ai_step) — 4.69s
- Prompt: Classify brand vs manufacturer from website content
- Tools called: ['tam_analyze']
- tool_error:tam_analyze: Run 227 is in phase 'prepare_verification', expected 'analyze'. Cannot skip phas

**15_step_add_remove_iterations Step 8** (verify_all_4_iterations) — 4.42s
- Prompt: Show me all iterations
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 4.95s
- Prompt: Search for UK influencer platforms
- Tools called: ['tam_gather']
- missing:gathered: True
- tool_error:tam_gather: missing_essential_filters

## GPT Tool Selection Issues (14)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 4.56s
- Prompt: Find fashion brands in Italy, about 10 targets
- Tools called: ['list_projects']
- missing_tool:parse_gathering_intent: called:['list_projects'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**09_multi_source_csv_first Step 2** (project_selection) — 3.43s
- Prompt: Let's work on Result
- Tools called: ['get_context']
- missing_tool:select_project: called:['get_context'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 3** (source_selection) — 4.06s
- Prompt: Run pipeline on this CSV file /data/take-test-100.csv — looking for fashion and apparel brands in La
- Tools called: ['tam_list_sources']
- missing_tool:tam_gather: called:['tam_list_sources'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- unexpected:Apollo: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 3.4s
- Prompt: Now scrape and analyze all the companies
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 4.9s
- Prompt: Run blacklist check on the new companies
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 3.41s
- Prompt: Scrape and analyze the new companies
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.86s
- Prompt: Add to existing one
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 4.22s
- Prompt: Run the full pipeline
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 3.52s
- Prompt: Run the classification
- Tools called: ['run_full_pipeline']
- missing_tool:tam_re_analyze: called:['run_full_pipeline'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True

**13_blacklist_isolation Step 3** (gather_for_project_b) — 4.05s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 5.04s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['import_smartlead_campaigns']
- missing_tool:tam_gather: called:['import_smartlead_campaigns'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:duplicate: True
- missing:already: True

**23_second_project_onsocial Step 2** (switch_project) — 3.94s
- Prompt: Switch to the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 5.05s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 6** (verify_isolation) — 3.61s
- Prompt: Blacklist check for this project
- Tools called: ['list_projects']
- missing_tool:tam_blacklist_check: called:['list_projects'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['list_projects'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

## Other Issues (12)

**02_new_user_fashion Step 3** (no_campaigns_check) — 4.88s
- Prompt: No existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:gather: True
- missing:find: True

**02_new_user_fashion Step 6** (email_accounts) — 5.24s
- Prompt: Send from elnar@thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 3.52s
- Prompt: I have more leads in Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgm
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 5.47s
- Prompt: Use the existing run, add the sheet data there
- Tools called: ['tam_gather']
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 3.31s
- Prompt: Also check this Drive folder with 3 CSV files: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7V
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 4.2s
- Prompt: Re-analyze with custom prompts: First classify the industry (FASHION_BRAND, TEXTILE_PRODUCER, RETAIL
- Tools called: ['tam_re_analyze']
- missing:step: True
- missing:filter: True

**12_custom_prompt_chain Step 3** (review_results) — 4.6s
- Prompt: How many in each segment?
- Tools called: ['crm_stats']
- missing:FASHION_BRAND: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 4.5s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['list_projects']
- missing:215: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 4.13s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['list_projects']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 5.0s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 3.34s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_list_sources']
- must_contain_any: ['file path', 'upload', 'where is the file']

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 4.14s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['check_integrations']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

