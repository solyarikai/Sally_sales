"""
GetSales — заполнить поле `linkedin` (nickname) для контактов, у которых оно пустое.

Логика:
  1. Загрузить все CSV из sofia/get_sales_hub/ → dict {email: linkedin_url}
  2. Для каждого GetSales списка → получить все контакты (пагинация)
  3. Для контактов без `linkedin`:
     - Матч по work_email → linkedin_url из CSV
     - Извлечь slug: linkedin.com/in/john-doe → john-doe
     - Обновить через PUT /leads/api/leads/{uuid}
  4. Итоговый отчёт

Запуск локально:
    cd ~/sales_engineer
    python3.11 sofia/scripts/getsales_fix_linkedin_id.py
"""

import csv
import glob
import re
import time
import httpx
from pathlib import Path
from urllib.parse import unquote

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

BASE_URL = "https://amazing.getsales.io"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
DELAY = 0.2
DRY_RUN = False

# Если задать — обрабатываем только эти списки (по подстроке в имени, case-insensitive).
# Пустой список = обрабатываем все.
ONLY_LISTS: list[str] = ["OS |", "OnSocial"]

# Папка с CSV источниками (относительно рабочей директории)
HUB_DIR = Path("sofia/get_sales_hub")


# ── Утилиты ────────────────────────────────────────────────────────────────────

def extract_slug(url: str) -> str | None:
    """linkedin.com/in/john-doe-123 → john-doe-123"""
    if not url:
        return None
    url = url.strip().rstrip("/")
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.IGNORECASE)
    if m:
        slug = unquote(m.group(1)).strip()
        return slug if slug else None
    return None


def build_mappings() -> tuple[dict[str, str], dict[str, str]]:
    """Читает все CSV в get_sales_hub.
    Возвращает:
      email_map  — {email.lower(): linkedin_slug}
      name_map   — {full_name.lower(): linkedin_slug}  (для контактов без email)
    """
    email_map: dict[str, str] = {}
    name_map: dict[str, str] = {}

    for csv_path in HUB_DIR.rglob("*.csv"):
        try:
            with open(csv_path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            continue

        if not rows:
            continue

        cols = list(rows[0].keys())

        email_col = next(
            (c for c in cols if c.lower() in ("work_email", "email", "work email")), None
        )
        name_col = next(
            (c for c in cols if c.lower() in ("full_name", "name")), None
        )
        url_col = next(
            (c for c in cols if c.lower() in ("linkedin_url", "linkedin url")), None
        )
        nick_col = next(
            (c for c in cols if c.lower() in ("linkedin_nickname", "linkedin nickname")), None
        )

        for row in rows:
            # Получаем slug
            slug = None
            if nick_col:
                slug = row.get(nick_col, "").strip() or None
            if not slug and url_col:
                slug = extract_slug(row.get(url_col, ""))
            if not slug:
                continue

            # Матч по email
            if email_col:
                email = row.get(email_col, "").strip().lower()
                if email and email not in email_map:
                    email_map[email] = slug

            # Матч по имени (fallback)
            if name_col:
                name = row.get(name_col, "").strip().lower()
                if name and name not in name_map:
                    name_map[name] = slug

    return email_map, name_map


# ── GetSales API ────────────────────────────────────────────────────────────────

def get_all_lists(client: httpx.Client) -> list:
    resp = client.get(f"{BASE_URL}/leads/api/lists", headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_contacts_from_list(client: httpx.Client, list_uuid: str) -> list:
    contacts = []
    offset = 0
    page_size = 100

    while True:
        resp = client.post(
            f"{BASE_URL}/leads/api/leads/search",
            headers=HEADERS,
            json={"filter": {"list_uuid": list_uuid}, "limit": page_size, "offset": offset},
        )
        if resp.status_code != 200:
            print(f"    ⚠️  {resp.status_code}: {resp.text[:150]}")
            break

        data = resp.json()
        batch = data.get("data", [])
        total = data.get("total", 0)

        if not batch:
            break

        contacts.extend(batch)
        offset += len(batch)

        if offset >= total:
            break

        time.sleep(DELAY)

    return contacts


def update_linkedin(client: httpx.Client, lead_uuid: str, slug: str) -> bool:
    resp = client.put(
        f"{BASE_URL}/leads/api/leads/{lead_uuid}",
        headers=HEADERS,
        json={"linkedin": slug},
    )
    return resp.status_code in (200, 201)


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("📂 Загружаю CSV источники...")
    email_to_slug, name_to_slug = build_mappings()
    print(f"   Email→slug маппингов: {len(email_to_slug)}")
    print(f"   Name→slug маппингов:  {len(name_to_slug)}\n")

    total_checked = 0
    total_already_ok = 0
    total_missing = 0
    total_updated = 0
    total_no_data = 0
    total_failed = 0

    with httpx.Client(timeout=60) as client:
        print("📋 Получаю списки из GetSales...")
        lists = get_all_lists(client)
        print(f"   Списков: {len(lists)}\n")

        for lst in lists:
            list_uuid = lst.get("uuid") or lst.get("id")
            list_name = lst.get("name", "?")
            if not list_uuid:
                continue

            # Фильтр по ONLY_LISTS
            if ONLY_LISTS and not any(f.lower() in list_name.lower() for f in ONLY_LISTS):
                continue

            print(f"📂 {list_name}")
            contacts = get_contacts_from_list(client, list_uuid)
            total_checked += len(contacts)

            updated = failed = no_data = 0

            for item in contacts:
                lead = item.get("lead", {})
                lead_uuid = lead.get("uuid")
                current_linkedin = lead.get("linkedin")

                if current_linkedin:
                    total_already_ok += 1
                    continue

                total_missing += 1

                # Матч по email
                email = (lead.get("work_email") or lead.get("personal_email") or "").strip().lower()
                slug = email_to_slug.get(email) if email else None

                # Fallback: матч по full_name (для контактов без email)
                if not slug:
                    name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip().lower()
                    slug = name_to_slug.get(name) if name else None

                if not slug:
                    no_data += 1
                    total_no_data += 1
                    continue

                if DRY_RUN:
                    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
                    print(f"  [DRY] {name} ({email}) → {slug}")
                    updated += 1
                    total_updated += 1
                    continue

                if update_linkedin(client, lead_uuid, slug):
                    updated += 1
                    total_updated += 1
                else:
                    failed += 1
                    total_failed += 1
                    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
                    print(f"  ✗ {name} ({lead_uuid})")

                time.sleep(DELAY)

            missing_in_list = updated + failed + no_data
            if missing_in_list > 0:
                print(f"   Без linkedin: {missing_in_list} | Обновлено: {updated} | Нет данных: {no_data} | Ошибок: {failed}")
            else:
                print(f"   Все OK ✓")
            print()

    print("=" * 60)
    print("ИТОГО:")
    print(f"  Проверено:       {total_checked}")
    print(f"  Уже OK:          {total_already_ok}")
    print(f"  Без linkedin:    {total_missing}")
    print(f"  Обновлено:       {total_updated}")
    print(f"  Нет данных:      {total_no_data}")
    print(f"  Ошибок API:      {total_failed}")
    if DRY_RUN:
        print("\n  [DRY RUN — изменений не было]")


if __name__ == "__main__":
    main()
