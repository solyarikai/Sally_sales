#!/usr/bin/env python3
"""
Export leads from SmartLead campaigns, score them, and produce analysis.
Uses paginated API to get full custom_fields (title, segment, etc.).
"""
import os
import csv
import json
import re
import time
import sys
from collections import Counter

import httpx

API_KEY = os.environ["SMARTLEAD_API_KEY"]
BASE = "https://server.smartlead.ai/api/v1"

CAMPAIGNS = [
    (3065429, "INFPLAT_MENA_APAC"),
    (3059650, "INFPLAT_INDIA"),
    (3063527, "IMAGENCY_INDIA"),
    (3064966, "INDIA_GENERAL"),
]

# SmartLead sequence-level statuses: INPROGRESS/COMPLETED = sent, no reply
KEEP_STATUSES = {"INPROGRESS", "COMPLETED"}

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/smartlead_export")

# --- Scoring ---

TITLE_PATTERNS = [
    (r'\b(founder|co-founder|ceo|chief executive)\b', 10),
    (r'\b(managing director|md(?!\w)|president)\b', 9),
    (r'\b(vp|vice president|head of|chief)\b', 8),
    (r'\b(director|gm|general manager)\b', 6),
    (r'\b(manager|lead|principal)\b', 4),
]

GEO_TIER1 = {
    'india': 5, 'uae': 5, 'dubai': 5, 'united arab emirates': 5,
    'singapore': 5, 'united states': 4, 'usa': 4, 'us': 4,
    'united kingdom': 4, 'uk': 4,
}
GEO_TIER2 = {
    'australia': 3, 'indonesia': 3, 'malaysia': 3, 'philippines': 3,
    'saudi arabia': 3, 'qatar': 3, 'thailand': 3, 'vietnam': 3,
    'hong kong': 3, 'japan': 3, 'south korea': 3,
}


def score_title(title):
    if not title:
        return 2
    t = title.lower()
    for pattern, score in TITLE_PATTERNS:
        if re.search(pattern, t):
            return score
    return 2


def score_geo(location):
    if not location:
        return 1
    loc = location.lower().strip()
    for key, score in GEO_TIER1.items():
        if key in loc:
            return score
    for key, score in GEO_TIER2.items():
        if key in loc:
            return score
    return 1


def score_engagement(open_count):
    if open_count >= 3:
        return 5
    elif open_count >= 1:
        return 3
    return 1


def tier(score_total):
    if score_total >= 15:
        return "A"
    elif score_total >= 8:
        return "B"
    return "C"


# --- LinkedIn extraction ---

def extract_linkedin(lead_data):
    """Extract LinkedIn URL from lead fields or custom_fields."""
    val = lead_data.get('linkedin_profile', '')
    if val and 'linkedin' in str(val).lower():
        return str(val).strip()

    cf = lead_data.get('custom_fields', {})
    if isinstance(cf, str):
        try:
            cf = json.loads(cf)
        except (json.JSONDecodeError, TypeError):
            cf = {}
    if isinstance(cf, dict):
        for k, v in cf.items():
            if 'linkedin' in k.lower() and v and 'linkedin' in str(v).lower():
                return str(v).strip()
    return None


def extract_title(lead_data):
    """Extract job title from custom_fields or direct fields."""
    cf = lead_data.get('custom_fields', {})
    if isinstance(cf, str):
        try:
            cf = json.loads(cf)
        except (json.JSONDecodeError, TypeError):
            cf = {}
    if isinstance(cf, dict):
        # Try title, job_title from custom_fields
        for key in ('title', 'job_title', 'position'):
            val = cf.get(key, '')
            if val and str(val).strip():
                return str(val).strip()
    return ''


# --- Export via paginated API ---

def fetch_leads_paginated(client, campaign_id):
    """Fetch all leads via paginated API (has custom_fields)."""
    all_leads = []
    offset = 0
    while True:
        time.sleep(0.4)
        resp = client.get(
            f"{BASE}/campaigns/{campaign_id}/leads",
            params={"api_key": API_KEY, "limit": 100, "offset": offset},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"  API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            break
        data = resp.json()
        if isinstance(data, dict):
            batch = data.get('data', [])
            total = int(data.get('total_leads', 0))
        elif isinstance(data, list):
            batch = data
            total = len(data)
        else:
            break
        if not batch:
            break
        all_leads.extend(batch)
        offset += len(batch)
        print(f"  Fetched {offset}/{total}...", file=sys.stderr)
        if len(batch) < 100:
            break
    return all_leads


def get_open_counts(client, campaign_id):
    """Get open counts from CSV export (has open_count field)."""
    try:
        import csv, io
        resp = client.get(
            f"{BASE}/campaigns/{campaign_id}/leads-export",
            params={"api_key": API_KEY},
            timeout=60,
        )
        if resp.status_code == 200:
            reader = csv.DictReader(io.StringIO(resp.text))
            return {row['email']: int(row.get('open_count', 0) or 0) for row in reader}
    except Exception as e:
        print(f"  Open counts fetch failed: {e}", file=sys.stderr)
    return {}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = httpx.Client()

    all_scored = []
    campaign_stats = {}

    for cid, cname in CAMPAIGNS:
        print(f"\n=== Campaign: {cname} (ID: {cid}) ===", file=sys.stderr)

        # Fetch open counts from CSV export
        time.sleep(0.4)
        open_counts = get_open_counts(client, cid)

        # Fetch full lead data via paginated API
        raw_leads = fetch_leads_paginated(client, cid)
        print(f"  Total leads: {len(raw_leads)}", file=sys.stderr)

        # Normalize and filter
        filtered = []
        for entry in raw_leads:
            status = (entry.get('status', '') or '').upper().strip()
            if status not in KEEP_STATUSES:
                continue

            # Lead data is nested under 'lead' key in paginated API
            lead = entry.get('lead', entry)

            linkedin = extract_linkedin(lead)
            if not linkedin:
                continue

            email = lead.get('email', '')
            first_name = lead.get('first_name', '')
            last_name = lead.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()
            title = extract_title(lead)
            company = lead.get('company_name', '') or ''
            location = lead.get('location', '') or ''

            # Get open count for this email
            oc = open_counts.get(email, 0)

            st = score_title(title)
            sg = score_geo(location)
            se = score_engagement(oc)
            total = st + sg + se

            filtered.append({
                'campaign_id': cid,
                'campaign_name': cname,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'title': title,
                'company_name': company,
                'location': location,
                'linkedin_url': linkedin,
                'email_status': status,
                'open_count': oc,
                'score_title': st,
                'score_geo': sg,
                'score_engagement': se,
                'score_total': total,
                'priority_tier': tier(total),
            })

        campaign_stats[cname] = {
            'total_raw': len(raw_leads),
            'filtered': len(filtered),
            'leads': filtered,
        }
        all_scored.extend(filtered)
        print(f"  Filtered (status + LinkedIn): {len(filtered)}/{len(raw_leads)}", file=sys.stderr)

    # Sort by score
    all_scored.sort(key=lambda x: -x['score_total'])

    # Write CSV
    csv_path = os.path.join(OUTPUT_DIR, "ALL_CAMPAIGNS_scored.csv")
    fieldnames = [
        'campaign_id', 'campaign_name', 'email', 'first_name', 'last_name',
        'full_name', 'title', 'company_name', 'location', 'linkedin_url',
        'email_status', 'open_count', 'score_title', 'score_geo', 'score_engagement',
        'score_total', 'priority_tier',
    ]
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_scored)
    print(f"\nCSV saved: {csv_path} ({len(all_scored)} leads)", file=sys.stderr)

    # --- Analysis ---
    analysis = []
    analysis.append("# Segment Analysis - SmartLead Campaign Export\n")
    analysis.append(f"**Date:** 2026-04-01\n")
    analysis.append(f"**Total leads with LinkedIn (filtered):** {len(all_scored)}\n\n")

    tier_total = Counter(l['priority_tier'] for l in all_scored)
    analysis.append(f"## Overall Tier Distribution\n")
    analysis.append(f"- **A (>=15):** {tier_total.get('A', 0)}")
    analysis.append(f"- **B (8-14):** {tier_total.get('B', 0)}")
    analysis.append(f"- **C (<8):** {tier_total.get('C', 0)}\n")

    for cname, stats in campaign_stats.items():
        leads = stats['leads']
        analysis.append(f"\n---\n## {cname}\n")
        analysis.append(f"- Raw leads: {stats['total_raw']}")
        analysis.append(f"- With LinkedIn + correct status: {stats['filtered']}\n")

        if not leads:
            analysis.append("*No leads after filtering.*\n")
            continue

        # Tier distribution
        tiers = Counter(l['priority_tier'] for l in leads)
        analysis.append(f"### Tier Distribution")
        analysis.append(f"- A: {tiers.get('A', 0)} ({tiers.get('A', 0)/len(leads)*100:.0f}%)")
        analysis.append(f"- B: {tiers.get('B', 0)} ({tiers.get('B', 0)/len(leads)*100:.0f}%)")
        analysis.append(f"- C: {tiers.get('C', 0)} ({tiers.get('C', 0)/len(leads)*100:.0f}%)\n")

        # Top titles
        title_counts = Counter(l['title'] for l in leads if l['title'])
        if title_counts:
            analysis.append(f"### Top 5 Titles")
            for t, c in title_counts.most_common(5):
                analysis.append(f"- {t}: {c}")
        else:
            analysis.append(f"### Titles")
            analysis.append(f"- *No title data available (not imported to SmartLead)*")

        # Top locations
        loc_counts = Counter(l['location'] for l in leads if l['location'])
        analysis.append(f"\n### Top 5 Locations")
        for loc, c in loc_counts.most_common(5):
            analysis.append(f"- {loc}: {c}")

        # Top companies
        companies = Counter(l['company_name'] for l in leads if l['company_name'])
        analysis.append(f"\n### Top 5 Companies")
        for co, c in companies.most_common(5):
            analysis.append(f"- {co}: {c}")

        # Engagement
        opens = sum(1 for l in leads if l['open_count'] > 0)
        analysis.append(f"\n### Engagement")
        analysis.append(f"- Leads with opens: {opens}/{len(leads)} ({opens/len(leads)*100:.0f}%)")

    # Merge recommendation
    analysis.append(f"\n---\n## Recommendations: Merge or Separate Sequences?\n")

    for cname, stats in campaign_stats.items():
        leads = stats['leads']
        if not leads:
            continue
        loc_counts = Counter(l['location'] for l in leads if l['location'])
        total_with_loc = sum(loc_counts.values())
        if total_with_loc > 0:
            top_loc, top_count = loc_counts.most_common(1)[0]
            pct = top_count / total_with_loc * 100
        else:
            top_loc, pct = "unknown", 0

        # Check India concentration
        india_count = sum(c for loc, c in loc_counts.items() if 'india' in loc.lower())
        india_pct = india_count / total_with_loc * 100 if total_with_loc else 0

        analysis.append(f"\n### {cname}")
        analysis.append(f"- Leads: {len(leads)}")
        analysis.append(f"- Top geo: {top_loc} ({pct:.0f}%)")
        if india_pct > 0:
            analysis.append(f"- India concentration: {india_pct:.0f}%")

        if 'IMAGENCY' in cname:
            analysis.append(f"- **KEEP SEPARATE** - IMAGENCY segment (agency pain points differ from platform pain)")
            analysis.append(f"- Hook: agency margins, white-label influencer management, client retention")
            analysis.append(f"- Pain: managing multiple brand campaigns, ROI reporting, influencer vetting at scale")
        elif 'MENA_APAC' in cname:
            analysis.append(f"- **KEEP SEPARATE** - MENA/APAC is multi-market, needs region-aware messaging")
            analysis.append(f"- Hook: cross-border influencer campaigns, multi-market compliance")
            analysis.append(f"- Pain: fragmented influencer ecosystem across regions, local platform gaps")
        elif 'GENERAL' in cname:
            if india_pct >= 70:
                analysis.append(f"- **CAN MERGE with INFPLAT_INDIA** - >=70% India concentration")
            else:
                analysis.append(f"- **KEEP SEPARATE** - mixed geo, different messaging needed")
            analysis.append(f"- Hook: general influencer marketing growth, platform consolidation")
            analysis.append(f"- Pain: scattered tools, lack of analytics, manual workflows")
        else:
            if india_pct >= 70:
                analysis.append(f"- India >=70% - consider merging with INDIA_GENERAL if title distribution matches")
            else:
                analysis.append(f"- **KEEP SEPARATE** - geo mix requires tailored messaging")
            analysis.append(f"- Hook: Indian creator economy boom, influencer discovery, regional languages")
            analysis.append(f"- Pain: no unified platform for Indian influencer market, manual outreach")

    # Check if INFPLAT_INDIA and INDIA_GENERAL can merge
    india_leads = campaign_stats.get('INFPLAT_INDIA', {}).get('leads', [])
    general_leads = campaign_stats.get('INDIA_GENERAL', {}).get('leads', [])

    if india_leads and general_leads:
        india_titles = Counter(l['title'] for l in india_leads if l['title'])
        general_titles = Counter(l['title'] for l in general_leads if l['title'])

        analysis.append(f"\n### INFPLAT_INDIA + INDIA_GENERAL Merge Analysis")
        india_locs = Counter(l['location'] for l in india_leads if l['location'])
        general_locs = Counter(l['location'] for l in general_leads if l['location'])
        india_geo_overlap = set(india_locs.keys()) & set(general_locs.keys())
        analysis.append(f"- Geo overlap: {len(india_geo_overlap)} shared locations")
        if india_titles and general_titles:
            title_overlap = set(india_titles.keys()) & set(general_titles.keys())
            analysis.append(f"- Title overlap: {len(title_overlap)} shared titles")
        analysis.append(f"- Recommendation: Merge ONLY if both are platform-focused ICP")

    analysis.append(f"\n### Final Recommendation")
    analysis.append(f"1. **IMAGENCY_INDIA** - always separate (different ICP: agencies vs platforms)")
    analysis.append(f"2. **INFPLAT_INDIA + INDIA_GENERAL** - can merge if ICP aligns (both platform users)")
    analysis.append(f"3. **INFPLAT_MENA_APAC** - separate (different geo, different compliance/market)")
    analysis.append(f"4. Recommended: **3 separate sequences** minimum:")
    analysis.append(f"   - Sequence A: IMAGENCY_INDIA (agency-focused messaging)")
    analysis.append(f"   - Sequence B: INFPLAT_INDIA + INDIA_GENERAL (India platform users)")
    analysis.append(f"   - Sequence C: INFPLAT_MENA_APAC (multi-market platform users)")

    md_path = os.path.join(OUTPUT_DIR, "SEGMENT_ANALYSIS.md")
    with open(md_path, 'w') as f:
        f.write('\n'.join(analysis))
    print(f"Analysis saved: {md_path}", file=sys.stderr)

    # Print summary to stdout
    print("\n=== SUMMARY ===")
    for cname, stats in campaign_stats.items():
        print(f"{cname}: {stats['filtered']}/{stats['total_raw']} leads (with LinkedIn + status filter)")
    print(f"\nTotal: {len(all_scored)} scored leads")
    print(f"Tier A: {tier_total.get('A', 0)}, B: {tier_total.get('B', 0)}, C: {tier_total.get('C', 0)}")


if __name__ == "__main__":
    main()
