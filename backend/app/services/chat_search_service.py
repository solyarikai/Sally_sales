"""
Chat-based search service — parses natural language into search parameters
and classifies feedback for knowledge updates.

The chat API is designed as a universal interface: any client (web UI, Slack,
Telegram) sends a text message and receives a structured action response.
"""
import json
import logging
from typing import Optional, Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)

# All actions the chat can route to
CHAT_ACTIONS = [
    "start_search",      # Launch segment-based search pipeline
    "stop",              # Stop running pipeline
    "status",            # Show pipeline status
    "push",              # Push contacts to SmartLead
    "show_targets",      # List top target companies
    "show_stats",        # Performance analytics
    "search",            # New ICP-based search (legacy AI-random)
    "lookup_domain",     # Look up everything known about specific domains
    "show_config",       # Show current search config (segments/geos/templates)
    "edit_config",       # Edit search config via AI
    "show_knowledge",    # Display knowledge base entries
    "update_knowledge",  # Add/edit a knowledge base entry via natural language
    "ask",               # General question answered using KB context
    "verify_emails",     # Run Findymail verification on contacts
    "show_verification_stats",  # Show email verification stats
    "show_segments",     # Show segment breakdown across pipeline
    "toggle_verification",  # Enable/disable Findymail for project
    "show_contacts",     # Show CRM contacts with filters, open CRM view
    "clay_export",       # Export TAM from Clay — find companies matching ICP, export to Google Sheets
    "clay_people",       # Search Clay for contacts at known target companies
    "clay_gather",       # Full Clay pipeline: find companies + find contacts + promote to CRM
    "info",              # General question / unknown
]

# Fallback segment keys when no DB config exists (Deliryo defaults)
FALLBACK_SEGMENTS = [
    "real_estate", "investment", "legal", "migration",
    "crypto", "family_office", "importers",
]

FALLBACK_GEOS_STR = (
    "real_estate: dubai, turkey, cyprus, thailand_bali, montenegro, spain_portugal, greece, london, israel, italy, global_aggregator\n"
    "investment: moscow, switzerland, singapore, dubai_difc\n"
    "legal: moscow, cyprus_legal, uae_legal, estonia, georgia_legal, serbia_legal, offshore, london, malta, israel\n"
    "migration: portugal_gv, spain_gv, greece_gv, montenegro_rp, caribbean_cbi, eb5_usa, uae_visa, general_migration, malta_rp, uk_visa, italy_gv\n"
    "crypto: dubai_crypto, moscow_crypto\n"
    "family_office: moscow_fo, dubai_fo, switzerland_fo, singapore_fo, ppli_insurance, private_banks_ru\n"
    "importers: moscow_import"
)


class ChatSearchService:
    """Parses chat messages into search intents and feedback.

    Core method: parse_chat_action() — the universal intent parser.
    Any input source (UI, Slack, Telegram) calls this to get a structured action.
    """

    async def parse_chat_action(
        self,
        message: str,
        project_context: Optional[Dict[str, Any]] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Parse any user message into a structured action using Gemini 2.5 Pro.

        This is the universal entry point — works for pipeline commands,
        analytics queries, search instructions, and general questions.

        Returns:
            {
                "action": str,           # one of CHAT_ACTIONS
                "engine": str|None,      # "yandex" | "google" | "both"
                "segments": list|None,   # segment keys to search
                "geos": list|None,       # geo keys to filter
                "max_queries": int|None,
                "target_goal": int|None,
                "skip_smartlead_push": bool,
                "stats_scope": str|None, # "segment"|"geo"|"engine"|"cost"|"funnel"|"top_queries"
                "reply": str,            # Human-readable response
            }
        """
        project_block = ""
        if project_context:
            parts = []
            parts.append(f"PROJECT: {project_context.get('project_name', 'Unknown')} (id={project_context.get('project_id', '?')})")
            parts.append(f"TARGETS: {project_context.get('total_targets', 0)} targets from {project_context.get('total_discovered', 0)} discovered companies")
            parts.append(f"CONTACTS IN CAMPAIGNS: {project_context.get('contacts_in_campaigns', 0)}")
            parts.append(f"UNPUSHED CONTACTS: {project_context.get('unpushed_contacts', 0)}")
            if project_context.get("pipeline_running"):
                parts.append(f"PIPELINE STATUS: running (phase: {project_context.get('pipeline_phase', 'unknown')})")
            else:
                parts.append("PIPELINE STATUS: not running")
            if project_context.get("top_segments"):
                parts.append(f"TOP SEGMENTS BY TARGETS: {project_context['top_segments']}")
            if project_context.get("cost_summary"):
                parts.append(f"COST SPENT: {project_context['cost_summary']}")
            verif = project_context.get("verification", {})
            if verif:
                parts.append(f"FINDYMAIL: {'enabled' if verif.get('findymail_enabled') else 'disabled'}, "
                           f"verified={verif.get('verified_emails', 0)}, valid={verif.get('valid', 0)}, "
                           f"invalid={verif.get('invalid', 0)}, cost=${verif.get('cost_usd', 0):.2f}")
            seg_breakdown = project_context.get("segments_breakdown", [])
            if seg_breakdown:
                seg_summary = ", ".join(f"{s['segment']}({s['targets']} targets)" for s in seg_breakdown[:5])
                parts.append(f"SEGMENTS: {seg_summary}")
            if project_context.get("knowledge_summary"):
                parts.append(f"\nPROJECT KNOWLEDGE BASE:\n{project_context['knowledge_summary'][:2000]}")
            project_block = "\n".join(parts)

        # Build dynamic segments/geos from project's search_config (if available)
        search_config = project_context.get("search_config", {}) if project_context else {}
        config_segments = search_config.get("segments", {})

        if config_segments:
            available_segments = list(config_segments.keys())
            geos_lines = []
            for seg_key, seg_data in config_segments.items():
                geos = list(seg_data.get("geos", {}).keys())
                if geos:
                    geos_lines.append(f"{seg_key}: {', '.join(geos)}")
            available_geos_str = "\n".join(geos_lines) if geos_lines else "No geos configured"
        else:
            available_segments = FALLBACK_SEGMENTS
            available_geos_str = FALLBACK_GEOS_STR

        system_prompt = f"""You are an AI assistant for a lead generation platform. You parse user messages into structured actions.

{f"CURRENT PROJECT STATE:{chr(10)}{project_block}" if project_block else "No project selected."}

AVAILABLE ACTIONS:
1. "start_search" — Launch data gathering pipeline with template-based search.
   Parameters: engine (yandex|google|both), segments (list), geos (list), max_queries (int), target_goal (int), skip_smartlead_push (bool)
   Use when user wants to search/gather/find/run/launch searching for companies/contacts.

2. "stop" — Stop a running pipeline. Use when user says stop/cancel/halt.

3. "status" — Show pipeline status. Use when user asks about progress/status/what's running.

4. "push" — Push contacts to SmartLead campaigns. Use when user says push/send to smartlead/campaigns.

5. "show_targets" — Show top target companies. Use when user asks to see/show/list targets/companies.

6. "show_stats" — Show performance analytics.
   Parameter: stats_scope (segment|geo|engine|cost|funnel|top_queries)
   Use when user asks about stats/numbers/performance/how many/cost/conversion/funnel.

7. "search" — Launch new ICP-based AI search (not template-based). Use only when user describes a NEW type of company to find.

8. "lookup_domain" — Look up all known data about specific domain(s).
   Use when user mentions a domain name (contains a dot, like company.com) and asks to find/show/lookup/check history/info about it.
   Extract ALL domain names from the message into the "domains" field.

9. "show_config" — Show current search configuration (segments, geos, templates).
   Use when user asks to see/show/display config/configuration/segments/search setup.

10. "edit_config" — Edit search configuration.
    Use when user wants to add/remove/change segments, geos, templates, or keywords.
    The "edit_instruction" field should contain the user's edit request as-is.

11. "show_knowledge" — Show project knowledge base entries.
    Use when user asks to see/show/display knowledge, KB, notes, ICP details, outreach strategy.
    Parameter: kb_category (icp|search|outreach|contacts|gtm|notes|null for all)

12. "update_knowledge" — Add or edit a knowledge base entry.
    Use when user says "remember", "note", "add to KB", "update ICP", "set outreach tone", or provides info about ICP/outreach/contacts that should be stored.
    Parameters: kb_category, kb_key, kb_value (the content to store), kb_title

13. "ask" — Answer a general question using project knowledge context.
    Use when user asks a question about the project, strategy, ICP, or needs advice based on existing data.

14. "verify_emails" — Run Findymail email verification on contacts.
    Use when user says "verify emails", "run findymail", "check emails", "validate emails".

15. "show_verification_stats" — Show email verification statistics.
    Use when user asks "how many verified?", "email quality", "findymail stats", "verification results".

16. "show_segments" — Show segment breakdown across the pipeline.
    Use when user asks "show segments", "segment breakdown", "funnel by segment", "how many family office?".

17. "toggle_verification" — Enable or disable Findymail for the project.
    Use when user says "enable findymail", "turn on verification", "disable findymail", "turn off verification".
    Set "toggle_value" to true (enable) or false (disable).

18. "show_contacts" — Show CRM contacts or open filtered CRM view.
    Use when user asks about contacts, wants to see/view contacts, asks "show me contacts", "how many contacts replied",
    "open Family Office RU contacts", "which campaigns have contacts", "show contacts in outreach", etc.
    Parameters: contact_segment (optional), contact_geo (optional "RU"|"Global"), contact_status (optional),
    contact_campaign (optional), contact_replied (optional bool), contact_source (optional).
    The reply should summarize the contacts and tell user a CRM view is opening.

19. "clay_export" — Export TAM from Clay.com. Searches Clay's company database for companies matching an ICP description, creates a table, and exports to Google Sheets. NO credits used.
    Use when user says "find in clay", "clay export", "export from clay", "search clay for", "find companies in clay",
    "gather TAM from clay", "clay TAM", or describes companies to find and mentions clay/Clay.
    Parameter: "clay_icp" — the ICP description text (what kind of companies to find).
    The reply should confirm the Clay export is starting and mention it takes 3-5 minutes.

20. "clay_people" — Search Clay for CONTACTS (people) at known target companies. Uses company domains already in the pipeline.
    Use when user says "find contacts", "get people at companies", "clay people search", "find contacts at clay companies",
    "search contacts in clay", "get decision makers", or asks for contacts/people at target companies.
    The reply should confirm people search is starting with domains from the pipeline.

21. "clay_gather" — Full Clay pipeline: find companies matching a segment, find contacts at those companies, apply office rules, save to CRM as draft contacts.
    Use when user says "gather X contacts from Y companies in Z segment", "gather segment", "full clay pipeline", "find companies and contacts",
    or describes both a segment/ICP AND a desired number of companies/contacts in one message.
    IMPORTANT: Any message that mentions a NUMBER of contacts/companies/people AND a segment/industry/vertical/ICP description is ALWAYS clay_gather, NOT ask.
    Examples that MUST be clay_gather: "30 contacts from payroll segment", "find 50 people in fintech", "100 contacts in europe from gaming companies",
    "get me 20 leads from crypto exchanges", "N contacts from X segment in Y region", "10 companies in payroll".
    If the message contains a number + (contacts|companies|people|leads) + any segment description → clay_gather.
    Parameters: "clay_segment" (string — the segment/ICP description), "clay_company_count" (int, default 10), "clay_contact_count" (int, default 30).
    The reply should confirm the gather pipeline is starting with the segment and counts.

22. "info" — Fallback for anything that doesn't map to any action. Reply conversationally.

AVAILABLE SEGMENTS: {', '.join(available_segments)}

AVAILABLE GEOS BY SEGMENT:
{available_geos_str}

RULES:
- PRIORITY: If message contains a number + "contacts"/"companies"/"people"/"leads" + a segment/industry name → ALWAYS use "clay_gather", NEVER "ask".
- ALWAYS return valid JSON, no markdown fences.
- For "start_search": default engine is "yandex" (cheap at $0.25/1K queries). Only use "google" ($3.50/1K) when user explicitly asks for it or mentions English/international queries.
- For "start_search": default skip_smartlead_push is false (push after search).
- If user says "all segments" or doesn't specify, set segments to null (means all).
- If user says "all geos" or doesn't specify geos, set geos to null (means all for selected segments).
- max_queries defaults to 1500 unless user specifies.
- target_goal defaults to 500 unless user specifies.
- The "reply" should be 1-2 sentences confirming the action, with specifics (engine, segments, budget).
- NEVER ask clarifying questions. Always pick the best action from context.
- Understand Russian and English equally well.

Respond ONLY with JSON:
{{
    "action": "start_search|stop|status|push|show_targets|show_stats|search|lookup_domain|show_config|edit_config|show_knowledge|update_knowledge|ask|verify_emails|show_verification_stats|show_segments|toggle_verification|show_contacts|clay_export|clay_people|clay_gather|info",
    "engine": "yandex|google|both|null",
    "segments": ["segment_key", ...] or null,
    "geos": ["geo_key", ...] or null,
    "max_queries": 1500,
    "target_goal": 500,
    "skip_smartlead_push": false,
    "stats_scope": "segment|geo|engine|cost|funnel|top_queries|null",
    "domains": ["domain1.com", "domain2.com"] or null,
    "edit_instruction": "user's config edit request as-is, or null",
    "kb_category": "icp|search|outreach|contacts|gtm|notes|null",
    "kb_key": "key name or null",
    "kb_value": "content to store or null",
    "kb_title": "human-readable title or null",
    "toggle_value": true,
    "contact_segment": "segment name or null",
    "contact_geo": "RU|Global|null",
    "contact_status": "status or null",
    "contact_campaign": "campaign name or null",
    "contact_replied": true,
    "contact_source": "source or null",
    "clay_icp": "ICP description for Clay export or null",
    "clay_segment": "segment/ICP description for clay_gather or null",
    "clay_company_count": 10,
    "clay_contact_count": 30,
    "reply": "..."
}}"""

        user_parts = []
        if context:
            for msg in context[-6:]:  # Last 6 messages for context
                role = msg.get("role", "user")
                user_parts.append(f"[{role}]: {msg.get('content', '')}")
        user_parts.append(f"[user]: {message}")
        user_prompt = "\n".join(user_parts)

        try:
            from app.services.gemini_client import is_gemini_available, gemini_generate, extract_json_from_gemini

            if is_gemini_available():
                gen_result = await gemini_generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=1000,
                )
                raw = extract_json_from_gemini(gen_result["content"])
                logger.info(f"Chat action parsing: {gen_result['tokens']['total']} tokens, model={gen_result['model']}")
                if not raw or not raw.strip():
                    logger.warning("Gemini returned empty content for intent parsing, defaulting to ask")
                    return {
                        "action": "ask",
                        "reply": "",
                        "engine": None, "segments": None, "geos": None,
                        "max_queries": None, "target_goal": None,
                        "skip_smartlead_push": True, "stats_scope": None, "domains": None,
                    }
                result = json.loads(raw)
            else:
                # OpenAI fallback
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    max_tokens=1000,
                )
                result = json.loads(response.choices[0].message.content)

            # Validate action
            if result.get("action") not in CHAT_ACTIONS:
                result["action"] = "ask"

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini JSON response: {e}, defaulting to ask")
            return {
                "action": "ask",
                "reply": "",
                "engine": None, "segments": None, "geos": None,
                "max_queries": None, "target_goal": None,
                "skip_smartlead_push": True, "stats_scope": None, "domains": None,
            }
        except Exception as e:
            logger.error(f"Failed to parse chat action: {e}", exc_info=True)
            return {
                "action": "ask",
                "reply": "",
                "engine": None, "segments": None, "geos": None,
                "max_queries": None, "target_goal": None,
                "skip_smartlead_push": True, "stats_scope": None, "domains": None,
            }

    async def parse_search_intent(
        self,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Parse a natural language message into structured search parameters.
        Receives project context (existing results, knowledge) for smart strategy.

        Returns:
            {
                "target_segments": str,  # formatted for project.target_segments
                "project_name": str,
                "geography": str,
                "industry": str,
                "reply": str,  # AI reply to show user
            }
        """
        # Build project context block
        project_block = ""
        if project_context:
            parts = [f"PROJECT: {project_context.get('project_name', 'Unknown')}"]
            if project_context.get("existing_target_segments"):
                parts.append(f"CURRENT TARGET DEFINITION:\n{project_context['existing_target_segments']}")
            parts.append(f"RESULTS SO FAR: {project_context.get('total_results_analyzed', 0)} companies analyzed, {project_context.get('total_targets_found', 0)} targets found")
            if project_context.get("top_targets"):
                parts.append(f"TOP TARGETS: {', '.join(project_context['top_targets'][:10])}")
            knowledge = project_context.get("knowledge", {})
            if knowledge.get("anti_keywords"):
                parts.append(f"EXCLUDED PATTERNS: {', '.join(knowledge['anti_keywords'][:15])}")
            if knowledge.get("industry_keywords"):
                parts.append(f"CONFIRMED KEYWORDS: {', '.join(knowledge['industry_keywords'][:15])}")
            project_block = "\n".join(parts)

        system_prompt = f"""You are a search assistant that operates within a project scope. The user describes target companies and you convert this into structured search parameters to IMMEDIATELY launch a web scraping pipeline.

{f"EXISTING PROJECT CONTEXT:{chr(10)}{project_block}" if project_block else "This is a new project with no prior data."}

Your task:
1. Create/update a "target_segments" text block (ICP document) based on the user's description
2. If the project already has results, consider them when refining the target definition
3. Generate a SHORT action confirmation reply

CRITICAL RULES:
- You MUST ALWAYS return a non-empty "target_segments" string. Never return null or empty.
- NEVER ask clarifying questions. Interpret and start searching immediately.
- Expand acronyms (HNWI = High Net Worth Individual, SaaS = Software as a Service, etc.)
- If the project already has targets, your reply should acknowledge existing data and what the new search will add.
- The "reply" MUST be 1 sentence confirming the search is starting.

Format target_segments as a structured document:
- КОМПАНИЯ (company type, size, characteristics)
- УСЛУГИ (services they provide)
- ГЕОГРАФИЯ (geography/location)
- ЯЗЫК (website language)

Respond ONLY with valid JSON (no markdown fences):
{{
    "target_segments": "...",
    "project_name": "...",
    "geography": "...",
    "industry": "...",
    "reply": "Searching for [what] in [where] — results will appear as websites are analyzed."
}}"""

        # Build user prompt with conversation context
        user_parts = []
        if context:
            for msg in context:
                role = msg.get("role", "user")
                user_parts.append(f"[{role}]: {msg.get('content', '')}")
        user_parts.append(f"[user]: {message}")
        user_prompt = "\n".join(user_parts)

        try:
            from app.services.gemini_client import is_gemini_available, gemini_generate, extract_json_from_gemini

            if is_gemini_available():
                # Gemini 2.5 Pro — better at understanding complex intents
                gen_result = await gemini_generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=1500,
                )
                raw = extract_json_from_gemini(gen_result["content"])
                logger.info(f"Gemini intent parsing: {gen_result['tokens']['total']} tokens (thinking: {gen_result['tokens'].get('thinking', 0)})")
                result = json.loads(raw)
            else:
                # OpenAI fallback
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ] if not context else [
                        {"role": "system", "content": system_prompt},
                        *context,
                        {"role": "user", "content": message},
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    max_tokens=1500,
                )
                result = json.loads(response.choices[0].message.content)

            return result

        except Exception as e:
            logger.error(f"Failed to parse search intent: {e}")
            return {
                "target_segments": None,
                "project_name": None,
                "reply": f"I couldn't understand your request. Could you describe the companies you're looking for in more detail?",
                "error": str(e),
            }

    async def parse_feedback(
        self,
        message: str,
        project_knowledge: Optional[Dict[str, Any]] = None,
        target_segments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classify user feedback and return knowledge updates.

        Returns:
            {
                "action": "update_knowledge" | "adjust_search" | "info",
                "reply": str,
                "knowledge_updates": {
                    "anti_keywords": [...],
                    "industry_keywords": [...],
                    "good_query_patterns": [...],
                    "bad_query_patterns": [...],
                }
            }
        """
        import openai

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = f"""You are a search feedback classifier. The user is running a company search and providing feedback about results.

Current search target: {target_segments or 'Not specified'}
Current knowledge: {json.dumps(project_knowledge or {}, ensure_ascii=False)[:500]}

Classify the user's feedback and determine what knowledge updates to make.

Possible actions:
- "update_knowledge": User wants to exclude/include certain types of companies
- "adjust_search": User wants to change search parameters
- "info": User is asking a question, no action needed

Respond in JSON:
{{
    "action": "update_knowledge" | "adjust_search" | "info",
    "reply": "...",
    "knowledge_updates": {{
        "anti_keywords": ["keywords to exclude"],
        "industry_keywords": ["keywords to prioritize"],
        "good_query_patterns": ["effective query patterns"],
        "bad_query_patterns": ["ineffective query patterns"]
    }}
}}"""

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=800,
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            logger.error(f"Failed to parse feedback: {e}")
            return {
                "action": "info",
                "reply": "I noted your feedback. The search will continue with current settings.",
                "knowledge_updates": {},
            }


chat_search_service = ChatSearchService()
