"""
GetSales MCP Server
Manage LinkedIn automation: flows, contacts, messages, sender profiles.
"""

import os
import json
import httpx
from fastmcp import FastMCP

API_TOKEN = os.environ.get("GETSALES_API_TOKEN", "")
BASE_URL = "https://amazing.getsales.io"

mcp = FastMCP("GetSales")


def headers() -> dict:
    token = API_TOKEN or os.environ.get("GETSALES_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def api_get(path: str, query: dict = None) -> dict:
    resp = httpx.get(f"{BASE_URL}{path}", headers=headers(), params=query or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict = None) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_put(path: str, body: dict = None) -> dict:
    resp = httpx.put(f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_delete(path: str) -> dict:
    resp = httpx.delete(f"{BASE_URL}{path}", headers=headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# CONTACTS
# ---------------------------------------------------------------------------

@mcp.tool()
def create_contacts(list_uuid: str, leads: list[dict]) -> str:
    """
    Add contacts to a GetSales list.

    Each lead dict supports:
        linkedin_id, first_name, last_name, company_name, linkedin (URL),
        email, domain, headline, position, raw_address, custom_fields (dict)

    Args:
        list_uuid: GetSales list UUID to add contacts to
        leads: List of contact dicts
    """
    data = api_post("/leads/api/leads", {"list_uuid": list_uuid, "leads": leads})
    if isinstance(data, list):
        return f"Created {len(data)} contacts | first UUID: {data[0].get('uuid') if data else 'N/A'}"
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def upsert_contact(
    list_uuid: str,
    linkedin: str = None,
    email: str = None,
    first_name: str = None,
    last_name: str = None,
    company_name: str = None,
    position: str = None,
    custom_fields: dict = None,
) -> str:
    """
    Create or update a single contact. Uses linkedin URL or email as identifier.

    Args:
        list_uuid: GetSales list UUID
        linkedin: LinkedIn profile URL
        email: Email address
        first_name: First name
        last_name: Last name
        company_name: Company name
        position: Job title
        custom_fields: Dict of custom field values
    """
    body: dict = {"list_uuid": list_uuid}
    if linkedin:
        body["linkedin"] = linkedin
    if email:
        body["email"] = email
    if first_name:
        body["first_name"] = first_name
    if last_name:
        body["last_name"] = last_name
    if company_name:
        body["company_name"] = company_name
    if position:
        body["position"] = position
    if custom_fields:
        body["custom_fields"] = custom_fields
    data = api_post("/leads/api/leads/upsert", body)
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def get_contact(lead_uuid: str) -> str:
    """
    Get a contact by UUID.

    Args:
        lead_uuid: Contact UUID
    """
    data = api_get(f"/leads/api/leads/{lead_uuid}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def search_contacts(
    query: str = None,
    linkedin: str = None,
    email: str = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """
    Search contacts by text query, LinkedIn URL, or email.

    Args:
        query: Free text search
        linkedin: LinkedIn profile URL filter
        email: Email address filter
        limit: Max results (default 50)
        offset: Pagination offset
    """
    body: dict = {"limit": limit, "offset": offset}
    if query:
        body["query"] = query
    if linkedin:
        body["linkedin"] = linkedin
    if email:
        body["email"] = email
    data = api_post("/leads/api/leads/search", body)
    leads = data if isinstance(data, list) else data.get("data", [])
    total = data.get("total", len(leads)) if isinstance(data, dict) else len(leads)
    lines = [f"Found {total} contacts (showing {len(leads)})\n"]
    for lead in leads:
        lines.append(
            f"- {lead.get('first_name', '')} {lead.get('last_name', '')} | "
            f"{lead.get('company_name', 'N/A')} | {lead.get('position', '')} | "
            f"uuid: {lead.get('uuid')} | linkedin: {lead.get('linkedin', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
def delete_contact(lead_uuid: str) -> str:
    """
    Delete a contact by UUID.

    Args:
        lead_uuid: Contact UUID
    """
    data = api_delete(f"/leads/api/leads/{lead_uuid}")
    return f"Deleted contact {lead_uuid} | result: {json.dumps(data)}"


# ---------------------------------------------------------------------------
# FLOWS (CAMPAIGNS)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_flows(limit: int = 50, offset: int = 0) -> str:
    """
    List all automation flows (LinkedIn campaigns) in the account.

    Args:
        limit: Max results (default 50)
        offset: Pagination offset
    """
    data = api_get("/flows/api/flows", {"limit": limit, "offset": offset})
    flows = data if isinstance(data, list) else data.get("data", [])
    total = data.get("total", len(flows)) if isinstance(data, dict) else len(flows)
    lines = [f"Found {total} flows (showing {len(flows)})\n"]
    for f in flows:
        lines.append(
            f"- {f.get('name', 'N/A')} | "
            f"status: {f.get('status', 'N/A')} | "
            f"uuid: {f.get('uuid')} | "
            f"leads: {f.get('leads_count', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
def start_flow(flow_uuid: str) -> str:
    """
    Start (activate) a flow.

    Args:
        flow_uuid: Flow UUID
    """
    data = api_put(f"/flows/api/flows/{flow_uuid}/start")
    return f"Flow {flow_uuid} started | result: {json.dumps(data)}"


@mcp.tool()
def stop_flow(flow_uuid: str) -> str:
    """
    Stop (pause) a flow.

    Args:
        flow_uuid: Flow UUID
    """
    data = api_put(f"/flows/api/flows/{flow_uuid}/stop")
    return f"Flow {flow_uuid} stopped | result: {json.dumps(data)}"


@mcp.tool()
def add_lead_to_flow(flow_uuid: str, lead_uuid: str) -> str:
    """
    Add an existing contact to a flow by their UUIDs.

    Args:
        flow_uuid: Flow UUID
        lead_uuid: Contact UUID
    """
    data = api_post(f"/flows/api/flows/{flow_uuid}/leads/{lead_uuid}")
    return f"Added lead {lead_uuid} to flow {flow_uuid} | result: {json.dumps(data)}"


@mcp.tool()
def add_new_lead_to_flow(
    flow_uuid: str,
    linkedin: str = None,
    email: str = None,
    first_name: str = None,
    last_name: str = None,
    company_name: str = None,
    position: str = None,
    custom_fields: dict = None,
) -> str:
    """
    Create a new contact and immediately enroll them in a flow.

    Args:
        flow_uuid: Flow UUID
        linkedin: LinkedIn profile URL (required if no email)
        email: Email address
        first_name: First name
        last_name: Last name
        company_name: Company name
        position: Job title
        custom_fields: Dict of custom field values
    """
    body: dict = {}
    if linkedin:
        body["linkedin"] = linkedin
    if email:
        body["email"] = email
    if first_name:
        body["first_name"] = first_name
    if last_name:
        body["last_name"] = last_name
    if company_name:
        body["company_name"] = company_name
    if position:
        body["position"] = position
    if custom_fields:
        body["custom_fields"] = custom_fields
    data = api_post(f"/flows/api/flows/{flow_uuid}/add-new-lead", body)
    return f"Added new lead to flow {flow_uuid} | result: {json.dumps(data)}"


@mcp.tool()
def cancel_lead_from_flow(lead_uuid: str) -> str:
    """
    Remove a lead from their current active flow.

    Args:
        lead_uuid: Contact UUID
    """
    data = api_put(f"/flows/api/flows/leads/{lead_uuid}/cancel")
    return f"Lead {lead_uuid} cancelled from flow | result: {json.dumps(data)}"


@mcp.tool()
def cancel_lead_from_all_flows(lead_uuid: str) -> str:
    """
    Remove a lead from ALL flows they are enrolled in.

    Args:
        lead_uuid: Contact UUID
    """
    data = api_put(f"/flows/api/flows/leads/{lead_uuid}/cancel-all")
    return f"Lead {lead_uuid} cancelled from all flows | result: {json.dumps(data)}"


# ---------------------------------------------------------------------------
# MESSAGES
# ---------------------------------------------------------------------------

@mcp.tool()
def list_messages(
    lead_uuid: str = None,
    limit: int = 50,
    offset: int = 0,
    order_field: str = "sent_at",
    order_type: str = "desc",
) -> str:
    """
    List LinkedIn messages, optionally filtered by contact.

    Args:
        lead_uuid: Filter messages by contact UUID
        limit: Max results (default 50)
        offset: Pagination offset
        order_field: Sort field (default: sent_at)
        order_type: Sort direction - asc or desc (default: desc)
    """
    query: dict = {
        "limit": limit,
        "offset": offset,
        "order-field": order_field,
        "order-type": order_type,
    }
    if lead_uuid:
        query["filter[lead_uuid]"] = lead_uuid
    data = api_get("/flows/api/linkedin-messages", query)
    messages = data.get("data", []) if isinstance(data, dict) else data
    total = data.get("total", len(messages)) if isinstance(data, dict) else len(messages)
    lines = [f"Found {total} messages (showing {len(messages)})\n"]
    for m in messages:
        lines.append(
            f"[{m.get('sent_at', 'N/A')}] {m.get('type', 'outbound')} | "
            f"lead: {m.get('lead_uuid', 'N/A')} | "
            f"text: {str(m.get('text', ''))[:200]}"
        )
    return "\n".join(lines)


@mcp.tool()
def send_message(sender_profile_uuid: str, lead_uuid: str, text: str) -> str:
    """
    Send a LinkedIn message to a contact manually.

    Args:
        sender_profile_uuid: Sender profile UUID (get from list_sender_profiles)
        lead_uuid: Recipient contact UUID
        text: Message text
    """
    data = api_post("/flows/api/messages", {
        "sender_profile_uuid": sender_profile_uuid,
        "lead_uuid": lead_uuid,
        "text": text,
    })
    return f"Message sent | uuid: {data.get('uuid')} | status: {data.get('status')}"


# ---------------------------------------------------------------------------
# SENDER PROFILES
# ---------------------------------------------------------------------------

@mcp.tool()
def list_sender_profiles(limit: int = 50, offset: int = 0) -> str:
    """
    List all connected LinkedIn sender profiles (accounts).

    Args:
        limit: Max results (default 50)
        offset: Pagination offset
    """
    data = api_get("/flows/api/sender-profiles", {"limit": limit, "offset": offset})
    profiles = data if isinstance(data, list) else data.get("data", [])
    total = data.get("total", len(profiles)) if isinstance(data, dict) else len(profiles)
    lines = [f"Found {total} sender profiles\n"]
    for p in profiles:
        lines.append(
            f"- {p.get('full_name', 'N/A')} | "
            f"status: {p.get('status', 'N/A')} | "
            f"uuid: {p.get('uuid')} | "
            f"linkedin: {p.get('linkedin', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_sender_profile(sender_profile_uuid: str) -> str:
    """
    Get details of a specific sender profile.

    Args:
        sender_profile_uuid: Sender profile UUID
    """
    data = api_get(f"/flows/api/sender-profiles/{sender_profile_uuid}")
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
