"""Apollo Filter Intelligence — translates natural language to optimal Apollo filters.

Approach: Probe + Scrape + Evaluate + Extract (ZERO hardcoding)
1. GPT generates candidate filters from NL (cheap, gpt-4o-mini is fine here)
2. Probe search (1 page = 1 credit, up to 100 companies)
3. Scrape top 10 websites via httpx (~3 sec, FREE)
4. User's model (Opus/Gemini/GPT) evaluates REAL website content against query
5. If quality LOW → model adjusts filters → retry probe (max 3 loops)
6. If quality OK → enrich TOP 5 for real keyword taxonomy (5 credits)
7. Return refined filters based on REAL Apollo data

Apollo credit costs:
  /mixed_companies/search    — 1 credit / page (up to 100 companies)
  /organizations/enrich      — 1 credit / result
  /people/bulk_match         — 1 credit / net-new email
"""
import asyncio
import logging
import json
from typing import Any, Dict, List, Optional
from collections import Counter

import httpx

logger = logging.getLogger(__name__)

MAX_PROBE_RETRIES = 3
MIN_RELEVANCE_SCORE = 0.6  # At least 60% of sampled companies must be relevant


async def suggest_filters(
    query: str,
    apollo_service,
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
    target_count: int = 10,
) -> Dict[str, Any]:
    """Translate NL query into optimal Apollo filters via probe + scrape + evaluate loop."""

    # Resolve which model to use for evaluation (user's best model)
    eval_model = _pick_eval_model(anthropic_key, gemini_key, openai_key)
    logger.info(f"Filter intelligence: using {eval_model['provider']} for probe evaluation")

    # Step 1: LLM generates candidate filters (cheap, gpt-4o-mini is enough)
    candidate = await _llm_generate_candidates(query, openai_key)
    if not candidate:
        return {"error": "Failed to generate candidate filters from query"}

    credits_spent = {"search_pages": 0, "enrichments": 0, "websites_scraped": 0}
    probe_history = []

    # Step 2-4: Probe + Scrape + Evaluate loop (max 3 attempts)
    companies = []
    total_available = 0
    final_filters = candidate.get("filters", {})

    for attempt in range(1, MAX_PROBE_RETRIES + 1):
        probe_filters = final_filters.copy()

        # 2a. Apollo search (1 credit)
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
            adjusted = await _model_adjust_filters(query, probe_filters, [], "No companies found. Broaden keywords.", eval_model)
            if adjusted:
                final_filters = adjusted.get("filters", final_filters)
            continue

        # 2b. Scrape top 10 websites in parallel via Apify proxies (FREE, ~3 sec)
        from app.services.scraper_service import ScraperService
        scraper = ScraperService()
        domains_to_scrape = []
        for comp in companies[:10]:
            domain = comp.get("domain") or comp.get("primary_domain")
            if domain:
                domains_to_scrape.append(domain)

        raw_texts = await scraper.scrape_domains_fast(domains_to_scrape, timeout=10, max_concurrent=10)
        # Cap at 2000 chars per site for evaluation (enough to understand what they do)
        website_texts = {d: t[:2000] for d, t in raw_texts.items()}
        credits_spent["websites_scraped"] = len(website_texts)

        logger.info(f"Probe attempt {attempt}: scraped {len(website_texts)}/{len(domains_to_scrape)} websites")

        # 2c. Evaluate with user's model using REAL website content
        evaluation = await _model_evaluate_probe(query, companies[:10], website_texts, eval_model)

        probe_history.append({
            "attempt": attempt,
            "filters": probe_filters,
            "companies_found": len(companies),
            "total_available": total_available,
            "websites_scraped": len(website_texts),
            "relevance_score": evaluation.get("relevance_score", 0),
            "verdict": evaluation.get("verdict", "unknown"),
            "model_used": eval_model["provider"],
        })

        logger.info(
            f"Probe attempt {attempt}: {len(companies)} companies, "
            f"{len(website_texts)} scraped, "
            f"relevance={evaluation.get('relevance_score', 0):.0%}, "
            f"verdict={evaluation.get('verdict')}"
        )

        # Good enough? Stop probing.
        if evaluation.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE:
            break

        # Bad quality — ask model to adjust filters based on website content
        if attempt < MAX_PROBE_RETRIES:
            feedback = evaluation.get("feedback", "Companies don't match the query")
            adjusted = await _model_adjust_filters(
                query, probe_filters, companies[:5], feedback, eval_model,
                website_texts=website_texts,
            )
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

    # Step 5: Enrich TOP 5 companies for REAL Apollo keyword taxonomy
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

    # Step 5b: Extract from search results too
    taxonomy = _extract_taxonomy(companies)
    taxonomy["keywords"] += enriched_keywords
    taxonomy["industries"] += enriched_industries

    # Step 6: Build refined filters
    refined = _build_refined_filters({"filters": final_filters}, taxonomy, target_count)

    per_page = 100
    companies_needed = int(target_count / 0.3)
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
        "credits_spent": {**credits_spent, "total_apollo": total_credits},
        "estimated": {
            "target_count": target_count,
            "pages_needed": pages_needed,
            "credits_for_gathering": pages_needed,
            "total_companies": min(total_available, pages_needed * per_page),
        },
        "message": (
            f"Probe found {len(companies)} companies ({total_available} total) "
            f"in {len(probe_history)} attempt(s), evaluated by {eval_model['provider']}. "
            f"Discovery cost: {total_credits} Apollo credits. "
            f"To gather ~{target_count} targets: {pages_needed} page(s) = {pages_needed} credit(s)."
        ),
    }


# ── Model abstraction ──────────────────────────────────────────────

def _pick_eval_model(anthropic_key: Optional[str], gemini_key: Optional[str], openai_key: Optional[str]) -> Dict[str, str]:
    """Pick the best available model for evaluation. Prefer Opus > Gemini > GPT."""
    if anthropic_key:
        return {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "key": anthropic_key}
    if gemini_key:
        return {"provider": "gemini", "model": "gemini-2.5-pro", "key": gemini_key}
    if openai_key:
        return {"provider": "openai", "model": "gpt-4o-mini", "key": openai_key}
    # Fallback to system keys
    from app.config import settings
    if settings.ANTHROPIC_API_KEY:
        return {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "key": settings.ANTHROPIC_API_KEY}
    if settings.GEMINI_API_KEY:
        return {"provider": "gemini", "model": "gemini-2.5-pro", "key": settings.GEMINI_API_KEY}
    if settings.OPENAI_API_KEY:
        return {"provider": "openai", "model": "gpt-4o-mini", "key": settings.OPENAI_API_KEY}
    return {"provider": "none", "model": "none", "key": ""}


async def _call_llm(model_info: Dict[str, str], system: str, user_msg: str, max_tokens: int = 500) -> Optional[str]:
    """Call any supported LLM provider. Returns raw text response."""
    provider = model_info["provider"]
    key = model_info["key"]
    model = model_info["model"]

    if not key or provider == "none":
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if provider == "openai":
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ], "max_tokens": max_tokens, "temperature": 0.2},
                )
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")

            elif provider == "anthropic":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={"model": model, "max_tokens": max_tokens, "system": system,
                          "messages": [{"role": "user", "content": user_msg}]},
                )
                data = resp.json()
                content = data.get("content", [])
                return content[0].get("text", "") if content else ""

            elif provider == "gemini":
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": f"{system}\n\n{user_msg}"}]}],
                          "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}},
                )
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return parts[0].get("text", "") if parts else ""
                return ""

    except Exception as e:
        logger.error(f"LLM call to {provider}/{model} failed: {e}")
        return None


def _parse_json_response(text: Optional[str]) -> Optional[Dict]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not text:
        return None
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM JSON: {clean[:200]}")
        return None


# ── Probe evaluation (uses REAL website content) ──────────────────

async def _model_evaluate_probe(
    query: str, companies: List[Dict], website_texts: Dict[str, str], model_info: Dict[str, str],
) -> Dict[str, Any]:
    """Evaluate probe quality using scraped website content + user's model."""

    if model_info["provider"] == "none":
        return {"relevance_score": 0.7, "verdict": "no_model", "feedback": ""}

    # Build company descriptions from REAL website content
    company_lines = []
    for c in companies[:10]:
        name = c.get("name", "?")
        domain = c.get("domain") or c.get("primary_domain", "?")
        industry = c.get("industry", "?")

        # Use scraped website text if available — this is the key difference
        site_text = website_texts.get(domain, "")
        if site_text:
            # First 500 chars of website = what the company actually does
            snippet = site_text[:500].replace("\n", " ")
            company_lines.append(f"**{name}** ({domain})\nIndustry: {industry}\nWebsite content: {snippet}")
        else:
            company_lines.append(f"**{name}** ({domain})\nIndustry: {industry}\n(website not scraped)")

    companies_text = "\n\n".join(company_lines)

    system = """You evaluate Apollo search results quality by reading REAL website content.
Given the user's search query and scraped company websites, judge relevance.

Return ONLY valid JSON:
{
  "relevance_score": 0.0-1.0,
  "verdict": "good" | "mediocre" | "bad",
  "relevant_count": N,
  "irrelevant_examples": ["company X does Y, not matching query"],
  "feedback": "specific suggestion to improve Apollo keyword filters"
}

Scoring based on website content (NOT just company name):
- 0.8-1.0 = most companies clearly match the search intent based on their website
- 0.5-0.7 = mixed — some match, some are clearly wrong industry
- 0.0-0.4 = most companies are irrelevant based on what their websites say"""

    user_msg = f"Search query: \"{query}\"\n\nCompanies found (with website content):\n\n{companies_text}"

    raw = await _call_llm(model_info, system, user_msg, max_tokens=500)
    result = _parse_json_response(raw)

    if result and "relevance_score" in result:
        return result

    return {"relevance_score": 0.5, "verdict": "parse_failed", "feedback": raw or ""}


async def _model_adjust_filters(
    query: str, current_filters: Dict, companies: List[Dict],
    feedback: str, model_info: Dict[str, str],
    website_texts: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """Model adjusts Apollo filters based on feedback + website evidence."""

    if model_info["provider"] == "none":
        return None

    company_summary = ""
    if companies:
        lines = []
        for c in companies[:5]:
            name = c.get("name", "?")
            domain = c.get("domain") or c.get("primary_domain", "?")
            site = ""
            if website_texts and domain in website_texts:
                site = f" — site says: {website_texts[domain][:200]}"
            lines.append(f"- {name} ({domain}){site}")
        company_summary = f"\n\nCompanies that came back (wrong):\n" + "\n".join(lines)

    current_kw = current_filters.get("q_organization_keyword_tags", [])
    current_loc = current_filters.get("organization_locations", [])
    current_size = current_filters.get("organization_num_employees_ranges", [])

    system = """You fix Apollo.io search filters that returned wrong results.
Given the original query, current filters, and REAL evidence from company websites about what went wrong, generate BETTER filters.

Return ONLY valid JSON:
{
  "filters": {
    "organization_locations": ["City, Country" or "Country"],
    "q_organization_keyword_tags": ["keyword1", "keyword2", ...],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,200"]
  }
}

Strategies:
- If results were too broad: use more specific/niche keywords
- If results were empty: use broader/synonym keywords
- If wrong industry: change keyword tags entirely based on what the CORRECT companies would have
- Keep 3-7 keyword tags"""

    user_msg = (
        f"Original query: {query}\n"
        f"Current keywords: {current_kw}\n"
        f"Current locations: {current_loc}\n"
        f"Current sizes: {current_size}\n"
        f"Problem: {feedback}"
        f"{company_summary}"
    )

    raw = await _call_llm(model_info, system, user_msg, max_tokens=400)
    return _parse_json_response(raw)


# ── Initial filter generation (cheap, gpt-4o-mini is fine) ────────

async def _llm_generate_candidates(query: str, openai_key: Optional[str] = None) -> Optional[Dict]:
    """Use GPT-4o-mini to generate initial Apollo filter candidates from natural language.
    This is the cheap step — just keyword extraction, no quality judgment."""
    if not openai_key:
        from app.config import settings
        openai_key = settings.OPENAI_API_KEY
    if not openai_key:
        return _basic_parse(query)

    model_info = {"provider": "openai", "model": "gpt-4o-mini", "key": openai_key}
    system = """You translate natural language business queries into Apollo.io search filters.
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
- Include synonyms and related terms
- Location should include country if city is given
- Employee ranges should cover the likely range for the segment
- Generate 3-7 keyword tags for best results"""

    raw = await _call_llm(model_info, system, f"Generate Apollo search filters for: {query}", max_tokens=300)
    result = _parse_json_response(raw)
    return result if result else _basic_parse(query)


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


# ── Taxonomy extraction ──────────────────────────────────────────

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
