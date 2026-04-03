"""
Create "New Only" tabs in Google Sheet for contacts not in CRM.
Runs inside leadgen-backend container.
"""
import gspread
from google.oauth2.service_account import Credentials
import psycopg2

SHEET_ID = "1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU"
CORRIDORS = ["UAE-Pakistan", "AU-Philippines", "Arabic-SouthAfrica"]
CREDS_PATH = "/app/google-credentials.json"
IMPERSONATE = "services@getsally.io"
DB_DSN = "postgresql://leadgen:leadgen_secret@postgres:5432/leadgen"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_crm_emails_and_urls():
    """Fetch all known emails and LinkedIn URLs from CRM."""
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    cur.execute("SELECT lower(trim(email)) FROM contacts WHERE email IS NOT NULL AND email != ''")
    emails = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT lower(trim(linkedin_url)) FROM contacts WHERE linkedin_url IS NOT NULL AND linkedin_url != ''")
    urls = {row[0] for row in cur.fetchall()}

    cur.close()
    conn.close()
    print(f"CRM has {len(emails)} emails and {len(urls)} LinkedIn URLs")
    return emails, urls


def clean_value(val):
    """Remove null bytes and clean whitespace."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.replace("\x00", "").strip()
    return val


def find_email_col(header):
    """Find the email column index (0-based)."""
    for i, h in enumerate(header):
        if h and "email" in h.lower():
            return i
    return None


def find_linkedin_col(header):
    """Find the LinkedIn URL column index (0-based)."""
    for i, h in enumerate(header):
        if h and ("linkedin" in h.lower() or "li_url" in h.lower() or "profile" in h.lower()):
            return i
    return None


def main():
    # Auth
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    creds = creds.with_subject(IMPERSONATE)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SHEET_ID)

    # Get CRM data
    crm_emails, crm_urls = get_crm_emails_and_urls()

    # Existing worksheet titles
    existing_titles = {ws.title for ws in spreadsheet.worksheets()}

    for corridor in CORRIDORS:
        print(f"\n--- Processing: {corridor} ---")

        try:
            ws = spreadsheet.worksheet(corridor)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  Tab '{corridor}' not found, skipping")
            continue

        all_values = ws.get_all_values()
        if not all_values:
            print(f"  Tab '{corridor}' is empty, skipping")
            continue

        header = [clean_value(v) for v in all_values[0]]
        rows = all_values[1:]
        total = len(rows)

        email_col = find_email_col(header)
        linkedin_col = find_linkedin_col(header)

        print(f"  Header: {header}")
        print(f"  Email col index: {email_col}, LinkedIn col index: {linkedin_col}")
        print(f"  Total data rows: {total}")

        if email_col is None and linkedin_col is None:
            print(f"  WARNING: No email or LinkedIn column found, copying all rows")
            new_rows = rows
        else:
            new_rows = []
            for row in rows:
                cleaned = [clean_value(v) for v in row]
                email = cleaned[email_col].lower().strip() if email_col is not None and email_col < len(cleaned) else ""
                li_url = cleaned[linkedin_col].lower().strip() if linkedin_col is not None and linkedin_col < len(cleaned) else ""

                # Contact is "existing" if EITHER email or LinkedIn URL matches
                email_match = email and email in crm_emails
                url_match = li_url and li_url in crm_urls

                if not email_match and not url_match:
                    new_rows.append(cleaned)

        new_count = len(new_rows)
        removed = total - new_count
        print(f"  Original: {total} | New Only: {new_count} | Removed (in CRM): {removed}")

        # Create or clear the "New Only" tab
        new_title = f"{corridor} - New Only"
        if new_title in existing_titles:
            new_ws = spreadsheet.worksheet(new_title)
            new_ws.clear()
            print(f"  Cleared existing tab '{new_title}'")
        else:
            new_ws = spreadsheet.add_worksheet(title=new_title, rows=max(new_count + 1, 10), cols=len(header))
            print(f"  Created new tab '{new_title}'")

        # Write header + data
        cleaned_header = [clean_value(h) for h in header]
        all_data = [cleaned_header] + new_rows
        if all_data:
            new_ws.update(range_name="A1", values=all_data)
            print(f"  Wrote {len(all_data)} rows (1 header + {new_count} data)")

    print("\nDone!")


if __name__ == "__main__":
    main()
