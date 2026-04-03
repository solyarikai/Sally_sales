# IMAGENCY Europe — DM Segmentation Report

**Date:** 2026-04-03
**Source:** OS_Leads_IMAGENCY-EUROPE_20260403_1658.csv
**Total leads:** 1,441

## Goal
Split leads by DM role clusters + company HQ geo -> unique SmartLead campaigns with tailored sequences per group.

## Decisions Log

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Which leads? | All 1,441 (incl. STARTED/INPROGRESS) | Re-segment and relaunch |
| 2 | How many campaigns? | 3 | Founders vs Creative Leadership vs Account/Ops |
| 3 | Art Directors/Copywriters? | Exclude from email (~105 leads) | Not DMs for SaaS purchases; route to GetSales LinkedIn |
| 4 | Geo source? | Apollo Company Enrichment | Person location != company HQ |
| 5 | Enrichment method | Apollo /mixed_companies/api_search by company name | Free, ~95% accuracy |

## Pipeline Checkpoints

- [ ] **CP1** — Extract unique companies from CSV
- [ ] **CP2** — Apollo enrichment: company name -> HQ country/city
- [ ] **CP3** — Match rate analysis (how many matched?)
- [ ] **CP4** — Geo distribution of companies (actual vs person-location)
- [ ] **CP5** — Final segment matrix: 3 role clusters x geo clusters
- [ ] **CP6** — Deep research: pains per cluster
- [ ] **CP7** — Sequence drafts per campaign
- [ ] **CP8** — SmartLead campaign creation + lead upload

## CP1 — Unique Companies

Pending enrichment script run.

## CP2 — Apollo Enrichment

Script: `sofia/scripts/enrich_imagency_company_hq.py`
Method: For each unique company_name, search Apollo by `q_organization_name` (exact) with fallback to `q_organization_keyword_tags`.
Rate: 0.3s/call, ~900 companies = ~5 min.
Cost: FREE (search endpoint, no credits).

## CP3-CP8

Pending.
