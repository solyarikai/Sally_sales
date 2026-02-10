"""
Data Search Service — Yandex-powered company discovery pipeline.

Replaces Apollo: instead of querying a proprietary database,
generates search queries via OpenAI, runs them on Yandex Search API,
and optionally verifies results by scraping websites via Crona + OpenAI.

Pipeline:
1. User describes target segment ("family offices in Dubai accepting crypto")
2. OpenAI generates search queries shown to user for transparency
3. Yandex Search finds domains matching those queries
4. OpenAI generates a filtering/qualification prompt
5. Crona scrapes website text
6. OpenAI applies the prompt → qualified / not qualified
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from app.core.config import settings
from app.services.openai_service import openai_service
from app.services.search_service import search_service
from app.services.crona_service import crona_service
from app.services.usage_logger import usage_logger

logger = logging.getLogger(__name__)


class DataSearchService:
    """Orchestrates segment-based search using Yandex + OpenAI + Crona."""

    # ------------------------------------------------------------------
    # Step 1: Generate search queries from user's segment description
    # ------------------------------------------------------------------

    async def generate_search_queries(
        self,
        segment_description: str,
        count: int = 10,
    ) -> Dict[str, Any]:
        """
        Turn a natural-language segment description into concrete
        search queries for Yandex.  Returns the queries AND the
        filtering prompt so the user can see exactly what's happening.
        """
        system_prompt = (
            "You are an expert at lead-generation search queries. "
            "Given a target business segment description, generate search queries "
            "that would help find company websites matching that segment on a search engine. "
            "Also create a short qualification prompt that can be used to check "
            "if a scraped website text actually belongs to the target segment.\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            '{\n'
            '  "queries": ["query 1", "query 2", ...],\n'
            '  "qualification_prompt": "Based on the website text, determine if this company is a ...",\n'
            '  "segment_summary": "One-line description of what we are looking for"\n'
            '}'
        )

        user_prompt = (
            f"Target segment: \"{segment_description}\"\n\n"
            f"Generate exactly {count} diverse search queries (mix English/Russian if "
            f"relevant to the geography). Focus on queries that will find COMPANY "
            f"WEBSITES, not news articles or directories.\n\n"
            f"Also create a qualification_prompt that can evaluate scraped website "
            f"text to determine if the company matches the target segment."
        )

        try:
            result = await openai_service.enrich_single_row(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model="gpt-4o-mini",
            )
            raw = result["result"].strip() if result["success"] else ""
            tokens_used = result.get("tokens_used", 0)
            usage_logger.log_openai_request(
                operation=f"generate_queries: {segment_description[:50]}",
                model="gpt-4o-mini",
                tokens_used=tokens_used,
            )
            if not result["success"]:
                raise Exception(result.get("error", "OpenAI call failed"))
            if raw.startswith("```"):
                raw = re.sub(r"^```json?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            data = json.loads(raw)

            queries = [str(q).strip() for q in data.get("queries", []) if q]
            qualification_prompt = data.get("qualification_prompt", "")
            segment_summary = data.get("segment_summary", segment_description)

            logger.info(
                f"Generated {len(queries)} queries for segment: {segment_description}"
            )
            return {
                "queries": queries,
                "qualification_prompt": qualification_prompt,
                "segment_summary": segment_summary,
            }

        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            # Fallback: use the description directly as a query
            return {
                "queries": [segment_description],
                "qualification_prompt": (
                    f"Determine if the company matches: {segment_description}"
                ),
                "segment_summary": segment_description,
            }

    # ------------------------------------------------------------------
    # Step 2: Run Yandex search with the generated queries
    # ------------------------------------------------------------------

    async def search_yandex(
        self,
        queries: List[str],
        max_pages: int = 10,
        max_concurrent: int = 2,
    ) -> Dict[str, Any]:
        """
        Run queries on Yandex and collect unique domains.
        Returns domains grouped by which query found them.
        """
        if not settings.YANDEX_SEARCH_API_KEY:
            raise ValueError("YANDEX_SEARCH_API_KEY not configured")
        if not settings.YANDEX_SEARCH_FOLDER_ID:
            raise ValueError("YANDEX_SEARCH_FOLDER_ID not configured")

        all_domains: Set[str] = set()
        query_results: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_query(query: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    domains = await search_service._yandex_search_single_query(
                        query, max_pages
                    )
                    new = domains - all_domains
                    all_domains.update(domains)
                    usage_logger.log_yandex_request(
                        query=query,
                        pages_scanned=max_pages,
                        domains_found=len(domains),
                        status="ok",
                    )
                    return {
                        "query": query,
                        "domains_found": len(domains),
                        "new_domains": len(new),
                        "domains": list(domains),
                        "status": "done",
                    }
                except Exception as e:
                    logger.error(f"Yandex search failed for '{query}': {e}")
                    usage_logger.log_yandex_request(
                        query=query,
                        pages_scanned=0,
                        domains_found=0,
                        status=f"failed: {str(e)[:50]}",
                    )
                    return {
                        "query": query,
                        "domains_found": 0,
                        "new_domains": 0,
                        "domains": [],
                        "status": "failed",
                        "error": str(e),
                    }

        tasks = [_run_query(q) for q in queries]
        results = await asyncio.gather(*tasks)
        query_results = list(results)

        logger.info(
            f"Yandex search complete: {len(all_domains)} unique domains from "
            f"{len(queries)} queries"
        )
        return {
            "total_domains": len(all_domains),
            "domains": sorted(all_domains),
            "query_results": query_results,
        }

    # ------------------------------------------------------------------
    # Step 3: Qualify domains via Crona scraping + OpenAI
    # ------------------------------------------------------------------

    async def qualify_domains(
        self,
        domains: List[str],
        qualification_prompt: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Scrape websites via Crona and apply the qualification prompt
        using OpenAI.  Returns qualified / not-qualified results.
        """
        domains_to_check = domains[:limit]

        # 3a. Scrape via Crona
        websites = [f"https://{d}" for d in domains_to_check]

        scraped_content: Dict[str, str] = {}
        if crona_service.is_configured():
            try:
                result = await crona_service.scrape_websites_and_wait(
                    websites=websites,
                    project_name="Segment Qualification",
                    timeout_seconds=300,
                )
                scraped_content = crona_service.parse_results_to_dict(
                    result.get("results", {}), websites
                )
                logger.info(f"Crona scraped {len(scraped_content)} websites")
            except Exception as e:
                logger.error(f"Crona scraping failed: {e}")
        else:
            logger.warning("Crona not configured — skipping website scraping")

        # 3b. Apply qualification prompt via OpenAI
        qualified: List[Dict[str, Any]] = []
        not_qualified: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        semaphore = asyncio.Semaphore(5)

        async def _qualify_one(domain: str) -> Dict[str, Any]:
            async with semaphore:
                content = scraped_content.get(domain, "")
                if not content:
                    return {
                        "domain": domain,
                        "qualified": None,
                        "reason": "No website content scraped",
                        "confidence": 0,
                    }

                truncated = content[:3000]
                prompt = (
                    f"{qualification_prompt}\n\n"
                    f"Website domain: {domain}\n"
                    f"Website content:\n{truncated}\n\n"
                    f"Return ONLY valid JSON:\n"
                    f'{{"qualified": true/false, "confidence": 0.0-1.0, '
                    f'"reason": "brief explanation", '
                    f'"company_name": "detected name or null", '
                    f'"company_description": "one sentence about what they do"}}'
                )

                try:
                    openai_result = await openai_service.enrich_single_row(
                        prompt=prompt,
                        system_prompt=(
                            "You are a company qualification analyst. "
                            "Analyze website content and determine if the company "
                            "matches the given criteria. Be precise."
                        ),
                        model="gpt-4o-mini",
                    )
                    tokens_used = openai_result.get("tokens_used", 0)
                    usage_logger.log_openai_request(
                        operation=f"qualify: {domain}",
                        model="gpt-4o-mini",
                        tokens_used=tokens_used,
                    )
                    if not openai_result["success"]:
                        raise Exception(openai_result.get("error", "OpenAI call failed"))
                    raw = openai_result["result"].strip()
                    if raw.startswith("```"):
                        raw = re.sub(r"^```json?\n?", "", raw)
                        raw = re.sub(r"\n?```$", "", raw)
                    result = json.loads(raw)
                    result["domain"] = domain
                    return result
                except Exception as e:
                    return {
                        "domain": domain,
                        "qualified": None,
                        "reason": f"Qualification error: {e}",
                        "confidence": 0,
                    }

        tasks = [_qualify_one(d) for d in domains_to_check]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r.get("qualified") is True:
                qualified.append(r)
            elif r.get("qualified") is False:
                not_qualified.append(r)
            else:
                errors.append(r)

        # Sort qualified by confidence descending
        qualified.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        return {
            "qualified": qualified,
            "not_qualified": not_qualified,
            "errors": errors,
            "total_checked": len(domains_to_check),
            "total_qualified": len(qualified),
            "total_not_qualified": len(not_qualified),
            "total_errors": len(errors),
        }

    # ------------------------------------------------------------------
    # Full pipeline: segment → queries → Yandex → qualify
    # ------------------------------------------------------------------

    async def search_segment(
        self,
        segment_description: str,
        query_count: int = 10,
        max_pages: int = 10,
        qualify: bool = False,
        qualify_limit: int = 50,
    ) -> Dict[str, Any]:
        """
        End-to-end pipeline:
        1. Generate queries from segment description
        2. Run Yandex search
        3. Optionally qualify via Crona + OpenAI
        """
        # Step 1
        gen_result = await self.generate_search_queries(
            segment_description, count=query_count
        )
        queries = gen_result["queries"]
        qualification_prompt = gen_result["qualification_prompt"]
        segment_summary = gen_result["segment_summary"]

        # Step 2
        search_result = await self.search_yandex(
            queries, max_pages=max_pages
        )
        domains = search_result["domains"]

        # Step 3 (optional)
        qualification = None
        if qualify and domains:
            qualification = await self.qualify_domains(
                domains, qualification_prompt, limit=qualify_limit
            )

        # Log session summary after full pipeline
        usage_logger.log_session_summary()

        return {
            "segment_description": segment_description,
            "segment_summary": segment_summary,
            "generated_queries": queries,
            "qualification_prompt": qualification_prompt,
            "search_results": {
                "total_domains": search_result["total_domains"],
                "domains": domains,
                "query_details": search_result["query_results"],
            },
            "qualification": qualification,
        }

    # ------------------------------------------------------------------
    # Chat-style interface (for the frontend)
    # ------------------------------------------------------------------

    async def chat_search(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Chat interface: user describes what they want,
        system generates queries, searches, and returns results
        with the queries visible for transparency.
        """
        # Generate queries + qualification prompt
        gen_result = await self.generate_search_queries(message, count=10)
        queries = gen_result["queries"]
        qualification_prompt = gen_result["qualification_prompt"]
        segment_summary = gen_result["segment_summary"]

        # Run Yandex search
        search_result = await self.search_yandex(queries, max_pages=10)
        domains = search_result["domains"]

        # Format company results from domains
        companies = [
            {
                "id": str(i + 1),
                "name": d.split(".")[0].replace("-", " ").title(),
                "domain": d,
                "verified": None,
            }
            for i, d in enumerate(domains[:100])
        ]

        # Generate conversational response
        response_text = (
            f"I found **{len(domains)}** company websites for: *{segment_summary}*\n\n"
            f"**Generated {len(queries)} search queries:**\n"
        )
        for i, q in enumerate(queries, 1):
            response_text += f"{i}. {q}\n"

        if domains:
            response_text += (
                f"\nTop domains found: {', '.join(domains[:10])}"
            )
            if len(domains) > 10:
                response_text += f" ... and {len(domains) - 10} more"
            response_text += (
                "\n\nClick **Verify** to scrape these websites and check "
                "if they truly match your target segment."
            )
        else:
            response_text += "\nNo domains found. Try broadening your search criteria."

        # Log session summary after chat search
        usage_logger.log_session_summary()

        return {
            "response": response_text,
            "queries_generated": queries,
            "qualification_prompt": qualification_prompt,
            "segment_summary": segment_summary,
            "companies": companies,
            "total": len(companies),
        }


data_search_service = DataSearchService()
