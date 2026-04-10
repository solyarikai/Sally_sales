#!/usr/bin/env python3.11
"""Filter pipeline output CSVs against contacts table in DB (dedup vs SmartLead/GetSales)."""

import csv
import subprocess
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "Project_42" / "pipeline"
SEGMENTS = ["IMAGENCY", "INFPLAT", "SOCCOM"]
DATE = "2026-04-10"

# 1. Collect all emails from output CSVs
all_emails = set()
files = {}
for seg in SEGMENTS:
    for kind in ["leads_with_email", "leads_linkedin_only"]:
        fname = f"{kind}_{seg}_{DATE}.csv"
        fpath = OUTPUT_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath) as f:
            rows = list(csv.DictReader(f))
        files[(seg, kind)] = (fpath, rows)
        for row in rows:
            e = row.get("email", "").strip().lower()
            if e:
                all_emails.add(e)

print(f"Всего email для проверки: {len(all_emails)}")

# 2. Query DB via SSH — find which emails already exist in contacts
email_list = list(all_emails)
# Split into chunks to avoid too-long query
CHUNK = 200
found_in_db = set()

for i in range(0, len(email_list), CHUNK):
    chunk = email_list[i : i + CHUNK]
    values = ",".join(f"'{e}'" for e in chunk)
    sql = f"SELECT LOWER(email) FROM contacts WHERE LOWER(email) IN ({values})"
    cmd = [
        "ssh",
        "hetzner",
        f'docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -c "{sql}"',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in result.stdout.strip().splitlines():
        e = line.strip().lower()
        if e:
            found_in_db.add(e)

print(f"Найдено в БД (уже контактировали): {len(found_in_db)}")

# 3. Filter CSVs
total_in = total_out = total_blocked = 0

for (seg, kind), (fpath, rows) in files.items():
    kept = []
    blocked = []
    for row in rows:
        e = row.get("email", "").strip().lower()
        if e and e in found_in_db:
            blocked.append(row)
        else:
            kept.append(row)

    total_in += len(rows)
    total_out += len(kept)
    total_blocked += len(blocked)

    if blocked:
        print(f"\n  {seg} / {kind}: {len(rows)} → {len(kept)} (убрано {len(blocked)})")
        for row in blocked:
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            email = row.get("email", "")
            print(f"    ✗ {name} <{email}>")
    else:
        print(f"  {seg} / {kind}: {len(rows)} → {len(kept)} (новых дублей нет)")

    if blocked and kept:
        with open(fpath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(kept)
        print("    → CSV обновлён")

print(f"\n{'=' * 50}")
print(f"Итого: {total_in} → {total_out} (убрано {total_blocked})")
