"""
Findymail MCP Server
Find and verify business emails via Findymail API.
"""

import os
import json
import httpx
from fastmcp import FastMCP

API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
BASE_URL = "https://app.findymail.com"

mcp = FastMCP("Findymail")


def headers() -> dict:
    key = API_KEY or os.environ.get("FINDYMAIL_API_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def api_get(path: str) -> dict:
    resp = httpx.get(f"{BASE_URL}{path}", headers=headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", headers=headers(), json=body, timeout=60)
    if resp.status_code == 404:
        return {"found": False, "email": None}
    if resp.status_code == 402:
        return {"error": "Out of credits"}
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
def find_email_by_linkedin(linkedin_url: str) -> str:
    """
    Find email by LinkedIn profile URL.

    Args:
        linkedin_url: Full LinkedIn profile URL (e.g. https://linkedin.com/in/johndoe)

    Returns:
        JSON with email and verified status
    """
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    data = api_post("/api/search/linkedin", {"linkedin_url": url})
    contact = data.get("contact", {})
    email = data.get("email") or contact.get("email")
    verified = data.get("verified", False) or contact.get("verified", False)

    return json.dumps({
        "email": email,
        "verified": verified,
        "found": bool(email),
        "raw": data,
    }, ensure_ascii=False)


@mcp.tool()
def find_email_by_name(name: str, domain: str) -> str:
    """
    Find email by person's full name and company domain.

    Args:
        name: Full name (e.g. "John Doe")
        domain: Company domain or name (e.g. "acme.com" or "Acme Inc")

    Returns:
        JSON with email and verified status
    """
    data = api_post("/api/search/name", {"name": name, "domain": domain})
    contact = data.get("contact", {})
    email = data.get("email") or contact.get("email")
    verified = data.get("verified", False) or contact.get("verified", False)

    return json.dumps({
        "email": email,
        "verified": verified,
        "found": bool(email),
        "raw": data,
    }, ensure_ascii=False)


@mcp.tool()
def verify_email(email: str) -> str:
    """
    Verify if an email is valid and won't bounce.

    Args:
        email: Email address to verify

    Returns:
        JSON with verification result
    """
    data = api_post("/api/verify", {"email": email})
    return json.dumps({
        "email": data.get("email", email),
        "verified": data.get("verified", False),
        "provider": data.get("provider"),
        "raw": data,
    }, ensure_ascii=False)


@mcp.tool()
def get_credits() -> str:
    """
    Check remaining Findymail credits balance.

    Returns:
        JSON with credits info
    """
    data = api_get("/api/credits")
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
def find_emails_bulk(contacts_json: str) -> str:
    """
    Find emails for multiple contacts by LinkedIn URL.
    Use this for enriching a list of contacts.

    Args:
        contacts_json: JSON array of objects with fields:
            - name: person's name
            - linkedin_url: LinkedIn profile URL
            - company: company name (optional, for reference)

    Returns:
        JSON array with email results for each contact
    """
    contacts = json.loads(contacts_json)
    results = []

    for c in contacts:
        li_url = c.get("linkedin_url", "").strip()
        name = c.get("name", "")

        if not li_url:
            results.append({**c, "email": None, "verified": False, "found": False})
            continue

        if not li_url.startswith("http"):
            li_url = f"https://{li_url}"

        try:
            data = api_post("/api/search/linkedin", {"linkedin_url": li_url})
            contact = data.get("contact", {})
            email = data.get("email") or contact.get("email")
            verified = data.get("verified", False) or contact.get("verified", False)
            results.append({**c, "email": email, "verified": verified, "found": bool(email)})
        except Exception as e:
            if "Out of credits" in str(e) or "402" in str(e):
                return json.dumps({"error": "Out of credits", "processed": results}, ensure_ascii=False)
            results.append({**c, "email": None, "verified": False, "error": str(e)})

    found = sum(1 for r in results if r.get("found"))
    return json.dumps({
        "total": len(results),
        "found": found,
        "not_found": len(results) - found,
        "results": results,
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
