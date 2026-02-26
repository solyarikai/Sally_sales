"""Smartlead integration service for cold email campaigns.

Uses Smartlead API: https://api.smartlead.ai/
Base URL: https://server.smartlead.ai/api/v1
"""
import asyncio
import collections
import httpx
import time
from typing import Optional, List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


def parse_history_response(data) -> list:
    """Normalize SmartLead message-history response to a list.

    The API returns 3 different formats:
      1. A plain list: [{"time_stamp": ..., "message_text": ...}, ...]
      2. {"history": [...]}
      3. {"messages": [...]}
    This function handles all three.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("history", data.get("messages", []))
    return []


# --- Global SmartLead rate limiter ---
_sl_semaphore = asyncio.Semaphore(10)        # max 10 concurrent requests
_sl_timestamps: collections.deque = collections.deque()  # sliding window
_SL_WINDOW = 60       # 1 minute window
_SL_MAX_PER_WINDOW = 150  # target 150/min (headroom under 200 limit)
_sl_429_count = 0
_sl_total_count = 0


async def smartlead_request(
    method: str,
    url: str,
    *,
    params: dict = None,
    json: dict = None,
    timeout: float = 30.0,
    client: httpx.AsyncClient = None,
    max_retries: int = 3,
) -> httpx.Response:
    """Central SmartLead API request with rate limiting + 429 retry."""
    global _sl_429_count, _sl_total_count

    async with _sl_semaphore:
        for attempt in range(max_retries + 1):
            # Sliding window: wait if at capacity
            now = time.monotonic()
            while len(_sl_timestamps) >= _SL_MAX_PER_WINDOW:
                oldest = _sl_timestamps[0]
                wait = _SL_WINDOW - (now - oldest)
                if wait > 0:
                    await asyncio.sleep(min(wait, 2.0))
                    now = time.monotonic()
                else:
                    _sl_timestamps.popleft()

            _sl_timestamps.append(time.monotonic())
            _sl_total_count += 1

            owns_client = client is None
            c = client or httpx.AsyncClient(timeout=timeout)
            try:
                resp = await c.request(method, url, params=params, json=json, timeout=timeout)
                if resp.status_code == 429:
                    _sl_429_count += 1
                    if attempt < max_retries:
                        delay = [2, 8, 30][min(attempt, 2)]
                        logger.warning(f"SmartLead 429 on {url} — retry {attempt+1}/{max_retries} in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    logger.error(f"SmartLead 429 on {url} — all {max_retries} retries exhausted")
                return resp
            except httpx.TimeoutException:
                if attempt < max_retries:
                    logger.warning(f"SmartLead timeout on {url} — retry {attempt+1}")
                    await asyncio.sleep(2)
                    continue
                raise
            finally:
                if owns_client:
                    await c.aclose()
    # unreachable, but satisfies type checker
    raise RuntimeError("smartlead_request: exhausted retries")


class SmartleadService:
    """Service for interacting with Smartlead API."""
    
    def __init__(self):
        # Try to load from environment, then from pydantic settings (.env file)
        self._api_key: Optional[str] = os.environ.get('SMARTLEAD_API_KEY')
        if not self._api_key:
            try:
                from app.core.config import settings
                self._api_key = settings.SMARTLEAD_API_KEY
            except Exception:
                pass
        self.base_url = "https://server.smartlead.ai/api/v1"
        if self._api_key:
            logger.info("Smartlead API key loaded from config")
    
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
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns",
                params={"api_key": self._api_key},
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
        # Allowed top-level: email, first_name, last_name, company_name, website.
        # Everything else (phone, linkedin_url, etc.) goes into custom_fields.
        formatted_leads = []
        TOP_LEVEL_KEYS = {"email", "first_name", "last_name", "company_name", "website"}
        INPUT_ALIASES = {
            "firstName": "first_name", "lastName": "last_name",
            "companyName": "company_name", "phone_number": "phone",
            "linkedinUrl": "linkedin_url",
        }
        for lead in leads:
            # Normalize aliases
            normalized = {}
            for k, v in lead.items():
                key = INPUT_ALIASES.get(k, k)
                if key == "custom_fields":
                    continue  # handled separately
                normalized[key] = v

            formatted_lead = {
                "email": normalized.get("email", ""),
                "first_name": normalized.get("first_name", ""),
                "last_name": normalized.get("last_name", ""),
            }
            if normalized.get("company_name"):
                formatted_lead["company_name"] = normalized["company_name"]
            if normalized.get("website"):
                formatted_lead["website"] = normalized["website"]

            # Everything else → custom_fields
            custom_fields = dict(lead.get("custom_fields", {}))
            for key, value in normalized.items():
                if key not in TOP_LEVEL_KEYS and key != "custom_fields":
                    custom_fields[key] = value
            if custom_fields:
                formatted_lead["custom_fields"] = custom_fields

            formatted_leads.append(formatted_lead)
        
        # Prepare request payload
        payload = {
            "lead_list": formatted_leads,
        }
        
        # Add settings if provided
        if settings:
            payload.update(settings)
        
        try:
            response = await smartlead_request(
                "POST", f"{self.base_url}/campaigns/{campaign_id}/leads",
                params={"api_key": self._api_key},
                json=payload,
                timeout=60.0,
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
                except (ValueError, KeyError):
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
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}",
                params={"api_key": self._api_key},
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
        limit: int = 100,
        lead_category_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get leads for a specific campaign.

        Args:
            campaign_id: Campaign ID
            offset: Pagination offset
            limit: Number of leads to fetch
            lead_category_id: Filter by category (e.g. 9 = replied)

        Returns:
            Dict with leads list and pagination info
        """
        if not self._api_key:
            raise ValueError("API key not set")

        try:
            params = {
                "api_key": self._api_key,
                "offset": offset,
                "limit": limit
            }
            if lead_category_id is not None:
                params["lead_category_id"] = lead_category_id

            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/leads",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                # Normalize response: API returns either a list or
                # {"total_leads": N, "data": [{campaign_lead_map_id, lead: {...}}, ...]}
                if isinstance(data, list):
                    leads = data
                    total = len(data)
                elif isinstance(data, dict):
                    leads = data.get("data", data.get("leads", []))
                    total = data.get("total_leads", data.get("total", len(leads)))
                else:
                    leads = []
                    total = 0
                # Flatten: extract inner "lead" object if present
                flat = []
                for item in leads:
                    if isinstance(item, dict) and "lead" in item:
                        flat.append(item["lead"])
                    else:
                        flat.append(item)
                return {"leads": flat, "total": total}
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
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/leads",
                params={"api_key": self._api_key, "email": email},
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("data", data.get("leads", []))
                else:
                    items = []
                for item in items:
                    lead = item.get("lead", item) if isinstance(item, dict) else item
                    if (lead.get("email") or "").lower() == email.lower():
                        return lead
                return None
            else:
                logger.error(f"Failed to fetch lead: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching Smartlead lead: {e}")
            return None

    async def get_lead_by_email_global(self, email: str) -> Optional[Dict[str, Any]]:
        """Get lead data by email across all campaigns (global search).

        This is the endpoint n8n uses for lead enrichment:
        GET /api/v1/leads/?email={email}

        Returns lead data including custom_fields, company_name, website,
        linkedin_profile, location, and lead_campaign_data.
        """
        if not self._api_key:
            raise ValueError("API key not set")

        try:
            response = await smartlead_request(
                "GET", f"{self.base_url}/leads/",
                params={"api_key": self._api_key, "email": email},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Global lead search for {email}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error in global lead search for {email}: {e}")
            return None

    async def get_email_thread(
        self,
        campaign_id: str,
        lead_id: str
    ) -> List[Dict[str, Any]]:
        """Get email thread/conversation for a lead.

        Args:
            campaign_id: Campaign ID
            lead_id: Numeric lead ID (NOT email address)

        Returns:
            List of email messages in the thread (from history key)
        """
        if not self._api_key:
            raise ValueError("API key not set")

        try:
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                params={"api_key": self._api_key},
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("history", data.get("messages", []))
            else:
                logger.error(f"Failed to fetch email thread for lead {lead_id}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching email thread for lead {lead_id}: {e}")
            return []

    async def get_campaign_reply_count(self, campaign_id: str) -> int:
        """Single API call to /analytics to get total reply count for a campaign.
        Returns -1 on failure."""
        try:
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/analytics",
                params={"api_key": self._api_key},
                timeout=30.0,
            )
            if response.status_code == 200:
                data = response.json()
                return int(data.get("reply_count", 0))
            logger.warning(f"Analytics API returned {response.status_code} for campaign {campaign_id}")
        except Exception as e:
            logger.warning(f"Failed to fetch analytics for campaign {campaign_id}: {e}")
        return -1

    async def get_all_campaign_replied_leads(
        self,
        campaign_id: str,
        max_pages: int = 40
    ) -> List[Dict[str, Any]]:
        """Paginate /statistics to find all replied leads in a campaign.

        Pure API call — no caching logic here. The caller (sync_smartlead_replies)
        handles the analytics count check using the campaigns DB table.
        """
        if not self._api_key:
            raise ValueError("API key not set")

        replied_by_email: Dict[str, Dict[str, Any]] = {}
        offset = 0
        page_size = 500
        page_retries = 0
        max_page_retries = 3

        for page in range(max_pages):
            try:
                response = await smartlead_request(
                    "GET", f"{self.base_url}/campaigns/{campaign_id}/statistics",
                    params={"api_key": self._api_key, "limit": page_size, "offset": offset},
                    timeout=60.0,
                )

                if response.status_code == 429:
                    page_retries += 1
                    if page_retries <= max_page_retries:
                        wait = 5 * page_retries
                        logger.warning(f"429 on statistics page {page} for campaign {campaign_id}, retry {page_retries} in {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    else:
                        logger.error(f"429 persisted after {max_page_retries} retries, stopping (got {len(replied_by_email)} so far)")
                        break

                if response.status_code != 200:
                    logger.error(f"Statistics API error for campaign {campaign_id}: {response.status_code}")
                    break

                page_retries = 0
                data = response.json()
                entries = data.get("data", [])
                if not entries:
                    break

                for entry in entries:
                    if entry.get("reply_time") and not entry.get("is_bounced"):
                        email = (entry.get("lead_email") or "").lower().strip()
                        if email and email not in replied_by_email:
                            replied_by_email[email] = {
                                "lead_email": email,
                                "lead_name": entry.get("lead_name", ""),
                                "lead_id": entry.get("lead_id") or entry.get("id"),
                                "reply_time": entry.get("reply_time"),
                                "lead_category": entry.get("lead_category"),
                                "stats_id": entry.get("stats_id"),
                                "email_subject": entry.get("email_subject", ""),
                            }

                offset += page_size
                await asyncio.sleep(0.15)

            except Exception as e:
                page_retries += 1
                if page_retries <= max_page_retries:
                    logger.warning(f"Error on statistics page {page} for campaign {campaign_id} (retry {page_retries}): {e}")
                    await asyncio.sleep(3 * page_retries)
                    continue
                else:
                    logger.error(f"Persistent error on page {page} after {max_page_retries} retries: {e}")
                    break

        return list(replied_by_email.values())

    async def get_email_thread_with_client(
        self,
        client: httpx.AsyncClient,
        campaign_id: str,
        lead_id: str
    ) -> List[Dict[str, Any]]:
        """Get email thread using a shared httpx client (avoids per-call connection overhead).

        Same as get_email_thread but accepts an external client for batching.
        """
        if not self._api_key:
            raise ValueError("API key not set")

        try:
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/leads/{lead_id}/message-history",
                params={"api_key": self._api_key},
                client=client,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("history", data.get("messages", []))
            else:
                logger.error(f"Failed to fetch email thread for lead {lead_id}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching email thread for lead {lead_id}: {e}")
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
        hist_resp = await smartlead_request(
            "GET", f"{self.base_url}/campaigns/{campaign_id}/leads/{lead_id}/message-history",
            params={"api_key": self._api_key},
        )
        if hist_resp.status_code != 200:
            return {"error": f"Failed to fetch history: {hist_resp.status_code} {hist_resp.text}"}

        messages = parse_history_response(hist_resp.json())
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
        send_resp = await smartlead_request(
            "POST", f"{self.base_url}/campaigns/{campaign_id}/reply-email-thread",
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
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/analytics",
                params={"api_key": self._api_key},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch campaign statistics: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error fetching campaign statistics: {e}")
            return {}

    # In-memory cache for campaign sequences (rarely change)
    _sequence_cache: Dict[str, tuple] = {}  # campaign_id -> (timestamp, data)
    _SEQUENCE_CACHE_TTL = 3600  # 1 hour

    async def get_campaign_sequences(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get email sequence steps for a campaign, with 1-hour in-memory cache.

        Returns list of sequence steps: [{seq_number, subject, email_body, ...}]
        """
        if not self._api_key:
            raise ValueError("API key not set")

        # Check cache
        cached = self._sequence_cache.get(campaign_id)
        if cached and (time.time() - cached[0]) < self._SEQUENCE_CACHE_TTL:
            return cached[1]

        try:
            response = await smartlead_request(
                "GET", f"{self.base_url}/campaigns/{campaign_id}/sequences",
                params={"api_key": self._api_key},
            )
            if response.status_code == 200:
                data = response.json()
                sequences = data if isinstance(data, list) else data.get("sequences", [])
                self._sequence_cache[campaign_id] = (time.time(), sequences)
                return sequences
            else:
                logger.error(f"Failed to fetch sequences: {response.status_code}")
                return cached[1] if cached else []
        except Exception as e:
            logger.error(f"Error fetching campaign sequences: {e}")
            return cached[1] if cached else []

    # configure_campaign_webhook was removed — it was one of three independent
    # webhook registration paths that caused 360+ duplicates across 102 campaigns.
    # Webhook registration now lives EXCLUSIVELY in crm_scheduler.py →
    # setup_crm_webhooks_on_startup() → SmartleadClient.setup_crm_webhooks().


# Global instance
smartlead_service = SmartleadService()


async def fetch_all_campaign_replies(campaign_id: str, api_key: str, max_pages: int = 20) -> list:
    """Fetch all replies from a campaign using pagination.

    Args:
        campaign_id: Smartlead campaign ID
        api_key: Smartlead API key
        max_pages: Maximum pages to fetch (safety limit)

    Returns:
        List of statistics entries that have reply_time
    """
    all_replies = []
    offset = 0
    page_size = 500

    import asyncio
    retries = 0
    max_retries = 3

    for page in range(max_pages):
        try:
            resp = await smartlead_request(
                "GET", f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics",
                params={"api_key": api_key, "limit": page_size, "offset": offset},
            )
            if resp.status_code == 429:
                retries += 1
                if retries <= max_retries:
                    await asyncio.sleep(5 * retries)
                    continue
                break
            retries = 0
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
                break

        except Exception as e:
            retries += 1
            if retries <= max_retries:
                logger.warning(f"Error fetching page {page} for campaign {campaign_id} (retry {retries}): {e}")
                await asyncio.sleep(3 * retries)
                continue
            logger.error(f"Persistent error on page {page} for campaign {campaign_id}: {e}")
            break

    return all_replies
