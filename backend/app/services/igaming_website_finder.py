"""
iGaming Website Finder — Yandex Search + Gemini AI.

Finds websites for companies without domains:
1. Search Yandex for "{company_name} official site igaming"
2. Extract candidate domains from results
3. Gemini Flash picks the correct domain
4. Update company + contacts
"""
import asyncio
import base64
import json
import logging
import random
import re
from typing import Optional

import httpx
from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.igaming import IGamingCompany, IGamingContact

logger = logging.getLogger(__name__)

_progress: dict[str, dict] = {}


def get_progress(task_id: str) -> dict:
    return _progress.get(task_id, {"processed": 0, "total": 0, "found": 0, "status": "idle"})


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
]


def _extract_domains_from_html(html: str) -> list[str]:
    """Extract unique domains from Yandex search result HTML."""
    domains = []
    seen = set()
    # Match href URLs
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        url = m.group(1)
        # Extract domain
        dm = re.match(r'https?://(?:www\.)?([^/]+)', url)
        if dm:
            domain = dm.group(1).lower().rstrip(".")
            # Skip Yandex/Google/cache domains
            skip = ("yandex.", "google.", "cache.", "webcache.", "translate.")
            if not any(domain.startswith(s) or s in domain for s in skip) and domain not in seen:
                seen.add(domain)
                domains.append(domain)
    return domains[:15]  # Top 15 candidates


async def _yandex_search(query: str) -> list[str]:
    """Search Yandex and return candidate domains."""
    if not settings.YANDEX_SEARCH_API_KEY or not settings.YANDEX_SEARCH_FOLDER_ID:
        logger.warning("Yandex Search not configured")
        return []

    headers = {
        "Authorization": f"Api-Key {settings.YANDEX_SEARCH_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "page": 0,
        },
        "folderId": settings.YANDEX_SEARCH_FOLDER_ID,
        "responseFormat": "FORMAT_HTML",
        "userAgent": random.choice(USER_AGENTS),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Submit search
            resp = await client.post(settings.YANDEX_SEARCH_API_URL, json=body, headers=headers)
            if resp.status_code == 429:
                logger.warning("Yandex 429 rate limit")
                await asyncio.sleep(3)
                return []
            resp.raise_for_status()
            data = resp.json()

            operation_id = data.get("id")
            if not operation_id:
                return []

            # Step 2: Poll for results
            ops_url = f"{settings.YANDEX_OPERATIONS_URL}/{operation_id}"
            for _ in range(20):  # Max 20 polls × 1.5s = 30s
                await asyncio.sleep(1.5)
                poll_resp = await client.get(ops_url, headers=headers)
                if poll_resp.status_code == 429:
                    await asyncio.sleep(3)
                    continue
                poll_data = poll_resp.json()
                if poll_data.get("done"):
                    # Extract HTML from response
                    response_data = poll_data.get("response", {})
                    raw_html = response_data.get("rawData")
                    if raw_html:
                        html = base64.b64decode(raw_html).decode("utf-8", errors="replace")
                        return _extract_domains_from_html(html)
                    return []

    except Exception as e:
        logger.error(f"Yandex search failed for '{query}': {e}")

    return []


async def _gemini_pick_domain(company_name: str, candidates: list[str]) -> Optional[str]:
    """Use Gemini Flash to pick the correct website from candidates."""
    if not candidates:
        return None

    from app.services.gemini_client import gemini_generate

    prompt = f"""Company name: "{company_name}"
Industry: iGaming / online gambling

Candidate domains found via search:
{chr(10).join(f"- {d}" for d in candidates)}

Which domain is the official website of this company?
Rules:
- Pick the domain that best matches the company name
- Prefer .com, .io, .net over country-specific TLDs
- If none of the candidates match, respond with "NONE"
- Respond with ONLY the domain (e.g. "betsson.com") or "NONE", nothing else"""

    try:
        result = await gemini_generate(
            system_prompt="You pick the correct company website domain from a list. Respond with ONLY the domain or NONE. No explanation.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=200,
            model="gemini-2.5-flash",
            thinking_budget=0,
        )
        answer = (result.get("content") or "").strip().lower()
        # Clean up response
        answer = answer.strip('"\'` \n')
        if answer and answer != "none" and "." in answer:
            # Remove protocol if present
            for prefix in ("https://www.", "http://www.", "https://", "http://", "www."):
                if answer.startswith(prefix):
                    answer = answer[len(prefix):]
            return answer.rstrip("/")
    except Exception as e:
        logger.error(f"Gemini domain pick failed for '{company_name}': {e}")

    return None


async def find_websites(
    session: AsyncSession,
    company_ids: Optional[list[int]] = None,
    limit: int = 100,
    task_id: str = "default",
) -> dict:
    """
    Find websites for companies without domains.
    Uses Yandex Search + Gemini Flash.

    Args:
        company_ids: Specific company IDs to process (None = all without website)
        limit: Max companies to process
        task_id: For progress tracking
    """
    # Load companies without website, skip garbage names
    skip_names = {"nda", "-", "n/a", "na", "none", "null", "test", "unknown", ".", ".."}
    query = select(IGamingCompany).where(
        and_(
            IGamingCompany.website.is_(None),
            IGamingCompany.name.isnot(None),
            func.length(IGamingCompany.name) > 2,  # Skip 1-2 char names
        )
    )
    if company_ids:
        query = query.where(IGamingCompany.id.in_(company_ids))
    query = query.order_by(IGamingCompany.contacts_count.desc()).limit(limit)

    companies = (await session.execute(query)).scalars().all()
    total = len(companies)

    _progress[task_id] = {"processed": 0, "total": total, "found": 0, "status": "running"}

    processed = 0
    found = 0
    results = []

    for company in companies:
        try:
            # Skip garbage names
            if not company.name or company.name.strip().lower() in skip_names:
                processed += 1
                continue

            # Search Yandex
            search_query = f'"{company.name}" official website'
            candidates = await _yandex_search(search_query)

            domain = None
            if candidates:
                # If only 1 candidate and it looks like a match, use it directly
                if len(candidates) == 1:
                    domain = candidates[0]
                else:
                    # Use Gemini to pick the right one
                    domain = await _gemini_pick_domain(company.name, candidates)

            if domain:
                company.website = domain
                # Update contacts too
                await session.execute(
                    update(IGamingContact)
                    .where(
                        and_(
                            IGamingContact.company_id == company.id,
                            IGamingContact.website_url.is_(None),
                        )
                    )
                    .values(website_url=domain)
                )
                found += 1
                results.append({"company": company.name, "domain": domain})

            processed += 1
            _progress[task_id].update({"processed": processed, "found": found})

            if processed % 10 == 0:
                await session.flush()
                logger.info(f"Website finder: {processed}/{total}, found {found}")

            # Rate limit: ~1 req/sec for Yandex
            await asyncio.sleep(1.0)

        except Exception as e:
            processed += 1
            logger.warning(f"Website finder error for '{company.name}': {e}")

    await session.flush()
    _progress[task_id] = {"processed": processed, "total": total, "found": found, "status": "completed"}

    logger.info(f"Website finder done: {found}/{total} websites found")
    return {
        "processed": processed,
        "total": total,
        "found": found,
        "results": results[:50],  # Return first 50 for display
    }
