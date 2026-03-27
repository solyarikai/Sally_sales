"""Web Scraper Service — adapted for MCP.

Uses Apify residential proxies (if configured) for parallel scraping.
Same approach as main pipeline: 50 concurrent requests via semaphore,
httpx + proxy, rotating User-Agents. Fast until 429.
"""
import asyncio
import random
import re
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
import httpx

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class ScraperService:
    def __init__(self):
        self._request_count = 0

    def _validate_url(self, url: str) -> tuple[bool, str, str]:
        if not url:
            return False, "", "Empty URL"
        url = url.strip()
        if url in ['--', '-', 'n/a', 'N/A', 'none', 'null', '']:
            return False, "", "No URL"
        if len(url) < 4:
            return False, "", "URL too short"
        url = re.sub(r'^(https?:/*)?', '', url, flags=re.IGNORECASE)
        url = url.rstrip('/')
        if not url or '.' not in url.split('/')[0]:
            return False, "", "No valid domain"
        normalized = f"https://{url}"
        try:
            parsed = urlparse(normalized)
            if not parsed.netloc:
                return False, "", "Could not parse"
        except Exception:
            return False, "", "Parse failed"
        return True, normalized, ""

    def _extract_text(self, html: str, url: str) -> str:
        try:
            soup = BeautifulSoup(html, 'lxml')
            for el in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe', 'svg', 'form', 'button']):
                el.decompose()
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:50000]
        except Exception:
            return ""

    def _get_headers(self) -> dict:
        self._request_count += 1
        ua = USER_AGENTS[self._request_count % len(USER_AGENTS)]
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_proxy_url(self) -> Optional[str]:
        """Build Apify residential proxy URL if configured."""
        from app.config import settings
        if not getattr(settings, 'APIFY_PROXY_PASSWORD', None):
            return None
        session_id = f"scrape_{random.randint(10000, 99999)}"
        host = getattr(settings, 'APIFY_PROXY_HOST', 'proxy.apify.com')
        port = getattr(settings, 'APIFY_PROXY_PORT', 8000)
        return f"http://groups-RESIDENTIAL,session-{session_id}:{settings.APIFY_PROXY_PASSWORD}@{host}:{port}"

    async def scrape_website(self, url: str, timeout: int = 15) -> Dict[str, Any]:
        original = url
        is_valid, normalized, error = self._validate_url(url)
        if not is_valid:
            return {"success": False, "error": error, "url": original, "status_code": None}

        result = await self._fetch_url(original, normalized, timeout)
        if not result["success"] and "CONNECTION" in result.get("error", ""):
            http_url = normalized.replace("https://", "http://")
            http_result = await self._fetch_url(original, http_url, timeout)
            if http_result["success"]:
                return http_result
        return result

    async def _fetch_url(self, original: str, fetch_url: str, timeout: int) -> Dict[str, Any]:
        """Fetch URL with Apify residential proxy if configured."""
        proxy_url = self._get_proxy_url()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
                verify=True,
                proxy=proxy_url,
            ) as client:
                response = await client.get(fetch_url, headers=self._get_headers())
                if response.status_code == 429:
                    return {"success": False, "error": "Rate limited (429)", "url": original, "status_code": 429}
                if response.status_code >= 400:
                    return {"success": False, "error": f"HTTP {response.status_code}", "url": original, "status_code": response.status_code}
                html = response.text
                text = self._extract_text(html, fetch_url)
                if not text or len(text) < 50:
                    return {"success": False, "error": "No text content", "url": original, "status_code": response.status_code}
                return {"success": True, "text": text, "url": original, "final_url": str(response.url), "status_code": response.status_code}
        except httpx.TimeoutException:
            return {"success": False, "error": f"Timeout ({timeout}s)", "url": original, "status_code": None}
        except httpx.ConnectError:
            return {"success": False, "error": "CONNECTION_ERROR", "url": original, "status_code": None}
        except Exception as e:
            return {"success": False, "error": str(e)[:100], "url": original, "status_code": None}

    async def scrape_batch(
        self, urls: List[Dict[str, Any]], timeout: int = 15,
        max_concurrent: int = 50, delay: float = 0.05,
        on_result: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape batch with 50 concurrent requests via Apify residential proxies.
        Same pattern as main pipeline — fast until 429."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = [] if not on_result else None
        completed = 0
        total = len(urls)

        async def process(item):
            nonlocal completed
            async with semaphore:
                await asyncio.sleep(delay)
                result = await self.scrape_website(item["url"], timeout=timeout)
                result["row_id"] = item["row_id"]
                completed += 1
                if completed % 25 == 0:
                    logger.info(f"Scrape progress: {completed}/{total}")
                if on_result:
                    await on_result(result)
                else:
                    results.append(result)

        await asyncio.gather(*[process(item) for item in urls], return_exceptions=True)
        return results or []

    async def scrape_domains_fast(self, domains: List[str], timeout: int = 10, max_concurrent: int = 50) -> Dict[str, str]:
        """Quick parallel scrape of domains. Returns {domain: text} dict.
        Used by filter intelligence for probe evaluation.
        50 concurrent via Apify residential proxies — fast until 429."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results: Dict[str, str] = {}

        async def process(domain: str):
            async with semaphore:
                result = await self.scrape_website(domain, timeout=timeout)
                if result.get("success"):
                    results[domain] = result["text"]

        await asyncio.gather(*[process(d) for d in domains], return_exceptions=True)
        logger.info(f"Fast scrape: {len(results)}/{len(domains)} domains scraped successfully")
        return results
