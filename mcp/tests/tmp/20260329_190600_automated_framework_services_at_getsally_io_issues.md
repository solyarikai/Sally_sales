# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_190600

## MCP Server Issues (4)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**02_new_user_fashion Step 7** (second_project) — 11.01s
- Prompt: I also need to find influencer platforms in UK for https://onsocial.ai/
- Tools called: ['tam_gather', 'tam_gather']
- missing_tool:create_project: called:['tam_gather', 'tam_gather'] (acceptable: ['create_project'])
- tool_error:tam_gather: Project not found

**09_multi_source_csv_first Step 3** (source_selection) — 7.91s
- Prompt: I have a CSV with LATAM fashion companies. Here: /data/take-test-100.csv. Classify them as fashion b
- Tools called: ['tam_gather', 'parse_gathering_intent']
- missing:gathered: True
- tool_error:tam_gather: Project not found
- tool_error:parse_gathering_intent: Project not found

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 5.35s
- Prompt: Here's another batch from Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBd
- Tools called: ['tam_gather']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']
- tool_error:tam_gather: Project not found

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 4.03s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_gather']
- must_contain_any: ['file path', 'upload', 'where is the file']
- tool_error:tam_gather: Project not found

## GPT Tool Selection Issues (21)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 3.57s
- Prompt: Gather fashion brands from Italy, around 10 targets please
- Tools called: ['list_projects']
- missing_tool:parse_gathering_intent: called:['list_projects'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**02_new_user_fashion Step 5** (full_pipeline) — 3.91s
- Prompt: Run blacklist and analysis
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**09_multi_source_csv_first Step 2** (project_selection) — 3.5s
- Prompt: Select project Result
- Tools called: ['get_context']
- missing_tool:select_project: called:['get_context'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 5** (blacklist) — 5.1s
- Prompt: Run blacklist check and approve
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 4.23s
- Prompt: Process the pipeline — scrape and analyze
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 4.06s
- Prompt: Target list looks fine, proceed
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 3.76s
- Prompt: Same pipeline, just add these companies
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 3.35s
- Prompt: Blacklist check for the sheet import
- Tools called: ['tam_list_sources']
- missing_tool:tam_blacklist_check: called:['tam_list_sources'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['tam_list_sources'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 4.87s
- Prompt: Run the pipeline on the new batch
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**10_multi_source_sheet_add_to_existing Step 5** (checkpoint2_approval) — 5.67s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.72s
- Prompt: Add to existing one
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 5.95s
- Prompt: Run blacklist check
- Tools called: ['check_integrations']
- missing_tool:tam_blacklist_check: called:['check_integrations'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['check_integrations'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 6.83s
- Prompt: Pre-filter, scrape, analyze
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**11_multi_source_drive_add_to_existing Step 5** (checkpoint2_approval) — 4.03s
- Prompt: Approve
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 3.57s
- Prompt: Perfect, analyze with these
- Tools called: ['get_context']
- missing_tool:tam_re_analyze: called:['get_context'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True

**12_custom_prompt_chain Step 4** (approve) — 3.92s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**13_blacklist_isolation Step 3** (gather_for_project_b) — 3.6s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**23_second_project_onsocial Step 2** (switch_project) — 3.5s
- Prompt: Switch to the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 3.84s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 3.62s
- Prompt: Find influencer platforms in UK, about 10 targets
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**23_second_project_onsocial Step 6** (verify_isolation) — 3.53s
- Prompt: Blacklist check for this project
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

## Other Issues (14)

**02_new_user_fashion Step 3** (no_campaigns_check) — 3.61s
- Prompt: We haven't set up any campaigns before
- Tools called: ['get_context']
- missing:gather: True
- missing:find: True

**02_new_user_fashion Step 6** (email_accounts) — 3.59s
- Prompt: Use elnar at thefashionpeopletech.com
- Tools called: ['check_integrations']
- missing:email account: True
- missing:which: True

**09_multi_source_csv_first Step 4** (custom_prompt) — 4.84s
- Prompt: My segmentation: look for companies that design and produce clothing, fashion accessories, or textil
- Tools called: ['get_context']
- missing:prompt: True
- missing:classify: True

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 4.55s
- Prompt: Also check this Drive folder with 3 CSV files: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7V
- Tools called: ['tam_gather']
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 3.61s
- Prompt: I need multi-step classification: 1) Segment by business type (fashion brand, textile producer, reta
- Tools called: ['get_context']
- missing:classify: True
- missing:filter: True

**12_custom_prompt_chain Step 3** (review_results) — 3.45s
- Prompt: Show me the breakdown by segment and size
- Tools called: ['get_context']
- missing:FASHION_BRAND: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 3.32s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['get_context']
- missing:215: True

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 7.43s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['list_projects', 'tam_gather']
- missing:duplicate: True
- missing:already: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 3.58s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['get_context']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 3.41s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 4.7s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['tam_gather']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

**15_step_add_remove_iterations Step 1** (add_regex_step) — 3.83s
- Prompt: Add employee size segmentation column
- Tools called: ['get_context']
- missing:added: True
- unexpected:AI: True

**15_step_add_remove_iterations Step 3** (remove_step) — 3.72s
- Prompt: I don't need size_segment anymore, remove it
- Tools called: ['get_context']
- missing:removed: True

**15_step_add_remove_iterations Step 5** (add_ai_step) — 3.72s
- Prompt: Add business_model column: BRAND if they sell own brand, MANUFACTURER if they produce for others
- Tools called: ['get_context']
- missing:classify: True
- missing:prompt: True

