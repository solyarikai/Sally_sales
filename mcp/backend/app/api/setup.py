"""Integration setup API — connect SmartLead, Apollo, OpenAI, Apify, GetSales."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.models.user import MCPUser
from app.models.integration import MCPIntegrationSetting
from app.auth.dependencies import get_current_user
from app.services.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

SUPPORTED_INTEGRATIONS = {"smartlead", "apollo", "openai", "apify", "getsales"}


class IntegrationRequest(BaseModel):
    integration_name: str
    api_key: str


class IntegrationResponse(BaseModel):
    connected: bool
    message: str


@router.post("/integrations", response_model=IntegrationResponse)
async def configure_integration(
    req: IntegrationRequest,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if req.integration_name not in SUPPORTED_INTEGRATIONS:
        raise HTTPException(400, f"Unsupported integration: {req.integration_name}")
    if not req.api_key or len(req.api_key) < 8:
        raise HTTPException(400, "API key too short (minimum 8 characters)")
    if len(req.api_key) > 4000:
        raise HTTPException(400, "API key too long (maximum 4000 characters)")

    # Test connection
    connected = False
    message = ""

    if req.integration_name == "smartlead":
        from app.services.smartlead_service import SmartLeadService
        svc = SmartLeadService(api_key=req.api_key)
        connected = await svc.test_connection()
        if connected:
            campaigns = await svc.get_campaigns()
            message = f"{len(campaigns)} campaigns found"
        else:
            message = "Connection failed — check API key"

    elif req.integration_name == "apollo":
        from app.services.apollo_service import ApolloService
        svc = ApolloService(api_key=req.api_key)
        connected = await svc.test_connection()
        message = "Connected" if connected else "Connection failed — check API key"

    elif req.integration_name == "findymail":
        from app.services.findymail_service import FindymailService
        svc = FindymailService(api_key=req.api_key)
        connected = await svc.test_connection()
        if connected:
            credits = await svc.get_credits()
            message = f"Connected. Credits: {credits}" if credits else "Connected"
        else:
            message = "Connection failed — check API key"

    elif req.integration_name == "apify":
        # Store + set as env var so scraper picks it up immediately
        import os
        os.environ["APIFY_PROXY_PASSWORD"] = req.api_key
        connected = True
        message = "Apify proxy password saved — website scraping will use residential proxy"

    elif req.integration_name == "getsales":
        # Just store — GetSales uses JWT token, no simple test
        connected = True
        message = "GetSales key saved"

    elif req.integration_name == "openai":
        # Just store — no easy test endpoint
        connected = True
        message = "OpenAI key saved"

    # Upsert integration setting
    existing = await session.execute(
        select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.user_id == user.id,
            MCPIntegrationSetting.integration_name == req.integration_name,
        )
    )
    setting = existing.scalar_one_or_none()

    encrypted = encrypt_value(req.api_key)

    if setting:
        setting.api_key_encrypted = encrypted
        setting.is_connected = connected
        setting.connection_info = message
    else:
        setting = MCPIntegrationSetting(
            user_id=user.id,
            integration_name=req.integration_name,
            api_key_encrypted=encrypted,
            is_connected=connected,
            connection_info=message,
        )
        session.add(setting)

    await session.commit()
    return IntegrationResponse(connected=connected, message=message)


@router.get("/integrations")
async def list_integrations(
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.user_id == user.id
        )
    )
    return [
        {
            "name": i.integration_name,
            "connected": i.is_connected,
            "info": i.connection_info,
        }
        for i in result.scalars().all()
    ]
