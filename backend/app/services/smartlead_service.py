"""Smartlead integration service for cold email campaigns.

Uses Smartlead API: https://api.smartlead.ai/
Base URL: https://server.smartlead.ai/api/v1
"""
import httpx
from typing import Optional, List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class SmartleadService:
    """Service for interacting with Smartlead API."""
    
    def __init__(self):
        # Try to load from environment first
        self._api_key: Optional[str] = os.environ.get('SMARTLEAD_API_KEY')
        self.base_url = "https://server.smartlead.ai/api/v1"
        if self._api_key:
            logger.info("Smartlead API key loaded from environment")
    
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
        """Test the API connection by fetching campaigns."""
        if not self._api_key:
            return False
        
        try:
            campaigns = await self.get_campaigns()
            return True
        except Exception as e:
            logger.error(f"Smartlead connection test failed: {e}")
            return False
    
    async def get_campaigns(self) -> List[Dict[str, Any]]:
        """Get all campaigns from Smartlead.
        
        Returns:
            List of campaign objects with id, name, status, etc.
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/campaigns",
                    params={"api_key": self._api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Smartlead returns campaigns in different formats
                    # Handle both array and object with campaigns key
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("campaigns", data.get("data", []))
                    return []
                else:
                    logger.error(f"Failed to fetch campaigns: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching Smartlead campaigns: {e}")
            raise
    
    async def add_leads_to_campaign(
        self,
        campaign_id: str,
        leads: List[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add leads to a Smartlead campaign.
        
        Args:
            campaign_id: Campaign ID to add leads to
            leads: List of lead objects with email, firstName, lastName, etc.
            settings: Optional campaign settings (e.g., ignore_global_block_list)
        
        Returns:
            Response from Smartlead API
            
        Example lead format:
            {
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "company_name": "Acme Inc",
                "custom_fields": {...}
            }
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        if not leads:
            raise ValueError("No leads provided")
        
        # Format leads for Smartlead API
        formatted_leads = []
        for lead in leads:
            formatted_lead = {
                "email": lead.get("email", ""),
                "first_name": lead.get("first_name", lead.get("firstName", "")),
                "last_name": lead.get("last_name", lead.get("lastName", "")),
            }
            
            # Add optional fields
            if "company_name" in lead or "companyName" in lead:
                formatted_lead["company_name"] = lead.get("company_name", lead.get("companyName", ""))
            
            if "phone" in lead or "phone_number" in lead:
                formatted_lead["phone"] = lead.get("phone", lead.get("phone_number", ""))
            
            if "website" in lead:
                formatted_lead["website"] = lead["website"]
            
            if "linkedin_url" in lead or "linkedinUrl" in lead:
                formatted_lead["linkedin_url"] = lead.get("linkedin_url", lead.get("linkedinUrl", ""))
            
            # Add custom variables (everything else goes here)
            custom_fields = lead.get("custom_fields", {})
            for key, value in lead.items():
                if key not in ["email", "first_name", "firstName", "last_name", "lastName", 
                              "company_name", "companyName", "phone", "phone_number", 
                              "website", "linkedin_url", "linkedinUrl", "custom_fields"]:
                    custom_fields[key] = value
            
            if custom_fields:
                formatted_lead["custom_fields"] = custom_fields
            
            formatted_leads.append(formatted_lead)
        
        # Prepare request payload
        payload = {
            "campaign_id": campaign_id,
            "leads": formatted_leads,
        }
        
        # Add settings if provided
        if settings:
            payload.update(settings)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params={"api_key": self._api_key},
                    json=payload
                )
                
                if response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "data": response.json(),
                        "message": f"Successfully added {len(leads)} leads to campaign"
                    }
                else:
                    error_msg = f"Failed to add leads: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", error_msg)
                    except:
                        error_msg = response.text or error_msg
                    
                    logger.error(f"Smartlead add leads error: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "message": error_msg
                    }
        except Exception as e:
            logger.error(f"Error adding leads to Smartlead: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add leads: {str(e)}"
            }
    
    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific campaign by ID.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Campaign object or None
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}",
                    params={"api_key": self._api_key}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to fetch campaign: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching Smartlead campaign: {e}")
            return None

    async def get_campaign_leads(
        self, 
        campaign_id: str, 
        offset: int = 0, 
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get leads for a specific campaign.
        
        Args:
            campaign_id: Campaign ID
            offset: Pagination offset
            limit: Number of leads to fetch
            
        Returns:
            Dict with leads list and pagination info
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params={
                        "api_key": self._api_key,
                        "offset": offset,
                        "limit": limit
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return {"leads": data, "total": len(data)}
                    return data
                else:
                    logger.error(f"Failed to fetch campaign leads: {response.status_code}")
                    return {"leads": [], "total": 0}
        except Exception as e:
            logger.error(f"Error fetching Smartlead campaign leads: {e}")
            return {"leads": [], "total": 0}

    async def get_lead_by_email(
        self, 
        campaign_id: str, 
        email: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific lead by email from a campaign.
        
        Args:
            campaign_id: Campaign ID
            email: Lead's email address
            
        Returns:
            Lead object or None
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params={
                        "api_key": self._api_key,
                        "email": email
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    leads = data if isinstance(data, list) else data.get("leads", [])
                    for lead in leads:
                        if lead.get("email", "").lower() == email.lower():
                            return lead
                    return None
                else:
                    logger.error(f"Failed to fetch lead: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching Smartlead lead: {e}")
            return None

    async def get_email_thread(
        self, 
        campaign_id: str, 
        email: str
    ) -> List[Dict[str, Any]]:
        """Get email thread/conversation for a lead.
        
        Args:
            campaign_id: Campaign ID
            email: Lead's email address
            
        Returns:
            List of email messages in the thread
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Smartlead API endpoint for email history
                response = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads/{email}/message-history",
                    params={"api_key": self._api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    return data.get("messages", data.get("history", []))
                else:
                    logger.error(f"Failed to fetch email thread: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching email thread: {e}")
            return []

    async def get_campaign_statistics(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Campaign statistics
        """
        if not self._api_key:
            raise ValueError("API key not set")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/analytics",
                    params={"api_key": self._api_key}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to fetch campaign statistics: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching campaign statistics: {e}")
            return {}


# Global instance
smartlead_service = SmartleadService()
