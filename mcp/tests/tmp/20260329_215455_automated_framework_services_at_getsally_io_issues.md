# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_215455

## MCP Server Issues (7)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**09_multi_source_csv_first Step 4** (custom_prompt) — 3.86s
- Prompt: Classify with: fashion/apparel brands in LATAM = target. Non-fashion companies = reject.
- Tools called: ['tam_analyze']
- unexpected:error: True
- tool_error:tam_analyze: Run not found

**09_multi_source_csv_first Step 5** (blacklist) — 7.25s
- Prompt: Run blacklist check and approve
- Tools called: ['tam_blacklist_check', 'tam_approve_checkpoint']
- missing:approved: True
- tool_error:tam_blacklist_check: Run not found
- tool_error:tam_approve_checkpoint: Gate not found

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 3.84s
- Prompt: Approve
- Tools called: ['tam_approve_checkpoint']
- tool_error:tam_approve_checkpoint: Gate not found

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 3.66s
- Prompt: Pre-filter, scrape, analyze
- Tools called: ['tam_pre_filter']
- missing_tool:tam_scrape: called:['tam_pre_filter'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['tam_pre_filter'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])
- tool_error:tam_pre_filter: Run 233 is in phase 'blacklist', expected 'pre_filter'. Cannot skip phases.

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 5.52s
- Prompt: I need multi-step classification: 1) Segment by business type (fashion brand, textile producer, reta
- Tools called: ['tam_analyze']
- tool_error:tam_analyze: Run 233 is in phase 'blacklist', expected 'analyze'. Cannot skip phases.

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 3.88s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

**15_step_add_remove_iterations Step 8** (verify_all_4_iterations) — 3.37s
- Prompt: Show me all iterations
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

## GPT Tool Selection Issues (14)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 4.47s
- Prompt: Search for Italian fashion companies
- Tools called: ['tam_list_sources']
- missing_tool:parse_gathering_intent: called:['tam_list_sources'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters', 'get_context'])
- missing_tool:tam_gather: called:['tam_list_sources'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**02_new_user_fashion Step 5** (full_pipeline) — 3.67s
- Prompt: Run blacklist and analysis
- Tools called: ['run_full_pipeline']
- missing_tool:tam_blacklist_check: called:['run_full_pipeline'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['run_full_pipeline'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])

**02_new_user_fashion Step 7** (second_project) — 4.5s
- Prompt: I also need to find influencer platforms in UK for https://onsocial.ai/
- Tools called: ['list_projects']
- missing_tool:create_project: called:['list_projects'] (acceptable: ['create_project', 'get_context'])

**09_multi_source_csv_first Step 3** (source_selection) — 3.67s
- Prompt: Run pipeline on this CSV file /data/take-test-100.csv — looking for fashion and apparel brands in La
- Tools called: ['tam_list_sources']
- missing_tool:tam_gather: called:['tam_list_sources'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- missing:gathered: True
- unexpected:Apollo: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 3.41s
- Prompt: Run pre-filter, scrape websites, and classify
- Tools called: ['run_full_pipeline']
- missing_tool:tam_pre_filter: called:['run_full_pipeline'] (acceptable: ['tam_pre_filter', 'get_context', 'pipeline_status'])
- missing_tool:tam_scrape: called:['run_full_pipeline'] (acceptable: ['tam_scrape', 'get_context', 'pipeline_status'])
- missing_tool:tam_analyze: called:['run_full_pipeline'] (acceptable: ['tam_analyze', 'get_context', 'pipeline_status'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 3.88s
- Prompt: Run blacklist check on the new companies
- Tools called: ['tam_blacklist_check']
- missing_tool:tam_approve_checkpoint: called:['tam_blacklist_check'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 3.7s
- Prompt: Run the pipeline on the new batch
- Tools called: ['get_context']
- missing:targets: True

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.71s
- Prompt: Add to the existing pipeline, don't create a new one
- Tools called: ['get_context']
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 3.58s
- Prompt: Check blacklist for the drive import
- Tools called: ['tam_list_sources']
- missing_tool:tam_blacklist_check: called:['tam_list_sources'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['tam_list_sources'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing:approved: True

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 3.56s
- Prompt: Go ahead with those prompts
- Tools called: ['get_context']
- missing:targets: True
- missing:classified: True
- missing:segments: True

**13_blacklist_isolation Step 3** (gather_for_project_b) — 4.07s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 5.73s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['import_smartlead_campaigns']
- missing_tool:tam_gather: called:['import_smartlead_campaigns'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- missing:duplicate: True
- missing:already: True

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 4.15s
- Prompt: Gather creator economy companies in the UK
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters', 'get_context'])
- missing:gathered: True

**23_second_project_onsocial Step 6** (verify_isolation) — 3.89s
- Prompt: Run blacklist check for OnSocial UK and approve
- Tools called: ['blacklist_check']
- missing_tool:tam_blacklist_check: called:['blacklist_check'] (acceptable: ['tam_blacklist_check', 'get_context', 'pipeline_status'])
- missing_tool:tam_approve_checkpoint: called:['blacklist_check'] (acceptable: ['tam_approve_checkpoint', 'get_context'])
- missing:approved: True

## Other Issues (13)

**02_new_user_fashion Step 3** (no_campaigns_check) — 4.25s
- Prompt: No existing campaigns
- Tools called: ['list_smartlead_campaigns']
- missing:gather: True
- missing:find: True

**02_new_user_fashion Step 6** (email_accounts) — 3.84s
- Prompt: Use elnar at thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 3.31s
- Prompt: I have more leads in Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgm
- Tools called: ['tam_list_sources']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 4.57s
- Prompt: Use the existing run, add the sheet data there
- Tools called: ['tam_gather']
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 4.15s
- Prompt: I've got more files on Drive: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj_LATAM_batches
- Tools called: ['tam_gather']
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**12_custom_prompt_chain Step 3** (review_results) — 3.49s
- Prompt: What's the distribution?
- Tools called: ['crm_stats']
- missing:FASHION_BRAND: True
- missing:segment: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 3.52s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['crm_stats']
- missing:215: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 3.58s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['list_projects']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 3.75s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 4.16s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_list_sources']
- must_contain_any: ['file path', 'upload', 'where is the file']

**15_step_add_remove_iterations Step 1** (add_regex_step) — 3.51s
- Prompt: Add employee size segmentation column
- Tools called: ['tam_list_sources']
- missing:added: True
- unexpected:AI: True

**15_step_add_remove_iterations Step 3** (remove_step) — 4.32s
- Prompt: Drop the size column
- Tools called: ['provide_feedback']
- missing:removed: True
- missing:size_segment: True

**15_step_add_remove_iterations Step 5** (add_ai_step) — 3.26s
- Prompt: I want to know which companies are brands vs manufacturers — analyze their websites
- Tools called: ['tam_list_sources']
- missing:classify: True
- missing:prompt: True

