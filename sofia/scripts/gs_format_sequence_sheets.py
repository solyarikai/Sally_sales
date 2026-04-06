#!/usr/bin/env python3
import warnings; warnings.filterwarnings("ignore")
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/sofia/Documents/GitHub/Sally_sales/.claude/google-sheets/token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E"

creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
service = build("sheets", "v4", credentials=creds)
sheets = service.spreadsheets()

meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
sheet_ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

# ── Color palette ─────────────────────────────────────────────────────────────
def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

DARK_BLUE    = rgb(30, 55, 90)       # campaign title header
MID_BLUE     = rgb(52, 103, 165)     # section headers
LIGHT_BLUE   = rgb(214, 227, 245)    # table column headers
VARIANT_A    = rgb(180, 220, 180)    # Variant A highlight
VARIANT_B    = rgb(255, 230, 180)    # Variant B highlight
GREY_ROW     = rgb(245, 245, 248)    # alternating rows
GREEN_DONE   = rgb(87, 187, 138)     # done status
ORANGE_TODO  = rgb(255, 180, 80)     # todo status
WHITE        = rgb(255, 255, 255)
TEXT_WHITE   = rgb(255, 255, 255)
TEXT_DARK    = rgb(30, 30, 30)

def cell_fmt(sid, r1, c1, r2, c2, bg=None, bold=False, text_color=None,
             font_size=None, wrap=None, valign=None, halign=None, borders=None):
    fmt = {}
    if bg:           fmt["backgroundColor"] = bg
    if text_color:   fmt.setdefault("textFormat", {})["foregroundColor"] = text_color
    if bold:         fmt.setdefault("textFormat", {})["bold"] = True
    if font_size:    fmt.setdefault("textFormat", {})["fontSize"] = font_size
    if wrap:         fmt["wrapStrategy"] = wrap
    if valign:       fmt["verticalAlignment"] = valign
    if halign:       fmt["horizontalAlignment"] = halign
    req = {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat(" + ",".join([
            "backgroundColor" if bg else "",
            "textFormat" if (bold or text_color or font_size) else "",
            "wrapStrategy" if wrap else "",
            "verticalAlignment" if valign else "",
            "horizontalAlignment" if halign else "",
        ]).replace(",,",",").strip(",") + ")"
    }}
    return req

def merge(sid, r1, c1, r2, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL"
    }}

def col_width(sid, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": col, "endIndex": col+1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize"
    }}

def row_height(sid, row, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": row, "endIndex": row+1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize"
    }}

def freeze(sid, rows=1, cols=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": rows, "frozenColumnCount": cols}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
    }}

def outline_border(sid, r1, c1, r2, c2, color=None):
    c = color or rgb(180, 180, 180)
    style = {"style": "SOLID", "color": c}
    return {"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "top": style, "bottom": style, "left": style, "right": style,
        "innerHorizontal": {"style": "SOLID", "color": rgb(220, 220, 220)},
        "innerVertical": {"style": "SOLID", "color": rgb(220, 220, 220)},
    }}

all_requests = []

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 1: Sequences | INFPLAT
# ═══════════════════════════════════════════════════════════════════════════════
sid = sheet_ids.get("Sequences | INFPLAT")
if sid is not None:
    R = all_requests
    # Column widths
    for col, px in [(0,220),(1,90),(2,70),(3,80),(4,280)]:
        R.append(col_width(sid, col, px))
    # Row 0 — campaign title
    R.append(cell_fmt(sid,0,0,1,6, bg=DARK_BLUE, bold=True, text_color=TEXT_WHITE, font_size=12, halign="LEFT"))
    R.append(row_height(sid, 0, 36))
    # Row 1 — target/context (light blue)
    R.append(cell_fmt(sid,1,0,2,6, bg=LIGHT_BLUE, bold=True, halign="LEFT"))
    # Row 2 — empty spacer
    R.append(cell_fmt(sid,2,0,3,6, bg=WHITE))
    # Row 3 — "STEP / DELAY" column headers
    R.append(cell_fmt(sid,3,0,4,6, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE, halign="CENTER"))
    R.append(row_height(sid, 3, 28))
    # Row 4 — subheaders (SUBJECT / BODY)
    R.append(cell_fmt(sid,4,0,5,6, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    # Rows 5-9 — step data alternating
    for i, r in enumerate(range(5, 14)):
        bg = WHITE if i % 2 == 0 else GREY_ROW
        R.append(cell_fmt(sid, r, 0, r+1, 6, bg=bg, wrap="WRAP", valign="TOP"))
    # Variant A column (cols 1-2) tint
    R.append(cell_fmt(sid,4,1,14,3, bg=rgb(220,240,220)))
    # Variant B column (cols 3-4) tint
    R.append(cell_fmt(sid,4,3,14,5, bg=rgb(255,240,210)))
    # Headers re-bold after tint
    R.append(cell_fmt(sid,3,0,4,6, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE, halign="CENTER"))
    R.append(cell_fmt(sid,4,0,5,6, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    R.append(freeze(sid, rows=5))
    R.append(outline_border(sid,3,0,14,5))

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 2: Sequences | INFPLAT_ALLGEO
# Row layout (from script that created it):
# 0: campaign title
# 1: status
# 2: empty
# 3: table headers (Step/Day/Subject/Body)
# 4-8: Step 1A, 1B, 2, 3, 4, 5
# ...
# 11: "Source" header
# 12-14: source rows + delays
# ═══════════════════════════════════════════════════════════════════════════════
sid = sheet_ids.get("Sequences | INFPLAT_ALLGEO")
if sid is not None:
    R = all_requests
    for col, px in [(0,120),(1,50),(2,250),(3,420)]:
        R.append(col_width(sid, col, px))
    # Title row 0
    R.append(cell_fmt(sid,0,0,1,4, bg=DARK_BLUE, bold=True, text_color=TEXT_WHITE, font_size=12))
    R.append(row_height(sid,0,36))
    # Status row 1
    R.append(cell_fmt(sid,1,0,2,4, bg=rgb(255,244,200), bold=True))
    # Row 2 spacer
    R.append(cell_fmt(sid,2,0,3,4, bg=WHITE))
    # Table header row 3
    R.append(cell_fmt(sid,3,0,4,4, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE, halign="CENTER"))
    R.append(row_height(sid,3,28))
    # Step rows 4-8 (Step 1A, 1B, 2, 3, 4, 5) — alternating + variant colors
    step_colors = [VARIANT_A, VARIANT_B, GREY_ROW, WHITE, GREY_ROW, WHITE]
    for i, r in enumerate(range(4, 10)):
        bg = step_colors[i] if i < len(step_colors) else WHITE
        R.append(cell_fmt(sid,r,0,r+1,4, bg=bg, wrap="WRAP", valign="TOP"))
        R.append(row_height(sid,r,120))
    # Spacer row 10
    R.append(cell_fmt(sid,10,0,11,4, bg=WHITE))
    # Source header row 11
    R.append(cell_fmt(sid,11,0,12,4, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE))
    # Source data rows 12-15
    for i, r in enumerate(range(12, 16)):
        R.append(cell_fmt(sid,r,0,r+1,4, bg=WHITE if i%2==0 else GREY_ROW))
    R.append(outline_border(sid,3,0,10,4))
    R.append(outline_border(sid,11,0,16,4))
    R.append(freeze(sid,rows=4))

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 3: Sequences | IMAGENCY_ALLGEO
# Row layout:
# 0: title, 1: status, 2: empty
# 3: "REPLY DATA" header, 4: col headers, 5-9: campaign rows, 10: total
# 11: empty, 12: note
# 13: empty, 14: "A/B DECISION" header, 15: sub-headers, 16-20: decision rows
# 21: empty, 22: "FULL SEQUENCES" header, 23: col headers, 24-28: step rows
# 29: empty, 30: delays note
# ═══════════════════════════════════════════════════════════════════════════════
sid = sheet_ids.get("Sequences | IMAGENCY_ALLGEO")
if sid is not None:
    R = all_requests
    for col, px in [(0,130),(1,90),(2,90),(3,390),(4,390)]:
        R.append(col_width(sid, col, px))
    # Title
    R.append(cell_fmt(sid,0,0,1,5, bg=DARK_BLUE, bold=True, text_color=TEXT_WHITE, font_size=12))
    R.append(row_height(sid,0,36))
    # Status
    R.append(cell_fmt(sid,1,0,2,5, bg=rgb(255,244,200), bold=True))
    # Spacer
    R.append(cell_fmt(sid,2,0,3,5, bg=WHITE))
    # Reply data section header
    R.append(cell_fmt(sid,3,0,4,5, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE))
    R.append(row_height(sid,3,28))
    # Col headers
    R.append(cell_fmt(sid,4,0,5,5, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    # Campaign rows 5-9
    for i, r in enumerate(range(5, 10)):
        R.append(cell_fmt(sid,r,0,r+1,5, bg=WHITE if i%2==0 else GREY_ROW))
    # Total row 10 — bold
    R.append(cell_fmt(sid,10,0,11,5, bg=LIGHT_BLUE, bold=True))
    # Note row 12
    R.append(cell_fmt(sid,12,0,13,5, bg=rgb(255,250,220)))
    # Spacer 13
    R.append(cell_fmt(sid,13,0,14,5, bg=WHITE))
    # A/B Decision section
    R.append(cell_fmt(sid,14,0,15,5, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE))
    R.append(row_height(sid,14,28))
    R.append(cell_fmt(sid,15,0,16,5, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    # Variant A col (cols 1)
    R.append(cell_fmt(sid,15,1,21,2, bg=rgb(220,240,220)))
    # Variant B col (cols 2)
    R.append(cell_fmt(sid,15,2,21,3, bg=rgb(255,240,210)))
    # Re-apply header
    R.append(cell_fmt(sid,15,0,16,5, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    for i, r in enumerate(range(16, 21)):
        R.append(cell_fmt(sid,r,0,r+1,5, bg=WHITE if i%2==0 else GREY_ROW, wrap="WRAP"))
    # Spacer 21
    R.append(cell_fmt(sid,21,0,22,5, bg=WHITE))
    # Full sequences section
    R.append(cell_fmt(sid,22,0,23,5, bg=MID_BLUE, bold=True, text_color=TEXT_WHITE))
    R.append(row_height(sid,22,28))
    R.append(cell_fmt(sid,23,0,24,5, bg=LIGHT_BLUE, bold=True, halign="CENTER"))
    # Variant A/B column headers in step rows
    R.append(cell_fmt(sid,23,3,24,4, bg=VARIANT_A, bold=True, halign="CENTER"))
    R.append(cell_fmt(sid,23,4,24,5, bg=VARIANT_B, bold=True, halign="CENTER"))
    # Step rows 24-28
    for i, r in enumerate(range(24, 29)):
        R.append(cell_fmt(sid,r,0,r+1,3, bg=WHITE if i%2==0 else GREY_ROW, wrap="WRAP", valign="TOP"))
        R.append(cell_fmt(sid,r,3,r+1,4, bg=rgb(235,248,235), wrap="WRAP", valign="TOP"))
        R.append(cell_fmt(sid,r,4,r+1,5, bg=rgb(255,246,230), wrap="WRAP", valign="TOP"))
        R.append(row_height(sid,r,160))
    # Note row 30
    R.append(cell_fmt(sid,30,0,31,5, bg=rgb(235,235,245)))
    R.append(outline_border(sid,3,0,11,5))
    R.append(outline_border(sid,14,0,21,5))
    R.append(outline_border(sid,22,0,29,5))
    R.append(freeze(sid, rows=1))

# ── Execute all requests in batches of 50 ─────────────────────────────────────
BATCH = 50
for i in range(0, len(all_requests), BATCH):
    batch = all_requests[i:i+BATCH]
    sheets.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": batch}).execute()
    print(f"  Batch {i//BATCH + 1}/{(len(all_requests)-1)//BATCH + 1} done ({len(batch)} requests)")

print(f"\nDone. Total requests: {len(all_requests)}")
print(f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
