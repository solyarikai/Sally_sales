"""
Project Knowledge API — CRUD for project knowledge entries.

Endpoints:
- GET    /projects/{id}/knowledge              -> All entries grouped by category
- GET    /projects/{id}/knowledge/{category}    -> Entries for one category
- PUT    /projects/{id}/knowledge/{cat}/{key}   -> Upsert entry
- DELETE /projects/{id}/knowledge/{cat}/{key}   -> Delete entry
- POST   /projects/{id}/knowledge/sync          -> Sync from legacy tables
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Any
from pydantic import BaseModel, Field
import logging

from app.db import get_session
from app.api.companies import get_required_company
from app.models.user import Company
from app.models.contact import Project
from app.services.project_knowledge_service import project_knowledge_service

router = APIRouter(prefix="/projects", tags=["project-knowledge"])
logger = logging.getLogger(__name__)


class KnowledgeUpsertRequest(BaseModel):
    value: Any = Field(..., description="JSONB value for the entry")
    title: Optional[str] = Field(None, max_length=255)
    source: str = Field("manual", max_length=50)


async def _get_project(db: AsyncSession, project_id: int, company: Company) -> Project:
    """Verify project exists and belongs to company."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/knowledge")
async def get_all_knowledge(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get all knowledge entries grouped by category."""
    await _get_project(db, project_id, company)
    grouped = await project_knowledge_service.get_all(db, project_id)
    return {"project_id": project_id, "knowledge": grouped}


@router.get("/{project_id}/knowledge/{category}")
async def get_knowledge_by_category(
    project_id: int,
    category: str,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get all entries for a specific category."""
    await _get_project(db, project_id, company)
    entries = await project_knowledge_service.get_by_category(db, project_id, category)
    return {"project_id": project_id, "category": category, "entries": entries}


@router.put("/{project_id}/knowledge/{category}/{key}")
async def upsert_knowledge(
    project_id: int,
    category: str,
    key: str,
    body: KnowledgeUpsertRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Create or update a knowledge entry."""
    await _get_project(db, project_id, company)
    entry = await project_knowledge_service.upsert(
        db, project_id, category, key,
        value=body.value, title=body.title, source=body.source,
    )
    return entry


@router.delete("/{project_id}/knowledge/{category}/{key}")
async def delete_knowledge(
    project_id: int,
    category: str,
    key: str,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete a knowledge entry."""
    await _get_project(db, project_id, company)
    deleted = await project_knowledge_service.delete_entry(db, project_id, category, key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}


@router.post("/{project_id}/knowledge/sync")
async def sync_knowledge(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Sync knowledge from legacy tables (Project.target_segments, ProjectSearchKnowledge, stats)."""
    await _get_project(db, project_id, company)
    count = await project_knowledge_service.sync_from_legacy(db, project_id)
    return {"project_id": project_id, "entries_synced": count}
