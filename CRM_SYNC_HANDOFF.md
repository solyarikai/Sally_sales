# CRM Sync System - Handoff Summary

## Goal
Build a unified CRM view that merges contacts from **Smartlead** (email outreach) and **GetSales** (LinkedIn outreach), with real-time sync via webhooks.

## What's Been Built

### 1. Backend - CRM Sync Service (`backend/app/services/crm_sync_service.py`)
- **SmartleadClient**: API client for Smartlead
  - Fetch campaigns, leads, message history
  - Configure webhooks via API (`/campaigns/{id}/webhooks`)
  - `setup_crm_webhooks(url)` - auto-registers webhooks on all active campaigns

- **GetSalesClient**: API client for GetSales  
  - Fetch lists, flows, leads
  - Webhook management via `/integrations/api/webhooks`
  - `setup_crm_webhooks(url)` - registers webhooks for LinkedIn replies

### 2. Backend - API Endpoints (`backend/app/api/crm_sync.py`)
- `POST /api/crm-sync/trigger` - Start background sync
- `POST /api/crm-sync/sync-now` - Synchronous full sync
- `GET /api/crm-sync/status` - Sync statistics
- `POST /api/crm-sync/setup-webhooks` - Configure webhooks in both platforms
- `GET /api/crm-sync/webhooks` - List configured webhooks
- `POST /api/crm-sync/webhook/smartlead` - Receive Smartlead events (EMAIL_REPLY, LEAD_CATEGORY_UPDATED)
- `POST /api/crm-sync/webhook/getsales` - Receive GetSales events (LinkedIn replies)
- `POST /api/crm-sync/webhook/getsales/bulk-import` - **NEW** Bulk import endpoint for GetSales export
- `GET /api/crm-sync/contacts/{id}/activities` - Activity history for a contact

### 3. Database Models (`backend/app/models/contact.py`)
**Contact model - new fields:**
- `smartlead_id`, `getsales_id` - External system IDs
- `smartlead_status`, `getsales_status` - Status in each platform
- `has_replied`, `last_reply_at`, `reply_channel` - Reply tracking
- `last_synced_at` - Sync timestamp

**ContactActivity model** - Tracks all interactions:
- `activity_type`: email_sent, email_replied, linkedin_sent, linkedin_replied, etc.
- `channel`: email, linkedin, manual
- `source`: smartlead, getsales
- `body`, `snippet`, `subject` - Message content
- `extra_data` - JSON metadata (campaign info, conversation threads)

### 4. Background Scheduler (`backend/app/services/crm_scheduler.py`)
- Runs periodic full sync (configurable interval)
- Auto-registers webhooks on startup

### 5. Database Migration
- `backend/alembic/versions/2fb87aa98654_add_crm_sync_fields_to_contacts.py`
- Run with: `alembic upgrade head`

## Current State

### Contacts in Database
- ~10K from Smartlead
- ~14K from GetSales (from lists only - API has 10K limit per search)
- **217K contacts in GetSales UI not in any list** - can't fetch via API

### Webhooks Configured
1. **GetSales** - `contact_replied_linkedin_message` → `http://46.62.210.24:8000/api/crm-sync/webhook/getsales`
2. **Smartlead** - `EMAIL_REPLY`, `LEAD_CATEGORY_UPDATED` → `http://46.62.210.24:8000/api/crm-sync/webhook/smartlead` (on active campaigns)

## NEXT STEP: Bulk Export 230K GetSales Contacts

Per GetSales support (Peter), use **webhook export** to get all contacts:

### Setup in GetSales UI:
1. **Settings → Webhooks → Create new Webhook**
   - Name: `CRM Bulk Import`
   - Event: `Contact Export (Custom Call)`
   - Target URL: `http://46.62.210.24:8000/api/crm-sync/webhook/getsales/bulk-import`

2. **Contacts → Select All (230,442) → Export → Webhook → Select "CRM Bulk Import" → Confirm**

GetSales will POST each contact to the webhook one by one.

## API Credentials (in `backend/.env`)
```
SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
GETSALES_API_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## Key Files
```
backend/app/api/crm_sync.py          # API endpoints
backend/app/services/crm_sync_service.py  # API clients & sync logic
backend/app/services/crm_scheduler.py     # Background scheduler
backend/app/models/contact.py        # Contact & ContactActivity models
frontend/src/pages/ContactsPage.tsx  # CRM UI
```

## Commands to Verify
```bash
# Check backend health
curl http://46.62.210.24:8000/health

# Check contact count
curl -H "X-Company-ID: 1" "http://46.62.210.24:8000/api/contacts?limit=1"

# Run migration (if needed)
cd backend && alembic upgrade head

# Restart backend
docker-compose restart backend
```

## Frontend Issues Fixed
- `ContactsPage.tsx` - Added defensive `|| []` for filter options that could be undefined
