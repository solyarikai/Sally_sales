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
    ) -> Dict[str, Any]:
        """
        Parse a natural language message into structured search parameters.

        Returns:
            {
                "target_segments": str,  # formatted for project.target_segments
                "project_name": str,
                "geography": str,
                "industry": str,
                "max_queries": int | None,
                "target_goal": int | None,
                "reply": str,  # AI reply to show user
            }
        """
        import openai

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = """You are a search assistant that converts natural language descriptions into structured company search parameters.

Given a user's description of companies they want to find, extract:
1. A formatted "target_segments" text block describing the ideal target company (like an ICP document)
2. A short project name
3. Geography/location
4. Industry/vertical
5. A friendly reply acknowledging what you understood

Format the target_segments as a structured document with sections:
- КОМПАНИЯ (company type, size, characteristics)
- УСЛУГИ (services they provide)
- ГЕОГРАФИЯ (geography/location)
- ЯЗЫК (website language)

Respond in JSON format:
{
    "target_segments": "...",
    "project_name": "...",
    "geography": "...",
    "industry": "...",
    "reply": "..."
}"""

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
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
