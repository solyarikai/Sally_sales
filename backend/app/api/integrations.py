"""API endpoints for managing integrations (Instantly, Findymail, etc.)."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db import get_session, async_session_maker
from app.models import Dataset, DataRow, IntegrationSetting
from app.services import instantly_service, smartlead_service, findymail_service, millionverifier_service
from app.services.fireflies_service import fireflies_service
from app.schemas import FindymailEnrichmentRequest, FindymailEnrichmentResponse
from .websocket import notify_job_progress, notify_job_complete
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============ Schemas ============

class IntegrationStatus(BaseModel):
    name: str
    connected: bool
    has_api_key: bool


class AllIntegrationsResponse(BaseModel):
    integrations: List[IntegrationStatus]


class IntegrationConnectRequest(BaseModel):
    api_key: str


class InstantlyDetailsResponse(BaseModel):
    connected: bool
    campaigns: List[dict] = []


class FindymailDetailsResponse(BaseModel):
    connected: bool
    credits: Optional[dict] = None


class InstantlySendLeadsRequest(BaseModel):
    campaign_id: str
    dataset_id: int
    row_ids: Optional[List[int]] = None
    email_column: str
    first_name_column: Optional[str] = None
    last_name_column: Optional[str] = None
    company_column: Optional[str] = None
    custom_variables: Optional[dict] = None


class InstantlySendLeadsResponse(BaseModel):
    success: bool
    leads_sent: int
    errors: List[str] = []


# ============ Helper Functions ============

async def get_integration_setting(session: AsyncSession, name: str) -> Optional[IntegrationSetting]:
    """Get integration setting from DB."""
    result = await session.execute(
        select(IntegrationSetting).where(IntegrationSetting.integration_name == name)
    )
    return result.scalar_one_or_none()


async def save_integration_setting(
    session: AsyncSession, 
    name: str, 
    api_key: str, 
    is_connected: bool,
    settings: dict = None
) -> IntegrationSetting:
    """Save or update integration setting in DB."""
    existing = await get_integration_setting(session, name)
    
    if existing:
        existing.api_key = api_key
        existing.is_connected = is_connected
        if settings:
            existing.settings = settings
    else:
        existing = IntegrationSetting(
            integration_name=name,
            api_key=api_key,
            is_connected=is_connected,
            settings=settings or {}
        )
        session.add(existing)
    
    await session.commit()
    await session.refresh(existing)
    return existing


async def load_integration_keys(session: AsyncSession):
    """Load all integration keys from DB into services."""
    from app.core.config import settings as app_settings

    # Load Instantly
    instantly_setting = await get_integration_setting(session, "instantly")
    if instantly_setting and instantly_setting.api_key:
        instantly_service.set_api_key(instantly_setting.api_key)

    # Load Findymail (DB key takes priority, then env var)
    findymail_setting = await get_integration_setting(session, "findymail")
    if findymail_setting and findymail_setting.api_key:
        findymail_service.set_api_key(findymail_setting.api_key)
    elif app_settings.FINDYMAIL_API_KEY and not findymail_service.is_connected():
        findymail_service.set_api_key(app_settings.FINDYMAIL_API_KEY)
    
    # Load Smartlead
    smartlead_setting = await get_integration_setting(session, "smartlead")
    if smartlead_setting and smartlead_setting.api_key:
        smartlead_service.set_api_key(smartlead_setting.api_key)
    
    # Load MillionVerifier
    millionverifier_setting = await get_integration_setting(session, "millionverifier")
    if millionverifier_setting and millionverifier_setting.api_key:
        millionverifier_service.set_api_key(millionverifier_setting.api_key)

    # Load Fireflies
    fireflies_setting = await get_integration_setting(session, "fireflies")
    if fireflies_setting and fireflies_setting.api_key:
        fireflies_service.set_api_key(fireflies_setting.api_key)


# ============ General Endpoints ============

@router.get("", response_model=AllIntegrationsResponse)
async def get_all_integrations(session: AsyncSession = Depends(get_session)):
    """Get status of all integrations."""
    # Load keys from DB first
    await load_integration_keys(session)
    
    integrations = []
    
    # Instantly
    instantly_setting = await get_integration_setting(session, "instantly")
    integrations.append(IntegrationStatus(
        name="instantly",
        connected=instantly_service.is_connected(),
        has_api_key=bool(instantly_setting and instantly_setting.api_key)
    ))
    
    # Smartlead
    smartlead_setting = await get_integration_setting(session, "smartlead")
    integrations.append(IntegrationStatus(
        name="smartlead",
        connected=smartlead_service.is_connected(),
        has_api_key=bool(smartlead_setting and smartlead_setting.api_key)
    ))
    
    # Findymail
    findymail_setting = await get_integration_setting(session, "findymail")
    integrations.append(IntegrationStatus(
        name="findymail",
        connected=findymail_service.is_connected(),
        has_api_key=bool(findymail_setting and findymail_setting.api_key)
    ))
    
    # MillionVerifier
    millionverifier_setting = await get_integration_setting(session, "millionverifier")
    integrations.append(IntegrationStatus(
        name="millionverifier",
        connected=millionverifier_service.is_connected(),
        has_api_key=bool(millionverifier_setting and millionverifier_setting.api_key)
    ))

    # Fireflies
    fireflies_setting = await get_integration_setting(session, "fireflies")
    integrations.append(IntegrationStatus(
        name="fireflies",
        connected=fireflies_service.is_connected(),
        has_api_key=bool(fireflies_setting and fireflies_setting.api_key)
    ))

    return AllIntegrationsResponse(integrations=integrations)


# ============ Instantly Endpoints ============

@router.get("/instantly", response_model=InstantlyDetailsResponse)
async def get_instantly_details(session: AsyncSession = Depends(get_session)):
    """Get Instantly integration details."""
    await load_integration_keys(session)
    
    campaigns = []
    if instantly_service.is_connected():
        campaigns = await instantly_service.get_campaigns()
    
    return InstantlyDetailsResponse(
        connected=instantly_service.is_connected(),
        campaigns=campaigns
    )


@router.post("/instantly/connect", response_model=InstantlyDetailsResponse)
async def connect_instantly(
    data: IntegrationConnectRequest,
    session: AsyncSession = Depends(get_session)
):
    """Connect Instantly integration."""
    instantly_service.set_api_key(data.api_key)
    
    # Test connection
    is_valid = await instantly_service.test_connection()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to Instantly"
        )
    
    # Save to DB
    await save_integration_setting(session, "instantly", data.api_key, True)
    
    # Fetch campaigns
    campaigns = await instantly_service.get_campaigns()
    
    return InstantlyDetailsResponse(
        connected=True,
        campaigns=campaigns
    )


@router.delete("/instantly/disconnect")
async def disconnect_instantly(session: AsyncSession = Depends(get_session)):
    """Disconnect Instantly integration."""
    setting = await get_integration_setting(session, "instantly")
    if setting:
        setting.api_key = None
        setting.is_connected = False
        await session.commit()
    
    instantly_service.set_api_key("")
    
    return {"status": "disconnected"}


@router.get("/instantly/campaigns")
async def get_instantly_campaigns(session: AsyncSession = Depends(get_session)):
    """Get list of campaigns from Instantly."""
    await load_integration_keys(session)
    
    if not instantly_service.is_connected():
        raise HTTPException(status_code=400, detail="Instantly not connected")
    
    campaigns = await instantly_service.get_campaigns()
    return {"campaigns": campaigns}


@router.post("/instantly/send-leads", response_model=InstantlySendLeadsResponse)
async def send_leads_to_instantly(
    data: InstantlySendLeadsRequest,
    session: AsyncSession = Depends(get_session)
):
    """Send leads from a dataset to an Instantly campaign."""
    await load_integration_keys(session)
    
    if not instantly_service.is_connected():
        raise HTTPException(status_code=400, detail="Instantly not connected")
    
    # Verify dataset exists
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows to send
    query = select(DataRow).where(DataRow.dataset_id == data.dataset_id)
    if data.row_ids:
        query = query.where(DataRow.id.in_(data.row_ids))
    
    result = await session.execute(query)
    rows = result.scalars().all()
    
    if not rows:
        raise HTTPException(status_code=400, detail="No rows to send")
    
    # Prepare leads
    leads = []
    errors = []
    
    for row in rows:
        all_data = {**row.data, **row.enriched_data}
        
        email = all_data.get(data.email_column)
        if not email:
            errors.append(f"Row {row.row_index}: Missing email")
            continue
        
        lead = {"email": email}
        
        if data.first_name_column:
            first_name = all_data.get(data.first_name_column)
            if first_name:
                lead["first_name"] = str(first_name)
        
        if data.last_name_column:
            last_name = all_data.get(data.last_name_column)
            if last_name:
                lead["last_name"] = str(last_name)
        
        if data.company_column:
            company = all_data.get(data.company_column)
            if company:
                lead["company_name"] = str(company)
        
        if data.custom_variables:
            custom_vars = {}
            for var_name, col_name in data.custom_variables.items():
                value = all_data.get(col_name)
                if value:
                    custom_vars[var_name] = str(value)
            if custom_vars:
                lead["custom_variables"] = custom_vars
        
        leads.append(lead)
    
    if not leads:
        return InstantlySendLeadsResponse(
            success=False,
            leads_sent=0,
            errors=errors or ["No valid leads to send"]
        )
    
    # Send leads in batches
    batch_size = 500
    total_sent = 0
    
    for i in range(0, len(leads), batch_size):
        batch = leads[i:i + batch_size]
        result = await instantly_service.add_leads_batch(data.campaign_id, batch)
        
        if result["success"]:
            total_sent += result["leads_sent"]
        else:
            errors.append(f"Batch {i//batch_size + 1}: {result.get('error', 'Unknown error')}")
    
    return InstantlySendLeadsResponse(
        success=total_sent > 0,
        leads_sent=total_sent,
        errors=errors
    )


# ============ Findymail Endpoints ============

@router.get("/findymail", response_model=FindymailDetailsResponse)
async def get_findymail_details(session: AsyncSession = Depends(get_session)):
    """Get Findymail integration details."""
    await load_integration_keys(session)
    
    credits = None
    if findymail_service.is_connected():
        credits = await findymail_service.get_credits()
    
    return FindymailDetailsResponse(
        connected=findymail_service.is_connected(),
        credits=credits
    )


@router.post("/findymail/connect", response_model=FindymailDetailsResponse)
async def connect_findymail(
    data: IntegrationConnectRequest,
    session: AsyncSession = Depends(get_session)
):
    """Connect Findymail integration."""
    findymail_service.set_api_key(data.api_key)
    
    # Test connection
    is_valid = await findymail_service.test_connection()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to Findymail"
        )
    
    # Save to DB
    await save_integration_setting(session, "findymail", data.api_key, True)
    
    # Get credits
    credits = await findymail_service.get_credits()
    
    return FindymailDetailsResponse(
        connected=True,
        credits=credits
    )


@router.delete("/findymail/disconnect")
async def disconnect_findymail(session: AsyncSession = Depends(get_session)):
    """Disconnect Findymail integration."""
    setting = await get_integration_setting(session, "findymail")
    if setting:
        setting.api_key = None
        setting.is_connected = False
        await session.commit()
    
    findymail_service.set_api_key("")
    
    return {"status": "disconnected"}


@router.post("/findymail/find-email")
async def find_email(
    name: str,
    domain: str,
    session: AsyncSession = Depends(get_session)
):
    """Find email by name and domain."""
    await load_integration_keys(session)
    
    if not findymail_service.is_connected():
        raise HTTPException(status_code=400, detail="Findymail not connected")
    
    result = await findymail_service.find_email_by_name(name, domain)
    return result


@router.post("/findymail/find-by-linkedin")
async def find_email_by_linkedin(
    linkedin_url: str,
    session: AsyncSession = Depends(get_session)
):
    """Find email by LinkedIn URL."""
    await load_integration_keys(session)
    
    if not findymail_service.is_connected():
        raise HTTPException(status_code=400, detail="Findymail not connected")
    
    result = await findymail_service.find_email_by_linkedin(linkedin_url)
    return result


@router.post("/findymail/verify-email")
async def verify_email(
    email: str,
    session: AsyncSession = Depends(get_session)
):
    """Verify an email address."""
    await load_integration_keys(session)
    
    if not findymail_service.is_connected():
        raise HTTPException(status_code=400, detail="Findymail not connected")
    
    result = await findymail_service.verify_email(email)
    return result


# Findymail pricing (per request)
FINDYMAIL_PRICING = {
    "find_email": 0.025,  # $0.025 per email search
    "find_by_linkedin": 0.025,  # $0.025 per LinkedIn search
    "verify_email": 0.001,  # $0.001 per verification
}


async def run_findymail_enrichment(
    dataset_id: int,
    row_ids: List[int],
    enrichment_type: str,
    output_column: str,
    name_column: Optional[str],
    domain_column: Optional[str],
    email_column: Optional[str],
):
    """Background task to run Findymail enrichment."""
    async with async_session_maker() as session:
        try:
            # Load integration keys
            await load_integration_keys(session)
            
            if not findymail_service.is_connected():
                await notify_job_complete(0, dataset_id, False, "Findymail not connected")
                return
            
            # Get rows
            query = select(DataRow).where(DataRow.dataset_id == dataset_id)
            if row_ids:
                query = query.where(DataRow.id.in_(row_ids))
            
            result = await session.execute(query)
            rows = result.scalars().all()
            
            total = len(rows)
            processed = 0
            found = 0
            errors = []
            total_cost = 0.0
            
            # Send initial progress
            await notify_job_progress(0, 0, total, "processing", 0)
            
            for row in rows:
                all_data = {**row.data, **row.enriched_data}
                result_data = None
                
                try:
                    if enrichment_type == "find_email":
                        # Handle name_column - can be single column or "first+last" format
                        if name_column and "+" in name_column:
                            parts = name_column.split("+")
                            first_name = all_data.get(parts[0], "") if len(parts) > 0 else ""
                            last_name = all_data.get(parts[1], "") if len(parts) > 1 else ""
                            name = f"{first_name} {last_name}".strip()
                        else:
                            name = all_data.get(name_column, "") if name_column else ""
                        
                        domain = all_data.get(domain_column, "") if domain_column else ""
                        
                        if not name or not domain:
                            errors.append(f"Row {row.row_index}: Missing name or domain")
                            processed += 1
                            continue
                        
                        result = await findymail_service.find_email_by_name(str(name), str(domain))
                        total_cost += FINDYMAIL_PRICING["find_email"]
                        
                        if result.get("success") and result.get("email"):
                            result_data = result["email"]
                            found += 1
                        elif result.get("error"):
                            result_data = f"[Not found: {result.get('error', 'Unknown')}]"
                        else:
                            result_data = "[Not found]"
                    
                    elif enrichment_type == "find_by_linkedin":
                        # email_column is reused for linkedin URL
                        linkedin_url = all_data.get(email_column, "") if email_column else ""
                        
                        if not linkedin_url:
                            errors.append(f"Row {row.row_index}: Missing LinkedIn URL")
                            processed += 1
                            continue
                        
                        result = await findymail_service.find_email_by_linkedin(str(linkedin_url))
                        total_cost += FINDYMAIL_PRICING["find_by_linkedin"]
                        
                        if result.get("success") and result.get("email"):
                            result_data = result["email"]
                            found += 1
                        elif result.get("error"):
                            result_data = f"[Not found: {result.get('error', 'Unknown')}]"
                        else:
                            result_data = "[Not found]"
                    
                    elif enrichment_type == "verify_email":
                        email = all_data.get(email_column, "") if email_column else ""
                        
                        if not email:
                            errors.append(f"Row {row.row_index}: Missing email")
                            processed += 1
                            continue
                        
                        result = await findymail_service.verify_email(str(email))
                        total_cost += FINDYMAIL_PRICING["verify_email"]
                        
                        if result.get("success"):
                            result_data = "Valid" if result.get("verified") else "Invalid"
                            if result.get("verified"):
                                found += 1
                        else:
                            result_data = f"[Error: {result.get('error', 'Unknown')}]"
                    
                    # Save result
                    if result_data is not None:
                        row.enriched_data = {
                            **row.enriched_data,
                            output_column: result_data
                        }
                        row.last_enriched_at = datetime.utcnow()
                    
                    processed += 1
                    
                    # Commit every 10 rows
                    if processed % 10 == 0:
                        await session.commit()
                        await notify_job_progress(0, processed, total, "processing", len(errors))
                    
                    # Rate limiting - 1 request per 100ms
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    errors.append(f"Row {row.row_index}: {str(e)}")
                    processed += 1
            
            await session.commit()
            
            # Dispatch cost update event
            # Store cost in a way frontend can retrieve it
            
            await notify_job_complete(
                0, 
                dataset_id, 
                True, 
                f"Processed {processed}, found {found}. Cost: ${total_cost:.4f}"
            )
            
        except Exception as e:
            logger.error(f"Findymail enrichment failed: {str(e)}")
            await notify_job_complete(0, dataset_id, False, str(e))


@router.post("/findymail/enrich", response_model=FindymailEnrichmentResponse)
async def findymail_enrich(
    data: FindymailEnrichmentRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Run Findymail enrichment on dataset rows."""
    await load_integration_keys(session)
    
    if not findymail_service.is_connected():
        raise HTTPException(status_code=400, detail="Findymail not connected")
    
    # Validate dataset
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Validate enrichment type
    if data.enrichment_type not in ["find_email", "find_by_linkedin", "verify_email"]:
        raise HTTPException(status_code=400, detail="Invalid enrichment type")
    
    if data.enrichment_type == "find_email":
        if not data.name_column or not data.domain_column:
            raise HTTPException(status_code=400, detail="name_column and domain_column required for find_email")
    
    if data.enrichment_type == "find_by_linkedin":
        if not data.email_column:  # Reusing email_column for linkedin URL
            raise HTTPException(status_code=400, detail="email_column (linkedin URL) required for find_by_linkedin")
    
    if data.enrichment_type == "verify_email":
        if not data.email_column:
            raise HTTPException(status_code=400, detail="email_column required for verify_email")
    
    # Get row count
    query = select(DataRow).where(DataRow.dataset_id == data.dataset_id)
    if data.row_ids:
        query = query.where(DataRow.id.in_(data.row_ids))
    
    result = await session.execute(query)
    rows = result.scalars().all()
    row_count = len(rows)
    
    # Estimate cost
    cost_per = FINDYMAIL_PRICING.get(data.enrichment_type, 0)
    estimated_cost = cost_per * row_count
    
    # Start background task
    background_tasks.add_task(
        run_findymail_enrichment,
        data.dataset_id,
        data.row_ids or [r.id for r in rows],
        data.enrichment_type,
        data.output_column,
        data.name_column,
        data.domain_column,
        data.email_column,
    )
    
    return FindymailEnrichmentResponse(
        success=True,
        processed=0,
        found=0,
        errors=[],
        total_cost=estimated_cost
    )


# ============ MillionVerifier Endpoints ============

class MillionVerifierDetailsResponse(BaseModel):
    connected: bool
    credits: Optional[dict] = None


class MillionVerifierVerifyRequest(BaseModel):
    dataset_id: int
    email_column: str
    output_column: str = "Email_Verified_MV"
    row_ids: Optional[List[int]] = None
    timeout: int = 20


async def run_millionverifier_verification(
    dataset_id: int,
    row_ids: List[int],
    email_column: str,
    output_column: str,
    timeout: int = 20,
):
    """Background task to verify emails using MillionVerifier."""
    async with async_session_maker() as session:
        try:
            # Load integration keys
            await load_integration_keys(session)
            
            if not millionverifier_service.is_connected():
                await notify_job_complete(0, dataset_id, False, "MillionVerifier not connected")
                return
            
            # Get rows
            query = select(DataRow).where(DataRow.dataset_id == dataset_id)
            if row_ids:
                query = query.where(DataRow.id.in_(row_ids))
            
            result = await session.execute(query)
            rows = result.scalars().all()
            
            total = len(rows)
            processed = 0
            verified_count = 0
            errors = []
            
            # Send initial progress
            await notify_job_progress(0, 0, total, "processing", 0)
            
            for row in rows:
                all_data = {**row.data, **row.enriched_data}
                email = all_data.get(email_column, "")
                
                if not email:
                    errors.append(f"Row {row.row_index}: Missing email")
                    processed += 1
                    continue
                
                try:
                    result = await millionverifier_service.verify_email(str(email), timeout)
                    
                    if result.get("success"):
                        verification_result = result.get("result", "unknown")
                        
                        # Store comprehensive result
                        status_parts = [verification_result]
                        if result.get("is_disposable"):
                            status_parts.append("disposable")
                        if result.get("is_catch_all"):
                            status_parts.append("catch-all")
                        if result.get("is_free"):
                            status_parts.append("free")
                        if result.get("is_role"):
                            status_parts.append("role")
                        
                        result_text = " | ".join(status_parts)
                        
                        row.enriched_data = {
                            **row.enriched_data,
                            output_column: result_text,
                            f"{output_column}_result": verification_result,
                            f"{output_column}_quality": result.get("quality", ""),
                        }
                        
                        if verification_result == "ok":
                            verified_count += 1
                        
                        row.last_enriched_at = datetime.utcnow()
                    else:
                        error_msg = result.get("error", "Unknown error")
                        row.enriched_data = {
                            **row.enriched_data,
                            output_column: f"[Error: {error_msg}]"
                        }
                        errors.append(f"Row {row.row_index}: {error_msg}")
                    
                    processed += 1
                    
                    # Commit every 10 rows
                    if processed % 10 == 0:
                        await session.commit()
                        await notify_job_progress(0, processed, total, "processing", len(errors))
                    
                    # Rate limiting - respect 100 req/sec limit
                    await asyncio.sleep(0.015)  # ~66 req/sec to be safe
                    
                except Exception as e:
                    errors.append(f"Row {row.row_index}: {str(e)}")
                    processed += 1
            
            await session.commit()
            
            await notify_job_complete(
                0, 
                dataset_id, 
                True, 
                f"Verified {processed} emails. Valid: {verified_count}, Issues: {processed - verified_count}"
            )
            
        except Exception as e:
            logger.error(f"MillionVerifier verification failed: {str(e)}")
            await notify_job_complete(0, dataset_id, False, str(e))


@router.get("/millionverifier", response_model=MillionVerifierDetailsResponse)
async def get_millionverifier_details(session: AsyncSession = Depends(get_session)):
    """Get MillionVerifier integration details."""
    await load_integration_keys(session)
    
    credits = None
    if millionverifier_service.is_connected():
        credits = await millionverifier_service.get_credits()
    
    return MillionVerifierDetailsResponse(
        connected=millionverifier_service.is_connected(),
        credits=credits
    )


@router.post("/millionverifier/connect", response_model=MillionVerifierDetailsResponse)
async def connect_millionverifier(
    data: IntegrationConnectRequest,
    session: AsyncSession = Depends(get_session)
):
    """Connect MillionVerifier integration."""
    millionverifier_service.set_api_key(data.api_key)
    
    # Test connection
    is_valid = await millionverifier_service.test_connection()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to MillionVerifier"
        )
    
    # Save to DB
    await save_integration_setting(session, "millionverifier", data.api_key, True)
    
    # Get credits
    credits = await millionverifier_service.get_credits()
    
    return MillionVerifierDetailsResponse(
        connected=True,
        credits=credits
    )


@router.delete("/millionverifier/disconnect")
async def disconnect_millionverifier(session: AsyncSession = Depends(get_session)):
    """Disconnect MillionVerifier integration."""
    setting = await get_integration_setting(session, "millionverifier")
    if setting:
        setting.api_key = None
        setting.is_connected = False
        await session.commit()
    
    millionverifier_service.set_api_key("")
    
    return {"status": "disconnected"}


@router.post("/millionverifier/verify")
async def millionverifier_verify(
    data: MillionVerifierVerifyRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Verify emails in a dataset using MillionVerifier."""
    await load_integration_keys(session)
    
    if not millionverifier_service.is_connected():
        raise HTTPException(status_code=400, detail="MillionVerifier not connected")
    
    # Validate dataset
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get row count
    query = select(DataRow).where(DataRow.dataset_id == data.dataset_id)
    if data.row_ids:
        query = query.where(DataRow.id.in_(data.row_ids))
    
    result = await session.execute(query)
    rows = result.scalars().all()
    row_count = len(rows)
    
    if row_count == 0:
        raise HTTPException(status_code=400, detail="No rows to verify")
    
    # Start background task
    background_tasks.add_task(
        run_millionverifier_verification,
        data.dataset_id,
        data.row_ids or [r.id for r in rows],
        data.email_column,
        data.output_column,
        data.timeout,
    )
    
    return {
        "success": True,
        "rows_to_verify": row_count,
        "message": f"Verification started for {row_count} emails"
    }


# ============ Smartlead Endpoints ============

class SmartleadDetailsResponse(BaseModel):
    connected: bool
    campaigns: List[dict] = []


class SmartleadSendLeadsRequest(BaseModel):
    campaign_id: str
    dataset_id: int
    row_ids: Optional[List[int]] = None
    email_column: str
    first_name_column: Optional[str] = None
    last_name_column: Optional[str] = None
    company_column: Optional[str] = None
    custom_variables: Optional[dict] = None


@router.get("/smartlead", response_model=SmartleadDetailsResponse)
async def get_smartlead_details(session: AsyncSession = Depends(get_session)):
    """Get Smartlead integration details."""
    await load_integration_keys(session)
    
    campaigns = []
    if smartlead_service.is_connected():
        try:
            campaigns = await smartlead_service.get_campaigns()
        except Exception as e:
            logger.error(f"Failed to fetch Smartlead campaigns: {e}")
    
    return SmartleadDetailsResponse(
        connected=smartlead_service.is_connected(),
        campaigns=campaigns
    )


@router.post("/smartlead/connect", response_model=SmartleadDetailsResponse)
async def connect_smartlead(
    data: IntegrationConnectRequest,
    session: AsyncSession = Depends(get_session)
):
    """Connect Smartlead integration."""
    smartlead_service.set_api_key(data.api_key)
    
    # Test connection by fetching campaigns
    is_valid = await smartlead_service.test_connection()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to Smartlead"
        )
    
    # Save to DB
    await save_integration_setting(session, "smartlead", data.api_key, True)
    
    # Get campaigns
    campaigns = await smartlead_service.get_campaigns()
    
    return SmartleadDetailsResponse(
        connected=True,
        campaigns=campaigns
    )


@router.delete("/smartlead/disconnect")
async def disconnect_smartlead(session: AsyncSession = Depends(get_session)):
    """Disconnect Smartlead integration."""
    setting = await get_integration_setting(session, "smartlead")
    if setting:
        setting.api_key = None
        setting.is_connected = False
        await session.commit()
    
    smartlead_service.set_api_key("")
    
    return {"status": "disconnected"}


@router.get("/smartlead/campaigns")
async def get_smartlead_campaigns(session: AsyncSession = Depends(get_session)):
    """Get all Smartlead campaigns."""
    await load_integration_keys(session)
    
    if not smartlead_service.is_connected():
        raise HTTPException(status_code=400, detail="Smartlead not connected")
    
    campaigns = await smartlead_service.get_campaigns()
    return {"campaigns": campaigns}


@router.post("/smartlead/send-leads")
async def send_leads_to_smartlead(
    data: SmartleadSendLeadsRequest,
    session: AsyncSession = Depends(get_session)
):
    """Send leads from a dataset to a Smartlead campaign."""
    await load_integration_keys(session)
    
    if not smartlead_service.is_connected():
        raise HTTPException(status_code=400, detail="Smartlead not connected")
    
    # Validate dataset
    dataset = await session.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Get rows
    query = select(DataRow).where(DataRow.dataset_id == data.dataset_id)
    if data.row_ids:
        query = query.where(DataRow.id.in_(data.row_ids))
    
    result = await session.execute(query)
    rows = result.scalars().all()
    
    if not rows:
        raise HTTPException(status_code=400, detail="No rows found")
    
    # Build leads list
    leads = []
    errors = []
    
    for row in rows:
        all_data = {**row.data, **row.enriched_data}
        
        email = all_data.get(data.email_column, "")
        if not email:
            errors.append(f"Row {row.row_index}: Missing email")
            continue
        
        lead = {"email": email}
        
        # Add first name
        if data.first_name_column:
            lead["first_name"] = all_data.get(data.first_name_column, "")
        
        # Add last name
        if data.last_name_column:
            lead["last_name"] = all_data.get(data.last_name_column, "")
        
        # Add company name
        if data.company_column:
            lead["company_name"] = all_data.get(data.company_column, "")
        
        # Add custom variables
        if data.custom_variables:
            custom_fields = {}
            for key, column_name in data.custom_variables.items():
                value = all_data.get(column_name, "")
                if value:
                    custom_fields[key] = value
            if custom_fields:
                lead["custom_fields"] = custom_fields
        
        leads.append(lead)
    
    if not leads:
        return {
            "success": False,
            "leads_sent": 0,
            "errors": errors or ["No valid leads found"]
        }
    
    # Send to Smartlead
    response = await smartlead_service.add_leads_to_campaign(
        campaign_id=data.campaign_id,
        leads=leads
    )
    
    if response.get("success"):
        # Update rows with "Exported to Smartlead" column
        now = datetime.utcnow().isoformat()
        for row in rows:
            if any(lead["email"] == ({**row.data, **row.enriched_data}).get(data.email_column) for lead in leads):
                row.enriched_data = {
                    **row.enriched_data,
                    "Exported to Smartlead": now
                }
        
        await session.commit()
        
        return {
            "success": True,
            "leads_sent": len(leads),
            "errors": errors
        }
    else:
        return {
            "success": False,
            "leads_sent": 0,
            "errors": errors + [response.get("message", "Unknown error")]
        }


# ============ Fireflies Endpoints ============

class FirefliesDetailsResponse(BaseModel):
    connected: bool
    user: Optional[dict] = None


@router.get("/fireflies", response_model=FirefliesDetailsResponse)
async def get_fireflies_details(session: AsyncSession = Depends(get_session)):
    """Get Fireflies integration details."""
    await load_integration_keys(session)

    user_info = None
    if fireflies_service.is_connected():
        user_info = await fireflies_service.get_user()

    return FirefliesDetailsResponse(
        connected=fireflies_service.is_connected(),
        user=user_info,
    )


@router.post("/fireflies/connect", response_model=FirefliesDetailsResponse)
async def connect_fireflies(
    data: IntegrationConnectRequest,
    session: AsyncSession = Depends(get_session),
):
    """Connect Fireflies integration."""
    fireflies_service.set_api_key(data.api_key)

    is_valid = await fireflies_service.test_connection()
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to Fireflies",
        )

    await save_integration_setting(session, "fireflies", data.api_key, True)

    user_info = await fireflies_service.get_user()
    return FirefliesDetailsResponse(connected=True, user=user_info)


@router.delete("/fireflies/disconnect")
async def disconnect_fireflies(session: AsyncSession = Depends(get_session)):
    """Disconnect Fireflies integration."""
    setting = await get_integration_setting(session, "fireflies")
    if setting:
        setting.api_key = None
        setting.is_connected = False
        await session.commit()

    fireflies_service.set_api_key("")

    return {"status": "disconnected"}
