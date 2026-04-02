"""
GetSales — обновить linkedin_id для существующих контактов через API upsert.
Запускать локально: python3.11 getsales_update_linkedin_id.py
"""

import csv
import json
import time
import httpx
from pathlib import Path

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3NDQ1NzU0MywiZXhwIjoxODY5MDY1NTQzLCJuYmYiOjE3NzQ0NTc1NDMsImp0aSI6ImNWOEJDVmprV08yeGdLdEIiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.2dDmw7L-ZWNd4RJWL0XOSlP2qq1PjZtS1QSJr3pe0Vw"

LIST_IDS = {
    "IMAGENCY_INDIA":    "43c1e21f-1eb8-4f69-9611-e4ce0119a2f7",
    "INFPLAT_INDIA":     "a6e3ae0c-f4f9-4279-bc4f-c2d6e59a7a01",
    "INFPLAT_MENA_APAC": "",  # список ещё не создан в GetSales
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # sales_engineer/
CSV_FILES = {
    "IMAGENCY_INDIA":    BASE_DIR / "GS_Import_IMAGENCY_INDIA_2026-04-01.csv",
    "INFPLAT_INDIA":     BASE_DIR / "GS_Import_INFPLAT_INDIA_2026-04-01.csv",
    "INFPLAT_MENA_APAC": BASE_DIR / "GS_Import_INFPLAT_MENA_APAC_2026-04-01.csv",
}

API_URL = "https://amazing.getsales.io/leads/api/leads"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
DELAY = 0.3  # секунд между запросами
# ──────────────────────────────────────────────────────────────────────────────


def update_contacts(segment_name: str, list_id: str, csv_path: Path):
    print(f"\n{'='*60}")
    print(f"Сегмент: {segment_name} | List ID: {list_id}")
    print(f"Файл: {csv_path.name}")

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Контактов в CSV: {len(rows)}")

    ok, fail, skip = 0, 0, 0

    with httpx.Client(timeout=30) as client:
        for i, row in enumerate(rows, 1):
            linkedin_id = row.get("linkedin_id", "").strip()
            email = row.get("work_email", "").strip()
            full_name = row.get("full_name", "").strip()

            if not linkedin_id:
                skip += 1
                continue

            lead = {
                "linkedin_id": linkedin_id,
                "linkedin_url": row.get("linkedin_url", "").strip(),
                "linkedin_nickname": row.get("linkedin_nickname", "").strip(),
                "first_name": row.get("first_name", "").strip(),
                "last_name": row.get("last_name", "").strip(),
                "work_email": email,
                "company_name": row.get("company_name", "").strip(),
            }
            lead = {k: v for k, v in lead.items() if v}

            payload = {
                "list_uuid": list_id,
                "leads": [lead],
            }

            try:
                resp = client.post(API_URL, headers=HEADERS, json=payload)
                if resp.status_code in (200, 201):
                    ok += 1
                    if i % 20 == 0:
                        print(f"  [{i}/{len(rows)}] ✓ {full_name}")
                else:
                    fail += 1
                    if fail <= 3:
                        print(f"  [{i}] ✗ {full_name} — {resp.status_code}: {resp.text[:300]}")
            except Exception as e:
                fail += 1
                if fail <= 3:
                    print(f"  [{i}] ✗ {full_name} — ошибка: {e}")

            time.sleep(DELAY)

    print(f"\nРезультат {segment_name}: ✓ {ok} обновлено | ✗ {fail} ошибок | — {skip} пропущено")


def main():
    if API_KEY == "ВСТАВЬ_СВОЙ_API_KEY":
        print("❌ Вставь API_KEY в скрипт!")
        return

    for segment, list_id in LIST_IDS.items():
        if list_id == "ВСТАВЬ_LIST_ID":
            print(f"⚠️  Пропускаю {segment} — не заполнен LIST_ID")
            continue
        update_contacts(segment, list_id, CSV_FILES[segment])

    print("\n✅ Готово")


if __name__ == "__main__":
    main()
