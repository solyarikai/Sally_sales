"""
Project Knowledge Service — unified CRUD for project knowledge entries.

Provides get/upsert/delete operations on the project_knowledge table,
plus sync_from_legacy() to populate from existing tables (Project.target_segments,
ProjectSearchKnowledge fields, aggregated search stats).
"""
import json
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.project_knowledge import ProjectKnowledge
from app.models.contact import Project
from app.models.domain import ProjectSearchKnowledge

logger = logging.getLogger(__name__)


class ProjectKnowledgeService:
    """CRUD + sync for project knowledge entries."""

    async def get_all(self, session: AsyncSession, project_id: int) -> Dict[str, List[dict]]:
        """Get all knowledge entries grouped by category."""
        result = await session.execute(
            select(ProjectKnowledge)
            .where(ProjectKnowledge.project_id == project_id)
            .order_by(ProjectKnowledge.category, ProjectKnowledge.key)
        )
        rows = result.scalars().all()

        grouped: Dict[str, List[dict]] = {}
        for r in rows:
            cat = r.category
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append({
                "id": r.id,
                "category": r.category,
                "key": r.key,
                "title": r.title,
                "value": r.value,
                "source": r.source,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
        return grouped

    async def get_by_category(
        self, session: AsyncSession, project_id: int, category: str,
    ) -> List[dict]:
        """Get all entries for a single category."""
        result = await session.execute(
            select(ProjectKnowledge)
            .where(
                ProjectKnowledge.project_id == project_id,
                ProjectKnowledge.category == category,
            )
            .order_by(ProjectKnowledge.key)
        )
        return [
            {
                "id": r.id,
                "category": r.category,
                "key": r.key,
                "title": r.title,
                "value": r.value,
                "source": r.source,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in result.scalars().all()
        ]

    async def get_entry(
        self, session: AsyncSession, project_id: int, category: str, key: str,
    ) -> Optional[dict]:
        """Get a single entry by (category, key)."""
        result = await session.execute(
            select(ProjectKnowledge).where(
                ProjectKnowledge.project_id == project_id,
                ProjectKnowledge.category == category,
                ProjectKnowledge.key == key,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "id": r.id,
            "category": r.category,
            "key": r.key,
            "title": r.title,
            "value": r.value,
            "source": r.source,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    async def upsert(
        self,
        session: AsyncSession,
        project_id: int,
        category: str,
        key: str,
        value: Any,
        title: Optional[str] = None,
        source: str = "manual",
    ) -> dict:
        """Insert or update a knowledge entry."""
        stmt = pg_insert(ProjectKnowledge).values(
            project_id=project_id,
            category=category,
            key=key,
            title=title,
            value=value,
            source=source,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "category", "key"],
            set_={
                "value": stmt.excluded.value,
                "title": stmt.excluded.title,
                "source": stmt.excluded.source,
                "updated_at": sql_text("now()"),
            },
        )
        await session.execute(stmt)
        await session.commit()

        # Return the upserted row
        return await self.get_entry(session, project_id, category, key)

    async def delete_entry(
        self, session: AsyncSession, project_id: int, category: str, key: str,
    ) -> bool:
        """Delete a single knowledge entry. Returns True if deleted."""
        result = await session.execute(
            delete(ProjectKnowledge).where(
                ProjectKnowledge.project_id == project_id,
                ProjectKnowledge.category == category,
                ProjectKnowledge.key == key,
            )
        )
        await session.commit()
        return result.rowcount > 0

    async def sync_from_legacy(self, session: AsyncSession, project_id: int) -> int:
        """
        Populate project_knowledge from existing tables.
        Returns number of entries created/updated.
        """
        count = 0

        # 1. Project.target_segments -> icp/target_description
        proj_result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            return 0

        if project.target_segments:
            await self.upsert(
                session, project_id, "icp", "target_description",
                {"text": project.target_segments},
                title="Target Description (ICP)",
                source="sync",
            )
            count += 1

        # 2. ProjectSearchKnowledge -> search/* entries
        k_result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = k_result.scalar_one_or_none()

        if knowledge:
            # search/config
            if knowledge.search_config:
                await self.upsert(
                    session, project_id, "search", "config",
                    knowledge.search_config,
                    title="Search Configuration",
                    source="sync",
                )
                count += 1

            # search/learned_patterns
            patterns = {}
            if knowledge.good_query_patterns:
                patterns["good_queries"] = knowledge.good_query_patterns
            if knowledge.bad_query_patterns:
                patterns["bad_queries"] = knowledge.bad_query_patterns
            if knowledge.industry_keywords:
                patterns["industry_keywords"] = knowledge.industry_keywords
            if knowledge.anti_keywords:
                patterns["anti_keywords"] = knowledge.anti_keywords
            if patterns:
                await self.upsert(
                    session, project_id, "search", "learned_patterns",
                    patterns,
                    title="Learned Search Patterns",
                    source="sync",
                )
                count += 1

        # 3. Aggregated stats from discovered_companies
        stats = await session.execute(sql_text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_target) as targets,
                COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as enriched
            FROM discovered_companies
            WHERE project_id = :pid
        """), {"pid": project_id})
        row = stats.fetchone()
        if row and row.total > 0:
            await self.upsert(
                session, project_id, "search", "performance",
                {
                    "total_discovered": row.total,
                    "total_targets": row.targets,
                    "total_enriched": row.enriched,
                    "target_rate": round(100 * row.targets / max(row.total, 1), 1),
                },
                title="Search Performance",
                source="sync",
            )
            count += 1

        logger.info(f"Synced {count} knowledge entries for project {project_id}")
        return count

    async def get_summary(self, session: AsyncSession, project_id: int) -> str:
        """
        Build an AI-friendly text summary of all knowledge for a project.
        Used to enrich chat context / system prompts.
        """
        grouped = await self.get_all(session, project_id)
        if not grouped:
            return "No knowledge entries for this project yet."

        parts = []
        for category, entries in grouped.items():
            cat_lines = [f"## {category.upper()}"]
            for entry in entries:
                title = entry.get("title") or entry["key"]
                value = entry["value"]
                if isinstance(value, dict) and "text" in value:
                    cat_lines.append(f"**{title}**: {value['text'][:500]}")
                elif isinstance(value, list):
                    items = ", ".join(str(v) for v in value[:10])
                    cat_lines.append(f"**{title}**: [{items}]")
                else:
                    val_str = json.dumps(value, ensure_ascii=False)[:300]
                    cat_lines.append(f"**{title}**: {val_str}")
            parts.append("\n".join(cat_lines))

        return "\n\n".join(parts)


project_knowledge_service = ProjectKnowledgeService()
