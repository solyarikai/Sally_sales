"""MCP Tool definitions — 26 tools for the LeadGen pipeline."""

TOOLS = [
    # ── Account (3) ──
    {
        "name": "setup_account",
        "description": "Create a new MCP account and get an API token. The token is shown once — save it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Your email address"},
                "name": {"type": "string", "description": "Your name"},
            },
            "required": ["email", "name"],
        },
    },
    {
        "name": "configure_integration",
        "description": "Connect an external service (smartlead, apollo, findymail, openai, gemini) by providing your API key. Tests the connection automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "integration_name": {"type": "string", "enum": ["smartlead", "apollo", "findymail", "openai", "gemini"]},
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
        "description": "Create a new sales project with ICP definition and sender identity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
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

    # ── Pipeline (9) ──
    {
        "name": "tam_gather",
        "description": """Phase 1: Gather companies from a source. IMPORTANT: Before calling this tool, you MUST have these essential filters clarified with the user. If any are missing, ASK the user first — do NOT guess or use defaults silently.

ESSENTIAL FILTERS (must be explicit):
- locations: Which countries/cities to search
- keywords/industry: What type of companies
- employee_count_min / employee_count_max: Company size range (e.g. 10-200)
- max_pages: How many pages to fetch (controls credit spend, 1 credit/page for Apollo API)

EXAMPLE: User says "find SaaS companies in Germany" → You MUST ask: "What company size? (e.g. 10-50, 50-200, 200-1000) And how many pages max? (each page = 25 companies, 1 Apollo credit)"

Only for manual/CSV/sheets sources can you skip size and page filters.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project to gather for"},
                "source_type": {
                    "type": "string",
                    "enum": ["apollo.companies.api", "apollo.people.emulator", "apollo.companies.emulator",
                             "clay.companies.emulator", "clay.people.emulator",
                             "google_sheets.companies.manual", "csv.companies.manual", "manual.companies.manual"],
                    "description": "Source to gather from. Apollo API costs 1 credit/page. Emulators are free. Manual/CSV/Sheets are free.",
                },
                "filters": {
                    "type": "object",
                    "description": "Source-specific filters",
                    "properties": {
                        "q_organization_keyword_tags": {"type": "array", "items": {"type": "string"}, "description": "REQUIRED for Apollo. Industry keywords (e.g. ['SaaS', 'fintech'])"},
                        "organization_locations": {"type": "array", "items": {"type": "string"}, "description": "REQUIRED for Apollo. Countries or cities (e.g. ['Germany', 'United Kingdom'])"},
                        "organization_num_employees_ranges": {"type": "array", "items": {"type": "string"}, "description": "REQUIRED for Apollo. Size ranges in 'min,max' format (e.g. ['11,50', '51,200'])"},
                        "max_pages": {"type": "integer", "description": "REQUIRED for Apollo. Max pages to fetch (1 credit each). Default: 4. Each page = 25 companies."},
                        "per_page": {"type": "integer", "description": "Results per page (default: 25, max: 100)"},
                        "organization_latest_funding_stage_cd": {"type": "array", "items": {"type": "string"}, "description": "Optional. Funding stages (e.g. ['seed', 'series_a', 'series_b'])"},
                        "domains": {"type": "array", "items": {"type": "string"}, "description": "For manual source: list of domains"},
                        "sheet_url": {"type": "string", "description": "For Google Sheets source: sheet URL"},
                    },
                },
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
        "description": "Phase 5: AI analysis to identify target companies. Optionally auto-refines until target accuracy reached. Creates Checkpoint 2 gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "prompt_text": {"type": "string", "description": "ICP analysis prompt (built from project knowledge if omitted)"},
                "auto_refine": {"type": "boolean", "default": False, "description": "Enable self-refinement loop"},
                "target_accuracy": {"type": "number", "default": 0.9, "description": "Target accuracy for refinement (0-1)"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_prepare_verification",
        "description": "Creates Checkpoint 3 with FindyMail cost estimate before spending credits.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_run_verification",
        "description": "Phase 6: Run FindyMail email verification on approved targets. COSTS CREDITS.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },
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

    # ── GOD_SEQUENCE (5) ──
    {
        "name": "god_score_campaigns",
        "description": "Score and rank campaigns by quality (warm reply rate, meetings, volume).",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
        },
    },
    {
        "name": "god_extract_patterns",
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
        "name": "god_generate_sequence",
        "description": "Generate a 5-step email sequence using extracted patterns + project knowledge.",
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
        "name": "god_approve_sequence",
        "description": "Mark a generated sequence as approved.",
        "inputSchema": {
            "type": "object",
            "properties": {"sequence_id": {"type": "integer"}},
            "required": ["sequence_id"],
        },
    },
    {
        "name": "god_push_to_smartlead",
        "description": "Push an approved sequence to SmartLead as a DRAFT campaign. Never activates or adds leads.",
        "inputSchema": {
            "type": "object",
            "properties": {"sequence_id": {"type": "integer"}},
            "required": ["sequence_id"],
        },
    },

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
        "description": "Get the current status of a pipeline run: phase, progress, next action needed.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "integer"}},
            "required": ["run_id"],
        },
    },

    # ── Utility (2) ──
    {
        "name": "estimate_cost",
        "description": "Estimate the cost of a gathering run before starting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string"},
                "filters": {"type": "object"},
            },
            "required": ["source_type", "filters"],
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
]
