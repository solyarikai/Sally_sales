"""Apollo Filter Mapper — maps user query to Apollo search filters.

Steps:
  A. Embedding pre-filter: query → top 50 keywords from taxonomy by similarity
  B. GPT filter mapper: picks from industries (112) + keywords (50) + size (8)
  C. Location extractor: regex, no GPT
  D. Filter assembler: combine + validate

Input:  "IT consulting in Miami" + "EasyStaff payroll platform"
Output: {"q_organization_keyword_tags": [...], "organization_locations": [...],
         "organization_num_employees_ranges": [...]}

All values come from known Apollo vocabulary. No hallucination.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def map_query_to_filters(
    query: str,
    offer: str,
    openai_key: str,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """Full pipeline: query → Apollo filters.

    Returns:
        {
            "q_organization_keyword_tags": [...],
            "organization_locations": [...],
            "organization_num_employees_ranges": [...],
            "mapping_details": {
                "industries_selected": [...],
                "keywords_selected": [...],
                "unverified_keywords": [...],
                "employee_ranges": [...],
                "locations": [...],
                "keyword_map_size": N,
                "shortlist_size": N,
                "model_used": "...",
            }
        }
    """
    from app.services.taxonomy_service import taxonomy_service

    # ── Step A: Embedding pre-filter ──
    keyword_shortlist = await taxonomy_service.get_keyword_shortlist(query, openai_key, top_n=50)
    all_industries = taxonomy_service.get_all_industries()
    employee_ranges = taxonomy_service.get_employee_ranges()
    keyword_map_size = len(taxonomy_service.get_all_keywords())

    logger.info(f"Filter mapper: {len(all_industries)} industries, "
                f"{keyword_map_size} keywords in map, {len(keyword_shortlist)} in shortlist")

    # ── Step B: GPT structured picker ──
    gpt_result = await _gpt_pick_filters(
        query=query,
        offer=offer,
        industries=all_industries,
        keyword_shortlist=keyword_shortlist,
        employee_ranges=employee_ranges,
        openai_key=openai_key,
        model=model,
    )

    # ── Step C: Location extraction ──
    locations = _extract_locations(query)

    # ── Step D: Assemble + validate ──
    industries_selected = gpt_result.get("industries", [])
    keywords_selected = gpt_result.get("keywords", [])
    unverified = gpt_result.get("unverified_keywords", [])
    size_ranges = gpt_result.get("employee_ranges", ["11,50", "51,200"])

    # Validate industries against known list
    valid_industries = set(i.lower() for i in all_industries)
    industries_clean = [i for i in industries_selected if i.lower() in valid_industries]
    if len(industries_clean) < len(industries_selected):
        dropped = [i for i in industries_selected if i.lower() not in valid_industries]
        logger.warning(f"Dropped invalid industries: {dropped}")

    # Validate keywords against known list
    valid_keywords = set(k.lower() for k in taxonomy_service.get_all_keywords())
    keywords_clean = [k for k in keywords_selected if k.lower() in valid_keywords]
    keywords_unverified = [k for k in keywords_selected if k.lower() not in valid_keywords]
    keywords_unverified.extend(unverified)

    # Validate employee ranges
    valid_ranges = set(employee_ranges)
    ranges_clean = [r for r in size_ranges if r in valid_ranges]
    if not ranges_clean:
        ranges_clean = ["11,50", "51,200"]  # safe default

    # Build final keyword_tags: industries (broad) + keywords (precise) + unverified (cold start)
    keyword_tags = industries_clean + keywords_clean
    if keywords_unverified and len(keyword_tags) < 3:
        # Only add unverified if we don't have enough verified keywords
        keyword_tags.extend(keywords_unverified[:2])

    if not keyword_tags:
        # Emergency fallback — use industries only
        keyword_tags = industries_clean[:3] if industries_clean else [query.split(" in ")[0]]

    # Ensure at least 1 industry name for broad coverage
    if not any(i.lower() in set(k.lower() for k in keyword_tags) for i in industries_clean):
        if industries_clean:
            keyword_tags.insert(0, industries_clean[0])

    result = {
        "q_organization_keyword_tags": keyword_tags,
        "organization_locations": locations,
        "organization_num_employees_ranges": ranges_clean,
        "mapping_details": {
            "industries_selected": industries_clean,
            "keywords_selected": keywords_clean,
            "unverified_keywords": keywords_unverified,
            "employee_ranges": ranges_clean,
            "locations": locations,
            "keyword_map_size": keyword_map_size,
            "shortlist_size": len(keyword_shortlist),
            "model_used": gpt_result.get("model_used", model),
        },
    }

    logger.info(f"Filters assembled: {len(keyword_tags)} keyword_tags, "
                f"{len(locations)} locations, {len(ranges_clean)} size ranges")
    return result


async def _gpt_pick_filters(
    query: str,
    offer: str,
    industries: List[str],
    keyword_shortlist: List[str],
    employee_ranges: List[str],
    openai_key: str,
    model: str = "gpt-4.1-mini",
) -> Dict:
    """GPT picks from provided lists. Never invents."""

    keyword_section = ""
    if keyword_shortlist:
        keyword_section = f"""
STEP 2 — KEYWORDS
Pick 3-7 from this list of real Apollo keyword tags (ranked by relevance to your query):
{json.dumps(keyword_shortlist)}
Pick the ones that best describe the TARGET COMPANIES (not our product).
If fewer than 3 match, you may suggest up to 2 new ones in "unverified_keywords"."""
    else:
        keyword_section = """
STEP 2 — KEYWORDS
No known Apollo keyword tags available yet (cold start).
Suggest 3-5 keywords that target companies would use on their profiles.
Put ALL in "unverified_keywords" (they haven't been verified against Apollo yet).
Leave "keywords" empty."""

    prompt = f"""You map business queries to Apollo.io search filters.
Select ONLY from the lists provided. Never invent industry names.

User's segment: {query}
User's product: {offer}

STEP 1 — INDUSTRIES
Pick 2-4 from this EXACT list (these are Apollo's industry categories):
{json.dumps(industries)}

{keyword_section}

STEP 3 — EMPLOYEE SIZE
Pick 1-3 ranges that match the typical BUYER of this product.
Available ranges: {json.dumps(employee_ranges)}
Think: what size companies would buy "{offer[:100]}"?

Return ONLY valid JSON:
{{"industries": ["exact industry 1", "exact industry 2"],
  "keywords": ["exact keyword from list"],
  "unverified_keywords": ["suggested keyword not in list"],
  "employee_ranges": ["11,50", "51,200"]}}"""

    for try_model in [model, "gpt-4o-mini"]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={
                        "model": try_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "temperature": 0,
                    },
                )
                data = resp.json()
                if "error" in data:
                    logger.warning(f"Filter mapper {try_model}: {data['error']}")
                    continue
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                result = json.loads(content)
                result["model_used"] = try_model
                return result
        except Exception as e:
            logger.warning(f"Filter mapper {try_model} failed: {e}")
            continue

    # Total fallback
    return {
        "industries": industries[:2] if industries else [],
        "keywords": [],
        "unverified_keywords": [query.split(" in ")[0]],
        "employee_ranges": ["11,50", "51,200"],
        "model_used": "fallback",
    }


def _extract_locations(query: str) -> List[str]:
    """Extract location from query using rules. No GPT needed."""
    # Common patterns: "in Miami", "in UK and UAE", "in Italy"
    match = re.search(r'\bin\s+(.+?)(?:\s+for|\s+with|\s+targeting|\s*$)', query, re.IGNORECASE)
    if not match:
        return []

    loc_text = match.group(1).strip()

    # Split on "and" / ","
    parts = re.split(r'\s+and\s+|,\s*', loc_text, flags=re.IGNORECASE)
    locations = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Remove trailing segment words that leaked in
        part = re.sub(r'\s*(companies|firms|agencies|brands|platforms|businesses)\s*$', '', part, flags=re.IGNORECASE).strip()
        if part:
            locations.append(part)

    return locations
