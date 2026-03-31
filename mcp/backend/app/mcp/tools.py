"""MCP Tool definitions — 26 tools for the LeadGen pipeline."""

TOOLS = [
    # ── Account (3) ──
    {
        "name": "login",
        "description": """MANDATORY FIRST STEP. Call this BEFORE any other tool. ALL tools require authentication.

If user hasn't provided a token yet, DO NOT proceed with ANY request. Instead say:
"Sign up at http://46.62.210.24:3000 to get your API token, then paste it here."

NEVER ask questions about companies, segments, or campaigns before login. NEVER skip this step.
Only accept tokens starting with mcp_.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "API token starting with mcp_"},
            },
            "required": ["token"],
        },
    },
    {
        "name": "get_context",
        "description": """Get the user's current state — projects, pipelines, campaigns, pending actions.
Call this ONLY after login or when user asks "what was I working on?" / "status" / "resume".
DO NOT call this when the user asks to DO something (gather, explore, generate, activate).
For those actions, call the specific tool directly (tam_gather, tam_explore, smartlead_generate_sequence, activate_campaign).""",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "configure_integration",
        "description": "Connect an external service by providing your API key. Required: apollo (find companies), smartlead (create campaigns), openai (AI analysis), apify (scrape websites). Optional: getsales (LinkedIn outreach).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "integration_name": {"type": "string", "enum": ["apollo", "smartlead", "openai", "apify", "getsales"]},
                "api_key": {"type": "string", "description": "Your API key for this service"},
            },
            "required": ["integration_name", "api_key"],
        },
    },
    {
        "name": "check_integrations",
        "description": "List all connected integrations and their status.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ── Project (4) ──
    {
        "name": "select_project",
        "description": """Set your active working project. CRITICAL: You MUST call this before any pipeline operation if the user has multiple projects. This determines which project's campaigns are used for blacklisting.

When a user first connects or says something like 'gather companies' without specifying a project, you MUST:
1. Call list_projects to see their projects
2. If multiple projects exist, ASK which one they want to work on
3. Call select_project to set it
4. Show them the project's campaigns and blacklist scope

The response shows: project name, ICP, active campaigns, and which companies are already contacted.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project to set as active"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "create_project",
        "description": """Create a new project from the user's website.

WHEN USER SAYS: "easystaff.io", "our website is X", "we sell Y" → call THIS with website=URL.
The website is scraped to extract offer/value proposition. This is REQUIRED before gathering.
AFTER creating project, ask: "Have you launched campaigns for this project before?" (ONE question only).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "website": {"type": "string", "description": "Company website URL (e.g. 'https://easystaff.io'). REQUIRED — will be scraped to extract value proposition for ICP and sequence generation."},
                "target_segments": {"type": "string", "description": "ICP description (e.g. 'Series A-B SaaS in DACH, 50-500 emp')"},
                "target_industries": {"type": "string", "description": "Target industries (e.g. 'SaaS, Fintech, IT Services')"},
                "sender_name": {"type": "string"},
                "sender_company": {"type": "string"},
                "sender_position": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_projects",
        "description": "List all your projects.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "update_project",
        "description": "Update a project's ICP or sender info.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "name": {"type": "string"},
                "target_segments": {"type": "string"},
                "target_industries": {"type": "string"},
                "sender_name": {"type": "string"},
                "sender_company": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },

    # ── Intent Parsing ──
    {
        "name": "parse_gathering_intent",
        "description": """INTERNAL: Parse multi-segment queries. Usually you DON'T need to call this — tam_gather handles it automatically.
Only call explicitly when user provides 2+ DIFFERENT segments in one message (e.g. "IT consulting Miami AND fashion brands Italy") and you need to confirm how many pipelines to run.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "User's raw gathering query"},
                "project_id": {"type": "integer", "description": "Project ID (to get user's offer for competitor exclusion)"},
            },
            "required": ["query", "project_id"],
        },
    },
    # ── Pipeline ──
    {
        "name": "tam_gather",
        "description": """Gather companies from Apollo/CSV/Sheet. THIS is the tool for "find companies", "gather", "search", "launch pipeline".

WHEN USER SAYS: "find IT consulting in Miami", "gather companies", "start pipeline", "search for" → call THIS tool.
DO NOT call parse_gathering_intent or suggest_apollo_filters — tam_gather handles everything.

TWO-STEP for Apollo:
  Step 1: Call WITHOUT confirm_filters → returns FILTER PREVIEW (keywords, total available, cost estimate). Show to user, ask "Proceed?"
  Step 2: Call WITH confirm_filters=true → actually searches Apollo and spends credits.
NEVER skip the preview step. NEVER call twice without user confirmation between calls.

Pass query= with the user's natural language (e.g. "IT consulting in Miami"). System auto-generates Apollo filters from taxonomy maps.
Pass filters= with at least organization_num_employees_ranges (e.g. ["11,50","51,200"]).

AFTER gathering starts, ask: "Which email accounts to use for the campaign?" (call list_email_accounts).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project to gather for"},
                "source_type": {
                    "type": "string",
                    "enum": ["apollo.companies.api",
                             "csv.companies.manual", "csv.companies.file",
                             "google_sheets.companies.manual", "google_sheets.companies.sheet",
                             "google_drive.companies.folder",
                             "manual.companies.manual"],
                    "description": "Source to gather from. Apollo API costs credits. CSV/Sheet/Drive/Manual are free.",
                },
                "target_count": {"type": "integer", "description": "How many TARGET companies the user wants. System auto-calculates pages needed."},
                "filters": {
                    "type": "object",
                    "description": "Source-specific filters. For Apollo: keywords, locations, etc. For CSV: file_path. For Sheet: sheet_url. For Drive: drive_url or folder_path.",
                    "properties": {
                        "q_organization_keyword_tags": {"type": "array", "items": {"type": "string"}},
                        "organization_locations": {"type": "array", "items": {"type": "string"}},
                        "organization_num_employees_ranges": {"type": "array", "items": {"type": "string"}},
                        "max_pages": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "organization_latest_funding_stage_cd": {"type": "array", "items": {"type": "string"}},
                        "domains": {"type": "array", "items": {"type": "string"}},
                        "sheet_url": {"type": "string", "description": "Google Sheets URL for google_sheets.companies.sheet source"},
                        "file_path": {"type": "string", "description": "Path to CSV file for csv.companies.file source"},
                        "file_url": {"type": "string", "description": "URL to download CSV for csv.companies.file source"},
                        "drive_url": {"type": "string", "description": "Google Drive folder URL for google_drive.companies.folder source"},
                        "folder_path": {"type": "string", "description": "Local folder path for google_drive.companies.folder source (testing)"},
                        "tab_name": {"type": "string", "description": "Sheet tab name for google_sheets.companies.sheet source"},
                        "column_mapping": {"type": "object", "description": "Explicit column mapping override: {domain: 'Website', name: 'Company Name', ...}"},
                    },
                },
                "query": {"type": "string", "description": "Natural language query — triggers auto-filter discovery if no keywords provided"},
                "reuse_run_id": {"type": "integer", "description": "Reuse filters from a previous run. User says 'same filters, more targets'"},
                "confirm_filters": {"type": "boolean", "description": "For Apollo: set true AFTER user approves the filter preview. First call without this returns preview only."},
            },
            "required": ["project_id", "source_type", "filters"],
        },
    },
    {
        "name": "tam_blacklist_check",
        "description": "Phase 2: Check gathered companies against existing campaigns. Creates Checkpoint 1 gate.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_approve_checkpoint",
        "description": "Approve a pipeline checkpoint (CP1: scope, CP2: targets, CP3: cost).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "gate_id": {"type": "integer"},
                "note": {"type": "string", "description": "Optional approval note"},
            },
            "required": ["gate_id"],
        },
    },
    {
        "name": "tam_pre_filter",
        "description": "Phase 3: Deterministic pre-filtering (remove trash domains, too-small companies).",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_scrape",
        "description": "Phase 4: Scrape websites for all non-blacklisted companies. Free, no credits used.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_analyze",
        "description": """Phase 5: GPT-4o-mini analyzes scraped companies via negativa. Labels segments, creates Checkpoint 2.

GPT is the cheap workhorse ($0.003/company). YOU (the agent = Opus) are the QA.
After this returns, review the target_list and borderline_rejections.
If GPT's accuracy < 90% (false positives), call tam_re_analyze with an adjusted prompt.

Via negativa: GPT focuses on EXCLUDING shit, not confirming matches.
Segments: CAPS_LOCKED labels (IT_OUTSOURCING, SAAS_COMPANY, AGENCY, etc.)

Custom prompts: Users can provide their own classification prompts via prompt_text.
Multi-step chains: Provide prompt_steps array for sequential classification (each step feeds into the next).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "prompt_text": {"type": "string", "description": "ICP description for via negativa analysis. Built from project knowledge if omitted. Users can provide their own classification prompt."},
                "prompt_steps": {
                    "type": "array",
                    "description": "Multi-step prompt chain. Each step runs sequentially; output feeds into next step.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Step name (e.g., 'classify_fashion')"},
                            "prompt": {"type": "string", "description": "Classification prompt for this step"},
                            "output_column": {"type": "string", "description": "Name of the output column/field"},
                            "type": {"type": "string", "enum": ["classify", "filter"], "description": "Step type: 'classify' runs GPT, 'filter' removes non-matching companies"},
                            "filter_condition": {"type": "string", "description": "For filter steps: condition like 'segment != OTHER'"},
                        },
                        "required": ["name", "prompt"],
                    },
                },
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_explore",
        "description": """Exploration: enrich top 5 targets to discover better Apollo filters.

WHEN USER SAYS: "explore", "find better filters", "optimize", "enrich targets" → call THIS.
Costs 5 Apollo credits. Returns optimized filters with real Apollo vocabulary.
Call AFTER classification is done (targets exist in the pipeline).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "Pipeline run to explore (must have targets)"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_enrich_from_examples",
        "description": """Reverse-engineer Apollo filters from example companies. User provides a list of domains (companies they KNOW are targets), Apollo enrichment reveals their real keyword tags and industries. Use the output as filters for tam_gather.

Use case: user says 'companies like X, Y, Z' or provides a file with example companies.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domains": {"type": "array", "items": {"type": "string"}, "description": "List of example company domains (max 10)"},
                "segment_description": {"type": "string", "description": "What kind of companies these are"},
                "locations": {"type": "array", "items": {"type": "string"}, "description": "Target locations for the search"},
            },
            "required": ["domains"],
        },
    },
    {
        "name": "tam_re_analyze",
        "description": """Re-classify same companies with better prompt. Creates new pipeline iteration.

WHEN USER SAYS: "these aren't right", "exclude X", "re-analyze", "wrong targets" → call provide_feedback FIRST, then THIS.
WHEN USER'S AGENT provides verdicts: pass agent_verdicts={domain: {target: bool, reason: str}} for auto-tuning.

Does NOT re-gather. Same companies, different classification. New iteration visible in UI.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "prompt_text": {"type": "string", "description": "Improved classification prompt (manual mode)"},
                "agent_verdicts": {"type": "object", "description": "Auto-tune: {domain: {target: bool, reason: str}}"},
            },
            "required": ["run_id"],
        },
    },
    # FindyMail DISABLED in MVP — uncomment when ready for production
    # {
    #     "name": "tam_prepare_verification",
    #     "description": "Creates Checkpoint 3 with FindyMail cost estimate before spending credits.",
    #     "inputSchema": {
    #         "type": "object",
    #         "properties": {"run_id": {"type": "integer"}},
    #         "required": ["run_id"],
    #     },
    # },
    # {
    #     "name": "tam_run_verification",
    #     "description": "Phase 6: Run FindyMail email verification on approved targets. COSTS CREDITS.",
    #     "inputSchema": {
    #         "type": "object",
    #         "properties": {"run_id": {"type": "integer"}},
    #         "required": ["run_id"],
    #     },
    # },
    {
        "name": "tam_list_sources",
        "description": "List available gathering sources with their filter schemas.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ── Refinement (2) ──
    {
        "name": "refinement_status",
        "description": "Get the current status of a self-refinement run: iteration count, accuracy history, patterns found.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "refinement_override",
        "description": "Accept current accuracy and stop the refinement loop early.",
        "inputSchema": {
            "type": "object",
            "properties": {"refinement_run_id": {"type": "integer"}},
            "required": ["refinement_run_id"],
        },
    },

    # ── Campaign Sequence Tools (5) ──
    {
        "name": "smartlead_score_campaigns",
        "description": "Score and rank campaigns by quality (warm reply rate, meetings, volume).",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
        },
    },
    {
        "name": "smartlead_extract_patterns",
        "description": "Extract reusable patterns from top-performing campaigns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {"type": "string"},
                "top_n": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "smartlead_generate_sequence",
        "description": """Generate email sequence for a campaign.

WHEN USER SAYS: "generate sequence", "create emails", "write the campaign" → call THIS.
Returns a DRAFT sequence (4-5 steps). Show preview to user, then call smartlead_approve_sequence.
FLOW: generate → user approves → smartlead_approve_sequence → smartlead_push_campaign.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "campaign_name": {"type": "string"},
                "instructions": {"type": "string", "description": "Additional instructions for sequence generation"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "smartlead_approve_sequence",
        "description": "Mark a generated sequence as approved.",
        "inputSchema": {
            "type": "object",
            "properties": {"sequence_id": {"type": "integer"}},
            "required": ["sequence_id"],
        },
    },
    {
        "name": "check_destination",
        "description": """Check which outreach platforms are configured (SmartLead, GetSales, or both).
MUST be called before pushing a campaign when you're not sure which platform to use.
If both are configured, returns a question asking the user to choose.""",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "smartlead_push_campaign",
        "description": """Push an approved sequence to SmartLead as a DRAFT campaign with FULL configuration.
IMPORTANT: You MUST call list_email_accounts first and ask the user which accounts to use before calling this tool.

BEFORE calling this, you MUST:
1. Ask the user: "Which email accounts should I use for this campaign?"
2. Call list_email_accounts to show available accounts
3. Wait for user to select accounts — NEVER proceed without their choice
4. Pass the selected account IDs in email_account_ids parameter

Without email accounts: campaign is created but test email CANNOT be sent.
The user might say: "Use Eleonora's accounts from my petr campaigns" or provide a specific email.

Campaign settings (production-grade):
- Plain text, no tracking, stop on reply, 40% follow-up, Mon-Fri 9-18 target timezone
- Target contacts auto-uploaded with normalized company names + segment as custom fields
- Test email auto-sent to user's email after creation

Campaign is ALWAYS DRAFT — never activated without explicit user approval.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_id": {"type": "integer"},
                "email_account_ids": {"type": "array", "items": {"type": "integer"}, "description": "SmartLead email account IDs to use. Get from list_email_accounts."},
                "target_country": {"type": "string", "description": "Country for timezone (from gathering geo filter). E.g. 'United States', 'Germany'"},
            },
            "required": ["sequence_id"],
        },
    },
    {
        "name": "list_email_accounts",
        "description": """List SmartLead email accounts available for campaigns. Shows accounts used in the user's existing campaigns (from blacklist import) so they can reuse the same sending accounts.

Call this BEFORE smartlead_push_campaign to let the user choose which accounts to use.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer", "description": "Optional: show accounts from a specific campaign"},
            },
        },
    },
    {
        "name": "send_test_email",
        "description": """Send a test email via SmartLead's native API. Uses the user's email as recipient.
Auto-resolves sending account and lead for variable substitution.

Call this after smartlead_push_campaign to let the user preview the email in their inbox.
Also called automatically when a campaign is created.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer", "description": "SmartLead campaign ID (external_id)"},
                "test_email": {"type": "string", "description": "Override recipient email (defaults to user's email)"},
                "sequence_number": {"type": "integer", "default": 1, "description": "Which sequence step to test (1, 2, 3...)"},
            },
            "required": ["campaign_id"],
        },
    },

    # ── GetSales LinkedIn Automation (5) ──
    {
        "name": "gs_generate_flow",
        "description": """Generate a LinkedIn automation flow for GetSales using proven patterns from your 414 live flows.

Analyzes your project's ICP, sender info, and knowledge to create an optimized LinkedIn sequence.

Flow types (from GETSALES_AUTOMATION_PLAYBOOK.md):
- "standard": Qualifying question + 3 follow-ups (EasyStaff UAE pattern, 68% positive rate)
- "networking": No connection note + soft intro + 3 messages (Rizzult Miami, 69% positive)
- "product": Generic connect + product showcase + 3 messages (Mifort, 85% on niche ICP)
- "volume": Value prop note + 4 msgs + InMail fallback (EasyStaff RU, high volume play)
- "event": Event hook connection + 3 messages (Palark ICE, 52% positive)

The generated flow includes:
- Connection request note (or empty for networking)
- 3-4 follow-up messages with engagement actions between them
- Non-accept branch (like → visit → endorse → withdraw)
- Proven timing patterns from top campaigns""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "flow_name": {"type": "string", "description": "Campaign name (defaults to 'Project - LinkedIn Type')"},
                "flow_type": {"type": "string", "enum": ["standard", "networking", "product", "volume", "event"], "default": "standard"},
                "instructions": {"type": "string", "description": "Additional instructions for flow generation"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "gs_approve_flow",
        "description": "Mark a generated GetSales flow as approved after user review.",
        "inputSchema": {
            "type": "object",
            "properties": {"sequence_id": {"type": "integer"}},
            "required": ["sequence_id"],
        },
    },
    {
        "name": "gs_list_sender_profiles",
        "description": """List GetSales sender profiles (LinkedIn accounts) available for automation flows.

Call this BEFORE gs_push_to_getsales to let the user choose which LinkedIn accounts to use.
Shows profile names, UUIDs, and which project each sender belongs to.""",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "gs_push_to_getsales",
        "description": """Push an approved flow to GetSales as a DRAFT automation with FULL configuration.

BEFORE calling this, you MUST:
1. Call gs_list_sender_profiles to show available LinkedIn accounts
2. Ask user which sender profiles to use
3. Wait for user to select — NEVER proceed without their choice

Creates the flow with:
- Node tree (connection request + messages + engagement + non-accept branch)
- Sender profiles with rotation strategy
- Schedule (Mon-Fri 9:00-18:00 in target timezone)
- Target leads auto-uploaded from pipeline

Flow is ALWAYS DRAFT — never activated without explicit user approval.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_id": {"type": "integer"},
                "sender_profile_uuids": {"type": "array", "items": {"type": "string"}, "description": "GetSales sender profile UUIDs. Get from gs_list_sender_profiles."},
                "rotation_strategy": {"type": "string", "enum": ["fair", "random", "prior_engagement", "new_sender"], "default": "fair"},
                "workspace_uuid": {"type": "string", "description": "GetSales workspace UUID (folder). Optional."},
                "target_country": {"type": "string", "description": "Country for timezone. E.g. 'United States', 'Germany'"},
            },
            "required": ["sequence_id", "sender_profile_uuids"],
        },
    },
    {
        "name": "gs_activate_flow",
        "description": """Activate a GetSales flow — START sending LinkedIn connection requests to real leads.

CRITICAL: NEVER call without EXPLICIT user approval. User must confirm they reviewed:
1. Flow messages (connection note + all follow-ups)
2. Sender profiles (correct LinkedIn accounts)
3. Target leads
4. Schedule and timezone

Only call when user explicitly says "activate", "start", "launch", or "go live".""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow_uuid": {"type": "string", "description": "GetSales flow UUID"},
                "user_confirmation": {"type": "string", "description": "Quote user's exact words confirming activation"},
            },
            "required": ["flow_uuid", "user_confirmation"],
        },
    },

    # suggest_apollo_filters REMOVED — tam_gather handles filter discovery + preview + confirmation in one tool.
    # When tam_gather is called without confirm_filters, it auto-discovers filters, probes Apollo for total_available,
    # shows cost breakdown, and waits for user to confirm. No separate filter suggestion tool needed.

    # ── Orchestration (2) ──
    {
        "name": "run_full_pipeline",
        "description": "Run the full pipeline end-to-end: gather → blacklist → filter → scrape → analyze (with optional auto-refine). Stops at each checkpoint for approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "source_type": {"type": "string"},
                "filters": {"type": "object"},
                "auto_refine": {"type": "boolean", "default": True},
                "target_accuracy": {"type": "number", "default": 0.9},
            },
            "required": ["project_id", "source_type", "filters"],
        },
    },
    {
        "name": "pipeline_status",
        "description": """Pipeline status — phase, progress, KPIs, timing, targets found, next action.

WHEN USER SAYS: "pipeline status", "how is gathering going", "what's the progress" → call THIS.
DO NOT call get_context for pipeline questions — use pipeline_status with the run_id.

Returns: KPI targets (target_count, contacts_per_company, min_targets), progress (people/targets found, percentages), timing (elapsed, ETA), cost (credits used/remaining).""",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "set_pipeline_kpi",
        "description": """Change pipeline KPI targets. Works on running or paused pipelines.

WHEN USER SAYS: "gather 200 contacts", "I need 50 companies", "set max 5 per company", "change target to 1000" → call THIS.
Returns updated KPIs + cost estimate for remaining work.

Orchestrator reads KPIs from DB each iteration, so changes take effect on the next batch.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "target_count": {"type": "integer", "description": "Target total contacts (e.g. 200)"},
                "min_targets": {"type": "integer", "description": "Target number of target companies"},
                "contacts_per_company": {"type": "integer", "description": "Max contacts per company (e.g. 5)"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "control_pipeline",
        "description": """Pause or resume a running pipeline.

WHEN USER SAYS: "pause", "stop gathering", "hold on", "wait" → action="pause"
WHEN USER SAYS: "resume", "continue", "keep going", "find more" → action="resume"

Pause: pipeline stops gracefully after current batch. All progress saved.
Resume: pipeline continues from where it stopped (same filters, same page offset).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "action": {"type": "string", "enum": ["pause", "resume"]},
            },
            "required": ["run_id", "action"],
        },
    },

    {
        "name": "set_people_filters",
        "description": """Change which roles/titles to search for when extracting contacts from target companies.

WHEN USER SAYS: "I want VP Marketing and CMO", "change roles to HR directors", "search for CTOs only" → call THIS.
Updates people_filters on the pipeline run. Takes effect on next people extraction batch.
People search is FREE (Apollo mixed_people endpoint).""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "person_titles": {"type": "array", "items": {"type": "string"}, "description": "Job titles to search (e.g. ['VP Marketing', 'CMO', 'Head of Marketing'])"},
                "person_seniorities": {"type": "array", "items": {"type": "string"}, "description": "Seniority levels: owner, founder, c_suite, partner, vp, head, director, manager, senior"},
                "contacts_per_company": {"type": "integer", "description": "Override max contacts per company"},
            },
            "required": ["run_id"],
        },
    },

    {
        "name": "run_auto_pipeline",
        "description": """Run the FULL automated pipeline that gathers until target contacts found.

Does everything automatically:
1. Apollo search page 1 → scrape → classify → extract people for targets
2. Exploration: enrich top 5 targets → optimize filters
3. Loop: 4 pages at a time → scrape → classify → extract people
4. Stops when target_count contacts gathered (default 100)
5. Each batch = new iteration (visible in UI)

People extraction runs IN PARALLEL — as soon as a target is found, contacts are gathered.
Pipeline runs in BACKGROUND — returns immediately. Use pipeline_status to track progress.

KPIs are configurable: target_count, contacts_per_company, min_targets.
User can change KPIs mid-run via set_pipeline_kpi, or pause/resume via control_pipeline.

Call AFTER user confirms filters (tam_gather with confirm_filters returned the preview).
Requires: project with offer context, Apollo + OpenAI keys configured.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "Gathering run to auto-continue"},
                "filters": {"type": "object", "description": "Apollo filters (from tam_gather preview)"},
                "target_count": {"type": "integer", "description": "Target total contacts to gather (default 100). User says 'gather 200 contacts' → 200."},
                "contacts_per_company": {"type": "integer", "description": "Max contacts per company (default 3). User says '5 per company' → 5."},
                "min_targets": {"type": "integer", "description": "Min target companies (auto-derived from target_count / contacts_per_company if not set)"},
            },
            "required": ["run_id"],
        },
    },

    {
        "name": "extract_people",
        "description": """Extract contacts (people) from target companies in a pipeline run.

Searches Apollo for 3 contacts per target company. Roles auto-adjusted to offer:
- Payroll offer → VP HR, CHRO, Head of People
- SaaS offer → CTO, VP Engineering
- Fashion → Brand Director, CMO

FREE — uses /mixed_people/api_search (no credits).
Call after targets are confirmed at Checkpoint 2.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "Pipeline run with confirmed targets"},
                "people_per_company": {"type": "integer", "default": 3, "description": "Contacts per company (default 3)"},
            },
            "required": ["run_id"],
        },
    },

    # ── CRM Queries (2) ──
    {
        "name": "query_contacts",
        "description": """Search contacts in CRM with filters. Use this to answer questions like:
- "Which leads need follow-ups?" → query_contacts with needs_followup=true
- "Which replies are warm?" → query_contacts with reply_category=interested
- "Show me contacts from Petr's campaigns" → query_contacts with search or pipeline filter
- "How many contacts do we have?" → query_contacts with no filters

Returns contacts + a CRM link with filters applied so the user can view them in the browser.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "search": {"type": "string", "description": "Search by email, name, company"},
                "has_replied": {"type": "boolean", "description": "Only contacts who replied"},
                "needs_followup": {"type": "boolean", "description": "Contacts needing follow-up"},
                "reply_category": {"type": "string", "description": "Filter by reply type: interested, meeting_request, question, not_interested, out_of_office, wrong_person"},
                "pipeline_run_id": {"type": "integer", "description": "Contacts from a specific pipeline run"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "crm_stats",
        "description": "Get CRM statistics: total contacts, by status, by source, by project. Use this for overview questions like 'how many contacts do I have?'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
            },
        },
    },

    # ── SmartLead Campaign Import (3) ──
    {
        "name": "list_smartlead_campaigns",
        "description": "Browse your SmartLead campaigns. Use this to help the user identify which campaigns belong to their project for blacklisting. Shows campaign name, lead count, status. Pass 'search' to filter by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
            },
        },
    },
    {
        "name": "import_smartlead_campaigns",
        "description": """Import previous campaigns into blacklist.

WHEN USER SAYS: "campaigns with petr", "I launched X before", "previous campaigns include Y" → call THIS.
Loads existing contacts so pipeline knows who NOT to gather again.
Pass rules.contains=["petr"] if user says "campaigns with petr in name".""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project to import into"},
                "rules": {
                    "type": "object",
                    "description": "How to match campaigns",
                    "properties": {
                        "prefixes": {"type": "array", "items": {"type": "string"}, "description": "Campaign name prefixes (e.g. ['ES Global'])"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "SmartLead campaign tags"},
                        "contains": {"type": "array", "items": {"type": "string"}, "description": "Substrings in campaign names"},
                        "exact_names": {"type": "array", "items": {"type": "string"}, "description": "Exact campaign names"},
                    },
                },
            },
            "required": ["project_id", "rules"],
        },
    },
    {
        "name": "set_campaign_rules",
        "description": "Save campaign detection rules on a project. These rules determine which SmartLead campaigns belong to this project for blacklisting and reply tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "rules": {
                    "type": "object",
                    "properties": {
                        "prefixes": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "contains": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "required": ["project_id", "rules"],
        },
    },

    # ── Utility (2) ──
    {
        "name": "estimate_cost",
        "description": "Estimate the cost of a gathering run before starting. Returns credits needed and estimated company count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "description": "Source type (default: apollo.companies.api)"},
                "filters": {"type": "object", "description": "Optional filters (max_pages, per_page)"},
                "target_count": {"type": "integer", "description": "How many target companies you want"},
            },
        },
    },
    {
        "name": "blacklist_check",
        "description": "Quick check: are these domains already in any campaign?",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["domains"],
        },
    },

    # ── Replies (4) ──
    {
        "name": "replies_summary",
        "description": "Get a summary of reply categories for a project. Returns counts per category (interested, meeting_request, question, not_interested, ooo, wrong_person, unsubscribe). Use this when the user asks 'how are my campaigns doing?' or 'what replies did I get?'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project name to filter replies for"},
            },
            "required": ["project_name"],
        },
    },
    {
        "name": "replies_list",
        "description": "List replies filtered by category, project, or search. Returns reply cards with lead info, message preview, and category. Use for 'show me warm replies' or 'which leads are interested?'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category: interested, meeting_request, question, not_interested, out_of_office, wrong_person, unsubscribe, other"},
                "project_name": {"type": "string", "description": "Project name to filter replies for"},
                "search": {"type": "string", "description": "Search by lead name, email, or company"},
                "needs_reply": {"type": "boolean", "description": "Only show replies that need operator action"},
                "page": {"type": "integer", "default": 1, "description": "Page number"},
            },
        },
    },
    {
        "name": "replies_followups",
        "description": "List leads that need follow-up. Returns leads where the last message was from us and no reply received within the follow-up window.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project name to filter follow-ups for"},
                "page": {"type": "integer", "default": 1, "description": "Page number"},
            },
        },
    },
    {
        "name": "replies_deep_link",
        "description": "Generate a deep link URL to view specific replies in the browser UI. Use when the user asks to 'see' or 'open' replies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project name for the deep link"},
                "category": {"type": "string", "description": "Optional category filter for the link"},
                "tab": {"type": "string", "description": "Optional tab name: all, meetings, interested, questions, other, not_interested, ooo, wrong_person, unsubscribe, followups"},
            },
            "required": ["project_name"],
        },
    },
    # ── User Feedback & Editing Tools ──
    {
        "name": "smartlead_edit_sequence",
        "description": """Edit a specific step of a generated sequence. User can change subject, body, or both.
Changes are saved to DB and pushed to SmartLead if campaign already created.

Use when user says: "change the subject of email 1", "rewrite email 3 body", "add a case study to email 2".""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_id": {"type": "integer", "description": "The generated sequence ID"},
                "step_number": {"type": "integer", "description": "Which email step to edit (1-5)"},
                "subject": {"type": "string", "description": "New subject line (omit to keep current)"},
                "body": {"type": "string", "description": "New email body (omit to keep current). Use <br> for line breaks."},
            },
            "required": ["sequence_id", "step_number"],
        },
    },
    {
        "name": "edit_campaign_accounts",
        "description": "Change the email sending accounts on a SmartLead campaign. User can add or replace accounts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer", "description": "SmartLead campaign ID (external_id)"},
                "email_account_ids": {"type": "array", "items": {"type": "integer"}, "description": "New list of SmartLead email account IDs"},
            },
            "required": ["campaign_id", "email_account_ids"],
        },
    },
    {
        "name": "override_company_target",
        "description": """Override a company's target/not-target status with user feedback.

Use when user says: "this company IS a target" or "remove this, not a match".
Stores override + reasoning for learning.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "integer", "description": "DiscoveredCompany ID"},
                "is_target": {"type": "boolean", "description": "True = target, False = not target"},
                "reasoning": {"type": "string", "description": "Why the user thinks this should be changed"},
            },
            "required": ["company_id", "is_target"],
        },
    },
    {
        "name": "provide_feedback",
        "description": """Store feedback to improve pipeline. Use feedback_type to categorize:
- "targets": user says which companies are/aren't targets → then call tam_re_analyze
- "filters": user wants different Apollo filters
- "sequence": user wants to change email content
- "general": anything else

WHEN USER SAYS: "these aren't targets", "exclude software companies", "wrong classifications" → call THIS with feedback_type="targets", then tam_re_analyze.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "feedback_type": {"type": "string", "enum": ["sequence", "filters", "analysis", "targets", "general"]},
                "feedback_text": {"type": "string", "description": "The user's feedback in their own words"},
                "context": {"type": "object", "description": "Optional: step_number, company_id, filter_name, etc."},
            },
            "required": ["project_id", "feedback_type", "feedback_text"],
        },
    },
    {
        "name": "activate_campaign",
        "description": """Activate a campaign — START sending to real leads.

WHEN USER SAYS: "activate", "launch", "start the campaign", "go live" → call THIS.
NEVER call without explicit user approval.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer", "description": "SmartLead campaign ID"},
                "user_confirmation": {"type": "string", "description": "Quote user's exact words confirming activation"},
            },
            "required": ["campaign_id", "user_confirmation"],
        },
    },
]
