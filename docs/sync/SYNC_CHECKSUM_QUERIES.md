# CRM ↔ SmartLead/GetSales Sync Checksum Queries

## How to run sync
```bash
ssh hetzner "docker exec leadgen-backend curl -s -X POST 'http://localhost:8000/api/crm-sync/contact-sync/start?phase=full_load' -H 'X-Company-ID: 1'"
```

## Check sync progress
```bash
ssh hetzner "docker exec leadgen-backend curl -s 'http://localhost:8000/api/crm-sync/contact-sync/progress' -H 'X-Company-ID: 1'"
```

## Checksum: CRM total vs last sync date
```sql
SELECT COUNT(*) as total, COUNT(DISTINCT domain) as domains, MAX(created_at)::date as last_synced
FROM contacts WHERE project_id = 9;
```

## Checksum: contacts by source
```sql
SELECT
  CASE WHEN smartlead_id IS NOT NULL THEN 'SmartLead'
       WHEN getsales_id IS NOT NULL THEN 'GetSales'
       ELSE source END as src,
  COUNT(*) as contacts, COUNT(DISTINCT domain) as domains
FROM contacts WHERE project_id = 9
GROUP BY 1 ORDER BY contacts DESC;
```

## SmartLead campaigns: DB leads_count vs CRM contacts
```sql
SELECT c.name, c.status, c.leads_count as smartlead_leads,
  c.created_at::date, c.external_id
FROM campaigns c
WHERE c.project_id = 9 AND c.platform = 'smartlead'
ORDER BY c.created_at DESC;
```

## Check blacklist coverage after sync
```sql
-- Refresh mat view first
REFRESH MATERIALIZED VIEW active_campaign_domains;

-- Compare CRM domains vs mat view
SELECT
  (SELECT COUNT(DISTINCT domain) FROM contacts WHERE project_id=9 AND domain IS NOT NULL AND domain != '') as crm_domains,
  (SELECT COUNT(*) FROM active_campaign_domains WHERE project_id = 9) as matview_domains;
```

## Check target overlap with CRM
```sql
SELECT COUNT(DISTINCT dc.domain) as targets_already_in_crm
FROM discovered_companies dc
JOIN contacts c ON LOWER(c.domain) = LOWER(dc.domain) AND c.project_id = 9
WHERE dc.project_id = 9 AND dc.is_target = true AND dc.domain NOT LIKE '%_apollo_%';
```

## March 20, 2026 — Sync Results

**Before sync:**
- CRM: 114,855 contacts, 55,375 domains
- Last synced: March 15 (5 days stale)
- 83 of 428 targets already in CRM

**Sync in progress:**
- SmartLead: 293,685 processed, 151 new contacts found
- GetSales: pending
