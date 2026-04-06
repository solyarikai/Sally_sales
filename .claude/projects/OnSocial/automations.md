---
last_updated: 2026-04-07
status: active
---

# OnSocial — Automations & Pipeline

## End-to-End Pipeline

```
Company Search (Apollo/Clay) → Contact Enrichment (Apollo People/Findymail)
  → Dedup & Blacklist Check → SmartLead Upload → Email Campaign
  → No-email contacts → GetSales Export → LinkedIn Campaign
```

## Tools & Their Roles

| Tool | Role | Notes |
|------|------|-------|
| **Apollo** | Company + people search | Internal API via Puppeteer, 4 search methods, `--mode apollo` in universal pipeline |
| **Clay** | Company search + lookalike | Semantic AI search, Ocean.io lookalike, ICP text descriptions |
| **Findymail** | Email enrichment | Finds emails for Apollo/Clay contacts |
| **SmartLead** | Email campaigns | 750/day capacity (expanding to 1,500). No API activation — manual only |
| **GetSales** | LinkedIn automation | 30-step flows, 49-column CSV import, auto-export for no-email contacts |
| **Google Sheets** | Data tracking | OAuth2 (python3.11), dual-save rule (CSV + GSheets), protected sheets |
| **magnum-opus** | Backend system | FastAPI + PostgreSQL, campaign intelligence, gathering pipeline |

## Key Scripts

### Data Pipeline
- `universal_pipeline.py` — main pipeline orchestrator
- `GOD_pipeline_onsocial_restored.py` — OnSocial-specific full pipeline

### Company Search → Contacts
- `onsocial_apollo_infplatforms_allgeo_2026-03-31.py` — Apollo search for INFPLAT
- `onsocial_clay_infplat_v4_allgeo_2026-03-31.py` — Clay search for INFPLAT
- `onsocial_clay_imagency_v4_allgeo_2026-03-31.py` — Clay search for IMAGENCY
- `onsocial_clay_affperf_v4_allgeo_2026-03-31.py` — Clay search for AFFPERF
- `targets_to_contacts.py` — convert company targets to contact list

### Enrichment & Upload
- `findymail_to_smartlead.py` — enrich emails + upload to SmartLead (+ GetSales export for no-email)
- `onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py` — Clay enrichment → SmartLead
- `upload_to_smartlead.py` — direct upload to SmartLead
- `enrich_imagency_company_hq.py` — Apollo HQ enrichment for IMAGENCY
- `build_smartlead_csvs.py` — maps enriched CSV → 3 SmartLead CSVs (founders/creative/account_ops) with geo custom fields. GEO_FIELDS updated April 2026 with corrected social proof values (no "teams like" prefix)
- `segment_new_leads_2026-04-06.py` — classifies new lead batch from Google Sheets into IMAGENCY/INFPLAT/OTHER segments

### GetSales (LinkedIn)
- `getsales_export_leads.py` — export leads for GetSales
- `getsales_dedup_check.py` — dedup against existing GetSales contacts
- `getsales_dump_contacts.py` — dump current GetSales contacts
- `getsales_fix_linkedin_id.py` / `getsales_update_linkedin_id.py` — fix LinkedIn IDs

### Analytics & Maintenance
- `smartlead_ab_analysis_v2.py` — A/B test analysis
- `export_score_campaigns.py` — campaign scoring
- `sync_leads_to_booking_sheet.py` — sync leads to booking tracking
- `enrich_not_interested_sheet.py` — enrich negative responses for analysis
- `cleanup.py` — data cleanup utilities

### Sync & Automation
- `leads_to_blacklist_sync.gs` — Google Apps Script: auto-sync leads to blacklist
- `auto-sync.sh` / `watch-sync.sh` — auto-sync shell scripts

## Apollo Search Details

4 метода поиска (см. reference_apollo_company_search.md):
1. `q_organization_keyword_tags` — основной, keyword-based
2. Company domain search — по списку доменов
3. People search with org filters
4. Lookalike search

Фильтры v4: расширенные keywords (30+ для INFPLAT), ALL GEO, unified management levels. Dedup обязателен vs v3 exports (~40-50% net-new).

## Execution Environment

- **Все скрипты запускаются на Hetzner** (не локально)
- SSH: `ssh hetzner`, repo path: `~/magnum-opus-project/repo`
- DB: PostgreSQL в Docker (`leadgen-postgres`)
- sofia/ scripts не на Hetzner по умолчанию — SCP перед запуском
- Python: `python3.11` для Google API скриптов (локально)

## Capacity & Operational Notes

- SmartLead: 750 emails/day → expanding to 1,500 by April 2026
- 28,427 leads queued = 38 days at current capacity
- Tiered sending: T1 (500/day), T2 (200/day), T3 testing (50/day)
- Auto-pause rule: 500 emails sent with 0 replies → pause
- Known bugs: `sl_reply_count = 0` in some campaigns, GetSales API not integrated, metadata empty in some records

## Blacklist & Dedup

- Blacklist in Google Sheets: `OS | Ops | Blacklist`
- Exclusion list for Apollo: `OS | Ops | Exclusion List — Apollo`
- Competitors blacklisted: HypeAuditor, Modash, GRIN
- Cross-segment exclusions: negative responders, active pipeline
- 25-company manual sample check required before launch (70%+ match rate)
