"""
Master Leads API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sql_delete
from typing import List, Optional
import csv
import io

from app.db import get_session
from app.models.master_lead import MasterLead
from app.models.dataset import Dataset, DataRow
from app.schemas.master_lead import (
    MasterLeadResponse,
    MasterLeadListResponse,
    AddToMasterRequest,
    AddToMasterResponse,
    SuggestMappingRequest,
    FieldMappingSuggestion,
    MasterLeadsStats,
    CORE_FIELDS,
)
from app.services.master_leads_service import master_leads_service
from app.services.field_mapper import field_mapper_service

router = APIRouter(prefix="/master-leads", tags=["Master Leads"])


@router.get("", response_model=MasterLeadListResponse)
async def get_master_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    source_dataset_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    """Get paginated list of master leads"""
    leads, total = await master_leads_service.get_leads(
        session,
        page=page,
        page_size=page_size,
        search=search,
        source_dataset_id=source_dataset_id
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return MasterLeadListResponse(
        leads=[MasterLeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=MasterLeadsStats)
async def get_master_leads_stats(session: AsyncSession = Depends(get_session)):
    """Get master leads statistics"""
    return await master_leads_service.get_stats(session)


@router.get("/core-fields")
async def get_core_fields():
    """Get list of core fields for mapping UI"""
    return CORE_FIELDS


@router.post("/suggest-mapping", response_model=FieldMappingSuggestion)
async def suggest_field_mapping(
    request: SuggestMappingRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Get AI-powered field mapping suggestions for a dataset.
    Pass columns and optionally sample_data for better AI suggestions.
    """
    try:
        # If sample_data not provided, get from dataset
        sample_data = request.sample_data
        if not sample_data and request.dataset_id:
            result = await session.execute(
                select(DataRow)
                .where(DataRow.dataset_id == request.dataset_id)
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
        # Fallback: return basic mappings without AI
        import logging
        logging.error(f"Mapping suggestion failed: {e}")
        
        from app.schemas.master_lead import FieldMapping
        basic_mappings = []
        for col in request.columns:
            basic_mappings.append(FieldMapping(
                source_column=col,
                target_field="custom",
                custom_field_name=col,
                confidence=0.5
            ))
        
        return FieldMappingSuggestion(
            mappings=basic_mappings,
            unmapped_columns=[]
        )


@router.post("/add-from-dataset", response_model=AddToMasterResponse)
async def add_leads_from_dataset(
    request: AddToMasterRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Add leads from a dataset to the master database.
    Uses provided field mappings for data transformation.
    Handles deduplication automatically.
    """
    result = await master_leads_service.add_from_dataset(
        session=session,
        dataset_id=request.dataset_id,
        row_ids=request.row_ids,
        field_mappings=request.field_mappings
    )
    
    return result


@router.get("/{lead_id}", response_model=MasterLeadResponse)
async def get_master_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a single master lead by ID"""
    lead = await session.get(MasterLead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return MasterLeadResponse.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_master_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a master lead"""
    success = await master_leads_service.delete_lead(session, lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True}


@router.post("/export")
async def export_master_leads(
    lead_ids: Optional[List[int]] = None,
    include_custom_fields: bool = True,
    session: AsyncSession = Depends(get_session)
):
    """Export master leads as CSV"""
    leads_data = await master_leads_service.export_leads(
        session,
        lead_ids=lead_ids,
        include_custom_fields=include_custom_fields
    )
    
    if not leads_data:
        raise HTTPException(status_code=404, detail="No leads to export")
    
    # Create CSV
    output = io.StringIO()
    
    # Get all columns
    all_columns = set()
    for row in leads_data:
        all_columns.update(row.keys())
    
    # Order columns: core fields first, then custom
    core_order = [
        "email", "first_name", "last_name", "full_name",
        "company_name", "job_title", "phone", "linkedin_url",
        "location", "country", "city", "industry",
        "company_size", "company_domain", "website"
    ]
    ordered_columns = [c for c in core_order if c in all_columns]
    ordered_columns.extend(sorted([c for c in all_columns if c not in core_order]))
    
    writer = csv.DictWriter(output, fieldnames=ordered_columns)
    writer.writeheader()
    for row in leads_data:
        writer.writerow({col: row.get(col, "") for col in ordered_columns})
    
    # Return as streaming response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=master_leads.csv"
        }
    )


@router.delete("")
async def delete_all_master_leads(
    confirm: bool = Query(False),
    session: AsyncSession = Depends(get_session)
):
    """Delete all master leads (requires confirm=true)"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must pass confirm=true to delete all leads"
        )
    
    result = await session.execute(sql_delete(MasterLead))
    await session.commit()
    
    return {"success": True, "deleted": result.rowcount}
