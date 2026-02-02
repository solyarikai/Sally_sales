#!/usr/bin/env python3
"""
Merge contacts from Smartlead and GetSales by LinkedIn URL or Email
"""
import json
import sys
from urllib.parse import urlparse


def normalize_linkedin(url):
    """Normalize LinkedIn URL to compare"""
    if not url:
        return None
    
    url = url.strip().lower()
    
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Extract the profile path
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        # Remove /in/ prefix if present
        if '/in/' in path:
            path = path.split('/in/')[-1]
        
        # Get just the username
        username = path.strip('/').split('/')[0]
        
        return username if username else None
    except:
        return None


def normalize_email(email):
    """Normalize email for comparison"""
    if not email:
        return None
    return email.strip().lower()


def merge_contacts(smartlead_file="smartlead_contacts.json", getsales_file="getsales_contacts.json"):
    """Merge contacts from both sources"""
    
    # Load contacts
    print("Loading contacts...")
    
    try:
        with open(smartlead_file, "r") as f:
            smartlead_contacts = json.load(f)
    except FileNotFoundError:
        print(f"Error: {smartlead_file} not found. Run fetch_smartlead_contacts.py first.")
        return
    
    try:
        with open(getsales_file, "r") as f:
            getsales_contacts = json.load(f)
    except FileNotFoundError:
        print(f"Error: {getsales_file} not found. Run fetch_getsales_contacts.py first.")
        return
    
    print(f"Loaded {len(smartlead_contacts)} Smartlead contacts")
    print(f"Loaded {len(getsales_contacts)} GetSales contacts")
    
    # Build lookup maps
    linkedin_map = {}
    email_map = {}
    
    # Index Smartlead contacts
    for contact in smartlead_contacts:
        linkedin = normalize_linkedin(contact.get("linkedin"))
        email = normalize_email(contact.get("email"))
        
        if linkedin:
            linkedin_map[linkedin] = contact
        if email:
            email_map[email] = contact
    
    # Merge GetSales contacts
    merged = []
    matched_by_linkedin = 0
    matched_by_email = 0
    unmatched = 0
    
    for gs_contact in getsales_contacts:
        linkedin = normalize_linkedin(gs_contact.get("linkedin"))
        email = normalize_email(gs_contact.get("email"))
        
        sl_contact = None
        match_type = None
        
        # Try to match by LinkedIn first
        if linkedin and linkedin in linkedin_map:
            sl_contact = linkedin_map[linkedin]
            match_type = "linkedin"
            matched_by_linkedin += 1
        # Then try email
        elif email and email in email_map:
            sl_contact = email_map[email]
            match_type = "email"
            matched_by_email += 1
        else:
            unmatched += 1
        
        # Create merged contact
        if sl_contact:
            merged_contact = {
                "match_type": match_type,
                "sources": ["smartlead", "getsales"],
                "email": sl_contact.get("email") or gs_contact.get("email"),
                "first_name": sl_contact.get("first_name") or gs_contact.get("first_name"),
                "last_name": sl_contact.get("last_name") or gs_contact.get("last_name"),
                "company": sl_contact.get("company") or gs_contact.get("company"),
                "linkedin": sl_contact.get("linkedin") or gs_contact.get("linkedin"),
                "phone": sl_contact.get("phone") or gs_contact.get("phone"),
                "title": sl_contact.get("title") or gs_contact.get("title"),
                "location": sl_contact.get("location") or gs_contact.get("location"),
                "status": sl_contact.get("status") or gs_contact.get("status"),
                "replied": sl_contact.get("replied") or gs_contact.get("replied"),
                "smartlead_data": {
                    "campaign_id": sl_contact.get("campaign_id"),
                    "campaign_name": sl_contact.get("campaign_name"),
                    "opened": sl_contact.get("opened"),
                    "clicked": sl_contact.get("clicked"),
                    "created_at": sl_contact.get("created_at")
                },
                "getsales_data": {
                    "created_at": gs_contact.get("created_at")
                }
            }
        else:
            # GetSales only contact
            merged_contact = {
                "match_type": None,
                "sources": ["getsales"],
                "email": gs_contact.get("email"),
                "first_name": gs_contact.get("first_name"),
                "last_name": gs_contact.get("last_name"),
                "company": gs_contact.get("company"),
                "linkedin": gs_contact.get("linkedin"),
                "phone": gs_contact.get("phone"),
                "title": gs_contact.get("title"),
                "location": gs_contact.get("location"),
                "status": gs_contact.get("status"),
                "replied": gs_contact.get("replied"),
                "smartlead_data": None,
                "getsales_data": {
                    "created_at": gs_contact.get("created_at")
                }
            }
        
        merged.append(merged_contact)
    
    # Add Smartlead-only contacts
    smartlead_only = 0
    for sl_contact in smartlead_contacts:
        linkedin = normalize_linkedin(sl_contact.get("linkedin"))
        email = normalize_email(sl_contact.get("email"))
        
        # Check if already merged
        already_merged = False
        for merged_contact in merged:
            if merged_contact.get("match_type"):
                merged_linkedin = normalize_linkedin(merged_contact.get("linkedin"))
                merged_email = normalize_email(merged_contact.get("email"))
                
                if (linkedin and linkedin == merged_linkedin) or (email and email == merged_email):
                    already_merged = True
                    break
        
        if not already_merged:
            smartlead_only += 1
            merged.append({
                "match_type": None,
                "sources": ["smartlead"],
                "email": sl_contact.get("email"),
                "first_name": sl_contact.get("first_name"),
                "last_name": sl_contact.get("last_name"),
                "company": sl_contact.get("company"),
                "linkedin": sl_contact.get("linkedin"),
                "phone": sl_contact.get("phone"),
                "title": sl_contact.get("title"),
                "location": sl_contact.get("location"),
                "status": sl_contact.get("status"),
                "replied": sl_contact.get("replied"),
                "smartlead_data": {
                    "campaign_id": sl_contact.get("campaign_id"),
                    "campaign_name": sl_contact.get("campaign_name"),
                    "opened": sl_contact.get("opened"),
                    "clicked": sl_contact.get("clicked"),
                    "created_at": sl_contact.get("created_at")
                },
                "getsales_data": None
            })
    
    # Save merged contacts
    output_file = "merged_contacts.json"
    with open(output_file, "w") as f:
        json.dump(merged, f, indent=2, default=str)
    
    # Print results
    print("\n" + "=" * 60)
    print("MERGE RESULTS")
    print("=" * 60)
    print(f"Total merged contacts: {len(merged)}")
    print(f"\nMatching:")
    print(f"  Matched by LinkedIn: {matched_by_linkedin}")
    print(f"  Matched by Email: {matched_by_email}")
    print(f"  Total matched: {matched_by_linkedin + matched_by_email}")
    print(f"\nUnmatched:")
    print(f"  GetSales only: {unmatched}")
    print(f"  Smartlead only: {smartlead_only}")
    print(f"  Total unmatched: {unmatched + smartlead_only}")
    print(f"\nSaved to {output_file}")
    
    # Print match rate
    total_contacts = len(smartlead_contacts) + len(getsales_contacts)
    match_rate = ((matched_by_linkedin + matched_by_email) / total_contacts * 100) if total_contacts > 0 else 0
    print(f"\nMatch rate: {match_rate:.1f}%")


if __name__ == "__main__":
    merge_contacts()
