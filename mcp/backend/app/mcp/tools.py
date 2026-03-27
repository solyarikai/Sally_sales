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
        "description": """Push an approved sequence to SmartLead as a DRAFT campaign with FULL configuration.

BEFORE calling this, you MUST ask the user:
1. "Which email accounts should I use?" — call list_email_accounts first to show options
2. The schedule will be set to 9:00-18:00 Mon-Fri in the TARGET country's timezone (from the gathering geo filter)

The campaign is created with production settings:
- Plain text emails (no HTML)
- No open/click tracking (deliverability)
- Stop on reply
- 40% follow-up rate
- 3 min between emails
- 100 max new leads/day
- Mon-Fri 9:00-18:00 in target timezone

Campaign is ALWAYS DRAFT — never activated, never adds leads.""",
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

Call this BEFORE god_push_to_smartlead to let the user choose which accounts to use.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "integer", "description": "Optional: show accounts from a specific campaign"},
            },
        },
    },

    # ── Filter Intelligence (1) ──
    {
        "name": "suggest_apollo_filters",
        "description": """INTERNAL: Auto-discover optimal Apollo filters for a natural language query.

Call this AUTOMATICALLY before tam_gather — the user should NEVER be asked about Apollo keywords,
industries, or filter details. That's our job.

User says: "find IT consulting in London"
You call: suggest_apollo_filters(query="IT consulting in London", target_count=10)
System: probes Apollo (1 credit) → discovers real taxonomy → returns optimal filters
You call: tam_gather with the suggested filters

The user sees: "Found 25 matching companies, searching for ~10 targets..."
The user does NOT see: keyword lists, industry codes, or filter JSON.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language description of companies to find"},
                "target_count": {"type": "integer", "default": 10, "description": "How many target companies the user wants"},
            },
            "required": ["query"],
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
        "description": "Browse your SmartLead campaigns. Use this to help the user identify which campaigns belong to their project for blacklisting. Shows campaign name, lead count, status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search campaigns by name (optional)"},
            },
        },
    },
    {
        "name": "import_smartlead_campaigns",
        "description": "Import contacts from SmartLead campaigns into MCP CRM as blacklist. The user tells you which campaigns to import — by name prefix, tags, or exact names. This loads their existing contacts so the pipeline knows who NOT to gather again.",
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
