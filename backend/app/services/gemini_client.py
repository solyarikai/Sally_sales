"""
Gemini API client — used for complex reasoning tasks (query generation, website analysis).
Falls back to OpenAI GPT-4o-mini if Gemini API key is not configured.
"""
import json
import logging
import re
from typing import Optional, AsyncGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized client
_gemini_client = None


def _get_client():
    global _gemini_client
    if _gemini_client is None and settings.GEMINI_API_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def is_gemini_available() -> bool:
    """Check if Gemini API is configured."""
    return bool(settings.GEMINI_API_KEY)


async def gemini_generate(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    max_tokens: int = 4000,
    model: Optional[str] = None,
    project_id: Optional[int] = None,
) -> dict:
    """
    Call Gemini API for text generation.

    Returns: {"content": str, "tokens": {"input": int, "output": int, "total": int}, "model": str}
    """
    client = _get_client()
    if not client:
        raise RuntimeError("Gemini API key not configured")

    model_name = model or settings.GEMINI_MODEL
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        # Extract text — response.text can be None for thinking models
        try:
            content = response.text or ""
        except Exception:
            # Fallback: extract from candidates directly
            content = ""
            if response.candidates:
                for part in (response.candidates[0].content.parts or []):
                    if hasattr(part, 'text') and part.text and not getattr(part, 'thought', False):
                        content += part.text
        if not content:
            logger.warning(f"Gemini returned empty content for model {model_name}")
        usage = response.usage_metadata
        tokens = {
            "input": usage.prompt_token_count or 0,
            "output": usage.candidates_token_count or 0,
            "thinking": getattr(usage, "thoughts_token_count", 0) or 0,
            "total": usage.total_token_count or 0,
        }

        # Track cost if project_id provided
        if project_id and tokens["total"] > 0:
            try:
                from app.services.cost_service import cost_service
                await cost_service.record_cost_standalone(
                    project_id, "gemini_1k_tokens",
                    units=max(1, tokens["total"] // 1000),
                    description=f"gemini/{model_name}",
                )
            except Exception as cost_err:
                logger.debug(f"Failed to record Gemini cost: {cost_err}")

        return {"content": content, "tokens": tokens, "model": model_name}

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise


async def gemini_generate_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    max_tokens: int = 4000,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream Gemini response token-by-token.
    Yields text chunks as they arrive.
    """
    client = _get_client()
    if not client:
        raise RuntimeError("Gemini API key not configured")

    model_name = model or settings.GEMINI_MODEL
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    try:
        from google.genai import types

        response_stream = client.models.generate_content_stream(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        for chunk in response_stream:
            text = chunk.text
            if text:
                yield text

    except Exception as e:
        logger.error(f"Gemini streaming call failed: {e}")
        raise


def extract_json_from_gemini(text: str) -> str:
    """Strip markdown code fences that Gemini wraps around JSON."""
    # Remove ```json ... ``` or ``` ... ```
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*?)```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text
