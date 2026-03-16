"""
Extract Pakistani-origin contacts hiding in AU-Philippines and Arabic-SouthAfrica corridors.
Writes to a NEW tab in the master sheet — never modifies existing tabs.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from datetime import datetime
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = "1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU"

# Pakistani surnames (from diaspora_service.py SURNAME_BATCHES + COUNTRY_NAME_PROFILES)
PK_SURNAMES = {
    s.lower() for s in [
        "Khan", "Malik", "Butt", "Chaudhry", "Qureshi", "Rana", "Rajput", "Akhtar",
        "Mirza", "Gill", "Bhatti", "Cheema", "Awan", "Virk", "Warraich", "Gondal",
        "Bajwa", "Afridi", "Khattak", "Siddiqui", "Sethi", "Khawaja", "Shah",
        "Hussain", "Raza", "Javed", "Aslam", "Iqbal", "Naqvi", "Bokhari",
        "Hashmi", "Haider", "Rehman", "Niazi", "Baloch", "Durrani", "Abbasi",
        "Chaudhary", "Dar", "Gul", "Mehmood", "Mahmood", "Shahid", "Waqar",
        "Tariq", "Nadeem", "Saeed", "Ashraf", "Zafar", "Anwar", "Shabbir",
        "Riaz", "Baig", "Memon", "Shaikh", "Syed", "Pasha", "Lodhi",
        "Mughal", "Minhas", "Kayani", "Bangash", "Yousaf", "Yousuf",
    ]
}

# Pakistani first names (distinctive — not shared with Arab countries)
PK_FIRST_NAMES = {
    s.lower() for s in [
        "Imran", "Kashif", "Naveed", "Arshad", "Shoaib", "Waqas", "Rizwan",
        "Asim", "Faizan", "Kamran", "Usman", "Zeeshan", "Adeel", "Junaid",
        "Irfan", "Farhan", "Arslan", "Bilal", "Hamza", "Umer", "Usama",
        "Saqib", "Shahzad", "Shehzad", "Atif", "Jawad", "Fahad", "Saad",
        "Babar", "Noman", "Rehan", "Sajid", "Tahir", "Waheed", "Zahid",
    ]
}

# Pakistani universities
PK_UNIVERSITIES = [
    "lahore", "karachi", "islamabad", "peshawar", "rawalpindi",
    "lums", "nust", "iba ", "comsats", "fast-nu", "giki",
    "quaid-i-azam", "punjab university", "aga khan", "ned university",
    "bahria", "air university", "pieas", "uet lahore", "uet peshawar",
]

SOURCE_TABS = [
    "AU-PH Combined 0316_0058",
    "Arabic-SA Combined 0316_0100",
]


def is_pk_origin(row, headers):
    """Check if a contact is likely Pakistani origin."""
    idx = {h: i for i, h in enumerate(headers)}

    last_name = (row[idx["Last Name"]] if idx.get("Last Name") is not None and idx["Last Name"] < len(row) else "").strip().lower()
    first_name = (row[idx["First Name"]] if idx.get("First Name") is not None and idx["First Name"] < len(row) else "").strip().lower()
    schools = (row[idx["Schools (from Clay)"]] if idx.get("Schools (from Clay)") is not None and idx["Schools (from Clay)"] < len(row) else "").strip().lower()

    signals = []

    # Strong signal: Pakistani surname
    if last_name in PK_SURNAMES:
        signals.append(f"surname:{last_name}")

    # Medium signal: Pakistani first name
    if first_name in PK_FIRST_NAMES:
        signals.append(f"firstname:{first_name}")

    # Strong signal: Pakistani university
    for uni in PK_UNIVERSITIES:
        if uni in schools:
            signals.append(f"university:{uni}")
            break

    # Need at least one strong signal (surname or university) or two medium signals
    has_surname = any(s.startswith("surname:") for s in signals)
    has_uni = any(s.startswith("university:") for s in signals)
    has_firstname = any(s.startswith("firstname:") for s in signals)

    if has_surname or has_uni or (has_firstname and len(signals) >= 2):
        return True, "; ".join(signals)

    return False, ""


def main():
    gs = GoogleSheetsService()

    all_pk_contacts = []
    headers = None

    for tab_name in SOURCE_TABS:
        print(f"\nReading {tab_name}...")
        raw = gs.read_sheet_raw(SHEET_ID, tab_name)
        if not raw:
            print(f"  Empty tab, skipping")
            continue

        tab_headers = raw[0]
        if headers is None:
            headers = tab_headers

        data_rows = raw[1:]
        print(f"  {len(data_rows)} contacts")

        pk_count = 0
        for row in data_rows:
            is_pk, reason = is_pk_origin(row, tab_headers)
            if is_pk:
                # Add source corridor and PK signal reason
                extended_row = list(row)
                # Pad to header length if needed
                while len(extended_row) < len(tab_headers):
                    extended_row.append("")
                extended_row.append(tab_name)  # Source Corridor
                extended_row.append(reason)    # PK Signal
                all_pk_contacts.append(extended_row)
                pk_count += 1

        print(f"  Found {pk_count} PK-origin contacts")

    if not all_pk_contacts:
        print("\nNo PK-origin contacts found in other corridors.")
        return

    # Dedup by email
    idx = {h: i for i, h in enumerate(headers)}
    email_idx = idx.get("Email", 3)
    seen_emails = set()
    deduped = []
    for row in all_pk_contacts:
        email = row[email_idx].strip().lower() if email_idx < len(row) else ""
        if email and email not in seen_emails:
            seen_emails.add(email)
            deduped.append(row)

    print(f"\nTotal PK-origin: {len(all_pk_contacts)}, after dedup: {len(deduped)}")

    # Write to NEW tab
    timestamp = datetime.now().strftime("%m%d_%H%M")
    tab_name = f"UAE-PK Reuse from Other Corridors {timestamp}"

    output_headers = list(headers) + ["Source Corridor", "PK Signal"]
    output_rows = [output_headers] + deduped

    print(f"\nWriting {len(deduped)} contacts to '{tab_name}'...")

    # Create new tab using raw Sheets API
    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        ).execute()
    except Exception as e:
        print(f"Tab creation error (may already exist): {e}")

    # Write data
    gs.sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": output_rows},
    ).execute()
    print(f"Done! Tab created: {tab_name}")

    # Summary by signal type
    signal_counts = {}
    for row in deduped:
        signals = row[-1] if len(row) > len(headers) + 1 else row[-1]
        for sig in signals.split("; "):
            key = sig.split(":")[0] if ":" in sig else sig
            signal_counts[key] = signal_counts.get(key, 0) + 1

    print(f"\nSignal breakdown:")
    for sig, count in sorted(signal_counts.items(), key=lambda x: -x[1]):
        print(f"  {sig}: {count}")


if __name__ == "__main__":
    main()
