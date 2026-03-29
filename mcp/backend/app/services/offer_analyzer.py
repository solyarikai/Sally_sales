"""Offer Analyzer — infers target company size and ICP from offer/website text.

Used to auto-set Apollo employee_count filter without asking user.
"""
import json
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

INFER_SIZE_PROMPT = """You are analyzing a company's offer to determine their ideal customer profile (ICP).

Company offer/website text:
{offer_text}

Based on this offer, determine:
1. What size companies would typically buy this product/service?
2. What's the Apollo employee_count filter range?

Common patterns:
- Payroll/HR/contractor management → SMB/mid-market: 10-200 employees
- Enterprise SaaS → 200-10000 employees
- Small business tools → 1-50 employees
- Freelancer platforms → 1-20 employees
- B2B consulting → 50-500 employees
- Infrastructure/DevOps → 50-1000 employees

Return ONLY valid JSON:
{{
  "min_employees": <number>,
  "max_employees": <number>,
  "apollo_range": "<min>,<max>",
  "reasoning": "<1 sentence why this size range>"
}}"""


async def infer_target_size(offer_text: str, openai_key: str) -> Dict:
    """Infer target company size from offer text using GPT-4o-mini.

    Returns: {"min_employees": 10, "max_employees": 200, "apollo_range": "11,200", "reasoning": "..."}
    """
    if not offer_text or not openai_key:
        return {"min_employees": 10, "max_employees": 500, "apollo_range": "11,500",
                "reasoning": "Default range (no offer text provided)"}

    prompt = INFER_SIZE_PROMPT.format(offer_text=offer_text[:2000])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(clean)

            # Validate and format for Apollo
            min_emp = result.get("min_employees", 10)
            max_emp = result.get("max_employees", 500)
            result["apollo_range"] = f"{min_emp},{max_emp}"
            logger.info(f"Inferred target size: {min_emp}-{max_emp} ({result.get('reasoning', '')})")
            return result

    except Exception as e:
        logger.warning(f"Size inference failed: {e}")
        return {"min_employees": 10, "max_employees": 500, "apollo_range": "11,500",
                "reasoning": f"Default (inference failed: {str(e)[:50]})"}
