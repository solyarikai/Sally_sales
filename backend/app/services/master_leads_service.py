"""
Master Leads Service
Handles deduplication, merging, and CRUD operations for the master leads database.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, delete as sql_delete
import logging

from app.models.master_lead import MasterLead
from app.models.dataset import Dataset, DataRow
from app.schemas.master_lead import (
    FieldMapping, AddToMasterResponse, MasterLeadsStats, CORE_FIELD_NAMES
)
from app.services.field_mapper import field_mapper_service

logger = logging.getLogger(__name__)


from app.utils.normalization import normalize_linkedin_url, normalize_email, calculate_name_similarity


class MasterLeadsService:
    """Service for managing the master leads database"""
    
    async def find_duplicate(
        self,
        session: AsyncSession,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> Optional[MasterLead]:
        """Find existing lead using smart deduplication."""
        # 1. Try email match
        if email:
            normalized_email = normalize_email(email)
            result = await session.execute(
                select(MasterLead).where(func.lower(MasterLead.email) == normalized_email)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
        
        # 2. Try LinkedIn URL match
        if linkedin_url:
            normalized_linkedin = normalize_linkedin_url(linkedin_url)
            if normalized_linkedin:
                result = await session.execute(
                    select(MasterLead).where(MasterLead.linkedin_url.isnot(None))
                )
                leads = result.scalars().all()
                for lead in leads:
                    if normalize_linkedin_url(lead.linkedin_url) == normalized_linkedin:
                        return lead
        
        # 3. Try name + company match (fuzzy)
        if company_name and (full_name or (first_name and last_name)):
            result = await session.execute(
                select(MasterLead).where(MasterLead.company_name.isnot(None))
            )
            candidates = result.scalars().all()
            for lead in candidates:
                company_sim = calculate_name_similarity(company_name, lead.company_name or "")
                if company_sim < 0.85:
                    continue
                
                if full_name and lead.full_name:
                    if calculate_name_similarity(full_name, lead.full_name) >= 0.85:
                        return lead
                
                if first_name and last_name and lead.first_name and lead.last_name:
                    if (calculate_name_similarity(first_name, lead.first_name) >= 0.85 and 
                        calculate_name_similarity(last_name, lead.last_name) >= 0.85):
                        return lead
        
        return None
    
    def merge_lead_data(
        self,
        existing: MasterLead,
        new_data: Dict[str, Any],
        source_info: Dict[str, Any]
    ) -> MasterLead:
        """Merge new data into existing lead."""
        for field in CORE_FIELD_NAMES:
            if field == "custom_fields":
                continue
            new_value = new_data.get(field)
            if new_value and not getattr(existing, field, None):
                setattr(existing, field, new_value)
        
        existing_custom = existing.custom_fields or {}
        new_custom = new_data.get("custom_fields", {})
        for key, value in new_custom.items():
            if key not in existing_custom and value:
                existing_custom[key] = value
        existing.custom_fields = existing_custom
        
        sources = existing.sources or []
        sources.append(source_info)
        existing.sources = sources
        existing.updated_at = datetime.utcnow()
        
        return existing
    
    def create_lead(
        self,
        session: AsyncSession,
        lead_data: Dict[str, Any],
        source_info: Dict[str, Any]
    ) -> MasterLead:
        """Create a new master lead"""
        lead = MasterLead(
            email=lead_data.get("email"),
            linkedin_url=lead_data.get("linkedin_url"),
            first_name=lead_data.get("first_name"),
            last_name=lead_data.get("last_name"),
            full_name=lead_data.get("full_name"),
            company_name=lead_data.get("company_name"),
            company_domain=lead_data.get("company_domain"),
            company_linkedin=lead_data.get("company_linkedin"),
            job_title=lead_data.get("job_title"),
            phone=lead_data.get("phone"),
            location=lead_data.get("location"),
            country=lead_data.get("country"),
            city=lead_data.get("city"),
            industry=lead_data.get("industry"),
            company_size=lead_data.get("company_size"),
            website=lead_data.get("website"),
            custom_fields=lead_data.get("custom_fields", {}),
            sources=[source_info],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(lead)
        return lead
    
    async def add_from_dataset(
        self,
        session: AsyncSession,
        dataset_id: int,
        row_ids: Optional[List[int]],
        field_mappings: List[FieldMapping]
    ) -> AddToMasterResponse:
        """Add leads from a dataset to the master database."""
        dataset = await session.get(Dataset, dataset_id)
        if not dataset:
            return AddToMasterResponse(
                success=False, total_processed=0, new_leads=0,
                updated_leads=0, errors=["Dataset not found"]
            )
        
        query = select(DataRow).where(DataRow.dataset_id == dataset_id)
        if row_ids:
            query = query.where(DataRow.id.in_(row_ids))
        result = await session.execute(query)
        rows = result.scalars().all()
        
        if not rows:
            return AddToMasterResponse(
                success=False, total_processed=0, new_leads=0,
                updated_leads=0, errors=["No rows found"]
            )
        
        new_leads = 0
        updated_leads = 0
        errors: List[str] = []
        
        for row in rows:
            try:
                mapped_data = field_mapper_service.apply_mapping(
                    row.data or {}, row.enriched_data or {}, field_mappings
                )
                
                source_info = {
                    "dataset_id": dataset_id,
                    "dataset_name": dataset.name,
                    "row_id": row.id,
                    "added_at": datetime.utcnow().isoformat()
                }
                
                existing = await self.find_duplicate(
                    session,
                    email=mapped_data.get("email"),
                    linkedin_url=mapped_data.get("linkedin_url"),
                    first_name=mapped_data.get("first_name"),
                    last_name=mapped_data.get("last_name"),
                    full_name=mapped_data.get("full_name"),
                    company_name=mapped_data.get("company_name"),
                )
                
                if existing:
                    self.merge_lead_data(existing, mapped_data, source_info)
                    updated_leads += 1
                else:
                    self.create_lead(session, mapped_data, source_info)
                    new_leads += 1
                    
            except Exception as e:
                logger.error(f"Error processing row {row.id}: {e}")
                errors.append(f"Row {row.id}: {str(e)}")
        
        await session.commit()
        
        return AddToMasterResponse(
            success=True,
            total_processed=len(rows),
            new_leads=new_leads,
            updated_leads=updated_leads,
            errors=errors[:10]
        )
    
    async def get_leads(
        self,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        source_dataset_id: Optional[int] = None,
    ) -> Tuple[List[MasterLead], int]:
        """Get paginated list of master leads"""
        query = select(MasterLead)
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    MasterLead.email.ilike(search_term),
                    MasterLead.first_name.ilike(search_term),
                    MasterLead.last_name.ilike(search_term),
                    MasterLead.full_name.ilike(search_term),
                    MasterLead.company_name.ilike(search_term),
                )
            )
        
        # Get total
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        
        # Get paginated results
        result = await session.execute(
            query.order_by(MasterLead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        leads = result.scalars().all()
        
        return list(leads), total
    
    async def get_stats(self, session: AsyncSession) -> MasterLeadsStats:
        """Get master leads statistics"""
        total_result = await session.execute(select(func.count(MasterLead.id)))
        total = total_result.scalar() or 0
        
        email_result = await session.execute(
            select(func.count(MasterLead.id)).where(
                MasterLead.email.isnot(None), MasterLead.email != ""
            )
        )
        with_email = email_result.scalar() or 0
        
        linkedin_result = await session.execute(
            select(func.count(MasterLead.id)).where(
                MasterLead.linkedin_url.isnot(None), MasterLead.linkedin_url != ""
            )
        )
        with_linkedin = linkedin_result.scalar() or 0
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await session.execute(
            select(func.count(MasterLead.id)).where(MasterLead.created_at >= week_ago)
        )
        recent = recent_result.scalar() or 0
        
        return MasterLeadsStats(
            total_leads=total,
            leads_with_email=with_email,
            leads_with_linkedin=with_linkedin,
            sources_count={},
            recent_additions=recent
        )
    
    async def delete_lead(self, session: AsyncSession, lead_id: int) -> bool:
        """Delete a master lead"""
        lead = await session.get(MasterLead, lead_id)
        if lead:
            await session.delete(lead)
            await session.commit()
            return True
        return False
    
    async def export_leads(
        self,
        session: AsyncSession,
        lead_ids: Optional[List[int]] = None,
        include_custom_fields: bool = True
    ) -> List[Dict[str, Any]]:
        """Export leads as list of dicts"""
        query = select(MasterLead)
        if lead_ids:
            query = query.where(MasterLead.id.in_(lead_ids))
        
        result = await session.execute(query)
        leads = result.scalars().all()
        
        export_result = []
        for lead in leads:
            row = {
                "email": lead.email,
                "linkedin_url": lead.linkedin_url,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "full_name": lead.full_name,
                "company_name": lead.company_name,
                "company_domain": lead.company_domain,
                "job_title": lead.job_title,
                "phone": lead.phone,
                "location": lead.location,
                "country": lead.country,
                "city": lead.city,
                "industry": lead.industry,
                "company_size": lead.company_size,
                "website": lead.website,
            }
            
            if include_custom_fields and lead.custom_fields:
                for key, value in lead.custom_fields.items():
                    row[f"custom_{key}"] = value
            
            export_result.append(row)
        
        return export_result


master_leads_service = MasterLeadsService()
