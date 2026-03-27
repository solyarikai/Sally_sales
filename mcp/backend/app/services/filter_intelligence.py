"""Apollo Filter Intelligence — translates natural language to optimal Apollo filters.

Approach: Probe + Evaluate + Extract (ZERO hardcoding)
1. GPT generates candidate filters from NL
2. Probe search (1 page = 1 credit, up to 100 companies)
3. GPT EVALUATES probe quality — are returned companies relevant?
4. If quality LOW → GPT adjusts filters → retry probe (max 3 loops)
5. If quality OK → enrich TOP 5 for real keyword taxonomy (5 credits)
6. Return refined filters based on REAL Apollo data

Apollo credit costs:
  /mixed_companies/search    — 1 credit / page (up to 100 companies)
  /organizations/enrich      — 1 credit / result
  /people/bulk_match         — 1 credit / net-new email
"""
import logging
import json
from typing import Any, Dict, List, Optional
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

MAX_PROBE_RETRIES = 3
MIN_RELEVANCE_SCORE = 0.5  # At least 50% of sampled companies must be relevant


async def suggest_filters(
    query: str,
    apollo_service,
    openai_key: Optional[str] = None,
    target_count: int = 10,
) -> Dict[str, Any]:
    """Translate NL query into optimal Apollo filters via probe + evaluate loop."""

    # Step 1: LLM generates candidate filters
    candidate = await _llm_generate_candidates(query, openai_key)
    if not candidate:
        return {"error": "Failed to generate candidate filters from query"}

    credits_spent = {"search_pages": 0, "enrichments": 0}
    probe_history = []

    # Step 2-4: Probe + Evaluate loop (max 3 attempts)
    companies = []
    total_available = 0
    final_filters = candidate.get("filters", {})

    for attempt in range(1, MAX_PROBE_RETRIES + 1):
        probe_filters = final_filters.copy()

        probe_results = await apollo_service.search_organizations(
            keyword_tags=probe_filters.get("q_organization_keyword_tags", []),
            locations=probe_filters.get("organization_locations"),
            num_employees_ranges=probe_filters.get("organization_num_employees_ranges"),
            page=1,
            per_page=100,
        )
        credits_spent["search_pages"] += 1

        if not probe_results:
            probe_history.append({"attempt": attempt, "filters": probe_filters, "result": "no_response"})
            continue

        companies = probe_results.get("organizations", []) or probe_results.get("accounts", [])
        total_available = probe_results.get("pagination", {}).get("total_entries", 0)

        if not companies:
            probe_history.append({"attempt": attempt, "filters": probe_filters, "result": "empty", "total": 0})
            # Ask LLM to broaden
            adjusted = await _llm_adjust_filters(query, probe_filters, [], "No companies found. Broaden keywords.", openai_key)
            if adjusted:
                final_filters = adjusted.get("filters", final_filters)
            continue

        # Evaluate quality of returned companies
        sample = companies[:10]  # Evaluate first 10
        evaluation = await _llm_evaluate_probe(query, sample, openai_key)

        probe_history.append({
            "attempt": attempt,
            "filters": probe_filters,
            "companies_found": len(companies),
            "total_available": total_available,
            "relevance_score": evaluation.get("relevance_score", 0),
            "verdict": evaluation.get("verdict", "unknown"),
        })

        logger.info(
            f"Probe attempt {attempt}: {len(companies)} companies, "
            f"relevance={evaluation.get('relevance_score', 0):.0%}, "
            f"verdict={evaluation.get('verdict')}"
        )

        # Good enough? Stop probing.
        if evaluation.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE:
            break

        # Bad quality — ask LLM to adjust filters based on what went wrong
        if attempt < MAX_PROBE_RETRIES:
            feedback = evaluation.get("feedback", "Companies don't match the query")
            adjusted = await _llm_adjust_filters(query, probe_filters, sample, feedback, openai_key)
            if adjusted:
                final_filters = adjusted.get("filters", final_filters)

    if not companies:
        return {
            "candidate_filters": final_filters,
            "probe_history": probe_history,
            "credits_spent": credits_spent,
            "probe_results": {"companies_found": 0, "total_available": total_available},
            "message": f"No relevant companies found after {len(probe_history)} attempts. Try a different query.",
        }

    # Step 5: Enrich TOP 5 companies to get their REAL Apollo keywords
    enriched_keywords = Counter()
    enriched_industries = Counter()
    enriched_count = 0
    for comp in companies[:5]:
        domain = comp.get("domain") or comp.get("primary_domain")
        if not domain:
            continue
        org_data = await apollo_service.enrich_organization(domain)
        if org_data:
            enriched_count += 1
            credits_spent["enrichments"] += 1
            ind = org_data.get("industry")
            if ind:
                enriched_industries[ind.lower()] += 1
            for ind_item in (org_data.get("industries") or []):
                enriched_industries[ind_item.lower()] += 1
            for kw in (org_data.get("keywords") or []):
                kw_clean = kw.lower().strip()
                if 2 < len(kw_clean) < 50:
                    enriched_keywords[kw_clean] += 1

    # Step 5b: Extract from search results too (sizes, etc.)
    taxonomy = _extract_taxonomy(companies)
    taxonomy["keywords"] += enriched_keywords
    taxonomy["industries"] += enriched_industries

    # Step 6: Build refined filters from REAL Apollo data
    refined = _build_refined_filters({"filters": final_filters}, taxonomy, target_count)

    # Calculate pages needed (100 companies per page, 1 credit per page)
    per_page = 100
    companies_needed = int(target_count / 0.3)  # ~30% target rate
    pages_needed = max(1, (companies_needed + per_page - 1) // per_page)

    total_credits = credits_spent["search_pages"] + credits_spent["enrichments"]

    return {
        "suggested_filters": refined,
        "probe_results": {
            "companies_found": len(companies),
            "total_available": total_available,
            "top_industries": dict(taxonomy["industries"].most_common(5)),
            "top_keywords": dict(taxonomy["keywords"].most_common(10)),
            "size_distribution": dict(taxonomy["sizes"].most_common(5)),
            "sample_companies": [
                {"name": c.get("name"), "domain": c.get("domain") or c.get("primary_domain"),
                 "industry": c.get("industry")}
                for c in companies[:5]
            ],
        },
        "probe_history": probe_history,
        "credits_spent": {**credits_spent, "total": total_credits},
        "estimated": {
            "target_count": target_count,
            "pages_needed": pages_needed,
            "credits_for_gathering": pages_needed,
            "total_companies": min(total_available, pages_needed * per_page),
        },
        "message": (
            f"Probe found {len(companies)} companies ({total_available} total) "
            f"in {len(probe_history)} attempt(s). "
            f"Discovery cost: {total_credits} credits ({credits_spent['search_pages']} search + {credits_spent['enrichments']} enrichment). "
            f"To gather ~{target_count} targets: {pages_needed} page(s) = {pages_needed} credit(s)."
        ),
    }


async def _llm_evaluate_probe(
    query: str, companies: List[Dict], openai_key: Optional[str] = None
) -> Dict[str, Any]:
    """GPT evaluates whether probe results match the user's query.
    Returns relevance_score (0-1), verdict, feedback."""
    if not openai_key:
        from app.config import settings
        openai_key = settings.OPENAI_API_KEY
    if not openai_key:
        return {"relevance_score": 0.7, "verdict": "no_llm", "feedback": ""}

    company_lines = []
    for c in companies[:10]:
        name = c.get("name", "?")
        domain = c.get("domain") or c.get("primary_domain", "?")
        industry = c.get("industry", "?")
        emp = c.get("estimated_num_employees") or c.get("num_contacts", "?")
        company_lines.append(f"- {name} ({domain}) | industry: {industry} | employees: {emp}")

    companies_text = "\n".join(company_lines)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": """You evaluate Apollo search results quality.
Given the user's search query and the companies returned, judge how relevant they are.

Return ONLY valid JSON:
{
  "relevance_score": 0.0-1.0,
  "verdict": "good" | "mediocre" | "bad",
  "relevant_count": N,
  "irrelevant_examples": ["company X is a restaurant, not IT"],
  "feedback": "one-line suggestion to improve filters"
}

Scoring:
- 0.8-1.0 = most companies clearly match the query intent
- 0.5-0.7 = mixed results, some match, some don't
- 0.0-0.4 = most companies are irrelevant to the query"""},
                        {"role": "user", "content": f"Query: {query}\n\nReturned companies:\n{companies_text}"},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.2,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
    except Exception as e:
        logger.error(f"LLM probe evaluation failed: {e}")
        return {"relevance_score": 0.7, "verdict": "eval_failed", "feedback": str(e)}


async def _llm_adjust_filters(
    query: str, current_filters: Dict, companies: List[Dict],
    feedback: str, openai_key: Optional[str] = None
) -> Optional[Dict]:
    """GPT adjusts Apollo filters based on feedback about why probe was bad."""
    if not openai_key:
        from app.config import settings
        openai_key = settings.OPENAI_API_KEY
    if not openai_key:
        return None

    company_summary = ""
    if companies:
        lines = [f"- {c.get('name', '?')} ({c.get('industry', '?')})" for c in companies[:5]]
        company_summary = f"\n\nCompanies that came back (wrong):\n" + "\n".join(lines)

    current_kw = current_filters.get("q_organization_keyword_tags", [])
    current_loc = current_filters.get("organization_locations", [])
    current_size = current_filters.get("organization_num_employees_ranges", [])

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": """You fix Apollo.io search filters that returned wrong results.

Given the original query, current filters, and feedback about what went wrong, generate BETTER filters.

Return ONLY valid JSON:
{
  "filters": {
    "organization_locations": ["City, Country" or "Country"],
    "q_organization_keyword_tags": ["keyword1", "keyword2", ...],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,200"]
  }
}

Strategies:
- If results were too broad: use more specific keywords
- If results were too narrow or empty: use broader/synonym keywords
- If wrong industry: change keyword tags entirely
- Keep 3-7 keyword tags"""},
                        {"role": "user", "content": (
                            f"Original query: {query}\n"
                            f"Current keywords: {current_kw}\n"
                            f"Current locations: {current_loc}\n"
                            f"Current size ranges: {current_size}\n"
                            f"Problem: {feedback}"
                            f"{company_summary}"
                        )},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.4,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
    except Exception as e:
        logger.error(f"LLM filter adjustment failed: {e}")
        return None


async def _llm_generate_candidates(query: str, openai_key: Optional[str] = None) -> Optional[Dict]:
    """Use GPT to generate initial Apollo filter candidates from natural language."""
    if not openai_key:
        from app.config import settings
        openai_key = settings.OPENAI_API_KEY
    if not openai_key:
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
        ind = c.get("industry") or c.get("organization_industry")
        if ind:
            industries[ind.lower()] += 1

        for kw_field in ["keywords", "keyword_tags", "q_organization_keyword_tags"]:
            kws = c.get(kw_field) or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            for kw in kws:
                if kw and len(kw) > 2:
                    keywords[kw.lower().strip()] += 1

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

    top_kw = taxonomy["keywords"].most_common(10)
    refined_keywords = [kw for kw, count in top_kw if count >= 2]
    if len(refined_keywords) < 3:
        refined_keywords = [kw for kw, _ in top_kw[:7]]

    original_kw = [k.lower() for k in original.get("q_organization_keyword_tags", [])]
    all_keywords = list(dict.fromkeys(refined_keywords + original_kw))[:10]

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
