"""Intent Parser — analyzes user's gathering query into structured segments.

Takes raw user input like "find IT consulting and media production companies in Miami"
and outputs structured segment definitions for pipeline creation.

Also extracts competitor exclusion rules from the user's offer/website.
"""
import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PARSE_INTENT_PROMPT = """You are a B2B lead generation expert. Analyze the user's query and extract structured gathering segments.

USER'S QUERY: {query}

USER'S COMPANY (what they sell — use for competitor exclusion):
{user_offer}

RULES:
1. Each DISTINCT business segment = separate pipeline (different Apollo filters, different GPT prompts)
2. "IT consulting and media production" = 2 segments (different industries)
3. "IT consulting companies in Miami and London" = 2 segments (same industry, different geo → could be 1 or 2, prefer 1 if Apollo supports multi-geo)
4. "SaaS companies" = 1 segment
5. Extract geographic context (country, city) for each segment
6. Generate a CAPS_LOCKED segment label (e.g. IT_CONSULTING, MEDIA_PRODUCTION, FASHION_BRAND)
7. List what should be EXCLUDED — competitors who offer the same service as the user

Return ONLY valid JSON:
{{
  "segments": [
    {{
      "label": "IT_CONSULTING",
      "description": "IT consulting firms that provide technology advisory services",
      "apollo_keywords": ["IT consulting", "technology consulting", "IT advisory"],
      "apollo_industries": ["information technology"],
      "geo": "Miami, Florida, United States",
      "country": "United States",
      "city": "Miami"
    }}
  ],
  "competitor_exclusions": [
    "Companies that provide payroll or contractor payment services (competitors to EasyStaff)"
  ],
  "pipelines_needed": 1
}}"""


async def parse_gathering_intent(
    query: str,
    user_offer: str = "",
    openai_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse user's gathering query into structured segments.

    Uses GPT-4o (OpenAI) — only requires OpenAI key.
    """
    prompt = PARSE_INTENT_PROMPT.format(
        query=query,
        user_offer=user_offer or "(not provided — skip competitor exclusion)",
    )

    # Use OpenAI (GPT-4o for quality, GPT-4o-mini as fallback)
    if openai_key:
        result = await _call_openai(openai_key, prompt)
        if result:
            return result

    # Last resort — single segment from raw query
    logger.warning("No AI key available for intent parsing, using raw query")
    return _fallback_parse(query)


async def _call_gemini(api_key: str, prompt: str) -> Optional[Dict]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
                },
            )
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return _parse_json(text)
    except Exception as e:
        logger.warning(f"Gemini intent parsing failed: {e}")
        return None


async def _call_openai(api_key: str, prompt: str) -> Optional[Dict]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You parse B2B lead generation queries into structured JSON. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 800,
                    "temperature": 0.1,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return _parse_json(content)
    except Exception as e:
        logger.warning(f"OpenAI intent parsing failed: {e}")
        return None


def _parse_json(text: str) -> Optional[Dict]:
    import re
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict) and "segments" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def _fallback_parse(query: str) -> Dict:
    """Simple regex fallback when no AI is available."""
    import re
    label = re.sub(r'[^a-z0-9]+', '_', query.lower().split(' in ')[0].split(' from ')[0]).upper().strip('_')[:30]
    geo_match = re.search(r'\bin\s+(.+?)(?:\s+for|\s*$)', query, re.IGNORECASE)
    geo = geo_match.group(1).strip() if geo_match else ""

    return {
        "segments": [{
            "label": label or "TARGET",
            "description": query,
            "apollo_keywords": query.split(' in ')[0].split(' and '),
            "geo": geo,
            "country": "",
            "city": "",
        }],
        "competitor_exclusions": [],
        "pipelines_needed": 1,
    }
