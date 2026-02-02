#!/usr/bin/env python3
"""
Fetch recent contacts from Smartlead API
"""
import os
import sys
import json
import httpx
import asyncio
from datetime import datetime

SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5")
BASE_URL = "https://server.smartlead.ai/api/v1"


async def fetch_smartlead_contacts(limit=1000):
    """Fetch recent contacts from Smartlead"""
    contacts = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # First, get all campaigns
        print("Fetching campaigns...")
        campaigns_resp = await client.get(
            f"{BASE_URL}/campaigns",
            params={"api_key": SMARTLEAD_API_KEY}
        )
        campaigns = campaigns_resp.json()
        
        print(f"Found {len(campaigns)} campaigns")
        
        # Fetch leads from each campaign
        for campaign in campaigns[:10]:  # Limit to first 10 campaigns for now
            campaign_id = campaign.get("id")
            campaign_name = campaign.get("name")
            
            print(f"Fetching leads from campaign: {campaign_name}")
            
            offset = 0
            page_size = 100
            
            while len(contacts) < limit:
                try:
                    leads_resp = await client.get(
                        f"{BASE_URL}/campaigns/{campaign_id}/leads",
                        params={
                            "api_key": SMARTLEAD_API_KEY,
                            "offset": offset,
                            "limit": page_size
                        }
                    )
                    
                    if leads_resp.status_code != 200:
                        print(f"Error fetching leads: {leads_resp.status_code}")
                        break
                    
                    leads_data = leads_resp.json()
                    leads = leads_data.get("data", [])
                    
                    if not leads:
                        break
                    
                    for lead in leads:
                        # Extract lead data - it's nested in "lead" field
                        lead_data = lead.get("lead", {})
                        
                        contact = {
                            "source": "smartlead",
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "email": lead_data.get("email"),
                            "first_name": lead_data.get("first_name"),
                            "last_name": lead_data.get("last_name"),
                            "company": lead_data.get("company_name"),
                            "linkedin": lead_data.get("linkedin_profile") or lead_data.get("linkedin_url"),
                            "phone": lead_data.get("phone_number"),
                            "title": None,  # Not provided by Smartlead
                            "location": lead_data.get("location"),
                            "status": lead.get("status"),  # Campaign status, not lead status
                            "replied": lead.get("replied", False),
                            "opened": lead.get("opened", False),
                            "clicked": lead.get("clicked", False),
                            "created_at": lead.get("created_at"),
                            "raw_data": lead
                        }
                        contacts.append(contact)
                    
                    offset += page_size
                    
                    if len(leads) < page_size:
                        break
                        
                except Exception as e:
                    print(f"Error fetching leads: {e}")
                    break
            
            if len(contacts) >= limit:
                break
    
    return contacts[:limit]


async def main():
    print("=" * 60)
    print("Fetching Smartlead Contacts")
    print("=" * 60)
    
    contacts = await fetch_smartlead_contacts(limit=1000)
    
    print(f"\nFetched {len(contacts)} contacts from Smartlead")
    
    # Save to file
    output_file = "smartlead_contacts.json"
    with open(output_file, "w") as f:
        json.dump(contacts, f, indent=2, default=str)
    
    print(f"Saved to {output_file}")
    
    # Print summary
    replied_count = sum(1 for c in contacts if c.get("replied"))
    print(f"\nSummary:")
    print(f"  Total: {len(contacts)}")
    print(f"  Replied: {replied_count}")
    print(f"  With LinkedIn: {sum(1 for c in contacts if c.get('linkedin'))}")
    print(f"  With Email: {sum(1 for c in contacts if c.get('email'))}")


if __name__ == "__main__":
    asyncio.run(main())
