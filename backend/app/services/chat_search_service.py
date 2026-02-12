"""
Chat-based search service — unified intent classification for search, refine, and questions.

Single entry point: classify_and_process() handles all chat messages within a project scope.
"""
import json
import logging
from typing import Optional, Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatSearchService:
    """Classifies chat messages into search/refine/question intents."""

    async def classify_and_process(
        self,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        project_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Unified intent classification. Returns:
        {
            "intent": "search" | "refine" | "question",
            "target_segments": str | null,
            "knowledge_updates": {
                "anti_keywords": [], "industry_keywords": [],
                "good_query_patterns": [], "bad_query_patterns": []
            },
            "reply": str,
            "suggestions": [str, ...]
        }
        """
        has_results = False
        project_block = ""
        if project_context:
            has_results = (project_context.get("total_results_analyzed", 0) > 0)
            parts = [f"PROJECT: {project_context.get('project_name', 'Unknown')}"]
            if project_context.get("existing_target_segments"):
                parts.append(f"CURRENT TARGET DEFINITION:\n{project_context['existing_target_segments']}")
            parts.append(
                f"RESULTS SO FAR: {project_context.get('total_results_analyzed', 0)} companies analyzed, "
                f"{project_context.get('total_targets_found', 0)} targets found"
            )
            if project_context.get("top_targets"):
                parts.append(f"TOP TARGETS: {', '.join(project_context['top_targets'][:10])}")
            knowledge = project_context.get("knowledge", {})
            if knowledge.get("anti_keywords"):
                parts.append(f"EXCLUDED PATTERNS: {', '.join(knowledge['anti_keywords'][:15])}")
            if knowledge.get("industry_keywords"):
                parts.append(f"CONFIRMED KEYWORDS: {', '.join(knowledge['industry_keywords'][:15])}")
            project_block = "\n".join(parts)

        system_prompt = f"""You are a search assistant that classifies user messages into one of three intents and produces structured output.

{f"EXISTING PROJECT CONTEXT:{chr(10)}{project_block}" if project_block else "This is a NEW project with NO prior data."}

INTENT CLASSIFICATION RULES:
1. "search" — User wants to start a NEW search for a DIFFERENT type of company. Use when:
   - Project has NO results yet (first message)
   - User explicitly says "search for X instead", "start over", "find Y instead", "new search"
   - The request describes a completely different target than current target_segments

2. "refine" — User wants to ADJUST the current search. DEFAULT when project has results. Use when:
   - User says "exclude X", "skip Y", "also look in Z", "focus on W"
   - User gives feedback about results ("too many portals", "need bigger companies")
   - User adds criteria ("also in France", "only with 50+ employees")
   {"- THIS IS THE DEFAULT when the project already has results" if has_results else ""}

3. "question" — User is asking about results or the search, NOT requesting changes. Use when:
   - "how many targets?", "what's excluded?", "show me stats"
   - "what are the top results?", "which industries are represented?"
   - Pure information requests that don't change anything

RESPONSE FORMAT — respond ONLY with valid JSON (no markdown fences):
{{
    "intent": "search" | "refine" | "question",
    "target_segments": "full ICP document if intent is search, null otherwise",
    "knowledge_updates": {{
        "anti_keywords": ["keywords to EXCLUDE from results"],
        "industry_keywords": ["keywords that indicate a GOOD match"],
        "good_query_patterns": ["effective search query patterns"],
        "bad_query_patterns": ["ineffective query patterns to avoid"]
    }},
    "reply": "1-2 sentence confirmation of what you're doing",
    "suggestions": ["2-3 follow-up suggestions for the user"]
}}

CRITICAL RULES:
- NEVER ask clarifying questions. Act immediately.
- For "search" intent, target_segments MUST be a non-empty structured ICP document with КОМПАНИЯ, УСЛУГИ, ГЕОГРАФИЯ, ЯЗЫК sections.
- For "refine" intent, populate knowledge_updates with the refinements. If the user mentions ANY new geography, country, industry, or company type — you MUST provide UPDATED full target_segments (copy the existing ICP and add the new elements). Only set target_segments to null if the refinement is purely about exclusions/keywords.
- For "question" intent, reply with the answer based on project context. knowledge_updates should have empty arrays.
- The reply MUST be 1-2 sentences confirming the action taken, NEVER a question.
- target_segments MUST be a flat string (NOT a JSON object/dict). Use "SECTION: value" format separated by newlines.
- suggestions should be contextual follow-up actions the user might want.
- Reply and suggestions MUST match the language of the user's message (Russian message → Russian reply/suggestions, English → English).
- Expand acronyms (HNWI = High Net Worth Individual, SaaS = Software as a Service, etc.)"""

        # Build user prompt with conversation context
        user_parts = []
        if context:
            for msg in context:
                role = msg.get("role", "user")
                user_parts.append(f"[{role}]: {msg.get('content', '')}")
        user_parts.append(f"[user]: {message}")
        user_prompt = "\n".join(user_parts)

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=1500,
            )
            result = json.loads(response.choices[0].message.content)

            # Normalize result
            if "intent" not in result:
                result["intent"] = "search" if not has_results else "refine"
            if "knowledge_updates" not in result:
                result["knowledge_updates"] = {}
            ku = result.setdefault("knowledge_updates", {})
            for field in ["anti_keywords", "industry_keywords", "good_query_patterns", "bad_query_patterns"]:
                val = ku.get(field)
                if val is None:
                    ku[field] = []
                elif isinstance(val, str):
                    ku[field] = [val]
                elif not isinstance(val, list):
                    ku[field] = []
            if "suggestions" not in result or not isinstance(result["suggestions"], list):
                result["suggestions"] = []
            if "reply" not in result:
                result["reply"] = ""

            logger.info(f"Chat intent: {result['intent']} for message: {message[:80]!r}")
            return result

        except Exception as e:
            logger.error(f"Failed to classify message: {e}")
            return {
                "intent": "search" if not has_results else "refine",
                "target_segments": message.strip() if not has_results else None,
                "knowledge_updates": {
                    "anti_keywords": [], "industry_keywords": [],
                    "good_query_patterns": [], "bad_query_patterns": [],
                },
                "reply": f"Processing your request..." if not has_results else "Noted, adjusting the search.",
                "suggestions": [],
                "error": str(e),
            }


chat_search_service = ChatSearchService()
