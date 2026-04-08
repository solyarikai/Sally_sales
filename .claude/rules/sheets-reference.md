# Google Sheets — Naming & Protected Sheets

## Naming Convention

All data exports saved BOTH locally and to Google Sheets with identical names.

Formula: `[PROJECT] | [TYPE] | [SEGMENT] — [DATE]`

| Field | Values |
|-------|--------|
| PROJECT | `OS` (OnSocial), `Sally` (internal), `Ops` (shared) |
| TYPE | `Leads` (campaign-ready), `Targets` (pre-enrichment), `Import` (raw exports), `Archive` (historical), `Analytics` (audits), `Ops` (operational) |
| SEGMENT | `INFPLAT` (Influencer Platforms), `IMAGENCY` (IM-First Agencies), `AFFPERF` (Affiliate Performance), `SOCCOM` (Social Commerce) |
| DATE | `YYYY-MM-DD` |

**Examples:**
- Google Sheets: `OS | Targets | INFPLAT — 2026-03-27`
- Local file:    `OS_Targets_INFPLAT_2026-03-27.csv`

Local filenames: replace ` | ` -> `_`, ` — ` -> `_`, spaces -> `_`. No spaces in local filenames.

## Protected Sheets (DO NOT rename or overwrite)

| Name | Sheet ID |
|------|----------|
| OnSocial <> Sally | `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E` |
| OS \| Ops \| Blacklist | `1drDBlOBr_BEeYd0Fv5292IbAfdTApLgITOht6PZHCU4` |
| OS \| Leads \| All | `1Jia8Sor5V2cby3sORXZxuaSvM_vgWB-uMdazK6RZ5wA` |
| OS \| Ops \| Exclusion List — Apollo | `1O2xy9Huo0uaCErTq5Er_6xj0PQv8AXZc_DWC13einn8` |
| OS \| Ops \| Daily | `1c0PpKPsZfxbPYUPTqEyVPfKPOffExwLhrCOUDk3-RKA` |
| Infra (Accounts) | `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg` |
