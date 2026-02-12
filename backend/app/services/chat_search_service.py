"""
Chat-based search service — parses natural language into search parameters
and classifies feedback for knowledge updates.
"""
import json
import logging
from typing import Optional, Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatSearchService:
    """Parses chat messages into search intents and feedback."""

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
