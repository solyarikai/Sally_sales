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

    async def send_reply(
        self,
        campaign_id: str,
        lead_id: str,
        email_body: str,
    ) -> Dict[str, Any]:
        """Send a reply to a lead via SmartLead Master Inbox API.

        Fetches the message history to get required IDs, then posts the reply.

        Args:
            campaign_id: Campaign ID
            lead_id: SmartLead lead ID (numeric)
            email_body: HTML body of the reply

        Returns:
            dict with status and details
        """
        if not self._api_key:
            raise ValueError("API key not set")

        # 1. Get message history to find email_stats_id and last message
        async with httpx.AsyncClient(timeout=30.0) as client:
            hist_resp = await client.get(
                f"{self.base_url}/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                params={"api_key": self._api_key},
            )
            if hist_resp.status_code != 200:
                return {"error": f"Failed to fetch history: {hist_resp.status_code} {hist_resp.text}"}

            hist_data = hist_resp.json()
            messages = hist_data.get("history", [])
            if not messages:
                return {"error": "No message history found"}

            # Find the last inbound (REPLY) message to thread onto
            last_reply = None
            for msg in reversed(messages):
                if msg.get("type") == "REPLY":
                    last_reply = msg
                    break

            # Fall back to last message of any type
            if not last_reply:
                last_reply = messages[-1]

            email_stats_id = last_reply.get("stats_id") or messages[0].get("stats_id")
            reply_message_id = last_reply.get("message_id", "")
            reply_email_time = last_reply.get("time", "")
            reply_email_body = last_reply.get("email_body", "")

            # 2. Send reply
            send_resp = await client.post(
                f"{self.base_url}/campaigns/{campaign_id}/reply-email-thread",
                params={"api_key": self._api_key},
                json={
                    "email_stats_id": email_stats_id,
                    "email_body": email_body,
                    "reply_message_id": reply_message_id,
                    "reply_email_time": reply_email_time,
                    "reply_email_body": reply_email_body,
                },
            )

            if send_resp.status_code == 200:
                logger.info(f"Reply sent for lead {lead_id} in campaign {campaign_id}")
                return {"status": "queued", "message": send_resp.text}
            else:
                logger.error(f"Failed to send reply: {send_resp.status_code} {send_resp.text}")
                return {"error": f"Send failed: {send_resp.status_code}", "detail": send_resp.text}

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

    async def configure_campaign_webhook(
        self,
        campaign_id: str,
        webhook_url: str,
        webhook_name: str = "Auto-Replies Webhook"
    ) -> bool:
        """Configure a webhook for a Smartlead campaign."""
        if not self.api_key:
            logger.warning("Smartlead API key not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                # Check if webhook already exists
                resp = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/webhooks",
                    params={"api_key": self.api_key},
                    timeout=30.0
                )
                
                if resp.status_code == 200:
                    existing = resp.json()
                    for wh in existing:
                        if wh.get("webhook_url") == webhook_url:
                            logger.info(f"Webhook already configured for campaign {campaign_id}")
                            return True
                
                # Add new webhook
                webhook_data = {
                    "name": webhook_name,
                    "webhook_url": webhook_url,
                    "event_types": ["EMAIL_REPLY"]
                }
                
                resp = await client.post(
                    f"{self.base_url}/campaigns/{campaign_id}/webhooks",
                    params={"api_key": self.api_key},
                    json=webhook_data,
                    timeout=30.0
                )
                
                if resp.status_code == 200:
                    logger.info(f"Webhook configured for campaign {campaign_id}")
                    return True
                else:
                    logger.error(f"Failed to configure webhook: {resp.status_code} - {resp.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error configuring webhook for campaign {campaign_id}: {e}")
            return False


# Global instance
smartlead_service = SmartleadService()



async def sync_webhooks_on_startup():
    """Verify and re-register webhooks for all active automations on startup."""
    import logging
    from app.db import async_session_maker
    from app.models.reply import ReplyAutomation
    from sqlalchemy import select
    
    logger = logging.getLogger(__name__)
    logger.info("Syncing Smartlead webhooks for active automations...")
    
    webhook_url = "http://46.62.210.24:8000/api/smartlead/webhook"
    synced = 0
    failed = 0
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReplyAutomation).where(
                ReplyAutomation.is_active == True,
                ReplyAutomation.active == True
            )
        )
        automations = result.scalars().all()
        
        for automation in automations:
            for campaign_id in (automation.campaign_ids or []):
                try:
                    await smartlead_service.configure_campaign_webhook(
                        campaign_id=campaign_id,
                        webhook_url=webhook_url
                    )
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync webhook for campaign {campaign_id}: {e}")
                    failed += 1
    
    logger.info(f"Webhook sync complete: {synced} configured, {failed} failed")
    return {"synced": synced, "failed": failed}


async def fetch_all_campaign_replies(campaign_id: str, api_key: str, max_pages: int = 20) -> list:
    """Fetch all replies from a campaign using pagination.
    
    Args:
        campaign_id: Smartlead campaign ID
        api_key: Smartlead API key
        max_pages: Maximum pages to fetch (safety limit)
        
    Returns:
        List of statistics entries that have reply_time
    """
    import httpx
    
    all_replies = []
    offset = 0
    page_size = 500
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for page in range(max_pages):
            try:
                resp = await client.get(
                    f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                    params={"api_key": api_key, "limit": page_size, "offset": offset}
                )
                data = resp.json()
                entries = data.get("data", [])
                
                if not entries:
                    break
                
                # Filter for replies
                replies = [e for e in entries if e.get("reply_time")]
                all_replies.extend(replies)
                
                offset += page_size
                
                # Stop early if no replies found in last 2 pages
                if page > 2 and not replies:
                    consecutive_empty = True
                    break
                    
            except Exception as e:
                logger.warning(f"Error fetching page {page} for campaign {campaign_id}: {e}")
                break
    
    return all_replies
