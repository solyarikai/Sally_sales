"""SmartLead Service — full campaign lifecycle for MCP."""
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Country → IANA timezone mapping (business hours 9-18)
COUNTRY_TIMEZONES = {
    "united states": "America/New_York", "us": "America/New_York",
    "united kingdom": "Europe/London", "uk": "Europe/London",
    "germany": "Europe/Berlin", "austria": "Europe/Vienna", "switzerland": "Europe/Zurich",
    "france": "Europe/Paris", "spain": "Europe/Madrid", "italy": "Europe/Rome",
    "netherlands": "Europe/Amsterdam", "belgium": "Europe/Brussels",
    "india": "Asia/Kolkata", "australia": "Australia/Sydney",
    "united arab emirates": "Asia/Dubai", "uae": "Asia/Dubai",
    "south africa": "Africa/Johannesburg", "nigeria": "Africa/Lagos",
    "brazil": "America/Sao_Paulo", "mexico": "America/Mexico_City",
    "canada": "America/Toronto", "japan": "Asia/Tokyo",
    "singapore": "Asia/Singapore", "philippines": "Asia/Manila",
    "russia": "Europe/Moscow", "israel": "Asia/Jerusalem",
    "turkey": "Europe/Istanbul", "saudi arabia": "Asia/Riyadh",
    "qatar": "Asia/Qatar", "kuwait": "Asia/Kuwait",
    "poland": "Europe/Warsaw", "czech republic": "Europe/Prague",
    "romania": "Europe/Bucharest", "ukraine": "Europe/Kyiv",
}


def get_timezone_for_country(country: str) -> str:
    """Get IANA timezone for a country. Defaults to UTC."""
    if not country:
        return "UTC"
    return COUNTRY_TIMEZONES.get(country.lower().strip(), "UTC")


class SmartLeadService:
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self.base_url = "https://server.smartlead.ai/api/v1"

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        from app.config import settings
        return settings.SMARTLEAD_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _api_call(self, method: str, endpoint: str, json_data: dict = None, params: dict = None) -> Optional[dict]:
        try:
            p = params or {}
            p["api_key"] = self.api_key
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "POST":
                    resp = await client.post(f"{self.base_url}{endpoint}", json=json_data, params=p)
                elif method == "PATCH":
                    resp = await client.patch(f"{self.base_url}{endpoint}", json=json_data, params=p)
                else:
                    resp = await client.get(f"{self.base_url}{endpoint}", params=p)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"SmartLead {method} {endpoint}: {e}")
            return None

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        data = await self._api_call("GET", "/campaigns")
        return data is not None

    async def get_campaigns(self) -> List[Dict[str, Any]]:
        data = await self._api_call("GET", "/campaigns")
        return data if isinstance(data, list) else []

    # ── Campaign Creation ──

    async def create_campaign(self, name: str) -> Optional[Dict[str, Any]]:
        """Create a DRAFT campaign."""
        return await self._api_call("POST", "/campaigns/create", {"name": name})

    async def set_campaign_sequences(self, campaign_id: int, sequences: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Set email sequence steps."""
        # Format sequences for SmartLead API
        formatted = []
        for i, step in enumerate(sequences):
            formatted.append({
                "seq_number": step.get("step", i + 1),
                "seq_delay_details": {"delay_in_days": step.get("day", i * 3)},
                "subject": step.get("subject", ""),
                "email_body": step.get("body", ""),
            })
        return await self._api_call("POST", f"/campaigns/{campaign_id}/sequences", {"sequences": formatted})

    async def set_campaign_schedule(self, campaign_id: int, timezone: str, start_hour: str = "09:00", end_hour: str = "18:00") -> Optional[Dict[str, Any]]:
        """Set campaign sending schedule — 9-6 business hours in target timezone."""
        return await self._api_call("POST", f"/campaigns/{campaign_id}/schedule", {
            "timezone": timezone,
            "days_of_the_week": [1, 2, 3, 4, 5],  # Mon-Fri only
            "start_hour": start_hour,
            "end_hour": end_hour,
            "min_time_btw_emails": 3,
            "max_new_leads_per_day": 100,
        })

    async def set_campaign_settings(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Set campaign delivery settings — matching production campaigns."""
        return await self._api_call("POST", f"/campaigns/{campaign_id}/settings", {
            "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
            "stop_lead_settings": "REPLY_TO_AN_EMAIL",
            "send_as_plain_text": True,
            "follow_up_percentage": 40,
        })

    async def set_campaign_email_accounts(self, campaign_id: int, account_ids: List[int]) -> Optional[Dict[str, Any]]:
        """Assign email sending accounts to campaign."""
        return await self._api_call("POST", f"/campaigns/{campaign_id}/email-accounts", {
            "email_account_ids": account_ids,
        })

    async def get_email_accounts(self) -> List[Dict[str, Any]]:
        """Get all email accounts."""
        data = await self._api_call("GET", "/email-accounts")
        return data if isinstance(data, list) else []

    async def get_campaign_email_accounts(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get email accounts assigned to a specific campaign."""
        data = await self._api_call("GET", f"/campaigns/{campaign_id}/email-accounts")
        return data if isinstance(data, list) else []

    # ── Leads ──

    async def export_campaign_leads(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Export ALL leads from a campaign as CSV."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads-export",
                    params={"api_key": self.api_key},
                )
                if resp.status_code != 200:
                    return []
                import csv, io
                text = resp.text
                if not text.strip():
                    return []
                reader = csv.DictReader(io.StringIO(text))
                leads = []
                for row in reader:
                    email = row.get("email", "").strip()
                    if not email:
                        continue
                    domain = email.split("@")[1] if "@" in email else ""
                    leads.append({
                        "email": email,
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "company_name": row.get("company_name", ""),
                        "domain": domain,
                    })
                return leads
        except Exception as e:
            logger.error(f"SmartLead export {campaign_id} failed: {e}")
            return []

    async def get_campaign_sequences(self, campaign_id: int) -> Optional[List[Dict[str, Any]]]:
        data = await self._api_call("GET", f"/campaigns/{campaign_id}/sequences")
        return data if isinstance(data, list) else None

    async def get_campaign_leads_with_status(self, campaign_id: int, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get leads from a campaign, optionally filtered by status."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["lead_status"] = status
        data = await self._api_call("GET", f"/campaigns/{campaign_id}/leads", params=params)
        if not data:
            return []
        return data if isinstance(data, list) else data.get("data", data.get("leads", []))

    async def get_lead_message_history(self, campaign_id: int, email: str) -> List[Dict[str, Any]]:
        """Get full message thread for one lead."""
        data = await self._api_call("GET", f"/campaigns/{campaign_id}/leads/{email}/message-history")
        return data if isinstance(data, list) else []

    async def add_leads_to_campaign(self, campaign_id: int, leads: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Add leads to a SmartLead campaign.

        Each lead dict: {email, first_name, last_name, company_name, custom_fields?}
        """
        formatted = []
        for lead in leads:
            entry = {
                "email": lead["email"],
                "first_name": lead.get("first_name", "Test"),
                "last_name": lead.get("last_name", "Lead"),
                "company_name": lead.get("company_name", "TEST - DELETE"),
            }
            if lead.get("custom_fields"):
                entry["custom_fields"] = lead["custom_fields"]
            formatted.append(entry)

        return await self._api_call("POST", f"/campaigns/{campaign_id}/leads", {"lead_list": formatted})

    async def update_campaign_status(self, campaign_id: int, status: str = "START") -> Optional[Dict[str, Any]]:
        """Start/pause/stop a campaign. Status: START, PAUSE, STOP."""
        return await self._api_call("POST", f"/campaigns/{campaign_id}/status", {"status": status})

    async def add_test_lead_and_activate(
        self,
        campaign_id: int,
        test_email: str = "pn@getsally.io",
        sample_custom_fields: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Add a test lead to campaign and activate it so SmartLead sends the email.

        This mirrors the existing platform's battle-tested approach:
        instead of using SmartLead's buggy /send-test-email API,
        we add the user as a real lead and let SmartLead send normally.
        """
        # Build test lead with sample custom fields for proper variable substitution
        test_lead = {
            "email": test_email,
            "first_name": "Test",
            "last_name": "Lead",
            "company_name": "TEST - DELETE",
        }
        if sample_custom_fields:
            # Copy custom fields from a real lead so merge tags resolve
            test_lead["custom_fields"] = {
                **sample_custom_fields,
                "is_test_lead": "true",
            }
        else:
            test_lead["custom_fields"] = {"is_test_lead": "true"}

        result = await self.add_leads_to_campaign(campaign_id, [test_lead])
        if not result:
            return {"ok": False, "error": "Failed to add test lead to campaign"}

        # Activate the campaign so SmartLead sends
        status_result = await self.update_campaign_status(campaign_id, "START")
        if not status_result:
            return {"ok": False, "error": "Test lead added but failed to activate campaign", "lead_added": True}

        return {"ok": True, "test_email": test_email, "campaign_activated": True}
