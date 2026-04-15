#!/usr/bin/env python3
"""
Ремаппинг SL листов в Google Sheets.

Все 4 листа содержат данные из нескольких источников с разными схемами колонок.
Скрипт определяет тип каждой строки и ремапит в единый формат SmartLead.

Целевой формат (14 колонок):
first_name, last_name, email, company_name, website, linkedin_url,
phone_number, location, title, custom1, custom2, custom3, custom4, custom5
"""

import json
from pathlib import Path

SPREADSHEET_ID = "1MK_ynBiUumk5NCRksQGvwEVBMi4G9iB5-i416lgrOEA"

HEADERS = [
    "first_name",
    "last_name",
    "email",
    "company_name",
    "website",
    "linkedin_url",
    "phone_number",
    "location",
    "title",
    "custom1",
    "custom2",
    "custom3",
    "custom4",
    "custom5",
]

SEGMENTS = {"IMAGENCY", "INFPLAT", "AFFPERF", "SOCCOM"}


def is_linkedin_url(s):
    return bool(s and "linkedin.com" in s)


def is_domain(s):
    """Строка похожа на домен (нет пробелов, есть точка, нет linkedin)"""
    if not s:
        return False
    return (
        "." in s
        and " " not in s
        and "linkedin.com" not in s
        and not s.startswith("http")
    )


def is_segment_tag(s):
    return s in SEGMENTS


def is_empty_row(r):
    return all(not v for v in r.values())


def detect_row_type(r):
    """
    Определяем тип строки по содержимому полей.

    Тип NORMAL: linkedin_url содержит linkedin URL
    Тип A: linkedin_url = домен, phone_number = сегмент, location = linkedin URL
    Тип B: company_name = должность, website = название компании, linkedin_url = домен/название,
           location = linkedin URL (или title = linkedin URL)
    Тип C: first_name = домен, last_name = компания, email = имя, company_name = фамилия,
           website = должность, location = email, custom2 = сегмент
    """
    ln = r.get("linkedin_url", "")
    phone = r.get("phone_number", "")
    loc = r.get("location", "")
    title = r.get("title", "")
    comp = r.get("company_name", "")
    web = r.get("website", "")
    fn = r.get("first_name", "")
    email = r.get("email", "")
    custom2 = r.get("custom2", "")

    if is_empty_row(r):
        return "EMPTY"

    # Тип NORMAL: linkedin_url содержит настоящий linkedin URL
    if is_linkedin_url(ln):
        return "NORMAL"

    # Тип C: first_name выглядит как домен (domain.com)
    if is_domain(fn) and "@" in loc:
        return "C"

    # Тип A: linkedin_url = домен, phone_number = сегмент, location = linkedin URL
    if is_domain(ln) and is_segment_tag(phone) and is_linkedin_url(loc):
        return "A"

    # Тип B: location = linkedin URL (или title = linkedin URL), linkedin_url = домен/компания
    if is_linkedin_url(loc):
        return "B_loc"

    if is_linkedin_url(title):
        return "B_title"

    # Остальное — NORMAL (пустые linkedin, не можем ремапить)
    return "NORMAL"


def remap_row(r, segment):
    """Возвращает строку в целевом формате"""
    row_type = detect_row_type(r)

    if row_type == "EMPTY":
        return None

    if row_type == "NORMAL":
        # Уже в правильном формате, только убедимся что custom5 = сегмент если пустой
        out = {k: r.get(k, "") for k in HEADERS}
        if not out["custom5"] and segment:
            out["custom5"] = segment
        return out

    if row_type == "A":
        # linkedin_url = домен → website
        # phone_number = сегмент → custom5
        # location = реальный linkedin → linkedin_url
        # title пустой (нет данных о должности)
        out = {
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            "email": r.get("email", ""),
            "company_name": r.get("company_name", ""),
            "website": r.get("linkedin_url", ""),  # домен был в linkedin_url
            "linkedin_url": r.get("location", ""),  # реальный linkedin был в location
            "phone_number": "",
            "location": "",
            "title": r.get("title", ""),
            "custom1": r.get("custom1", ""),
            "custom2": r.get("custom2", ""),
            "custom3": r.get("custom3", ""),
            "custom4": r.get("custom4", ""),
            "custom5": segment or r.get("phone_number", ""),
        }
        return out

    if row_type == "B_loc":
        # company_name = должность
        # website = название компании
        # linkedin_url = домен или название компании
        # location = реальный linkedin
        # title = страна (игнорируем или в custom1)
        # custom1 = linkedin company url
        # custom2 = employees
        out = {
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            "email": r.get("email", ""),
            "company_name": r.get("website", ""),  # название компании было в website
            "website": r.get("linkedin_url", "")
            if is_domain(r.get("linkedin_url", ""))
            else "",
            "linkedin_url": r.get("location", ""),  # реальный linkedin
            "phone_number": "",
            "location": "",
            "title": r.get("company_name", ""),  # должность была в company_name
            "custom1": "",
            "custom2": "",
            "custom3": "",
            "custom4": "",
            "custom5": segment,
        }
        return out

    if row_type == "B_title":
        # company_name = должность
        # website = название компании
        # linkedin_url = домен
        # location = сегмент
        # title = реальный linkedin
        # custom1 = linkedin company url
        # custom2 = employees
        # custom3 = страна
        out = {
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            "email": r.get("email", ""),
            "company_name": r.get("website", ""),  # название компании
            "website": r.get("linkedin_url", "")
            if is_domain(r.get("linkedin_url", ""))
            else "",
            "linkedin_url": r.get("title", ""),  # реальный linkedin
            "phone_number": "",
            "location": "",
            "title": r.get("company_name", ""),  # должность
            "custom1": "",
            "custom2": "",
            "custom3": "",
            "custom4": "",
            "custom5": segment,
        }
        return out

    if row_type == "C":
        # first_name = домен
        # last_name = название компании
        # email = имя человека
        # company_name = фамилия (обфусцированная)
        # website = должность
        # phone_number = linkedin url (в INFPLAT) или пусто
        # location = email человека
        # custom2 = сегмент
        real_linkedin = (
            r.get("phone_number", "")
            if is_linkedin_url(r.get("phone_number", ""))
            else ""
        )
        out = {
            "first_name": r.get("email", ""),  # имя было в email
            "last_name": r.get("company_name", ""),  # фамилия в company_name
            "email": r.get("location", ""),  # реальный email в location
            "company_name": r.get("last_name", ""),  # название компании в last_name
            "website": r.get("first_name", ""),  # домен в first_name
            "linkedin_url": real_linkedin,
            "phone_number": "",
            "location": "",
            "title": r.get("website", ""),  # должность в website
            "custom1": "",
            "custom2": "",
            "custom3": "",
            "custom4": "",
            "custom5": segment or r.get("custom2", ""),
        }
        return out

    return {k: r.get(k, "") for k in HEADERS}


def process_sheet(raw_rows, segment):
    """Обрабатывает список строк, возвращает чистые данные + статистику"""
    results = []
    stats = {
        "NORMAL": 0,
        "A": 0,
        "B_loc": 0,
        "B_title": 0,
        "C": 0,
        "EMPTY": 0,
        "HEADER": 0,
    }

    for r in raw_rows:
        # Пропускаем строки-заголовки (where first_name == "first_name")
        if r.get("first_name") == "first_name":
            stats["HEADER"] += 1
            continue

        row_type = detect_row_type(r)
        stats[row_type] = stats.get(row_type, 0) + 1

        if row_type == "EMPTY":
            continue

        remapped = remap_row(r, segment)
        if remapped:
            results.append(remapped)

    return results, stats


def rows_to_values(rows):
    """Конвертирует список dict в 2D массив для записи в Sheets"""
    return [[r.get(h, "") for h in HEADERS] for r in rows]


def read_sheet_file(filepath):
    with open(filepath) as f:
        data = json.load(f)
    result = json.loads(data["result"])
    return result["values"]


def main():
    # Файлы с сырыми данными (уже скачаны агентами)
    base = Path(
        "/Users/user/.claude/projects/-Users-user-sales-engineer/e94603b6-b1e3-41e2-844d-2868c2e28771/tool-results"
    )

    sheets_config = [
        {
            "name": "SL IMAGENCY",
            "segment": "IMAGENCY",
            "file": base / "mcp-google-sheets-sheets_read_range-1776233445408.txt",
        },
        {
            "name": "SL INFPLAT",
            "segment": "INFPLAT",
            "file": base / "mcp-google-sheets-sheets_read_range-1776233608501.txt",
        },
        {
            "name": "SL AFFPERF",
            "segment": "AFFPERF",
            "file": base / "mcp-google-sheets-sheets_read_range-1776233609376.txt",
        },
        {
            "name": "SL SOCCOM",
            "segment": "SOCCOM",
            "file": base / "mcp-google-sheets-sheets_read_range-1776233446261.txt",
        },
    ]

    all_results = {}

    for cfg in sheets_config:
        print(f"\n{'=' * 50}")
        print(f"Processing: {cfg['name']}")
        raw = read_sheet_file(cfg["file"])
        rows, stats = process_sheet(raw, cfg["segment"])
        all_results[cfg["name"]] = rows
        print(f"  Stats: {stats}")
        print(f"  Output rows: {len(rows)}")

        # Validate: проверим пару строк каждого типа
        if rows:
            print(
                f"  Sample row 1: fn={rows[0]['first_name']!r} ln={rows[0]['linkedin_url'][:50]!r} title={rows[0]['title'][:30]!r} c5={rows[0]['custom5']!r}"
            )
            if len(rows) > 1:
                print(
                    f"  Sample row 2: fn={rows[1]['first_name']!r} ln={rows[1]['linkedin_url'][:50]!r} title={rows[1]['title'][:30]!r} c5={rows[1]['custom5']!r}"
                )

    # Сохраняем результаты в JSON для проверки перед записью
    output_file = "/tmp/sl_sheets_remapped.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {output_file}")

    # Summary
    print(f"\n{'=' * 50}")
    print("SUMMARY:")
    for name, rows in all_results.items():
        print(f"  {name}: {len(rows)} rows ready to write")

    return all_results


if __name__ == "__main__":
    main()
