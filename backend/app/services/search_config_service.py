"""
Per-project search config service — AI bootstrap + CRUD for segments/geos/templates.

Replaces hardcoded SEGMENTS/DOC_KEYWORDS from query_templates.py with per-project
config stored in ProjectSearchKnowledge.search_config.
"""
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.contact import Project
from app.models.domain import ProjectSearchKnowledge

logger = logging.getLogger(__name__)

BOOTSTRAP_SYSTEM_PROMPT = """You are a search configuration generator for a B2B lead generation platform.

Given a project's target company description (ICP), generate a structured search config with:
- segments: distinct market segments to search for
- geos: geographic markets per segment
- vars: keyword variable pools per segment (company types, services, etc.)
- templates: search query templates using {placeholders}
- doc_keywords: curated exact search phrases

OUTPUT FORMAT (strict JSON):
{
  "segments": {
    "segment_key": {
      "priority": 1,
      "label_en": "Human readable name",
      "label_ru": "Название по-русски",
      "geos": {
        "geo_key": {
          "cities_en": ["City1", "City2"],
          "cities_ru": ["Город1", "Город2"],
          "country_en": "Country",
          "country_ru": "Страна"
        }
      },
      "vars": {
        "company_type_en": ["type1", "type2"],
        "company_type_ru": ["тип1", "тип2"],
        "service_en": ["service1", "service2"],
        "service_ru": ["услуга1", "услуга2"]
      },
      "templates_en": ["{company_type} {city}", "{service} agency {city}"],
      "templates_ru": ["{company_type} {city}", "{service} агентство {city}"]
    }
  },
  "doc_keywords": [
    ["segment_key", "geo_key", "en", ["exact search phrase 1", "exact phrase 2"]],
    ["segment_key", "geo_key", "ru", ["точная поисковая фраза 1"]]
  ]
}

RULES:
- segment_key: lowercase_snake_case, descriptive (e.g. "influencer_agencies", "saas_platforms")
- geo_key: lowercase_snake_case matching the market (e.g. "usa", "uk", "russia", "dubai")
- Generate 3-8 company_type variants per language, 3-8 service variants
- Templates use {company_type}, {service}, {city}, {country} placeholders
- Generate 5-15 templates per language per segment
- doc_keywords: 10-30 exact phrases per segment×geo×language — these are the BEST search queries
- Include both English and Russian templates/keywords when the target geography warrants it
- For Russian markets, prioritize Russian queries; for international, prioritize English
- Be specific: "influencer marketing agency NYC" not just "marketing agency"

Respond ONLY with valid JSON, no markdown fences or explanations."""


class SearchConfigService:
    """Manages per-project search configuration stored in ProjectSearchKnowledge.search_config."""

    async def bootstrap_config(self, target_segments: str, project_name: str) -> dict:
        """Use AI to generate initial search_config from target_segments text."""
        user_prompt = (
            f"Project: {project_name}\n\n"
            f"Target Company Description (ICP):\n{target_segments}\n\n"
            "Generate a complete search configuration for finding these companies."
        )

        try:
            from app.services.gemini_client import is_gemini_available, gemini_generate, extract_json_from_gemini

            if is_gemini_available():
                gen_result = await gemini_generate(
                    system_prompt=BOOTSTRAP_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=8000,
                )
                raw = extract_json_from_gemini(gen_result["content"])
                logger.info(f"Search config bootstrap via Gemini: {gen_result['tokens']['total']} tokens")
                config = json.loads(raw)
            else:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": BOOTSTRAP_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    max_tokens=8000,
                )
                config = json.loads(response.choices[0].message.content)

            # Validate basic structure
            if "segments" not in config:
                config = {"segments": {}, "doc_keywords": []}
            if "doc_keywords" not in config:
                config["doc_keywords"] = []

            return config

        except Exception as e:
            logger.error(f"Failed to bootstrap search config: {e}", exc_info=True)
            return {"segments": {}, "doc_keywords": []}

    async def get_or_create_config(self, session: AsyncSession, project_id: int) -> dict:
        """Load search_config from DB. If null, bootstrap from project.target_segments."""
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = result.scalar_one_or_none()

        if knowledge and knowledge.search_config:
            return knowledge.search_config

        # Load project to get target_segments
        proj_result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = proj_result.scalar_one_or_none()
        if not project or not project.target_segments:
            return {"segments": {}, "doc_keywords": []}

        # Bootstrap via AI
        config = await self.bootstrap_config(project.target_segments, project.name)

        # Save to DB
        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=project_id)
            session.add(knowledge)

        knowledge.search_config = config
        await session.commit()

        logger.info(f"Bootstrapped search config for project {project_id}: "
                     f"{len(config.get('segments', {}))} segments, "
                     f"{len(config.get('doc_keywords', []))} doc_keyword groups")
        return config

    async def get_config(self, session: AsyncSession, project_id: int) -> Optional[dict]:
        """Load search_config from DB without bootstrapping."""
        result = await session.execute(
            select(ProjectSearchKnowledge.search_config).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        row = result.scalar_one_or_none()
        return row if row else None

    async def update_config(self, session: AsyncSession, project_id: int, new_config: dict) -> dict:
        """Replace entire search_config for a project."""
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=project_id)
            session.add(knowledge)

        knowledge.search_config = new_config
        await session.commit()
        return new_config

    async def edit_config_via_ai(
        self,
        session: AsyncSession,
        project_id: int,
        user_message: str,
        current_config: dict,
    ) -> Dict[str, Any]:
        """Use AI to interpret a user's edit request and produce updated config."""
        system_prompt = f"""You are editing a search configuration for a lead generation platform.

CURRENT CONFIG:
{json.dumps(current_config, ensure_ascii=False, indent=2)[:6000]}

The user wants to modify this config. Interpret their request and return the FULL updated config.
Common operations:
- Add/remove segments
- Add/remove geos to a segment
- Add/remove keywords, templates, or variables
- Change priorities

Return ONLY valid JSON with two keys:
{{
  "config": {{ ... full updated config ... }},
  "summary": "Human-readable summary of what changed"
}}"""

        try:
            from app.services.gemini_client import is_gemini_available, gemini_generate, extract_json_from_gemini

            if is_gemini_available():
                gen_result = await gemini_generate(
                    system_prompt=system_prompt,
                    user_prompt=user_message,
                    temperature=0.2,
                    max_tokens=8000,
                )
                raw = extract_json_from_gemini(gen_result["content"])
                result = json.loads(raw)
            else:
                import openai
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    max_tokens=8000,
                )
                result = json.loads(response.choices[0].message.content)

            new_config = result.get("config", current_config)
            summary = result.get("summary", "Config updated")

            # Save
            await self.update_config(session, project_id, new_config)
            return {"config": new_config, "summary": summary}

        except Exception as e:
            logger.error(f"Failed to edit config via AI: {e}", exc_info=True)
            return {"config": current_config, "summary": f"Error: {str(e)[:200]}"}

    def format_config_summary(self, config: dict) -> str:
        """Format search_config as human-readable summary for chat."""
        if not config or not config.get("segments"):
            return "No search config configured. Use 'bootstrap config' or describe your target companies."

        segments = config.get("segments", {})
        doc_keywords = config.get("doc_keywords", [])

        lines = [f"**Search Config** ({len(segments)} segments)\n"]
        for seg_key, seg in segments.items():
            label = seg.get("label_en", seg_key)
            priority = seg.get("priority", "?")
            geos = list(seg.get("geos", {}).keys())
            templates_en = len(seg.get("templates_en", []))
            templates_ru = len(seg.get("templates_ru", []))
            vars_count = sum(len(v) for v in seg.get("vars", {}).values())

            lines.append(f"**{label}** (`{seg_key}`, priority {priority})")
            lines.append(f"  Geos: {', '.join(geos) if geos else 'none'}")
            lines.append(f"  Templates: {templates_en} EN + {templates_ru} RU")
            lines.append(f"  Variables: {vars_count} values")
            lines.append("")

        # Doc keywords summary
        dk_count = sum(len(entry[3]) for entry in doc_keywords if len(entry) >= 4)
        if dk_count:
            lines.append(f"**Doc keywords**: {dk_count} phrases across {len(doc_keywords)} groups")

        return "\n".join(lines)


search_config_service = SearchConfigService()
