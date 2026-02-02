"""
CRM API - Unified contact management from Smartlead and GetSales
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional, List
from datetime import datetime

from app.db import get_session
from app.models import Contact, Project
from pydantic import BaseModel


router = APIRouter(prefix="/crm", tags=["CRM"])


# Schemas
class ContactCreate(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    project_id: Optional[int] = None
    source: str = "manual"
    source_id: Optional[str] = None
    status: str = "lead"
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    project_id: Optional[int] = None
    status: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    company_name: Optional[str]
    domain: Optional[str]
    job_title: Optional[str]
    segment: Optional[str]
    project_id: Optional[int]
    source: str
    source_id: Optional[str]
    status: str
    phone: Optional[str]
    linkedin_url: Optional[str]
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total: int
    page: int
    page_size: int


class ContactStats(BaseModel):
    total: int
    by_status: dict
    by_source: dict
    by_segment: dict
    replied: int
    contacted: int


# API Endpoints

@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    search: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    segment: Optional[str] = None,
    project_id: Optional[int] = None,
    replied_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session)
):
    """List contacts with filters"""
    query = select(Contact).where(Contact.deleted_at == None)
    count_query = select(func.count(Contact.id)).where(Contact.deleted_at == None)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Contact.email.ilike(search_term),
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.company_name.ilike(search_term),
                Contact.job_title.ilike(search_term)
            )
        )
        count_query = count_query.where(
            or_(
                Contact.email.ilike(search_term),
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.company_name.ilike(search_term),
                Contact.job_title.ilike(search_term)
            )
        )
    
    if status:
        query = query.where(Contact.status == status)
        count_query = count_query.where(Contact.status == status)
    
    if source:
        query = query.where(Contact.source == source)
        count_query = count_query.where(Contact.source == source)
    
    if segment:
        query = query.where(Contact.segment == segment)
        count_query = count_query.where(Contact.segment == segment)
    
    if project_id:
        query = query.where(Contact.project_id == project_id)
        count_query = count_query.where(Contact.project_id == project_id)
    
    if replied_only:
        query = query.where(Contact.status == "replied")
        count_query = count_query.where(Contact.status == "replied")
    
    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(Contact.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(query)
    contacts = result.scalars().all()
    
    return ContactListResponse(
        contacts=[ContactResponse.model_validate(c) for c in contacts],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/contacts/stats", response_model=ContactStats)
async def get_contact_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get contact statistics"""
    
    # Total contacts
    total_result = await session.execute(
        select(func.count(Contact.id)).where(Contact.deleted_at == None)
    )
    total = total_result.scalar()
    
    # By status
    status_result = await session.execute(
        select(Contact.status, func.count(Contact.id))
        .where(Contact.deleted_at == None)
        .group_by(Contact.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}
    
    # By source
    source_result = await session.execute(
        select(Contact.source, func.count(Contact.id))
        .where(Contact.deleted_at == None)
        .group_by(Contact.source)
    )
    by_source = {row[0]: row[1] for row in source_result.all()}
    
    # By segment
    segment_result = await session.execute(
        select(Contact.segment, func.count(Contact.id))
        .where(and_(Contact.deleted_at == None, Contact.segment != None))
        .group_by(Contact.segment)
    )
    by_segment = {row[0]: row[1] for row in segment_result.all()}
    
    # Replied and contacted counts
    replied = by_status.get("replied", 0)
    contacted = by_status.get("contacted", 0)
    
    return ContactStats(
        total=total,
        by_status=by_status,
        by_source=by_source,
        by_segment=by_segment,
        replied=replied,
        contacted=contacted
    )


@router.post("/contacts", response_model=ContactResponse)
async def create_contact(
    contact: ContactCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new contact"""
    
    # Check if contact already exists
    existing = await session.execute(
        select(Contact).where(
            and_(
                Contact.email == contact.email,
                Contact.deleted_at == None
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Contact with this email already exists")
    
    db_contact = Contact(**contact.model_dump())
    session.add(db_contact)
    await session.commit()
    await session.refresh(db_contact)
    
    return ContactResponse.model_validate(db_contact)


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific contact"""
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.deleted_at == None
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return ContactResponse.model_validate(contact)


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    contact_update: ContactUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a contact"""
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.deleted_at == None
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Update fields
    for field, value in contact_update.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    
    contact.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(contact)
    
    return ContactResponse.model_validate(contact)


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete a contact"""
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.deleted_at == None
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.deleted_at = datetime.utcnow()
    await session.commit()
    
    return {"success": True, "message": "Contact deleted"}


@router.post("/import")
async def import_contacts(
    contacts: List[dict],
    session: AsyncSession = Depends(get_session)
):
    """Import contacts from merged JSON"""
    
    imported = 0
    skipped = 0
    errors = []
    
    for contact_data in contacts:
        try:
            email = contact_data.get("email")
            if not email:
                skipped += 1
                continue
            
            # Check if exists
            existing = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.email == email,
                        Contact.deleted_at == None
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            
            # Determine status based on replied field
            status = "replied" if contact_data.get("replied") else "lead"
            
            # Determine source
            sources = contact_data.get("sources", [])
            if "smartlead" in sources and "getsales" in sources:
                source = "smartlead+getsales"
            elif "smartlead" in sources:
                source = "smartlead"
            elif "getsales" in sources:
                source = "getsales"
            else:
                source = "import"
            
            # Create contact
            contact = Contact(
                email=email,
                first_name=contact_data.get("first_name"),
                last_name=contact_data.get("last_name"),
                company_name=contact_data.get("company"),
                job_title=contact_data.get("title"),
                phone=contact_data.get("phone"),
                linkedin_url=contact_data.get("linkedin"),
                location=contact_data.get("location"),
                source=source,
                status=status
            )
            
            session.add(contact)
            imported += 1
            
        except Exception as e:
            errors.append(f"Error importing {contact_data.get('email')}: {str(e)}")
    
    await session.commit()
    
    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10]  # Return first 10 errors
    }
