#!/usr/bin/env python3
import json, sys
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

gs = GoogleSheetsService()
raw = gs.read_sheet_raw("14HZooDysNErNYlLBvCvn5KfxJnB1LqFxhHJlPfypaHU", "Sheet1")
headers = raw[0]
rows = raw[1:]
removals = set(json.load(open("/tmp/uae_pk_final_removals.json")))

clean = [r for r in rows if r[0].strip() not in removals]
for i, r in enumerate(clean):
    r[0] = str(i + 1)

url = gs.create_and_populate("UAE-PK FINAL 8406 Opus-verified", [headers] + clean)
print(f"URL: {url}")
print(f"Contacts: {len(clean)}")
