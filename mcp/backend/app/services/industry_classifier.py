"""A11: Industry Specificity Classifier — decides if industry_tag_ids or keywords are better.

Some Apollo industries are EXACT matches (apparel & fashion → fashion brands = perfect).
Others are TOO BROAD (marketing & advertising → includes magazines, PR, events, NOT just video production).

This agent decides the search strategy in one GPT call.
"""
import json
import logging
import httpx
from typing import Dict, List, Optional

from app.services.cost_tracker import extract_openai_usage

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """Given this user search query and the matched Apollo industries, classify each industry as SPECIFIC or BROAD for this query.

SPECIFIC = the industry directly describes what the user wants. Using it as a filter will return mostly relevant companies.
BROAD = the industry is a superset. It includes many company types the user does NOT want.

User query: "{query}"
User's offer context: "{offer}"

Matched industries: {industries}

For each industry, answer: SPECIFIC or BROAD, with 1-line reason.
Then give your RECOMMENDATION: should we search by industry_tag_ids (if any are SPECIFIC) or by keywords?

Return JSON:
{{
  "classifications": {{"industry_name": {{"verdict": "SPECIFIC|BROAD", "reason": "..."}}}},
  "recommendation": "industry_first|keywords_first",
  "reason": "1 sentence why"
}}"""


async def classify_industry_specificity(
    query: str,
    offer: str,
    industries: List[str],
    openai_key: str,
) -> Dict:
    """Classify if matched industries are specific enough for the query.

    Returns:
        {
            "recommendation": "industry_first" | "keywords_first",
            "specific_industries": ["apparel & fashion"],
            "broad_industries": ["marketing & advertising"],
            "reason": "...",
        }
    """
    if not industries or not openai_key:
        return {"recommendation": "keywords_first", "specific_industries": [], "broad_industries": industries or [], "reason": "no industries or key"}

    prompt = CLASSIFY_PROMPT.format(
        query=query, offer=offer[:300],
        industries=json.dumps(industries),
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0,
                },
            )
            data = resp.json()
            extract_openai_usage(data, "gpt-4o-mini", "classify_industry_specificity")

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(clean)

            specific = []
            broad = []
            for ind_name, classification in result.get("classifications", {}).items():
                if classification.get("verdict") == "SPECIFIC":
                    specific.append(ind_name)
                else:
                    broad.append(ind_name)

            recommendation = result.get("recommendation", "keywords_first")
            # Override: if ANY industry is specific, use it
            if specific:
                recommendation = "industry_first"

            logger.info(f"Industry classifier: {recommendation} — specific={specific}, broad={broad}")

            return {
                "recommendation": recommendation,
                "specific_industries": specific,
                "broad_industries": broad,
                "reason": result.get("reason", ""),
                "classifications": result.get("classifications", {}),
            }

    except Exception as e:
        logger.warning(f"Industry classifier failed: {e}")
        # Default: if query words appear in industry name, it's probably specific
        specific = [i for i in industries if any(w in i.lower() for w in query.lower().split())]
        return {
            "recommendation": "industry_first" if specific else "keywords_first",
            "specific_industries": specific,
            "broad_industries": [i for i in industries if i not in specific],
            "reason": f"Fallback heuristic (classifier failed: {str(e)[:50]})",
        }
