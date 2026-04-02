#!/usr/bin/env python3
"""
SmartLead A/B Test Analysis v2 — IM-FIRST AGENCIES
====================================================

Анализирует реальные A/B варианты из статистики SmartLead.
Парсит email subjects и calculates metrics per variant.

✅ Запускать НА HETZNER: ssh hetzner "python3 sofia/scripts/smartlead_ab_analysis_v2.py"
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")

CAMPAIGNS = {
    "c-OnSocial_IM-FIRST AGENCIES #C": 3050462,
    "c-OnSocial_IM-FIRST AGENCIES INDIA #C": 3063527,
    "c-OnSocial_IM-FIRST AGENCIES EUROPE #C": 3064335,
    "c-OnSocial_IM-FIRST AGENCIES US_CANADA_LATAM #C": 3071851,
}


def api_get(path: str, params: Dict = None) -> Dict:
    """SmartLead API request."""
    if not API_KEY:
        raise ValueError("❌ SMARTLEAD_API_KEY not set")

    query = params or {}
    query["api_key"] = API_KEY

    try:
        resp = httpx.get(f"{BASE_URL}{path}", params=query, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        print(f"❌ API Error: {e}")
        return {}


def get_campaign_statistics(campaign_id: int) -> Dict:
    """Get full statistics for a campaign."""
    return api_get(f"/campaigns/{campaign_id}/statistics")


def extract_variant_from_subject(subject: str) -> str:
    """
    Extract A/B variant identifier from email subject.

    Examples:
    - "Paolo, 450M influencer profiles ready for your API" → INTRO
    - "question about your client reports" → SOFTENING
    - "Last chance to verify your creator accounts" → FINAL
    """

    # Map keywords in subjects to variant types
    if not subject:
        return "UNKNOWN"

    subject_lower = subject.lower()

    # Step 1 variants (Intro)
    if "450m influencer profiles" in subject_lower or "450m creator" in subject_lower:
        if "ready for your api" in subject_lower:
            return "INTRO_A_450M_API"
        elif "are ready" in subject_lower:
            return "INTRO_A_READY"
        return "INTRO_450M"

    if "verify creator" in subject_lower or "verification" in subject_lower:
        return "INTRO_VERIFY"

    # Step 2-3 variants (Softening/Follow-up)
    if "question" in subject_lower or "quick question" in subject_lower:
        return "SOFTENING_QUESTION"

    if "client reports" in subject_lower or "reports" in subject_lower:
        return "SOFTENING_REPORTS"

    # Step 4+ variants (CTA variations)
    if "last chance" in subject_lower or "last touch" in subject_lower:
        return "FINAL_CTA"

    if "demo" in subject_lower or "walkthrough" in subject_lower:
        return "CTA_DEMO"

    if "thread" in subject_lower or subject.strip() == "(thread)":
        return "FOLLOWUP_THREAD"

    # Fallback
    return "OTHER"


def analyze_campaign(campaign_id: int, campaign_name: str) -> Dict:
    """Analyze one campaign's A/B performance."""

    print(f"\n{'='*80}")
    print(f"📊 {campaign_name}")
    print(f"{'='*80}")

    stats = get_campaign_statistics(campaign_id)

    if not stats or "data" not in stats:
        print(f"❌ No statistics data for campaign {campaign_id}")
        return {}

    email_stats = stats.get("data", [])
    total_leads = len(email_stats)

    print(f"📈 Total leads with stats: {total_leads}")

    # Group by variant
    variants = defaultdict(lambda: {
        "sent": 0,
        "opened": 0,
        "clicked": 0,
        "replied": 0,
        "bounced": 0,
        "unsubscribed": 0,
        "leads": []
    })

    for entry in email_stats:
        variant = extract_variant_from_subject(entry.get("email_subject", ""))

        variants[variant]["sent"] += 1
        if entry.get("open_time"):
            variants[variant]["opened"] += 1
        if entry.get("click_time"):
            variants[variant]["clicked"] += 1
        if entry.get("reply_time"):
            variants[variant]["replied"] += 1
        if entry.get("is_bounced"):
            variants[variant]["bounced"] += 1
        if entry.get("is_unsubscribed"):
            variants[variant]["unsubscribed"] += 1

        variants[variant]["leads"].append({
            "email": entry.get("lead_email"),
            "name": entry.get("lead_name"),
            "subject": entry.get("email_subject"),
            "sent": entry.get("sent_time"),
            "reply": entry.get("reply_time"),
        })

    # Calculate metrics per variant
    results = []
    for variant_name, data in sorted(variants.items()):
        sent = data["sent"]
        replied = data["replied"]
        opened = data["opened"]
        clicked = data["clicked"]

        open_rate = round((opened / sent * 100) if sent > 0 else 0, 2)
        click_rate = round((clicked / sent * 100) if sent > 0 else 0, 2)
        reply_rate = round((replied / sent * 100) if sent > 0 else 0, 2)

        results.append({
            "variant": variant_name,
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
            "bounced": data["bounced"],
            "unsubscribed": data["unsubscribed"],
            "open_rate": open_rate,
            "click_rate": click_rate,
            "reply_rate": reply_rate,
        })

        print(f"\n  🎯 {variant_name}")
        print(f"     Sent: {sent}")
        print(f"     Opens: {opened} ({open_rate}%)")
        print(f"     Clicks: {clicked} ({click_rate}%)")
        print(f"     Replies: {replied} ({reply_rate}%) ← KEY METRIC")

    # Find best performer
    if results:
        best = max(results, key=lambda x: x["reply_rate"])
        print(f"\n  🏆 BEST: {best['variant']} ({best['reply_rate']}% reply rate)")

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "total_leads": total_leads,
        "variants": results,
        "variant_data": variants,
    }


def print_comparison(all_campaigns: List[Dict]) -> None:
    """Compare all campaigns side-by-side."""

    print(f"\n\n{'='*80}")
    print(f"📊 A/B COMPARISON ACROSS ALL CAMPAIGNS")
    print(f"{'='*80}\n")

    # Summary table
    print("Campaign Summary:")
    print("| Campaign | Total | Opened | Clicked | Replied | Best Variant |")
    print("|----------|-------|--------|---------|---------|---|")

    for campaign in all_campaigns:
        name = campaign["campaign_name"][:30]
        total = campaign["total_leads"]

        all_opened = sum(v.get("opened", 0) for v in campaign.get("variant_data", {}).values())
        all_clicked = sum(v.get("clicked", 0) for v in campaign.get("variant_data", {}).values())
        all_replied = sum(v.get("replied", 0) for v in campaign.get("variant_data", {}).values())

        best_variant = max(campaign["variants"], key=lambda x: x["reply_rate"]) if campaign["variants"] else None
        best_name = best_variant["variant"][:20] if best_variant else "N/A"

        print(f"| {name:30} | {total:5} | {all_opened:6} | {all_clicked:7} | {all_replied:7} | {best_name:20} |")

    # Variant performance across campaigns
    print(f"\n\nVariant Performance (Reply Rate %):")
    print("| Variant | Campaign 1 | Campaign 2 | Campaign 3 | Campaign 4 | AVG |")
    print("|---------|-----------|-----------|-----------|-----------|-----|")

    # Collect all unique variants
    all_variants = set()
    for campaign in all_campaigns:
        for variant in campaign["variants"]:
            all_variants.add(variant["variant"])

    for variant in sorted(all_variants):
        rows = [variant[:25]]
        values = []

        for campaign in all_campaigns:
            v_data = next((v for v in campaign["variants"] if v["variant"] == variant), None)
            if v_data:
                rows.append(f"{v_data['reply_rate']:.1f}%")
                values.append(v_data['reply_rate'])
            else:
                rows.append("—")

        avg = round(sum(values) / len(values), 2) if values else 0
        rows.append(f"{avg:.1f}%")

        print(f"| {rows[0]:25} | {rows[1]:9} | {rows[2]:9} | {rows[3]:9} | {rows[4]:9} | {rows[5]:5} |")


def main():
    print(f"\n🚀 SmartLead A/B Analysis v2 — IM-FIRST AGENCIES\n")

    if not API_KEY:
        print(f"❌ SMARTLEAD_API_KEY not set")
        return

    all_campaigns = []

    for campaign_name, campaign_id in CAMPAIGNS.items():
        try:
            result = analyze_campaign(campaign_id, campaign_name)
            if result:
                all_campaigns.append(result)
        except Exception as e:
            print(f"❌ Error: {e}")

    if all_campaigns:
        print_comparison(all_campaigns)
        export_json(all_campaigns)

    print(f"\n{'='*80}\n")


def export_json(campaigns: List[Dict]) -> None:
    """Export results to JSON."""
    output_dir = Path("sofia/projects/OnSocial/hub")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "im_agencies_ab_analysis_v2.json"

    export_data = {
        "campaigns": campaigns,
        "summary": {
            "total_campaigns": len(campaigns),
            "total_leads": sum(c["total_leads"] for c in campaigns),
        }
    }

    output_file.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
    print(f"✅ Results saved: {output_file}")


if __name__ == "__main__":
    main()
