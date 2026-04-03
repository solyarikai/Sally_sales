"""
Favicon extraction service
Automatically fetches and validates company favicons from websites
"""
import httpx
import base64
from io import BytesIO
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class FaviconService:
    """Service for extracting and validating website favicons"""
    
    # Minimum size for valid favicon (in pixels)
    MIN_SIZE = 16
    MAX_SIZE = 512
    
    # Timeout for HTTP requests
    TIMEOUT = 10.0
    
    # Common favicon locations to try
    FAVICON_PATHS = [
        '/favicon.ico',
        '/favicon.png',
        '/apple-touch-icon.png',
        '/apple-touch-icon-precomposed.png',
    ]
    
    async def fetch_favicon(self, website_url: str) -> Optional[str]:
        """
        Fetch favicon from website and return the best URL.
        Returns None if no valid favicon found.
        
        Strategy:
        1. Parse HTML for <link rel="icon"> tags
        2. Try common favicon paths
        3. Validate image is real (not blank/default)
        4. Return best favicon URL
        """
        try:
            # Normalize URL
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url
            
            parsed = urlparse(website_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            logger.info(f"Fetching favicon from {website_url}")
            
            # Try to find favicon in HTML
            favicon_url = await self._find_favicon_in_html(website_url, base_url)
            if favicon_url:
                return favicon_url
            
            # Try common paths
            favicon_url = await self._try_common_paths(base_url)
            if favicon_url:
                return favicon_url
            
            logger.info(f"No valid favicon found for {website_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching favicon from {website_url}: {e}")
            return None
    
    async def _find_favicon_in_html(self, url: str, base_url: str) -> Optional[str]:
        """Parse HTML to find favicon link tags"""
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; FaviconBot/1.0)'
                })
                
                if response.status_code != 200:
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for icon link tags (in order of preference)
                selectors = [
                    'link[rel="icon"]',
                    'link[rel="shortcut icon"]',
                    'link[rel="apple-touch-icon"]',
                    'link[rel="apple-touch-icon-precomposed"]',
                ]
                
                for selector in selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        if href:
                            # Make absolute URL
                            favicon_url = urljoin(base_url, href)
                            
                            # Validate the image
                            if await self._validate_favicon(favicon_url):
                                logger.info(f"Found valid favicon: {favicon_url}")
                                return favicon_url
                
                return None
                
        except Exception as e:
            logger.error(f"Error parsing HTML for favicon: {e}")
            return None
    
    async def _try_common_paths(self, base_url: str) -> Optional[str]:
        """Try common favicon paths"""
        for path in self.FAVICON_PATHS:
            favicon_url = base_url + path
            if await self._validate_favicon(favicon_url):
                logger.info(f"Found favicon at common path: {favicon_url}")
                return favicon_url
        return None
    
    async def _validate_favicon(self, url: str) -> bool:
        """
        Validate that the favicon is a real, non-blank image.
        
        Checks:
        1. URL is accessible
        2. Content-Type is image
        3. Image can be opened
        4. Image has reasonable dimensions
        5. Image is not completely blank/transparent
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return False
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not any(img_type in content_type for img_type in ['image/', 'application/octet-stream']):
                    return False
                
                # Try to open as image
                try:
                    img = Image.open(BytesIO(response.content))
                    
                    # Check dimensions
                    width, height = img.size
                    if width < self.MIN_SIZE or height < self.MIN_SIZE:
                        logger.debug(f"Favicon too small: {width}x{height}")
                        return False
                    
                    if width > self.MAX_SIZE or height > self.MAX_SIZE:
                        logger.debug(f"Favicon too large: {width}x{height}")
                        return False
                    
                    # Check if image is not blank/transparent
                    if not self._is_valid_image_content(img):
                        logger.debug("Favicon appears to be blank or invalid")
                        return False
                    
                    return True
                    
                except Exception as e:
                    logger.debug(f"Failed to open favicon as image: {e}")
                    return False
                
        except Exception as e:
            logger.debug(f"Error validating favicon {url}: {e}")
            return False
    
    def _is_valid_image_content(self, img: Image.Image) -> bool:
        """
        Check if image has actual content (not blank/transparent).
        
        Strategy:
        1. Convert to RGB if needed
        2. Check if image has variation in colors
        3. Ensure it's not all white/transparent
        """
        try:
            # Convert to RGB for analysis
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')
            
            # Get image data
            pixels = list(img.getdata())
            
            # Check if all pixels are the same (blank image)
            if len(set(pixels)) == 1:
                return False
            
            # Check if image is mostly transparent
            if img.mode == 'RGBA':
                transparent_count = sum(1 for p in pixels if p[3] < 10)
                if transparent_count > len(pixels) * 0.9:
                    return False
            
            # Check if image is mostly white/light
            if img.mode in ('RGB', 'RGBA'):
                light_count = sum(
                    1 for p in pixels 
                    if p[0] > 240 and p[1] > 240 and p[2] > 240
                )
                if light_count > len(pixels) * 0.9:
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking image content: {e}")
            return False


# Singleton instance
favicon_service = FaviconService()


async def get_favicon_service() -> FaviconService:
    """Dependency injection for favicon service"""
    return favicon_service
