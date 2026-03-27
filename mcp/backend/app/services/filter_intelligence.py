"""Apollo Filter Intelligence — translates natural language to optimal Apollo filters.

Approach: Probe + Extract (ZERO hardcoding)
1. GPT generates candidate filters from NL
2. Probe search (1 page, 1 credit) returns 25 real companies
3. Extract Apollo's actual taxonomy from results (industry/keyword frequency)
4. Return refined filters based on REAL Apollo data
"""
import logging
import json
from typing import Any, Dict, List, Optional
from collections import Counter

import httpx

logger = logging.getLogger(__name__)


async def suggest_filters(
    query: str,
    apollo_service,
    openai_key: Optional[str] = None,
    target_count: int = 10,
) -> Dict[str, Any]:
    """Translate NL query into optimal Apollo filters via probe search."""

    # Step 1: LLM generates candidate filters
    candidate = await _llm_generate_candidates(query, openai_key)
    if not candidate:
        return {"error": "Failed to generate candidate filters from query"}

    # Step 2: Probe search (1 page = max 25 results)
    probe_filters = candidate.get("filters", {})
    probe_filters["max_pages"] = 1
    probe_filters["per_page"] = 25

    probe_results = await apollo_service.search_organizations(
        keyword_tags=probe_filters.get("q_organization_keyword_tags", []),
        locations=probe_filters.get("organization_locations"),
        num_employees_ranges=probe_filters.get("organization_num_employees_ranges"),
        page=1,
        per_page=25,
    )

    if not probe_results:
        return {
            "candidate_filters": probe_filters,
            "probe_results": None,
            "message": "Probe search returned no results. Try broader keywords.",
        }

    # Apollo returns companies in "accounts" or "organizations"
    companies = probe_results.get("organizations", []) or probe_results.get("accounts", [])
    total_available = probe_results.get("pagination", {}).get("total_entries", 0)

    if not companies:
        return {
            "candidate_filters": probe_filters,
            "probe_results": {"companies_found": 0, "total_available": total_available},
            "message": "No companies matched. Try different keywords.",
        }

    # Step 3: Extract Apollo's actual taxonomy from probe results
    taxonomy = _extract_taxonomy(companies)

    # Step 4: Build refined filters
    refined = _build_refined_filters(candidate, taxonomy, target_count)

    # Calculate pages needed
    per_page = 25
    companies_needed = int(target_count / 0.3)  # ~30% target rate
    pages_needed = max(1, (companies_needed + per_page - 1) // per_page)

    return {
        "suggested_filters": refined,
        "probe_results": {
            "companies_found": len(companies),
            "total_available": total_available,
            "top_industries": dict(taxonomy["industries"].most_common(5)),
            "top_keywords": dict(taxonomy["keywords"].most_common(10)),
            "size_distribution": dict(taxonomy["sizes"].most_common(5)),
        },
        "estimated": {
            "target_count": target_count,
            "pages_needed": pages_needed,
            "credits": pages_needed,
            "total_companies": min(total_available, pages_needed * per_page),
        },
        "message": f"Probe found {len(companies)} companies ({total_available} total available). "
                   f"Refined filters based on Apollo's actual taxonomy. "
                   f"To find ~{target_count} targets: {pages_needed} pages, {pages_needed} credits.",
    }


async def _llm_generate_candidates(query: str, openai_key: Optional[str] = None) -> Optional[Dict]:
    """Use GPT to generate initial Apollo filter candidates from natural language."""
    if not openai_key:
        from app.config import settings
        openai_key = settings.OPENAI_API_KEY
    if not openai_key:
        # Fallback: basic parsing
        return _basic_parse(query)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": """You translate natural language business queries into Apollo.io search filters.
Return ONLY valid JSON with these fields:
{
  "filters": {
    "organization_locations": ["City, Country" or "Country"],
    "q_organization_keyword_tags": ["keyword1", "keyword2", ...],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,200"]
  }
}

Rules:
- Keywords should be BROAD industry terms, not the exact user query
- Include synonyms and related terms (e.g., "IT consulting" → also "IT services", "technology consulting", "software development")
- Location should include country if city is given
- Employee ranges should cover the likely range for the segment
- Generate 3-7 keyword tags for best results"""},
                        {"role": "user", "content": f"Generate Apollo search filters for: {query}"},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
    except Exception as e:
        logger.error(f"LLM filter generation failed: {e}")
        return _basic_parse(query)


def _basic_parse(query: str) -> Dict:
    """Fallback: basic keyword extraction without LLM."""
    words = query.lower().split()
    keywords = [w for w in words if len(w) > 3 and w not in ("find", "gather", "search", "companies", "businesses", "firms")]
    locations = []
    # Common city/country detection
    for loc in ["london", "new york", "dubai", "berlin", "paris", "mumbai", "singapore", "sydney", "tokyo"]:
        if loc in query.lower():
            locations.append(loc.title())
    return {
        "filters": {
            "organization_locations": locations or None,
            "q_organization_keyword_tags": keywords[:5] or ["business services"],
            "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
        }
    }


def _extract_taxonomy(companies: List[Dict]) -> Dict[str, Counter]:
    """Extract industry/keyword/size frequency from probe results."""
    industries = Counter()
    keywords = Counter()
    sizes = Counter()

    for c in companies:
        # Industry
        ind = c.get("industry") or c.get("organization_industry")
        if ind:
            industries[ind.lower()] += 1

        # Keywords from various Apollo fields
        for kw_field in ["keywords", "keyword_tags", "q_organization_keyword_tags"]:
            kws = c.get(kw_field) or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            for kw in kws:
                if kw and len(kw) > 2:
                    keywords[kw.lower().strip()] += 1

        # SIC/NAICS as fallback keywords
        for code_field in ["sic_codes", "naics_codes"]:
            codes = c.get(code_field) or []
            # We don't use codes as keywords — they're numeric

        # Size
        emp = c.get("estimated_num_employees") or c.get("num_contacts")
        if emp:
            if emp <= 10:
                sizes["1-10"] += 1
            elif emp <= 50:
                sizes["11-50"] += 1
            elif emp <= 200:
                sizes["51-200"] += 1
            elif emp <= 500:
                sizes["201-500"] += 1
            else:
                sizes["500+"] += 1

    return {"industries": industries, "keywords": keywords, "sizes": sizes}


def _build_refined_filters(candidate: Dict, taxonomy: Dict[str, Counter], target_count: int) -> Dict:
    """Build refined filters from taxonomy analysis."""
    original = candidate.get("filters", {})

    # Use top keywords from probe results (frequency ≥ 2 or top 7)
    top_kw = taxonomy["keywords"].most_common(10)
    refined_keywords = [kw for kw, count in top_kw if count >= 2]
    if len(refined_keywords) < 3:
        refined_keywords = [kw for kw, _ in top_kw[:7]]

    # Merge with original candidate keywords (keep unique)
    original_kw = [k.lower() for k in original.get("q_organization_keyword_tags", [])]
    all_keywords = list(dict.fromkeys(refined_keywords + original_kw))[:10]

    # Employee ranges from probe data
    size_map = {"1-10": "1,10", "11-50": "11,50", "51-200": "51,200", "201-500": "201,500", "500+": "501,10000"}
    top_sizes = taxonomy["sizes"].most_common(3)
    refined_sizes = [size_map.get(s, "11,50") for s, _ in top_sizes]
    if not refined_sizes:
        refined_sizes = original.get("organization_num_employees_ranges", ["11,50", "51,200"])

    return {
        "organization_locations": original.get("organization_locations"),
        "q_organization_keyword_tags": all_keywords,
        "organization_num_employees_ranges": refined_sizes,
    }
