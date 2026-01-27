"""
Datasets API - CRUD operations for datasets and rows
All data is scoped to the company specified in X-Company-ID header.
Supports streaming upload for large CSV files.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from datetime import datetime
import asyncio

from app.db import get_session, async_session_maker
from app.models import Dataset, DataRow, EnrichmentStatus, Folder, Company, User
from app.schemas import (
    DatasetCreate,
    DatasetResponse,
    DatasetListResponse,
    DatasetUpdate,
    GoogleSheetsImport,
    DataRowResponse,
    DataRowsPageResponse,
    FolderCreate,
    FolderUpdate,
    FolderResponse,
)
from app.services import import_service
from app.api.companies import get_current_user, get_required_company, get_optional_company
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])
folder_router = APIRouter(prefix="/folders", tags=["folders"])

# File size threshold for streaming (10MB)
STREAMING_THRESHOLD = 10 * 1024 * 1024


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List all datasets for the current company with pagination"""
    # Get total count
    count_query = select(func.count(Dataset.id)).where(
        and_(Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    total = await session.scalar(count_query) or 0
    
    # Get datasets
    query = (
        select(Dataset)
        .where(and_(Dataset.company_id == company.id, Dataset.deleted_at == None))
        .order_by(Dataset.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(query)
    datasets = result.scalars().all()
    
    return DatasetListResponse(
        datasets=[DatasetResponse.model_validate(d) for d in datasets],
        total=total
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get a specific dataset"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    return DatasetResponse.model_validate(dataset)


@router.post("/upload-csv", response_model=DatasetResponse)
async def upload_csv(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Upload a CSV file and create a dataset.
    For small files (<10MB), loads into memory.
    For large files, use /upload-csv-streaming endpoint.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB. Use streaming endpoint for large files."
        )
    
    content = await file.read()
    
    try:
        columns, rows = import_service.parse_csv(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create dataset
    dataset = Dataset(
        company_id=company.id,
        name=name or file.filename.replace('.csv', ''),
        source_type="csv",
        original_filename=file.filename,
        columns=columns,
        row_count=len(rows),
    )
    session.add(dataset)
    await session.flush()
    
    # Create rows in batches
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        data_rows = [
            DataRow(
                dataset_id=dataset.id,
                row_index=i + j,
                data=row,
                enriched_data={},
                enrichment_status=EnrichmentStatus.PENDING,
            )
            for j, row in enumerate(batch)
        ]
        session.add_all(data_rows)
        await session.flush()
    
    await session.commit()
    await session.refresh(dataset)
    
    logger.info(f"Created dataset {dataset.id} with {len(rows)} rows for company {company.id}")
    
    return DatasetResponse.model_validate(dataset)


@router.post("/upload-csv-streaming", response_model=DatasetResponse)
async def upload_csv_streaming(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = None,
    company: Company = Depends(get_required_company),
):
    """
    Upload large CSV file using streaming.
    Memory-efficient for files up to 100MB+.
    Processes file in chunks without loading entire file into memory.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    dataset_name = name or file.filename.replace('.csv', '')
    company_id = company.id
    
    # Create dataset first (we'll update row_count after)
    async with async_session_maker() as session:
        dataset = Dataset(
            company_id=company_id,
            name=dataset_name,
            source_type="csv",
            original_filename=file.filename,
            columns=[],  # Will be updated
            row_count=0,  # Will be updated
        )
        session.add(dataset)
        await session.commit()
        await session.refresh(dataset)
        dataset_id = dataset.id
    
    total_rows = 0
    columns = []
    row_index_offset = 0
    
    async def process_batch(cols: list, rows: list, batch_index: int):
        """Callback to process each batch of rows"""
        nonlocal total_rows, columns, row_index_offset
        
        if not columns:
            columns = cols
        
        async with async_session_maker() as session:
            data_rows = [
                DataRow(
                    dataset_id=dataset_id,
                    row_index=row_index_offset + i,
                    data=row,
                    enriched_data={},
                    enrichment_status=EnrichmentStatus.PENDING,
                )
                for i, row in enumerate(rows)
            ]
            session.add_all(data_rows)
            await session.commit()
        
        row_index_offset += len(rows)
        total_rows += len(rows)
        logger.debug(f"Dataset {dataset_id}: processed batch {batch_index}, total rows: {total_rows}")
    
    try:
        # Process file in streaming mode
        columns, total_rows = await import_service.parse_csv_streaming(
            file.file,
            process_batch,
            batch_size=1000
        )
        
        # Update dataset with final counts
        async with async_session_maker() as session:
            result = await session.execute(
                select(Dataset).where(Dataset.id == dataset_id)
            )
            dataset = result.scalar_one()
            dataset.columns = columns
            dataset.row_count = total_rows
            await session.commit()
            await session.refresh(dataset)
        
        logger.info(f"Created dataset {dataset_id} with {total_rows} rows via streaming for company {company_id}")
        
        return DatasetResponse.model_validate(dataset)
        
    except Exception as e:
        # Cleanup on error
        logger.error(f"Streaming upload failed: {e}")
        async with async_session_maker() as session:
            await session.execute(
                select(Dataset).where(Dataset.id == dataset_id)
            )
            # Delete the incomplete dataset
            result = await session.execute(
                select(Dataset).where(Dataset.id == dataset_id)
            )
            dataset = result.scalar_one_or_none()
            if dataset:
                await session.delete(dataset)
                await session.commit()
        
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")


@router.post("/import-google-sheets", response_model=DatasetResponse)
async def import_google_sheets(
    data: GoogleSheetsImport,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Import from Google Sheets URL"""
    try:
        columns, rows, sheet_name = await import_service.import_google_sheet(data.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create dataset
    dataset = Dataset(
        company_id=company.id,
        name=data.name or f"Google Sheet - {sheet_name}",
        source_type="google_sheets",
        source_url=data.url,
        columns=columns,
        row_count=len(rows),
    )
    session.add(dataset)
    await session.flush()
    
    # Create rows in batches
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        data_rows = [
            DataRow(
                dataset_id=dataset.id,
                row_index=i + j,
                data=row,
                enriched_data={},
                enrichment_status=EnrichmentStatus.PENDING,
            )
            for j, row in enumerate(batch)
        ]
        session.add_all(data_rows)
        await session.flush()
    
    await session.commit()
    await session.refresh(dataset)
    
    return DatasetResponse.model_validate(dataset)


@router.get("/{dataset_id}/rows", response_model=DataRowsPageResponse)
async def get_dataset_rows(
    dataset_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000),
    status_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get rows for a dataset with pagination"""
    # Verify dataset exists and belongs to company
    dataset_query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    dataset_result = await session.execute(dataset_query)
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Build query
    base_query = select(DataRow).where(DataRow.dataset_id == dataset_id)
    
    if status_filter:
        try:
            status = EnrichmentStatus(status_filter)
            base_query = base_query.where(DataRow.enrichment_status == status)
        except ValueError:
            pass
    
    # Get total count
    count_query = select(func.count(DataRow.id)).where(DataRow.dataset_id == dataset_id)
    if status_filter:
        try:
            status = EnrichmentStatus(status_filter)
            count_query = count_query.where(DataRow.enrichment_status == status)
        except ValueError:
            pass
    total = await session.scalar(count_query) or 0
    
    # Get rows with pagination
    offset = (page - 1) * page_size
    query = base_query.order_by(DataRow.row_index).offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return DataRowsPageResponse(
        rows=[DataRowResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{dataset_id}/all-columns")
async def get_all_columns(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Get ALL columns for a dataset, including enriched columns.
    Returns both original data columns and any columns added via enrichment.
    """
    # Get dataset
    dataset_query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    dataset_result = await session.execute(dataset_query)
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get original columns from dataset
    original_columns = list(dataset.columns or [])
    
    # Find all enriched columns by scanning rows
    enriched_columns = set()
    rows_query = select(DataRow.enriched_data).where(DataRow.dataset_id == dataset_id).limit(100)
    rows_result = await session.execute(rows_query)
    
    for (enriched_data,) in rows_result:
        if enriched_data:
            enriched_columns.update(enriched_data.keys())
    
    # Filter out columns already in original (some might be duplicated)
    enriched_only = [c for c in sorted(enriched_columns) if c not in original_columns]
    
    # Combine: original columns first, then enriched
    all_columns = original_columns + enriched_only
    
    return {
        "dataset_id": dataset_id,
        "original_columns": original_columns,
        "enriched_columns": enriched_only,
        "all_columns": all_columns,
        "total": len(all_columns)
    }


@router.post("/{dataset_id}/sync-enriched-columns")
async def sync_enriched_columns(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Sync enriched columns to dataset columns list.
    Call this to make enriched columns appear in the table UI.
    """
    # Get dataset
    dataset_query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    dataset_result = await session.execute(dataset_query)
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Find all enriched columns
    enriched_columns = set()
    rows_query = select(DataRow.enriched_data).where(DataRow.dataset_id == dataset_id).limit(500)
    rows_result = await session.execute(rows_query)
    
    for (enriched_data,) in rows_result:
        if enriched_data:
            enriched_columns.update(enriched_data.keys())
    
    # Get current columns
    current_columns = list(dataset.columns or [])
    
    # Add enriched columns that aren't already present
    added_columns = []
    for col in sorted(enriched_columns):
        if col not in current_columns:
            current_columns.append(col)
            added_columns.append(col)
    
    if added_columns:
        # Update dataset columns (new list for SQLAlchemy change detection)
        dataset.columns = current_columns
        await session.commit()
    
    return {
        "dataset_id": dataset_id,
        "columns_added": added_columns,
        "total_columns": len(current_columns),
        "all_columns": current_columns
    }


@router.patch("/{dataset_id}/rename")
async def rename_dataset(
    dataset_id: int,
    name: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Rename a dataset"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset.name = name
    await session.commit()
    
    return {"status": "renamed", "id": dataset_id, "name": name}


@router.patch("/{dataset_id}/rename-column")
async def rename_column(
    dataset_id: int,
    old_name: str = Query(..., min_length=1),
    new_name: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Rename a column in a dataset"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    if old_name not in dataset.columns:
        raise HTTPException(status_code=400, detail=f"Column '{old_name}' not found")
    
    if new_name in dataset.columns and new_name != old_name:
        raise HTTPException(status_code=400, detail=f"Column '{new_name}' already exists")
    
    # Update columns list
    new_columns = [new_name if c == old_name else c for c in dataset.columns]
    dataset.columns = new_columns
    
    # Update all rows to rename the column key in data
    rows_query = select(DataRow).where(DataRow.dataset_id == dataset_id)
    rows_result = await session.execute(rows_query)
    rows = rows_result.scalars().all()
    
    for row in rows:
        if old_name in row.data:
            new_data = {new_name if k == old_name else k: v for k, v in row.data.items()}
            row.data = new_data
    
    await session.commit()
    
    return {"status": "renamed", "old_name": old_name, "new_name": new_name}


@router.delete("/{dataset_id}/columns/{column_name}")
async def delete_column(
    dataset_id: int,
    column_name: str,
    is_enriched: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete a column from a dataset"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get all rows
    rows_query = select(DataRow).where(DataRow.dataset_id == dataset_id)
    rows_result = await session.execute(rows_query)
    rows = rows_result.scalars().all()
    
    if is_enriched:
        # Delete from enriched_data in all rows
        for row in rows:
            if column_name in row.enriched_data:
                new_enriched = {k: v for k, v in row.enriched_data.items() if k != column_name}
                row.enriched_data = new_enriched
    else:
        # Delete from regular data and columns list
        if column_name in dataset.columns:
            dataset.columns = [c for c in dataset.columns if c != column_name]
            for row in rows:
                if column_name in row.data:
                    new_data = {k: v for k, v in row.data.items() if k != column_name}
                    row.data = new_data
    
    await session.commit()
    
    return {"status": "deleted", "column": column_name, "is_enriched": is_enriched}


@router.delete("/{dataset_id}/rows")
async def delete_rows(
    dataset_id: int,
    row_ids: List[int] = Query(...),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete specific rows from a dataset"""
    # Verify dataset exists
    dataset_query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    dataset_result = await session.execute(dataset_query)
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Delete rows
    delete_query = select(DataRow).where(
        DataRow.dataset_id == dataset_id,
        DataRow.id.in_(row_ids)
    )
    result = await session.execute(delete_query)
    rows = result.scalars().all()
    
    deleted_count = 0
    for row in rows:
        await session.delete(row)
        deleted_count += 1
    
    # Update row count
    dataset.row_count -= deleted_count
    
    await session.commit()
    
    return {"status": "deleted", "count": deleted_count}


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Soft delete a dataset and all its rows"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Soft delete
    dataset.deleted_at = datetime.utcnow()
    await session.commit()
    
    return {"status": "deleted", "id": dataset_id}


@router.patch("/{dataset_id}")
async def update_dataset(
    dataset_id: int,
    data: DatasetUpdate,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update a dataset (name, description, folder_id)"""
    query = select(Dataset).where(
        and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
    )
    result = await session.execute(query)
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    if data.name is not None:
        dataset.name = data.name
    if data.description is not None:
        dataset.description = data.description
    if data.folder_id is not None:
        dataset.folder_id = data.folder_id if data.folder_id > 0 else None
    
    await session.commit()
    await session.refresh(dataset)
    
    return DatasetResponse.model_validate(dataset)


@router.post("/{dataset_id}/mark-exported")
async def mark_rows_exported(
    dataset_id: int,
    row_ids: List[int],
    column_name: str = Query(..., description="Column name to store export status"),
    export_target: str = Query(..., description="Export target (e.g., 'instantly', 'getsales')"),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Mark rows as exported by adding/updating an enriched column"""
    # Verify dataset exists
    dataset = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == dataset_id, Dataset.company_id == company.id, Dataset.deleted_at == None)
        )
    )
    dataset = dataset.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows
    query = select(DataRow).where(
        DataRow.dataset_id == dataset_id,
        DataRow.id.in_(row_ids)
    )
    result = await session.execute(query)
    rows = result.scalars().all()
    
    # Update enriched_data with export status
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    for row in rows:
        row.enriched_data = {
            **row.enriched_data,
            column_name: f"{export_target} ({timestamp})"
        }
    
    await session.commit()
    
    return {
        "success": True,
        "rows_marked": len(rows),
        "column_name": column_name
    }


# ============ Folder Endpoints ============

@folder_router.get("", response_model=List[FolderResponse])
async def list_folders(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List all folders for the current company"""
    query = select(Folder).where(Folder.company_id == company.id).order_by(Folder.name)
    result = await session.execute(query)
    folders = result.scalars().all()
    return [FolderResponse.model_validate(f) for f in folders]


@folder_router.post("", response_model=FolderResponse)
async def create_folder(
    data: FolderCreate,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Create a new folder"""
    folder = Folder(
        company_id=company.id,
        name=data.name,
        parent_id=data.parent_id
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return FolderResponse.model_validate(folder)


@folder_router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    data: FolderUpdate,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update a folder"""
    query = select(Folder).where(
        and_(Folder.id == folder_id, Folder.company_id == company.id)
    )
    result = await session.execute(query)
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if data.name is not None:
        folder.name = data.name
    if data.parent_id is not None:
        folder.parent_id = data.parent_id if data.parent_id > 0 else None
    
    await session.commit()
    await session.refresh(folder)
    return FolderResponse.model_validate(folder)


@folder_router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Delete a folder (datasets inside will be moved to root)"""
    query = select(Folder).where(
        and_(Folder.id == folder_id, Folder.company_id == company.id)
    )
    result = await session.execute(query)
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Move datasets in this folder to root
    datasets_query = select(Dataset).where(Dataset.folder_id == folder_id)
    datasets_result = await session.execute(datasets_query)
    for dataset in datasets_result.scalars().all():
        dataset.folder_id = None
    
    await session.delete(folder)
    await session.commit()
    
    return {"status": "deleted", "id": folder_id}
