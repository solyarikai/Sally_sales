"""
Web Scraper Service

Fetches website content and extracts raw text for enrichment.
Uses httpx with rotating user agents and proper headers.
Designed for scale (10k+ companies) with proper error handling.
"""

import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
import httpx

logger = logging.getLogger(__name__)

# Realistic browser user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class ScraperService:
    """
    Web scraper service using httpx with realistic browser headers.
    """
    
    def __init__(self):
        self._request_count = 0
    
    def _validate_url(self, url: str) -> tuple[bool, str, str]:
        """
        Validate and normalize URL.
        Returns: (is_valid, normalized_url, error_message)
        """
        if not url:
            return False, "", "INVALID_URL: URL is empty"
        
        url = url.strip()
        
        # Check for placeholder values
        if url in ['--', '-', 'n/a', 'N/A', 'na', 'NA', 'none', 'None', 'null', '']:
            return False, "", "INVALID_URL: No URL provided"
        
        # Check for obviously invalid URLs
        if len(url) < 4:
            return False, "", "INVALID_URL: URL is too short"
        
        # Check for invalid characters
        if ' ' in url or '\n' in url or '\t' in url:
            return False, "", "INVALID_URL: URL contains invalid characters"
        
        # Remove common malformed prefixes and normalize
        url = re.sub(r'^(https?:/*)?', '', url, flags=re.IGNORECASE)
        
        # Remove trailing slashes for consistency
        url = url.rstrip('/')
        
        # Check if there's a valid domain
        if not url or '.' not in url.split('/')[0]:
            return False, "", "INVALID_URL: No valid domain found"
        
        # Build normalized URL with HTTPS
        normalized_url = f"https://{url}"
        
        # Validate parsed URL
        try:
            parsed = urlparse(normalized_url)
            if not parsed.netloc or not parsed.scheme:
                return False, "", "INVALID_URL: Could not parse URL"
            
            # Check for valid TLD (at least 2 chars)
            domain_parts = parsed.netloc.split('.')
            if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
                return False, "", "INVALID_URL: Invalid domain format"
                
        except Exception:
            return False, "", "INVALID_URL: URL parsing failed"
        
        return True, normalized_url, ""
    
    def _extract_text(self, html: str, url: str) -> str:
        """
        Extract readable text content from HTML.
        Removes scripts, styles, navigation, and other non-content elements.
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Remove non-content elements
            for element in soup.find_all([
                'script', 'style', 'nav', 'header', 'footer', 
                'aside', 'noscript', 'iframe', 'svg', 'path',
                'meta', 'link', 'form', 'button', 'input',
                'select', 'textarea'
            ]):
                element.decompose()
            
            # Remove elements with common non-content classes/ids
            selectors_to_remove = [
                '[class*="nav"]', '[class*="menu"]', '[class*="sidebar"]',
                '[class*="footer"]', '[class*="header"]', '[class*="cookie"]',
                '[class*="popup"]', '[class*="modal"]', '[class*="banner"]',
                '[class*="advertisement"]', '[class*="social"]', '[class*="share"]',
                '[id*="nav"]', '[id*="menu"]', '[id*="sidebar"]',
                '[id*="footer"]', '[id*="header"]', '[id*="cookie"]',
            ]
            for selector in selectors_to_remove:
                try:
                    for el in soup.select(selector):
                        el.decompose()
                except Exception:
                    pass
            
            # Get text content
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            # Limit text length (max ~50KB)
            max_chars = 50000
            if len(text) > max_chars:
                text = text[:max_chars] + "... [truncated]"
            
            return text
            
        except Exception as e:
            logger.warning(f"Text extraction failed for {url}: {e}")
            return ""
    
    def _is_binary_content(self, content: str) -> bool:
        """Check if content appears to be binary/garbled."""
        if not content:
            return False
        sample = content[:1000]
        non_printable = sum(1 for c in sample if not c.isprintable() and c not in '\n\r\t ')
        return non_printable > len(sample) * 0.15
    
    def _get_headers(self) -> dict:
        """Get realistic browser headers with rotating user agent."""
        self._request_count += 1
        ua = USER_AGENTS[self._request_count % len(USER_AGENTS)]
        
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    
    async def scrape_website(
        self,
        url: str,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """
        Scrape a single website and extract text content.
        
        Args:
            url: Website URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            dict with keys: success, text/error, url, status_code
        """
        original_url = url
        
        # Validate URL
        is_valid, normalized_url, error_msg = self._validate_url(url)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "url": original_url,
                "status_code": None,
            }
        
        # Try HTTPS first, then HTTP if it fails
        result = await self._fetch_url(original_url, normalized_url, timeout)
        
        # If HTTPS failed with connection error, try HTTP
        if not result["success"] and "CONNECTION" in result.get("error", ""):
            http_url = normalized_url.replace("https://", "http://")
            http_result = await self._fetch_url(original_url, http_url, timeout)
            if http_result["success"]:
                return http_result
        
        return result
    
    def _get_proxy_url(self) -> Optional[str]:
        """Build Apify residential proxy URL if configured."""
        from app.core.config import settings
        if not getattr(settings, 'APIFY_PROXY_PASSWORD', None):
            return None
        import random
        session_id = f"scrape_{random.randint(10000, 99999)}"
        host = getattr(settings, 'APIFY_PROXY_HOST', 'proxy.apify.com')
        port = getattr(settings, 'APIFY_PROXY_PORT', 8000)
        return f"http://groups-RESIDENTIAL,session-{session_id}:{settings.APIFY_PROXY_PASSWORD}@{host}:{port}"

    async def _fetch_url(
        self,
        original_url: str,
        fetch_url: str,
        timeout: int,
    ) -> Dict[str, Any]:
        """Fetch a URL and extract text content. Uses Apify proxy if configured."""

        headers = self._get_headers()
        proxy_url = self._get_proxy_url()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
                verify=True,
                proxy=proxy_url,
            ) as client:
                response = await client.get(fetch_url, headers=headers)
                status_code = response.status_code
                
                # Handle error status codes
                if status_code == 403:
                    return {
                        "success": False,
                        "error": "BLOCKED: Access denied (403)",
                        "url": original_url,
                        "status_code": 403,
                    }
                elif status_code == 404:
                    return {
                        "success": False,
                        "error": "NOT_FOUND: Page does not exist (404)",
                        "url": original_url,
                        "status_code": 404,
                    }
                elif status_code == 429:
                    return {
                        "success": False,
                        "error": "RATE_LIMITED: Too many requests (429)",
                        "url": original_url,
                        "status_code": 429,
                    }
                elif status_code >= 500:
                    return {
                        "success": False,
                        "error": f"SERVER_ERROR: Website error ({status_code})",
                        "url": original_url,
                        "status_code": status_code,
                    }
                elif status_code >= 400:
                    return {
                        "success": False,
                        "error": f"ERROR: HTTP {status_code}",
                        "url": original_url,
                        "status_code": status_code,
                    }
                
                # Get response text
                try:
                    html = response.text
                except Exception:
                    # Try decoding with different encodings
                    try:
                        html = response.content.decode('utf-8', errors='ignore')
                    except Exception:
                        html = response.content.decode('latin-1', errors='ignore')
                
                # Check for binary/garbled content
                if self._is_binary_content(html):
                    return {
                        "success": False,
                        "error": "ENCODING_ERROR: Could not decode page content",
                        "url": original_url,
                        "status_code": status_code,
                    }
                
                # Extract text
                text = self._extract_text(html, fetch_url)
                
                if not text or len(text) < 50:
                    return {
                        "success": False,
                        "error": "EMPTY: No text content (site may use JavaScript rendering)",
                        "url": original_url,
                        "status_code": status_code,
                    }
                
                return {
                    "success": True,
                    "text": text,
                    "url": original_url,
                    "final_url": str(response.url),
                    "status_code": status_code,
                }
                
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"TIMEOUT: Site did not respond within {timeout}s",
                "url": original_url,
                "status_code": None,
            }
        except httpx.ConnectError as e:
            error_str = str(e).lower()
            if "ssl" in error_str or "certificate" in error_str:
                return {
                    "success": False,
                    "error": "SSL_ERROR: Certificate verification failed",
                    "url": original_url,
                    "status_code": None,
                }
            if "nodename" in error_str or "getaddrinfo" in error_str or "name or service not known" in error_str:
                return {
                    "success": False,
                    "error": "DNS_ERROR: Website domain not found",
                    "url": original_url,
                    "status_code": None,
                }
            return {
                "success": False,
                "error": "CONNECTION_ERROR: Could not connect to website",
                "url": original_url,
                "status_code": None,
            }
        except httpx.TooManyRedirects:
            return {
                "success": False,
                "error": "REDIRECT_ERROR: Too many redirects",
                "url": original_url,
                "status_code": None,
            }
        except Exception as e:
            logger.error(f"Scrape error for {original_url}: {e}")
            return {
                "success": False,
                "error": f"ERROR: {str(e)[:100]}",
                "url": original_url,
                "status_code": None,
            }
    
    async def scrape_batch(
        self,
        urls: List[Dict[str, Any]],
        timeout: int = 15,
        max_concurrent: int = 50,
        delay_between_requests: float = 0.05,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        on_result: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple websites with high concurrency + streaming results.

        Args:
            urls: List of dicts with 'row_id' and 'url' keys
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent requests (default 50)
            delay_between_requests: Delay between starting new requests
            progress_callback: Optional callback(completed, total)
            on_result: Optional async callback(result_dict) — called per result for
                       immediate DB commit. If set, results are NOT accumulated in memory.

        Returns:
            List of results (empty if on_result is used — results streamed via callback)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        completed = 0
        total = len(urls)
        results = [] if not on_result else None

        async def process_url(item: Dict[str, Any]):
            nonlocal completed
            async with semaphore:
                await asyncio.sleep(delay_between_requests)

                try:
                    result = await self.scrape_website(item["url"], timeout=timeout)
                    result["row_id"] = item["row_id"]
                except Exception as e:
                    result = {
                        "row_id": item["row_id"],
                        "success": False,
                        "error": f"ERROR: {str(e)[:100]}",
                        "url": item["url"],
                        "status_code": None,
                    }

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

                if on_result:
                    await on_result(result)
                else:
                    results.append(result)

        # Process all URLs concurrently with semaphore
        tasks = [process_url(item) for item in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results or []


# Global instance
scraper_service = ScraperService()
