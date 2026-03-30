# Issues Found — test4@getsally.io

**Source:** automated_framework | **Time:** 20260330_193527

## MCP Server Issues (7)

These are REAL bugs in the MCP server — tool was called correctly but returned error.

**01_default_smartlead_flow Step 10** (4.1_blacklist_check) — 0.46s
- Prompt: How is gathering going?
- Tools called: ['pipeline_status']
- must_contain_any: ['blacklist', 'checkpoint', 'approve']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 11** (4.2_approve_checkpoint1) — 0.39s
- Prompt: Looks good
- Tools called: ['tam_approve_checkpoint']
- must_contain_any: ['approved', 'scraping', 'analyzing']
- tool_error:tam_approve_checkpoint: Gate not found

**01_default_smartlead_flow Step 12** (4.3_classification_results) — 0.37s
- Prompt: Pipeline status?
- Tools called: ['pipeline_status']
- must_contain_any: ['target', 'classified', 'segment']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 13** (4.4_exploration) — 0.38s
- Prompt: Run exploration
- Tools called: ['tam_explore']
- tool_error:tam_explore: Run not found

**01_default_smartlead_flow Step 14** (7.1_iteration_visible) — 0.49s
- Prompt: Show the pipeline results
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'filter']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 16** (7.3_iteration2_results) — 0.38s
- Prompt: How did the re-analysis go?
- Tools called: ['pipeline_status']
- must_contain_any: ['iteration', 'target', 'improved']
- tool_error:pipeline_status: Run not found

**01_default_smartlead_flow Step 18** (5.1_sequence_generation) — 32.01s
- Prompt: Generate the email sequence
- Tools called: ['smartlead_generate_sequence']
- tool_error:smartlead_generate_sequence: Connection closed

## Other Issues (5)

**01_default_smartlead_flow Step 1** (1.1_greeting_no_token) — 0.0s
- Prompt: Hey, I want to launch some campaigns
- Tools called: []
- must_contain_any: ['sign up', 'token', 'mcp_']

**01_default_smartlead_flow Step 2** (1.2_login) — 0.61s
- Prompt: Here is my token: mcp_13ca4093381b847d8664eb3c7842fb022d8a551d18693249f03bf0e6903ab039
- Tools called: ['login']
- must_contain_any: ['apollo', 'smartlead', 'openai']

**01_default_smartlead_flow Step 15** (7.2_agent_feedback_reanalyze) — 0.86s
- Prompt: Remove software product companies, keep only consulting
- Tools called: ['provide_feedback']
- must_contain_any: ['prompt', 're-analyze', 'iteration']

**01_default_smartlead_flow Step 20** (5.3_activate) — 0.0s
- Prompt: Approved, activate
- Tools called: ['activate_campaign']
- must_contain_any: ['activated', 'launched', 'monitoring']

**01_default_smartlead_flow Step 22** (6.3_session_continuity) — 0.0s
- Prompt: What was I working on?
- Tools called: ['get_context']
- must_contain_any: ['EasyStaff', 'project', 'campaign']

