#!/usr/bin/env python3
"""
Export leads from SmartLead campaigns, score them, and produce analysis.
"""
import os
import csv
import io
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

# SmartLead uses sequence-level statuses, not email-level
# INPROGRESS = emails being sent, no reply yet
# COMPLETED = all steps sent, no reply
# We want leads who received emails but didn't reply
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
    """Score based on actual open_count from SmartLead."""
    if open_count >= 3:
        return 5
    elif open_count >= 1:
        return 3
    return 1  # no opens tracked


def tier(score_total):
    if score_total >= 15:
        return "A"
    elif score_total >= 8:
        return "B"
    return "C"


# --- LinkedIn extraction ---

def extract_linkedin(lead):
    """Try multiple fields to find LinkedIn URL."""
    for field in ['linkedin_profile', 'linkedin_url', 'linkedin']:
        val = lead.get(field, '')
        if val and 'linkedin' in str(val).lower():
            return str(val).strip()

    # Check custom_fields
    custom = lead.get('custom_fields', {})
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except (json.JSONDecodeError, TypeError):
            custom = {}

    if isinstance(custom, dict):
        for k, v in custom.items():
            if 'linkedin' in k.lower() and v and 'linkedin' in str(v).lower():
                return str(v).strip()
    elif isinstance(custom, list):
        for item in custom:
            if isinstance(item, dict):
                for k, v in item.items():
                    if 'linkedin' in k.lower() and v and 'linkedin' in str(v).lower():
                        return str(v).strip()

    return None


# --- Export ---

def export_csv(client, campaign_id):
    """Try CSV export endpoint first, fallback to paginated."""
    url = f"{BASE}/campaigns/{campaign_id}/leads-export"
    try:
        resp = client.get(url, params={"api_key": API_KEY}, timeout=60)
        if resp.status_code == 200 and resp.text.strip():
            reader = csv.DictReader(io.StringIO(resp.text))
            leads = list(reader)
            if leads:
                print(f"  CSV export: {len(leads)} leads", file=sys.stderr)
                return leads
    except Exception as e:
        print(f"  CSV export failed: {e}", file=sys.stderr)

    # Fallback: paginated API
    print(f"  Falling back to paginated API...", file=sys.stderr)
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
            print(f"  Paginated API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            break
        data = resp.json()
        if isinstance(data, list):
            batch = data
        elif isinstance(data, dict) and 'data' in data:
            batch = data['data']
        else:
            batch = []
        if not batch:
            break
        all_leads.extend(batch)
        offset += len(batch)
        if len(batch) < 100:
            break
    print(f"  Paginated: {len(all_leads)} leads", file=sys.stderr)
    return all_leads


def normalize_lead(lead):
    """Normalize field names from various API response formats."""
    normalized = {}
    for k, v in lead.items():
        normalized[k.lower().strip()] = v
    return normalized


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = httpx.Client()

    all_scored = []
    campaign_stats = {}

    for cid, cname in CAMPAIGNS:
        print(f"\n=== Campaign: {cname} (ID: {cid}) ===", file=sys.stderr)
        time.sleep(0.4)
        raw_leads = export_csv(client, cid)

        # Normalize and filter
        filtered = []
        for lead in raw_leads:
            lead = normalize_lead(lead)
            status = (lead.get('lead_status') or lead.get('status') or lead.get('email_status') or '').upper().strip()
            if status not in KEEP_STATUSES:
                continue
            linkedin = extract_linkedin(lead)
            if not linkedin:
                continue

            email = lead.get('email', '')
            first_name = lead.get('first_name', '')
            last_name = lead.get('last_name', '')
            full_name = lead.get('full_name', '') or f"{first_name} {last_name}".strip()
            title = lead.get('title', '') or lead.get('job_title', '') or lead.get('position', '') or ''
            company = lead.get('company_name', '') or lead.get('company', '') or ''
            location = lead.get('location', '') or lead.get('country', '') or lead.get('geo', '') or ''

            st = score_title(title)
            sg = score_geo(location)
            se = score_engagement(status)
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
        'email_status', 'score_title', 'score_geo', 'score_engagement',
        'score_total', 'priority_tier',
    ]
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_scored)
    print(f"\nCSV saved: {csv_path} ({len(all_scored)} leads)", file=sys.stderr)

    # --- Analysis ---
    analysis = []
    analysis.append("# Segment Analysis — SmartLead Campaign Export\n")
    analysis.append(f"**Date:** 2026-04-01\n")
    analysis.append(f"**Total leads with LinkedIn (filtered):** {len(all_scored)}\n\n")

    tier_total = Counter(l['priority_tier'] for l in all_scored)
    analysis.append(f"## Overall Tier Distribution\n")
    analysis.append(f"- **A (≥15):** {tier_total.get('A', 0)}")
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
        analysis.append(f"### Top 5 Titles")
        for t, c in title_counts.most_common(5):
            analysis.append(f"- {t}: {c}")

        # Top locations
        loc_counts = Counter(l['location'] for l in leads if l['location'])
        analysis.append(f"\n### Top 5 Locations")
        for loc, c in loc_counts.most_common(5):
            analysis.append(f"- {loc}: {c}")

        # Company size (if available)
        companies = Counter(l['company_name'] for l in leads if l['company_name'])
        analysis.append(f"\n### Top 5 Companies")
        for co, c in companies.most_common(5):
            analysis.append(f"- {co}: {c}")

    # Merge recommendation
    analysis.append(f"\n---\n## Recommendations: Merge or Separate Sequences?\n")

    # Check geo concentration per campaign
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

        analysis.append(f"\n### {cname}")
        if 'IMAGENCY' in cname:
            analysis.append(f"- **KEEP SEPARATE** — IMAGENCY segment (agency pain points differ from platform pain)")
            analysis.append(f"- Hook: agency margins, white-label influencer management, client retention")
        elif 'INDIA' in cname and 'MENA' not in cname:
            analysis.append(f"- Top geo: {top_loc} ({pct:.0f}%)")
            if pct >= 70:
                analysis.append(f"- **KEEP SEPARATE** — ≥70% single geo concentration")
            else:
                analysis.append(f"- Can merge with other INDIA campaigns")
            analysis.append(f"- Hook: Indian market growth, regional influencer discovery, cost efficiency")
        else:
            analysis.append(f"- Top geo: {top_loc} ({pct:.0f}%)")
            analysis.append(f"- **KEEP SEPARATE** — MENA/APAC mix requires region-aware messaging")
            analysis.append(f"- Hook: cross-border influencer campaigns, multi-market management")

    analysis.append(f"\n### Summary")
    analysis.append(f"1. **IMAGENCY_INDIA** — always separate (different ICP: agencies vs platforms)")
    analysis.append(f"2. **INFPLAT_INDIA + INDIA_GENERAL** — can merge IF >70% geo overlap AND similar title distribution")
    analysis.append(f"3. **INFPLAT_MENA_APAC** — separate (different geo, different compliance/market dynamics)")
    analysis.append(f"4. Recommended: **3-4 separate sequences** minimum")

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
