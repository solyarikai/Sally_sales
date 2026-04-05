# Sales Engineer — Shared Instructions

This CLAUDE.md applies to ALL projects under sales_engineer/ (magnum-opus, sofia, scripts, etc.).

## Google Sheets & Drive — MCP Server (25 tools)

**Google Sheets + Drive MCP server is connected** via `.claude/mcp.json` → `google-sheets`.
- Server: `.claude/mcp/google-sheets/server.py`
- Scopes: `spreadsheets` + `drive` (full, NOT `drive.readonly`)
- Auth: OAuth2 credentials from `.claude/mcp/google-sheets/token.json`

### Available MCP Tools

**Sheets — Data (8 tools):**
- `sheets_read_range` — read cells (supports as_json mode)
- `sheets_write_range` — write/overwrite cells
- `sheets_append_rows` — append rows after last filled row
- `sheets_search` — search text across sheet/tab
- `sheets_clear_range` — clear values in range
- `sheets_list_sheets` — list tabs in a spreadsheet
- `sheets_list_my_spreadsheets` — find spreadsheets by name
- `sheets_create_spreadsheet` — create new spreadsheet

**Sheets — Structure (8 tools):**
- `sheets_add_tab` / `sheets_delete_tab` / `sheets_rename_tab` / `sheets_duplicate_tab` — manage tabs
- `sheets_get_metadata` / `sheets_update_metadata` — title, locale, timezone
- `sheets_sort_range` — sort by column
- `sheets_auto_resize` — auto-fit column widths
- `sheets_format_range` — bold, background color

**Drive (9 tools):**
- `drive_create_folder` — create folder
- `drive_move_file` — move file to folder (for Dual Save Rule)
- `drive_list_folder` — list folder contents
- `drive_search_files` — search files by name
- `drive_get_file_info` — file metadata
- `drive_delete_file` — trash file (recoverable)
- `drive_share_file` — share with email
- `drive_copy_file` — copy file

**Always use MCP tools instead of writing Python scripts for Google Sheets/Drive operations.**
Fallback to Python only for unsupported operations (conditional formatting, charts, etc.).

**NEVER use service account / Docker for Google Sheets.**

### Naming Convention

**All data exports must be saved BOTH locally and to Google Sheets with identical names.**

Formula: `[PROJECT] | [TYPE] | [SEGMENT] — [DATE]`

| Field | Values |
|-------|--------|
| PROJECT | `OS` (OnSocial), `Sally` (internal), `Ops` (shared) |
| TYPE | `Leads` (campaign-ready), `Targets` (pre-enrichment), `Import` (raw exports), `Archive` (historical), `Analytics` (audits), `Ops` (operational) |
| SEGMENT | `INFPLAT` (Influencer Platforms), `IMAGENCY` (IM-First Agencies), `AFFPERF` (Affiliate Performance) |
| DATE | `YYYY-MM-DD` |

**Examples:**
- Google Sheets: `OS | Targets | INFPLAT — 2026-03-27`
- Local file:    `OS_Targets_INFPLAT_2026-03-27.csv`

Local filenames: replace ` | ` → `_`, ` — ` → `_`, spaces → `_`. No spaces in local filenames.

### Dual Save Rule

Every time data is saved to a CSV locally, it MUST also be uploaded to Google Sheets with the same name (per naming convention). Every time data is read from Google Sheets, save a local copy too.

### Protected Sheets (DO NOT rename or overwrite)

| Name | Sheet ID |
|------|----------|
| OnSocial <> Sally | `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E` |
| OS \| Ops \| Blacklist | `1drDBlOBr_BEeYd0Fv5292IbAfdTApLgITOht6PZHCU4` |
| OS \| Leads \| All | `1Jia8Sor5V2cby3sORXZxuaSvM_vgWB-uMdazK6RZ5wA` |
| OS \| Ops \| Exclusion List — Apollo | `1O2xy9Huo0uaCErTq5Er_6xj0PQv8AXZc_DWC13einn8` |
| OS \| Ops \| Daily | `1c0PpKPsZfxbPYUPTqEyVPfKPOffExwLhrCOUDk3-RKA` |
| Infra (Accounts) | `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg` |

## Execution Environment — Hetzner

- **All scripts, DB queries, scrapers run on Hetzner.** Local machine is for code editing only.
- SSH: `ssh hetzner` (host alias in ~/.ssh/config)
- DB: `ssh hetzner "docker exec leadgen-postgres psql -U leadgen -d leadgen -c 'SQL'"`
- Backend container: `leadgen-backend` (FastAPI on port 8000)
- Deploy: `ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main && docker-compose up --build -d"`
- Env vars: `set -a && source .env && set +a` before running Python scripts directly
- **sofia/ scripts are NOT on Hetzner by default.** SCP script + dependencies (sequences/) before running: `scp sofia/scripts/foo.py hetzner:~/magnum-opus-project/repo/sofia/scripts/`
- Hetzner repo path: `~/magnum-opus-project/repo`

## SmartLead - Formatting Rules

When writing email sequences (markdown files or GOD_SEQUENCE):
- **No em dashes** (`—`). Use regular dash (`-`). Em dashes break in some email clients.
- **Line breaks**: SmartLead API ignores `\n`. Use `<br>` for line breaks, `<br><br>` for paragraph breaks.
- Pipeline scripts auto-convert `\n` → `<br>` and `—` → `-` when uploading, but markdown source files should be clean.
- **A/B variants**: SmartLead API doesn't support variants. Add B variants manually in SmartLead UI.
- **Activation**: NEVER activate campaigns via API. Only manually in SmartLead UI.

## GetSales Export

Contacts without email from Findymail → auto-export to GetSales-ready CSV in `sofia/get_sales_hub/{dd_mm}/`.
- 49 columns matching GetSales import format (full_name, first_name, last_name, position, linkedin_nickname, linkedin_url, company_name, cf_location, list_name, tags, etc.)
- Built into both `findymail_to_smartlead.py` and `onsocial_clay_to_smartlead...py`

## Local Python

- Use `python3.11` (homebrew) for local scripts — has google-auth, google-api-python-client installed
- System `python3` (3.9) lacks most dependencies and has no write access to site-packages

## Project Structure

| Directory | What |
|-----------|------|
| `magnum-opus/` | Backend (FastAPI + SQLAlchemy), gathering pipeline, API — **GIT SUBMODULE** |
| `sofia/` | Sales ops: scripts, sequences, research, projects |
| `sofia/projects/OnSocial/` | OnSocial-specific sequences, docs, segments |
| `sofia/smartlead-hub/` | SmartLead campaigns, sequences, lead data |
| `tam-guide/` | Training/onboarding materials (HTML lessons) |
| `scripts/` | Shared utility scripts |
| `.claude/mcp/` | All MCP servers (apollo, crona, google-sheets, smartlead, findymail, getsales, transkriptor) |
| `.claude/skills/` | Shared Claude Code skills |

## Git Structure

- **Parent repo** (`sales_engineer/`): GitHub
- **Submodule** (`magnum-opus/`): GitLab (`git@gitlab.com:sally-saas/magnum-opus.git`)
- Always push submodule FIRST, then parent
- Always check `git submodule status` before git operations
- API keys are per-project (OnSocial, TAM, etc.) — never change globally
