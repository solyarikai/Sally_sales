# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_185601

## MCP Server Issues (6)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**09_multi_source_csv_first Step 3** (source_selection) — 3.65s
- Prompt: Run pipeline on this CSV file /data/take-test-100.csv — looking for fashion and apparel brands in La
- Tools called: ['tam_gather']
- missing:gathered: True
- tool_error:tam_gather: Project not found

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 4.41s
- Prompt: I have more leads in Google Sheets: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgm
- Tools called: ['tam_gather']
- missing:existing: True
- missing:pipeline: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']
- tool_error:tam_gather: Project not found

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 3.81s
- Prompt: I've got more files on Drive: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj_LATAM_batches
- Tools called: ['tam_gather']
- missing:existing: True
- missing:pipeline: True
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']
- tool_error:tam_gather: Project not found

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 3.75s
- Prompt: Yep, same project, just add these files
- Tools called: ['tam_gather']
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']
- tool_error:tam_gather: Project not found

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 3.24s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_gather']
- must_contain_any: ['file path', 'upload', 'where is the file']
- tool_error:tam_gather: Project not found

**15_step_add_remove_iterations Step 4** (verify_iteration_history) — 3.42s
- Prompt: Switch to iteration 1
- Tools called: ['refinement_status']
- tool_error:refinement_status: Refinement run not found

## GPT Tool Selection Issues (20)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 4** (gathering) — 2.83s
- Prompt: Search for Italian fashion companies
- Tools called: ['get_context']
- missing_tool:parse_gathering_intent: called:['get_context'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**02_new_user_fashion Step 5** (full_pipeline) — 3.07s
- Prompt: Process the gathered companies
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**09_multi_source_csv_first Step 2** (project_selection) — 3.02s
- Prompt: Select project Result
- Tools called: ['get_context']
- missing_tool:select_project: called:['get_context'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 5** (blacklist) — 3.27s
- Prompt: Blacklist check please
- Tools called: ['check_integrations']
- missing_tool:tam_blacklist_check: called:['check_integrations'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['check_integrations'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 3.07s
- Prompt: Now scrape and analyze all the companies
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 3.24s
- Prompt: Looks good, approve the targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 3.04s
- Prompt: Add to existing pipeline
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:companies: True
- missing:gathered: True
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 3.03s
- Prompt: Blacklist check for the sheet import
- Tools called: ['blacklist_check']
- missing_tool:tam_blacklist_check: called:['blacklist_check'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['blacklist_check'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 3.11s
- Prompt: Scrape and analyze the new companies
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**10_multi_source_sheet_add_to_existing Step 5** (checkpoint2_approval) — 3.17s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 2.97s
- Prompt: Check blacklist for the drive import
- Tools called: ['check_integrations']
- missing_tool:tam_blacklist_check: called:['check_integrations'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['check_integrations'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 3.16s
- Prompt: Scrape and analyze
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**11_multi_source_drive_add_to_existing Step 5** (checkpoint2_approval) — 3.86s
- Prompt: Approve
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 3.7s
- Prompt: Go ahead with those prompts
- Tools called: ['get_context']
- missing_tool:tam_re_analyze: called:['get_context'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True

**12_custom_prompt_chain Step 4** (approve) — 2.97s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**13_blacklist_isolation Step 3** (gather_for_project_b) — 2.95s
- Prompt: Gather companies for TestProjectB from this CSV: /data/test_overlap.csv
- Tools called: ['list_projects']
- missing_tool:tam_gather: called:['list_projects'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**23_second_project_onsocial Step 2** (switch_project) — 3.02s
- Prompt: Switch to the Result project
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 2.86s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 3.56s
- Prompt: Search for UK influencer platforms
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**23_second_project_onsocial Step 6** (verify_isolation) — 3.11s
- Prompt: Check blacklist and approve for OnSocial
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

## Other Issues (13)

**02_new_user_fashion Step 3** (no_campaigns_check) — 2.83s
- Prompt: This is our first outreach campaign
- Tools called: ['get_context']
- missing:gather: True
- missing:find: True

**02_new_user_fashion Step 6** (email_accounts) — 3.33s
- Prompt: Send from elnar@thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**09_multi_source_csv_first Step 4** (custom_prompt) — 3.08s
- Prompt: Here's my classification: VALID if fashion brand/clothing manufacturer in LATAM. NOT_VALID if market
- Tools called: ['get_context']
- missing:prompt: True
- missing:classify: True

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 3.28s
- Prompt: Re-analyze with custom prompts: First classify the industry (FASHION_BRAND, TEXTILE_PRODUCER, RETAIL
- Tools called: ['get_context']
- missing:step: True
- missing:filter: True

**12_custom_prompt_chain Step 3** (review_results) — 2.96s
- Prompt: Show me the breakdown by segment and size
- Tools called: ['get_context']
- missing:FASHION_BRAND: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 3.37s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['get_context']
- missing:215: True

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 6.13s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['get_context', 'tam_gather']
- missing:duplicate: True
- missing:already: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 2.85s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['get_context']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 2.88s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['list_projects']
- missing:Apollo: True

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 3.91s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['tam_gather']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

**15_step_add_remove_iterations Step 1** (add_regex_step) — 3.15s
- Prompt: Classify companies by headcount into SMALL, MEDIUM, LARGE
- Tools called: ['get_context']
- missing:size: True
- missing:column: True
- missing:added: True
- unexpected:AI: True

**15_step_add_remove_iterations Step 3** (remove_step) — 3.36s
- Prompt: Remove the size_segment column
- Tools called: ['get_context']
- missing:removed: True

**15_step_add_remove_iterations Step 5** (add_ai_step) — 3.6s
- Prompt: Classify brand vs manufacturer from website content
- Tools called: ['get_context']
- missing:prompt: True

