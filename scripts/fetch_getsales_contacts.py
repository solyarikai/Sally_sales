#!/usr/bin/env python3
"""
Fetch ALL contacts from ALL lists in GetSales API
"""
import os
import sys
import json
import httpx
import asyncio
from datetime import datetime

GETSALES_API_KEY = os.getenv("GETSALES_API_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc")
BASE_URL = "https://amazing.getsales.io"


async def fetch_all_lists(client, headers):
    """Fetch all lists from GetSales"""
    print("Fetching all GetSales lists...")
    resp = await client.get(f"{BASE_URL}/leads/api/lists", headers=headers)
    
    if resp.status_code != 200:
        print(f"Error fetching lists: {resp.status_code}")
        return []
    
    data = resp.json()
    lists = data.get("data", [])
    print(f"Found {len(lists)} lists")
    return lists


async def fetch_all_flows(client, headers):
    """Fetch all flows/automations from GetSales"""
    print("Fetching all GetSales flows...")
    resp = await client.get(f"{BASE_URL}/flows/api/flows", headers=headers)
    
    if resp.status_code != 200:
        print(f"Error fetching flows: {resp.status_code}")
        return []
    
    data = resp.json()
    flows = data.get("data", [])
    print(f"Found {len(flows)} flows")
    return flows


async def fetch_contacts_from_list(client, headers, list_uuid, list_name):
    """Fetch all contacts from a specific list"""
    contacts = []
    offset = 0
    page_size = 100
    
    while True:
        try:
            payload = {
                "filter": {"list_uuid": list_uuid},
                "limit": page_size,
                "offset": offset
            }
            
            resp = await client.post(
                f"{BASE_URL}/leads/api/leads/search",
                headers=headers,
                json=payload
            )
            
            if resp.status_code != 200:
                print(f"  Error fetching from list {list_name}: {resp.status_code}")
                break
            
            data = resp.json()
            leads_data = data.get("data", [])
            total = data.get("total", 0)
            
            if not leads_data:
                break
            
            for item in leads_data:
                contact = parse_getsales_contact(item, list_name, list_uuid)
                contacts.append(contact)
            
            offset += page_size
            
            if offset >= total:
                break
                
        except Exception as e:
            print(f"  Error: {e}")
            break
    
    return contacts


async def fetch_contacts_global(client, headers, limit=50000):
    """Fetch contacts globally (no list filter) - catches any not in lists"""
    contacts = []
    offset = 0
    page_size = 100
    
    print("Fetching global contacts (not in specific lists)...")
    
    while len(contacts) < limit:
        try:
            payload = {
                "filter": {},
                "limit": page_size,
                "offset": offset,
                "order_field": "created_at",
                "order_type": "desc"
            }
            
            resp = await client.post(
                f"{BASE_URL}/leads/api/leads/search",
                headers=headers,
                json=payload
            )
            
            if resp.status_code != 200:
                print(f"Error fetching global contacts: {resp.status_code}")
                break
            
            data = resp.json()
            leads_data = data.get("data", [])
            total = data.get("total", 0)
            
            if offset == 0:
                print(f"Total contacts in GetSales: {total}")
            
            if not leads_data:
                break
            
            for item in leads_data:
                contact = parse_getsales_contact(item, None, None)
                contacts.append(contact)
            
            offset += page_size
            
            if len(leads_data) < page_size or offset >= total:
                break
                
        except Exception as e:
            print(f"Error: {e}")
            break
    
    return contacts


def parse_getsales_contact(item, list_name=None, list_uuid=None):
    """Parse a GetSales contact item into our standard format"""
    lead = item.get("lead", {})
    custom_fields = item.get("custom_fields", {})
    markers = item.get("markers", [])
    flows = item.get("flows", [])
    
    # Extract email
    email = lead.get("work_email") or lead.get("personal_email")
    
    # Extract LinkedIn URL
    linkedin = lead.get("linkedin")
    if linkedin and not linkedin.startswith("http"):
        linkedin = f"https://linkedin.com/in/{linkedin}"
    
    # Extract phone
    phone = lead.get("work_phone_number") or lead.get("personal_phone_number")
    
    # Extract location
    location = lead.get("raw_address")
    location_data = lead.get("location", [])
    if not location and location_data and len(location_data) > 0:
        location = location_data[0].get("name") if isinstance(location_data[0], dict) else str(location_data[0])
    
    # Extract experience
    experience = lead.get("experience", [])
    current_experience = experience[0] if experience else {}
    
    # Flow names from the flows array
    flow_names = [f.get("name") for f in flows if f.get("name")]
    
    return {
        "source": "getsales",
        # Core fields
        "uuid": lead.get("uuid"),
        "email": email,
        "work_email": lead.get("work_email"),
        "personal_email": lead.get("personal_email"),
        "first_name": lead.get("first_name"),
        "last_name": lead.get("last_name"),
        "name": lead.get("name"),
        "company": lead.get("company_name"),
        "linkedin": linkedin,
        "linkedin_id": lead.get("ln_id"),
        "linkedin_member_id": lead.get("ln_member_id"),
        "phone": phone,
        "work_phone": lead.get("work_phone_number"),
        "personal_phone": lead.get("personal_phone_number"),
        
        # Position info
        "title": lead.get("position"),
        "headline": lead.get("headline"),
        "about": lead.get("about"),
        
        # Location
        "location": location,
        "raw_address": lead.get("raw_address"),
        
        # Social
        "facebook": lead.get("facebook"),
        "twitter": lead.get("twitter"),
        "avatar_url": lead.get("avatar_url"),
        
        # LinkedIn stats
        "connections_number": lead.get("connections_number"),
        "followers_number": lead.get("followers_number"),
        "has_premium": lead.get("has_premium"),
        "has_open_profile": lead.get("has_open_profile"),
        
        # Languages
        "primary_language": lead.get("primary_language"),
        "supported_languages": lead.get("supported_languages"),
        
        # Status
        "status": lead.get("status"),
        "linkedin_status": lead.get("linkedin_status"),
        "email_status": lead.get("email_status"),
        
        # Experience, education, skills
        "experience": experience,
        "current_company": current_experience.get("company_name"),
        "current_position": current_experience.get("position"),
        "educations": lead.get("educations"),
        "skills": lead.get("skills"),
        
        # Timestamps
        "created_at": lead.get("created_at"),
        "updated_at": lead.get("updated_at"),
        "last_enrich_at": lead.get("last_enrich_at"),
        
        # List info
        "list_name": list_name,
        "list_uuid": list_uuid or lead.get("list_uuid"),
        
        # Custom fields and tags
        "custom_fields": custom_fields,
        "tags": lead.get("tags"),
        "markers": markers,
        "flows": flow_names,
        
        # Pipeline
        "pipeline_stage_uuid": lead.get("pipeline_stage_uuid"),
        
        # Full raw data
        "raw_data": item
    }


async def fetch_getsales_contacts():
    """Fetch ALL contacts from ALL lists in GetSales"""
    all_contacts = {}  # Use dict to dedupe by UUID
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        headers = {
            "Authorization": f"Bearer {GETSALES_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 1. Get all lists
        lists = await fetch_all_lists(client, headers)
        
        # 2. Get all flows
        flows = await fetch_all_flows(client, headers)
        
        # Create a mapping of list names
        list_info = {lst["uuid"]: lst["name"] for lst in lists}
        
        # 3. Fetch contacts from each list
        print(f"\n{'='*60}")
        print("Fetching contacts from each list...")
        print(f"{'='*60}")
        
        for lst in lists:
            list_uuid = lst["uuid"]
            list_name = lst["name"]
            
            contacts = await fetch_contacts_from_list(client, headers, list_uuid, list_name)
            
            new_count = 0
            for c in contacts:
                uuid = c.get("uuid")
                if uuid and uuid not in all_contacts:
                    all_contacts[uuid] = c
                    new_count += 1
                elif uuid and uuid in all_contacts:
                    # Add this list to existing contact's lists
                    existing = all_contacts[uuid]
                    if existing.get("list_name") and list_name:
                        if list_name not in existing["list_name"]:
                            existing["list_name"] = f"{existing['list_name']}, {list_name}"
                    elif list_name:
                        existing["list_name"] = list_name
            
            print(f"  [{list_name}]: {len(contacts)} contacts ({new_count} new)")
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # 4. Also fetch global contacts to catch any not in lists
        print(f"\n{'='*60}")
        global_contacts = await fetch_contacts_global(client, headers, limit=50000)
        
        new_from_global = 0
        for c in global_contacts:
            uuid = c.get("uuid")
            if uuid and uuid not in all_contacts:
                all_contacts[uuid] = c
                new_from_global += 1
        
        print(f"Global fetch: {len(global_contacts)} contacts ({new_from_global} new unique)")
    
    return list(all_contacts.values())


async def main():
    print("=" * 60)
    print("Fetching ALL GetSales Contacts from ALL Lists")
    print("=" * 60)
    
    contacts = await fetch_getsales_contacts()
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(contacts)} unique contacts from GetSales")
    print(f"{'='*60}")
    
    # Save to file
    output_file = "getsales_contacts.json"
    with open(output_file, "w") as f:
        json.dump(contacts, f, indent=2, default=str)
    
    print(f"Saved to {output_file}")
    
    # Print summary
    with_email = sum(1 for c in contacts if c.get("email"))
    with_linkedin = sum(1 for c in contacts if c.get("linkedin"))
    with_title = sum(1 for c in contacts if c.get("title"))
    with_list = sum(1 for c in contacts if c.get("list_name"))
    
    # Count by list
    list_counts = {}
    for c in contacts:
        list_name = c.get("list_name") or "No List"
        list_counts[list_name] = list_counts.get(list_name, 0) + 1
    
    print(f"\nSummary:")
    print(f"  Total: {len(contacts)}")
    print(f"  With Email: {with_email}")
    print(f"  With LinkedIn: {with_linkedin}")
    print(f"  With Title: {with_title}")
    print(f"  With List: {with_list}")
    
    print(f"\nBy List:")
    for name, count in sorted(list_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {name}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
