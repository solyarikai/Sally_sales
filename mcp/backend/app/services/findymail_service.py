"""FindyMail Service — adapted for MCP with per-user API keys."""
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class FindymailService:
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self.base_url = "https://app.findymail.com"

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        from app.config import settings
        return settings.FINDYMAIL_API_KEY

    def is_connected(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            credits = await self.get_credits()
            return credits is not None
        except Exception:
            return False

    async def get_credits(self) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/credits", headers=self._get_headers())
                return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching Findymail credits: {e}")
            return None

    async def find_email_by_name(self, name: str, domain: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No API key configured"}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/api/search/name", headers=self._get_headers(), json={"name": name, "domain": domain})
                if response.status_code == 200:
                    data = response.json()
                    contact = data.get("contact", {})
                    return {"success": True, "email": data.get("email") or contact.get("email"), "verified": data.get("verified", False) or contact.get("verified", False)}
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                elif response.status_code == 404:
                    return {"success": False, "error": "Email not found", "email": None}
                return {"success": False, "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_email(self, email: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No API key configured"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/api/verify", headers=self._get_headers(), json={"email": email})
                if response.status_code == 200:
                    data = response.json()
                    return {"success": True, "email": data.get("email"), "verified": data.get("verified", False)}
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                return {"success": False, "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def find_email_by_linkedin(self, linkedin_url: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No API key configured"}
        url = linkedin_url.strip()
        if not url.startswith('http'):
            url = f"https://{url}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/api/search/linkedin", headers=self._get_headers(), json={"linkedin_url": url})
                if response.status_code == 200:
                    data = response.json()
                    contact = data.get("contact", {})
                    return {"success": True, "email": data.get("email") or contact.get("email"), "verified": data.get("verified", False) or contact.get("verified", False)}
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                elif response.status_code == 404:
                    return {"success": False, "error": "Email not found", "email": None}
                return {"success": False, "error": f"Status {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
