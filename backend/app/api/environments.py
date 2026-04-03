"""
Environments API - CRUD operations for environment/workspace management
Environments group companies for isolation (e.g., per client workspace)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List
from datetime import datetime

from app.db import get_session
from app.models import User, Environment, Company
from app.schemas import (
    EnvironmentCreate, EnvironmentUpdate, EnvironmentResponse, EnvironmentWithStats,
    MessageResponse
)
from app.api.companies import get_current_user

router = APIRouter(prefix="/environments", tags=["environments"])


# ============ Environment CRUD Endpoints ============

@router.get("", response_model=List[EnvironmentWithStats])
async def list_environments(
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """List all environments for the current user with company counts"""
    result = await db.execute(
        select(Environment).where(
            and_(Environment.user_id == user.id, Environment.is_active == True, Environment.deleted_at == None)
        ).order_by(Environment.created_at.desc())
    )
    environments = result.scalars().all()
    
    # Get company counts for each environment
    environments_with_stats = []
    for env in environments:
        companies_result = await db.execute(
            select(func.count(Company.id)).where(
                and_(
                    Company.environment_id == env.id,
                    Company.is_active == True,
                    Company.deleted_at == None
                )
            )
        )
        companies_count = companies_result.scalar() or 0
        
        environments_with_stats.append(EnvironmentWithStats(
            **EnvironmentResponse.model_validate(env).model_dump(),
            companies_count=companies_count
        ))
    
    return environments_with_stats


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(
    data: EnvironmentCreate,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Create a new environment"""
    environment = Environment(
        user_id=user.id,
        name=data.name,
        description=data.description,
        color=data.color or "#6366F1",  # Default indigo color
        icon=data.icon,
        is_active=True
    )
    db.add(environment)
    await db.commit()
    await db.refresh(environment)
    
    return environment


@router.get("/{environment_id}", response_model=EnvironmentWithStats)
async def get_environment(
    environment_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Get a specific environment by ID"""
    result = await db.execute(
        select(Environment).where(
            and_(
                Environment.id == environment_id,
                Environment.user_id == user.id,
                Environment.is_active == True,
                Environment.deleted_at == None
            )
        )
    )
    env = result.scalar_one_or_none()
    
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    
    # Get company count
    companies_result = await db.execute(
        select(func.count(Company.id)).where(
            and_(
                Company.environment_id == env.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    companies_count = companies_result.scalar() or 0
    
    return EnvironmentWithStats(
        **EnvironmentResponse.model_validate(env).model_dump(),
        companies_count=companies_count
    )


@router.put("/{environment_id}", response_model=EnvironmentResponse)
async def update_environment(
    environment_id: int,
    data: EnvironmentUpdate,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Update an environment"""
    result = await db.execute(
        select(Environment).where(
            and_(
                Environment.id == environment_id,
                Environment.user_id == user.id,
                Environment.is_active == True,
                Environment.deleted_at == None
            )
        )
    )
    env = result.scalar_one_or_none()
    
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    
    if data.name is not None:
        env.name = data.name
    if data.description is not None:
        env.description = data.description
    if data.color is not None:
        env.color = data.color
    if data.icon is not None:
        env.icon = data.icon
    
    env.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(env)
    
    return env


@router.delete("/{environment_id}", response_model=MessageResponse)
async def delete_environment(
    environment_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Soft delete an environment.
    Companies in this environment will be moved to no environment (null).
    """
    result = await db.execute(
        select(Environment).where(
            and_(
                Environment.id == environment_id,
                Environment.user_id == user.id,
                Environment.is_active == True,
                Environment.deleted_at == None
            )
        )
    )
    env = result.scalar_one_or_none()
    
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    
    # Move companies to no environment
    await db.execute(
        Company.__table__.update()
        .where(Company.environment_id == environment_id)
        .values(environment_id=None)
    )
    
    # Soft delete environment
    env.deleted_at = datetime.utcnow()
    env.is_active = False
    
    await db.commit()
    
    return {"message": f"Environment '{env.name}' has been deleted"}


@router.get("/{environment_id}/companies", response_model=List[dict])
async def get_environment_companies(
    environment_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Get all companies in an environment"""
    # Verify environment exists and belongs to user
    env_result = await db.execute(
        select(Environment).where(
            and_(
                Environment.id == environment_id,
                Environment.user_id == user.id,
                Environment.deleted_at == None
            )
        )
    )
    if not env_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Environment not found")
    
    # Get companies
    result = await db.execute(
        select(Company).where(
            and_(
                Company.environment_id == environment_id,
                Company.user_id == user.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        ).order_by(Company.created_at.desc())
    )
    companies = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "color": c.color,
            "created_at": c.created_at.isoformat()
        }
        for c in companies
    ]
