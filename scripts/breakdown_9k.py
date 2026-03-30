#!/usr/bin/env python3
"""Breakdown of 9,206 UAE-PK clean contacts by search approach."""
import sys
from collections import Counter
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

gs = GoogleSheetsService()
raw = gs.read_sheet_raw("14HZooDysNErNYlLBvCvn5KfxJnB1LqFxhHJlPfypaHU", "Sheet1")
headers = raw[0]
rows = raw[1:]
col = {h: i for i, h in enumerate(headers)}

print(f"Total: {len(rows)}")

st_idx = col.get("Search Type", -1)
os_idx = col.get("Origin Score", -1)

# By search type
search_types = Counter()
origin_scores = Counter()
for r in rows:
    st = (r[st_idx] if st_idx >= 0 and st_idx < len(r) else "").strip()
    os_val = (r[os_idx] if os_idx >= 0 and os_idx < len(r) else "").strip()
    search_types[st or "(empty)"] += 1
    origin_scores[os_val or "0"] += 1

print("\nBy search approach:")
for st, cnt in search_types.most_common():
    pct = cnt * 100 / len(rows)
    print(f"  {cnt:>5} ({pct:4.1f}%)  {st}")

print("\nBy origin score:")
for os_val, cnt in sorted(origin_scores.items()):
    pct = cnt * 100 / len(rows)
    label = {"10": "language (auto-accept)", "9": "university (auto-accept)", "8": "surname (GPT-scored)"}.get(os_val, "other")
    print(f"  {cnt:>5} ({pct:4.1f}%)  origin={os_val} — {label}")
