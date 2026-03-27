"""
Smartlead Lab — OnSocial Data Fetcher

Fetches all active OnSocial campaigns, their leads and sequences,
then organizes everything into CSV and MD files.

Usage:
    SMARTLEAD_API_KEY=your_key python fetch_data.py
    python fetch_data.py --api-key your_key
    python fetch_data.py --filter onsocial --status ACTIVE
"""

import os
import sys
import re
import csv
import time
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict

import httpx

BASE_URL = "https://server.smartlead.ai/api/v1"
OUT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────

def api_get(path: str, params: dict, api_key: str):
    p = {"api_key": api_key, **params}
    for attempt in range(5):
        resp = httpx.get(f"{BASE_URL}{path}", params=p, timeout=30)
        if resp.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"  [429 rate limit, waiting {wait}s]", end="", flush=True)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def fetch_all_campaigns(api_key: str, name_filter: str = None, status_filter: str = None) -> list[dict]:
    data = api_get("/campaigns", {}, api_key)
    campaigns = data if isinstance(data, list) else data.get("data", [])
    if name_filter:
        campaigns = [c for c in campaigns if name_filter.lower() in c.get("name", "").lower()]
    if status_filter:
        campaigns = [c for c in campaigns if c.get("status", "").upper() == status_filter.upper()]
    return campaigns


def fetch_all_leads(campaign_id: int, api_key: str) -> list[dict]:
    leads = []
    offset = 0
    limit = 100
    while True:
        data = api_get(f"/campaigns/{campaign_id}/leads", {"offset": offset, "limit": limit}, api_key)
        page = data if isinstance(data, list) else data.get("data", [])
        if not page:
            break
        leads.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return leads


def fetch_sequence(campaign_id: int, api_key: str) -> list[dict]:
    try:
        data = api_get(f"/campaigns/{campaign_id}/sequences", {}, api_key)
        seq = data if isinstance(data, list) else data.get("sequences", data.get("data", []))
        return seq if isinstance(seq, list) else []
    except Exception:
        return []


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.strip(". ")
    return name[:100] or "unnamed"


def sequence_fingerprint(seq: list[dict]) -> str:
    """Hash sequence content (subject + body) to detect duplicates."""
    parts = []
    for step in seq:
        subj = step.get("subject", "") or ""
        body = step.get("email_body", step.get("body", "")) or ""
        parts.append(f"{subj}|||{body}")
    raw = "\n---\n".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


LEAD_FIELDS = [
    "email", "first_name", "last_name", "company_name",
    "phone_number", "website", "linkedin_profile",
    "location", "title", "campaign_name", "campaign_id", "lead_status",
]


def flatten_lead(entry: dict, campaign_name: str, campaign_id: int) -> dict:
    lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
    return {
        "email":            lead.get("email", ""),
        "first_name":       lead.get("first_name", ""),
        "last_name":        lead.get("last_name", ""),
        "company_name":     lead.get("company_name", ""),
        "phone_number":     lead.get("phone_number", ""),
        "website":          lead.get("website", ""),
        "linkedin_profile": lead.get("linkedin_profile", ""),
        "location":         lead.get("location", ""),
        "title":            lead.get("custom_fields", {}).get("title", lead.get("title", "")) if isinstance(lead.get("custom_fields"), dict) else lead.get("title", ""),
        "campaign_name":    campaign_name,
        "campaign_id":      campaign_id,
        "lead_status":      entry.get("status", "N/A"),
    }


def write_csv(path: Path, rows: list[dict], fields: list[str] = None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ──────────────────────────────────────────────
# MD builders
# ──────────────────────────────────────────────

def company_md(company_name: str, leads: list[dict]) -> str:
    campaigns_seen = sorted(set(l["campaign_name"] for l in leads))
    statuses = defaultdict(int)
    for l in leads:
        statuses[l["lead_status"]] += 1

    lines = [
        f"# {company_name}",
        "",
        f"**Лидов:** {len(leads)}  ",
        f"**Кампаний:** {len(campaigns_seen)}",
        "",
        "## Кампании",
        "",
    ]
    for c in campaigns_seen:
        c_leads = [l for l in leads if l["campaign_name"] == c]
        lines.append(f"- **{c}** — {len(c_leads)} лид(ов)")
    lines += ["", "## Статусы лидов", ""]
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        lines.append(f"- `{status}` — {count}")
    lines += ["", "## Контакты", ""]
    lines.append("| Имя | Email | Должность | Кампания | Статус |")
    lines.append("|-----|-------|-----------|----------|--------|")
    for l in sorted(leads, key=lambda x: x["campaign_name"]):
        name = f"{l['first_name']} {l['last_name']}".strip() or "—"
        title = l.get("title", "") or "—"
        lines.append(f"| {name} | {l['email']} | {title} | {l['campaign_name']} | `{l['lead_status']}` |")
    lines.append("")
    return "\n".join(lines)


def sequences_md(seq_groups: dict) -> str:
    """
    seq_groups: fingerprint -> {campaigns: [...], steps: [...]}
    """
    lines = [
        "# Сиквенсы OnSocial — сгруппированные",
        "",
        f"Всего уникальных сиквенсов: **{len(seq_groups)}**",
        "",
    ]
    for fp, info in sorted(seq_groups.items(), key=lambda x: -len(x[1]["campaigns"])):
        camps = info["campaigns"]
        steps = info["steps"]
        lines += [
            f"---",
            f"## Сиквенс `{fp}`",
            f"**Используется в {len(camps)} кампании(ях):**",
        ]
        for c in camps:
            lines.append(f"- {c}")
        lines += ["", f"**Шагов:** {len(steps)}", ""]
        for i, step in enumerate(steps, 1):
            subj = step.get("subject", "") or "(без темы)"
            delay = step.get("seq_delay_details", {})
            delay_str = ""
            if isinstance(delay, dict):
                days = delay.get("delay_in_days", 0)
                delay_str = f" *(через {days} дн.)*" if days else ""
            lines.append(f"### Шаг {i}: {subj}{delay_str}")
            body = step.get("email_body", step.get("body", "")) or ""
            if body:
                lines.append("")
                lines.append("```")
                lines.append(body[:2000] + ("..." if len(body) > 2000 else ""))
                lines.append("```")
            lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("SMARTLEAD_API_KEY", ""))
    parser.add_argument("--filter", default="onsocial", help="Campaign name filter (default: onsocial)")
    parser.add_argument("--status", default="ACTIVE", help="Campaign status filter (default: ACTIVE)")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set SMARTLEAD_API_KEY env var or pass --api-key")
        sys.exit(1)

    api_key = args.api_key

    # ── 1. Campaigns ──────────────────────────
    print(f"Fetching campaigns (filter='{args.filter}', status='{args.status}')...")
    campaigns = fetch_all_campaigns(api_key, args.filter, args.status)
    print(f"Found {len(campaigns)} campaigns\n")

    if not campaigns:
        print("No campaigns found. Exiting.")
        sys.exit(0)

    all_leads: list[dict] = []
    # campaign_id -> list of flat leads
    campaign_leads: dict[int, list[dict]] = {}
    # fingerprint -> {campaigns, steps}
    seq_groups: dict[str, dict] = {}

    # ── 2. Per-campaign: leads + sequences ────
    for i, camp in enumerate(campaigns, 1):
        cid = camp["id"]
        cname = camp.get("name", f"campaign_{cid}")
        print(f"[{i}/{len(campaigns)}] {cname}", end="")

        # Leads
        try:
            raw_leads = fetch_all_leads(cid, api_key)
        except Exception as e:
            print(f"  ERROR leads: {e}")
            raw_leads = []

        flat = [flatten_lead(e, cname, cid) for e in raw_leads]
        campaign_leads[cid] = flat
        all_leads.extend(flat)
        print(f"  →  {len(flat)} leads", end="")

        # Sequence
        seq = fetch_sequence(cid, api_key)
        if seq:
            fp = sequence_fingerprint(seq)
            if fp not in seq_groups:
                seq_groups[fp] = {"campaigns": [], "steps": seq}
            seq_groups[fp]["campaigns"].append(cname)
            print(f"  |  {len(seq)} seq steps (fp={fp})", end="")

        print()

    print(f"\nTotal leads collected: {len(all_leads)}")

    # ── 3. all_leads.csv ──────────────────────
    print("\nWriting all_leads.csv...")
    write_csv(OUT_DIR / "all_leads.csv", all_leads, LEAD_FIELDS)

    # ── 4. Per-campaign CSVs ──────────────────
    print("Writing campaign CSVs...")
    for camp in campaigns:
        cid = camp["id"]
        cname = camp.get("name", f"campaign_{cid}")
        leads = campaign_leads.get(cid, [])
        if leads:
            path = OUT_DIR / "campaigns" / f"{safe_filename(cname)}.csv"
            write_csv(path, leads, LEAD_FIELDS)

    # ── 5. Group leads by company ─────────────
    company_map: dict[str, list[dict]] = defaultdict(list)
    for lead in all_leads:
        company = (lead.get("company_name") or "").strip()
        key = company.lower() if company else "__no_company__"
        company_map[key].append(lead)

    print(f"Companies found: {len(company_map)}")

    # ── 6. Per-company MD + CSV ───────────────
    print("Writing company files...")
    for company_key, leads in company_map.items():
        display = leads[0].get("company_name", "").strip() or company_key
        fname = safe_filename(display)

        # CSV
        write_csv(
            OUT_DIR / "companies" / f"{fname}.csv",
            leads, LEAD_FIELDS
        )

        # MD
        md = company_md(display, leads)
        (OUT_DIR / "companies" / f"{fname}.md").write_text(md, encoding="utf-8")

    # ── 7. sequences_grouped.md ───────────────
    print("Writing sequences_grouped.md...")
    seq_md = sequences_md(seq_groups)
    (OUT_DIR / "sequences" / "sequences_grouped.md").write_text(seq_md, encoding="utf-8")

    # ── Summary ───────────────────────────────
    dup_seqs = {fp: info for fp, info in seq_groups.items() if len(info["campaigns"]) > 1}
    print(f"\n{'='*55}")
    print(f"DONE")
    print(f"{'='*55}")
    print(f"  Campaigns:          {len(campaigns)}")
    print(f"  Total leads:        {len(all_leads)}")
    print(f"  Companies:          {len(company_map)}")
    print(f"  Unique sequences:   {len(seq_groups)}")
    print(f"  Duplicate seqs:     {len(dup_seqs)} (used in 2+ campaigns)")
    print(f"\nOutput: {OUT_DIR}")


if __name__ == "__main__":
    main()
