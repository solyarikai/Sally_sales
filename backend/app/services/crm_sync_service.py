import asyncio
"""
CRM Sync Service - Unified sync for Smartlead and GetSales.

Provides:
- Full sync of contacts from both platforms
- Incremental sync of status changes and replies
- Activity tracking for all touches across channels
- Webhook handlers for real-time updates
"""
import os
import re
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models.contact import Contact, ContactActivity
from app.services.cache_service import acquire_sync_lock, release_sync_lock, bulk_check_replies, bulk_add_replies, add_processed_reply

logger = logging.getLogger(__name__)

# Known GetSales flow UUIDs -> names mapping (from webhook data)
GETSALES_FLOW_NAMES = {
    "b4188b80-4e23-47df-83cf-29d2654fc943": "EasyStaff - Russian DM [>500 connects]",
    "f62647b1-c054-4434-8402-7adac1c26e64": "Inxy - Russian DM's",
    "4bbd26d3-706b-4168-9262-d70fe09a5b25": "RIzzult_Wellness apps 10 01 26",
    "6bfeca8c-23a6-49da-a8e8-b0dacae88857": "Rizzult_shopping_apps",
}

def get_getsales_flow_name(activity_extra_data: dict = None, contact_campaigns: list = None) -> str:
    """
    Get the GetSales flow/automation name with fallback logic.
    
    Priority:
    1. activity.extra_data.automation_name
    2. activity.extra_data.flow_name  
    3. Most recent active GetSales campaign from contact.campaigns (with valid name)
    4. 'Unknown Flow' as last resort
    """
    import re
    
    def is_valid_flow_name(name: str) -> bool:
        """Check if flow name is a real campaign, not a placeholder, timestamp, or export automation."""
        if not name:
            return False
        if name.startswith("Unknown ("):
            return False
        # Filter out date/timestamp patterns (export automations like "3 Feb 2026, 02:42")
        if re.match(r'^\d{1,2} \w{3} \d{4},? \d{2}:\d{2}', name):
            return False
        # Filter out other export automation patterns
        if re.match(r'^\d{1,2} \w+ \d{4}', name):  # e.g. "3 February 2026"
            return False
        return True
    
    flow_name = None
    
    # Try activity extra_data first
    if activity_extra_data:
        candidate = activity_extra_data.get("automation_name") or activity_extra_data.get("flow_name")
        if is_valid_flow_name(candidate):
            flow_name = candidate
    
    # Fallback 1: Try to look up UUID in known flow names mapping
    if not flow_name and activity_extra_data:
        uuid = activity_extra_data.get("automation_uuid")
        if uuid and uuid in GETSALES_FLOW_NAMES:
            flow_name = GETSALES_FLOW_NAMES[uuid]
    
    # Fallback 2: Check contact campaigns for valid flow names
    if not flow_name and contact_campaigns:
        # First try to find UUID match in mapping
        for camp in contact_campaigns:
            if camp.get("source") == "getsales":
                camp_id = camp.get("id", "")
                if camp_id in GETSALES_FLOW_NAMES:
                    flow_name = GETSALES_FLOW_NAMES[camp_id]
                    break
        
        # Then try to find valid name by status priority
        if not flow_name:
            for status_priority in ["in_progress", "active", "ready", "restarted", "finished"]:
                for camp in contact_campaigns:
                    if camp.get("source") == "getsales" and camp.get("status") == status_priority:
                        name_candidate = camp.get("name", "")
                        if is_valid_flow_name(name_candidate):
                            flow_name = name_candidate
                            break
                if flow_name:
                    break
    
    return flow_name or "Unknown Flow"



def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn URL for matching (strip protocol, www, lowercase)."""
    if not url or url == '--':
        return None
    import re
    # Remove protocol and www
    normalized = re.sub(r'^https?://(www\.)?', '', url.lower())
    # Remove trailing slash
    normalized = normalized.rstrip('/')
    return normalized if normalized else None
def _truncate(value: str | None, max_len: int = 500) -> str | None:
    """Truncate string to max length to prevent varchar overflow."""
    if value is None:
        return None
    return str(value)[:max_len] if len(str(value)) > max_len else value




class SmartleadClient:
    """Client for Smartlead API."""
    
    BASE_URL = "https://server.smartlead.ai/api/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        await self.client.aclose()
    
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Smartlead API."""
        params = params or {}
        params["api_key"] = self.api_key
        resp = await self.client.get(f"{self.BASE_URL}{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def get_campaigns(self) -> List[dict]:
        """Get all campaigns. Smartlead returns all campaigns in one call (no pagination)."""
        data = await self._get("/campaigns")
        return data if isinstance(data, list) else data.get("data", [])
    
    async def get_campaign_leads(self, campaign_id: int, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get leads from a campaign."""
        data = await self._get(f"/campaigns/{campaign_id}/leads", {"limit": limit, "offset": offset})
        return data if isinstance(data, list) else data.get("data", [])
    
    async def get_global_leads(self, limit: int = 100, offset: int = 0) -> Tuple[List[dict], bool]:
        """Get global leads with hasMore flag."""
        data = await self._get("/leads/global-leads", {"limit": limit, "offset": offset})
        if isinstance(data, dict):
            return data.get("data", []), data.get("hasMore", False)
        return data, False
    
    async def get_lead_message_history(self, lead_id: int) -> List[dict]:
        """Get message history for a lead."""
        try:
            data = await self._get(f"/leads/{lead_id}/message-history")
            return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get message history for lead {lead_id}: {e}")
            return []
    
    async def get_campaign_statistics(self, campaign_id: int) -> dict:
        """Get campaign statistics including reply counts."""
        try:
            return await self._get(f"/campaigns/{campaign_id}/statistics")
        except Exception:
            return {}
    
    async def get_all_leads_with_status(self, status: str = "REPLIED", limit: int = 1000) -> List[dict]:
        """Get all leads with a specific status across campaigns."""
        all_leads = []
        offset = 0
        
        while len(all_leads) < limit:
            leads, has_more = await self.get_global_leads(limit=100, offset=offset)
            if not leads:
                break
            
            # Filter by status
            for lead in leads:
                campaigns = lead.get("campaigns", [])
                for camp in campaigns:
                    if camp.get("lead_status") == status:
                        all_leads.append(lead)
                        break
            
            offset += 100
            if not has_more:
                break
        
        return all_leads[:limit]
    
    # ============= Webhook Management =============
    
    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to Smartlead API."""
        params = {"api_key": self.api_key}
        resp = await self.client.post(f"{self.BASE_URL}{endpoint}", params=params, json=data)
        resp.raise_for_status()
        return resp.json()
    
    async def get_campaign_webhooks(self, campaign_id: int) -> List[dict]:
        """Get all webhooks for a campaign."""
        try:
            data = await self._get(f"/campaigns/{campaign_id}/webhooks")
            return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get webhooks for campaign {campaign_id}: {e}")
            return []
    
    async def create_campaign_webhook(
        self,
        campaign_id: int,
        webhook_url: str,
        webhook_name: str = "CRM Sync Webhook",
        event_types: List[str] = None
    ) -> dict:
        """
        Create a webhook for a Smartlead campaign.
        
        Args:
            campaign_id: Smartlead campaign ID
            webhook_url: URL to receive webhook POST requests
            webhook_name: Name for the webhook
            event_types: List of event types (default: EMAIL_REPLY, LEAD_CATEGORY_UPDATED)
        
        Returns:
            Created webhook data
        """
        if event_types is None:
            event_types = ["EMAIL_REPLY", "LEAD_CATEGORY_UPDATED", "EMAIL_SENT"]
        
        webhook_data = {
            "name": webhook_name,
            "webhook_url": webhook_url,
            "event_types": event_types
        }
        
        return await self._post(f"/campaigns/{campaign_id}/webhooks", webhook_data)
    
    async def setup_crm_webhooks(self, webhook_url: str) -> Dict[str, Any]:
        """
        Set up CRM webhooks for all active Smartlead campaigns.
        
        Args:
            webhook_url: Base URL for webhooks
        
        Returns:
            Dict with created/existing/failed/skipped counts
        """
        results = {"created": [], "existing": [], "failed": [], "skipped": []}
        
        try:
            campaigns = await self.get_campaigns()
            logger.info(f"Found {len(campaigns)} Smartlead campaigns")
            
            for campaign in campaigns:
                campaign_id = campaign.get("id")
                campaign_name = campaign.get("name", "Unknown")
                status = campaign.get("status", "").upper()
                
                # Skip inactive campaigns
                if status != "ACTIVE":
                    results["skipped"].append({"id": campaign_id, "name": campaign_name, "status": status})
                    continue
                
                try:
                    # Check if webhook already exists
                    existing_webhooks = await self.get_campaign_webhooks(campaign_id)
                    already_configured = False
                    
                    for wh in existing_webhooks:
                        if wh.get("webhook_url") == webhook_url:
                            already_configured = True
                            results["existing"].append({"id": campaign_id, "name": campaign_name})
                            break
                    
                    if not already_configured:
                        await self.create_campaign_webhook(
                            campaign_id=campaign_id,
                            webhook_url=webhook_url,
                            webhook_name=f"CRM Sync - {campaign_name[:30]}"
                        )
                        results["created"].append({"id": campaign_id, "name": campaign_name})
                        logger.info(f"Created Smartlead webhook for campaign: {campaign_name}")
                        
                except Exception as e:
                    results["failed"].append({"id": campaign_id, "name": campaign_name, "error": str(e)})
                    logger.warning(f"Failed to set up webhook for campaign {campaign_name}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to get Smartlead campaigns: {e}")
            results["error"] = str(e)
        
        return results


class GetSalesClient:
    """Client for GetSales API."""
    
    BASE_URL = "https://amazing.getsales.io"
    
    # Available webhook events
    WEBHOOK_EVENTS = [
        "contact_replied_linkedin_message",
        "contact_replied_email",
        "contact_enriched",
        "contact_linkedin_connection_accepted",
        "contact_linkedin_connection_requested",
    ]
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        await self.client.aclose()
    
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to GetSales API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        resp = await self.client.get(f"{self.BASE_URL}{endpoint}", headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to GetSales API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        resp = await self.client.post(f"{self.BASE_URL}{endpoint}", headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()
    
    async def _delete(self, endpoint: str) -> bool:
        """Make DELETE request to GetSales API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        resp = await self.client.delete(f"{self.BASE_URL}{endpoint}", headers=headers)
        return resp.status_code in (200, 204)
    
    async def get_lists(self) -> List[dict]:
        """Get all lists."""
        data = await self._get("/leads/api/lists")
        return data.get("data", [])
    
    async def get_flows(self) -> List[dict]:
        """Get all automations/flows."""
        data = await self._get("/flows/api/flows")
        return data.get("data", [])
    
    async def get_inbox_messages(self, limit: int = 100, offset: int = 0) -> Tuple[List[dict], bool, int]:
        """
        Get LinkedIn inbox messages (replies from contacts).
        
        Returns: (messages, has_more, total)
        """
        params = {
            "filter[type]": "inbox",
            "limit": limit,
            "offset": offset,
            "order_field": "created_at",
            "order_type": "desc"
        }
        data = await self._get("/flows/api/linkedin-messages", params)
        if isinstance(data, dict):
            return data.get("data", []), data.get("has_more", False), data.get("total", 0)
        return data, False, len(data)
    
    async def search_leads(self, filter_: dict = None, limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """Search leads with optional filters."""
        payload = {
            "filter": filter_ or {},
            "limit": limit,
            "offset": offset,
            "order_field": "created_at",
            "order_type": "desc"
        }
        data = await self._post("/leads/api/leads/search", payload)
        return data.get("data", []), data.get("total", 0)
    
    async def get_leads_by_list(self, list_uuid: str, limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """Get leads from a specific list."""
        return await self.search_leads({"list_uuid": list_uuid}, limit, offset)
    
    # ============= Webhook Management =============
    
    async def get_webhooks(self) -> List[dict]:
        """Get all configured webhooks."""
        data = await self._get("/integrations/api/webhooks")
        return data.get("data", [])
    
    async def create_webhook(
        self,
        name: str,
        target_url: str,
        event: str = "contact_replied_linkedin_message",
        flow_uuids: List[str] = None
    ) -> dict:
        """
        Create a new webhook.
        
        Args:
            name: Webhook name
            target_url: URL to receive webhook POST requests
            event: Event type (see WEBHOOK_EVENTS)
            flow_uuids: Optional list of flow UUIDs to filter (None = all flows)
        
        Returns:
            Created webhook data
        """
        payload = {
            "name": name,
            "event": event,
            "request_method": "POST",
            "target_url": target_url,
            "filters": {}
        }
        
        # Add flow filters if specified
        if flow_uuids:
            flow_filters = [{"flow_uuid": uuid} for uuid in flow_uuids]
            payload["filters"] = {
                "jsonLogic": {
                    "data": {"flows": flow_filters},
                    "logic": {"or": [
                        {"some": [{"var": "flows"}, {"==": [{"var": "flow_uuid"}, uuid]}]}
                        for uuid in flow_uuids
                    ]}
                }
            }
        
        return await self._post("/integrations/api/webhooks", payload)
    
    async def delete_webhook(self, webhook_uuid: str) -> bool:
        """Delete a webhook by UUID."""
        return await self._delete(f"/integrations/api/webhooks/{webhook_uuid}")
    
    async def setup_crm_webhooks(self, webhook_base_url: str) -> Dict[str, Any]:
        """
        Set up all CRM webhooks for GetSales.
        
        Creates webhooks for:
        - LinkedIn replies
        - Email replies (if supported)
        - Connection accepted
        
        Args:
            webhook_base_url: Base URL for webhooks (e.g., "http://your-domain.com/api/crm-sync/webhook/getsales")
        
        Returns:
            Dict with created/existing/failed counts
        """
        results = {"created": [], "existing": [], "failed": []}
        
        # Get existing webhooks
        existing = await self.get_webhooks()
        existing_urls = {wh.get("target_url"): wh for wh in existing}
        
        # Events to set up
        events_to_create = [
            ("CRM Sync - LinkedIn Replies", "contact_replied_linkedin_message"),
            ("CRM Sync - Connections", "contact_linkedin_connection_accepted"),
        ]
        
        for name, event in events_to_create:
            # Check if already exists
            if webhook_base_url in existing_urls:
                existing_wh = existing_urls[webhook_base_url]
                if existing_wh.get("event") == event:
                    results["existing"].append({"name": name, "event": event})
                    continue
            
            try:
                webhook = await self.create_webhook(
                    name=name,
                    target_url=webhook_base_url,
                    event=event
                )
                results["created"].append({
                    "name": name,
                    "event": event,
                    "uuid": webhook.get("uuid")
                })
                logger.info(f"Created GetSales webhook: {name} ({event})")
            except Exception as e:
                results["failed"].append({"name": name, "event": event, "error": str(e)})
                logger.error(f"Failed to create webhook {name}: {e}")
        
        return results


class CRMSyncService:
    """
    Main CRM sync service that orchestrates syncing from all sources.
    """
    
    def __init__(
        self,
        smartlead_api_key: str = None,
        getsales_api_key: str = None
    ):
        self.smartlead_key = smartlead_api_key or os.getenv("SMARTLEAD_API_KEY")
        self.getsales_key = getsales_api_key or os.getenv("GETSALES_API_KEY")
        
        self.smartlead = SmartleadClient(self.smartlead_key) if self.smartlead_key else None
        self.getsales = GetSalesClient(self.getsales_key) if self.getsales_key else None
    
    async def close(self):
        """Close all clients."""
        if self.smartlead:
            await self.smartlead.close()
        if self.getsales:
            await self.getsales.close()
    
    @staticmethod
    def normalize_email(email: str) -> Optional[str]:
        """Normalize email for matching."""
        if not email:
            return None
        return email.lower().strip()
    
    @staticmethod
    def normalize_linkedin(url: str) -> Optional[str]:
        """Normalize LinkedIn URL - extracts clean handle for matching."""
        if not url:
            return None
        url = url.lower().strip().rstrip("/")
        if "/in/" in url:
            handle = url.split("/in/")[-1].split("/")[0].split("?")[0].strip()
            return handle if handle else None
        # For non-standard formats, return cleaned URL
        return url
    
    async def sync_smartlead_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        limit: int = 50000
    ) -> Dict[str, int]:
        """
        Sync contacts from Smartlead.
        
        Returns dict with created, updated, skipped counts.
        """
        if not self.smartlead:
            raise ValueError("Smartlead API key not configured")
        
        stats = {"created": 0, "updated": 0, "skipped": 0, "activities": 0}
        offset = 0
        
        while stats["created"] + stats["updated"] + stats["skipped"] < limit:
            leads, has_more = await self.smartlead.get_global_leads(limit=100, offset=offset)
            
            if not leads:
                break
            
            for lead in leads:
                result = await self._process_smartlead_lead(session, company_id, lead)
                stats[result] += 1
            
            offset += 100
            if not has_more:
                break
            
            await session.commit()
        
        await session.commit()
        return stats
    
    async def _process_smartlead_lead(
        self,
        session: AsyncSession,
        company_id: int,
        lead: dict
    ) -> str:
        """Process a single Smartlead lead. Returns 'created', 'updated', or 'skipped'."""
        email = self.normalize_email(lead.get("email"))
        linkedin = self.normalize_linkedin(lead.get("linkedin_profile"))
        smartlead_id = str(lead.get("id"))
        
        if not email:
            return "skipped"
        
        # Find existing contact by smartlead_id, email, or linkedin
        existing = await self._find_contact(session, company_id, email, linkedin, smartlead_id=smartlead_id)
        
        # Determine status from campaigns
        campaigns = lead.get("campaigns", [])
        # Check for replies - either REPLIED status or has reply_time
        has_replied = any(
            c.get("lead_status") == "REPLIED" or c.get("reply_time") 
            for c in campaigns
        )
        smartlead_status = campaigns[0].get("lead_status") if campaigns else None
        campaign_names = [c.get("campaign_name") for c in campaigns if c.get("campaign_name")]
        
        if existing:
            # Update existing contact
            existing.smartlead_id = smartlead_id
            existing.smartlead_status = smartlead_status
            if has_replied and not existing.has_replied:
                existing.has_replied = True
                existing.reply_channel = "email"
                existing.status = "replied"
            if "smartlead" not in (existing.source or ""):
                if existing.source:
                    existing.source = f"{existing.source}+smartlead"
                else:
                    existing.source = "smartlead"
            # Merge campaign data
            existing_campaigns = existing.campaigns or []
            new_campaigns = [
                {
                    "name": c.get("campaign_name"),
                    "id": c.get("campaign_id"),
                    "source": "smartlead",
                    "status": c.get("lead_status")
                }
                for c in campaigns if c.get("campaign_name")
            ]
            # Merge without duplicates
            campaign_ids = {(c.get("id"), c.get("source")) for c in existing_campaigns}
            for nc in new_campaigns:
                if (nc.get("id"), nc.get("source")) not in campaign_ids:
                    existing_campaigns.append(nc)
            existing.campaigns = existing_campaigns if existing_campaigns else None
            existing.last_synced_at = datetime.utcnow()
            return "updated"
        else:
            # Create new contact
            custom_fields = lead.get("custom_fields", {})
            # Build campaign data
            campaign_data = [
                {
                    "name": c.get("campaign_name"),
                    "id": c.get("campaign_id"),
                    "source": "smartlead",
                    "status": c.get("lead_status")
                }
                for c in campaigns if c.get("campaign_name")
            ]
            contact = Contact(
                company_id=company_id,
                email=email,
                first_name=_truncate(lead.get("first_name"), 255),
                last_name=_truncate(lead.get("last_name"), 255),
                company_name=_truncate(lead.get("company_name"), 500),
                job_title=_truncate(custom_fields.get("Title") or custom_fields.get("title"), 500),
                phone=_truncate(lead.get("phone_number"), 100),
                linkedin_url=_truncate(lead.get("linkedin_profile"), 500),
                location=_truncate(lead.get("location"), 500),
                source="smartlead",
                smartlead_id=smartlead_id,
                smartlead_status=smartlead_status,
                has_replied=has_replied,
                status="replied" if has_replied else "lead",
                campaigns=campaign_data if campaign_data else None,
                last_synced_at=datetime.utcnow()
            )
            session.add(contact)
            return "created"
    
    async def sync_getsales_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        limit: int = 50000
    ) -> Dict[str, int]:
        """
        Sync contacts from GetSales.
        
        Returns dict with created, updated, skipped counts.
        """
        if not self.getsales:
            raise ValueError("GetSales API key not configured")
        
        stats = {"created": 0, "updated": 0, "skipped": 0, "activities": 0}
        
        # Get all lists
        lists = await self.getsales.get_lists()
        
        for lst in lists:
            list_uuid = lst.get("uuid")
            list_name = lst.get("name")
            offset = 0
            
            while True:
                leads, total = await self.getsales.get_leads_by_list(list_uuid, limit=100, offset=offset)
                
                if not leads:
                    break
                
                for item in leads:
                    result = await self._process_getsales_lead(session, company_id, item, list_name)
                    stats[result] += 1
                
                offset += 100
                if offset >= total:
                    break
            
            await session.commit()
        
        await session.commit()
        return stats
    
    async def _process_getsales_lead(
        self,
        session: AsyncSession,
        company_id: int,
        item: dict,
        list_name: str = None
    ) -> str:
        """Process a single GetSales lead. Returns 'created', 'updated', or 'skipped'."""
        lead = item.get("lead", {})
        
        email = self.normalize_email(lead.get("work_email") or lead.get("personal_email"))
        linkedin_raw = lead.get("linkedin")
        linkedin = self.normalize_linkedin(linkedin_raw)
        if linkedin_raw and not linkedin_raw.startswith("http"):
            linkedin_raw = f"https://linkedin.com/in/{linkedin_raw}"
        
        getsales_id = lead.get("uuid")
        
        if not email and not linkedin:
            return "skipped"
        
        # Find existing contact
        existing = await self._find_contact(session, company_id, email, linkedin, getsales_id=getsales_id)
        
        getsales_status = lead.get("status")
        
        if existing:
            # Update existing contact
            existing.getsales_id = getsales_id
            existing.getsales_status = getsales_status
            if not existing.linkedin_url and linkedin_raw:
                existing.linkedin_url = linkedin_raw
            if "getsales" not in (existing.source or ""):
                if existing.source:
                    existing.source = f"{existing.source}+getsales"
                else:
                    existing.source = "getsales"
            # Merge campaign data
            existing_campaigns = existing.campaigns or []
            new_campaigns = [
                {
                    "name": c.get("campaign_name"),
                    "id": c.get("campaign_id"),
                    "source": "smartlead",
                    "status": c.get("lead_status")
                }
                for c in campaigns if c.get("campaign_name")
            ]
            # Merge without duplicates
            campaign_ids = {(c.get("id"), c.get("source")) for c in existing_campaigns}
            for nc in new_campaigns:
                if (nc.get("id"), nc.get("source")) not in campaign_ids:
                    existing_campaigns.append(nc)
            existing.campaigns = existing_campaigns if existing_campaigns else None
            existing.last_synced_at = datetime.utcnow()
            return "updated"
        else:
            # Create new contact
            phone = lead.get("work_phone_number") or lead.get("personal_phone_number")
            location = lead.get("raw_address")
            
            contact = Contact(
                company_id=company_id,
                email=email or f"linkedin_{linkedin}@placeholder.local",  # Placeholder for LinkedIn-only contacts
                first_name=lead.get("first_name"),
                last_name=lead.get("last_name"),
                company_name=lead.get("company_name"),
                job_title=lead.get("position"),
                phone=phone,
                linkedin_url=linkedin_raw,
                location=location,
                source="getsales",
                getsales_id=getsales_id,
                getsales_status=getsales_status,
                status="lead",
                last_synced_at=datetime.utcnow()
            )
            session.add(contact)
            return "created"
    
    async def _find_contact(
        self,
        session: AsyncSession,
        company_id: int,
        email: str = None,
        linkedin: str = None,
        smartlead_id: str = None,
        getsales_id: str = None
    ) -> Optional[Contact]:
        """Find existing contact by various identifiers."""
        conditions = [
            Contact.company_id == company_id,
            Contact.deleted_at.is_(None)
        ]
        
        # Priority order: source_id > email > linkedin
        if smartlead_id:
            result = await session.execute(
                select(Contact).where(
                    and_(*conditions, Contact.smartlead_id == smartlead_id)
                )
            )
            contact = result.scalars().first()
            if contact:
                return contact
        
        if getsales_id:
            result = await session.execute(
                select(Contact).where(
                    and_(*conditions, Contact.getsales_id == getsales_id)
                )
            )
            contact = result.scalars().first()
            if contact:
                return contact
        
        if email:
            result = await session.execute(
                select(Contact).where(
                    and_(*conditions, func.lower(Contact.email) == email.lower())
                )
            )
            contact = result.scalars().first()
            if contact:
                return contact
        
        if linkedin:
            # Need to match normalized LinkedIn
            result = await session.execute(
                select(Contact).where(
                    and_(*conditions, Contact.linkedin_url.isnot(None))
                )
            )
            contacts = result.scalars().all()
            for c in contacts:
                if self.normalize_linkedin(c.linkedin_url) == linkedin:
                    return c
        
        return None
    
    async def sync_smartlead_replies(
        self,
        session: AsyncSession,
        company_id: int,
        since: datetime = None
    ) -> Dict[str, int]:
        """
        Sync reply activities from Smartlead using per-campaign approach.
        
        Iterates through ACTIVE and PAUSED campaigns to find replied leads.
        Uses Redis cache to avoid redundant DB queries.
        """
        if not self.smartlead:
            raise ValueError("Smartlead API key not configured")
        
        stats = {"new_replies": 0, "existing": 0, "cached": 0, "campaigns_checked": 0, "errors": 0}
        new_reply_ids = []
        
        try:
            # Get all campaigns
            campaigns = await self.smartlead.get_campaigns()
            logger.info(f"Reply sync: checking {len(campaigns)} campaigns")
            
            for campaign in campaigns:
                status = campaign.get("status", "").upper()
                campaign_id = campaign.get("id")
                campaign_name = campaign.get("name", "Unknown")
                
                # Only check ACTIVE and PAUSED campaigns
                if status not in ("ACTIVE", "PAUSED"):
                    continue
                
                stats["campaigns_checked"] += 1
                
                try:
                    # Fetch leads for this campaign (first 100 to limit API calls)
                    leads = await self.smartlead.get_campaign_leads(campaign_id, limit=100)
                    
                    # Filter to only replied leads first
                    replied_leads = []
                    for lead_data in leads:
                        has_reply = (
                            lead_data.get("reply_time") or 
                            lead_data.get("lead_status") == "REPLIED" or
                            lead_data.get("status") == "REPLIED"
                        )
                        if has_reply:
                            replied_leads.append(lead_data)
                    
                    if not replied_leads:
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Bulk check which leads are already cached
                    lead_ids = [str(ld.get("lead", ld).get("id")) for ld in replied_leads]
                    cached_ids = await bulk_check_replies("smartlead", lead_ids)
                    
                    for lead_data in replied_leads:
                        lead = lead_data.get("lead", lead_data)
                        email = self.normalize_email(lead.get("email"))
                        lead_id = str(lead.get("id"))
                        
                        # Check Redis cache first (fast path)
                        if lead_id in cached_ids:
                            stats["cached"] += 1
                            continue
                        
                        # Find contact
                        contact = await self._find_contact(
                            session, company_id, email=email, smartlead_id=lead_id
                        )
                        
                        if not contact:
                            new_reply_ids.append(lead_id)  # Still cache it
                            continue
                        
                        # Check if we already have this reply activity (fallback)
                        existing = await session.execute(
                            select(ContactActivity).where(
                                and_(
                                    ContactActivity.contact_id == contact.id,
                                    ContactActivity.activity_type == "email_replied",
                                    ContactActivity.source == "smartlead",
                                    ContactActivity.source_id == lead_id
                                )
                            )
                        )
                        
                        if existing.scalar_one_or_none():
                            stats["existing"] += 1
                            new_reply_ids.append(lead_id)  # Add to cache
                            continue
                        
                        # Create activity
                        activity = ContactActivity(
                            contact_id=contact.id,
                            company_id=company_id,
                            activity_type="email_replied",
                            channel="email",
                            direction="inbound",
                            source="smartlead",
                            source_id=lead_id,
                            extra_data={
                                "campaign_id": campaign_id,
                                "campaign_name": campaign_name
                            },
                            activity_at=datetime.fromisoformat(lead_data["reply_time"].replace("Z", "+00:00")) if lead_data.get("reply_time") else datetime.utcnow()
                        )
                        session.add(activity)
                        
                        # Update contact
                        contact.has_replied = True
                        contact.reply_channel = "email"
                        contact.last_reply_at = activity.activity_at
                        contact.status = "replied"
                        
                        stats["new_replies"] += 1
                        new_reply_ids.append(lead_id)
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(f"Error checking campaign {campaign_name}: {e}")
            
            await session.commit()
            
            # Bulk add new reply IDs to cache
            if new_reply_ids:
                await bulk_add_replies("smartlead", new_reply_ids)
            
            logger.info(f"Reply sync complete: {stats}")
            
        except Exception as e:
            logger.error(f"Reply sync failed: {e}")
            stats["error"] = str(e)
        
        return stats

    async def sync_getsales_replies(
        self,
        session: AsyncSession,
        company_id: int,
        max_pages: int = 10,
        page_size: int = 100,
        max_age_hours: int = 48,
        early_stop_threshold: int = 20
    ) -> Dict[str, int]:
        """
        Sync LinkedIn reply activities from GetSales inbox.
        
        Fetches inbox messages sorted by newest first, paginates until:
        - No more messages (has_more=False)
        - Hit max_pages limit
        - Messages are older than max_age_hours
        - Consecutive cached hits exceed early_stop_threshold
        
        Uses Redis cache to avoid redundant DB queries.
        """
        if not self.getsales:
            logger.warning("GetSales API key not configured")
            return {"skipped": "no_api_key"}
        
        stats = {"new_replies": 0, "existing": 0, "cached": 0, "no_contact": 0, "pages": 0}
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        consecutive_cached = 0
        new_reply_ids = []
        
        try:
            offset = 0
            stop_pagination = False
            
            while not stop_pagination and stats["pages"] < max_pages:
                # Fetch inbox messages (replies) sorted by newest first
                messages, has_more, total = await self.getsales.get_inbox_messages(
                    limit=page_size, offset=offset
                )
                stats["pages"] += 1
                
                if stats["pages"] == 1:
                    logger.info(f"GetSales reply sync: {total} total inbox messages")
                
                if not messages:
                    break
                
                # Bulk check which messages are already cached
                message_ids = [msg.get("uuid") or msg.get("id") for msg in messages if msg.get("uuid") or msg.get("id")]
                cached_ids = await bulk_check_replies("getsales", message_ids)
                
                for msg in messages:
                    # Check message age - stop if too old
                    created_at_str = msg.get("created_at")
                    if created_at_str:
                        msg_time = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        if msg_time < cutoff_time:
                            logger.info(f"GetSales reply sync: stopping at message from {msg_time} (older than {max_age_hours}h)")
                            stop_pagination = True
                            break
                    
                    message_id = msg.get("uuid") or msg.get("id")
                    
                    # Check Redis cache first (fast path)
                    if str(message_id) in cached_ids:
                        stats["cached"] += 1
                        consecutive_cached += 1
                        # Early stop if too many consecutive cached hits
                        if consecutive_cached >= early_stop_threshold:
                            logger.info(f"GetSales reply sync: early stop after {consecutive_cached} consecutive cached hits")
                            stop_pagination = True
                            break
                        continue
                    
                    # Reset consecutive counter on non-cached message
                    consecutive_cached = 0
                    
                    # Extract lead info
                    lead_uuid = msg.get("lead_uuid") or msg.get("lead", {}).get("uuid")
                    message_text = msg.get("text") or msg.get("body", "")
                    
                    if not lead_uuid:
                        continue
                    
                    # Find contact by getsales_id
                    contact = await self._find_contact(
                        session, company_id, getsales_id=lead_uuid
                    )
                    
                    if not contact:
                        stats["no_contact"] += 1
                        # Still cache it to avoid re-checking
                        new_reply_ids.append(message_id)
                        continue
                    
                    # Check if we already have this activity (fallback for cache miss)
                    existing = await session.execute(
                        select(ContactActivity).where(
                            and_(
                                ContactActivity.contact_id == contact.id,
                                ContactActivity.activity_type == "linkedin_replied",
                                ContactActivity.source == "getsales",
                                ContactActivity.source_id == str(message_id)
                            )
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        stats["existing"] += 1
                        # Add to cache for next time
                        new_reply_ids.append(message_id)
                        continue
                    
                    # Create activity
                    activity = ContactActivity(
                        contact_id=contact.id,
                        company_id=company_id,
                        activity_type="linkedin_replied",
                        channel="linkedin",
                        direction="inbound",
                        source="getsales",
                        source_id=str(message_id),
                        body=message_text,
                        snippet=message_text[:200] if message_text else None,
                        extra_data={
                            "sender_profile_uuid": msg.get("sender_profile_uuid"),
                            "linkedin_conversation_uuid": msg.get("linkedin_conversation_uuid"),
                            "linkedin_type": msg.get("linkedin_type"),
                            "automation": msg.get("automation")
                        },
                        activity_at=msg_time if created_at_str else datetime.utcnow()
                    )
                    session.add(activity)
                    
                    # Update contact
                    contact.has_replied = True
                    contact.reply_channel = "linkedin"
                    contact.last_reply_at = activity.activity_at
                    contact.status = "replied"
                    
                    stats["new_replies"] += 1
                    new_reply_ids.append(message_id)
                
                # Pagination
                if not has_more:
                    stop_pagination = True
                else:
                    offset += page_size
                    await asyncio.sleep(0.1)  # Rate limiting
            
            await session.commit()
            
            # Bulk add new reply IDs to cache
            if new_reply_ids:
                await bulk_add_replies("getsales", new_reply_ids)
            
            logger.info(f"GetSales reply sync complete: {stats}")
            
        except Exception as e:
            logger.error(f"GetSales reply sync failed: {e}")
            stats["error"] = str(e)
        
        return stats

    async def full_sync(
        self,
        session: AsyncSession,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Perform full sync from all sources.
        
        Uses Redis lock to prevent concurrent syncs.
        
        1. Sync all Smartlead contacts
        2. Sync all GetSales contacts  
        3. Sync Smartlead replies
        """
        results = {
            "smartlead": {"contacts": None, "replies": None},
            "getsales": {"contacts": None},
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None
        }
        
        # Try to acquire sync lock
        if not await acquire_sync_lock():
            results["error"] = "Sync already in progress"
            results["success"] = False
            results["skipped"] = True
            logger.warning("Sync skipped - another sync already in progress")
            return results
        
        try:
            if self.smartlead:
                logger.info("Syncing Smartlead contacts...")
                results["smartlead"]["contacts"] = await self.sync_smartlead_contacts(session, company_id)
                
                logger.info("Syncing Smartlead replies...")
                results["smartlead"]["replies"] = await self.sync_smartlead_replies(session, company_id)
            
            if self.getsales:
                logger.info("Syncing GetSales contacts...")
                results["getsales"]["contacts"] = await self.sync_getsales_contacts(session, company_id)
            
            results["completed_at"] = datetime.utcnow().isoformat()
            results["success"] = True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            results["error"] = str(e)
            results["success"] = False
        finally:
            # Always release the lock
            await release_sync_lock()
        
        return results


# Singleton instance
_crm_sync_service: Optional[CRMSyncService] = None


def get_crm_sync_service() -> CRMSyncService:
    """Get or create the CRM sync service singleton."""
    global _crm_sync_service
    if _crm_sync_service is None:
        _crm_sync_service = CRMSyncService()
    return _crm_sync_service
