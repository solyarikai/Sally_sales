# SmartLead Sync Optimization — Progress Log

**Started:** 2026-02-12 23:45
**Branch:** `datamodel`
**Status:** Deployed, waiting for SmartLead rate limit (429) to cool down before verifying reply sync

---

## What was done

### 1. Fixed campaigns field double-encoding (COMPLETED)

**Root cause:** 7 code paths used `json.dumps()` before assigning to the `campaigns` JSON column, causing double-encoded strings (`"[{...}]"` instead of `[{...}]`). This broke all read paths that called `.get()` on campaign entries — they got characters instead of dicts.

**Changes:**
- Created `parse_campaigns()` helper in `crm_sync_service.py` — normalizes any format (None, list, string, double-encoded) to a list of dicts
- Removed `json.dumps()` from all 7 write paths:
  - `crm_sync.py` (4 locations — SmartLead webhook, GetSales webhook, new contact creation)
  - `smartlead.py` (1 — webhook handler new contact)
  - `reply_processor.py` (1 — new contact from reply)
- Added `parse_campaigns()` to all 12+ read paths:
  - `crm_sync_service.py` (3 — `get_getsales_flow_name`, SmartLead merge, GetSales merge)
  - `crm_sync.py` (2 — SmartLead/GetSales webhook campaign merge)
  - `contacts.py` (2 — campaigns list, status update)
  - `replies.py` (2 — campaign_id resolution for sending)
  - `search.py` (1 — domain search results)
  - `project_service.py` (1 — campaign name extraction)
- **SQL migration:** Fixed 10,300 corrupted rows in DB: `UPDATE contacts SET campaigns = (campaigns #>> '{}')::jsonb WHERE ...`
- **Verification:** 88,203 contacts now have `json_typeof(campaigns) = 'array'`, zero `string` type remaining

**Commits:**
- `858abe5` — fix: normalize campaigns field to prevent double-encoded JSON strings

### 2. Optimized SmartLead reply sync (COMPLETED, PENDING VERIFICATION)

**Problem:** `sync_smartlead_replies` made `GET /leads/?email={email}` API call for EVERY replied lead just to get `lead_id`. With 30+ campaigns and 50+ replies each, that's 1500+ unnecessary API calls per sync, hammering SmartLead's rate limit (10 req/2s).

**Changes:**
- **Local DB lookup first:** Look up `lead_id` from `contacts.smartlead_id` — instant, no API call
- **Statistics fallback:** Extract `lead_id` from statistics endpoint response (already fetched)
- **API as last resort:** `GET /leads/?email=` only called if both DB and stats lack lead_id (rare)
- **Shared httpx client:** Reuse single `httpx.AsyncClient` for all message-history fetches instead of creating one per call
- **Tracking stats:** Added `lead_id_from_db`, `lead_id_from_stats`, `lead_id_from_api` counters to log where lead_id came from

**Files modified:**
- `backend/app/services/crm_sync_service.py` — refactored `sync_smartlead_replies` enrichment section
- `backend/app/services/smartlead_service.py` — added `lead_id` to statistics response, added `get_email_thread_with_client()` method

**Commits:**
- `0ce1ac9` — perf: eliminate per-lead API call in SmartLead reply sync

---

## Current blocker

SmartLead API is returning **429 Too Many Requests** on the campaigns list endpoint (`GET /campaigns`). This is the very first call in both `sync_smartlead_contacts` and `sync_smartlead_replies`, so the entire sync fails before reaching any of the optimized code.

The 429s are caused by the `crm_scheduler` also hitting SmartLead API concurrently (webhook checks, campaign auto-assign). The rate limit is **10 requests per 2 seconds**.

## Next steps

1. **Wait for rate limit to cool down** (SmartLead 429s are temporary, typically clear within a few minutes of reduced traffic)
2. **Trigger sync again:**
   ```bash
   # Clear lock first
   ssh hetzner "docker exec leadgen-backend python -c \"
   import redis, os
   r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379'))
   r.delete('leadgen:sync_lock')
   print('Lock cleared')
   \""

   # Trigger async sync
   ssh hetzner "curl -s -X POST http://localhost:8000/api/crm-sync/trigger \
     -H 'Content-Type: application/json' \
     -H 'X-Company-ID: 1' \
     -d '{\"sources\": [\"smartlead\"], \"full_sync\": true}'"
   ```
3. **Verify optimization via logs:**
   ```bash
   ssh hetzner "cd ~/magnum-opus-project/repo && docker-compose logs --since=5m backend 2>&1 | grep -iE 'reply sync|lead_id_from'"
   ```
   Expected: `lead_id_from_db` count should be high, `lead_id_from_api` should be 0 or very low
4. **Optional further improvement:** Add retry-with-backoff for 429 errors on the campaigns list endpoint, or stagger the scheduler's SmartLead calls to avoid concurrent rate limit exhaustion

---

## Architecture overview

```
BEFORE (per replied lead = 2 API calls):
  statistics → email → GET /leads/?email= → lead_id → GET /message-history

AFTER (per replied lead = 0-1 API calls):
  statistics → email → DB lookup (contacts.smartlead_id) → lead_id → GET /message-history
                        ↓ (miss)
                        statistics.lead_id
                        ↓ (miss)
                        GET /leads/?email= (last resort)
```

API call reduction: ~50% overall (eliminated all per-lead enrichment calls, kept only message-history).
