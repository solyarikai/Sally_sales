"""
Gemini API client — used for complex reasoning tasks (query generation, website analysis).
Falls back to OpenAI GPT-4o-mini if Gemini API key is not configured.
"""
import json
import logging
import re
from typing import Optional

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

        content = response.text or ""
        usage = response.usage_metadata
        tokens = {
            "input": usage.prompt_token_count or 0,
            "output": usage.candidates_token_count or 0,
            "thinking": getattr(usage, "thoughts_token_count", 0) or 0,
            "total": usage.total_token_count or 0,
        }

        return {"content": content, "tokens": tokens, "model": model_name}

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise


def extract_json_from_gemini(text: str) -> str:
    """Strip markdown code fences that Gemini wraps around JSON."""
    # Remove ```json ... ``` or ``` ... ```
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*?)```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text
