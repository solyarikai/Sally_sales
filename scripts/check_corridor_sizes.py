#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService
gs = GoogleSheetsService()
sid = "1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU"
for tab in ["AU-Philippines", "Arabic-SouthAfrica", "UAE-Pakistan"]:
    raw = gs.read_sheet_raw(sid, tab)
    # Check last row search type
    if raw and len(raw) > 2:
        headers = raw[0]
        col = {h:i for i,h in enumerate(headers)}
        st_idx = col.get("Search Type", -1)
        last_st = raw[-1][st_idx] if st_idx >= 0 and st_idx < len(raw[-1]) else "?"
        print(f"{tab}: {len(raw)-1} contacts, last_search_type={last_st}")
    else:
        print(f"{tab}: {len(raw)-1 if raw else 0}")
