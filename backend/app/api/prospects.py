"""
Prospects API endpoints - All Prospects CRM
All data is scoped to the company specified in X-Company-ID header.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
import csv
import io

from app.db import get_session
from app.models.prospect import Prospect, ProspectActivity
from app.models.dataset import DataRow, Dataset
from app.models import Company
from app.schemas.prospect import (
    ProspectResponse,
    ProspectListResponse,
    ProspectUpdate,
    ProspectActivityResponse,
    AddToProspectsRequest,
    AddToProspectsResponse,
    SuggestMappingRequest,
    FieldMappingSuggestion,
    FieldMapping,
    ProspectStats,
    TagsUpdateRequest,
    NotesUpdateRequest,
    StatusUpdateRequest,
    CORE_FIELDS,
    LEAD_STATUSES,
)
from app.services.prospects_service import prospects_service
from app.services.field_mapper import field_mapper_service
from app.services.default_mappings import get_default_mappings, smart_field_mapping
from app.api.companies import get_required_company

router = APIRouter(prefix="/prospects", tags=["Prospects"])


@router.get("", response_model=ProspectListResponse)
async def get_prospects(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    search: Optional[str] = Query(None),
    # Filter params
    status: Optional[str] = Query(None),
    sent_to_email: Optional[bool] = Query(None),
    sent_to_linkedin: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    segment_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get paginated list of prospects with filtering and sorting"""
    # Build filters dict
    filters = {}
    if status:
        filters["status"] = status
    if sent_to_email is not None:
        filters["sent_to_email"] = sent_to_email
    if sent_to_linkedin is not None:
        filters["sent_to_linkedin"] = sent_to_linkedin
    if has_email:
        filters["email"] = {"operator": "isNotNull", "value": None}
    if has_linkedin:
        filters["linkedin_url"] = {"operator": "isNotNull", "value": None}
    if segment_id:
        filters["segment_id"] = segment_id
    
    prospects, total = await prospects_service.get_prospects(
        session,
        company_id=company.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        filters=filters if filters else None
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return ProspectListResponse(
        prospects=[ProspectResponse.model_validate(p) for p in prospects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=ProspectStats)
async def get_prospect_stats(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get prospect statistics"""
    return await prospects_service.get_stats(session, company_id=company.id)


@router.get("/columns")
async def get_all_columns(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get list of all available columns including custom fields"""
    return await prospects_service.get_all_columns(session, company_id=company.id)


@router.get("/core-fields")
async def get_core_fields():
    """Get list of core fields for mapping UI"""
    return CORE_FIELDS


@router.post("/suggest-mapping", response_model=FieldMappingSuggestion)
async def suggest_field_mapping(
    request: SuggestMappingRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get AI-powered field mapping suggestions for a dataset"""
    try:
        sample_data = request.sample_data
        if not sample_data and request.dataset_id:
            # Verify dataset belongs to company
            result = await session.execute(
                select(DataRow)
                .join(Dataset, DataRow.dataset_id == Dataset.id)
                .where(
                    and_(
                        DataRow.dataset_id == request.dataset_id,
                        Dataset.company_id == company.id
                    )
                )
                .limit(5)
            )
            rows = result.scalars().all()
            sample_data = []
            for row in rows:
                merged = {**(row.data or {}), **(row.enriched_data or {})}
                sample_data.append(merged)
        
        suggestion = await field_mapper_service.suggest_mappings(
            columns=request.columns,
            sample_data=sample_data,
            use_ai=True
        )
        
        return suggestion
    except Exception as e:
        import logging
        logging.error(f"Mapping suggestion failed: {e}")
        
        basic_mappings = [
            FieldMapping(
                source_column=col,
                target_field="custom",
                custom_field_name=col,
                confidence=0.5
            )
            for col in request.columns
        ]
        
        return FieldMappingSuggestion(
            mappings=basic_mappings,
            unmapped_columns=[]
        )


@router.post("/add-from-dataset", response_model=AddToProspectsResponse)
async def add_prospects_from_dataset(
    request: AddToProspectsRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Add prospects from a dataset with field mappings"""
    # Verify dataset belongs to company
    dataset_result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == request.dataset_id, Dataset.company_id == company.id)
        )
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # If no field mappings provided, use smart defaults
    field_mappings = request.field_mappings
    if not field_mappings:
        # Use smart mapping based on available columns
        if dataset.columns:
            field_mappings = smart_field_mapping(dataset.columns)
        else:
            field_mappings = get_default_mappings()
    
    result = await prospects_service.add_from_dataset(
        session=session,
        company_id=company.id,
        dataset_id=request.dataset_id,
        row_ids=request.row_ids,
        field_mappings=field_mappings
    )
    return result


@router.post("/import-direct")
async def import_prospects_direct(
    data: Dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Direct import of prospects from JSON data.
    Expects: { rows: [...], field_mappings: [...] }
    """
    rows = data.get("rows", [])
    field_mappings = data.get("field_mappings", [])
    
    if not rows:
        raise HTTPException(status_code=400, detail="No rows provided")
    
    new_count = 0
    updated_count = 0
    errors = []
    
    for idx, row in enumerate(rows):
        try:
            # Apply field mappings
            mapped_data: Dict[str, Any] = {}
            custom_fields: Dict[str, Any] = {}
            
            for mapping in field_mappings:
                source_col = mapping.get("source_column")
                target_field = mapping.get("target_field")
                custom_name = mapping.get("custom_field_name")
                
                if not source_col or target_field == "skip":
                    continue
                    
                value = row.get(source_col, "")
                if not value:
                    continue
                
                if target_field == "custom":
                    custom_fields[custom_name or source_col] = value
                else:
                    mapped_data[target_field] = value
            
            if custom_fields:
                mapped_data["custom_fields"] = custom_fields
            
            source_info = {
                "source": "direct_import",
                "row_index": idx,
                "added_at": "now"
            }
            
            # Find duplicate within company
            existing = await prospects_service.find_duplicate(
                session,
                company_id=company.id,
                email=mapped_data.get("email"),
                linkedin_url=mapped_data.get("linkedin_url"),
                first_name=mapped_data.get("first_name"),
                last_name=mapped_data.get("last_name"),
                full_name=mapped_data.get("full_name"),
                company_name=mapped_data.get("company_name"),
            )
            
            if existing:
                prospects_service.merge_prospect_data(existing, mapped_data, source_info)
                await prospects_service.add_activity(
                    session, existing.id, "updated",
                    "Merged data from direct import"
                )
                updated_count += 1
            else:
                prospect = prospects_service.create_prospect(session, company.id, mapped_data, source_info)
                await session.flush()
                await prospects_service.add_activity(
                    session, prospect.id, "added",
                    "Added from direct import"
                )
                new_count += 1
                
        except Exception as e:
            import logging
            logging.error(f"Error importing row {idx}: {e}")
            errors.append(f"Row {idx}: {str(e)}")
    
    await session.commit()
    
    return {
        "success": True,
        "new_prospects": new_count,
        "updated_prospects": updated_count,
        "total_processed": len(rows),
        "errors": errors[:10]  # Limit errors shown
    }


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get a single prospect by ID"""
    prospect = await prospects_service.get_prospect(session, prospect_id, company_id=company.id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.patch("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: int,
    updates: ProspectUpdate,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update a prospect"""
    prospect = await prospects_service.update_prospect(
        session, prospect_id, updates.model_dump(exclude_unset=True), company_id=company.id
    )
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.delete("/{prospect_id}")
async def delete_prospect(
    prospect_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete a prospect"""
    success = await prospects_service.delete_prospect(session, prospect_id, company_id=company.id)
    if not success:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {"success": True}


@router.get("/{prospect_id}/activities", response_model=List[ProspectActivityResponse])
async def get_prospect_activities(
    prospect_id: int,
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get activity history for a prospect"""
    # Verify prospect belongs to company
    prospect = await prospects_service.get_prospect(session, prospect_id, company_id=company.id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    activities = await prospects_service.get_prospect_activities(
        session, prospect_id, limit
    )
    return [ProspectActivityResponse.model_validate(a) for a in activities]


@router.post("/{prospect_id}/tags", response_model=ProspectResponse)
async def update_prospect_tags(
    prospect_id: int,
    request: TagsUpdateRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update prospect tags"""
    prospect = await prospects_service.update_tags(
        session, prospect_id, request.tags, company_id=company.id
    )
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.patch("/{prospect_id}/notes", response_model=ProspectResponse)
async def update_prospect_notes(
    prospect_id: int,
    request: NotesUpdateRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update prospect notes"""
    prospect = await prospects_service.update_notes(
        session, prospect_id, request.notes, company_id=company.id
    )
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.get("/statuses")
async def get_lead_statuses():
    """Get available lead statuses"""
    return LEAD_STATUSES


@router.patch("/{prospect_id}/status", response_model=ProspectResponse)
async def update_prospect_status(
    prospect_id: int,
    request: StatusUpdateRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update prospect status"""
    prospect = await prospects_service.update_status(
        session, prospect_id, request.status, company_id=company.id
    )
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.post("/mark-sent-email")
async def mark_prospects_sent_to_email(
    prospect_ids: List[int] = Body(...),
    campaign_id: str = Body(...),
    campaign_name: str = Body(...),
    tool: str = Body("instantly"),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Mark prospects as sent to email campaign"""
    count = await prospects_service.mark_sent_to_email(
        session, prospect_ids, campaign_id, campaign_name, tool, company_id=company.id
    )
    return {"success": True, "updated": count}


@router.post("/mark-sent-linkedin")
async def mark_prospects_sent_to_linkedin(
    prospect_ids: List[int] = Body(...),
    campaign_id: str = Body(...),
    campaign_name: str = Body(...),
    tool: str = Body("expandi"),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Mark prospects as sent to LinkedIn campaign"""
    count = await prospects_service.mark_sent_to_linkedin(
        session, prospect_ids, campaign_id, campaign_name, tool, company_id=company.id
    )
    return {"success": True, "updated": count}


@router.post("/export/csv")
async def export_prospects_csv(
    prospect_ids: Optional[List[int]] = Body(None),
    columns: Optional[List[str]] = Body(None),
    include_custom_fields: bool = Body(True),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export prospects as CSV"""
    prospects_data = await prospects_service.export_prospects(
        session,
        company_id=company.id,
        prospect_ids=prospect_ids,
        columns=columns,
        include_custom_fields=include_custom_fields
    )
    
    if not prospects_data:
        raise HTTPException(status_code=404, detail="No prospects to export")
    
    # Create CSV
    output = io.StringIO()
    
    # Get all columns
    all_columns = set()
    for row in prospects_data:
        all_columns.update(row.keys())
    
    # Order columns
    core_order = [
        "email", "first_name", "last_name", "full_name",
        "company_name", "job_title", "phone", "linkedin_url",
        "location", "country", "city", "industry",
        "company_size", "company_domain", "website",
        "sent_to_instantly", "sent_to_instantly_at", "instantly_campaign",
        "tags"
    ]
    ordered_columns = [c for c in core_order if c in all_columns]
    ordered_columns.extend(sorted([c for c in all_columns if c not in core_order]))
    
    writer = csv.DictWriter(output, fieldnames=ordered_columns)
    writer.writeheader()
    for row in prospects_data:
        writer.writerow({col: row.get(col, "") for col in ordered_columns})
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=prospects.csv"
        }
    )


@router.post("/export/clipboard")
async def export_prospects_clipboard(
    prospect_ids: Optional[List[int]] = Body(None),
    columns: Optional[List[str]] = Body(None),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export prospects as TSV for clipboard (paste into Google Sheets)"""
    prospects_data = await prospects_service.export_prospects(
        session,
        company_id=company.id,
        prospect_ids=prospect_ids,
        columns=columns,
        include_custom_fields=True
    )
    
    if not prospects_data:
        return {"data": [], "row_count": 0}
    
    # Get all columns
    all_columns = list(prospects_data[0].keys()) if prospects_data else []
    
    # Build TSV data
    rows = [all_columns]  # Header
    for row in prospects_data:
        rows.append([str(row.get(col, "")) for col in all_columns])
    
    return {
        "data": rows,
        "row_count": len(prospects_data),
        "columns": all_columns
    }


@router.delete("")
async def delete_multiple_prospects(
    prospect_ids: List[int] = Body(...),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete multiple prospects"""
    deleted = 0
    for pid in prospect_ids:
        if await prospects_service.delete_prospect(session, pid, company_id=company.id):
            deleted += 1
    return {"success": True, "deleted": deleted}
