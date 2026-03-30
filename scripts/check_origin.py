#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService
from collections import Counter

gs = GoogleSheetsService()
raw = gs.read_sheet_raw("14HZooDysNErNYlLBvCvn5KfxJnB1LqFxhHJlPfypaHU", "Sheet1")
headers = raw[0]
rows = raw[1:]
col = {h:i for i,h in enumerate(headers)}

origins = Counter()
searches = Counter()
for r in rows:
    o = r[col["Origin Score"]] if col["Origin Score"] < len(r) else "?"
    s = r[col["Search Type"]] if col["Search Type"] < len(r) else "?"
    origins[o] += 1
    searches[s] += 1

print("Origin Score:")
for o, cnt in sorted(origins.items()):
    label = {"10": "language (Urdu)", "9": "university (PK uni)", "8": "surname (GPT)"}.get(o, "other")
    print(f"  {o}: {cnt} ({cnt*100/len(rows):.1f}%) — {label}")

print("\nSearch Type:")
for s, cnt in searches.most_common():
    print(f"  {s}: {cnt}")

print("\nSample origin=8 (surname match):")
count = 0
for r in rows:
    if r[col["Origin Score"]] == "8" and count < 10:
        fn = r[col["First Name"]]
        ln = r[col["Last Name"]]
        sig = r[col.get("Origin Signal", 11)] if col.get("Origin Signal", 11) < len(r) else ""
        print(f"  {fn} {ln} | {sig[:80]}")
        count += 1
