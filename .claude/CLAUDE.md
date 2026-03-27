# Sales Engineer — Shared Instructions

This CLAUDE.md applies to ALL projects under sales_engineer/ (magnum-opus, sofia, scripts, etc.).

## Google Sheets — READ & WRITE

**Use the `google-sheets` MCP server for ALL Google Sheets operations.** This is an OAuth2 MCP server with the user's own credentials — full access to all their sheets.

**NEVER use service account / Docker for Google Sheets.** Always use the MCP tools.

### When to use

- **Reading** a Google Sheet by URL or ID (e.g., user shares a link)
- **Creating** a new sheet with data
- **Writing/appending** rows to an existing sheet
- **Searching** across sheets
- Any other Google Sheets operation

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

## Project Structure

| Directory | What |
|-----------|------|
| `magnum-opus/` | Backend (FastAPI + SQLAlchemy), gathering pipeline, API |
| `sofia/` | Sales ops: scripts, sequences, research, projects |
| `sofia/projects/OnSocial/` | OnSocial-specific sequences, docs, segments |
| `sofia/smartlead-hub/` | SmartLead campaigns, sequences, lead data |
