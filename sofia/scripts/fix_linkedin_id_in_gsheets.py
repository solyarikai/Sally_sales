#!/usr/bin/env python3
"""
Найти все Google Sheets с "No email" в названии (в папках OnSocial)
и заполнить пустой столбец linkedin_id из linkedin_url.

linkedin_id = никнейм из URL: https://www.linkedin.com/in/NICKNAME → NICKNAME

Usage:
    python3.11 sofia/scripts/fix_linkedin_id_in_gsheets.py
"""

import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/user/.claude/google-sheets/token.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Папки OnSocial для поиска
FOLDERS_TO_SEARCH = [
    "1_1ck-0sn1jXm2px4MCz4o_ZST6J6JfOe",  # Leads
    "1O-rkQK6btZjXzO-p31ZMsrjcLWeacZRV",  # Import
    "124SCStl6SHuMPquxyfj0Av5O8U4kNrTj",  # Target
    "1K7bVbvVU3LIK5V_cGLwhFKINBdURZLD0",  # Ops
]


def get_creds():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def extract_linkedin_id(url: str) -> str:
    """https://www.linkedin.com/in/NICKNAME → NICKNAME"""
    if not url:
        return ""
    m = re.search(r"linkedin\.com/in/([^/?#\s]+)", url, re.IGNORECASE)
    if m:
        return m.group(1).rstrip("/")
    return ""


def find_no_email_sheets(drive_svc):
    """Найти все файлы с 'No email' в названии в указанных папках."""
    results = []
    for folder_id in FOLDERS_TO_SEARCH:
        query = (
            f"'{folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.spreadsheet' "
            f"and name contains 'No email' "
            f"and trashed=false"
        )
        page_token = None
        while True:
            resp = drive_svc.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                results.append(f)
                print(f"  Найден: {f['name']} ({f['id']})")
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return results


def fix_linkedin_id_in_sheet(sheets_svc, sheet_id: str, sheet_name: str):
    """Заполнить linkedin_id из linkedin_url для строк где linkedin_id пуст."""
    # Читаем все данные
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="A1:AZ5000",
    ).execute()
    values = result.get("values", [])
    if not values:
        print(f"  [{sheet_name}] Пустой лист, пропускаю")
        return

    header = values[0]

    # Найти индексы нужных столбцов
    try:
        li_id_col = header.index("linkedin_id")
    except ValueError:
        print(f"  [{sheet_name}] Нет столбца linkedin_id, пропускаю")
        return

    try:
        li_url_col = header.index("linkedin_url")
    except ValueError:
        print(f"  [{sheet_name}] Нет столбца linkedin_url, пропускаю")
        return

    print(f"  [{sheet_name}] linkedin_id=col {li_id_col}, linkedin_url=col {li_url_col}")

    # Подготовить обновления для строк где linkedin_id пуст
    updates = []
    fixed_count = 0

    for row_idx, row in enumerate(values[1:], start=2):  # start=2 т.к. 1-я строка заголовок
        # Безопасно получить значение (строка может быть короче)
        li_id = row[li_id_col].strip() if li_id_col < len(row) else ""
        li_url = row[li_url_col].strip() if li_url_col < len(row) else ""

        if not li_id and li_url:
            new_id = extract_linkedin_id(li_url)
            if new_id:
                # Конвертируем col index → буква колонки
                col_letter = col_to_letter(li_id_col)
                cell = f"{col_letter}{row_idx}"
                updates.append({
                    "range": cell,
                    "values": [[new_id]],
                })
                fixed_count += 1

    if not updates:
        print(f"  [{sheet_name}] Нечего обновлять (все linkedin_id уже заполнены или нет URL)")
        return

    # Пакетное обновление
    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            "valueInputOption": "RAW",
            "data": updates,
        },
    ).execute()

    print(f"  [{sheet_name}] Заполнено {fixed_count} ячеек linkedin_id ✓")


def col_to_letter(col_idx: int) -> str:
    """0 → A, 25 → Z, 26 → AA, etc."""
    result = ""
    col_idx += 1  # 1-based
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def main():
    print("Авторизация Google...")
    creds = get_creds()
    drive_svc = build("drive", "v3", credentials=creds)
    sheets_svc = build("sheets", "v4", credentials=creds)

    print("\nИщу листы с 'No email' в названии...")
    sheets = find_no_email_sheets(drive_svc)

    if not sheets:
        print("Листы не найдены.")
        return

    print(f"\nНайдено {len(sheets)} листов. Обрабатываю...")
    for sheet in sheets:
        fix_linkedin_id_in_sheet(sheets_svc, sheet["id"], sheet["name"])

    print("\n✅ Готово")


if __name__ == "__main__":
    main()
