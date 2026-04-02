"""
GetSales — заполнить linkedin_id из linkedin_url для контактов, у которых ln_id пустой.

Логика:
  1. Получить все списки
  2. Для каждого списка — все контакты (пагинация по 100)
  3. Найти контакты: ln_id пустой + linkedin URL есть
  4. Извлечь nickname из URL: linkedin.com/in/john-doe → john-doe
  5. Обновить через POST /leads/api/leads (upsert по uuid)

Запуск локально:
    python3.11 sofia/scripts/getsales_fix_linkedin_id.py
"""

import json
import re
import time
import httpx

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

BASE_URL = "https://amazing.getsales.io"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
DELAY = 0.2  # сек между запросами
DRY_RUN = False  # True = только показать, не обновлять


def extract_linkedin_id(url: str) -> str | None:
    """Извлечь nickname из LinkedIn URL.

    linkedin.com/in/john-doe        → john-doe
    linkedin.com/in/john-doe/       → john-doe
    https://www.linkedin.com/in/ab  → ab
    """
    if not url:
        return None
    url = url.strip().rstrip("/")
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def get_all_lists(client: httpx.Client) -> list:
    resp = client.get(f"{BASE_URL}/leads/api/lists", headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def get_contacts_from_list(client: httpx.Client, list_uuid: str) -> list:
    """Получить все контакты из списка (пагинация по 100)."""
    contacts = []
    offset = 0
    page_size = 100

    while True:
        payload = {
            "filter": {"list_uuid": list_uuid},
            "limit": page_size,
            "offset": offset,
        }
        resp = client.post(
            f"{BASE_URL}/leads/api/leads/search",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code != 200:
            print(f"    ⚠️  search error {resp.status_code}: {resp.text[:200]}")
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


def update_lead_linkedin_id(client: httpx.Client, list_uuid: str, lead_uuid: str, linkedin_id: str) -> bool:
    """Обновить ln_id у контакта через upsert."""
    payload = {
        "list_uuid": list_uuid,
        "leads": [{"uuid": lead_uuid, "ln_id": linkedin_id}],
    }
    resp = client.post(f"{BASE_URL}/leads/api/leads", headers=HEADERS, json=payload)
    return resp.status_code in (200, 201)


def main():
    total_checked = 0
    total_missing = 0
    total_has_url = 0
    total_updated = 0
    total_failed = 0

    with httpx.Client(timeout=60) as client:
        print("📋 Получаю списки из GetSales...")
        lists = get_all_lists(client)
        print(f"   Найдено списков: {len(lists)}\n")

        for lst in lists:
            list_uuid = lst.get("uuid") or lst.get("id")
            list_name = lst.get("name", "?")

            if not list_uuid:
                continue

            print(f"📂 Список: {list_name} ({list_uuid})")
            contacts = get_contacts_from_list(client, list_uuid)
            print(f"   Контактов: {len(contacts)}")

            list_missing = 0
            list_updated = 0
            list_failed = 0
            list_no_url = 0

            for item in contacts:
                lead = item.get("lead", {})
                lead_uuid = lead.get("uuid")
                ln_id = lead.get("ln_id") or lead.get("linkedin_id")
                linkedin_url = lead.get("linkedin")
                name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()

                total_checked += 1

                if ln_id:
                    continue  # уже есть

                total_missing += 1
                list_missing += 1

                if not linkedin_url:
                    list_no_url += 1
                    continue

                extracted = extract_linkedin_id(linkedin_url)
                if not extracted:
                    list_no_url += 1
                    continue

                total_has_url += 1

                if DRY_RUN:
                    print(f"   [DRY] {name} → {extracted}")
                    list_updated += 1
                    total_updated += 1
                    continue

                success = update_lead_linkedin_id(client, list_uuid, lead_uuid, extracted)
                if success:
                    list_updated += 1
                    total_updated += 1
                else:
                    list_failed += 1
                    total_failed += 1
                    print(f"   ✗ Не удалось обновить: {name} ({lead_uuid})")

                time.sleep(DELAY)

            if list_missing > 0:
                print(f"   → Без ln_id: {list_missing} | Обновлено: {list_updated} | Нет URL: {list_no_url} | Ошибок: {list_failed}")
            else:
                print(f"   → Все контакты имеют ln_id ✓")
            print()

    print("=" * 60)
    print(f"ИТОГО:")
    print(f"  Проверено:    {total_checked}")
    print(f"  Без ln_id:    {total_missing}")
    print(f"  Был URL:      {total_has_url}")
    print(f"  Обновлено:    {total_updated}")
    print(f"  Ошибок:       {total_failed}")
    print(f"  Без URL:      {total_missing - total_has_url}")
    if DRY_RUN:
        print("\n  [DRY RUN — реальных изменений не было]")


if __name__ == "__main__":
    main()
