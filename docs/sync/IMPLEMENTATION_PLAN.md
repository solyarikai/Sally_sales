# Sync & Pipeline — Implementation Plan

## 1. SmartLead sync: detect changed campaigns via analytics endpoint

**Problem:** SmartLead API `lead_count` on campaign list is broken (returns 0). Current diff check compares our own DB numbers which are always equal after sync — so it never detects changes.

**Solution:** Before CSV export, call `GET /campaigns/{id}/analytics` for each campaign. Returns `campaign_lead_stats.total` — the real lead count. Compare with `synced_leads_count` in DB. Only export CSV for campaigns where count differs.

**Cost:** 1 lightweight API call per campaign (~0.5s each). 152 campaigns = ~76 seconds for the check. Then only export the 5-20 that actually changed.

**Implementation:**
- In `sync_contacts_global()`, after getting `sl_campaigns`:
  - For each campaign, call `smartlead_service.get_campaign_analytics(external_id)`
  - Extract `campaign_lead_stats.total`
  - Update `campaign.leads_count` with the real number
  - Only add to `needs_sync` if `leads_count != synced_leads_count`
- Parallel analytics calls (5 concurrent) to speed up the check phase
