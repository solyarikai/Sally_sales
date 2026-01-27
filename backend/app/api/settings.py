from fastapi import APIRouter, HTTPException
from app.schemas import OpenAISettingsUpdate, OpenAISettingsResponse
from app.services import openai_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/openai", response_model=OpenAISettingsResponse)
async def get_openai_settings():
    """Get current OpenAI settings"""
    return OpenAISettingsResponse(
        has_api_key=bool(openai_service.api_key),
        default_model=settings.DEFAULT_OPENAI_MODEL,
        available_models=settings.AVAILABLE_MODELS,
    )


@router.put("/openai", response_model=OpenAISettingsResponse)
async def update_openai_settings(data: OpenAISettingsUpdate):
    """Update OpenAI settings"""
    if data.api_key:
        openai_service.set_api_key(data.api_key)
        
        # Test the new key
        is_valid = await openai_service.test_connection()
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid API key")
    
    if data.default_model:
        if data.default_model not in settings.AVAILABLE_MODELS:
            raise HTTPException(status_code=400, detail="Invalid model")
        settings.DEFAULT_OPENAI_MODEL = data.default_model
    
    return OpenAISettingsResponse(
        has_api_key=bool(openai_service.api_key),
        default_model=settings.DEFAULT_OPENAI_MODEL,
        available_models=settings.AVAILABLE_MODELS,
    )


@router.post("/openai/test")
async def test_openai_connection():
    """Test OpenAI API connection"""
    if not openai_service.api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    
    is_valid = await openai_service.test_connection()
    
    if is_valid:
        return {"status": "success", "message": "API key is valid"}
    else:
        raise HTTPException(status_code=400, detail="Failed to connect to OpenAI")
