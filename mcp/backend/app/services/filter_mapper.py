"""Apollo Filter Mapper — maps user query to Apollo search filters.

Steps:
  A. GPT picks 2-3 industries from 67 real Apollo industries → tag_id lookup
  B. GPT generates 20-30 keywords freely (no predefined list)
  C. Location extractor: regex, no GPT
  D. Filter assembler: return both tag_ids + keywords for parallel streams

Apollo accepts ANY free-text in q_organization_keyword_tags.
No keyword taxonomy or embeddings needed.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.services.cost_tracker import extract_openai_usage

logger = logging.getLogger(__name__)

EMPLOYEE_RANGES = ["1,10", "11,50", "51,200", "201,500", "501,1000", "1001,5000", "5001,10000", "10001,"]


async def map_query_to_filters(
    query: str,
    offer: str,
    openai_key: str,
    model: str = "gpt-4.1-mini",
    seed_keywords: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Map a user query to Apollo search filters.

    Returns both industry_tag_ids AND keywords — streaming pipeline
    runs them in parallel and stops at KPI.
    """
    from app.db import async_session_maker
    from sqlalchemy import text as sa_text

    # ── Step A: Load real Apollo industries (with tag_ids) from DB ──
    async with async_session_maker() as session:
        result = await session.execute(
            sa_text("SELECT term, tag_id FROM apollo_taxonomy WHERE term_type='industry' AND tag_id IS NOT NULL ORDER BY term")
        )
        industry_rows = result.all()

    industries = [r[0] for r in industry_rows]
    industry_tag_map = {r[0].lower(): r[1] for r in industry_rows}

    logger.info(f"Filter mapper: {len(industries)} Apollo industries loaded")

    # ── Step B1: GPT picks 2-3 industries ──
    selected_industries = await _pick_industries(
        query=query, offer=offer, industries=industries, openai_key=openai_key,
    )

    # ── Step B2: GPT generates keywords + employee size (unconstrained) ──
    gpt_result = await _generate_keywords(
        query=query, offer=offer, openai_key=openai_key, model=model,
        seed_keywords=seed_keywords,
    )

    # ── Step C: Location extraction (regex) ──
    locations = _extract_locations(query)

    # ── Step D: Assemble ──
    keywords = gpt_result.get("keywords", [])
    size_ranges = gpt_result.get("employee_ranges", ["11,50", "51,200"])

    # Validate employee ranges
    valid_ranges = set(EMPLOYEE_RANGES)
    ranges_clean = [r for r in size_ranges if r in valid_ranges]
    if not ranges_clean:
        ranges_clean = ["11,50", "51,200"]

    # Add industry names to keywords for broad coverage
    keyword_tags = list(selected_industries) + keywords
    if not keyword_tags:
        keyword_tags = [query.split(" in ")[0]]

    # Look up tag_ids for selected industries
    industry_tag_ids = []
    for ind_name in selected_industries:
        tag = industry_tag_map.get(ind_name.lower())
        if tag:
            industry_tag_ids.append(tag)
            logger.info(f"Industry tag_id: '{ind_name}' → {tag}")

    # Deduplicate tag_ids (multiple names can share same tag)
    industry_tag_ids = list(dict.fromkeys(industry_tag_ids))

    result = {
        "q_organization_keyword_tags": keyword_tags,
        "organization_industry_tag_ids": industry_tag_ids if industry_tag_ids else None,
        "industries": selected_industries,
        "organization_locations": locations,
        "organization_num_employees_ranges": ranges_clean,
        "mapping_details": {
            "industries_selected": selected_industries,
            "industry_tag_ids": industry_tag_ids,
            "keywords_generated": keywords,
            "employee_ranges": ranges_clean,
            "locations": locations,
            "model_used": gpt_result.get("model_used", model),
            "seed_keywords_count": len(seed_keywords) if seed_keywords else 0,
        },
    }

    logger.info(f"Filters: {len(industry_tag_ids)} tag_ids, {len(keyword_tags)} keywords, {len(locations)} locations")
    return result


async def _pick_industries(
    query: str, offer: str, industries: List[str],
    openai_key: str, model: str = "gpt-4.1-mini",
) -> List[str]:
    """Pick 2-3 Apollo industries for a query."""
    prompt = f""""{query}" — pick 2-3 matching Apollo industries.
{json.dumps(industries)}
JSON: {{"industries": ["exact name from list"]}}"""

    for try_model in [model, "gpt-4o-mini"]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={"model": try_model, "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 200, "temperature": 0},
                )
                data = resp.json()
                if "error" in data:
                    continue
                extract_openai_usage(data, try_model, "pick_industries")
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                result = json.loads(content)
                inds = result.get("industries", [])
                if inds and isinstance(inds[0], dict):
                    inds = [x.get("name", "") for x in inds if x.get("name")]
                logger.info(f"Industries for '{query}': {inds}")
                return inds
        except Exception:
            continue
    return industries[:2]


async def _generate_keywords(
    query: str,
    offer: str,
    openai_key: str,
    model: str = "gpt-4.1-mini",
    seed_keywords: Optional[List[str]] = None,
) -> Dict:
    """GPT generates keywords freely — no predefined list constraint."""

    seed_section = ""
    if seed_keywords:
        seed_section = f"""
SEED KEYWORDS (from user's strategy document — use these as a starting point):
{json.dumps(seed_keywords[:30])}
Include these and generate related/adjacent keywords."""

    prompt = f"""Generate Apollo.io search keywords for finding B2B companies.

User's segment: {query}
User's product: {offer}
{seed_section}

Generate 20-30 keywords that target companies would have on their Apollo profiles.
Include: industry terms, product/service names, technology names, synonyms,
adjacent niches, specific sub-sectors, business model descriptors.
More keywords = broader search coverage.

EMPLOYEE SIZE
Pick 1-3 ranges that match the typical BUYER of this product.
Available: {json.dumps(EMPLOYEE_RANGES)}

Return ONLY valid JSON:
{{"keywords": ["keyword1", "keyword2", ...],
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
                        "max_tokens": 1000,
                        "temperature": 0,
                    },
                )
                data = resp.json()
                if "error" in data:
                    logger.warning(f"Keyword gen {try_model}: {data['error']}")
                    continue
                extract_openai_usage(data, try_model, "generate_keywords")
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                result = json.loads(content)
                result["model_used"] = try_model
                # Normalize if GPT returned dicts
                raw_kw = result.get("keywords", [])
                if raw_kw and isinstance(raw_kw[0], dict):
                    result["keywords"] = [k.get("term", k.get("name", "")) for k in raw_kw if k.get("term") or k.get("name")]
                logger.info(f"Generated {len(result.get('keywords', []))} keywords for '{query}'")
                return result
        except Exception as e:
            logger.warning(f"Keyword gen {try_model} failed: {e}")
            continue

    return {
        "keywords": [query.split(" in ")[0]],
        "employee_ranges": ["11,50", "51,200"],
        "model_used": "fallback",
    }


def _extract_locations(query: str) -> List[str]:
    """Extract location from query using rules. No GPT needed."""
    match = re.search(r'\bin\s+(.+?)(?:\s+for|\s+with|\s+targeting|\s*$)', query, re.IGNORECASE)
    if not match:
        return []

    loc_text = match.group(1).strip()
    parts = re.split(r'\s+and\s+|,\s*', loc_text, flags=re.IGNORECASE)
    locations = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part = re.sub(r'\s*(companies|firms|agencies|brands|platforms|businesses)\s*$', '', part, flags=re.IGNORECASE).strip()
        if part:
            locations.append(part)

    return locations
