from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict
from pydantic import BaseModel
from io import BytesIO
from app.db import get_session
from app.models import Dataset, DataRow
from app.services.export_service import export_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    format: str = "csv"  # csv, instantly, smartlead, google_sheets
    include_enriched: bool = True
    selected_row_ids: Optional[List[int]] = None
    # Column mappings for specific formats
    email_column: Optional[str] = None
    first_name_column: Optional[str] = None
    last_name_column: Optional[str] = None
    company_column: Optional[str] = None
    linkedin_url_column: Optional[str] = None
    message_column: Optional[str] = None
    custom_columns: Optional[Dict[str, str]] = None


class GoogleSheetsExportRequest(BaseModel):
    spreadsheet_url: str  # Existing sheet URL to append to
    sheet_name: Optional[str] = None
    include_enriched: bool = True
    selected_row_ids: Optional[List[int]] = None


@router.post("/{dataset_id}/csv")
async def export_csv(
    dataset_id: int,
    request: ExportRequest,
    session: AsyncSession = Depends(get_session),
):
    """Export dataset to CSV file"""
    # Get dataset
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows
    query = select(DataRow).where(DataRow.dataset_id == dataset_id)
    if request.selected_row_ids:
        query = query.where(DataRow.id.in_(request.selected_row_ids))
    query = query.order_by(DataRow.row_index)
    
    result = await session.execute(query)
    rows = result.scalars().all()
    
    # Convert to dict format
    rows_data = [
        {"data": row.data, "enriched_data": row.enriched_data}
        for row in rows
    ]
    
    # Generate CSV based on format
    if request.format == "instantly":
        if not request.email_column:
            raise HTTPException(status_code=400, detail="email_column is required for Instantly export")
        csv_content = export_service.export_to_instantly_csv(
            rows_data,
            dataset.columns,
            request.email_column,
            request.first_name_column,
            request.last_name_column,
            request.company_column,
            request.custom_columns,
        )
        filename = f"{dataset.name}_instantly.csv"
    elif request.format == "smartlead":
        csv_content = export_service.export_to_smartlead_csv(
            rows_data,
            dataset.columns,
            request.linkedin_url_column,
            request.first_name_column,
            request.last_name_column,
            request.company_column,
            request.email_column,
            request.message_column,
        )
        filename = f"{dataset.name}_smartlead.csv"
    else:
        csv_content = export_service.export_to_csv(
            rows_data,
            dataset.columns,
            request.include_enriched,
        )
        filename = f"{dataset.name}_export.csv"
    
    # Return as file download
    output = BytesIO(csv_content.encode('utf-8'))
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{dataset_id}/preview")
async def preview_export(
    dataset_id: int,
    format: str = Query("csv"),
    limit: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Preview export data (first N rows)"""
    # Get dataset
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get first N rows
    query = (
        select(DataRow)
        .where(DataRow.dataset_id == dataset_id)
        .order_by(DataRow.row_index)
        .limit(limit)
    )
    
    result = await session.execute(query)
    rows = result.scalars().all()
    
    # Convert to preview format
    rows_data = [
        {"data": row.data, "enriched_data": row.enriched_data}
        for row in rows
    ]
    
    prepared = export_service.prepare_row_data(rows_data, dataset.columns, include_enriched=True)
    
    # Get all columns
    all_columns = list(dataset.columns)
    if prepared:
        enriched_cols = [k for k in prepared[0].keys() if k not in dataset.columns]
        all_columns.extend(sorted(enriched_cols))
    
    return {
        "columns": all_columns,
        "original_columns": dataset.columns,
        "rows": prepared,
        "total_rows": dataset.row_count,
    }


@router.post("/{dataset_id}/google-sheets")
async def export_to_google_sheets(
    dataset_id: int,
    request: GoogleSheetsExportRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Export dataset to Google Sheets.
    Note: This generates data that can be pasted or used with Google Sheets API.
    For actual Google Sheets integration, you would need OAuth setup.
    """
    # Get dataset
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows
    query = select(DataRow).where(DataRow.dataset_id == dataset_id)
    if request.selected_row_ids:
        query = query.where(DataRow.id.in_(request.selected_row_ids))
    query = query.order_by(DataRow.row_index)
    
    result = await session.execute(query)
    rows = result.scalars().all()
    
    # Convert to dict format
    rows_data = [
        {"data": row.data, "enriched_data": row.enriched_data}
        for row in rows
    ]
    
    # Generate Google Sheets data format
    sheets_data = export_service.generate_google_sheets_data(
        rows_data,
        dataset.columns,
        request.include_enriched,
    )
    
    return {
        "status": "success",
        "message": "Data prepared for Google Sheets",
        "data": sheets_data,
        "row_count": len(sheets_data) - 1,  # Minus header row
        "column_count": len(sheets_data[0]) if sheets_data else 0,
        "instructions": "Copy this data or use Google Sheets API to import. For automatic sync, set up OAuth with Google Sheets API.",
    }
