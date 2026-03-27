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
        "description": "Create a new sales project. BEFORE calling this, you MUST know the user's offer — ask for their company website or a description of what they sell. Without this, sequences will be generic garbage. Scrape the website if provided.",
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

    # ── Pipeline (9) ──
    {
        "name": "tam_gather",
        "description": """Phase 1: Gather companies from a source.

For Apollo API source: if the user gives you a natural language description instead of explicit filters,
FIRST call suggest_apollo_filters to auto-discover optimal keywords, THEN call tam_gather with the result.

User says "find IT consulting in London, about 10 targets" → you:
1. Call suggest_apollo_filters(query="IT consulting in London", target_count=10)
2. Take the suggested_filters from the response
3. Call tam_gather(project_id=X, source_type="apollo.companies.api", filters=suggested_filters, target_count=10)

The user only needs to tell you: WHAT companies, WHERE, and HOW MANY targets.
You figure out the Apollo filters automatically. Never show filter details to the user.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project to gather for"},
                "source_type": {
                    "type": "string",
                    "enum": ["apollo.companies.api", "apollo.people.emulator", "apollo.companies.emulator",
                             "clay.companies.emulator", "clay.people.emulator",
                             "google_sheets.companies.manual", "csv.companies.manual", "manual.companies.manual"],
                    "description": "Source to gather from.",
                },
                "target_count": {"type": "integer", "description": "How many TARGET companies the user wants. System auto-calculates pages needed."},
                "filters": {
                    "type": "object",
                    "description": "Apollo filters — use output from suggest_apollo_filters",
                    "properties": {
                        "q_organization_keyword_tags": {"type": "array", "items": {"type": "string"}},
                        "organization_locations": {"type": "array", "items": {"type": "string"}},
                        "organization_num_employees_ranges": {"type": "array", "items": {"type": "string"}},
                        "max_pages": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "organization_latest_funding_stage_cd": {"type": "array", "items": {"type": "string"}},
                        "domains": {"type": "array", "items": {"type": "string"}},
                        "sheet_url": {"type": "string"},
                    },
                },
                "query": {"type": "string", "description": "Natural language query — triggers auto-filter discovery if no keywords provided"},
                "reuse_run_id": {"type": "integer", "description": "Reuse filters from a previous run. User says 'same filters, more targets'"},
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
Segments: CAPS_LOCKED labels (IT_OUTSOURCING, SAAS_COMPANY, AGENCY, etc.)""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "prompt_text": {"type": "string", "description": "ICP description for via negativa analysis. Built from project knowledge if omitted."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "tam_re_analyze",
        "description": """Re-run Phase 5 with an adjusted prompt. Use when YOU (Opus) reviewed GPT's target list at Checkpoint 2 and found accuracy < 90%.

Resets the run to scraped phase and re-analyzes all companies with the new prompt.
Iterate until GPT's results meet your quality bar.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "prompt_text": {"type": "string", "description": "Improved ICP prompt based on what GPT got wrong"},
            },
            "required": ["run_id", "prompt_text"],
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
    {
        "name": "send_test_email",
        "description": """Send a test email via SmartLead's native API. Uses the user's email as recipient.
Auto-resolves sending account and lead for variable substitution.

Call this after god_push_to_smartlead to let the user preview the email in their inbox.
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
        "name": "edit_sequence_step",
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
        "description": """Store user feedback about any pipeline aspect. General-purpose feedback tool.

Use when user says: "Apollo filters should include X", "sequence tone is too formal", "focus more on Y segment".
Stored per-project, used to improve future runs. Most recent feedback takes priority over older.""",
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
        "description": """Activate a SmartLead campaign — START sending emails to real leads.

CRITICAL: NEVER call without EXPLICIT user approval. User must confirm they reviewed:
1. Sequence content (all steps)
2. Leads list (target companies)
3. Campaign settings (timezone, accounts)
4. Test email (received and correct)

Only call when user explicitly says "activate", "start", or "go live".""",
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
