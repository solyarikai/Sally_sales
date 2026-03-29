# Issues Found — services@getsally.io

**Source:** automated_framework | **Time:** 20260329_214118

## GPT Tool Selection Issues (21)

GPT picked the wrong tool. May fix with better prompts or switch to Claude API.

**02_new_user_fashion Step 2** (project_setup) — 19.85s
- Prompt: I'm from The Fashion People (thefashionpeople.com), need to find fashion brands in Italy
- Tools called: ['get_context']
- missing_tool:create_project: called:['get_context'] (acceptable: ['create_project'])
- missing:created: True

**02_new_user_fashion Step 4** (gathering) — 19.4s
- Prompt: Look for e-commerce fashion brands based in Italy
- Tools called: ['get_context']
- missing_tool:parse_gathering_intent: called:['get_context'] (acceptable: ['parse_gathering_intent', 'tam_gather', 'suggest_apollo_filters'])
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])

**02_new_user_fashion Step 5** (full_pipeline) — 4.06s
- Prompt: Run blacklist and analysis
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**09_multi_source_csv_first Step 2** (project_selection) — 5.86s
- Prompt: Select project Result
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**09_multi_source_csv_first Step 3** (source_selection) — 19.22s
- Prompt: Here's my company list as CSV: /data/take-test-100.csv. I want to segment by fashion/apparel vs othe
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True

**09_multi_source_csv_first Step 5** (blacklist) — 19.58s
- Prompt: Check the blacklist for this project
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**09_multi_source_csv_first Step 6** (pre_filter_scrape_analyze) — 19.31s
- Prompt: Run pre-filter, scrape websites, and classify
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True
- missing:review: True

**09_multi_source_csv_first Step 7** (checkpoint2_approval) — 5.05s
- Prompt: Approve
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**10_multi_source_sheet_add_to_existing Step 2** (user_chooses_existing) — 5.01s
- Prompt: Add to existing pipeline
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['70 new', '40 duplicate', '40 already']

**10_multi_source_sheet_add_to_existing Step 3** (blacklist_with_overlap) — 19.7s
- Prompt: Blacklist check for the sheet import
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**10_multi_source_sheet_add_to_existing Step 4** (full_pipeline) — 19.86s
- Prompt: Scrape and analyze the new companies
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])
- missing:targets: True
- missing:checkpoint: True

**10_multi_source_sheet_add_to_existing Step 5** (checkpoint2_approval) — 5.48s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**11_multi_source_drive_add_to_existing Step 2** (user_chooses_existing) — 4.74s
- Prompt: Add to the existing pipeline, don't create a new one
- Tools called: ['get_context']
- missing_tool:tam_gather: called:['get_context'] (acceptable: ['tam_gather', 'parse_gathering_intent', 'suggest_apollo_filters'])
- missing:gathered: True
- must_contain_any: ['35 new', '70 duplicate', '70 already']

**11_multi_source_drive_add_to_existing Step 3** (blacklist) — 20.65s
- Prompt: Blacklist check please
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

**11_multi_source_drive_add_to_existing Step 4** (full_pipeline) — 20.24s
- Prompt: Pre-filter, scrape, analyze
- Tools called: ['get_context']
- missing_tool:tam_pre_filter: called:['get_context'] (acceptable: ['tam_pre_filter'])
- missing_tool:tam_scrape: called:['get_context'] (acceptable: ['tam_scrape'])
- missing_tool:tam_analyze: called:['get_context'] (acceptable: ['tam_analyze'])

**11_multi_source_drive_add_to_existing Step 5** (checkpoint2_approval) — 4.0s
- Prompt: Approve
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**12_custom_prompt_chain Step 2** (user_approves_prompts) — 5.05s
- Prompt: Go ahead with those prompts
- Tools called: ['get_context']
- missing_tool:tam_re_analyze: called:['get_context'] (acceptable: ['tam_re_analyze'])
- missing:targets: True
- missing:classified: True
- missing:segments: True

**12_custom_prompt_chain Step 4** (approve) — 5.2s
- Prompt: Approve targets
- Tools called: ['get_context']
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])

**23_second_project_onsocial Step 4** (switch_to_onsocial) — 19.96s
- Prompt: Switch to OnSocial UK
- Tools called: ['list_projects']
- missing_tool:select_project: called:['list_projects'] (acceptable: ['select_project'])

**23_second_project_onsocial Step 5** (gather_for_onsocial) — 20.13s
- Prompt: Gather creator economy companies in the UK
- Tools called: ['parse_gathering_intent']
- missing:gathered: True

**23_second_project_onsocial Step 6** (verify_isolation) — 5.48s
- Prompt: Blacklist check for this project
- Tools called: ['get_context']
- missing_tool:tam_blacklist_check: called:['get_context'] (acceptable: ['tam_blacklist_check'])
- missing_tool:tam_approve_checkpoint: called:['get_context'] (acceptable: ['tam_approve_checkpoint'])
- missing:approved: True

## Other Issues (16)

**02_new_user_fashion Step 3** (no_campaigns_check) — 4.69s
- Prompt: I don't have any SmartLead campaigns yet
- Tools called: ['list_smartlead_campaigns']
- missing:gather: True
- missing:find: True

**02_new_user_fashion Step 6** (email_accounts) — 20.08s
- Prompt: Send from elnar@thefashionpeopletech.com
- Tools called: ['list_email_accounts']
- missing:which: True

**09_multi_source_csv_first Step 4** (custom_prompt) — 4.78s
- Prompt: Here's my classification: VALID if fashion brand/clothing manufacturer in LATAM. NOT_VALID if market
- Tools called: ['get_context']
- missing:prompt: True
- missing:classify: True

**10_multi_source_sheet_add_to_existing Step 1** (source_addition) — 20.5s
- Prompt: Analyze this sheet too: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og
- Tools called: ['get_context']
- missing:existing: True
- missing:new: True
- must_contain_any: ['add to existing', 'create a new pipeline', 'existing run']

**11_multi_source_drive_add_to_existing Step 1** (source_addition) — 19.84s
- Prompt: Last batch — files in this folder: https://drive.google.com/drive/folders/1bBZFN5Yg2qe7VGj_LATAM_bat
- Tools called: ['get_context']
- missing:existing: True
- must_contain_any: ['add to existing', 'already have 2 runs', 'existing pipeline for Result']

**12_custom_prompt_chain Step 1** (user_provides_custom_prompt) — 20.65s
- Prompt: I need multi-step classification: 1) Segment by business type (fashion brand, textile producer, reta
- Tools called: ['get_context']
- missing:classify: True

**12_custom_prompt_chain Step 3** (review_results) — 19.95s
- Prompt: How many in each segment?
- Tools called: ['get_context']
- missing:FASHION_BRAND: True

**13_blacklist_isolation Step 1** (verify_project_a_state) — 19.34s
- Prompt: How many companies do we have in the Result project?
- Tools called: ['crm_stats']
- missing:215: True

**13_blacklist_isolation Step 5** (verify_same_project_dedup) — 20.65s
- Prompt: Add the CSV data again to Result project: /data/take-test-100.csv
- Tools called: ['tam_gather']
- missing:duplicate: True
- missing:already: True

**14_source_suggestion_edge_cases Step 1** (no_source_no_key) — 4.68s
- Prompt: Gather fashion companies in Argentina
- Tools called: ['parse_gathering_intent']
- must_contain_any: ['Apollo key not configured', 'provide a CSV', 'Google Sheet']

**14_source_suggestion_edge_cases Step 2** (no_source_has_key) — 20.91s
- Prompt: Find fashion brands in Colombia, about 50 targets
- Tools called: ['get_context']
- missing:Apollo: True
- missing:credits: True

**14_source_suggestion_edge_cases Step 3** (ambiguous_with_csv_mention) — 5.91s
- Prompt: I have a CSV file with my leads
- Tools called: ['tam_gather']
- must_contain_any: ['file path', 'upload', 'where is the file']

**14_source_suggestion_edge_cases Step 4** (google_doc_not_sheet) — 21.07s
- Prompt: Check this doc: https://docs.google.com/document/d/1abc123/edit
- Tools called: ['tam_gather']
- must_contain_any: ['Google Doc', 'spreadsheet', 'CSV']

**15_step_add_remove_iterations Step 1** (add_regex_step) — 20.63s
- Prompt: Add a column that classifies companies by size: LARGE if 100+ employees, MEDIUM if 20-99, SMALL if u
- Tools called: ['get_context']
- missing:added: True
- unexpected:AI: True

**15_step_add_remove_iterations Step 3** (remove_step) — 22.19s
- Prompt: Delete the size classification
- Tools called: ['get_context']
- missing:removed: True
- missing:size_segment: True

**15_step_add_remove_iterations Step 5** (add_ai_step) — 4.96s
- Prompt: Add business_model column: BRAND if they sell own brand, MANUFACTURER if they produce for others
- Tools called: ['get_context']
- missing:classify: True
- missing:prompt: True

