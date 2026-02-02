#!/usr/bin/env python3
"""
Fetch recent contacts from GetSales API
"""
import os
import sys
import json
import httpx
import asyncio
from datetime import datetime

GETSALES_API_KEY = os.getenv("GETSALES_API_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc")
BASE_URL = "https://amazing.getsales.io"


async def fetch_getsales_contacts(limit=1000):
    """Fetch recent contacts from GetSales"""
    contacts = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {GETSALES_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print("Fetching contacts from GetSales...")
        
        offset = 0
        page_size = 100
        
        while len(contacts) < limit:
            try:
                # GetSales API endpoint for searching contacts
                payload = {
                    "filter": {},  # Empty filter to get all
                    "limit": page_size,
                    "offset": offset,
                    "order_field": "created_at",
                    "order_type": "desc",
                    "disable_aggregation": False
                }
                
                resp = await client.post(
                    f"{BASE_URL}/leads/api/leads/search",
                    headers=headers,
                    json=payload
                )
                
                if resp.status_code != 200:
                    print(f"Error fetching contacts: {resp.status_code}")
                    print(f"Response: {resp.text}")
                    break
                
                data = resp.json()
                leads = data.get("data", [])
                total = data.get("total", 0)
                
                print(f"Fetched offset {offset}: {len(leads)} contacts (total available: {total})")
                
                if not leads:
                    break
                
                for lead_wrapper in leads:
                    # GetSales wraps the lead in a "lead" field
                    lead = lead_wrapper.get("lead", {})
                    
                    # Extract email - could be work_email or personal_email
                    email = lead.get("work_email") or lead.get("personal_email") or lead.get("email")
                    
                    # Extract LinkedIn URL
                    linkedin = lead.get("linkedin")
                    if linkedin and not linkedin.startswith("http"):
                        linkedin = f"https://linkedin.com/in/{linkedin}"
                    
                    # Extract phone
                    phone = lead.get("work_phone_number") or lead.get("personal_phone_number")
                    
                    # Extract location
                    location = lead.get("raw_address")
                    if not location and lead.get("location"):
                        location_data = lead.get("location", [])
                        if location_data and len(location_data) > 0:
                            location = location_data[0].get("name")
                    
                    contact = {
                        "source": "getsales",
                        "email": email,
                        "first_name": lead.get("first_name"),
                        "last_name": lead.get("last_name"),
                        "company": lead.get("company_name"),
                        "linkedin": linkedin,
                        "phone": phone,
                        "title": lead.get("position") or lead.get("headline"),
                        "location": location,
                        "status": lead.get("status"),
                        "linkedin_status": lead.get("linkedin_status"),
                        "email_status": lead.get("email_status"),
                        "created_at": lead.get("created_at"),
                        "raw_data": lead_wrapper
                    }
                    contacts.append(contact)
                
                offset += page_size
                
                # Check if we've reached the end
                if len(leads) < page_size or offset >= total:
                    break
                    
            except Exception as e:
                print(f"Error fetching contacts: {e}")
                import traceback
                traceback.print_exc()
                break
    
    return contacts[:limit]


async def main():
    print("=" * 60)
    print("Fetching GetSales Contacts")
    print("=" * 60)
    
    contacts = await fetch_getsales_contacts(limit=1000)
    
    print(f"\nFetched {len(contacts)} contacts from GetSales")
    
    # Save to file
    output_file = "getsales_contacts.json"
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
