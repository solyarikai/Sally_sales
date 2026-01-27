from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List
from app.db import get_session
from app.models import PromptTemplate, User
from app.schemas import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
)
from app.api.companies import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])


# Default system templates - ONLY DATA NORMALIZATION
DEFAULT_TEMPLATES = [
    {
        "name": "Company Name Normalization",
        "description": "Normalize company name to clean, canonical brand form (removes legal suffixes, locations, franchise markers)",
        "category": "data_cleaning",
        "tags": ["Data Cleaning", "Normalization", "Deduplication"],
        "prompt_template": """Normalize this company name to its clean, canonical brand form.

Company Name: {{Company Name}}

RULES:
1) Strip legal/entity suffixes: Inc, Inc., LLC, LLP, LP, PLC, Ltd, Co., Corp, Corporation, Company, AG, GmbH, B.V., BV, S.A., SA, SAS, SRL, SpA/SPA, Oy, Oyj, AB, AS, A/S, NV, KK, Kft, Zrt, d.o.o., JSC, ULC, Pty Ltd, L.P., LLP, LLC, etc.
2) Remove location/office/descriptive tails after separators (– — - | , / · or "at/in/of" phrases) when they're not part of the brand:
   - "Keller Williams Realty – Charlotte South Park" → "Keller Williams Realty"
   - "Coldwell Banker Sea Coast Advantage" → "Coldwell Banker"
   - "Berkshire Hathaway HomeServices California Properties" → "Berkshire Hathaway HomeServices"
3) For well-known franchise/networks (e.g., Keller Williams, Coldwell Banker, RE/MAX, Century 21, Sotheby's International Realty, Compass, ERA, Howard Hanna, Berkshire Hathaway HomeServices), keep the core brand; drop market/office names ("Group", "Team", "Premier Realty", "Realty DTC", city/region labels) unless they are officially part of the brand line.
4) Drop deal/status notes in parentheses or after commas: "(now …)", stock tickers, "division of…", "a subsidiary of…", "formerly…".
5) Keep meaningful brand terms (Group, Partners, Capital, HomeServices, Realty, Real Estate) when integral to the brand; drop generic role words like "Realtor", "Real Estate Investor", "Self Employed-Real Estate".
6) Casing: Title Case. Preserve acronyms & stylized tokens (RE/MAX, ERA, KW, NYC, DFW, LLC, LP). Convert ALL-CAPS non-acronyms to Title Case. Keep diacritics and brand punctuation (&, +, ').
7) Trim whitespace; no trailing separators.

Return EXACTLY one line: the normalized company name. No notes, no extra text.""",
        "output_column": "normalized_company_name",
        "system_prompt": "You are a data normalization expert specializing in company name standardization. Your goal is to extract the clean, canonical brand name by removing legal suffixes, franchise locations, and descriptive modifiers while preserving the core brand identity. Always output only the normalized company name with no additional text or explanation.",
        "is_system": True,
    },
    {
        "name": "First Name Normalization",
        "description": "Normalize first names by removing titles, prefixes, nicknames, and keeping only the primary given name",
        "category": "data_cleaning",
        "tags": ["Data Cleaning", "Normalization", "Names"],
        "prompt_template": """Normalize the first name in this input.

Input: {{First Name}}

RULES:
1) Do NOT remove duplicates — output exactly one normalized value.
2) Remove all titles and prefixes (e.g. Dr., Prof., Mr., Ms., Mrs., Miss, Rev., Capt., etc.).
3) If multiple words exist, keep only the first given name.
4) If hyphenated, keep the first part only (e.g. Jean-Paul → Jean).
5) Remove anything in parentheses, quotes, or nicknames (e.g. Robert "Bobby" → Robert).
6) Remove initials and suffixes (J., M., Jr., Sr., II, III, etc.).
7) Strip punctuation and extra spaces.
8) Convert to Title Case (e.g. michael → Michael, JOHN → John).
9) If the value is not a person (company, brand, placeholder like "N/A", "--"), return the first readable token or "Unknown".
10) Never invent or translate names — only clean them.

EXAMPLES:
- Dr. Alois → Alois
- Robert "Bobby" → Robert
- Jean-Paul → Jean
- michael → Michael
- JOHN SMITH → John
- Mr. James T. Kirk → James
- mary-jane → Mary
- Prof. Dr. Hans Mueller → Hans
- N/A → Unknown
- -- → Unknown

Output: Return only the normalized first name, nothing else.""",
        "output_column": "normalized_first_name",
        "system_prompt": "You are a data cleaning expert specializing in name normalization. Your task is to extract and normalize the primary first name by removing titles, nicknames, initials, and extra components. Apply proper Title Case capitalization. If the input is not a valid person name, return 'Unknown'. Output only the normalized first name with no additional text or explanation.",
        "is_system": True,
    },
]


async def ensure_default_templates(session: AsyncSession):
    """
    Create default templates if they don't exist.
    Remove old system templates that are no longer in DEFAULT_TEMPLATES.
    """
    # Get all current system templates
    query = select(PromptTemplate).where(PromptTemplate.is_system == True)
    result = await session.execute(query)
    existing_templates = result.scalars().all()
    
    # Get names of templates we want to keep
    default_template_names = {t["name"] for t in DEFAULT_TEMPLATES}
    
    # Delete system templates that are not in DEFAULT_TEMPLATES
    for template in existing_templates:
        if template.name not in default_template_names:
            await session.delete(template)
            logger.info(f"Removed old system template: {template.name}")
    
    # Add or update default templates
    for template_data in DEFAULT_TEMPLATES:
        query = select(PromptTemplate).where(
            PromptTemplate.name == template_data["name"],
            PromptTemplate.is_system == True
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        if not existing:
            template = PromptTemplate(**template_data)
            session.add(template)
            logger.info(f"Created system template: {template_data['name']}")
        else:
            # Update existing template with new data
            for key, value in template_data.items():
                if key != 'is_system':  # Don't change is_system flag
                    setattr(existing, key, value)
            logger.info(f"Updated system template: {template_data['name']}")
    
    await session.commit()


@router.get("", response_model=List[PromptTemplateResponse])
async def list_templates(
    category: str = None,
    tag: str = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    List all prompt templates available to the current user.
    Returns system templates + user's own templates.
    Templates are shared across all companies for the same user.
    """
    # Show system templates + user's own templates
    query = select(PromptTemplate).where(
        or_(
            PromptTemplate.is_system == True,
            PromptTemplate.user_id == user.id
        )
    ).order_by(PromptTemplate.is_system.desc(), PromptTemplate.name)
    
    if category:
        query = query.where(PromptTemplate.category == category)
    
    result = await session.execute(query)
    templates = result.scalars().all()
    
    # Filter by tag if specified (done in Python since tags is JSON)
    if tag:
        templates = [t for t in templates if t.tags and tag in t.tags]
    
    return [PromptTemplateResponse.model_validate(t) for t in templates]


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get a specific template (must be system template or owned by user)"""
    result = await session.execute(
        select(PromptTemplate).where(
            and_(
                PromptTemplate.id == template_id,
                or_(
                    PromptTemplate.is_system == True,
                    PromptTemplate.user_id == user.id
                )
            )
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return PromptTemplateResponse.model_validate(template)


@router.post("", response_model=PromptTemplateResponse)
async def create_template(
    data: PromptTemplateCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Create a new prompt template for the current user"""
    # Check for duplicate name within user's templates (not system templates)
    query = select(PromptTemplate).where(
        and_(
            PromptTemplate.name == data.name,
            or_(
                PromptTemplate.is_system == True,
                PromptTemplate.user_id == user.id
            )
        )
    )
    result = await session.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Template with this name already exists")
    
    template = PromptTemplate(
        **data.model_dump(),
        user_id=user.id,
        is_system=False,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    
    return PromptTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_template(
    template_id: int,
    data: PromptTemplateUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update a prompt template (only own templates, not system templates)"""
    # Get template that belongs to this user
    result = await session.execute(
        select(PromptTemplate).where(
            and_(
                PromptTemplate.id == template_id,
                PromptTemplate.user_id == user.id
            )
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        # Check if it's a system template
        sys_result = await session.execute(
            select(PromptTemplate).where(
                and_(PromptTemplate.id == template_id, PromptTemplate.is_system == True)
            )
        )
        if sys_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Cannot modify system templates")
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    
    await session.commit()
    await session.refresh(template)
    
    return PromptTemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Delete a prompt template (only own templates, not system templates)"""
    # Get template that belongs to this user
    result = await session.execute(
        select(PromptTemplate).where(
            and_(
                PromptTemplate.id == template_id,
                PromptTemplate.user_id == user.id
            )
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        # Check if it's a system template
        sys_result = await session.execute(
            select(PromptTemplate).where(
                and_(PromptTemplate.id == template_id, PromptTemplate.is_system == True)
            )
        )
        if sys_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Cannot delete system templates")
        raise HTTPException(status_code=404, detail="Template not found")
    
    await session.delete(template)
    await session.commit()
    
    return {"status": "deleted", "id": template_id}
