# Google Drive & Sheets Integration

Google Drive and Sheets are used for file uploads (exporting results as Google Sheets) and reply logging.

---

## Service Account

The project uses a **Google Cloud Service Account** (not a personal API key) for authentication.

| Field | Value |
|-------|-------|
| Project | `autoreplies010226` |
| Service account email | `autoreplies@autoreplies010226.iam.gserviceaccount.com` |
| Scope | `https://www.googleapis.com/auth/drive` (full Drive access) |
| Shared Drive ID | `0AEvTjlJFlWnZUk9PVA` |

---

## Credentials File

The service account JSON key is stored at the **repo root**:

```
magnum-opus/
├── google-credentials.json    <-- service account key (gitignored)
├── backend/
│   ├── .env                   <-- references ../google-credentials.json
│   └── app/
│       └── services/
│           ├── google_drive_service.py
│           └── google_sheets_service.py
```

---

## Environment Variables

Set in `backend/.env`:

```bash
# Path to the service account JSON key (relative to backend/)
GOOGLE_APPLICATION_CREDENTIALS=../google-credentials.json

# Optional: email to impersonate (not currently used in code)
GOOGLE_IMPERSONATE_EMAIL=services@getsally.io

# Shared Drive where files are uploaded (optional — defaults to service account's My Drive)
SHARED_DRIVE_ID=0AEvTjlJFlWnZUk9PVA
```

### Alternative: inline JSON

Instead of a file path, you can paste the entire JSON key as a string:

```bash
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"autoreplies010226",...}
```

**Priority order** (in `google_drive_service.py`):
1. `GOOGLE_SERVICE_ACCOUNT_JSON` — parsed as inline JSON string
2. `GOOGLE_APPLICATION_CREDENTIALS` — loaded from file path

---

## How It Works

### Initialization (`google_drive_service.py`)

1. `_initialize()` reads credentials from env vars (JSON string or file path).
2. Creates `service_account.Credentials` with `drive` scope.
3. Builds a `drive v3` API client via `googleapiclient.discovery.build`.
4. The service is a **lazy singleton** — initialized on first use.

### Upload Flow

1. File is uploaded via API endpoint (`POST /api/drive/upload`).
2. Saved to a temp file on disk.
3. `google_drive_service.upload_file()` uploads to Google Drive:
   - Office files are converted to Google format by default (xlsx → Sheets, docx → Docs, etc.).
   - Uploaded to the Shared Drive if `SHARED_DRIVE_ID` is set.
4. Permissions are set to **"anyone with link can view"**.
5. A public view URL is returned.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/drive/status` | GET | Check if Drive integration is configured |
| `/api/drive/upload` | POST | Upload any supported file (xlsx, csv, docx, pdf, etc.) |
| `/api/drive/upload-xlsx` | POST | Upload xlsx and convert to Google Sheets |

### Supported File Types

| Extension | Converts to |
|-----------|------------|
| `.xlsx`, `.xls`, `.csv` | Google Sheets |
| `.docx`, `.doc` | Google Docs |
| `.pptx`, `.ppt` | Google Slides |
| `.pdf` | PDF (no conversion) |

---

## Setup from Scratch

If you need to create a new service account:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → select project `autoreplies010226`.
2. Navigate to **IAM & Admin → Service Accounts**.
3. Create a new service account (or use existing `autoreplies@autoreplies010226.iam.gserviceaccount.com`).
4. Click the service account → **Keys** → **Add Key** → **Create new key** → JSON.
5. Save the downloaded JSON file as `google-credentials.json` at the repo root.
6. Make sure **Google Drive API** is enabled: APIs & Services → Library → search "Google Drive API" → Enable.
7. If using a Shared Drive, add the service account email as a member of that Shared Drive (Contributor or above).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Google Drive not configured" (503) | Check that `google-credentials.json` exists and the path in `.env` is correct |
| "Failed to initialize Google Drive service" | Verify the JSON key is valid and not expired; re-download from Google Cloud Console |
| Upload succeeds but file not visible | Check the `SHARED_DRIVE_ID` is correct and the service account has access to that Shared Drive |
| Permission errors on Shared Drive | Add `autoreplies@autoreplies010226.iam.gserviceaccount.com` as a member of the Shared Drive |


