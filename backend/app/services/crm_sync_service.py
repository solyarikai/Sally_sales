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
import json
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text as sa_text

from app.models.contact import Contact, ContactActivity
from app.services.cache_service import acquire_sync_lock, release_sync_lock, bulk_check_replies, bulk_add_replies, add_processed_reply

logger = logging.getLogger(__name__)


def parse_campaigns(campaigns) -> list:
    """Normalize campaigns field to always return a list of dicts.
    
    Handles all storage formats found in the database:
    - None -> []
    - list of dicts -> returned as-is
    - JSON string (double-encoded by json.dumps before SQLAlchemy JSON column) -> parsed
    - Double-encoded string -> parsed twice
    """
    if campaigns is None:
        return []
    if isinstance(campaigns, list):
        return campaigns
    if isinstance(campaigns, str):
        try:
            parsed = json.loads(campaigns)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, str):
                # Double-encoded — parse again
                return json.loads(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    return []


# Keyword patterns for quick classification
KEYWORD_PATTERNS = {
    "not_interested": [
        "not interested", "не интересно", "no interest", "не актуально", 
        "not relevant", "не нужно", "not now", "пока нет", "не подходит"
    ],
    "meeting_request": [
        "какое время", "назначить", "schedule", "book", "calendar", "calendly",
        "meeting", "call", "созвон", "встреч", "zoom", "teams", "google meet"
    ],
    "interested": [
        "интересно", "interested", "давайте", "let's", "tell me more",
        "подробнее", "расскажите", "хотел бы", "would like", "sounds good"
    ],
    "out_of_office": [
        "out of office", "vacation", "отпуск", "away", "holiday", "auto-reply"
    ],
    "wrong_person": [
        "wrong person", "не тот", "уже не работаю", "no longer", "left the company"
    ],
    "unsubscribe": [
        "unsubscribe", "stop", "remove", "отписаться", "don't contact"
    ]
}

def classify_reply_by_keywords(text: str) -> str | None:
    """Quick keyword-based classification. Returns None if unclear."""
    if not text:
        return None
    text_lower = text.lower()
    for category, patterns in KEYWORD_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return category
    return None

async def classify_reply_with_ai(text: str) -> str:
    """AI classification using GPT-4o-mini. Called when keywords don't match."""
    import httpx
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "other"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Classify B2B reply into: interested, meeting_request, not_interested, out_of_office, wrong_person, question, other. Reply with ONLY the category."},
                        {"role": "user", "content": text[:500]}
                    ],
                    "max_tokens": 20,
                    "temperature": 0
                },
                timeout=10.0
            )
            data = response.json()
            category = data["choices"][0]["message"]["content"].strip().lower()
            valid = ["interested", "meeting_request", "not_interested", "out_of_office", "wrong_person", "question", "other"]
            return category if category in valid else "other"
    except Exception:
        return "other"

async def classify_reply(text: str) -> str:
    """Classify reply: keywords first, then AI if unclear."""
    category = classify_reply_by_keywords(text)
    if category:
        return category
    return await classify_reply_with_ai(text)

def get_status_from_category(category: str) -> str:
    """Map reply category to contact status (13-status funnel)."""
    from app.services.status_machine import status_from_ai_category
    return status_from_ai_category(category)

def get_sentiment_from_category(category: str) -> str:
    """Map reply category to sentiment."""
    if category in ("interested", "meeting_request", "question"):
        return "warm"
    elif category in ("not_interested", "unsubscribe", "wrong_person"):
        return "cold"
    else:
        return "neutral"

# Sender profile UUID / automation UUID -> project ID (DB-backed cache)
# Populated by refresh_project_prefixes() from Campaign table + project ownership rules.
GETSALES_UUID_TO_PROJECT: dict[str, int] = {}

# DB-backed cache: GetSales automation UUID -> campaign name.
# Populated from Campaign table by refresh_getsales_flow_cache().
# IMPORTANT: ONLY automation UUIDs go here (from webhook data).
# NEVER put sender_profile UUIDs here.
_getsales_flow_cache: Dict[str, str] = {}

# Backward-compat alias — all read sites use this name
GETSALES_FLOW_NAMES = _getsales_flow_cache


async def refresh_getsales_flow_cache():
    """Reload GetSales automation UUID→name mapping from Campaign table."""
    from app.db import async_session_maker
    from app.models.campaign import Campaign

    async with async_session_maker() as session:
        result = await session.execute(
            select(Campaign.external_id, Campaign.name).where(
                and_(
                    Campaign.platform == "getsales",
                    Campaign.external_id.isnot(None),
                )
            )
        )
        rows = result.all()

    _getsales_flow_cache.clear()
    for ext_id, name in rows:
        _getsales_flow_cache[ext_id] = name
    logger.info(f"[CACHE] Refreshed GetSales flow cache: {len(_getsales_flow_cache)} automations")


# DB-backed cache: campaign name prefix -> project_id (sorted by length DESC).
# Populated from project.campaign_ownership_rules by refresh_project_prefixes().
_project_prefixes: list[tuple[str, int]] = []  # [(prefix_lower, project_id)]
_project_contains: list[tuple[str, int]] = []  # [(substring_lower, project_id)]
_project_tags: dict[str, int] = {}  # {tag_lower: project_id}

# Backward-compat alias for imports — returns a dict view
_PROJECT_PREFIXES: Dict[str, int] = {}


async def refresh_project_prefixes():
    """Reload project prefix/contains/tag rules from campaign_ownership_rules column."""
    from app.db import async_session_maker
    from app.models.contact import Project

    async with async_session_maker() as session:
        result = await session.execute(
            select(Project.id, Project.name, Project.campaign_ownership_rules).where(
                Project.deleted_at.is_(None)
            )
        )
        projects = result.all()

    prefixes = []
    contains = []
    tags = {}
    compat_dict = {}

    for pid, pname, rules in projects:
        rules = rules or {}

        # Ownership rules: prefixes
        for prefix in rules.get("prefixes", []):
            p_lower = prefix.lower().strip()
            if p_lower:
                prefixes.append((p_lower, pid))
                compat_dict[p_lower] = pid

        # Ownership rules: contains
        for substr in rules.get("contains", []):
            s_lower = substr.lower().strip()
            if s_lower:
                contains.append((s_lower, pid))

        # Ownership rules: smartlead_tags
        for tag in rules.get("smartlead_tags", []):
            t_lower = tag.lower().strip()
            if t_lower:
                tags[t_lower] = pid

        # Implicit project name prefix (always active)
        if pname and len(pname) >= 3:
            p_lower = pname.lower()
            if p_lower not in compat_dict:
                prefixes.append((p_lower, pid))
                compat_dict[p_lower] = pid

    # Sort prefixes by length DESC (longest match wins)
    prefixes.sort(key=lambda x: len(x[0]), reverse=True)

    _project_prefixes.clear()
    _project_prefixes.extend(prefixes)
    _project_contains.clear()
    _project_contains.extend(contains)
    _project_tags.clear()
    _project_tags.update(tags)
    _PROJECT_PREFIXES.clear()
    _PROJECT_PREFIXES.update(compat_dict)

    # Rebuild GETSALES_UUID_TO_PROJECT from flow cache + prefix matching
    GETSALES_UUID_TO_PROJECT.clear()
    for uuid, name in _getsales_flow_cache.items():
        pid = match_campaign_to_project(name)
        if pid:
            GETSALES_UUID_TO_PROJECT[uuid] = pid

    logger.info(f"[CACHE] Refreshed project prefixes: {len(prefixes)} prefixes, {len(contains)} contains, {len(tags)} tags")


def match_campaign_to_project(campaign_name: str, campaign_tags: list[str] | None = None) -> int | None:
    """Match a campaign name (and optional tags) to a project using ownership rules.

    Evaluation order: tags > longest prefix > contains.
    Returns project_id or None.
    """
    if not campaign_name:
        return None

    # 1. Tag match (most explicit)
    if campaign_tags:
        for tag in campaign_tags:
            t_lower = tag.lower().strip()
            if t_lower in _project_tags:
                return _project_tags[t_lower]

    # 2. Prefix match (longest wins — list is pre-sorted)
    name_lower = campaign_name.lower()
    for prefix, pid in _project_prefixes:
        if name_lower.startswith(prefix):
            return pid

    # 3. Contains match
    for substr, pid in _project_contains:
        if substr in name_lower:
            return pid

    return None

# Sender profile UUID → human name (LinkedIn account owner).
# DISPLAY ONLY — never use for campaign routing or project classification.
# A sender can work across multiple projects (e.g. Pavel Medvedev sends
# for both EasyStaff RU and Rizzult).
GETSALES_SENDER_PROFILES: Dict[str, str] = {
    "b10a34f2-e7d0-490e-bc67-012b7ccd35b8": "Aliaksei Paretski",
    "4d1effeb-34fc-4999-bada-4a3651021adb": "Ekaterina Khoroshilova",
    "7f829fca-20b8-4f0d-a19e-ec1b3f76704e": "Eleonora Andreevna",
    "07d392a8-13bb-4a30-a86f-9fe692b7055a": "Andriy Kovalenko",
    "5ecc3a67-75f4-413d-96e7-ca256e3113e0": "Aliaksandr Blank",
    "774af09b-8158-4150-835d-6cf1ee00819a": "Sergey Lebedev",
    "d67e1028-cf06-4ae8-bcc3-16e41710f19c": "Alexandra Trifonova",
    "b3b69a39-6b46-4043-85b1-ef4ce22239d5": "Aliaksandra Vailunova",
    "cf73001d-f893-4396-b301-0691ffdccd12": "Andrei Paliaukou",
    "d4d17541-2b69-4cc3-acd5-cb39ce9df4b6": "Valeriia Mutalava",
    "4419a283-4c5f-4e2b-87cd-f892ef8a47be": "Marina Mikhaylova",
    "c58462db-beda-44a5-ba32-12e436d55bba": "Sophia Powell",
    "430e90e2-adfb-47d6-a986-3b8a75f4c80e": "Lera Yurkoits",
    "789eba43-d87f-4412-8f2a-20557f5bf5e2": "Eugene Sukhoi",
    "961b646e-c66b-44f4-b362-2c206669f4f4": "Ilia Andreev",
    "0d22a72e-5e30-4f72-bac7-0fac29fe8121": "Anna Reisberg",
    "4cbc70b5-4fb6-4a76-9088-f50a4ef096e7": "Robert Hershberger",
    "cdeb709c-17c6-4b31-ad6b-271354cdd3a9": "Dias Nurlanov",
    "29fd2e4e-d218-4ddc-b733-630e68a98124": "Pavel Medvedev",
    "448339f7-07c4-4766-b9e5-c09474196fe9": "Sergei Gvianidze",
    "94aeceb5-12ca-4ed6-92ac-18ed4b3d937f": "Lisa Woodard",
    "aab81b67-61c7-4cb9-b642-ad8584f69550": "Ruslan Zholik",
    "765a68b2-99ce-4279-b1ed-5ccdbecff83e": "Theodore Ulianov",
    "e6aaa00c-bf52-42b5-8c0e-40df920934b6": "Roman Ulyanov",
    "d5c18723-aca1-4ca4-84b8-60fdee894d67": "Albina Yanchanka",
    "2529a3dd-0dd1-4fc5-b4f3-7fdae203e454": "Elena Pugovishnikova",
    "25598cb7-f9d7-40e8-88f3-c8654759a8ab": "Tamara Bustamante",
    "fb194e54-d8c0-41ed-88e9-4acc0ef393b3": "Anna Reisberg",
    "d15d89ff-b985-4f2a-b222-dbf3b69601fe": "Petro Shevchenko",
    "b970588c-22ac-4393-934e-bd6dadf6a62c": "Daulet Issatayev",
    "e7cd7b0f-3683-4412-b7d7-0f9a22f0cc50": "Arina Kozlova",
    "de480494-6125-4f48-9cf0-fb05d0544c6f": "Maksim Anisimov",
    "8c7d77fa-5d07-4c7a-844d-8e833488eaa1": "Dmitry Isaev",
    "09f85665-1e7d-482c-9e8f-1c74d5d1ea15": "Nikita Melnikov",
    "7c58101c-675d-4ed3-9463-c39b03399d45": "Maxim Savichev",
    "41b709f2-6d25-46cc-91a5-7f15ce84f5a7": "Daniel Rew",
    "91fb80ab-4430-4b07-bc19-330d3f4ac8fd": "Elena Shamaeva",
    "abf28dba-0834-432b-a57d-b7fc03bb0db7": "Pavel Tikhonov",
    "d16d6837-4156-4022-bd38-51945de1bf4a": "Max Ionin",
    "b0399ffb-8f6e-47e4-b909-2b23847cf74c": "Jegors Zubarevs",
}



def _is_valid_campaign_name(name: str) -> bool:
    """Reject placeholders, timestamps, short flow codes, and export automation names."""
    import re
    if not name or name == "Unknown":
        return False
    if name.startswith("Unknown ("):
        return False
    if re.match(r'^\d{1,2} \w{3,9} \d{4}', name):
        return False
    if re.match(r'^\d{4}-\d{2}-\d{2}', name):
        return False
    # Reject short uppercase flow codes like "KYD3", "ABC1" (GetSales internal codes)
    if re.match(r'^[A-Z0-9]{2,8}$', name):
        return False
    return True


def get_getsales_flow_name(activity_extra_data: dict = None, contact_campaigns: list = None) -> str:
    """
    Get the GetSales flow/automation name with fallback logic.
    
    Priority:
    1. activity.extra_data.automation_name
    2. activity.extra_data.flow_name  
    3. Most recent active GetSales campaign from contact_campaigns (with valid name)
    4. 'Unknown Flow' as last resort
    """
    flow_name = None
    
    # Try activity extra_data first
    if activity_extra_data:
        candidate = activity_extra_data.get("automation_name") or activity_extra_data.get("flow_name")
        if _is_valid_campaign_name(candidate):
            flow_name = candidate
    
    # Fallback 1: Try to look up UUID in known flow names mapping
    if not flow_name and activity_extra_data:
        uuid = activity_extra_data.get("automation_uuid")
        if uuid and uuid in GETSALES_FLOW_NAMES:
            flow_name = GETSALES_FLOW_NAMES[uuid]
    
    # Fallback 2: Check contact campaigns for valid flow names
    contact_campaigns = parse_campaigns(contact_campaigns)
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
                        if _is_valid_campaign_name(name_candidate):
                            flow_name = name_candidate
                            break
                if flow_name:
                    break
    
    return flow_name or "Unknown Flow"



from app.utils.normalization import normalize_linkedin_url, truncate as _truncate




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
        from app.services.smartlead_service import smartlead_request
        params = params or {}
        params["api_key"] = self.api_key
        resp = await smartlead_request("GET", f"{self.BASE_URL}{endpoint}", params=params, client=self.client)
        resp.raise_for_status()
        return resp.json()
    
    _campaigns_cache: list | None = None
    _campaigns_cache_at: float = 0
    _CAMPAIGNS_CACHE_TTL = 1800  # 30 min

    async def get_campaigns(self, force_refresh: bool = False) -> List[dict]:
        """Get all campaigns with 30-min cache. SmartLead returns all in one call."""
        import time
        now = time.time()
        if not force_refresh and self._campaigns_cache and (now - self._campaigns_cache_at) < self._CAMPAIGNS_CACHE_TTL:
            return self._campaigns_cache
        data = await self._get("/campaigns")
        result = data if isinstance(data, list) else data.get("data", [])
        SmartleadClient._campaigns_cache = result
        SmartleadClient._campaigns_cache_at = now
        return result
    
    async def export_campaign_leads(self, campaign_id: str) -> List[dict]:
        """Export ALL leads from a campaign via CSV in one API call.

        Returns list of dicts with: id, email, first_name, last_name,
        company_name, phone_number, location, linkedin_profile,
        custom_fields (JSON string), created_at, status, reply_count, etc.

        Much faster than paginated /leads endpoint (1 call vs N×100).
        """
        import csv as csv_mod
        import io

        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/campaigns/{campaign_id}/leads-export",
                params={"api_key": self.api_key},
                timeout=120,
            )
            if resp.status_code != 200:
                return []

            reader = csv_mod.DictReader(io.StringIO(resp.text))
            return list(reader)
        except Exception as e:
            logger.warning(f"CSV export failed for campaign {campaign_id}: {e}")
            return []

    async def get_campaign_lead_count(self, campaign_id: str) -> int:
        """Get total lead count for a campaign (1 lightweight API call)."""
        try:
            data = await self._get(f"/campaigns/{campaign_id}/leads", {"limit": 1, "offset": 0})
            if isinstance(data, dict):
                return data.get("total_leads", data.get("total", 0))
            return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(f"Failed to get lead count for campaign {campaign_id}: {e}")
            return 0

    async def get_campaign_leads(self, campaign_id: int, limit: int = 100, offset: int = 0, lead_category_id: int = None) -> List[dict]:
        """Get leads from a campaign.
        
        Args:
            campaign_id: Campaign ID
            limit: Max leads to return
            offset: Pagination offset
            lead_category_id: Filter by category (9 = replied, 1-8 = other categories)
        """
        params = {"limit": limit, "offset": offset}
        if lead_category_id is not None:
            params["lead_category_id"] = lead_category_id
        data = await self._get(f"/campaigns/{campaign_id}/leads", params)
        return data if isinstance(data, list) else data.get("data", [])
    
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
    
    # ============= Webhook Management =============
    
    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to Smartlead API."""
        from app.services.smartlead_service import smartlead_request
        params = {"api_key": self.api_key}
        resp = await smartlead_request("POST", f"{self.BASE_URL}{endpoint}", params=params, json=data, client=self.client)
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
            event_types = ["EMAIL_REPLY", "LEAD_CATEGORY_UPDATED"]
        
        # Categories required for Smartlead to include reply body in webhook payload
        categories = [
            "Interested", "Meeting Request", "Not Interested", "Do Not Contact",
            "Information Request", "Out Of Office", "Wrong Person",
            "Uncategorizable by Ai", "Sender Originated Bounce", "Sample Sent",
            "Positive Reply", "Negative Reply", "Sample Reviewed", "Qualified",
            "Meeting Booked", "Not Now", "Not Qualified"
        ]
        
        webhook_data = {
            "name": webhook_name,
            "webhook_url": webhook_url,
            "event_types": event_types,
            "categories": categories
        }
        
        return await self._post(f"/campaigns/{campaign_id}/webhooks", webhook_data)

    async def _delete_campaign_webhook(self, campaign_id: int, webhook_id: int) -> bool:
        """Delete a specific webhook from a SmartLead campaign."""
        from app.services.smartlead_service import smartlead_request
        params = {"api_key": self.api_key}
        resp = await smartlead_request(
            "DELETE", f"{self.BASE_URL}/campaigns/{campaign_id}/webhooks/{webhook_id}",
            params=params, client=self.client
        )
        return resp.status_code in (200, 204)

    _verified_webhooks: dict = {}
    _VERIFIED_CACHE_TTL = 3600
    _VERIFIED_CACHE_MAX = 2000

    def _cache_verified(self, campaign_id):
        import time
        if len(self._verified_webhooks) >= self._VERIFIED_CACHE_MAX:
            oldest_key = min(self._verified_webhooks, key=self._verified_webhooks.get)
            del self._verified_webhooks[oldest_key]
        self._verified_webhooks[campaign_id] = time.time()

    def _is_verified(self, campaign_id) -> bool:
        import time
        ts = self._verified_webhooks.get(campaign_id)
        if ts is None:
            return False
        if (time.time() - ts) > self._VERIFIED_CACHE_TTL:
            del self._verified_webhooks[campaign_id]
            return False
        return True

    async def setup_crm_webhooks(self, webhook_url: str, skip_campaigns: set = None) -> Dict[str, Any]:
        """
        Set up CRM webhooks for active Smartlead campaigns.
        
        Uses a bounded TTL cache (max 2000 entries, 1h TTL) to skip
        re-verifying campaigns that already have a webhook.
        """
        import asyncio

        results = {"created": [], "existing": [], "failed": [], "skipped": [], "cached": []}
        skip_campaigns = skip_campaigns or set()

        try:
            campaigns = await self.get_campaigns()

            active = []
            for c in campaigns:
                cid = c.get("id")
                cname = c.get("name", "Unknown")
                status = (c.get("status") or "").upper()
                if status != "ACTIVE":
                    results["skipped"].append({"id": cid, "name": cname, "status": c.get("status")})
                    continue
                if not str(cid).isdigit():
                    results["skipped"].append({"id": cid, "name": cname, "reason": "non-numeric ID"})
                    continue
                if cname in skip_campaigns:
                    results["skipped"].append({"id": cid, "name": cname, "reason": "webhooks disabled for project"})
                    continue
                if self._is_verified(cid):
                    results["cached"].append({"id": cid, "name": cname})
                    results["existing"].append({"id": cid, "name": cname})
                    continue
                active.append(c)

            logger.info(f"Webhook check: {len(active)} new campaigns to verify, {len(results['cached'])} already verified")

            sem = asyncio.Semaphore(10)

            from urllib.parse import urlparse
            parsed_target = urlparse(webhook_url)
            our_host = parsed_target.netloc
            our_path = parsed_target.path  # e.g. /api/smartlead/webhook

            async def _check_one(campaign: dict):
                campaign_id = campaign.get("id")
                campaign_name = campaign.get("name", "Unknown")
                async with sem:
                    try:
                        existing_webhooks = await self.get_campaign_webhooks(campaign_id)
                        has_correct = False
                        stale_ids = []
                        for wh in existing_webhooks:
                            wh_url = wh.get("webhook_url", "")
                            parsed_wh = urlparse(wh_url)
                            if parsed_wh.netloc != our_host:
                                continue
                            if parsed_wh.path == our_path:
                                has_correct = True
                            else:
                                # Same host but wrong path — stale/broken webhook
                                stale_ids.append(wh.get("id"))
                        # Delete stale webhooks with wrong path
                        for stale_id in stale_ids:
                            try:
                                await self._delete_campaign_webhook(campaign_id, stale_id)
                                logger.info(f"Deleted stale webhook {stale_id} from campaign {campaign_id}")
                            except Exception as de:
                                logger.warning(f"Failed to delete stale webhook {stale_id}: {de}")
                        if has_correct:
                            results["existing"].append({"id": campaign_id, "name": campaign_name})
                            self._cache_verified(campaign_id)
                            return
                        await self.create_campaign_webhook(
                            campaign_id=campaign_id,
                            webhook_url=webhook_url,
                            webhook_name=f"CRM Sync - {campaign_name[:30]}"
                        )
                        results["created"].append({"id": campaign_id, "name": campaign_name})
                        self._cache_verified(campaign_id)
                    except Exception as e:
                        results["failed"].append({"id": campaign_id, "name": campaign_name, "error": str(e)})

            await asyncio.gather(*[_check_one(c) for c in active])

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
    
    def __init__(self, api_key: str, team_id: str = None):
        self.api_key = api_key
        self.team_id = team_id or os.getenv("GETSALES_TEAM_ID", "")
        self.client = httpx.AsyncClient(timeout=60.0)
        self._last_request_at = 0.0  # rate limiting: min 200ms between requests

    async def close(self):
        await self.client.aclose()

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.team_id:
            h["Team-Id"] = self.team_id
        return h

    async def _rate_limit(self):
        """Enforce minimum 200ms between API requests to avoid rate limits."""
        import time
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_request_at = time.monotonic()

    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to GetSales API."""
        await self._rate_limit()
        resp = await self.client.get(f"{self.BASE_URL}{endpoint}", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to GetSales API."""
        await self._rate_limit()
        resp = await self.client.post(f"{self.BASE_URL}{endpoint}", headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, endpoint: str) -> bool:
        """Make DELETE request to GetSales API."""
        await self._rate_limit()
        resp = await self.client.delete(f"{self.BASE_URL}{endpoint}", headers=self._headers())
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
    
    async def get_outbox_messages(self, limit: int = 100, offset: int = 0) -> Tuple[List[dict], bool, int]:
        """
        Get LinkedIn outbox messages (sent messages).
        
        Returns: (messages, has_more, total)
        """
        params = {
            "filter[type]": "outbox",
            "limit": limit,
            "offset": offset,
            "order_field": "created_at",
            "order_type": "desc"
        }
        data = await self._get("/flows/api/linkedin-messages", params)
        if isinstance(data, dict):
            return data.get("data", []), data.get("has_more", False), data.get("total", 0)
        return data, False, len(data)
    
    async def get_all_messages(self, limit: int = 100, offset: int = 0, order_asc: bool = False) -> Tuple[List[dict], bool, int]:
        """
        Get ALL LinkedIn messages (both inbox and outbox).
        
        Args:
            order_asc: If True, order by created_at ASC (oldest first) for historical sync
        
        Returns: (messages, has_more, total)
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order_field": "created_at",
            "order_type": "asc" if order_asc else "desc"
        }
        data = await self._get("/flows/api/linkedin-messages", params)
        if isinstance(data, dict):
            return data.get("data", []), data.get("has_more", False), data.get("total", 0)
        return data, False, len(data)
    
    async def get_conversation_messages(self, conversation_uuid: str, limit: int = 100) -> List[dict]:
        """
        Get all messages in a specific LinkedIn conversation.
        
        Args:
            conversation_uuid: The linkedin_conversation_uuid
            
        Returns: List of messages in the conversation (both sent and received)
        """
        params = {
            "filter[linkedin_conversation_uuid]": conversation_uuid,
            "limit": limit,
            "order_field": "created_at",
            "order_type": "asc"  # Chronological order
        }
        data = await self._get("/flows/api/linkedin-messages", params)
        if isinstance(data, dict):
            return data.get("data", [])
        return data
    
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

    async def get_data_sources(self) -> List[dict]:
        """Get all data sources (lead import batches)."""
        data = await self._get("/leads/api/data-sources")
        return data if isinstance(data, list) else data.get("data", [])
    
    async def get_leads_by_list(self, list_uuid: str, limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """Get leads from a specific list."""
        return await self.search_leads({"list_uuid": list_uuid}, limit, offset)
    
    # ============= Sending Messages =============

    async def send_linkedin_message(
        self,
        sender_profile_uuid: str,
        lead_uuid: str,
        text: str,
    ) -> dict:
        """Send a LinkedIn message via GetSales API.

        Args:
            sender_profile_uuid: UUID of the sender profile (LinkedIn account)
            lead_uuid: UUID of the lead/contact to message
            text: Message text to send

        Returns:
            API response dict with message details
        """
        last_err = None
        for attempt in range(3):
            try:
                return await self._post("/flows/api/linkedin-messages", {
                    "sender_profile_uuid": sender_profile_uuid,
                    "lead_uuid": lead_uuid,
                    "text": text,
                })
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    wait = (attempt + 1) * 2  # 2s, 4s
                    logger.warning(f"[GETSALES] Send retry {attempt + 1}/3 after {e.response.status_code}, waiting {wait}s")
                    await asyncio.sleep(wait)
                    last_err = e
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < 2:
                    wait = (attempt + 1) * 2
                    logger.warning(f"[GETSALES] Send retry {attempt + 1}/3 after {type(e).__name__}, waiting {wait}s")
                    await asyncio.sleep(wait)
                    last_err = e
                    continue
                raise
        raise last_err  # should not reach here

    @staticmethod
    def build_inbox_url(lead_uuid: str, sender_profile_uuid: str = "") -> str:
        """Construct GetSales messenger URL for a specific lead conversation."""
        base = f"https://amazing.getsales.io/messenger/{lead_uuid}"
        if sender_profile_uuid:
            from urllib.parse import quote
            base += f'?senderProfileId={quote(chr(34) + sender_profile_uuid + chr(34))}'
        return base

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
        from app.utils.normalization import normalize_email
        return normalize_email(email)
    
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
        limit: int = 50000,
        only_campaigns: set = None,
    ) -> Dict[str, int]:
        """Sync contacts from SmartLead using per-campaign CSV export.

        Uses /campaigns/{id}/leads-export (full CSV in one API call per campaign)
        instead of paginated global-leads. ~795 API calls vs 6000+ paginated calls.

        When only_campaigns is set, skips contact sync (contacts are created
        during reply processing instead).
        """
        if not self.smartlead:
            raise ValueError("Smartlead API key not configured")

        if only_campaigns:
            logger.info(f"Smartlead contact sync skipped (scoped mode: {len(only_campaigns)} campaigns)")
            return {"created": 0, "updated": 0, "skipped": 0, "scoped": True}

        import json as json_mod
        from app.models.campaign import Campaign

        stats = {"created": 0, "updated": 0, "skipped": 0}

        # Get campaigns with leads, ordered by leads_count desc (biggest first)
        camp_result = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.platform == "smartlead",
                    Campaign.external_id.isnot(None),
                    func.coalesce(Campaign.leads_count, 0) > 0,
                )
            ).order_by(Campaign.leads_count.desc())
        )
        campaigns = camp_result.scalars().all()
        logger.info(f"[SL-SYNC] Syncing {len(campaigns)} campaigns via CSV export")

        for idx, camp in enumerate(campaigns):
            csv_rows = await self.smartlead.export_campaign_leads(camp.external_id)

            # Update leads_count and synced_leads_count from actual export
            actual_count = len(csv_rows)
            if actual_count > 0 and actual_count != (camp.leads_count or 0):
                camp.leads_count = actual_count
            if actual_count > 0:
                camp.synced_leads_count = actual_count
                camp.last_contact_sync_at = datetime.utcnow()

            if not csv_rows:
                await asyncio.sleep(0.3)
                continue

            # Convert CSV rows to lead dicts compatible with _process_smartlead_lead
            for row in csv_rows:
                try:
                    custom_fields_raw = row.get("custom_fields", "{}")
                    try:
                        custom_fields = json_mod.loads(custom_fields_raw) if custom_fields_raw else {}
                    except (json_mod.JSONDecodeError, TypeError):
                        custom_fields = {}

                    reply_count = int(row.get("reply_count", 0) or 0)
                    lead = {
                        "id": row.get("id", ""),
                        "email": row.get("email", ""),
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "company_name": row.get("company_name", ""),
                        "phone_number": row.get("phone_number", ""),
                        "linkedin_profile": row.get("linkedin_profile", ""),
                        "location": row.get("location", ""),
                        "custom_fields": custom_fields,
                        "created_at": row.get("created_at", ""),
                        "campaigns": [{
                            "campaign_name": camp.name,
                            "campaign_id": camp.external_id,
                            "lead_status": row.get("status", "ACTIVE"),
                            "created_at": row.get("created_at", ""),
                            "reply_time": True if reply_count > 0 else None,
                        }],
                    }
                    result = await self._process_smartlead_lead(
                        session, company_id, lead, campaign_project_id=camp.project_id
                    )
                    stats[result] += 1
                except Exception:
                    stats["skipped"] += 1

            await session.commit()

            total = stats["created"] + stats["updated"] + stats["skipped"]
            if (idx + 1) % 50 == 0 or idx < 3:
                logger.info(
                    f"[SL-SYNC] {idx+1}/{len(campaigns)} campaigns, "
                    f"created={stats['created']}, updated={stats['updated']}, skipped={stats['skipped']}"
                )

            if total >= limit:
                break
            await asyncio.sleep(0.5)

        await session.commit()
        logger.info(
            f"[SL-SYNC] Complete: {len(campaigns)} campaigns, "
            f"created={stats['created']}, updated={stats['updated']}, skipped={stats['skipped']}"
        )
        return stats

    async def sync_smartlead_contacts_delta(
        self,
        session: AsyncSession,
        company_id: int,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """Delta sync: check lead counts for a batch of campaigns, export only changed ones.

        Round-robin: each cycle checks ``batch_size`` campaigns ordered by
        ``last_contact_sync_at`` (oldest first, NULLs first so new campaigns
        get checked immediately).  Full rotation across all active campaigns
        takes ~100 min at default settings.

        Returns stats dict with campaigns_checked, campaigns_synced, created, updated.
        """
        if not self.smartlead:
            return {"error": "SmartLead not configured"}

        import json as json_mod
        from app.models.campaign import Campaign

        # Get next batch of campaigns to check (round-robin by last_contact_sync_at)
        result = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.platform == "smartlead",
                    Campaign.external_id.isnot(None),
                    Campaign.project_id.isnot(None),
                    Campaign.status == "active",
                )
            ).order_by(
                Campaign.last_contact_sync_at.asc().nullsfirst()
            ).limit(batch_size)
        )
        batch = result.scalars().all()
        if not batch:
            return {"campaigns_checked": 0, "campaigns_synced": 0, "created": 0, "updated": 0}

        # Phase 1: Quick count checks (1 API call per campaign, ~15s for 50)
        need_sync = []
        for camp in batch:
            try:
                sl_count = await self.smartlead.get_campaign_lead_count(camp.external_id)
                our_count = camp.synced_leads_count or camp.leads_count or 0
                if sl_count > our_count:
                    need_sync.append((camp, sl_count))
                    logger.info(
                        f"[SL-DELTA] {camp.name[:40]}: {our_count} → {sl_count} (+{sl_count - our_count})"
                    )
                # Mark as checked regardless
                camp.last_contact_sync_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"[SL-DELTA] Count check failed for {camp.name[:30]}: {e}")
            await asyncio.sleep(0.3)

        if not need_sync:
            await session.commit()
            logger.info(f"[SL-DELTA] Checked {len(batch)} campaigns, no changes")
            return {"campaigns_checked": len(batch), "campaigns_synced": 0, "created": 0, "updated": 0}

        # Phase 2: Export CSV and process only changed campaigns
        stats = {"created": 0, "updated": 0, "skipped": 0}
        for camp, sl_count in need_sync:
            csv_rows = await self.smartlead.export_campaign_leads(camp.external_id)
            actual_count = len(csv_rows)
            if actual_count > 0:
                camp.leads_count = actual_count
                camp.synced_leads_count = actual_count

            for row in csv_rows:
                try:
                    custom_fields_raw = row.get("custom_fields", "{}")
                    try:
                        custom_fields = json_mod.loads(custom_fields_raw) if custom_fields_raw else {}
                    except (json_mod.JSONDecodeError, TypeError):
                        custom_fields = {}
                    reply_count = int(row.get("reply_count", 0) or 0)
                    lead = {
                        "id": row.get("id", ""),
                        "email": row.get("email", ""),
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "company_name": row.get("company_name", ""),
                        "phone_number": row.get("phone_number", ""),
                        "linkedin_profile": row.get("linkedin_profile", ""),
                        "location": row.get("location", ""),
                        "custom_fields": custom_fields,
                        "created_at": row.get("created_at", ""),
                        "campaigns": [{
                            "campaign_name": camp.name,
                            "campaign_id": camp.external_id,
                            "lead_status": row.get("status", "ACTIVE"),
                            "created_at": row.get("created_at", ""),
                            "reply_time": True if reply_count > 0 else None,
                        }],
                    }
                    action = await self._process_smartlead_lead(
                        session, company_id, lead, campaign_project_id=camp.project_id
                    )
                    stats[action] += 1
                except Exception:
                    stats["skipped"] += 1

            await session.commit()
            logger.info(
                f"[SL-DELTA] Synced '{camp.name[:40]}': {actual_count} leads "
                f"(+{stats['created']} new, {stats['updated']} updated)"
            )
            await asyncio.sleep(0.5)

        logger.info(
            f"[SL-DELTA] Done: checked {len(batch)}, synced {len(need_sync)} campaigns, "
            f"created={stats['created']}, updated={stats['updated']}"
        )
        return {
            "campaigns_checked": len(batch),
            "campaigns_synced": len(need_sync),
            **stats,
        }

    async def _process_smartlead_lead(
        self,
        session: AsyncSession,
        company_id: int,
        lead: dict,
        campaign_project_id: int = None,
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
        # Check for replies - either REPLIED status, has reply_time,
        # OR has entries in processed_replies table (critical fix: this was missing,
        # causing 97%+ of replied contacts to have has_replied=false)
        has_replied = any(
            c.get("lead_status") == "REPLIED" or c.get("reply_time") 
            for c in campaigns
        )
        
        # Cross-reference with processed_replies table for definitive reply check
        if not has_replied and email:
            from app.models.reply import ProcessedReply
            reply_check = await session.execute(
                select(ProcessedReply.id).where(
                    ProcessedReply.lead_email == email
                ).limit(1)
            )
            if reply_check.scalar():
                has_replied = True
                logger.info(f"[SYNC] Found reply in processed_replies for {email} (campaign status didn't reflect it)")
        smartlead_status = campaigns[0].get("lead_status") if campaigns else None
        campaign_names = [c.get("campaign_name") for c in campaigns if c.get("campaign_name")]
        
        if existing:
            # Update existing contact
            existing.smartlead_id = smartlead_id
            existing.update_platform_status("smartlead", smartlead_status)
            if campaign_project_id and not existing.project_id:
                existing.project_id = campaign_project_id
            if not existing.domain and email and '@' in email:
                existing.domain = email.split('@')[1].lower()
            # Upgrade placeholder email with real email from Smartlead
            if email and existing.email and any(
                p in existing.email for p in ("@linkedin.placeholder", "@getsales.local", "@placeholder.local")
            ):
                logger.info(f"[SYNC] Upgrading placeholder email {existing.email} -> {email}")
                existing.email = email
                if '@' in email:
                    existing.domain = email.split('@')[1].lower()
            if has_replied and not existing.last_reply_at:
                existing.mark_replied("email")
                existing.status = "replied"
            if "smartlead" not in (existing.source or ""):
                if existing.source:
                    existing.source = f"{existing.source}+smartlead"
                else:
                    existing.source = "smartlead"
            # Merge campaign data into platform_state
            existing_campaigns = existing.get_platform("smartlead").get("campaigns", [])
            new_campaigns = [
                {
                    "name": c.get("campaign_name"),
                    "id": c.get("campaign_id"),
                    "source": "smartlead",
                    "status": c.get("lead_status"),
                    "added_at": c.get("created_at") or lead.get("created_at"),
                }
                for c in campaigns if c.get("campaign_name")
            ]
            campaign_ids = {c.get("id") if isinstance(c, dict) else c for c in existing_campaigns}
            for nc in new_campaigns:
                if nc.get("id") not in campaign_ids:
                    existing_campaigns.append(nc)
            existing_campaigns = [c for c in existing_campaigns if isinstance(c, dict)]
            if existing_campaigns:
                existing.set_platform("smartlead", {"campaigns": existing_campaigns})
            existing.mark_synced("smartlead")
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
                    "status": c.get("lead_status"),
                    "added_at": c.get("created_at") or lead.get("created_at"),
                }
                for c in campaigns if c.get("campaign_name")
            ]
            contact = Contact(
                company_id=company_id,
                project_id=campaign_project_id,
                email=email,
                domain=email.split('@')[1].lower() if email and '@' in email else None,
                first_name=_truncate(lead.get("first_name"), 255),
                last_name=_truncate(lead.get("last_name"), 255),
                company_name=_truncate(lead.get("company_name"), 500),
                job_title=_truncate(custom_fields.get("Title") or custom_fields.get("title"), 500),
                phone=_truncate(lead.get("phone_number"), 100),
                linkedin_url=_truncate(lead.get("linkedin_profile"), 500),
                location=_truncate(lead.get("location"), 500),
                source="smartlead",
                smartlead_id=smartlead_id,
                last_reply_at=datetime.utcnow() if has_replied else None,
                status="replied" if has_replied else "lead",
            )
            session.add(contact)
            contact.update_platform_status("smartlead", smartlead_status)
            if campaign_data:
                contact.set_platform("smartlead", {"campaigns": campaign_data})
            return "created"
    
    async def sync_getsales_contacts_full(
        self,
        session: AsyncSession,
        company_id: int,
        limit: int = 50000
    ) -> Dict[str, int]:
        """
        Full sync of ALL contacts from GetSales (used for daily reconciliation).

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
        list_name: str = None,
        campaign_project_id: int = None,
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

        # Auto-detect project from flow names or list name if not explicitly set
        if not campaign_project_id:
            # Check flow names against ownership rules
            for flow in item.get("flows", []):
                flow_uuid = flow.get("flow_uuid", "")
                flow_name = _getsales_flow_cache.get(flow_uuid, "")
                if flow_name:
                    pid = match_campaign_to_project(flow_name)
                    if pid:
                        campaign_project_id = pid
                        break
            # Fallback: check list name
            if not campaign_project_id and list_name:
                campaign_project_id = match_campaign_to_project(list_name)

        # Find existing contact
        existing = await self._find_contact(session, company_id, email, linkedin, getsales_id=getsales_id)

        getsales_status = lead.get("status")

        if existing:
            # Update existing contact
            existing.getsales_id = getsales_id
            existing.update_platform_status("getsales", getsales_status)
            if campaign_project_id and not existing.project_id:
                existing.project_id = campaign_project_id
            if not existing.domain and email and '@' in email:
                existing.domain = email.split('@')[1].lower()
            if not existing.linkedin_url and linkedin_raw:
                existing.linkedin_url = linkedin_raw
            if "getsales" not in (existing.source or ""):
                if existing.source:
                    existing.source = f"{existing.source}+getsales"
                else:
                    existing.source = "getsales"
            # Merge campaign data into platform_state
            existing_campaigns = existing.get_platform("getsales").get("campaigns", [])
            new_campaigns = []
            if list_name:
                new_campaigns.append({
                    "name": list_name,
                    "id": item.get("uuid") or lead.get("uuid"),
                    "source": "getsales",
                    "status": getsales_status
                })
            campaign_ids = {c.get("id") if isinstance(c, dict) else c for c in existing_campaigns}
            for nc in new_campaigns:
                if nc.get("id") not in campaign_ids:
                    existing_campaigns.append(nc)
            existing_campaigns = [c for c in existing_campaigns if isinstance(c, dict)]
            if existing_campaigns:
                existing.set_platform("getsales", {"campaigns": existing_campaigns})
            existing.mark_synced("getsales")
            return "updated"
        else:
            # Create new contact
            phone = lead.get("work_phone_number") or lead.get("personal_phone_number")
            location = lead.get("raw_address")

            # Build campaign data from list_name
            campaign_data = None
            if list_name:
                campaign_data = [{
                    "name": list_name,
                    "id": item.get("uuid") or lead.get("uuid"),
                    "source": "getsales",
                    "status": getsales_status
                }]

            # Use a more descriptive placeholder email with getsales_id for traceability
            # This makes it clear this is a LinkedIn-only contact and aids debugging
            actual_email = email or f"gs_{getsales_id or linkedin}@linkedin.placeholder"
            contact = Contact(
                company_id=company_id,
                project_id=campaign_project_id,
                email=actual_email,
                domain=email.split('@')[1].lower() if email and '@' in email else None,
                first_name=lead.get("first_name"),
                last_name=lead.get("last_name"),
                company_name=lead.get("company_name"),
                job_title=lead.get("position"),
                phone=phone,
                linkedin_url=linkedin_raw,
                location=location,
                source="getsales",
                getsales_id=getsales_id,
                status="lead",
            )
            contact.update_platform_status("getsales", getsales_status)
            if campaign_data:
                contact.set_platform("getsales", {"campaigns": campaign_data})
            contact.mark_synced("getsales")
            session.add(contact)
            return "created"

    async def sync_getsales_contacts_incremental(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> Dict[str, Any]:
        """
        Incremental sync: only fetch NEW contacts since last check.

        Stores {list_uuid: last_known_total} in Redis. Each cycle:
        1. Fetch all lists (1 API call)
        2. For each list, get current total (1 API call each)
        3. If total increased, scan only the delta (newest-first)
        4. Update stored totals

        Returns dict with stats + api_calls count.
        """
        from app.services.cache_service import cache_service

        if not self.getsales:
            raise ValueError("GetSales API key not configured")

        stats = {"created": 0, "updated": 0, "skipped": 0, "api_calls": 0, "lists_scanned": 0, "delta_contacts": 0}

        # Load stored totals from Redis
        REDIS_KEY = "leadgen:getsales:list_totals"
        stored_totals = await cache_service.get(REDIS_KEY) or {}

        # Fetch all lists
        lists = await self.getsales.get_lists()
        stats["api_calls"] += 1

        new_totals = {}

        for lst in lists:
            list_uuid = lst.get("uuid")
            list_name = lst.get("name")
            if not list_uuid:
                continue

            # Get current total with a minimal query (limit=1)
            _, current_total = await self.getsales.search_leads(
                {"list_uuid": list_uuid}, limit=1, offset=0
            )
            stats["api_calls"] += 1
            new_totals[list_uuid] = current_total

            previous_total = stored_totals.get(list_uuid, 0)
            delta = current_total - previous_total

            if delta <= 0:
                # No new contacts (or contacts removed — reconciliation handles that)
                continue

            # Scan the delta — API returns newest-first, so offset=0..delta gets new contacts
            stats["lists_scanned"] += 1
            logger.info(f"[DELTA-SYNC] List '{list_name}': {previous_total} -> {current_total} (+{delta} new)")

            offset = 0
            while offset < delta:
                batch_size = min(100, delta - offset)
                leads, _ = await self.getsales.get_leads_by_list(
                    list_uuid, limit=batch_size, offset=offset
                )
                stats["api_calls"] += 1

                if not leads:
                    break

                for item in leads:
                    result = await self._process_getsales_lead(session, company_id, item, list_name)
                    stats[result] += 1
                    stats["delta_contacts"] += 1

                offset += len(leads)

            await session.commit()

        # Store updated totals in Redis (no TTL — persistent until reconciliation resets)
        await cache_service.set(REDIS_KEY, new_totals)

        logger.info(
            f"[DELTA-SYNC] Complete: {stats['delta_contacts']} new contacts across {stats['lists_scanned']} lists, "
            f"{stats['api_calls']} API calls (created={stats['created']}, updated={stats['updated']})"
        )
        return stats

    async def sync_getsales_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        force_full: bool = False,
    ) -> Dict[str, Any]:
        """
        Smart sync dispatcher: incremental by default, full on reconciliation.

        Full scan triggers when:
        - force_full=True (manual trigger)
        - First run (no stored totals in Redis)
        - >24h since last full reconciliation
        """
        from app.services.cache_service import cache_service

        RECONCILIATION_KEY = "leadgen:getsales:last_full_reconciliation"
        TOTALS_KEY = "leadgen:getsales:list_totals"

        # Check if we need a full scan
        needs_full = force_full
        reason = "forced" if force_full else ""

        if not needs_full:
            stored_totals = await cache_service.get(TOTALS_KEY)
            if not stored_totals:
                needs_full = True
                reason = "cold_start"

        if not needs_full:
            last_reconciliation = await cache_service.get(RECONCILIATION_KEY)
            if not last_reconciliation:
                needs_full = True
                reason = "no_reconciliation_record"
            else:
                last_ts = datetime.fromisoformat(last_reconciliation)
                hours_since = (datetime.utcnow() - last_ts).total_seconds() / 3600
                if hours_since >= 24:
                    needs_full = True
                    reason = f"reconciliation_due ({hours_since:.0f}h since last)"

        if needs_full:
            logger.info(f"[GETSALES-SYNC] Running FULL reconciliation (reason: {reason})")
            stats = await self.sync_getsales_contacts_full(session, company_id)

            # Reset Redis totals to match reality
            lists = await self.getsales.get_lists()
            fresh_totals = {}
            for lst in lists:
                list_uuid = lst.get("uuid")
                if list_uuid:
                    _, total = await self.getsales.search_leads(
                        {"list_uuid": list_uuid}, limit=1, offset=0
                    )
                    fresh_totals[list_uuid] = total
            await cache_service.set(TOTALS_KEY, fresh_totals)
            await cache_service.set(RECONCILIATION_KEY, datetime.utcnow().isoformat())

            stats["sync_type"] = "full_reconciliation"
            stats["reason"] = reason
            return stats
        else:
            logger.info("[GETSALES-SYNC] Running incremental delta sync")
            stats = await self.sync_getsales_contacts_incremental(session, company_id)
            stats["sync_type"] = "incremental"
            return stats

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
            # M6 FIX: SQL-level match instead of loading all contacts into memory.
            # linkedin is already a normalized handle (e.g. "john-doe").
            # Match with ILIKE on the /in/<handle> portion of the URL.
            result = await session.execute(
                select(Contact).where(
                    and_(
                        *conditions,
                        Contact.linkedin_url.ilike(f"%/in/{linkedin}%"),
                    )
                ).limit(1)
            )
            contact = result.scalars().first()
            if contact:
                return contact

        return None

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags, CSS, and clean up whitespace from email body."""
        import re
        if not html or ("<" not in html):
            return html or ""
        text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"\*\s*\{[^}]*\}", "", text)  # inline CSS
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?(?:div|p|tr|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?(?:td|th)[^>]*>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&apos;", "'")
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove quoted content (previous emails in thread)
        for marker in ["\nOn ", "\nEl ", "\nDe: ", "\nFrom: ", "\nEnviado: ", "\nSent: ", "\n------"]:
            if marker in text:
                parts = text.split(marker, 1)
                if len(parts) > 1 and len(parts[0]) > 20:
                    suffix_lower = parts[1][:200].lower()
                    if any(x in suffix_lower for x in ["wrote:", "escribi", "forwarded", "original message"]):
                        text = parts[0].strip()
                        break
        return text.strip()

    async def sync_contacts_global(
        self,
        session: AsyncSession,
        company_id: int,
        max_leads: int = 3000,
        report_progress: bool = False,
        platform: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sync contacts via SmartLead CSV export + GetSales bulk search.

        SmartLead: Uses /campaigns/{id}/leads-export (full CSV per campaign,
        1 API call each). ~795 calls for all campaigns vs 6000+ paginated.
        GetSales: Uses bulk search with data_source chunking.

        When report_progress=True, writes live stats to Redis and checks cancel flag.
        platform: None="all", "smartlead", or "getsales" — run only one platform.
        """
        import json as json_mod
        from app.models.campaign import Campaign
        from app.db import async_session_maker
        import redis.asyncio as aioredis
        import time as _time

        stats = {"created": 0, "updated": 0, "skipped": 0, "processed": 0}
        started_at = _time.time()
        cancelled = False

        # Build campaign name → project_id lookup from DB
        camp_result = await session.execute(
            select(Campaign.name, Campaign.project_id).where(
                Campaign.project_id.isnot(None)
            )
        )
        campaign_project_map = {}
        for row in camp_result.all():
            campaign_project_map[row.name.lower()] = row.project_id

        # Single Redis connection for entire sync
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis = None
        try:
            redis = aioredis.from_url(redis_url)
        except Exception:
            pass

        run_smartlead = platform in (None, "smartlead")
        run_getsales = platform in (None, "getsales")

        processed = 0

        try:
            if run_smartlead and self.smartlead:
                # Get campaigns with leads
                sl_camps_result = await session.execute(
                    select(Campaign).where(
                        and_(
                            Campaign.platform == "smartlead",
                            Campaign.external_id.isnot(None),
                            func.coalesce(Campaign.leads_count, 0) > 0,
                        )
                    ).order_by(Campaign.leads_count.desc())
                )
                sl_campaigns = sl_camps_result.scalars().all()
                logger.info(f"[GLOBAL-SYNC] SmartLead: exporting {len(sl_campaigns)} campaigns via CSV")

                for idx, camp in enumerate(sl_campaigns):
                    # Check cancel flag
                    if report_progress and redis:
                        try:
                            cancel = await redis.get("contact_sync:cancel")
                            if cancel:
                                await redis.delete("contact_sync:cancel")
                                cancelled = True
                                logger.info("[GLOBAL-SYNC] Cancelled by user")
                                break
                        except Exception:
                            pass

                    csv_rows = await self.smartlead.export_campaign_leads(camp.external_id)
                    actual_count = len(csv_rows)
                    if actual_count > 0 and actual_count != (camp.leads_count or 0):
                        camp.leads_count = actual_count
                    if actual_count > 0:
                        camp.synced_leads_count = actual_count
                        camp.last_contact_sync_at = datetime.utcnow()

                    for row in csv_rows:
                        try:
                            custom_fields_raw = row.get("custom_fields", "{}")
                            try:
                                custom_fields = json_mod.loads(custom_fields_raw) if custom_fields_raw else {}
                            except (json_mod.JSONDecodeError, TypeError):
                                custom_fields = {}
                            reply_count = int(row.get("reply_count", 0) or 0)
                            lead = {
                                "id": row.get("id", ""),
                                "email": row.get("email", ""),
                                "first_name": row.get("first_name", ""),
                                "last_name": row.get("last_name", ""),
                                "company_name": row.get("company_name", ""),
                                "phone_number": row.get("phone_number", ""),
                                "linkedin_profile": row.get("linkedin_profile", ""),
                                "location": row.get("location", ""),
                                "custom_fields": custom_fields,
                                "created_at": row.get("created_at", ""),
                                "campaigns": [{
                                    "campaign_name": camp.name,
                                    "campaign_id": camp.external_id,
                                    "lead_status": row.get("status", "ACTIVE"),
                                    "created_at": row.get("created_at", ""),
                                    "reply_time": True if reply_count > 0 else None,
                                }],
                            }
                            async with session.begin_nested():
                                action = await self._process_smartlead_lead(
                                    session, company_id, lead, campaign_project_id=camp.project_id
                                )
                            stats[action] += 1
                        except Exception:
                            stats["skipped"] += 1
                        processed += 1

                    if csv_rows and processed % 500 == 0:
                        await session.flush()

                    # Report progress
                    if report_progress and redis and (idx + 1) % 10 == 0:
                        try:
                            await redis.hset("contact_sync:progress", mapping={
                                "sl_processed": str(processed),
                                "sl_created": str(stats["created"]),
                                "sl_updated": str(stats["updated"]),
                                "sl_campaigns": f"{idx+1}/{len(sl_campaigns)}",
                                "status": "running",
                                "elapsed": str(int(_time.time() - started_at)),
                            })
                        except Exception:
                            pass

                    if (idx + 1) % 50 == 0 or idx < 3:
                        logger.info(
                            f"[GLOBAL-SYNC] SmartLead {idx+1}/{len(sl_campaigns)} campaigns, "
                            f"created={stats['created']}, updated={stats['updated']}"
                        )

                    if processed >= max_leads:
                        break
                    await asyncio.sleep(0.5)

                await session.commit()
                stats["processed"] = processed
                logger.info(
                    f"[GLOBAL-SYNC] SmartLead complete: {processed} leads, "
                    f"created={stats['created']}, updated={stats['updated']}, skipped={stats['skipped']}"
                )

            if cancelled:
                if report_progress and redis:
                    try:
                        await redis.hset("contact_sync:progress", mapping={
                            "status": "cancelled",
                            "elapsed": str(int(_time.time() - started_at)),
                        })
                    except Exception:
                        pass
                return stats

            # ── GetSales bulk scan ──
            # ES hard limit: offset+size <= 10,000. For full loads (max_leads > 10K),
            # iterate by data_source_uuid so each chunk stays under the limit.
            gs_processed = 0
            gs_total = 0

            if run_getsales:
                use_datasource_chunking = max_leads > 9000

                if use_datasource_chunking:
                    # Get all data sources, then paginate within each
                    try:
                        data_sources = await self.getsales.get_data_sources()
                    except Exception as e:
                        logger.error(f"[GLOBAL-SYNC] GetSales get_data_sources failed: {e}")
                        data_sources = []

                    # Also get unfiltered total for progress
                    try:
                        _, gs_total = await self.getsales.search_leads(filter_={}, limit=1, offset=0)
                    except Exception:
                        pass

                    # Track which data sources we've completed (Redis set)
                    completed_ds_key = "contact_sync:gs_completed_ds"
                    completed_ds = set()
                    if redis:
                        try:
                            completed_ds = {m.decode() for m in await redis.smembers(completed_ds_key)}
                        except Exception:
                            pass

                    for ds in data_sources:
                        ds_uuid = ds.get("uuid", "")
                        if not ds_uuid or ds_uuid in completed_ds:
                            continue

                        if cancelled:
                            break

                        ds_offset = 0
                        while gs_processed < max_leads:
                            # Check cancel flag
                            if report_progress and redis:
                                try:
                                    cancel = await redis.get("contact_sync:cancel")
                                    if cancel:
                                        await redis.delete("contact_sync:cancel")
                                        cancelled = True
                                        logger.info("[GLOBAL-SYNC] Cancelled during GetSales phase")
                                        break
                                except Exception:
                                    pass

                            try:
                                gs_leads, ds_total = await self.getsales.search_leads(
                                    filter_={"data_source_uuid": ds_uuid},
                                    limit=100, offset=ds_offset,
                                )
                            except Exception as e:
                                logger.error(f"[GLOBAL-SYNC] GetSales ds={ds_uuid[:8]} offset={ds_offset}: {e}")
                                break

                            if not gs_leads:
                                break

                            for item in gs_leads:
                                flow_name = ""
                                if isinstance(item, dict):
                                    flow_name = item.get("automation_name") or item.get("flow_name") or ""

                                project_id = None
                                if flow_name:
                                    project_id = campaign_project_map.get(flow_name.lower())

                                try:
                                    async with session.begin_nested():
                                        action = await self._process_getsales_lead(
                                            session, company_id, item, list_name=flow_name,
                                            campaign_project_id=project_id,
                                        )
                                    stats[action] += 1
                                except Exception:
                                    stats["skipped"] += 1

                                gs_processed += 1

                            ds_offset += len(gs_leads)

                            if len(gs_leads) < 100 or ds_offset >= ds_total:
                                break

                            if gs_processed % 500 == 0:
                                await session.flush()

                            if report_progress and redis and gs_processed % 100 == 0:
                                try:
                                    await redis.hset("contact_sync:progress", mapping={
                                        "gs_processed": str(gs_processed),
                                        "gs_total": str(gs_total),
                                        "status": "running",
                                        "elapsed": str(int(_time.time() - started_at)),
                                    })
                                except Exception:
                                    pass

                        # Mark data source as completed
                        if redis and not cancelled:
                            try:
                                await redis.sadd(completed_ds_key, ds_uuid)
                            except Exception:
                                pass

                    # Also scan leads with no data source (list_uuid filter)
                    if not cancelled:
                        try:
                            lists = await self.getsales.get_lists()
                        except Exception:
                            lists = []
                        for lst in lists:
                            list_uuid = lst.get("uuid", "")
                            if not list_uuid or list_uuid in completed_ds:
                                continue
                            if cancelled:
                                break

                            ds_offset = 0
                            while gs_processed < max_leads:
                                if report_progress and redis:
                                    try:
                                        cancel = await redis.get("contact_sync:cancel")
                                        if cancel:
                                            await redis.delete("contact_sync:cancel")
                                            cancelled = True
                                            break
                                    except Exception:
                                        pass

                                try:
                                    gs_leads, ds_total = await self.getsales.search_leads(
                                        filter_={"list_uuid": list_uuid},
                                        limit=100, offset=ds_offset,
                                    )
                                except Exception as e:
                                    logger.error(f"[GLOBAL-SYNC] GetSales list={list_uuid[:8]} offset={ds_offset}: {e}")
                                    break

                                if not gs_leads:
                                    break

                                for item in gs_leads:
                                    flow_name = ""
                                    if isinstance(item, dict):
                                        flow_name = item.get("automation_name") or item.get("flow_name") or ""
                                    project_id = None
                                    if flow_name:
                                        project_id = campaign_project_map.get(flow_name.lower())
                                    try:
                                        async with session.begin_nested():
                                            action = await self._process_getsales_lead(
                                                session, company_id, item, list_name=flow_name,
                                                campaign_project_id=project_id,
                                            )
                                        stats[action] += 1
                                    except Exception:
                                        stats["skipped"] += 1
                                    gs_processed += 1

                                ds_offset += len(gs_leads)
                                if len(gs_leads) < 100 or ds_offset >= ds_total:
                                    break
                                if gs_processed % 500 == 0:
                                    await session.flush()

                            if redis and not cancelled:
                                try:
                                    await redis.sadd(completed_ds_key, list_uuid)
                                except Exception:
                                    pass

                else:
                    # Incremental: start from offset 0 (newest first), stop when
                    # we hit a streak of already-known contacts (all "updated").
                    # This correctly picks up new leads regardless of position shifts.
                    gs_offset = 0
                    consecutive_known = 0
                    KNOWN_STREAK_THRESHOLD = 200  # stop after 200 consecutive known leads
                    while gs_processed < max_leads and gs_offset < 9900:
                        if report_progress and redis:
                            try:
                                cancel = await redis.get("contact_sync:cancel")
                                if cancel:
                                    await redis.delete("contact_sync:cancel")
                                    cancelled = True
                                    logger.info("[GLOBAL-SYNC] Cancelled during GetSales phase")
                                    break
                            except Exception:
                                pass

                        try:
                            gs_leads, gs_total = await self.getsales.search_leads(
                                filter_={}, limit=100, offset=gs_offset
                            )
                        except Exception as e:
                            logger.error(f"[GLOBAL-SYNC] GetSales search failed at offset={gs_offset}: {e}")
                            break

                        if not gs_leads:
                            break

                        batch_created = 0
                        for item in gs_leads:
                            flow_name = ""
                            if isinstance(item, dict):
                                flow_name = item.get("automation_name") or item.get("flow_name") or ""
                            project_id = None
                            if flow_name:
                                project_id = campaign_project_map.get(flow_name.lower())
                            try:
                                async with session.begin_nested():
                                    action = await self._process_getsales_lead(
                                        session, company_id, item, list_name=flow_name,
                                        campaign_project_id=project_id,
                                    )
                                stats[action] += 1
                                if action == "created":
                                    batch_created += 1
                            except Exception:
                                stats["skipped"] += 1
                            gs_processed += 1

                        gs_offset += len(gs_leads)

                        # Track consecutive batches with no new contacts
                        if batch_created == 0:
                            consecutive_known += len(gs_leads)
                        else:
                            consecutive_known = 0

                        if consecutive_known >= KNOWN_STREAK_THRESHOLD:
                            logger.info(
                                f"[GLOBAL-SYNC] GetSales incremental: stopping after "
                                f"{consecutive_known} consecutive known leads"
                            )
                            break

                        if len(gs_leads) < 100 or gs_offset >= gs_total:
                            break
                        if gs_processed % 500 == 0:
                            await session.flush()

                        if report_progress and redis and gs_processed % 100 == 0:
                            try:
                                await redis.hset("contact_sync:progress", mapping={
                                    "gs_processed": str(gs_processed),
                                    "gs_offset": str(gs_offset),
                                    "gs_total": str(gs_total),
                                    "status": "running",
                                    "elapsed": str(int(_time.time() - started_at)),
                                })
                            except Exception:
                                pass

                await session.commit()
                stats["processed"] += gs_processed
                logger.info(
                    f"[GLOBAL-SYNC] GetSales: processed={gs_processed}, total={gs_total}"
                )

            # Final progress update
            if report_progress and redis:
                final_status = "cancelled" if cancelled else "completed"
                suffix = f"_{platform}" if platform else ""
                try:
                    await redis.hset("contact_sync:progress", mapping={
                        "status" + suffix: final_status,
                        "elapsed" + suffix: str(int(_time.time() - started_at)),
                    })
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"[GLOBAL-SYNC] Fatal error: {e}")
            if report_progress and redis:
                try:
                    await redis.hset("contact_sync:progress", mapping={
                        "status": "failed",
                        "error": str(e)[:500],
                        "elapsed": str(int(_time.time() - started_at)),
                    })
                except Exception:
                    pass
            raise
        finally:
            if redis:
                try:
                    await redis.aclose()
                except Exception:
                    pass

        return stats

    async def sync_campaign_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        max_campaigns: int = 5,
        max_leads_per_campaign: int = 500,
    ) -> Dict[str, Any]:
        """Sync contacts from campaigns that have more leads than we've synced.

        Picks campaigns with largest delta between leads_count and synced_leads_count.
        Returns stats dict with campaigns_synced, contacts_created, contacts_updated.
        """
        from app.models.campaign import Campaign

        stats = {"campaigns_synced": 0, "contacts_created": 0, "contacts_updated": 0, "contacts_skipped": 0}

        # Find campaigns needing sync: assigned to a project AND either:
        # 1. Never synced (last_contact_sync_at IS NULL), or
        # 2. Have more leads than synced (leads_count > synced_leads_count), or
        # 3. Active campaign last synced >7 days ago (detect new leads)
        # Prioritize active campaigns first (currently sending outreach)
        active_statuses = ("active", "ACTIVE", "INPROGRESS")
        resync_cutoff = datetime.utcnow() - timedelta(days=7)
        result = await session.execute(
            select(Campaign).where(
                and_(
                    Campaign.project_id.isnot(None),
                    or_(
                        Campaign.last_contact_sync_at.is_(None),
                        Campaign.leads_count > Campaign.synced_leads_count,
                        # Re-sync active campaigns weekly to detect new leads
                        and_(
                            Campaign.status.in_(active_statuses),
                            Campaign.last_contact_sync_at < resync_cutoff,
                        ),
                    ),
                )
            ).order_by(
                # Active campaigns first, then unsynced, then by delta
                Campaign.status.in_(active_statuses).desc(),
                Campaign.last_contact_sync_at.is_(None).desc(),
                (Campaign.leads_count - Campaign.synced_leads_count).desc(),
            ).limit(max_campaigns)
        )
        campaigns_to_sync = result.scalars().all()

        if not campaigns_to_sync:
            return stats

        # Capture campaign data for parallel processing (detach from main session)
        campaign_data = [
            {"id": c.id, "name": c.name, "platform": c.platform, "external_id": c.external_id,
             "project_id": c.project_id, "synced_leads_count": c.synced_leads_count or 0,
             "is_resync": c.last_contact_sync_at is not None}
            for c in campaigns_to_sync
        ]

        from app.db import async_session_maker

        async def _sync_one(cdata):
            """Sync one campaign with its own session."""
            try:
                async with async_session_maker() as camp_session:
                    # Reload campaign in this session
                    camp_result = await camp_session.execute(
                        select(Campaign).where(Campaign.id == cdata["id"])
                    )
                    campaign = camp_result.scalar()
                    if not campaign:
                        return None

                    start_offset = cdata["synced_leads_count"] if cdata["is_resync"] else 0

                    if cdata["platform"] == "smartlead":
                        synced = await self._sync_smartlead_campaign_contacts(
                            camp_session, company_id, campaign, max_leads_per_campaign,
                            start_offset=start_offset,
                        )
                    elif cdata["platform"] == "getsales":
                        synced = await self._sync_getsales_campaign_contacts(
                            camp_session, company_id, campaign, max_leads_per_campaign,
                            start_offset=start_offset,
                        )
                    else:
                        return None

                    campaign.last_contact_sync_at = datetime.utcnow()
                    await camp_session.commit()

                    logger.info(
                        f"[CONTACT-SYNC] Campaign '{cdata['name']}' (id={cdata['id']}): "
                        f"created={synced.get('created', 0)}, updated={synced.get('updated', 0)}, "
                        f"synced_leads_count={campaign.synced_leads_count}"
                    )
                    return synced
            except Exception as e:
                logger.error(f"[CONTACT-SYNC] Failed to sync campaign '{cdata['name']}': {e}", exc_info=True)
                return None

        # Run in parallel batches of 5 (each with own session)
        for i in range(0, len(campaign_data), 5):
            batch = campaign_data[i:i + 5]
            results = await asyncio.gather(*[_sync_one(c) for c in batch], return_exceptions=True)

            for r in results:
                if isinstance(r, Exception) or r is None:
                    continue
                stats["contacts_created"] += r.get("created", 0)
                stats["contacts_updated"] += r.get("updated", 0)
                stats["contacts_skipped"] += r.get("skipped", 0)
                stats["campaigns_synced"] += 1

        return stats

    async def _sync_smartlead_campaign_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        campaign,
        max_leads: int,
        start_offset: int = 0,
    ) -> Dict[str, int]:
        """Sync contacts from a single SmartLead campaign.

        For re-syncs, start_offset skips already-synced leads (1 API call if no new leads).
        """
        result = {"created": 0, "updated": 0, "skipped": 0}
        offset = start_offset
        total_synced = start_offset  # preserve count from previous sync

        while total_synced < max_leads + start_offset:
            batch_size = min(100, max_leads + start_offset - total_synced)
            raw_leads = await self.smartlead.get_campaign_leads(
                campaign.external_id, offset=offset, limit=batch_size
            )

            if not raw_leads:
                break

            # Flatten: API may return [{campaign_lead_map_id, lead: {...}}, ...] wrappers
            leads = []
            for item in raw_leads:
                if isinstance(item, dict) and "lead" in item:
                    leads.append(item["lead"])
                else:
                    leads.append(item)

            for lead in leads:
                if not lead.get("campaigns"):
                    lead["campaigns"] = [{
                        "campaign_name": campaign.name,
                        "campaign_id": campaign.external_id,
                        "lead_status": lead.get("status", "ACTIVE"),
                    }]
                try:
                    async with session.begin_nested():
                        action = await self._process_smartlead_lead(
                            session, company_id, lead, campaign_project_id=campaign.project_id
                        )
                    result[action] += 1
                except Exception:
                    result["skipped"] += 1

            total_synced += len(leads)
            offset += len(leads)

            if len(leads) < batch_size:
                break

            await session.flush()

        # Update campaign stats
        campaign.leads_count = max(campaign.leads_count or 0, total_synced)
        campaign.synced_leads_count = total_synced
        await session.flush()
        return result

    async def _sync_getsales_campaign_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        campaign,
        max_leads: int,
        start_offset: int = 0,
    ) -> Dict[str, int]:
        """Sync contacts from a single GetSales campaign (flow).

        For re-syncs, start_offset skips already-synced leads.
        """
        result = {"created": 0, "updated": 0, "skipped": 0}
        offset = start_offset
        total_synced = start_offset
        api_total = 0

        while total_synced < max_leads + start_offset:
            batch_size = min(100, max_leads + start_offset - total_synced)
            leads, api_total = await self.getsales.search_leads(
                filter_={"flow_uuid": campaign.external_id},
                limit=batch_size, offset=offset,
            )

            if not leads:
                break

            for item in leads:
                try:
                    async with session.begin_nested():
                        action = await self._process_getsales_lead(
                            session, company_id, item, list_name=campaign.name,
                            campaign_project_id=campaign.project_id,
                        )
                    result[action] += 1
                except Exception:
                    result["skipped"] += 1

            total_synced += len(leads)
            offset += len(leads)

            if len(leads) < batch_size or offset >= api_total:
                break

            await session.flush()

        # Update campaign stats
        campaign.leads_count = max(campaign.leads_count or 0, api_total or total_synced)
        campaign.synced_leads_count = total_synced
        await session.flush()
        return result

    async def sync_smartlead_replies(
        self,
        session: AsyncSession,
        company_id: int,
        since: datetime = None,
        skip_campaigns: set = None,
        only_campaigns: set = None,
    ) -> Dict[str, int]:
        """
        Sync reply activities from Smartlead — scoped to project campaigns only.

        When only_campaigns is provided, ONLY polls campaigns in that set
        (from enabled projects). This avoids iterating all 1700+ SmartLead
        campaigns and instead checks only the ~15-50 that matter.

        Falls back to skip_campaigns (old behavior) if only_campaigns is None.
        """
        if not self.smartlead:
            raise ValueError("Smartlead API key not configured")

        from app.models.reply import ProcessedReply
        from app.models.campaign import Campaign as CampaignModel
        from app.services.smartlead_service import smartlead_service

        skip_campaigns = skip_campaigns or set()
        stats = {
            "new_replies": 0, "existing": 0, "cached": 0,
            "campaigns_checked": 0, "errors": 0, "skipped_unchanged": 0,
            "lead_id_from_db": 0, "lead_id_from_stats": 0, "lead_id_from_api": 0,
        }
        try:
            campaigns = await self.smartlead.get_campaigns()

            if only_campaigns:
                campaigns = [c for c in campaigns if c.get("name") in only_campaigns]
                logger.info(f"Reply sync: {len(campaigns)} project campaigns (scoped)")
            else:
                logger.info(f"Reply sync: checking {len(campaigns)} campaigns (unscoped)")

            async with httpx.AsyncClient(timeout=30.0) as http_client:
                for campaign in campaigns:
                    status = campaign.get("status", "").upper()
                    campaign_id = campaign.get("id")
                    campaign_name = campaign.get("name", "Unknown")

                    if status not in ("ACTIVE", "PAUSED", "COMPLETED"):
                        continue

                    if campaign_name in skip_campaigns:
                        continue

                    stats["campaigns_checked"] += 1
                    cid_str = str(campaign_id)

                    # --- Analytics guard: 1 API call to check reply_count ---
                    sl_count = await smartlead_service.get_campaign_reply_count(cid_str)

                    if sl_count >= 0:
                        # Read DB counter (shared with webhook path)
                        db_campaign = (await session.execute(
                            select(CampaignModel).where(
                                CampaignModel.external_id == cid_str,
                                CampaignModel.platform == "smartlead",
                            ).limit(1)
                        )).scalar_one_or_none()

                        db_count = db_campaign.sl_reply_count if db_campaign else 0

                        if db_count > 0 and sl_count == db_count:
                            logger.debug(f"Reply sync: campaign '{campaign_name}' reply_count={sl_count} unchanged, skipping")
                            stats["skipped_unchanged"] += 1
                            continue

                        if db_count > 0:
                            logger.info(f"Reply sync: campaign '{campaign_name}' reply_count {db_count} → {sl_count} (delta: {sl_count - db_count})")

                    try:
                        replied_leads = await smartlead_service.get_all_campaign_replied_leads(
                            cid_str
                        )

                        # Update DB counter after successful pagination
                        if sl_count >= 0:
                            if db_campaign:
                                db_campaign.sl_reply_count = sl_count
                            else:
                                # Auto-register campaign if missing
                                db_campaign = CampaignModel(
                                    company_id=1,
                                    platform="smartlead",
                                    channel="email",
                                    external_id=cid_str,
                                    name=campaign_name,
                                    status=status.lower(),
                                    sl_reply_count=sl_count,
                                )
                                session.add(db_campaign)
                            await session.flush()

                        if not replied_leads:
                            await asyncio.sleep(0.05)
                            continue

                        logger.info(f"Reply sync: campaign '{campaign_name}' — {len(replied_leads)} replied leads")

                        for reply_data in replied_leads:
                            email = self.normalize_email(reply_data.get("lead_email"))
                            if not email:
                                continue
                            cache_key = f"{email}_{campaign_id}"

                            # Atomic Redis claim — if another process already claimed, skip
                            from app.services.cache_service import try_claim_reply
                            if not await try_claim_reply("smartlead", cache_key):
                                stats["cached"] += 1
                                continue

                            # Check if ProcessedReply already exists
                            existing_pr = await session.execute(
                                select(ProcessedReply).where(
                                    and_(
                                        func.lower(ProcessedReply.lead_email) == email.lower(),
                                        ProcessedReply.campaign_id == str(campaign_id)
                                    )
                                ).limit(1)
                            )
                            existing_record = existing_pr.scalar_one_or_none()
                            if existing_record:
                                # Update received_at if Smartlead shows a newer reply_time
                                raw_reply_time = reply_data.get("reply_time")
                                if raw_reply_time:
                                    try:
                                        from dateutil.parser import parse as parse_dt
                                        parsed_time = parse_dt(raw_reply_time).replace(tzinfo=None)
                                        if not existing_record.received_at or parsed_time > existing_record.received_at:
                                            existing_record.received_at = parsed_time
                                            existing_record.approval_status = None  # Re-surface for operator
                                            await session.flush()
                                            stats.setdefault("updated", 0)
                                            stats["updated"] += 1
                                            logger.info(f"Updated received_at for {email} to {parsed_time}")
                                    except Exception as dt_err:
                                        logger.debug(f"Could not parse reply_time '{raw_reply_time}': {dt_err}")
                                stats["existing"] += 1
                                continue

                            # --- Resolve lead data: DB first, then stats, then API ---
                            first_name = ""
                            last_name = ""
                            company_name = ""
                            custom_fields = {}
                            website = ""
                            linkedin_profile = ""
                            location = ""
                            lead_id = None
                            campaign_lead_map_id = ""

                            # 1) Local DB lookup (free, instant)
                            try:
                                contact_result = await session.execute(
                                    select(Contact).where(
                                        and_(
                                            func.lower(Contact.email) == email.lower(),
                                            Contact.deleted_at.is_(None)
                                        )
                                    ).limit(1)
                                )
                                contact = contact_result.scalar_one_or_none()
                                if contact and contact.smartlead_id:
                                    lead_id = str(contact.smartlead_id)
                                    first_name = contact.first_name or ""
                                    last_name = contact.last_name or ""
                                    company_name = contact.company_name or ""
                                    linkedin_profile = contact.linkedin_url or ""
                                    location = contact.location or ""
                                    stats["lead_id_from_db"] += 1
                            except Exception as db_err:
                                logger.warning(f"DB lookup failed for {email}: {db_err}")

                            # 2) Statistics response lead_id (already fetched, free)
                            if not lead_id:
                                stats_lead_id = reply_data.get("lead_id")
                                if stats_lead_id:
                                    lead_id = str(stats_lead_id)
                                    stats["lead_id_from_stats"] += 1

                            # 3) SmartLead global API — always called to resolve
                            # campaign_lead_map_id (the correct leadMap for inbox URLs).
                            # sl_email_lead_id != leadMap; using the wrong one produces
                            # broken "Open in Smartlead" links in Telegram notifications.
                            try:
                                global_lead = await smartlead_service.get_lead_by_email_global(email)
                                if global_lead:
                                    if not lead_id:
                                        lead_id = str(global_lead.get("id", ""))
                                        stats["lead_id_from_api"] += 1
                                    if not first_name:
                                        first_name = global_lead.get("first_name", "")
                                    if not last_name:
                                        last_name = global_lead.get("last_name", "")
                                    if not company_name:
                                        company_name = global_lead.get("company_name", "")
                                    custom_fields = global_lead.get("custom_fields") or {}
                                    website = global_lead.get("website", "")
                                    if not linkedin_profile:
                                        linkedin_profile = global_lead.get("linkedin_profile", "")
                                    if not location:
                                        location = global_lead.get("location", "")
                                    for cd in global_lead.get("lead_campaign_data", []):
                                        if str(cd.get("campaign_id")) == str(campaign_id):
                                            campaign_lead_map_id = str(cd.get("campaign_lead_map_id", ""))
                                            break
                            except Exception as enrich_err:
                                logger.warning(f"API lead lookup failed for {email}: {enrich_err}")

                            # Fallback: parse name from statistics data
                            if not first_name:
                                name_parts = (reply_data.get("lead_name") or "").strip().split()
                                first_name = name_parts[0] if name_parts else ""
                                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

                            # Fetch message history for reply content (needs lead_id)
                            reply_body = ""
                            reply_subject = reply_data.get("email_subject", "")
                            reply_time = reply_data.get("reply_time")

                            if lead_id:
                                try:
                                    thread = await smartlead_service.get_email_thread_with_client(
                                        http_client, str(campaign_id), lead_id
                                    )
                                    for msg in reversed(thread):
                                        if (msg.get("type") or "").upper() == "REPLY":
                                            raw_body = msg.get("email_body") or ""
                                            reply_body = self._strip_html(raw_body)
                                            if msg.get("subject"):
                                                reply_subject = msg["subject"]
                                            if msg.get("time"):
                                                reply_time = msg["time"]
                                            break
                                    if not reply_body and thread:
                                        raw_body = thread[-1].get("email_body") or ""
                                        reply_body = self._strip_html(raw_body)
                                except Exception as thread_err:
                                    logger.warning(f"Could not fetch thread for {email} (lead {lead_id}): {thread_err}")

                            # Build webhook-compatible payload
                            webhook_payload = {
                                "event_type": "EMAIL_REPLY",
                                "campaign_id": str(campaign_id),
                                "campaign_name": campaign_name,
                                "lead_email": email,
                                "to_email": email,
                                "to_name": f"{first_name} {last_name}".strip(),
                                "first_name": first_name,
                                "last_name": last_name,
                                "company_name": company_name,
                                "email_subject": reply_subject,
                                "preview_text": reply_body,
                                "email_body": reply_body,
                                "sl_email_lead_id": lead_id or "",
                                "sl_email_lead_map_id": campaign_lead_map_id,
                                "custom_fields": custom_fields,
                                "website": website,
                                "linkedin_profile": linkedin_profile,
                                "location": location,
                                "time_replied": reply_time,
                                "_source": "api_polling",
                            }

                            # Run the full reply processing pipeline
                            try:
                                from app.services.reply_processor import process_reply_webhook
                                processed = await process_reply_webhook(webhook_payload, session)
                                if processed:
                                    stats["new_replies"] += 1
                                    logger.info(f"Reply sync: processed reply from {email} in '{campaign_name}'")
                                else:
                                    logger.warning(f"Reply sync: process_reply_webhook returned None for {email}")
                            except Exception as proc_err:
                                stats["errors"] += 1
                                logger.warning(f"Reply sync: failed to process {email}: {proc_err}")

                            await asyncio.sleep(0.3)  # Rate limit per lead

                        await asyncio.sleep(0.2)  # Rate limit per campaign

                    except Exception as e:
                        stats["errors"] += 1
                        logger.warning(f"Error checking campaign '{campaign_name}': {e}")

            await session.commit()

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
        _pending_notifications = []  # (pr, contact, flow_name, flow_uuid, message_text, raw_data)
        
        try:
            # --- Total-count guard: skip if inbox total unchanged (like SmartLead analytics guard) ---
            GS_TOTAL_KEY = "leadgen:getsales_inbox_total"
            from app.services.cache_service import cache_service
            redis = cache_service._redis if cache_service.is_connected else None

            # Fetch first page (always needed to get the total)
            offset = 0
            stop_pagination = False
            messages, has_more, total = await self.getsales.get_inbox_messages(
                limit=page_size, offset=offset
            )
            stats["pages"] = 1
            logger.info(f"GetSales reply sync: {total} total inbox messages")

            if redis and total > 0:
                prev_total = await redis.get(GS_TOTAL_KEY)
                if prev_total is not None and int(prev_total) == total:
                    stats["skipped_unchanged"] = True
                    logger.info(f"GetSales reply sync: total unchanged ({total}), skipping")
                    return stats

            if not messages:
                if redis:
                    await redis.set(GS_TOTAL_KEY, str(total), ex=7200)
                return stats
            
            while not stop_pagination and stats["pages"] <= max_pages:
                
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

                    # Update contact — use status machine for forward-only transition
                    contact.mark_replied("linkedin", at=activity.activity_at)
                    from app.services.status_machine import transition_status, derive_external_status
                    new_st, ok, _msg = transition_status(contact.status, "interested")
                    if ok:
                        contact.status = new_st

                    # Create ProcessedReply with classification + draft (non-fatal)
                    _pr = None
                    try:
                        from app.services.reply_processor import process_getsales_reply
                        automation_info = msg.get("automation") or {}
                        flow_uuid = ""
                        flow_name = ""

                        if isinstance(automation_info, dict) and automation_info.get("uuid"):
                            flow_uuid = automation_info["uuid"]
                            mapped = GETSALES_FLOW_NAMES.get(flow_uuid)
                            raw_name = automation_info.get("name", "")
                            flow_name = mapped or (raw_name if _is_valid_campaign_name(raw_name) else "")
                        else:
                            # automation: "synced" — resolve campaign name in priority order:
                            # 1. Contact's cached campaigns (if UUID in GETSALES_FLOW_NAMES)
                            # 2. Contact's cached campaigns (if name passes validation)
                            # 3. Sender's most recent webhook automation (from webhook_events)
                            # 4. Leave empty — webhook path will enrich it later via upsert
                            gs_campaigns = (contact.get_platform("getsales") or {}).get("campaigns", [])
                            if gs_campaigns and isinstance(gs_campaigns, list):
                                for gc in gs_campaigns:
                                    gc_name = gc.get("name", "")
                                    gc_id = gc.get("id", "")
                                    if gc_id and gc_id in GETSALES_FLOW_NAMES:
                                        flow_name = GETSALES_FLOW_NAMES[gc_id]
                                        flow_uuid = gc_id
                                        break
                                    if gc_name and _is_valid_campaign_name(gc_name):
                                        flow_name = gc_name
                                        flow_uuid = gc_id
                                        break
                            # Fallback: resolve from sender's webhook history
                            if not flow_name:
                                _sender_uuid = msg.get("sender_profile_uuid", "")
                                if _sender_uuid:
                                    try:
                                        from app.models.reply import WebhookEventModel
                                        _wh_result = await session.execute(
                                            select(WebhookEventModel.payload).where(
                                                WebhookEventModel.event_type == "linkedin_inbox",
                                                sa_text(
                                                    "payload::jsonb->'sender_profile'->>'uuid' = :spuuid"
                                                ),
                                            ).params(spuuid=_sender_uuid)
                                            .order_by(WebhookEventModel.created_at.desc())
                                            .limit(1)
                                        )
                                        _wh_row = _wh_result.scalar()
                                        if _wh_row:
                                            import json as _json
                                            _wh_payload = _json.loads(_wh_row) if isinstance(_wh_row, str) else _wh_row
                                            _wh_auto = _wh_payload.get("automation", {})
                                            if isinstance(_wh_auto, dict) and _wh_auto.get("name"):
                                                flow_name = _wh_auto["name"]
                                                flow_uuid = _wh_auto.get("uuid", "")
                                                logger.info(f"[GETSALES] Resolved campaign from webhook history: {flow_name}")
                                    except Exception as _wh_err:
                                        logger.debug(f"[GETSALES] Webhook history lookup failed: {_wh_err}")
                        _pr = await process_getsales_reply(
                            message_text=message_text,
                            contact=contact,
                            flow_name=flow_name,
                            flow_uuid=flow_uuid,
                            message_id=str(message_id),
                            activity_at=msg_time if created_at_str else datetime.utcnow(),
                            raw_data=msg,
                            session=session,
                        )
                    except Exception as pr_err:
                        logger.warning(f"[GETSALES] ProcessedReply creation failed (non-fatal): {pr_err}")

                    # Derive client-facing external status using actual classification
                    if _pr and contact.project_id:
                        try:
                            from app.models.contact import Project
                            _proj_result = await session.execute(
                                select(Project).where(Project.id == contact.project_id)
                            )
                            _proj = _proj_result.scalar()
                            if _proj and _proj.external_status_config:
                                from app.services.status_machine import derive_external_status
                                ext = derive_external_status(
                                    _proj.external_status_config,
                                    reply_category=_pr.category,
                                    internal_status=contact.status,
                                )
                                if ext:
                                    contact.status_external = ext
                        except Exception:
                            pass  # Non-fatal

                    # Collect for post-commit notification
                    if _pr:
                        _pending_notifications.append((_pr, contact, flow_name, flow_uuid, message_text, msg))

                    stats["new_replies"] += 1
                    new_reply_ids.append(message_id)

                # Pagination — fetch next page for next iteration
                if not has_more:
                    stop_pagination = True
                else:
                    offset += page_size
                    await asyncio.sleep(0.1)
                    messages, has_more, total = await self.getsales.get_inbox_messages(
                        limit=page_size, offset=offset
                    )
                    stats["pages"] += 1
                    if not messages:
                        break

            await session.commit()

            # Send notifications AFTER commit — prevents ghost notifications on rollback
            if _pending_notifications:
                from app.services.reply_processor import send_getsales_notification
                for _pr, _contact, _fn, _fu, _mt, _rd in _pending_notifications:
                    try:
                        await send_getsales_notification(
                            processed_reply=_pr, contact=_contact,
                            flow_name=_fn, flow_uuid=_fu,
                            message_text=_mt, raw_data=_rd, session=session,
                        )
                    except Exception:
                        pass  # Non-fatal
            
            # Update total count in Redis after successful sync
            if redis:
                await redis.set(GS_TOTAL_KEY, str(total), ex=7200)
            
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
        company_id: int,
        only_campaigns: set = None,
    ) -> Dict[str, Any]:
        """
        Perform full sync from all sources.
        
        Uses Redis lock to prevent concurrent syncs.
        When only_campaigns is provided, scopes contact sync to those campaigns only.
        """
        results = {
            "smartlead": {"contacts": None, "replies": None},
            "getsales": {"contacts": None, "replies": None},
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None
        }
        
        if not await acquire_sync_lock():
            results["error"] = "Sync already in progress"
            results["success"] = False
            results["skipped"] = True
            logger.warning("Sync skipped - another sync already in progress")
            return results
        
        try:
            if self.smartlead:
                logger.info(f"Syncing Smartlead contacts{f' (scoped to {len(only_campaigns)} campaigns)' if only_campaigns else ''}...")
                results["smartlead"]["contacts"] = await self.sync_smartlead_contacts(
                    session, company_id, only_campaigns=only_campaigns,
                )
                
                logger.info("Syncing Smartlead replies...")
                results["smartlead"]["replies"] = await self.sync_smartlead_replies(
                    session, company_id, only_campaigns=only_campaigns,
                )
            
            if self.getsales:
                logger.info("Syncing GetSales contacts...")
                results["getsales"]["contacts"] = await self.sync_getsales_contacts(session, company_id)

                logger.info("Syncing GetSales replies...")
                results["getsales"]["replies"] = await self.sync_getsales_replies(session, company_id)

            results["completed_at"] = datetime.utcnow().isoformat()
            results["success"] = True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            results["error"] = str(e)
            results["success"] = False
        finally:
            await release_sync_lock()
        
        return results


# ============= Conversation History Sync =============

async def sync_conversation_histories(
    session: AsyncSession,
    limit: int = 100,
    days_back: int = 7,
) -> Dict[str, Any]:
    """Sync Smartlead message histories for recent pending replies.

    Resolves lead_id from DB only (zero API calls for resolution).
    Fetches message-history only for recent pending leads (~5-10 API calls).
    Marks replies as 'replied_externally' when the last message is outbound.
    Creates missing outbound ContactActivity records so future checks are instant.

    Args:
        session: Async DB session
        limit: Max unique leads to check per run
        days_back: Only check replies from last N days (default: 7 = 1 week)
    """
    from app.models.reply import ProcessedReply
    from app.services.smartlead_service import SmartleadService

    stats = {
        "checked": 0,
        "replied_externally": 0,
        "still_pending": 0,
        "no_lead_id": 0,
        "errors": 0,
        "activities_created": 0,
    }

    sl = SmartleadService()
    if not sl._api_key:
        logger.warning("sync_conversation_histories: SMARTLEAD_API_KEY not set, skipping")
        return stats

    # Only check recent replies
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    # Find pending replies needing outbound check (recent only).
    # Use same "latest activity direction" logic as the needs_reply filter:
    # two-step correlated subquery — contact_id from email index, then latest direction.
    contact_id_subq = (
        select(Contact.id)
        .where(
            func.lower(Contact.email) == func.lower(ProcessedReply.lead_email),
            Contact.deleted_at.is_(None),
            Contact.email.isnot(None),
            Contact.email != "",
        )
        .correlate(ProcessedReply)
        .limit(1)
        .scalar_subquery()
    )
    latest_direction = (
        select(ContactActivity.direction)
        .where(ContactActivity.contact_id == contact_id_subq)
        .order_by(ContactActivity.activity_at.desc())
        .limit(1)
        .correlate(ProcessedReply)
        .scalar_subquery()
    )

    pending_q = (
        select(ProcessedReply)
        .where(
            and_(
                or_(
                    ProcessedReply.approval_status == None,
                    ProcessedReply.approval_status == "pending",
                ),
                ProcessedReply.campaign_id.isnot(None),
                ProcessedReply.lead_email.isnot(None),
                ProcessedReply.received_at >= cutoff,
                # Latest activity is NOT outbound (lead sent last msg, or no activities)
                or_(latest_direction.is_(None), latest_direction != "outbound"),
            )
        )
        .order_by(ProcessedReply.received_at.desc())
        .limit(limit)
    )

    result = await session.execute(pending_q)
    pending_replies = result.scalars().all()

    if not pending_replies:
        logger.info("sync_conversation_histories: no recent pending replies to check")
        return stats

    # Deduplicate by (campaign_id, lead_email)
    seen = set()
    to_check = []
    reply_groups = {}

    for r in pending_replies:
        email_lower = (r.lead_email or "").lower()
        group_key = (r.campaign_id, email_lower)
        reply_groups.setdefault(group_key, []).append(r)
        if group_key not in seen and r.campaign_id and r.lead_email:
            seen.add(group_key)
            to_check.append(r)

    logger.info(
        f"sync_conversation_histories: {len(pending_replies)} recent pending, "
        f"{len(to_check)} unique leads to check"
    )

    # Fetch message histories — resolve lead_id from DB only
    from app.services.smartlead_service import smartlead_request as _sl_request

    for reply in to_check:
        email_lower = (reply.lead_email or "").lower()
        group_key = (reply.campaign_id, email_lower)

        # Resolve lead_id from local data only
        lead_id = None
        contact_id_for_backfill = None

        # 1. Contact.smartlead_id from DB
        contact_result = await session.execute(
            select(Contact.id, Contact.smartlead_id).where(
                func.lower(Contact.email) == email_lower,
                Contact.deleted_at.is_(None),
            )
        )
        row = contact_result.first()
        if row and row[1]:
            lead_id = str(row[1])
        if row:
            contact_id_for_backfill = row[0]

        # 2. Webhook raw data (sl_email_lead_id is the primary field Smartlead sends)
        if not lead_id and reply.raw_webhook_data and isinstance(reply.raw_webhook_data, dict):
            lead_id = str(
                reply.raw_webhook_data.get("sl_email_lead_id")
                or reply.raw_webhook_data.get("sl_lead_id")
                or reply.raw_webhook_data.get("lead_id")
                or ""
            ).strip() or None

        if not lead_id:
            stats["no_lead_id"] += 1
            continue

        # Backfill Contact.smartlead_id if it was null
        if contact_id_for_backfill and row and not row[1]:
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(Contact)
                .where(Contact.id == contact_id_for_backfill)
                .values(smartlead_id=lead_id)
            )
            logger.info(f"Backfilled smartlead_id={lead_id} for contact {contact_id_for_backfill} ({email_lower})")

        stats["checked"] += 1

        try:
            resp = await _sl_request(
                "GET",
                f"https://server.smartlead.ai/api/v1/campaigns/{reply.campaign_id}/leads/{lead_id}/message-history",
                params={"api_key": sl._api_key},
            )

            if resp.status_code != 200:
                stats["errors"] += 1
                continue

            from app.services.smartlead_service import parse_history_response
            history = parse_history_response(resp.json())
            if not history:
                stats["still_pending"] += 1
                continue

            last_msg = history[-1]
            last_type = last_msg.get("type", "")

            if last_type != "REPLY":
                stats["replied_externally"] += 1

                # Mark as auto_resolved so follow-up detection works within 3 min
                if reply.approval_status in (None, "pending"):
                    reply.approval_status = "auto_resolved"
                    reply.approved_at = datetime.utcnow()

                # Create missing outbound ContactActivity records (CRM data)
                reply_received = reply.received_at
                contact_result = await session.execute(
                    select(Contact).where(
                        func.lower(Contact.email) == email_lower,
                        Contact.deleted_at.is_(None),
                    )
                )
                contact = contact_result.scalar_one_or_none()

                if contact:
                    for msg in history:
                        if msg.get("type") != "REPLY" and msg.get("time"):
                            try:
                                msg_time = datetime.fromisoformat(
                                    msg["time"].replace("Z", "+00:00").replace("+00:00", "")
                                )
                            except (ValueError, TypeError):
                                continue

                            if reply_received and msg_time > reply_received:
                                existing = await session.execute(
                                    select(ContactActivity.id).where(
                                        and_(
                                            ContactActivity.contact_id == contact.id,
                                            ContactActivity.direction == "outbound",
                                            ContactActivity.source_id == msg.get("message_id", ""),
                                        )
                                    )
                                )
                                if not existing.first():
                                    activity = ContactActivity(
                                        contact_id=contact.id,
                                        company_id=contact.company_id,
                                        activity_type="email_sent",
                                        channel="email",
                                        direction="outbound",
                                        source="smartlead_sync",
                                        source_id=msg.get("message_id", ""),
                                        subject=msg.get("email_subject"),
                                        body=(msg.get("email_body", "") or "")[:500],
                                        activity_at=msg_time,
                                    )
                                    session.add(activity)
                                    stats["activities_created"] += 1
            else:
                stats["still_pending"] += 1

        except Exception as e:
            logger.error(f"sync_conversation_histories: error checking lead {reply.lead_email}: {e}")
            stats["errors"] += 1

    # Commit all changes
    try:
        await session.commit()
    except Exception as e:
        logger.error(f"sync_conversation_histories: commit failed: {e}")
        await session.rollback()
        stats["errors"] += 1

    logger.info(f"sync_conversation_histories: {stats}")
    return stats


async def deep_cleanup_needs_reply(session: AsyncSession, batch_limit: int = 200) -> Dict[str, Any]:
    """Daily deep cleanup: load pending reply threads, resolve where operator already replied.

    Unlike sync_conversation_histories (3-min, 7-day, SmartLead-only), this:
    - Has no date cutoff — checks ALL pending replies (oldest first, batch_limit per run)
    - Handles both SmartLead and GetSales
    - Sets approval_status='auto_resolved' directly
    - Writes per-project ReplyCleanupLog entries
    """
    from app.models.reply import ProcessedReply, ReplyCleanupLog, ThreadMessage
    from app.models.contact import Project
    from app.services.smartlead_service import SmartleadService, parse_history_response, smartlead_request as _sl_request
    import os

    stats = {"checked": 0, "resolved": 0, "errors": 0, "by_project": {}}

    # Find ALL pending needs_reply replies (no date limit)
    no_reply_categories = ("out_of_office", "unsubscribe", "wrong_person", "not_interested")
    pending_q = (
        select(ProcessedReply)
        .where(
            and_(
                or_(
                    ProcessedReply.approval_status == None,
                    ProcessedReply.approval_status == "pending",
                ),
                ProcessedReply.lead_email.isnot(None),
                or_(
                    ProcessedReply.category == None,
                    ~ProcessedReply.category.in_(no_reply_categories),
                ),
            )
        )
        .order_by(ProcessedReply.received_at.asc())  # Oldest first — work through backlog
        .limit(batch_limit * 5)  # Overfetch since dedup reduces the set
    )
    result = await session.execute(pending_q)
    pending_replies = result.scalars().all()

    if not pending_replies:
        logger.info("[CLEANUP] No pending needs_reply items to check")
        return stats

    logger.info(f"[CLEANUP] Starting deep cleanup: {len(pending_replies)} pending replies")

    # Build campaign_name → project mapping
    from app.models.campaign import Campaign
    camp_result = await session.execute(
        select(func.lower(Campaign.name), Campaign.project_id)
        .where(Campaign.project_id.isnot(None))
    )
    campaign_to_project: Dict[str, int] = {}
    for cname, pid in camp_result.all():
        if cname not in campaign_to_project:
            campaign_to_project[cname] = pid

    # Project names
    proj_result = await session.execute(
        select(Project.id, Project.name).where(Project.deleted_at.is_(None))
    )
    project_names = {pid: pname for pid, pname in proj_result.all()}

    # SmartLead API
    sl = SmartleadService()
    sl_available = bool(sl._api_key)

    # GetSales API
    gs_key = os.getenv("GETSALES_API_KEY", "")

    # Deduplicate by (source, campaign_id, lead_email), cap at batch_limit
    seen = set()
    api_calls = 0

    for reply in pending_replies:
        if api_calls >= batch_limit:
            break
        email_lower = (reply.lead_email or "").lower()
        source = reply.source or "smartlead"
        dedup_key = (source, reply.campaign_id or "", email_lower)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        resolved = False
        try:
            if source == "getsales":
                # GetSales: check if thread has outbound after reply
                if not gs_key:
                    continue
                # Get conversation UUID from raw_webhook_data
                conv_uuid = None
                if reply.raw_webhook_data and isinstance(reply.raw_webhook_data, dict):
                    conv_uuid = (
                        reply.raw_webhook_data.get("linkedin_conversation_uuid")
                        or reply.raw_webhook_data.get("conversation_uuid")
                        or (reply.raw_webhook_data.get("contact", {}) or {}).get("linkedin_conversation_uuid")
                    )
                if not conv_uuid:
                    continue

                gs_client = GetSalesClient(gs_key)
                try:
                    messages = await gs_client.get_conversation_messages(conv_uuid)
                finally:
                    await gs_client.close()

                if messages:
                    # Check if any outbound message after reply's received_at
                    for msg in reversed(messages):
                        if msg.get("type") == "outbox":
                            msg_time = None
                            ts = msg.get("sent_at") or msg.get("created_at")
                            if ts:
                                try:
                                    from dateutil.parser import parse as dt_parse
                                    msg_time = dt_parse(ts)
                                    if msg_time.tzinfo:
                                        msg_time = msg_time.replace(tzinfo=None)
                                except Exception:
                                    pass
                            if msg_time and reply.received_at and msg_time > reply.received_at:
                                resolved = True
                            elif not reply.received_at:
                                resolved = True
                            break
            else:
                # SmartLead: check message history
                if not sl_available or not reply.campaign_id:
                    continue

                lead_id = reply.smartlead_lead_id
                if not lead_id:
                    row = (await session.execute(
                        select(Contact.smartlead_id).where(
                            func.lower(Contact.email) == email_lower,
                            Contact.deleted_at.is_(None),
                        )
                    )).first()
                    if row and row[0]:
                        lead_id = str(row[0])

                if not lead_id and reply.raw_webhook_data and isinstance(reply.raw_webhook_data, dict):
                    lead_id = str(
                        reply.raw_webhook_data.get("sl_email_lead_id")
                        or reply.raw_webhook_data.get("sl_lead_id")
                        or reply.raw_webhook_data.get("lead_id")
                        or ""
                    ).strip() or None

                if not lead_id:
                    continue

                resp = await _sl_request(
                    "GET",
                    f"https://server.smartlead.ai/api/v1/campaigns/{reply.campaign_id}/leads/{lead_id}/message-history",
                    params={"api_key": sl._api_key},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    stats["errors"] += 1
                    continue

                history = parse_history_response(resp.json())
                if history:
                    last_type = history[-1].get("type", "")
                    if last_type != "REPLY":
                        resolved = True

            stats["checked"] += 1
            api_calls += 1

            if resolved:
                reply.approval_status = "auto_resolved"
                reply.approved_at = datetime.utcnow()
                stats["resolved"] += 1

                # Track per-project
                cname_lower = (reply.campaign_name or "").lower()
                pid = campaign_to_project.get(cname_lower)
                if pid:
                    if pid not in stats["by_project"]:
                        stats["by_project"][pid] = {"checked": 0, "resolved": 0, "resolved_items": []}
                    stats["by_project"][pid]["resolved"] += 1
                    stats["by_project"][pid]["resolved_items"].append({
                        "reply_id": reply.id,
                        "lead_email": reply.lead_email,
                        "campaign_name": reply.campaign_name,
                    })

        except Exception as e:
            logger.warning(f"[CLEANUP] Error checking reply {reply.id}: {e}")
            stats["errors"] += 1

    # Write per-project cleanup logs
    for pid, pstats in stats["by_project"].items():
        if pstats["resolved"] > 0:
            session.add(ReplyCleanupLog(
                project_id=pid,
                project_name=project_names.get(pid, "Unknown"),
                replies_checked=pstats.get("checked", 0),
                replies_resolved=pstats["resolved"],
                resolved_replies=pstats["resolved_items"][:50],  # Cap stored items
                errors=0,
            ))

    # Also write a global summary log (project_id=None)
    session.add(ReplyCleanupLog(
        project_id=None,
        project_name="[Global Summary]",
        replies_checked=stats["checked"],
        replies_resolved=stats["resolved"],
        errors=stats["errors"],
    ))

    try:
        await session.commit()
    except Exception as e:
        logger.error(f"[CLEANUP] Commit failed: {e}")
        await session.rollback()

    logger.info(f"[CLEANUP] Deep cleanup done: checked={stats['checked']}, resolved={stats['resolved']}, errors={stats['errors']}")
    return stats


# Singleton instance
_crm_sync_service: Optional[CRMSyncService] = None


def get_crm_sync_service() -> CRMSyncService:
    """Get or create the CRM sync service singleton."""
    global _crm_sync_service
    if _crm_sync_service is None:
        _crm_sync_service = CRMSyncService()
    return _crm_sync_service
