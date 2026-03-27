"""
Паузит дублирующихся лидов в НОВОЙ кампании, оставляя их в СТАРОЙ.
"Старая" = кампания с меньшим ID (раньше создана).

Usage:
    SMARTLEAD_API_KEY=your_key python pause_duplicates_in_newer.py --filter onsocial --status ACTIVE

    # Dry run (только показать что будет сделано, без изменений):
    SMARTLEAD_API_KEY=your_key python pause_duplicates_in_newer.py --filter onsocial --status ACTIVE --dry-run
"""

import os
import sys
import argparse
import httpx
from collections import defaultdict

BASE_URL = "https://server.smartlead.ai/api/v1"


def api_get(path: str, params: dict, api_key: str) -> dict | list:
    p = {"api_key": api_key, **params}
    resp = httpx.get(f"{BASE_URL}{path}", params=p, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict, api_key: str) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", params={"api_key": api_key}, json=body, timeout=30)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("SMARTLEAD_API_KEY", ""))
    parser.add_argument("--filter", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Показать что будет сделано без изменений")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set SMARTLEAD_API_KEY env var or pass --api-key")
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"Режим: {mode}\n")

    print("Fetching campaigns...")
    campaigns = fetch_all_campaigns(args.api_key, args.filter, args.status)
    print(f"Найдено {len(campaigns)} кампаний\n")

    # email -> list of {campaign_id, campaign_name, lead_id, email_lead_map_id, status}
    email_map: dict[str, list[dict]] = defaultdict(list)

    for i, camp in enumerate(campaigns, 1):
        cid = camp["id"]
        cname = camp.get("name", f"campaign_{cid}")
        print(f"[{i}/{len(campaigns)}] {cname} (id={cid})...", end=" ", flush=True)

        try:
            leads = fetch_all_leads(cid, args.api_key)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        print(f"{len(leads)} leads")

        for entry in leads:
            lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
            email = lead.get("email", "").lower().strip()
            if not email:
                continue
            email_map[email].append({
                "campaign_id": cid,
                "campaign_name": cname,
                "lead_id": lead.get("id"),
                "email_lead_map_id": entry.get("campaign_lead_map_id"),
                "status": entry.get("status", "N/A"),
            })

    # Найти дубли
    duplicates = {email: entries for email, entries in email_map.items() if len(entries) > 1}

    print(f"\n{'='*60}")
    print(f"Дублей найдено: {len(duplicates)}")
    print(f"{'='*60}\n")

    paused_count = 0
    skipped_count = 0
    error_count = 0

    for email, entries in sorted(duplicates.items()):
        # Сортируем по campaign_id: меньший ID = старая кампания = оставляем
        entries_sorted = sorted(entries, key=lambda x: x["campaign_id"])
        old = entries_sorted[0]
        newer_entries = entries_sorted[1:]

        print(f"EMAIL: {email}")
        print(f"  ОСТАВИТЬ  [{old['status']}] {old['campaign_name']} (id={old['campaign_id']})")

        for new in newer_entries:
            elmap_id = new.get("email_lead_map_id")
            lead_id = new.get("lead_id")

            if new["status"] == "PAUSED":
                print(f"  ПРОПУСК   [{new['status']}] {new['campaign_name']} — уже на паузе")
                skipped_count += 1
                continue

            print(f"  ПАУЗИМ    [{new['status']}] {new['campaign_name']} (id={new['campaign_id']}, map_id={elmap_id})")

            if args.dry_run:
                paused_count += 1
                continue

            # Паузим лид в новой кампании
            try:
                result = api_post(
                    f"/campaigns/{new['campaign_id']}/leads/{lead_id}/pause",
                    {},
                    args.api_key,
                )
                print(f"           ✓ ok: {result.get('ok')}")
                paused_count += 1
            except Exception as e:
                print(f"           ✗ ERROR: {e}")
                error_count += 1

        print()

    print(f"{'='*60}")
    print(f"ИТОГ ({mode}):")
    print(f"  Запаузено:  {paused_count}")
    print(f"  Пропущено:  {skipped_count} (уже на паузе)")
    print(f"  Ошибок:     {error_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
