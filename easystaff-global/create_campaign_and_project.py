#!/usr/bin/env python3
"""Create SmartLead campaign + system project for UAE-Pakistan Petr."""
import asyncio
import sys
import os
import httpx

sys.path.insert(0, '/app')
from app.services.smartlead_service import SmartleadService

API_BASE = "http://localhost:8000/api"
HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}


async def main():
    # 1. Create SmartLead campaign in draft
    print("=== Creating SmartLead Campaign ===")
    sl = SmartleadService()
    result = await sl.create_campaign("UAE-Pakistan Petr 16/03")
    print(f"Campaign: {result}")
    campaign_id = result.get('id') if result else None
    print(f"Campaign ID: {campaign_id}")

    # 2. Create project via API
    print("\n=== Creating Project ===")
    async with httpx.AsyncClient(timeout=30) as client:
        # Check if project already exists
        resp = await client.get(f"{API_BASE}/contacts/projects/names", headers=HEADERS)
        existing = resp.json() if resp.status_code == 200 else []
        print(f"Existing projects: {[p.get('name') for p in existing]}")

        es_global = next((p for p in existing if 'easystaff global' in p.get('name', '').lower()), None)
        if es_global:
            project_id = es_global['id']
            print(f"Found existing 'easystaff global' project: id={project_id}")
        else:
            # Create new project
            resp = await client.post(f"{API_BASE}/contacts/projects", headers=HEADERS, json={
                "name": "easystaff global",
                "description": "EasyStaff Global outreach — UAE-PK, AU-PH, Arabic-SA corridors",
                "sender_name": "Petr Nikolaev",
                "sender_position": "Partner",
                "sender_company": "easystaff.io",
            })
            if resp.status_code in (200, 201):
                project_id = resp.json().get('id')
                print(f"Created project: id={project_id}")
            else:
                print(f"Create failed: {resp.status_code} {resp.text[:200]}")
                return

        # 3. Update project with campaign_ownership_rules using tag
        print("\n=== Setting Campaign Ownership Rules ===")
        resp = await client.patch(f"{API_BASE}/contacts/projects/{project_id}", headers=HEADERS, json={
            "campaign_ownership_rules": {
                "prefixes": ["UAE-Pakistan Petr"],
                "contains": [],
                "smartlead_tags": ["petr easystaff global"],
            },
            "campaign_filters": ["UAE-Pakistan Petr 16/03"],
        })
        if resp.status_code == 200:
            print(f"Updated project {project_id} with ownership rules")
            rules = resp.json().get('campaign_ownership_rules', {})
            print(f"  Rules: {rules}")
        else:
            print(f"Update failed: {resp.status_code} {resp.text[:200]}")

    print(f"\n=== DONE ===")
    print(f"SmartLead Campaign ID: {campaign_id}")
    print(f"Project ID: {project_id}")
    print(f"")
    print(f"MANUAL STEPS NEEDED in SmartLead UI:")
    print(f'  1. Add tag "petr easystaff global" to campaign')
    print(f"  2. Add email sender accounts to campaign")
    print(f"  3. Set sequence (will be loaded via API after alignment)")


if __name__ == '__main__':
    asyncio.run(main())
