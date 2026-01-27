"""
Prospects Service
Handles deduplication, merging, CRUD, and activity tracking for prospects.
All operations are scoped to a company_id for data isolation.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, desc, asc, and_
import logging

from app.models.prospect import Prospect, ProspectActivity
from app.models.dataset import Dataset, DataRow
from app.schemas.prospect import (
    FieldMapping, AddToProspectsResponse, ProspectStats, CORE_FIELD_NAMES
)
from app.services.field_mapper import field_mapper_service

logger = logging.getLogger(__name__)


def normalize_linkedin_url(url: str) -> Optional[str]:
    """Normalize LinkedIn URL for comparison"""
    if not url:
        return None
    url = url.lower().strip()
    url = url.split('?')[0].rstrip('/')
    if '/in/' in url:
        parts = url.split('/in/')
        if len(parts) > 1:
            return f"linkedin.com/in/{parts[1].split('/')[0]}"
    return url


def normalize_email(email: str) -> Optional[str]:
    """Normalize email for comparison"""
    if not email:
        return None
    return email.lower().strip()


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names"""
    if not name1 or not name2:
        return 0.0
    return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()


class ProspectsService:
    """Service for managing prospects"""
    
    async def find_duplicate(
        self,
        session: AsyncSession,
        company_id: int,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> Optional[Prospect]:
        """Find existing prospect using smart deduplication within a company."""
        # 1. Try email match
        if email:
            normalized_email = normalize_email(email)
            result = await session.execute(
                select(Prospect).where(
                    and_(
                        Prospect.company_id == company_id,
                        func.lower(Prospect.email) == normalized_email,
                        Prospect.deleted_at == None
                    )
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
        
        # 2. Try LinkedIn URL match
        if linkedin_url:
            normalized_linkedin = normalize_linkedin_url(linkedin_url)
            if normalized_linkedin:
                result = await session.execute(
                    select(Prospect).where(
                        and_(
                            Prospect.company_id == company_id,
                            Prospect.linkedin_url.isnot(None),
                            Prospect.deleted_at == None
                        )
                    )
                )
                prospects = result.scalars().all()
                for prospect in prospects:
                    if normalize_linkedin_url(prospect.linkedin_url) == normalized_linkedin:
                        return prospect
        
        # 3. Try name + company match (fuzzy)
        if company_name and (full_name or (first_name and last_name)):
            result = await session.execute(
                select(Prospect).where(
                    and_(
                        Prospect.company_id == company_id,
                        Prospect.company_name.isnot(None),
                        Prospect.deleted_at == None
                    )
                )
            )
            candidates = result.scalars().all()
            for prospect in candidates:
                company_sim = calculate_name_similarity(company_name, prospect.company_name or "")
                if company_sim < 0.85:
                    continue
                
                if full_name and prospect.full_name:
                    if calculate_name_similarity(full_name, prospect.full_name) >= 0.85:
                        return prospect
                
                if first_name and last_name and prospect.first_name and prospect.last_name:
                    if (calculate_name_similarity(first_name, prospect.first_name) >= 0.85 and 
                        calculate_name_similarity(last_name, prospect.last_name) >= 0.85):
                        return prospect
        
        return None
    
    def merge_prospect_data(
        self,
        existing: Prospect,
        new_data: Dict[str, Any],
        source_info: Dict[str, Any]
    ) -> Prospect:
        """Merge new data into existing prospect."""
        # Update core fields (only if new value exists and existing is empty)
        for field in CORE_FIELD_NAMES:
            if field == "custom_fields":
                continue
            new_value = new_data.get(field)
            if new_value and not getattr(existing, field, None):
                setattr(existing, field, new_value)
        
        # Merge custom fields - CREATE NEW DICT for SQLAlchemy to detect change
        existing_custom = dict(existing.custom_fields or {})  # Copy to new dict!
        new_custom = new_data.get("custom_fields", {})
        
        fields_added = []
        for key, value in new_custom.items():
            if value:  # Only add if value is truthy
                if key not in existing_custom:
                    existing_custom[key] = value
                    fields_added.append(key)
                elif existing_custom.get(key) != value:
                    # Optionally update existing field if values differ
                    # For now, we only add new fields
                    pass
        
        # Assign NEW dict to trigger SQLAlchemy change detection
        existing.custom_fields = existing_custom
        
        # Update sources list - also create new list
        sources = list(existing.sources or [])
        sources.append(source_info)
        existing.sources = sources
        existing.updated_at = datetime.utcnow()
        
        return existing
    
    def create_prospect(
        self,
        session: AsyncSession,
        company_id: int,
        prospect_data: Dict[str, Any],
        source_info: Dict[str, Any]
    ) -> Prospect:
        """Create a new prospect"""
        prospect = Prospect(
            company_id=company_id,
            email=prospect_data.get("email"),
            linkedin_url=prospect_data.get("linkedin_url"),
            first_name=prospect_data.get("first_name"),
            last_name=prospect_data.get("last_name"),
            full_name=prospect_data.get("full_name"),
            company_name=prospect_data.get("company_name"),
            company_domain=prospect_data.get("company_domain"),
            company_linkedin=prospect_data.get("company_linkedin"),
            job_title=prospect_data.get("job_title"),
            phone=prospect_data.get("phone"),
            location=prospect_data.get("location"),
            country=prospect_data.get("country"),
            city=prospect_data.get("city"),
            industry=prospect_data.get("industry"),
            company_size=prospect_data.get("company_size"),
            website=prospect_data.get("website"),
            custom_fields=prospect_data.get("custom_fields", {}),
            sources=[source_info],
            tags=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(prospect)
        return prospect
    
    async def add_activity(
        self,
        session: AsyncSession,
        prospect_id: int,
        activity_type: str,
        description: str = None,
        activity_data: Dict[str, Any] = None
    ) -> ProspectActivity:
        """Add activity to prospect"""
        activity = ProspectActivity(
            prospect_id=prospect_id,
            activity_type=activity_type,
            description=description,
            activity_data=activity_data or {},
            created_at=datetime.utcnow()
        )
        session.add(activity)
        return activity
    
    async def add_from_dataset(
        self,
        session: AsyncSession,
        company_id: int,
        dataset_id: int,
        row_ids: Optional[List[int]],
        field_mappings: List[FieldMapping]
    ) -> AddToProspectsResponse:
        """Add prospects from a dataset."""
        result = await session.execute(
            select(Dataset).where(
                and_(Dataset.id == dataset_id, Dataset.company_id == company_id)
            )
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            return AddToProspectsResponse(
                success=False, total_processed=0, new_prospects=0,
                updated_prospects=0, errors=["Dataset not found"]
            )
        
        query = select(DataRow).where(DataRow.dataset_id == dataset_id)
        if row_ids:
            query = query.where(DataRow.id.in_(row_ids))
        result = await session.execute(query)
        rows = result.scalars().all()
        
        if not rows:
            return AddToProspectsResponse(
                success=False, total_processed=0, new_prospects=0,
                updated_prospects=0, errors=["No rows found"]
            )
        
        new_prospects = 0
        updated_prospects = 0
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
                    company_id=company_id,
                    email=mapped_data.get("email"),
                    linkedin_url=mapped_data.get("linkedin_url"),
                    first_name=mapped_data.get("first_name"),
                    last_name=mapped_data.get("last_name"),
                    full_name=mapped_data.get("full_name"),
                    company_name=mapped_data.get("company_name"),
                )
                
                if existing:
                    self.merge_prospect_data(existing, mapped_data, source_info)
                    await self.add_activity(
                        session, existing.id, "updated",
                        f"Merged data from {dataset.name}",
                        {"dataset_id": dataset_id, "row_id": row.id}
                    )
                    updated_prospects += 1
                else:
                    prospect = self.create_prospect(session, company_id, mapped_data, source_info)
                    await session.flush()  # Get the ID
                    await self.add_activity(
                        session, prospect.id, "added",
                        f"Added from {dataset.name}",
                        {"dataset_id": dataset_id, "row_id": row.id}
                    )
                    new_prospects += 1
                    
            except Exception as e:
                logger.error(f"Error processing row {row.id}: {e}")
                errors.append(f"Row {row.id}: {str(e)}")
        
        await session.commit()
        
        return AddToProspectsResponse(
            success=True,
            total_processed=len(rows),
            new_prospects=new_prospects,
            updated_prospects=updated_prospects,
            errors=errors[:10]
        )
    
    async def get_prospects(
        self,
        session: AsyncSession,
        company_id: int,
        page: int = 1,
        page_size: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Prospect], int]:
        """Get paginated list of prospects with filtering and sorting"""
        query = select(Prospect).where(
            and_(Prospect.company_id == company_id, Prospect.deleted_at == None)
        )
        
        # Search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Prospect.email.ilike(search_term),
                    Prospect.first_name.ilike(search_term),
                    Prospect.last_name.ilike(search_term),
                    Prospect.full_name.ilike(search_term),
                    Prospect.company_name.ilike(search_term),
                    Prospect.job_title.ilike(search_term),
                    Prospect.phone.ilike(search_term),
                )
            )
        
        # Apply filters
        if filters:
            for field, condition in filters.items():
                if hasattr(Prospect, field):
                    column = getattr(Prospect, field)
                    if isinstance(condition, dict):
                        op = condition.get("operator", "eq")
                        value = condition.get("value")
                        if op == "eq":
                            query = query.where(column == value)
                        elif op == "ne":
                            query = query.where(column != value)
                        elif op == "contains":
                            query = query.where(column.ilike(f"%{value}%"))
                        elif op == "startsWith":
                            query = query.where(column.ilike(f"{value}%"))
                        elif op == "endsWith":
                            query = query.where(column.ilike(f"%{value}"))
                        elif op == "isNull":
                            query = query.where(column.is_(None))
                        elif op == "isNotNull":
                            query = query.where(column.isnot(None))
                        elif op == "in":
                            query = query.where(column.in_(value))
                    else:
                        # Simple equality
                        query = query.where(column == condition)
        
        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        
        # Apply sorting
        if hasattr(Prospect, sort_by):
            order_column = getattr(Prospect, sort_by)
            if sort_order == "desc":
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            query = query.order_by(desc(Prospect.created_at))
        
        # Pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await session.execute(query)
        prospects = result.scalars().all()
        
        return list(prospects), total
    
    async def get_prospect(
        self,
        session: AsyncSession,
        prospect_id: int,
        company_id: Optional[int] = None
    ) -> Optional[Prospect]:
        """Get a single prospect by ID"""
        query = select(Prospect).where(
            and_(Prospect.id == prospect_id, Prospect.deleted_at == None)
        )
        if company_id:
            query = query.where(Prospect.company_id == company_id)
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_prospect_activities(
        self,
        session: AsyncSession,
        prospect_id: int,
        limit: int = 50
    ) -> List[ProspectActivity]:
        """Get activities for a prospect"""
        result = await session.execute(
            select(ProspectActivity)
            .where(ProspectActivity.prospect_id == prospect_id)
            .order_by(desc(ProspectActivity.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def update_prospect(
        self,
        session: AsyncSession,
        prospect_id: int,
        updates: Dict[str, Any],
        company_id: Optional[int] = None
    ) -> Optional[Prospect]:
        """Update a prospect"""
        prospect = await self.get_prospect(session, prospect_id, company_id)
        if not prospect:
            return None
        
        for field, value in updates.items():
            if hasattr(prospect, field) and field not in ['id', 'created_at', 'company_id']:
                setattr(prospect, field, value)
        
        prospect.updated_at = datetime.utcnow()
        await session.commit()
        return prospect
    
    async def update_tags(
        self,
        session: AsyncSession,
        prospect_id: int,
        tags: List[str],
        company_id: Optional[int] = None
    ) -> Optional[Prospect]:
        """Update prospect tags"""
        prospect = await self.get_prospect(session, prospect_id, company_id)
        if not prospect:
            return None
        
        old_tags = prospect.tags or []
        prospect.tags = tags
        prospect.updated_at = datetime.utcnow()
        
        await self.add_activity(
            session, prospect_id, "tagged",
            f"Tags updated",
            {"old_tags": old_tags, "new_tags": tags}
        )
        
        await session.commit()
        return prospect
    
    async def update_notes(
        self,
        session: AsyncSession,
        prospect_id: int,
        notes: str,
        company_id: Optional[int] = None
    ) -> Optional[Prospect]:
        """Update prospect notes"""
        prospect = await self.get_prospect(session, prospect_id, company_id)
        if not prospect:
            return None
        
        prospect.notes = notes
        prospect.updated_at = datetime.utcnow()
        
        await self.add_activity(
            session, prospect_id, "note_added",
            "Notes updated"
        )
        
        await session.commit()
        return prospect
    
    async def mark_sent_to_email(
        self,
        session: AsyncSession,
        prospect_ids: List[int],
        campaign_id: str,
        campaign_name: str,
        tool: str = "instantly",
        company_id: Optional[int] = None
    ) -> int:
        """Mark prospects as sent to email campaign"""
        count = 0
        for pid in prospect_ids:
            prospect = await self.get_prospect(session, pid, company_id)
            if prospect:
                prospect.sent_to_email = True
                prospect.sent_to_email_at = datetime.utcnow()
                prospect.email_campaign_id = campaign_id
                prospect.email_campaign_name = campaign_name
                prospect.email_tool = tool
                prospect.updated_at = datetime.utcnow()
                
                # Update status to contacted if still new
                if prospect.status == 'new':
                    prospect.status = 'contacted'
                    prospect.status_updated_at = datetime.utcnow()
                
                await self.add_activity(
                    session, pid, "sent_email",
                    f"Sent to email campaign: {campaign_name} ({tool})",
                    {"campaign_id": campaign_id, "campaign_name": campaign_name, "tool": tool}
                )
                count += 1
        
        await session.commit()
        return count
    
    async def mark_sent_to_linkedin(
        self,
        session: AsyncSession,
        prospect_ids: List[int],
        campaign_id: str,
        campaign_name: str,
        tool: str = "expandi",
        company_id: Optional[int] = None
    ) -> int:
        """Mark prospects as sent to LinkedIn campaign"""
        count = 0
        for pid in prospect_ids:
            prospect = await self.get_prospect(session, pid, company_id)
            if prospect:
                prospect.sent_to_linkedin = True
                prospect.sent_to_linkedin_at = datetime.utcnow()
                prospect.linkedin_campaign_id = campaign_id
                prospect.linkedin_campaign_name = campaign_name
                prospect.linkedin_tool = tool
                prospect.updated_at = datetime.utcnow()
                
                # Update status to contacted if still new
                if prospect.status == 'new':
                    prospect.status = 'contacted'
                    prospect.status_updated_at = datetime.utcnow()
                
                await self.add_activity(
                    session, pid, "sent_linkedin",
                    f"Sent to LinkedIn campaign: {campaign_name} ({tool})",
                    {"campaign_id": campaign_id, "campaign_name": campaign_name, "tool": tool}
                )
                count += 1
        
        await session.commit()
        return count
    
    async def update_status(
        self,
        session: AsyncSession,
        prospect_id: int,
        status: str,
        company_id: Optional[int] = None
    ) -> Optional[Prospect]:
        """Update prospect status"""
        prospect = await self.get_prospect(session, prospect_id, company_id)
        if not prospect:
            return None
        
        old_status = prospect.status
        prospect.status = status
        prospect.status_updated_at = datetime.utcnow()
        prospect.updated_at = datetime.utcnow()
        
        await self.add_activity(
            session, prospect_id, "status_changed",
            f"Status changed from {old_status} to {status}",
            {"old_status": old_status, "new_status": status}
        )
        
        await session.commit()
        return prospect
    
    async def get_stats(self, session: AsyncSession, company_id: int) -> ProspectStats:
        """Get prospect statistics for a company"""
        base_filter = and_(Prospect.company_id == company_id, Prospect.deleted_at == None)
        
        total_result = await session.execute(
            select(func.count(Prospect.id)).where(base_filter)
        )
        total = total_result.scalar() or 0
        
        email_result = await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.email.isnot(None), Prospect.email != "")
            )
        )
        with_email = email_result.scalar() or 0
        
        linkedin_result = await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.linkedin_url.isnot(None), Prospect.linkedin_url != "")
            )
        )
        with_linkedin = linkedin_result.scalar() or 0
        
        sent_email_result = await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.sent_to_email == True)
            )
        )
        sent_email = sent_email_result.scalar() or 0
        
        sent_linkedin_result = await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.sent_to_linkedin == True)
            )
        )
        sent_linkedin = sent_linkedin_result.scalar() or 0
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.created_at >= week_ago)
            )
        )
        recent = recent_result.scalar() or 0
        
        # Status counts
        status_new = (await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.status == 'new')
            )
        )).scalar() or 0
        
        status_contacted = (await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.status == 'contacted')
            )
        )).scalar() or 0
        
        status_interested = (await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.status == 'interested')
            )
        )).scalar() or 0
        
        status_not_interested = (await session.execute(
            select(func.count(Prospect.id)).where(
                and_(base_filter, Prospect.status == 'not_interested')
            )
        )).scalar() or 0
        
        # Count prospects with completed calls (Call Date and Call Done status)
        call_done_result = await session.execute(
            select(Prospect).where(base_filter)
        )
        all_prospects = call_done_result.scalars().all()
        call_done = sum(
            1 for p in all_prospects
            if p.custom_fields and (
                (p.custom_fields.get('Call Date') and p.custom_fields.get('Status') == 'Call Done') or
                p.custom_fields.get('Call Date')
            )
        )
        
        return ProspectStats(
            total_prospects=total,
            prospects_with_email=with_email,
            prospects_with_linkedin=with_linkedin,
            sent_to_email=sent_email,
            sent_to_linkedin=sent_linkedin,
            recent_additions=recent,
            call_done=call_done,
            status_new=status_new,
            status_contacted=status_contacted,
            status_interested=status_interested,
            status_not_interested=status_not_interested
        )
    
    async def delete_prospect(
        self,
        session: AsyncSession,
        prospect_id: int,
        company_id: Optional[int] = None
    ) -> bool:
        """Soft delete a prospect"""
        prospect = await self.get_prospect(session, prospect_id, company_id)
        if prospect:
            prospect.deleted_at = datetime.utcnow()
            await session.commit()
            return True
        return False
    
    async def get_all_columns(
        self,
        session: AsyncSession,
        company_id: int
    ) -> List[Dict[str, Any]]:
        """Get all available columns including custom fields for a company"""
        # Core columns
        columns = [
            {"field": "email", "header": "Email", "type": "text"},
            {"field": "full_name", "header": "Full Name", "type": "text"},
            {"field": "first_name", "header": "First Name", "type": "text"},
            {"field": "last_name", "header": "Last Name", "type": "text"},
            {"field": "company_name", "header": "Company", "type": "text"},
            {"field": "company_domain", "header": "Domain", "type": "text"},
            {"field": "job_title", "header": "Job Title", "type": "text"},
            {"field": "phone", "header": "Phone", "type": "text"},
            {"field": "linkedin_url", "header": "LinkedIn", "type": "url"},
            {"field": "location", "header": "Location", "type": "text"},
            {"field": "country", "header": "Country", "type": "text"},
            {"field": "city", "header": "City", "type": "text"},
            {"field": "industry", "header": "Industry", "type": "text"},
            {"field": "company_size", "header": "Company Size", "type": "text"},
            {"field": "website", "header": "Website", "type": "url"},
            {"field": "sent_to_instantly", "header": "Sent to Instantly", "type": "boolean"},
            {"field": "sent_to_instantly_at", "header": "Sent to Instantly At", "type": "date"},
            {"field": "instantly_campaign_name", "header": "Instantly Campaign", "type": "text"},
            {"field": "sent_to_smartlead", "header": "Sent to Smartlead", "type": "boolean"},
            {"field": "tags", "header": "Tags", "type": "tags"},
            {"field": "created_at", "header": "Created", "type": "date"},
            {"field": "updated_at", "header": "Updated", "type": "date"},
        ]
        
        # Get unique custom field keys from company's prospects
        result = await session.execute(
            select(Prospect.custom_fields).where(
                and_(
                    Prospect.company_id == company_id,
                    Prospect.custom_fields.isnot(None),
                    Prospect.deleted_at == None
                )
            )
        )
        all_custom_fields = set()
        for (custom_fields,) in result:
            if custom_fields:
                all_custom_fields.update(custom_fields.keys())
        
        for field in sorted(all_custom_fields):
            columns.append({
                "field": f"custom_fields.{field}",
                "header": field,
                "type": "text",
                "custom": True
            })
        
        return columns
    
    async def export_prospects(
        self,
        session: AsyncSession,
        company_id: int,
        prospect_ids: Optional[List[int]] = None,
        columns: Optional[List[str]] = None,
        include_custom_fields: bool = True
    ) -> List[Dict[str, Any]]:
        """Export prospects as list of dicts"""
        query = select(Prospect).where(
            and_(Prospect.company_id == company_id, Prospect.deleted_at == None)
        )
        if prospect_ids:
            query = query.where(Prospect.id.in_(prospect_ids))
        
        result = await session.execute(query)
        prospects = result.scalars().all()
        
        export_result = []
        for prospect in prospects:
            row = {
                "email": prospect.email,
                "linkedin_url": prospect.linkedin_url,
                "first_name": prospect.first_name,
                "last_name": prospect.last_name,
                "full_name": prospect.full_name,
                "company_name": prospect.company_name,
                "company_domain": prospect.company_domain,
                "job_title": prospect.job_title,
                "phone": prospect.phone,
                "location": prospect.location,
                "country": prospect.country,
                "city": prospect.city,
                "industry": prospect.industry,
                "company_size": prospect.company_size,
                "website": prospect.website,
                "sent_to_instantly": prospect.sent_to_email,
                "sent_to_instantly_at": prospect.sent_to_email_at.isoformat() if prospect.sent_to_email_at else None,
                "instantly_campaign": prospect.email_campaign_name,
                "tags": ", ".join(prospect.tags) if prospect.tags else "",
            }
            
            if include_custom_fields and prospect.custom_fields:
                for key, value in prospect.custom_fields.items():
                    row[f"custom_{key}"] = value
            
            export_result.append(row)
        
        return export_result


prospects_service = ProspectsService()
