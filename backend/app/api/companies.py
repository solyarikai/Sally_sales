"""
Companies API - CRUD operations for company/project management
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
import logging

from app.db import get_session, async_session_maker
from app.models import User, Environment, Company, Dataset, Prospect, Document, UserActivityLog
from app.schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyWithStats,
    EnvironmentResponse,
    MessageResponse, UserResponse, CurrentUserResponse
)
from app.services.favicon_service import favicon_service

router = APIRouter(prefix="/companies", tags=["companies"])
logger = logging.getLogger(__name__)


# ============ Background Tasks ============

async def fetch_favicon_background(company_id: int, website: str):
    """Background task to fetch and update company favicon"""
    try:
        logger.info(f"[Background] Fetching favicon for company {company_id} from {website}")
        
        # Fetch favicon
        favicon_url = await favicon_service.fetch_favicon(website)
        
        if favicon_url:
            # Update company in database
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Company).where(Company.id == company_id)
                )
                company = result.scalar_one_or_none()
                
                if company:
                    company.logo_url = favicon_url
                    company.updated_at = datetime.utcnow()
                    await session.commit()
                    logger.info(f"[Background] Favicon updated for company {company_id}: {favicon_url}")
                else:
                    logger.warning(f"[Background] Company {company_id} not found")
        else:
            logger.info(f"[Background] No valid favicon found for company {company_id}")
            
    except Exception as e:
        logger.error(f"[Background] Error fetching favicon for company {company_id}: {e}")


# ============ Dependency to get current user ============

async def get_current_user(db: AsyncSession = Depends(get_session)) -> User:
    """
    Get the current user. For now, returns the first user (default user).
    In future, this will be replaced with proper authentication.
    """
    result = await db.execute(select(User).where(User.is_active == True).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=500, detail="No active user found. Database may not be initialized.")
    
    return user


async def get_optional_company(
    x_company_id: Optional[int] = Header(None, alias="X-Company-ID"),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
) -> Optional[Company]:
    """Get company from header if provided. Verifies the company belongs to the current user."""
    if x_company_id is None:
        return None
    
    result = await db.execute(
        select(Company).where(
            and_(
                Company.id == x_company_id,
                Company.user_id == user.id,  # Verify ownership
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with ID {x_company_id} not found or access denied")
    
    return company


async def get_required_company(
    x_company_id: int = Header(..., alias="X-Company-ID"),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
) -> Company:
    """Get company from header - required. Verifies the company belongs to the current user."""
    result = await db.execute(
        select(Company).where(
            and_(
                Company.id == x_company_id,
                Company.user_id == user.id,  # Verify ownership
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with ID {x_company_id} not found or access denied")
    
    return company


# ============ User Endpoints ============

@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Get current user info with their environments and companies"""
    # Get environments
    env_result = await db.execute(
        select(Environment).where(
            and_(Environment.user_id == user.id, Environment.is_active == True, Environment.deleted_at == None)
        ).order_by(Environment.created_at.desc())
    )
    environments = env_result.scalars().all()
    
    # Get companies
    result = await db.execute(
        select(Company).where(
            and_(Company.user_id == user.id, Company.is_active == True, Company.deleted_at == None)
        ).order_by(Company.created_at.desc())
    )
    companies = result.scalars().all()
    
    return {
        "user": user,
        "environments": environments,
        "companies": companies
    }


# ============ Company CRUD Endpoints ============

@router.get("", response_model=List[CompanyWithStats])
async def list_companies(
    environment_id: Optional[int] = None,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    List companies for the current user with statistics.
    Optionally filter by environment_id.
    Uses subqueries to avoid N+1 problem.
    """
    # Build filter conditions
    conditions = [
        Company.user_id == user.id,
        Company.is_active == True,
        Company.deleted_at == None
    ]
    
    # Filter by environment if specified
    if environment_id is not None:
        # Verify environment belongs to user
        env_result = await db.execute(
            select(Environment).where(
                and_(Environment.id == environment_id, Environment.user_id == user.id)
            )
        )
        if not env_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Environment not found")
        conditions.append(Company.environment_id == environment_id)
    
    # Create subqueries for counts to avoid N+1
    prospects_count_subq = (
        select(func.count(Prospect.id))
        .where(and_(Prospect.company_id == Company.id, Prospect.deleted_at == None))
        .correlate(Company)
        .scalar_subquery()
        .label("prospects_count")
    )
    
    datasets_count_subq = (
        select(func.count(Dataset.id))
        .where(and_(Dataset.company_id == Company.id, Dataset.deleted_at == None))
        .correlate(Company)
        .scalar_subquery()
        .label("datasets_count")
    )
    
    documents_count_subq = (
        select(func.count(Document.id))
        .where(Document.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
        .label("documents_count")
    )
    
    # Single query with all counts
    result = await db.execute(
        select(
            Company,
            prospects_count_subq,
            datasets_count_subq,
            documents_count_subq
        )
        .where(and_(*conditions))
        .order_by(Company.created_at.desc())
    )
    
    companies_with_stats = []
    for row in result.all():
        company = row[0]
        companies_with_stats.append(CompanyWithStats(
            **CompanyResponse.model_validate(company).model_dump(),
            prospects_count=row[1] or 0,
            datasets_count=row[2] or 0,
            documents_count=row[3] or 0
        ))
    
    return companies_with_stats


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Create a new company, optionally in a specific environment.
    Favicon extraction happens in background if website provided.
    """
    # Verify environment if specified
    environment_id = None
    if data.environment_id:
        env_result = await db.execute(
            select(Environment).where(
                and_(
                    Environment.id == data.environment_id,
                    Environment.user_id == user.id,
                    Environment.deleted_at == None
                )
            )
        )
        if not env_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Environment not found")
        environment_id = data.environment_id
    
    company = Company(
        user_id=user.id,
        environment_id=environment_id,
        name=data.name,
        description=data.description,
        website=data.website,
        logo_url=data.logo_url,
        color=data.color or "#3B82F6",  # Default blue color
        is_active=True
    )
    db.add(company)
    await db.flush()
    
    # Log activity
    log = UserActivityLog(
        user_id=user.id,
        company_id=company.id,
        action="create",
        entity_type="company",
        entity_id=company.id,
        details={"name": company.name}
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(company)
    
    # Fetch favicon in background if website provided
    if data.website:
        background_tasks.add_task(fetch_favicon_background, company.id, data.website)
        logger.info(f"Scheduled favicon fetch for company {company.id}")
    
    return company


@router.get("/{company_id}", response_model=CompanyWithStats)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Get a specific company by ID with statistics in single query"""
    # Create subqueries for counts
    prospects_count_subq = (
        select(func.count(Prospect.id))
        .where(and_(Prospect.company_id == Company.id, Prospect.deleted_at == None))
        .correlate(Company)
        .scalar_subquery()
        .label("prospects_count")
    )
    
    datasets_count_subq = (
        select(func.count(Dataset.id))
        .where(and_(Dataset.company_id == Company.id, Dataset.deleted_at == None))
        .correlate(Company)
        .scalar_subquery()
        .label("datasets_count")
    )
    
    documents_count_subq = (
        select(func.count(Document.id))
        .where(Document.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
        .label("documents_count")
    )
    
    result = await db.execute(
        select(
            Company,
            prospects_count_subq,
            datasets_count_subq,
            documents_count_subq
        ).where(
            and_(
                Company.id == company_id,
                Company.user_id == user.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company = row[0]
    return CompanyWithStats(
        **CompanyResponse.model_validate(company).model_dump(),
        prospects_count=row[1] or 0,
        datasets_count=row[2] or 0,
        documents_count=row[3] or 0
    )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    data: CompanyUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Update a company.
    If website changed, favicon extraction happens in background.
    """
    result = await db.execute(
        select(Company).where(
            and_(
                Company.id == company_id,
                Company.user_id == user.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Track changes for activity log
    changes = {}
    website_changed = False
    
    if data.name is not None and data.name != company.name:
        changes["name"] = {"old": company.name, "new": data.name}
        company.name = data.name
    
    if data.description is not None:
        company.description = data.description
    
    if data.website is not None and data.website != company.website:
        website_changed = True
        company.website = data.website
    
    if data.logo_url is not None:
        company.logo_url = data.logo_url
    
    if data.color is not None:
        company.color = data.color
    
    # Handle environment change - check if field was explicitly set in request
    if 'environment_id' in data.model_fields_set:
        if data.environment_id is None or data.environment_id == 0:
            # Remove from environment
            if company.environment_id is not None:
                changes["environment_id"] = {"old": company.environment_id, "new": None}
            company.environment_id = None
        else:
            # Verify the environment exists and belongs to user
            env_result = await db.execute(
                select(Environment).where(
                    and_(
                        Environment.id == data.environment_id,
                        Environment.user_id == user.id,
                        Environment.deleted_at == None
                    )
                )
            )
            if not env_result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Environment not found")
            if company.environment_id != data.environment_id:
                changes["environment_id"] = {"old": company.environment_id, "new": data.environment_id}
            company.environment_id = data.environment_id
    
    company.updated_at = datetime.utcnow()
    
    # Log activity if changes were made
    if changes:
        log = UserActivityLog(
            user_id=user.id,
            company_id=company.id,
            action="update",
            entity_type="company",
            entity_id=company.id,
            details=changes
        )
        db.add(log)
    
    await db.commit()
    await db.refresh(company)
    
    # Fetch favicon in background if website changed
    if website_changed and company.website:
        background_tasks.add_task(fetch_favicon_background, company.id, company.website)
        logger.info(f"Scheduled favicon fetch for updated company {company.id}")
    
    return company


@router.delete("/{company_id}", response_model=MessageResponse)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Soft delete a company.
    This will NOT delete the data immediately - it marks the company as deleted.
    """
    result = await db.execute(
        select(Company).where(
            and_(
                Company.id == company_id,
                Company.user_id == user.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Soft delete
    company.deleted_at = datetime.utcnow()
    company.is_active = False
    
    # Log activity
    log = UserActivityLog(
        user_id=user.id,
        company_id=company.id,
        action="delete",
        entity_type="company",
        entity_id=company.id,
        details={"name": company.name}
    )
    db.add(log)
    
    await db.commit()
    
    return {"message": f"Company '{company.name}' has been deleted"}


# ============ Activity Logs Endpoint ============

@router.get("/{company_id}/activity", response_model=List[dict])
async def get_company_activity(
    company_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """Get activity logs for a company"""
    # Verify company belongs to user
    result = await db.execute(
        select(Company).where(
            and_(Company.id == company_id, Company.user_id == user.id)
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    result = await db.execute(
        select(UserActivityLog)
        .where(UserActivityLog.company_id == company_id)
        .order_by(UserActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]


# ============ Favicon Extraction Endpoint ============

@router.post("/{company_id}/fetch-favicon", response_model=CompanyResponse)
async def fetch_company_favicon(
    company_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Automatically fetch and set company favicon from website.
    Returns updated company with logo_url set if favicon found.
    """
    # Get company
    result = await db.execute(
        select(Company).where(
            and_(
                Company.id == company_id,
                Company.user_id == user.id,
                Company.is_active == True,
                Company.deleted_at == None
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if company has website
    if not company.website:
        raise HTTPException(status_code=400, detail="Company has no website set")
    
    # Fetch favicon
    favicon_url = await favicon_service.fetch_favicon(company.website)
    
    if favicon_url:
        company.logo_url = favicon_url
        company.updated_at = datetime.utcnow()
        
        # Log activity
        log = UserActivityLog(
            user_id=user.id,
            company_id=company.id,
            action="update",
            entity_type="company",
            entity_id=company.id,
            details={"favicon_fetched": favicon_url}
        )
        db.add(log)
        
        await db.commit()
        await db.refresh(company)
    
    return company
