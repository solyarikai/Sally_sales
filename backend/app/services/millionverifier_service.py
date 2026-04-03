"""MillionVerifier integration service for email verification.

Uses MillionVerifier API: https://developer.millionverifier.com/
"""
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MillionVerifierService:
    """Service for interacting with MillionVerifier API."""
    
    def __init__(self):
        self._api_key: Optional[str] = None
        self.base_url = "https://api.millionverifier.com"
    
    @property
    def api_key(self) -> Optional[str]:
        return self._api_key
    
    def set_api_key(self, api_key: str):
        """Set the API key."""
        self._api_key = api_key
    
    def is_connected(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self._api_key)
    
    async def test_connection(self) -> bool:
        """Test the API connection by verifying a test email."""
        if not self._api_key:
            return False
        
        try:
            result = await self.verify_email("test@example.com")
            return result.get("success", False) or "error" not in result
        except Exception as e:
            logger.error(f"MillionVerifier connection test failed: {e}")
            return False
    
    async def get_credits(self) -> Optional[Dict[str, Any]]:
        """Get current credits balance by making a test verification call."""
        if not self._api_key:
            return None
        
        try:
            result = await self.verify_email("test@example.com")
            if result.get("success"):
                return {
                    "credits": result.get("credits", 0),
                    "api_key": self._api_key[:10] + "..." if self._api_key else None
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching MillionVerifier credits: {e}")
            return None
    
    async def verify_email(
        self,
        email: str,
        timeout: int = 20
    ) -> Dict[str, Any]:
        """Verify an email address.
        
        Args:
            email: Email address to verify
            timeout: Timeout in seconds (2-60, default 20)
            
        Returns:
            Dict with verification result
            
        Response format:
            {
                "email": "user@example.com",
                "quality": "good",
                "result": "ok",  # ok, invalid, disposable, catch-all, unknown
                "resultcode": 1,
                "subresult": "",
                "free": false,
                "role": false,
                "didyoumean": "",
                "credits": 12345,
                "executiontime": 0.123,
                "error": ""
            }
        """
        if not self._api_key:
            return {"success": False, "error": "No API key configured"}
        
        # Validate timeout range
        timeout = max(2, min(60, timeout))
        
        params = {
            "api": self._api_key,
            "email": email,
            "timeout": timeout
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout + 5, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for error in response
                    if data.get("error"):
                        return {
                            "success": False,
                            "error": data["error"]
                        }
                    
                    # Map result to simple format
                    result = data.get("result", "unknown")
                    
                    return {
                        "success": True,
                        "email": data.get("email"),
                        "result": result,  # ok, invalid, disposable, catch-all, unknown
                        "quality": data.get("quality"),
                        "verified": result == "ok",  # Only "ok" is truly verified
                        "is_disposable": result == "disposable",
                        "is_catch_all": result == "catch-all",
                        "is_free": data.get("free", False),
                        "is_role": data.get("role", False),
                        "did_you_mean": data.get("didyoumean", ""),
                        "credits": data.get("credits"),
                        "execution_time": data.get("executiontime"),
                        "raw_data": data
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {response.text}"
                    }
        except Exception as e:
            logger.error(f"Error verifying email via MillionVerifier: {e}")
            return {"success": False, "error": str(e)}
    
    async def verify_batch(
        self,
        emails: list[str],
        timeout: int = 20,
        max_concurrent: int = 10
    ) -> list[Dict[str, Any]]:
        """Verify multiple emails concurrently.
        
        Args:
            emails: List of email addresses
            timeout: Timeout per request
            max_concurrent: Max concurrent requests (MillionVerifier limit: 160/sec)
            
        Returns:
            List of verification results
        """
        import asyncio
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def verify_with_semaphore(email: str) -> Dict[str, Any]:
            async with semaphore:
                result = await self.verify_email(email, timeout)
                # Small delay to respect rate limits
                await asyncio.sleep(0.01)  # 100 requests/sec max
                return {"email": email, **result}
        
        tasks = [verify_with_semaphore(email) for email in emails]
        return await asyncio.gather(*tasks)


# Global instance
millionverifier_service = MillionVerifierService()
