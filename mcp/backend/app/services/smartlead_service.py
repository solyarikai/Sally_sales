"""SmartLead Service — adapted for MCP. Only campaign creation (DRAFT) + sequence push."""
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


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
                else:
                    resp = await client.get(f"{self.base_url}{endpoint}", params=p)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"SmartLead {endpoint}: {e}")
            return None

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        data = await self._api_call("GET", "/campaigns")
        return data is not None

    async def get_campaigns(self) -> List[Dict[str, Any]]:
        data = await self._api_call("GET", "/campaigns")
        return data if isinstance(data, list) else []

    async def create_campaign(self, name: str) -> Optional[Dict[str, Any]]:
        """Create a DRAFT campaign — NEVER activates or adds leads."""
        return await self._api_call("POST", "/campaigns/create", {"name": name})

    async def set_campaign_sequences(self, campaign_id: int, sequences: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Set email sequence steps on a campaign."""
        return await self._api_call("POST", f"/campaigns/{campaign_id}/sequences", {"sequences": sequences})

    async def get_campaign_sequences(self, campaign_id: int) -> Optional[List[Dict[str, Any]]]:
        data = await self._api_call("GET", f"/campaigns/{campaign_id}/sequences")
        return data if isinstance(data, list) else None

    async def export_campaign_leads(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Export ALL leads from a campaign as CSV. Returns list of lead dicts."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads-export",
                    params={"api_key": self.api_key},
                )
                if resp.status_code != 200:
                    logger.error(f"SmartLead export {campaign_id}: HTTP {resp.status_code}")
                    return []

                # Parse CSV response
                import csv
                import io
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
