from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from typing import List
from datetime import datetime
from app.db import get_session, async_session_maker
from app.models import Dataset, DataRow, PromptTemplate, EnrichmentJob, EnrichmentStatus, Company
from app.schemas import (
    EnrichmentJobCreate,
    EnrichmentJobResponse,
    EnrichmentPreviewRequest,
    EnrichmentPreviewResponse,
    WebsiteScraperRequest,
    WebsiteScraperResponse,
)
from app.services import openai_service
from app.services.scraper_service import scraper_service
from app.services.kb_context import resolve_tags
from app.core.config import settings
from app.api.companies import get_required_company
from .websocket import notify_job_progress, notify_job_complete
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.get("/jobs/active")
async def get_active_jobs(
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get all active enrichment jobs for the company"""
    from sqlalchemy import or_
    
    # Get all datasets for this company
    datasets_query = select(Dataset).where(Dataset.company_id == company.id)
    datasets_result = await session.execute(datasets_query)
    dataset_ids = [d.id for d in datasets_result.scalars().all()]
    
    if not dataset_ids:
        return {"active_jobs": []}
    
    # Get active jobs for these datasets
    query = select(EnrichmentJob).where(
        and_(
            EnrichmentJob.dataset_id.in_(dataset_ids),
            or_(
                EnrichmentJob.status == EnrichmentStatus.PENDING,
                EnrichmentJob.status == EnrichmentStatus.PROCESSING
            )
        )
    ).order_by(EnrichmentJob.id.desc())
    
    result = await session.execute(query)
    jobs = result.scalars().all()
    
    # Calculate ETA for each job
    import time
    job_list = []
    for job in jobs:
        job_data = {
            "job_id": job.id,
            "dataset_id": job.dataset_id,
            "status": job.status.value,
            "total": job.total_rows,
            "processed": job.processed_rows,
            "failed": job.failed_rows,
            "percentage": round((job.processed_rows / job.total_rows) * 100, 1) if job.total_rows > 0 else 0,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        
        # Calculate ETA
        if job.started_at and job.processed_rows > 0 and job.total_rows > job.processed_rows:
            elapsed = (datetime.utcnow() - job.started_at).total_seconds()
            rate = job.processed_rows / elapsed
            remaining = job.total_rows - job.processed_rows
            eta_seconds = int(remaining / rate) if rate > 0 else None
            if eta_seconds:
                job_data["eta_seconds"] = eta_seconds
                job_data["eta_formatted"] = format_eta_simple(eta_seconds)
        
        job_list.append(job_data)
    
    return {"active_jobs": job_list}


def format_eta_simple(seconds: int) -> str:
    """Format ETA in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


async def check_job_cancelled(session: AsyncSession, job_id: int) -> bool:
    """Check if job was cancelled by user"""
    # Use fresh query to get latest status (avoid session cache issues)
    from sqlalchemy import select
    result = await session.execute(
        select(EnrichmentJob.status).where(EnrichmentJob.id == job_id)
    )
    status = result.scalar_one_or_none()
    if status is None:
        return True
    return status == EnrichmentStatus.CANCELLED


async def run_enrichment_job(job_id: int, company_id: int):
    """Background task to run enrichment with real-time progress updates"""
    async with async_session_maker() as session:
        dataset_id = None
        start_time = None
        try:
            # Get job
            job = await session.get(EnrichmentJob, job_id)
            if not job:
                return
            
            dataset_id = job.dataset_id
            
            # Check if already cancelled
            if job.status == EnrichmentStatus.CANCELLED:
                logger.info(f"[Job {job_id}] Already cancelled, skipping")
                return
            
            # Update job status
            job.status = EnrichmentStatus.PROCESSING
            job.started_at = datetime.utcnow()
            start_time = job.started_at.timestamp()
            await session.commit()
            
            logger.info(f"[Job {job_id}] Started enrichment for dataset {dataset_id}")
            
            # Get prompt template if specified
            system_prompt = None
            prompt_template = None
            
            if job.prompt_template_id:
                template = await session.get(PromptTemplate, job.prompt_template_id)
                if template:
                    prompt_template = template.prompt_template
                    system_prompt = template.system_prompt
            
            if not prompt_template:
                prompt_template = job.custom_prompt
            
            if not prompt_template:
                job.status = EnrichmentStatus.FAILED
                job.error_message = "No prompt template specified"
                await session.commit()
                await notify_job_complete(job_id, dataset_id, False, "No prompt template specified")
                return
            
            # Resolve @tags from Knowledge Base (with company_id)
            if '@' in prompt_template:
                tag_result = await resolve_tags(prompt_template, session, company_id)
                prompt_template = tag_result["enriched_prompt"]
                logger.info(f"Resolved {len(tag_result['tags_found'])} KB tags in prompt")
            
            # Get rows to process
            query = select(DataRow).where(DataRow.dataset_id == job.dataset_id)
            
            if job.selected_row_ids:
                query = query.where(DataRow.id.in_(job.selected_row_ids))
            
            result = await session.execute(query)
            rows = result.scalars().all()
            
            job.total_rows = len(rows)
            await session.commit()
            
            # Send initial progress
            await notify_job_progress(job_id, 0, job.total_rows, "processing", 0, start_time)
            logger.info(f"[Job {job_id}] Processing {job.total_rows} rows...")
            
            # Process in batches
            batch_size = settings.BATCH_SIZE
            success_count = 0
            failed_count = 0
            total_processed = 0
            
            for i in range(0, len(rows), batch_size):
                # ===== CHECK IF JOB WAS CANCELLED =====
                if await check_job_cancelled(session, job_id):
                    logger.info(f"[Job {job_id}] Cancelled by user at {total_processed}/{job.total_rows}")
                    await notify_job_complete(
                        job_id, 
                        dataset_id, 
                        False, 
                        f"Cancelled by user. Processed {total_processed} rows ({success_count} success, {failed_count} failed)"
                    )
                    return
                
                batch = rows[i:i + batch_size]
                
                # Prepare batch data
                batch_data = [{"id": row.id, "data": row.data} for row in batch]
                
                # Enrich batch
                try:
                    results = await openai_service.enrich_batch(
                        batch_data,
                        prompt_template,
                        system_prompt,
                        job.model,
                        max_concurrent=settings.MAX_CONCURRENT_REQUESTS,
                    )
                except Exception as e:
                    logger.error(f"[Job {job_id}] Batch error: {e}")
                    # Mark batch as failed but continue
                    for row in batch:
                        row.enrichment_status = EnrichmentStatus.FAILED
                        row.error_message = str(e)
                        failed_count += 1
                        total_processed += 1
                    results = []
                
                # Update rows with results - SAVE INTERIM RESULTS IMMEDIATELY
                for res in results:
                    row_id = res["row_id"]
                    row = next((r for r in batch if r.id == row_id), None)
                    if not row:
                        continue
                    
                    total_processed += 1
                    
                    if res["success"]:
                        # Save result to enriched_data
                        row.enriched_data = {
                            **row.enriched_data,
                            job.output_column: res["result"]
                        }
                        row.enrichment_status = EnrichmentStatus.COMPLETED
                        row.last_enriched_at = datetime.utcnow()
                        success_count += 1
                    else:
                        row.enrichment_status = EnrichmentStatus.FAILED
                        row.error_message = res.get("error", "Unknown error")
                        failed_count += 1
                
                # Update job counters - processed = ALL (success + failed)
                job.processed_rows = total_processed
                job.failed_rows = failed_count
                
                # COMMIT INTERIM RESULTS - so they're saved even if job stops
                await session.commit()
                
                # Send progress update via WebSocket
                await notify_job_progress(
                    job_id, 
                    total_processed, 
                    job.total_rows, 
                    "processing",
                    failed_count,
                    start_time
                )
                
                # Log progress every 10% or every 500 rows
                percentage = (total_processed / job.total_rows) * 100
                if total_processed % max(1, min(500, job.total_rows // 10)) == 0 or percentage >= 100:
                    logger.info(
                        f"[Job {job_id}] Progress: {total_processed}/{job.total_rows} "
                        f"({percentage:.1f}%) - {success_count} success, {failed_count} failed"
                    )
                
                # Small delay between batches to prevent overwhelming
                await asyncio.sleep(0.1)
            
            # Final check if cancelled during last batch
            if await check_job_cancelled(session, job_id):
                logger.info(f"[Job {job_id}] Cancelled during final processing")
                return
            
            # Complete job
            job.status = EnrichmentStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.processed_rows = total_processed
            job.failed_rows = failed_count
            
            # ADD NEW COLUMN TO DATASET COLUMNS LIST
            # This ensures the enriched column appears in the table/UI
            dataset_query = select(Dataset).where(Dataset.id == dataset_id)
            dataset_result = await session.execute(dataset_query)
            dataset = dataset_result.scalar_one_or_none()
            
            if dataset and job.output_column:
                # Create new columns list (for SQLAlchemy change detection)
                current_columns = list(dataset.columns or [])
                if job.output_column not in current_columns:
                    current_columns.append(job.output_column)
                    dataset.columns = current_columns
                    logger.info(f"[Job {job_id}] Added column '{job.output_column}' to dataset {dataset_id}")
            
            await session.commit()
            
            logger.info(f"[Job {job_id}] COMPLETED: {success_count} success, {failed_count} failed")
            
            # Notify completion
            await notify_job_complete(
                job_id, 
                dataset_id, 
                True, 
                f"Completed: {success_count} success, {failed_count} failed out of {total_processed}"
            )
            
        except Exception as e:
            logger.error(f"Enrichment job {job_id} failed: {str(e)}")
            try:
                job.status = EnrichmentStatus.FAILED
                job.error_message = str(e)
                await session.commit()
            except:
                pass
            
            if dataset_id:
                await notify_job_complete(job_id, dataset_id, False, str(e))


@router.post("/jobs", response_model=EnrichmentJobResponse)
async def create_enrichment_job(
    data: EnrichmentJobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Create a new enrichment job"""
    # Verify dataset exists AND belongs to this company
    result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == data.dataset_id, Dataset.company_id == company.id)
        )
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Verify prompt template if specified
    if data.prompt_template_id:
        template = await session.get(PromptTemplate, data.prompt_template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
    
    # Create job
    job = EnrichmentJob(
        dataset_id=data.dataset_id,
        prompt_template_id=data.prompt_template_id,
        custom_prompt=data.custom_prompt,
        output_column=data.output_column,
        model=data.model,
        selected_row_ids=data.selected_row_ids,
        status=EnrichmentStatus.PENDING,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    # Start background processing with company_id
    background_tasks.add_task(run_enrichment_job, job.id, company.id)
    
    return EnrichmentJobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=EnrichmentJobResponse)
async def get_enrichment_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get enrichment job status"""
    # Get job and verify it belongs to a dataset owned by this company
    job = await session.get(EnrichmentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify dataset belongs to company
    result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == job.dataset_id, Dataset.company_id == company.id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")
    
    return EnrichmentJobResponse.model_validate(job)


@router.get("/jobs", response_model=List[EnrichmentJobResponse])
async def list_enrichment_jobs(
    dataset_id: int = None,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List enrichment jobs for this company's datasets"""
    # Get all dataset IDs for this company
    datasets_query = select(Dataset.id).where(Dataset.company_id == company.id)
    datasets_result = await session.execute(datasets_query)
    company_dataset_ids = [d[0] for d in datasets_result.fetchall()]
    
    if not company_dataset_ids:
        return []
    
    query = select(EnrichmentJob).where(
        EnrichmentJob.dataset_id.in_(company_dataset_ids)
    ).order_by(EnrichmentJob.created_at.desc())
    
    if dataset_id:
        # Also verify the specific dataset belongs to company
        if dataset_id not in company_dataset_ids:
            raise HTTPException(status_code=404, detail="Dataset not found")
        query = query.where(EnrichmentJob.dataset_id == dataset_id)
    
    result = await session.execute(query)
    jobs = result.scalars().all()
    
    return [EnrichmentJobResponse.model_validate(j) for j in jobs]


@router.post("/jobs/{job_id}/stop")
async def stop_enrichment_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Stop a running enrichment job. Interim results are preserved."""
    job = await session.get(EnrichmentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify dataset belongs to company
    result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == job.dataset_id, Dataset.company_id == company.id)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [EnrichmentStatus.PROCESSING, EnrichmentStatus.PENDING]:
        raise HTTPException(status_code=400, detail=f"Job is not running (status: {job.status.value})")
    
    # Save current progress before cancelling
    processed = job.processed_rows
    failed = job.failed_rows
    total = job.total_rows
    
    job.status = EnrichmentStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await session.commit()
    
    logger.info(f"[Job {job_id}] CANCELLED by user. Progress: {processed}/{total}, Failed: {failed}")
    
    await notify_job_complete(
        job_id, 
        job.dataset_id, 
        False, 
        f"Cancelled. Processed {processed}/{total} rows. Results saved."
    )
    
    return {
        "message": "Job stopped successfully",
        "job_id": job_id,
        "processed": processed,
        "failed": failed,
        "total": total,
        "results_saved": True
    }


@router.post("/preview", response_model=EnrichmentPreviewResponse)
async def preview_enrichment(
    data: EnrichmentPreviewRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Preview enrichment on specific rows (for testing)"""
    # Verify dataset belongs to company
    ds_result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == data.dataset_id, Dataset.company_id == company.id)
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows
    query = select(DataRow).where(
        DataRow.dataset_id == data.dataset_id,
        DataRow.id.in_(data.row_ids)
    )
    result = await session.execute(query)
    rows = result.scalars().all()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No rows found")
    
    # Get prompt template
    system_prompt = None
    prompt_template = None
    
    if data.prompt_template_id:
        template = await session.get(PromptTemplate, data.prompt_template_id)
        if template:
            prompt_template = template.prompt_template
            system_prompt = template.system_prompt
    
    if not prompt_template:
        prompt_template = data.custom_prompt
    
    if not prompt_template:
        raise HTTPException(status_code=400, detail="No prompt specified")
    
    # Resolve @tags from Knowledge Base (with company_id)
    if '@' in prompt_template:
        tag_result = await resolve_tags(prompt_template, session, company.id)
        prompt_template = tag_result["enriched_prompt"]
    
    # Run enrichment
    batch_data = [{"id": row.id, "data": row.data} for row in rows]
    results = await openai_service.enrich_batch(
        batch_data,
        prompt_template,
        system_prompt,
        data.model,
        max_concurrent=5,
    )
    
    total_tokens = sum(r.get("tokens_used", 0) for r in results)
    
    return EnrichmentPreviewResponse(
        results=results,
        model_used=data.model,
        tokens_used=total_tokens,
    )


async def run_scraper_job(
    dataset_id: int,
    row_ids: List[int],
    url_column: str,
    output_column: str,
    timeout: int = 10,
):
    """Background task to scrape websites and update rows"""
    async with async_session_maker() as session:
        try:
            # Get rows to process
            query = select(DataRow).where(
                DataRow.dataset_id == dataset_id,
                DataRow.id.in_(row_ids)
            )
            result = await session.execute(query)
            rows = result.scalars().all()
            
            if not rows:
                logger.warning(f"No rows found for scraping job, dataset={dataset_id}")
                return
            
            # Prepare URLs for scraping
            urls_to_scrape = []
            for row in rows:
                url = row.data.get(url_column, "") or row.enriched_data.get(url_column, "")
                if url:
                    urls_to_scrape.append({"row_id": row.id, "url": str(url)})
            
            if not urls_to_scrape:
                logger.warning(f"No URLs found in column {url_column}")
                return
            
            # Scrape websites
            results = await scraper_service.scrape_batch(
                urls_to_scrape,
                timeout=timeout,
                max_concurrent=5,
                delay_between_requests=0.5,
            )
            
            # Update rows with scraped content
            for res in results:
                row = next((r for r in rows if r.id == res["row_id"]), None)
                if not row:
                    continue
                
                if res["success"]:
                    row.enriched_data = {
                        **row.enriched_data,
                        output_column: res["text"]
                    }
                    row.enrichment_status = EnrichmentStatus.COMPLETED
                else:
                    row.enriched_data = {
                        **row.enriched_data,
                        output_column: res["error"]
                    }
                    row.enrichment_status = EnrichmentStatus.FAILED
                    row.error_message = res["error"]
                
                row.last_enriched_at = datetime.utcnow()
            
            await session.commit()
            
            # Notify completion via WebSocket
            succeeded = sum(1 for r in results if r["success"])
            failed = len(results) - succeeded
            await notify_job_complete(
                0,  # No job_id for scraper
                dataset_id,
                True,
                f"Scraped {succeeded} websites, {failed} failed"
            )
            
        except Exception as e:
            logger.error(f"Scraper job failed: {e}")
            await notify_job_complete(0, dataset_id, False, str(e))


from pydantic import BaseModel

class EnhancePromptRequest(BaseModel):
    rough_prompt: str
    columns: List[str]
    output_description: str = ""
    language: str = "english"

class EnhancePromptResponse(BaseModel):
    enhanced_prompt: str
    suggested_output_column: str


@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
async def enhance_prompt(
    data: EnhancePromptRequest,
    company: Company = Depends(get_required_company),
):
    """
    Use AI to enhance a rough prompt description into a well-structured prompt.
    Supports any language input and outputs an optimized English prompt.
    """
    
    system_prompt = """You are an expert prompt engineer. Your task is to transform rough, informal prompt descriptions (in any language) into well-structured, effective prompts for data enrichment.

Rules:
1. Output ONLY the enhanced prompt text, nothing else
2. Use {{column_name}} syntax for variables - use exact column names provided
3. Be concise but specific
4. Include clear output format instructions
5. Add edge case handling if relevant
6. The prompt should work for processing one row at a time
7. Always respond with the prompt in English, even if input was in another language

Available columns to use as variables: {columns}

Example input: "найди емейл по имени и домену"
Example output: "Find the professional email address for {{full_name}} who works at {{domain}}. Use common email patterns like firstname@domain, firstname.lastname@domain, f.lastname@domain. Return only the most likely email address, or 'not_found' if cannot determine."
"""
    
    columns_str = ", ".join(data.columns)
    
    user_prompt = f"""Transform this rough prompt description into a professional, well-structured prompt:

Description: {data.rough_prompt}
{f'Expected output: {data.output_description}' if data.output_description else ''}
Available columns: {columns_str}

Return ONLY the enhanced prompt, nothing else."""

    try:
        result = await openai_service.generate_single(
            user_prompt,
            system_prompt.format(columns=columns_str),
            model="gpt-4o-mini",
        )
        
        enhanced = result.strip()
        
        # Generate suggested output column name
        suggest_col_prompt = f"Based on this prompt, suggest a short snake_case column name (2-3 words max) for storing the output. Only respond with the column name, nothing else.\n\nPrompt: {enhanced}"
        suggested_col = await openai_service.generate_single(
            suggest_col_prompt,
            "You suggest short, descriptive snake_case column names. Only output the column name.",
            model="gpt-4o-mini",
        )
        suggested_col = suggested_col.strip().lower().replace(" ", "_").replace("-", "_")
        if not suggested_col or len(suggested_col) > 30:
            suggested_col = "ai_result"
        
        return EnhancePromptResponse(
            enhanced_prompt=enhanced,
            suggested_output_column=suggested_col,
        )
        
    except Exception as e:
        logger.error(f"Failed to enhance prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enhance prompt: {str(e)}")


@router.post("/scrape", response_model=WebsiteScraperResponse)
async def scrape_websites(
    data: WebsiteScraperRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Scrape websites and extract text content.
    
    This endpoint fetches web pages and extracts readable text content,
    handling errors gracefully for inaccessible sites.
    """
    # Verify dataset exists AND belongs to this company
    result = await session.execute(
        select(Dataset).where(
            and_(Dataset.id == data.dataset_id, Dataset.company_id == company.id)
        )
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Verify URL column exists
    if data.url_column not in dataset.columns:
        # Check if it's an enriched column
        query = select(DataRow).where(DataRow.dataset_id == data.dataset_id).limit(1)
        result = await session.execute(query)
        sample_row = result.scalar_one_or_none()
        
        if not sample_row or data.url_column not in sample_row.enriched_data:
            raise HTTPException(
                status_code=400, 
                detail=f"Column '{data.url_column}' not found in dataset"
            )
    
    # Get row IDs to process
    if data.row_ids:
        row_ids = data.row_ids
    else:
        # Get all row IDs
        query = select(DataRow.id).where(DataRow.dataset_id == data.dataset_id)
        result = await session.execute(query)
        row_ids = [r[0] for r in result.fetchall()]
    
    if not row_ids:
        raise HTTPException(status_code=400, detail="No rows to process")
    
    # Start background scraping task
    background_tasks.add_task(
        run_scraper_job,
        data.dataset_id,
        row_ids,
        data.url_column,
        data.output_column,
        data.timeout,
    )
    
    return WebsiteScraperResponse(
        success=True,
        processed=len(row_ids),
        succeeded=0,  # Will be updated after background task
        failed=0,
        errors=[],
    )
