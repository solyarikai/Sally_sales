"""Document Extraction Service — extracts project data from strategy documents.

Reads a user-provided document (outreach plan, ICP definition, campaign brief)
and extracts structured data: offer, roles, filters, sequences, settings.
Silently skips what can't be automated.
"""
import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def extract_from_document(
    text: str,
    website: str,
    openai_key: str,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """Extract project data from a strategy document.

    Extracts what can be automated. Silently skips the rest.
    """
    prompt = f"""You are an expert at extracting structured campaign data from strategy documents.

Website: {website}

Extract the following from this document. Return ONLY valid JSON.
If a field cannot be determined, omit it (don't guess).
Silently skip anything that requires manual work, external signals, or data not in the document.

Extract:
1. "offer" — the company's product/service in 1-2 sentences
2. "value_prop" — the key value proposition
3. "target_audience" — who they're selling to
4. "target_roles" — object with:
   - "primary": [list of primary decision-maker titles]
   - "secondary": [list of secondary titles]
   - "tertiary": [list of tertiary/fallback titles]
   - "seniorities": [Apollo seniority levels: "owner", "founder", "c_suite", "vp", "head", "director"]
5. "segments" — array of target sub-segments, each with:
   - "name": segment name (e.g. "Payments/PSPs")
   - "keywords": [Apollo search keywords for this segment]
6. "apollo_filters" — object with:
   - "combined_keywords": [ALL keywords from ALL segments merged]
   - "locations": [target countries/regions]
   - "employee_range": "min,max" (e.g. "20,500")
   - "industries": [Apollo industry names if identifiable]
   - "funding_stages": [if mentioned: "series_a", "series_b", etc.]
7. "sequences" — array of email sequences that CAN be automated:
   - "name": sequence name
   - "steps": array of {{"day": N, "subject": "...", "body": "..."}}
   - ONLY include sequences where ALL variables are standard ({{{{company}}}}, {{{{firstName}}}}, {{{{signature}}}})
   - SKIP sequences requiring external data (funding dates, competitor info, event attendance)
8. "campaign_settings" — object with:
   - "daily_limit_per_mailbox": number
   - "tracking": boolean
   - "stop_on_reply": boolean
   - "plain_text": boolean

Return ONLY the JSON object, no markdown formatting.

DOCUMENT:
{text[:15000]}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4000,
                    "temperature": 0,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(clean)

            # Add metadata
            result["_model"] = model
            result["_tokens"] = data.get("usage", {})
            result["_website"] = website

            logger.info(f"Document extraction ({model}): "
                       f"{len(result.get('segments', []))} segments, "
                       f"{len(result.get('sequences', []))} sequences, "
                       f"{len(result.get('apollo_filters', {}).get('combined_keywords', []))} keywords")

            return result

    except Exception as e:
        logger.error(f"Document extraction failed ({model}): {e}")
        return {"error": str(e), "_model": model}


async def test_model_extraction(
    text: str,
    website: str,
    openai_key: str,
    models: list = None,
) -> list:
    """Test document extraction across multiple models. Returns scored results."""
    if not models:
        models = [
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-5-nano",
            "gpt-5-mini",
            "gpt-5.4-nano",
            "gpt-5.4-mini",
        ]

    results = []
    for model in models:
        logger.info(f"Testing model: {model}")
        result = await extract_from_document(text, website, openai_key, model)
        result["_model"] = model
        results.append(result)

    return results


def score_extraction(result: Dict, ground_truth: Dict) -> Dict:
    """Score an extraction result against ground truth. Returns per-field scores."""
    scores = {}

    # Offer (1 point)
    if result.get("offer") and len(result["offer"]) > 20:
        scores["offer"] = 1
    else:
        scores["offer"] = 0

    # Target audience (1 point)
    if result.get("target_audience") and len(result["target_audience"]) > 10:
        scores["target_audience"] = 1
    else:
        scores["target_audience"] = 0

    # Roles (3 points — 1 per tier)
    roles = result.get("target_roles", {})
    gt_roles = ground_truth.get("target_roles", {})
    for tier in ["primary", "secondary", "tertiary"]:
        extracted = set(r.lower() for r in roles.get(tier, []))
        expected = set(r.lower() for r in gt_roles.get(tier, []))
        if extracted and len(extracted & expected) >= len(expected) * 0.5:
            scores[f"roles_{tier}"] = 1
        else:
            scores[f"roles_{tier}"] = 0

    # Keywords (1 point — need 10+)
    kw = result.get("apollo_filters", {}).get("combined_keywords", [])
    scores["keywords"] = 1 if len(kw) >= 10 else 0

    # Locations (1 point — need 3+)
    locs = result.get("apollo_filters", {}).get("locations", [])
    scores["locations"] = 1 if len(locs) >= 3 else 0

    # Employee range (1 point)
    emp = result.get("apollo_filters", {}).get("employee_range", "")
    scores["employee_range"] = 1 if "20" in emp and "500" in emp else 0

    # Sequence (4 points — 1 per email)
    seqs = result.get("sequences", [])
    if seqs:
        steps = seqs[0].get("steps", [])
        for i in range(min(4, len(steps))):
            step = steps[i]
            has_subject = bool(step.get("subject"))
            has_body = bool(step.get("body")) and len(step.get("body", "")) > 50
            scores[f"sequence_email_{i+1}"] = 1 if has_subject and has_body else 0
        for i in range(len(steps), 4):
            scores[f"sequence_email_{i+1}"] = 0
    else:
        for i in range(4):
            scores[f"sequence_email_{i+1}"] = 0

    # Campaign settings (1 point)
    settings = result.get("campaign_settings", {})
    scores["settings"] = 1 if settings.get("stop_on_reply") is not None else 0

    scores["total"] = sum(scores.values())
    scores["max"] = 13
    scores["pct"] = round(scores["total"] / 13 * 100)

    return scores
