"""Instantly.ai integration service for sending leads to email campaigns.

Uses Instantly API V2: https://developer.instantly.ai/api/v2
"""
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class InstantlyService:
    """Service for interacting with Instantly.ai API V2."""
    
    def __init__(self):
        self._api_key: Optional[str] = settings.INSTANTLY_API_KEY
        self.base_url = settings.INSTANTLY_BASE_URL
    
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
        """Get headers for API V2 requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> bool:
        """Test the API connection by fetching campaigns."""
        if not self._api_key:
            return False
        
        try:
            campaigns = await self.get_campaigns()
            return campaigns is not None
        except Exception as e:
            logger.error(f"Instantly connection test failed: {e}")
            return False
    
    async def get_campaigns(self) -> List[Dict[str, Any]]:
        """Fetch all campaigns from Instantly using API V2."""
        if not self._api_key:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # API V2: GET /api/v2/campaigns
                response = await client.get(
                    f"{self.base_url}/campaigns",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # API V2 returns { "items": [...], "next_starting_after": "..." }
                    if isinstance(data, dict) and "items" in data:
                        return data["items"]
                    # Fallback for direct list response
                    return data if isinstance(data, list) else []
                else:
                    logger.error(f"Failed to fetch campaigns: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching Instantly campaigns: {e}")
            return []
    
    async def add_lead_to_campaign(
        self,
        campaign_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None,
        custom_variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a single lead to a campaign using API V2."""
        if not self._api_key:
            return {"success": False, "error": "No API key configured"}
        
        # API V2: POST /api/v2/leads
        payload: Dict[str, Any] = {
            "campaign": campaign_id,
            "email": email,
        }
        
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if company_name:
            payload["company_name"] = company_name
        if custom_variables:
            # API V2 uses "payload" for custom variables
            payload["payload"] = custom_variables
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/leads",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code in (200, 201):
                    return {"success": True, "data": response.json()}
                else:
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {response.text}"
                    }
        except Exception as e:
            logger.error(f"Error adding lead to Instantly: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_leads_batch(
        self,
        campaign_id: str,
        leads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add multiple leads to a campaign in batch using API V2.
        
        API V2 endpoint: POST /api/v2/leads/batch
        Each lead should have at minimum: {"email": "..."}
        Optional fields: first_name, last_name, company_name, website, phone, payload
        """
        if not self._api_key:
            return {"success": False, "error": "No API key configured", "leads_sent": 0}
        
        # Transform leads for API V2 format
        v2_leads = []
        for lead in leads:
            v2_lead = {
                "email": lead.get("email"),
            }
            if lead.get("first_name"):
                v2_lead["first_name"] = lead["first_name"]
            if lead.get("last_name"):
                v2_lead["last_name"] = lead["last_name"]
            if lead.get("company_name"):
                v2_lead["company_name"] = lead["company_name"]
            if lead.get("custom_variables"):
                v2_lead["payload"] = lead["custom_variables"]
            v2_leads.append(v2_lead)
        
        # API V2: POST /api/v2/leads/batch  
        payload = {
            "campaign": campaign_id,
            "leads": v2_leads
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/leads/batch",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code in (200, 201, 202):
                    result = response.json()
                    return {
                        "success": True,
                        "leads_sent": len(leads),
                        "data": result
                    }
                else:
                    error_text = response.text
                    logger.error(f"Instantly batch add failed: {response.status_code} - {error_text}")
                    return {
                        "success": False,
                        "error": f"Status {response.status_code}: {error_text}",
                        "leads_sent": 0
                    }
        except Exception as e:
            logger.error(f"Error adding leads batch to Instantly: {e}")
            return {"success": False, "error": str(e), "leads_sent": 0}


# Global instance
instantly_service = InstantlyService()
