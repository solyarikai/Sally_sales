"""Exploration Service — optimizes Apollo filters by reverse-engineering from target companies.

The exploration phase:
1. Initial Apollo search with user's filters → ~25-100 companies
2. Scrape top 10-15 company websites (free via Apify)
3. GPT-4o-mini classifies: pick top 5 definite targets
4. Apollo enrichment on those 5 (5 credits) → get ALL their Apollo labels
5. Extract common industry, keywords, SIC/NAICS from the 5 targets
6. Build optimized filter set → higher target conversion rate in full pipeline

Max cost: 5 Apollo enrichment credits + 1 search credit = 6 credits total.
"""
import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def run_exploration(
    query: str,
    initial_filters: Dict[str, Any],
    offer_text: str,
    apollo_key: str,
    openai_key: str,
    apify_proxy_password: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the exploration phase to optimize Apollo filters.

    Returns optimized filters + exploration stats.
    """
    result = {
        "initial_filters": initial_filters,
        "optimized_filters": None,
        "exploration_stats": {},
        "credits_used": 0,
    }

    # Step 1: Initial Apollo search (1 credit)
    logger.info("Exploration step 1: Initial Apollo search")
    companies = await _apollo_search(apollo_key, initial_filters, per_page=25)
    result["exploration_stats"]["initial_companies"] = len(companies)
    result["credits_used"] += 1

    if not companies:
        logger.warning("Exploration: no companies from initial search")
        result["optimized_filters"] = initial_filters
        return result

    # Step 2: Scrape top company websites (free)
    logger.info(f"Exploration step 2: Scraping {min(15, len(companies))} websites")
    scraped = await _scrape_websites(companies[:15], apify_proxy_password)
    result["exploration_stats"]["websites_scraped"] = len(scraped)

    # Step 3: GPT classifies — pick top 5 targets
    logger.info("Exploration step 3: GPT classifying targets")
    targets = await _classify_targets(scraped, query, offer_text, openai_key)
    result["exploration_stats"]["targets_identified"] = len(targets)

    if len(targets) < 2:
        logger.warning("Exploration: too few targets, using initial filters")
        result["optimized_filters"] = initial_filters
        return result

    # Step 4: Enrich top 5 targets via Apollo (5 credits max)
    top_5 = targets[:5]
    logger.info(f"Exploration step 4: Enriching {len(top_5)} targets")
    enriched = await _enrich_targets(apollo_key, top_5)
    result["credits_used"] += len(enriched)
    result["exploration_stats"]["enriched_targets"] = len(enriched)

    # Step 5: Extract common labels from enriched targets
    logger.info("Exploration step 5: Extracting common labels")
    common_labels = _extract_common_labels(enriched)
    result["exploration_stats"]["common_labels"] = common_labels

    # Step 6: Build optimized filters
    optimized = _build_optimized_filters(initial_filters, common_labels)
    result["optimized_filters"] = optimized
    result["exploration_stats"]["filters_added"] = {
        k: v for k, v in optimized.items() if k not in initial_filters or v != initial_filters.get(k)
    }

    logger.info(f"Exploration complete: {result['credits_used']} credits, "
                f"{len(targets)} targets, filters enhanced with {len(common_labels)} label groups")
    return result


async def _apollo_search(api_key: str, filters: Dict, per_page: int = 25) -> List[Dict]:
    """Single Apollo search call (1 credit)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            body = {
                "api_key": api_key,
                "per_page": per_page,
                "page": 1,
            }
            if filters.get("q_organization_keyword_tags"):
                body["q_organization_keyword_tags"] = filters["q_organization_keyword_tags"]
            if filters.get("organization_locations"):
                body["organization_locations"] = filters["organization_locations"]
            if filters.get("organization_num_employees_ranges"):
                body["organization_num_employees_ranges"] = filters["organization_num_employees_ranges"]

            resp = await client.post(
                "https://api.apollo.io/api/v1/mixed_companies/search",
                json=body,
            )
            data = resp.json()
            return data.get("organizations", data.get("accounts", []))
    except Exception as e:
        logger.error(f"Apollo search failed: {e}")
        return []


async def _scrape_websites(companies: List[Dict], apify_proxy: Optional[str]) -> List[Dict]:
    """Scrape company websites. Returns list of {domain, name, text, ...}."""
    results = []
    for company in companies:
        domain = company.get("primary_domain") or company.get("domain", "")
        if not domain:
            continue
        url = f"https://{domain}" if not domain.startswith("http") else domain
        try:
            headers = {}
            if apify_proxy:
                # Use Apify proxy for residential IP
                pass  # Proxy configured at httpx level

            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    text = resp.text[:5000]
                    # Strip HTML tags roughly
                    import re
                    clean = re.sub(r"<[^>]+>", " ", text)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    results.append({
                        **company,
                        "scraped_text": clean[:3000],
                    })
        except Exception:
            pass

    return results


async def _classify_targets(
    companies: List[Dict], query: str, offer_text: str, openai_key: str
) -> List[Dict]:
    """GPT-4o-mini classifies companies as target or not. Returns sorted targets."""
    if not companies or not openai_key:
        return []

    prompt = f"""Classify these companies as TARGET or NOT for this query:
Query: "{query}"
Our offer: {offer_text[:500]}

For each company, respond with JSON array:
[{{"domain": "...", "is_target": true/false, "confidence": 0.0-1.0, "reasoning": "..."}}]

Companies:
"""
    for c in companies:
        prompt += f"- {c.get('name', c.get('domain', '?'))}: {c.get('domain', '?')} — {c.get('scraped_text', '')[:200]}\n"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            classifications = json.loads(clean)

            # Match back to companies and filter targets
            targets = []
            domain_map = {c.get("domain", c.get("primary_domain", "")): c for c in companies}
            for cls in classifications:
                if cls.get("is_target") and cls.get("confidence", 0) >= 0.6:
                    domain = cls.get("domain", "")
                    company = domain_map.get(domain, cls)
                    company["classification"] = cls
                    targets.append(company)

            targets.sort(key=lambda x: -x.get("classification", {}).get("confidence", 0))
            return targets

    except Exception as e:
        logger.error(f"Target classification failed: {e}")
        return []


async def _enrich_targets(api_key: str, targets: List[Dict]) -> List[Dict]:
    """Enrich top targets via Apollo to get all their labels. 1 credit each."""
    enriched = []
    for target in targets:
        domain = target.get("primary_domain") or target.get("domain", "")
        if not domain:
            continue
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.apollo.io/api/v1/organizations/enrich",
                    params={"api_key": api_key, "domain": domain},
                )
                data = resp.json()
                org = data.get("organization", {})
                if org:
                    enriched.append({**target, "enriched": org})
        except Exception as e:
            logger.warning(f"Enrichment failed for {domain}: {e}")

    return enriched


def _extract_common_labels(enriched: List[Dict]) -> Dict[str, List[str]]:
    """Extract common Apollo labels from enriched targets."""
    industries = Counter()
    keywords = Counter()
    sic_codes = Counter()

    for e in enriched:
        org = e.get("enriched", {})

        # Industry
        ind = org.get("industry") or org.get("organization_industry")
        if ind:
            industries[ind] += 1

        # Keywords
        kw_tags = org.get("keywords") or org.get("keyword_tags") or []
        if isinstance(kw_tags, str):
            kw_tags = [k.strip() for k in kw_tags.split(",")]
        for kw in kw_tags[:20]:
            if kw and len(kw) > 2:
                keywords[kw.lower()] += 1

        # SIC codes
        sic = org.get("sic_codes") or []
        for code in sic:
            sic_codes[str(code)] += 1

    # Return ALL labels from targets — broader = more companies in Apollo
    # Industries: include all (these are the big multipliers)
    # Keywords: include top 15 by frequency (covers all enriched targets)
    return {
        "industries": [k for k, v in industries.most_common(10)],
        "keywords": [k for k, v in keywords.most_common(15)],
        "sic_codes": [k for k, v in sic_codes.most_common(5)],
    }


async def _build_optimized_filters(initial: Dict, common_labels: Dict, query: str, openai_key: str) -> Dict:
    """Filter optimization via negativa: only add keywords RELEVANT to the user's segment.

    Enriched companies have dozens of keywords (tech stacks, tools, products) — most are
    NOISE for search filters. GPT-4o-mini filters them: keep only segment-relevant ones,
    exclude specific technologies, product names, frameworks.
    """
    optimized = dict(initial)
    existing_kw = set(k.lower() for k in optimized.get("q_organization_keyword_tags", []))

    # Collect ALL candidate keywords from enrichment
    all_candidates = []
    for ind in common_labels.get("industries", []):
        if ind.lower() not in existing_kw:
            all_candidates.append(ind)
    for kw in common_labels.get("keywords", []):
        if kw.lower() not in existing_kw:
            all_candidates.append(kw)

    if not all_candidates or not openai_key:
        return optimized

    # GPT-4o-mini filters: only keep keywords that would find MORE companies matching the segment
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": f"""User is searching for: "{query}"
Current Apollo keywords: {list(existing_kw)}

These keywords were found on target companies' Apollo profiles:
{all_candidates}

Which of these keywords would HELP find MORE companies matching "{query}"?

KEEP: industry-level terms, business model descriptors, service categories
EXCLUDE: specific tech stacks (react, python, nodejs), product names, frameworks, tools, programming languages

Return ONLY a JSON array of keywords to ADD (max 8):
["keyword1", "keyword2", ...]"""}],
                    "max_tokens": 200,
                    "temperature": 0,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            import json as _json
            filtered_kw = _json.loads(content)

            if filtered_kw:
                optimized["q_organization_keyword_tags"] = list(optimized.get("q_organization_keyword_tags", [])) + filtered_kw[:8]
                logger.info(f"Optimized filters: added {filtered_kw[:8]} (from {len(all_candidates)} candidates)")

    except Exception as e:
        logger.warning(f"Keyword filtering failed: {e}")
        # Fallback: add just industry names (safest)
        industry_kw = [ind for ind in common_labels.get("industries", []) if ind.lower() not in existing_kw]
        if industry_kw:
            optimized["q_organization_keyword_tags"] = list(optimized.get("q_organization_keyword_tags", [])) + industry_kw[:5]

    return optimized
