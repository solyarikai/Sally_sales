#!/usr/bin/env python3
"""
Fetch ALL contacts with ALL columns from Smartlead API
"""
import os
import sys
import json
import httpx
import asyncio
from datetime import datetime

SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5")
BASE_URL = "https://server.smartlead.ai/api/v1"


async def fetch_smartlead_contacts(limit=50000):
    """Fetch ALL contacts from Smartlead using global leads endpoint"""
    contacts = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("Fetching leads from Smartlead (all campaigns)...")
        
        offset = 0
        page_size = 100
        
        while len(contacts) < limit:
            try:
                # Use global leads endpoint to get all leads across all campaigns
                leads_resp = await client.get(
                    f"{BASE_URL}/leads/global-leads",
                    params={
                        "api_key": SMARTLEAD_API_KEY,
                        "offset": offset,
                        "limit": page_size
                    }
                )
                
                if leads_resp.status_code != 200:
                    print(f"Error fetching leads: {leads_resp.status_code}")
                    # Don't print full response (might be HTML error page)
                    break
                
                leads_data = leads_resp.json()
                leads = leads_data.get("data", [])
                
                if not leads:
                    print(f"No more leads found at offset {offset}")
                    break
                
                print(f"Fetched {len(leads)} leads at offset {offset}")
                
                for lead in leads:
                    # Extract ALL custom fields
                    custom_fields = lead.get("custom_fields", {})
                    
                    # Get campaigns info
                    campaigns = lead.get("campaigns", [])
                    campaign_names = [c.get("campaign_name") for c in campaigns if c.get("campaign_name")]
                    campaign_statuses = [c.get("lead_status") for c in campaigns if c.get("lead_status")]
                    
                    # Check if replied in any campaign
                    replied = any(c.get("lead_status") == "REPLIED" for c in campaigns)
                    
                    contact = {
                        "source": "smartlead",
                        # Core fields
                        "id": lead.get("id"),
                        "email": lead.get("email"),
                        "first_name": lead.get("first_name"),
                        "last_name": lead.get("last_name"),
                        "company": lead.get("company_name"),
                        "website": lead.get("website"),
                        "company_url": lead.get("company_url"),
                        "linkedin": lead.get("linkedin_profile"),
                        "phone": lead.get("phone_number"),
                        "location": lead.get("location"),
                        "created_at": lead.get("created_at"),
                        
                        # Title from custom fields
                        "title": custom_fields.get("Title") or custom_fields.get("title") or custom_fields.get("Job Title"),
                        "industry": custom_fields.get("Industry") or custom_fields.get("industry"),
                        "timezone": custom_fields.get("timezone"),
                        "employees": custom_fields.get("Employees") or custom_fields.get("#_Employees"),
                        
                        # Campaign info
                        "campaigns": campaign_names,
                        "campaign_statuses": campaign_statuses,
                        "replied": replied,
                        
                        # All custom fields
                        "custom_fields": custom_fields,
                        
                        # Full raw data
                        "raw_data": lead
                    }
                    contacts.append(contact)
                
                offset += page_size
                
                if len(leads) < page_size:
                    print(f"Reached end of leads (got {len(leads)} < {page_size})")
                    break
                
                # Rate limiting - Smartlead allows 10 requests per 2 seconds
                await asyncio.sleep(0.2)
                    
            except Exception as e:
                print(f"Error fetching leads: {e}")
                import traceback
                traceback.print_exc()
                break
    
    return contacts[:limit]


async def main():
    print("=" * 60)
    print("Fetching Smartlead Contacts (ALL columns)")
    print("=" * 60)
    
    contacts = await fetch_smartlead_contacts(limit=50000)
    
    print(f"\nFetched {len(contacts)} contacts from Smartlead")
    
    # Save to file
    output_file = "smartlead_contacts.json"
    with open(output_file, "w") as f:
        json.dump(contacts, f, indent=2, default=str)
    
    print(f"Saved to {output_file}")
    
    # Print summary
    replied_count = sum(1 for c in contacts if c.get("replied"))
    with_email = sum(1 for c in contacts if c.get("email"))
    with_linkedin = sum(1 for c in contacts if c.get("linkedin"))
    with_title = sum(1 for c in contacts if c.get("title"))
    
    print(f"\nSummary:")
    print(f"  Total: {len(contacts)}")
    print(f"  With Email: {with_email}")
    print(f"  With LinkedIn: {with_linkedin}")
    print(f"  With Title: {with_title}")
    print(f"  Replied: {replied_count}")


if __name__ == "__main__":
    asyncio.run(main())
