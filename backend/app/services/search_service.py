"""
Search Service — Query generation (OpenAI) + Google SERP + Yandex Search API.

Supports two search engines:
- google_serp: HTTP scraping via Apify SERP proxy
- yandex_api: Yandex Cloud Search API (async/deferred, $0.25 per 1k requests)

Key difference from origin/fim: generate_queries is project-aware.
Instead of hardcoded ICP_MASTER_PROMPT_V4, it loads target_segments from
the project and builds a dynamic prompt.
"""
import asyncio
import base64
import json
import random
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchQueryStatus,
    DomainSource,
)
from app.services.domain_service import domain_service, normalize_domain, matches_trash_pattern

logger = logging.getLogger(__name__)


# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# =============================================================================
# PROJECT-AWARE QUERY GENERATION
# =============================================================================

def build_project_query_prompt(
    target_segments: str,
    count: int,
    existing_queries: List[str],
    good_queries: Optional[List[str]] = None,
    bad_queries: Optional[List[str]] = None,
    confirmed_targets: Optional[List[str]] = None,
) -> str:
    """
    Build a GPT prompt for generating search queries based on project's target_segments.
    This replaces the hardcoded ICP_MASTER_PROMPT_V4 from origin/fim.
    """
    # Sample existing queries for dedup context
    sample_k = 30
    existing_sample: List[str] = []
    seen_count = 0
    for q in (existing_queries or []):
        q = (q or "").strip()
        if not q:
            continue
        seen_count += 1
        if len(existing_sample) < sample_k:
            existing_sample.append(q)
        else:
            j = random.randint(1, seen_count)
            if j <= sample_k:
                existing_sample[j - 1] = q

    existing_str = "\n".join(f"  - {q}" for q in existing_sample) if existing_sample else "(none)"

    # Build feedback section from past job effectiveness (Phase 3d)
    feedback_section = ""
    if good_queries:
        good_str = "\n".join(f"  - {q}" for q in good_queries[:20])
        feedback_section += f"\nЭФФЕКТИВНЫЕ ЗАПРОСЫ (находили целевые компании — генерируй похожие):\n{good_str}\n"
    if bad_queries:
        bad_str = "\n".join(f"  - {q}" for q in bad_queries[:20])
        feedback_section += f"\nНЕЭФФЕКТИВНЫЕ ЗАПРОСЫ (находили только мусор — НЕ генерируй похожие):\n{bad_str}\n"
    if confirmed_targets:
        targets_str = "\n".join(f"  - {d}" for d in confirmed_targets[:30])
        feedback_section += f"\nПОДТВЕРЖДЁННЫЕ ЦЕЛЕВЫЕ ДОМЕНЫ (генерируй запросы, которые нашли бы похожие):\n{targets_str}\n"

    prompt = f"""Ты - эксперт по генерации поисковых запросов для B2B лидогенерации.

ЦЕЛЕВОЙ СЕГМЕНТ: {target_segments}

ЗАДАЧА: Сгенерируй поисковые запросы для поиска компаний в этом сегменте через Яндекс и Google.

ПРАВИЛА:
- Каждый запрос 3-8 слов
- Естественный язык как в Яндексе/Google
- 85% на русском, 15% на английском
- Разнообразие: названия компаний, услуги, города, подсегменты
- НЕ генерируй информационные запросы ("что такое...", "как работает...")
- НЕ генерируй buyer intent ("купить...", "цены на...")
- НЕ генерируй вакансии ("работа в...", "вакансии...")
- Ищем B2B партнёров и компании, НЕ конечных потребителей

ВАРИАЦИИ ЗАПРОСОВ:
- Прямые: "[тип компании] [город]"
- Уточнённые: "[тип компании] для [целевой аудитории]"
- Географические: варьируй города России (Москва, СПб, Екатеринбург, Новосибирск, Казань, Нижний Новгород, Ростов, Краснодар, и другие крупные города)
- Английские: для поиска российских компаний на английском
- СТРОГО следуй географическим ограничениям в описании целевого сегмента

УЖЕ ИСПОЛЬЗОВАННЫЕ ЗАПРОСЫ (НЕ ПОВТОРЯЙ!):
{existing_str}
{feedback_section}
Сгенерируй ровно {count} уникальных запросов. Верни ТОЛЬКО JSON массив: ["запрос1", "запрос2", ...]"""

    return prompt


def _normalize_query(q: str) -> str:
    return " ".join((q or "").strip().lower().split())


def _extract_json_array(text: str) -> List[str]:
    """Extract JSON array from OpenAI response text."""
    if not text:
        return []

    try:
        raw = json.loads(text)
        if isinstance(raw, list):
            return [str(x) for x in raw if x]
    except Exception:
        pass

    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            raw = json.loads(text[start:end + 1])
            if isinstance(raw, list):
                return [str(x) for x in raw if x]
    except Exception:
        pass

    # Fallback: line by line
    queries = []
    for line in text.strip().split("\n"):
        line = line.strip()
        for prefix in ["-", "*", '"', "'"]:
            if line.startswith(prefix):
                line = line[1:].strip()
        if line.endswith('"') or line.endswith("'") or line.endswith(","):
            line = line[:-1].strip()
        if line and len(line) > 5 and not line.startswith("{") and not line.startswith("["):
            queries.append(line)
    return queries


# =============================================================================
# GOOGLE SERP HTML PARSING
# =============================================================================

def extract_domains_from_html(html: str) -> Set[str]:
    """Extract domains from Google/Yandex search results HTML."""
    domains = set()
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if any(x in href for x in [
            "google.com", "google.ru", "gstatic.com", "youtube.com",
            "webcache.", "/search?", "/url?q=http", "javascript:", "#",
        ]):
            if "/url?q=" in href:
                match = re.search(r"/url\?q=([^&]+)", href)
                if match:
                    href = match.group(1)
                else:
                    continue
            else:
                continue

        try:
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                domain = normalize_domain(parsed.netloc)
                if domain and not matches_trash_pattern(domain):
                    domains.add(domain)
        except Exception:
            continue

    # Method 2: cite elements
    for cite in soup.find_all("cite"):
        text = cite.get_text()
        match = re.search(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})", text)
        if match:
            domain = normalize_domain(match.group(1))
            if domain and not matches_trash_pattern(domain):
                domains.add(domain)

    return domains


def check_for_captcha(html: str) -> bool:
    """Check if response contains a CAPTCHA."""
    indicators = [
        "unusual traffic", "captcha", "recaptcha",
        "sorry/index", "detected unusual traffic",
        "automated queries", "please verify",
    ]
    html_lower = html.lower()
    return any(ind in html_lower for ind in indicators)


# =============================================================================
# SEARCH SERVICE
# =============================================================================

class SearchService:
    """Handles query generation and search engine scraping."""

    # ------------------------------------------------------------------
    # Query generation (project-aware)
    # ------------------------------------------------------------------

    async def generate_queries(
        self,
        session: AsyncSession,
        count: int = 50,
        model: Optional[str] = None,
        existing_queries: Optional[List[str]] = None,
        target_segments: Optional[str] = None,
        project_id: Optional[int] = None,
        good_queries: Optional[List[str]] = None,
        bad_queries: Optional[List[str]] = None,
        confirmed_targets: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Generate search queries via OpenAI.
        Uses project's target_segments to build the prompt dynamically.
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        use_model = model or settings.DEFAULT_OPENAI_MODEL

        # Load target_segments from project if not provided directly
        if not target_segments and project_id:
            from app.models.contact import Project
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if project and project.target_segments:
                target_segments = project.target_segments

        if not target_segments:
            raise ValueError("target_segments required: pass directly or via project_id")

        prompt = build_project_query_prompt(
            target_segments=target_segments,
            count=count,
            existing_queries=existing_queries or [],
            good_queries=good_queries,
            bad_queries=bad_queries,
            confirmed_targets=confirmed_targets,
        )

        payload = {
            "model": use_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert at generating diverse B2B search queries. "
                        "Generate natural queries as people would type in Yandex or Google. "
                        "Output ONLY valid JSON array of strings, nothing else."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.95,
            "max_tokens": 4000,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }

        timeout = httpx.Timeout(120.0, connect=30.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"OpenAI query generation failed: {e}")
            raise

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        self._last_query_gen_tokens = {
            "total": usage.get("total_tokens", 0),
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
        }
        raw_queries = _extract_json_array(content)

        # Dedup against existing
        existing_norm = set(_normalize_query(q) for q in (existing_queries or []) if _normalize_query(q))
        seen = set(existing_norm)
        result_queries = []
        for q in raw_queries:
            q2 = (q or "").strip()
            if not q2:
                continue
            nq = _normalize_query(q2)
            if not nq or nq in seen or len(nq) < 8:
                continue
            seen.add(nq)
            result_queries.append(q2)

        return result_queries

    @property
    def last_query_gen_tokens(self) -> Dict[str, int]:
        """Token usage from the last generate_queries() call."""
        return getattr(self, "_last_query_gen_tokens", {"total": 0, "input": 0, "output": 0})

    # ------------------------------------------------------------------
    # Google SERP scraping
    # ------------------------------------------------------------------

    async def _scrape_single_query(
        self,
        query: str,
        max_pages: int,
    ) -> Set[str]:
        """Scrape Google for a single query via Apify SERP proxy."""
        all_domains: Set[str] = set()

        session_id = f"serp_{random.randint(10000, 99999)}"
        proxy_url = (
            f"http://groups-GOOGLE_SERP,session-{session_id}:"
            f"{settings.APIFY_PROXY_PASSWORD}@"
            f"{settings.APIFY_PROXY_HOST}:{settings.APIFY_PROXY_PORT}"
        )

        for page in range(max_pages):
            start = page * 10
            url = f"http://www.google.com/search?q={quote_plus(query)}&num=100&start={start}&hl=ru"

            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            }

            max_retries = 3
            success = False

            for retry in range(max_retries):
                try:
                    if retry > 0:
                        delay = (2 ** retry) * 5.0 + random.uniform(0, 2)
                        await asyncio.sleep(delay)

                    if page > 0 and retry == 0:
                        await asyncio.sleep(random.uniform(2.0, 4.0))

                    async with httpx.AsyncClient(
                        proxy=proxy_url,
                        timeout=settings.SEARCH_REQUEST_TIMEOUT,
                        follow_redirects=True,
                    ) as client:
                        resp = await client.get(url, headers=headers)

                    if resp.status_code == 429:
                        if retry < max_retries - 1:
                            continue
                        break

                    if resp.status_code == 200:
                        html = resp.text
                        if check_for_captcha(html):
                            success = True
                            break

                        domains = extract_domains_from_html(html)
                        new_domains = domains - all_domains
                        all_domains.update(domains)

                        if not new_domains and page > 0:
                            success = True
                            break

                        success = True
                        break
                    else:
                        if retry == max_retries - 1:
                            break

                except Exception as e:
                    logger.error(f"Request error for '{query}': {e}")
                    if retry == max_retries - 1:
                        break

            if not success:
                break

        return all_domains

    # ------------------------------------------------------------------
    # Yandex Search API (async/deferred)
    # ------------------------------------------------------------------

    async def _yandex_search_single_query(
        self,
        query: str,
        max_pages: int,
    ) -> Set[str]:
        """Search Yandex via official Cloud API (async/deferred mode)."""
        all_domains: Set[str] = set()

        headers = {
            "Authorization": f"Api-Key {settings.YANDEX_SEARCH_API_KEY}",
            "Content-Type": "application/json",
        }

        for page in range(max_pages):
            try:
                body = {
                    "query": {
                        "searchType": "SEARCH_TYPE_RU",
                        "queryText": query,
                        "page": page,
                    },
                    "folderId": settings.YANDEX_SEARCH_FOLDER_ID,
                    "responseFormat": "FORMAT_HTML",
                    "userAgent": random.choice(USER_AGENTS),
                }

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        settings.YANDEX_SEARCH_API_URL,
                        json=body,
                        headers=headers,
                    )

                if resp.status_code == 429:
                    logger.warning(f"Yandex 429 for '{query}' page {page + 1}, sleeping...")
                    await asyncio.sleep(5.0)
                    continue

                if resp.status_code != 200:
                    logger.error(f"Yandex API error {resp.status_code} for '{query}': {resp.text[:300]}")
                    break

                operation = resp.json()
                operation_id = operation.get("id")
                if not operation_id:
                    logger.error(f"No operation ID in Yandex response for '{query}'")
                    break

                html = await self._yandex_poll_operation(operation_id, headers)
                if not html:
                    logger.warning(f"Yandex operation timed out for '{query}' page {page + 1}")
                    break

                domains = extract_domains_from_html(html)
                new_domains = domains - all_domains
                all_domains.update(domains)

                logger.info(f"Yandex '{query}' page {page + 1}: {len(new_domains)} new ({len(all_domains)} total)")

                if not new_domains and page > 0:
                    break

            except Exception as e:
                logger.error(f"Yandex request error for '{query}' page {page + 1}: {e}")
                break

        return all_domains

    async def _yandex_poll_operation(
        self,
        operation_id: str,
        headers: dict,
        max_wait: int = 60,
        poll_interval: float = 1.0,
    ) -> Optional[str]:
        """Poll Yandex operation until done, return decoded HTML."""
        url = f"{settings.YANDEX_OPERATIONS_URL}/{operation_id}"

        for _ in range(int(max_wait / poll_interval)):
            await asyncio.sleep(poll_interval)

            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, headers=headers)

                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not data.get("done", False):
                    continue

                response_data = data.get("response", {})
                raw_data = response_data.get("rawData")
                if raw_data:
                    return base64.b64decode(raw_data).decode("utf-8", errors="replace")

                return None

            except Exception as e:
                logger.warning(f"Poll error for operation {operation_id}: {e}")
                continue

        return None

    # ------------------------------------------------------------------
    # Search Job Execution
    # ------------------------------------------------------------------

    async def run_search_job(
        self,
        session: AsyncSession,
        job_id: int,
    ) -> None:
        """
        Execute a search job: scrape all queries, filter domains, update DB.
        Designed to run as a background task.
        """
        result = await session.execute(
            select(SearchJob).where(SearchJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            logger.error(f"SearchJob {job_id} not found")
            return

        if job.status == SearchJobStatus.CANCELLED:
            return

        result = await session.execute(
            select(SearchQuery).where(SearchQuery.search_job_id == job_id)
        )
        queries = result.scalars().all()

        if not queries:
            job.status = SearchJobStatus.FAILED
            job.error_message = "No queries in job"
            await session.commit()
            return

        job.status = SearchJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await session.commit()

        max_pages = (job.config or {}).get("max_pages", settings.SEARCH_MAX_PAGES)
        workers = (job.config or {}).get("workers", settings.SEARCH_WORKERS)

        all_found_domains: List[str] = []

        is_yandex = job.search_engine == SearchEngine.YANDEX_API
        domain_source = DomainSource.SEARCH_YANDEX if is_yandex else DomainSource.SEARCH_GOOGLE

        try:
            semaphore = asyncio.Semaphore(workers)
            _cancelled = False

            # Track which query found each domain (first query wins)
            domain_to_query: Dict[str, int] = {}

            async def process_query(sq: SearchQuery):
                nonlocal _cancelled
                async with semaphore:
                    if _cancelled:
                        sq.status = SearchQueryStatus.FAILED
                        return (sq.id, [])

                    if not is_yandex:
                        await asyncio.sleep(random.uniform(0.3, 1.5))

                    try:
                        if is_yandex:
                            domains = await self._yandex_search_single_query(
                                sq.query_text, max_pages
                            )
                        else:
                            domains = await self._scrape_single_query(
                                sq.query_text, max_pages
                            )
                    except Exception as e:
                        logger.error(f"Query '{sq.query_text}' error: {e}")
                        sq.status = SearchQueryStatus.FAILED
                        return (sq.id, [])

                    sq.status = SearchQueryStatus.DONE
                    sq.domains_found = len(domains)
                    sq.pages_scraped = max_pages

                    return (sq.id, list(domains))

            tasks = [process_query(sq) for sq in queries]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    queries[i].status = SearchQueryStatus.FAILED
                    logger.error(f"Query '{queries[i].query_text}' failed: {res}")
                else:
                    query_id, domains_list = res
                    all_found_domains.extend(domains_list)
                    # Track first query that found each domain
                    for d in domains_list:
                        if d not in domain_to_query:
                            domain_to_query[d] = query_id

                job.queries_completed += 1

            await session.commit()

            if await self._is_job_cancelled(session, job_id):
                job.status = SearchJobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                await session.commit()
                return

            is_dry_run = (job.config or {}).get("dry_run", False)
            filter_result = await domain_service.filter_domains(
                session,
                all_found_domains,
                source=domain_source,
                dry_run=is_dry_run,
            )

            job.domains_found = len(all_found_domains)
            job.domains_new = len(filter_result["new"])
            job.domains_trash = len(filter_result["trash"])
            job.domains_duplicate = len(filter_result["duplicate"])
            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            # Store domain→query mapping for source tracking
            config = dict(job.config or {})
            # Merge with any existing mapping (for iterative runs)
            existing_mapping = config.get("domain_to_query", {})
            existing_mapping.update(domain_to_query)
            config["domain_to_query"] = existing_mapping
            job.config = config

        except Exception as e:
            logger.error(f"SearchJob {job_id} failed: {e}")
            job.status = SearchJobStatus.FAILED
            job.error_message = str(e)[:500]

        await session.commit()

        logger.info(
            f"SearchJob {job_id} done: "
            f"found={job.domains_found}, new={job.domains_new}, "
            f"trash={job.domains_trash}, dup={job.domains_duplicate}"
        )

    async def _is_job_cancelled(self, session: AsyncSession, job_id: int) -> bool:
        """Check if a job has been cancelled (fresh DB read)."""
        result = await session.execute(
            select(SearchJob.status).where(SearchJob.id == job_id)
        )
        status = result.scalar_one_or_none()
        return status == SearchJobStatus.CANCELLED


# Module-level singleton
search_service = SearchService()
