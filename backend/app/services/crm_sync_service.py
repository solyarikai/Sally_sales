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
from sqlalchemy import select, and_, or_

from app.models.contact import Contact, ContactActivity

logger = logging.getLogger(__name__)


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
    
    async def get_campaigns(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get all campaigns."""
        data = await self._get("/campaigns", {"limit": limit, "offset": offset})
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
    
    async def setup_crm_webhooks(self, webhook_url: str, max_campaigns: int = 50) -> Dict[str, Any]:
        """
        Set up CRM webhooks for all active Smartlead campaigns.
        
        Args:
            webhook_url: Base URL for webhooks (e.g., "http://your-domain.com/api/crm-sync/webhook/smartlead")
            max_campaigns: Maximum number of campaigns to configure
        
        Returns:
            Dict with created/existing/failed counts
        """
        results = {"created": [], "existing": [], "failed": [], "skipped": []}
        
        try:
            campaigns = await self.get_campaigns(limit=max_campaigns)
            logger.info(f"Found {len(campaigns)} Smartlead campaigns")
            
            for campaign in campaigns:
                campaign_id = campaign.get("id")
                campaign_name = campaign.get("name", "Unknown")
                status = campaign.get("status", "").upper()
                
                # Skip inactive campaigns
                if status not in ("ACTIVE", "SCHEDULED", "PAUSED"):
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
    
    async def _get(self, endpoint: str) -> dict:
        """Make GET request to GetSales API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        resp = await self.client.get(f"{self.BASE_URL}{endpoint}", headers=headers)
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
        """Normalize LinkedIn URL for matching."""
        if not url:
            return None
        url = url.lower().strip().rstrip("/")
        if "/in/" in url:
            return url.split("/in/")[-1].split("/")[0].split("?")[0]
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
        has_replied = any(c.get("lead_status") == "REPLIED" for c in campaigns)
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
                    and_(*conditions, Contact.email == email)
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
        Sync reply activities from Smartlead.
        
        Fetches leads with REPLIED status and creates activities.
        """
        if not self.smartlead:
            raise ValueError("Smartlead API key not configured")
        
        stats = {"new_replies": 0, "existing": 0}
        
        # Get all replied leads
        replied_leads = await self.smartlead.get_all_leads_with_status("REPLIED", limit=1000)
        
        for lead in replied_leads:
            email = self.normalize_email(lead.get("email"))
            smartlead_id = str(lead.get("id"))
            
            # Find contact
            contact = await self._find_contact(
                session, company_id, email=email, smartlead_id=smartlead_id
            )
            
            if not contact:
                continue
            
            # Check if we already have this reply activity
            existing_activity = await session.execute(
                select(ContactActivity).where(
                    and_(
                        ContactActivity.contact_id == contact.id,
                        ContactActivity.activity_type == "email_replied",
                        ContactActivity.source == "smartlead",
                        ContactActivity.source_id == smartlead_id
                    )
                )
            )
            
            if existing_activity.scalar_one_or_none():
                stats["existing"] += 1
                continue
            
            # Get message history for reply content
            messages = await self.smartlead.get_lead_message_history(int(smartlead_id))
            
            # Find reply messages (from lead, not from us)
            for msg in messages:
                if msg.get("type") == "REPLY" or msg.get("direction") == "inbound":
                    activity = ContactActivity(
                        contact_id=contact.id,
                        company_id=company_id,
                        activity_type="email_replied",
                        channel="email",
                        direction="inbound",
                        source="smartlead",
                        source_id=str(msg.get("id", smartlead_id)),
                        subject=msg.get("subject"),
                        body=msg.get("body"),
                        snippet=msg.get("snippet") or (msg.get("body", "")[:200] if msg.get("body") else None),
                        metadata={
                            "campaign_id": lead.get("campaigns", [{}])[0].get("campaign_id") if lead.get("campaigns") else None,
                            "campaign_name": lead.get("campaigns", [{}])[0].get("campaign_name") if lead.get("campaigns") else None
                        },
                        activity_at=datetime.fromisoformat(msg.get("created_at")) if msg.get("created_at") else datetime.utcnow()
                    )
                    session.add(activity)
                    
                    # Update contact
                    contact.has_replied = True
                    contact.reply_channel = "email"
                    contact.last_reply_at = activity.activity_at
                    contact.status = "replied"
                    
                    stats["new_replies"] += 1
        
        await session.commit()
        return stats
    
    async def full_sync(
        self,
        session: AsyncSession,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Perform full sync from all sources.
        
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
        
        return results


# Singleton instance
_crm_sync_service: Optional[CRMSyncService] = None


def get_crm_sync_service() -> CRMSyncService:
    """Get or create the CRM sync service singleton."""
    global _crm_sync_service
    if _crm_sync_service is None:
        _crm_sync_service = CRMSyncService()
    return _crm_sync_service
