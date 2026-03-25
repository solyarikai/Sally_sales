"""Web Scraper Service — adapted for MCP."""
import asyncio
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
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True, verify=True) as client:
                response = await client.get(fetch_url, headers=self._get_headers())
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

    async def scrape_batch(self, urls: List[Dict[str, Any]], timeout: int = 15, max_concurrent: int = 50, on_result: Optional[Callable] = None) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrent)
        results = [] if not on_result else None

        async def process(item):
            async with semaphore:
                await asyncio.sleep(0.05)
                result = await self.scrape_website(item["url"], timeout=timeout)
                result["row_id"] = item["row_id"]
                if on_result:
                    await on_result(result)
                else:
                    results.append(result)

        await asyncio.gather(*[process(item) for item in urls], return_exceptions=True)
        return results or []
