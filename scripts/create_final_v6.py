#!/usr/bin/env python3
import json, sys
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

gs = GoogleSheetsService()
raw = gs.read_sheet_raw("14HZooDysNErNYlLBvCvn5KfxJnB1LqFxhHJlPfypaHU", "Sheet1")
headers = raw[0]
rows = raw[1:]

removed = set(json.load(open("/tmp/uae_pk_final_algo_v6.json")))
clean = [r for r in rows if r[0].strip() not in removed]
for i, r in enumerate(clean):
    r[0] = str(i + 1)

url = gs.create_and_populate("UAE-PK FINAL 7913 v6", [headers] + clean)
print(f"URL: {url}")
print(f"Contacts: {len(clean)}")
