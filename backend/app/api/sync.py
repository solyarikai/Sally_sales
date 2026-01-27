"""Sync API - Manage automatic file synchronization"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.db import get_session
from app.models import Dataset, Company
from app.services import sync_service
from .companies import get_required_company
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


class SyncFileRequest(BaseModel):
    dataset_id: int
    file_path: str


class WatchFileRequest(BaseModel):
    dataset_id: int
    file_path: str


class WatchedPathResponse(BaseModel):
    path: str
    company_id: int
    dataset_id: int
    dataset_name: str


@router.get("/status")
async def get_sync_status(
    company: Company = Depends(get_required_company)
):
    """Get synchronization status"""
    watched_paths = sync_service.get_watched_paths()
    
    # Filter by company
    company_paths = [p for p in watched_paths if p['company_id'] == company.id]
    
    return {
        "enabled": len(company_paths) > 0,
        "watched_paths": len(company_paths),
        "total_watched": len(watched_paths)
    }


@router.get("/watched", response_model=List[WatchedPathResponse])
async def list_watched_paths(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """List all watched paths for this company"""
    watched_paths = sync_service.get_watched_paths()
    
    # Filter by company
    company_paths = [p for p in watched_paths if p['company_id'] == company.id]
    
    # Get dataset names
    result = []
    for path_info in company_paths:
        dataset = await session.get(Dataset, path_info['dataset_id'])
        if dataset:
            result.append(WatchedPathResponse(
                path=path_info['path'],
                company_id=path_info['company_id'],
                dataset_id=path_info['dataset_id'],
                dataset_name=dataset.name
            ))
    
    return result


@router.post("/watch")
async def watch_file(
    data: WatchFileRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Start watching a file for automatic sync"""
    # Verify dataset belongs to company
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset or dataset.company_id != company.id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Start watching
    sync_service.watch_file(
        data.file_path,
        company.id,
        data.dataset_id
    )
    
    return {
        "success": True,
        "message": f"Started watching: {data.file_path}",
        "dataset_id": data.dataset_id,
        "dataset_name": dataset.name
    }


@router.delete("/watch")
async def stop_watching(
    path: str,
    company: Company = Depends(get_required_company)
):
    """Stop watching a file"""
    # Verify path belongs to company
    watched_paths = sync_service.get_watched_paths()
    path_info = next((p for p in watched_paths if p['path'] == path), None)
    
    if not path_info:
        raise HTTPException(status_code=404, detail="Path not watched")
    
    if path_info['company_id'] != company.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    sync_service.stop_watching(path)
    
    return {
        "success": True,
        "message": f"Stopped watching: {path}"
    }


@router.post("/manual")
async def manual_sync(
    data: SyncFileRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company)
):
    """Manually sync a file to database"""
    # Verify dataset belongs to company
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset or dataset.company_id != company.id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Sync in background
    background_tasks.add_task(
        sync_service.manual_sync,
        data.file_path,
        data.dataset_id,
        company.id
    )
    
    return {
        "success": True,
        "message": f"Sync started for: {data.file_path}",
        "dataset_id": data.dataset_id
    }


@router.post("/setup-defaults")
async def setup_default_syncs(
    company: Company = Depends(get_required_company)
):
    """Setup default sync configurations for company projects"""
    if company.name == "Maincard":
        # Setup Maincard default syncs
        sync_service.watch_file(
            "/Users/theo/LeadGen Automation/Maincard/leads/maincard_leads_verified.csv",
            company_id=company.id,
            dataset_id=2  # "existing" dataset
        )
        message = "Setup Maincard default syncs"
    
    elif company.name == "Paybis":
        # Setup Paybis default syncs (when needed)
        message = "No default syncs configured for Paybis yet"
    
    else:
        message = f"No default syncs configured for {company.name}"
    
    return {
        "success": True,
        "message": message,
        "watched_paths": len(sync_service.get_watched_paths())
    }
