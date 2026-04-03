"""API endpoints for operator tasks (CRM task management)."""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from datetime import datetime
import logging

from app.db import get_session
from app.models.task import OperatorTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ============= Schemas =============

class TaskCreate(BaseModel):
    project_id: Optional[int] = None
    contact_id: Optional[int] = None
    task_type: str = "manual"
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None  # pending, done, skipped
    title: Optional[str] = None
    description: Optional[str] = None
    due_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    contact_id: Optional[int] = None
    task_type: str
    title: str
    description: Optional[str] = None
    due_at: datetime
    status: str
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TasksListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    pending: int
    done: int


# ============= Endpoints =============

@router.get("", response_model=TasksListResponse)
async def list_tasks(
    project_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    contact_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """List tasks, filterable by project, status, contact."""
    query = select(OperatorTask)

    conditions = []
    if project_id is not None:
        conditions.append(OperatorTask.project_id == project_id)
    if status:
        conditions.append(OperatorTask.status == status)
    if contact_id is not None:
        conditions.append(OperatorTask.contact_id == contact_id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(OperatorTask.due_at.asc()).limit(limit)

    result = await session.execute(query)
    tasks = result.scalars().all()

    # Stats
    total = len(tasks)
    pending = sum(1 for t in tasks if t.status == "pending")
    done = sum(1 for t in tasks if t.status == "done")

    return TasksListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        pending=pending,
        done=done,
    )


@router.post("", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new task."""
    db_task = OperatorTask(
        project_id=task.project_id,
        contact_id=task.contact_id,
        task_type=task.task_type,
        title=task.title,
        description=task.description,
        due_at=task.due_at or datetime.utcnow(),
        contact_email=task.contact_email,
        contact_name=task.contact_name,
    )
    session.add(db_task)
    await session.commit()
    await session.refresh(db_task)
    return TaskResponse.model_validate(db_task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    updates: TaskUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a task (mark done/skipped, edit title, etc.)."""
    result = await session.execute(
        select(OperatorTask).where(OperatorTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    task.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(task)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a task."""
    result = await session.execute(
        select(OperatorTask).where(OperatorTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await session.delete(task)
    await session.commit()
    return {"success": True}
