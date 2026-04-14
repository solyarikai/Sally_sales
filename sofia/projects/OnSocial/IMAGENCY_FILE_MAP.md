# IMAGENCY File Map

> Last updated: 2026-04-06

## Sequences (v5 — current)

```
sofia/projects/OnSocial/hub/smartlead_hub/sequences/
├── v5_imagency_founders.md       — Founders/C-Suite (Pain→Proof→Exit), 292 leads
├── v5_imagency_creative.md       — Creative Leadership (139 leads)
└── v5_imagency_account_ops.md    — Account/Ops — largest segment (876 leads)
```

## SmartLead-ready CSVs (Hetzner: /tmp/smartlead_ready/)

```
/tmp/smartlead_ready/
├── imagency_founders_smartlead.csv       — 348 leads (email, first_name, last_name, company_name, custom1-4)
├── imagency_creative_smartlead.csv       — 141 leads
├── imagency_account_ops_smartlead.csv    — 898 leads
└── imagency_excluded_getsales.csv        — 134 excluded → GetSales LinkedIn
```

## Master Data (Hetzner: /tmp/)

```
/tmp/
├── imagency_final_enriched.csv           — 1521 leads, all fields + hq_country + dm_cluster
└── imagency_new_80_enriched.csv          — 80 new leads (merged into final)
```

## Scripts

```
sofia/scripts/
├── build_smartlead_csvs.py                              — Builds 3 CSVs from enriched (geo → custom1-4)
├── segment_new_leads_2026-04-06.py                      — Segments new leads from Google Sheets
├── onsocial_clay_imagency_v4_allgeo_2026-03-31.py       — Full pipeline (Clay→Apollo→Findymail→SmartLead)
├── deploy_imagency_campaigns.py                         — Creates 3 campaigns in SmartLead
├── enrich_imagency_company_hq.py                        — Company HQ geo enrichment
├── gs_imagency_allgeo_sequences.py                      — Syncs sequences to Google Sheets
└── smartlead_imagency_*.py                              — Utilities (replies, check, fix signature, list)
```

## Reports & Docs

```
sofia/projects/OnSocial/reports/
└── IMAGENCY_EUROPE_SEGMENTATION_2026-04-03.md   — Full analysis (DM clusters, geo, pain points)

.claude/projects/OnSocial/
├── campaigns.md, sequences.md, market.md, decisions.md
```

## Google Sheets

| Sheet | ID | Contents |
|-------|----|----------|
| OS \| Leads \| IMAGENCY — 2026-03-28 | `1HrYSGsi43EwcybPz5BhVyM18tXwc3H3fFSZHck4kqeE` | New batch (552 leads, 80 → IMAGENCY) |
| OS \| Leads \| IMAGENCY_NEW — 2026-04-06 | `100ZO60fyQwxq6QK-BAt7lTK8weG-v3nAc6mjKewgibU` | 80 filtered IMAGENCY leads |
| OS \| Leads \| INFPLAT_NEW — 2026-04-06 | `1c92Fsgl7-CF-s-ZW8tSHeGDKQYTnaYMN-HYoy2v0Svo` | 90 INFPLAT (separate segment) |
| OnSocial <> Sally (master) | `1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E` | Sequences, variants |

## Flow

```
enriched.csv → build_smartlead_csvs.py → 3 CSVs → SmartLead (lead upload)
v5_imagency_*.md → SmartLead (sequence copy, manual or via deploy script)
excluded → GetSales LinkedIn outreach
```
