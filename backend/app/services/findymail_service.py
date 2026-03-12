"""Findymail integration service for email finding and verification.

Uses Findymail API: https://app.findymail.com/docs/
"""
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class FindymailService:
    """Service for interacting with Findymail API."""
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self.base_url = "https://app.findymail.com"
    
    @property
    def api_key(self) -> Optional[str]:
        return self._api_key
    
    def set_api_key(self, api_key: str):
        """Set the API key."""
        self._api_key = api_key
    
    def is_connected(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self._api_key)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> bool:
        """Test the API connection by checking credits."""
        if not self._api_key:
            return False
        
        try:
            credits = await self.get_credits()
            return credits is not None
        except Exception as e:
            logger.error(f"Findymail connection test failed: {e}")
            return False
    
    async def get_credits(self) -> Optional[Dict[str, Any]]:
        """Get current credits balance."""
        if not self._api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/credits",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to fetch credits: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching Findymail credits: {e}")
            return None
    
    async def find_email_by_name(
        self,
        name: str,
        domain: str
    ) -> Dict[str, Any]:
        """Find someone's email from name and company domain.
        
        Args:
            name: Full name of the person
            domain: Company domain (e.g., 'example.com') or company name
            
        Returns:
            Dict with email and verification status, or error
        """
        if not self._api_key:
            return {"success": False, "error": "No API key configured"}
        
        payload = {
            "name": name,
            "domain": domain
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/search/name",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    contact_obj = data.get("contact", {})
                    email = data.get("email") or contact_obj.get("email")
                    verified = data.get("verified", False) or contact_obj.get("verified", False)
                    return {
                        "success": True,
                        "email": email,
                        "verified": verified,
                        "data": data
                    }
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                elif response.status_code == 404:
                    return {"success": False, "error": "Email not found", "email": None}
                else:
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {response.text}"
                    }
        except Exception as e:
            logger.error(f"Error finding email via Findymail: {e}")
            return {"success": False, "error": str(e)}

    async def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify an email for potential bounce.
        
        Args:
            email: Email address to verify
            
        Returns:
            Dict with verification status
        """
        if not self._api_key:
            return {"success": False, "error": "No API key configured"}
        
        payload = {"email": email}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/verify",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "email": data.get("email"),
                        "verified": data.get("verified", False),
                        "provider": data.get("provider"),
                        "data": data
                    }
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                else:
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {response.text}"
                    }
        except Exception as e:
            logger.error(f"Error verifying email via Findymail: {e}")
            return {"success": False, "error": str(e)}
    
    async def find_email_by_linkedin(self, linkedin_url: str) -> Dict[str, Any]:
        """Find email from LinkedIn profile URL.
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            Dict with email and verification status
        """
        if not self._api_key:
            return {"success": False, "error": "No API key configured"}
        
        # Ensure URL is properly formatted
        url = linkedin_url.strip()
        if not url.startswith('http'):
            url = f"https://{url}"
        
        payload = {"linkedin_url": url}
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/search/linkedin",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Email can be at top level or nested in "contact" object
                    contact_obj = data.get("contact", {})
                    email = data.get("email") or contact_obj.get("email")
                    verified = data.get("verified", False) or contact_obj.get("verified", False)
                    return {
                        "success": True,
                        "email": email,
                        "verified": verified,
                        "data": data
                    }
                elif response.status_code == 402:
                    return {"success": False, "error": "Not enough credits"}
                elif response.status_code == 404:
                    return {"success": False, "error": "Email not found", "email": None}
                else:
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {response.text}"
                    }
        except Exception as e:
            logger.error(f"Error finding email from LinkedIn via Findymail: {e}")
            return {"success": False, "error": str(e)}


# Global instance
findymail_service = FindymailService()
