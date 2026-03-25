"""Pipeline REST API — for frontend status + manual operations."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.models.user import MCPUser
from app.models.project import Project, Company
from app.models.gathering import GatheringRun, ApprovalGate
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class ProjectCreateRequest(BaseModel):
    name: str
    target_segments: Optional[str] = None
    target_industries: Optional[str] = None
    sender_name: Optional[str] = None
    sender_company: Optional[str] = None
    sender_position: Optional[str] = None


@router.post("/projects")
async def create_project(
    req: ProjectCreateRequest,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Get or create user's company
    result = await session.execute(select(Company).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        company = Company(name=f"{user.name}'s Company")
        session.add(company)
        await session.flush()

    project = Project(
        company_id=company.id,
        user_id=user.id,
        name=req.name,
        target_segments=req.target_segments,
        target_industries=req.target_industries,
        sender_name=req.sender_name,
        sender_company=req.sender_company,
        sender_position=req.sender_position,
    )
    session.add(project)
    await session.flush()

    return {"project_id": project.id, "name": project.name}


@router.get("/projects")
async def list_projects(
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(
            Project.user_id == user.id,
            Project.is_active == True,
        )
    )
    projects = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "target_segments": p.target_segments,
            "sender_name": p.sender_name,
            "sender_company": p.sender_company,
        }
        for p in projects
    ]


@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: int,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    # Get pending gates
    gates_result = await session.execute(
        select(ApprovalGate).where(
            ApprovalGate.gathering_run_id == run_id,
            ApprovalGate.status == "pending",
        )
    )
    pending_gates = gates_result.scalars().all()

    return {
        "id": run.id,
        "status": run.status,
        "current_phase": run.current_phase,
        "source_type": run.source_type,
        "new_companies": run.new_companies_count,
        "duplicates": run.duplicate_count,
        "rejected": run.rejected_count,
        "target_rate": run.target_rate,
        "credits_used": run.credits_used,
        "pending_gates": [
            {
                "gate_id": g.id,
                "type": g.gate_type,
                "label": g.gate_label,
                "scope": g.scope,
            }
            for g in pending_gates
        ],
    }
