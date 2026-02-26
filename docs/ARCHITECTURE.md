# Architecture Reference

Single source of truth for system architecture. Updated Feb 2026.

---

## System Overview

Lead generation and outreach automation platform with:
- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL
- **Frontend**: React + TypeScript + Vite
- **Deployment**: Docker Compose on Hetzner, volume-mounted source code
- **Integrations**: SmartLead (email), GetSales (LinkedIn), Telegram (notifications)

---

## Scheduler Architecture

The CRM scheduler (`crm_scheduler.py`) is a singleton started in `main.py` lifespan. It manages all background tasks:

```
CRM Scheduler
  ├── _run_loop()                    — Full CRM sync every 30 min
  ├── _run_reply_loop()              — Reply polling, adaptive 3–10 min
  │     ├── sync_smartlead_replies()   (email)
  │     ├── sync_getsales_replies()    (LinkedIn)
  │     └── _auto_assign_new_campaigns() (every 6th run)
  ├── _run_webhook_loop()            — Webhook registration every 1 hour (5 min on failure)
  ├── _run_event_recovery_loop()     — Failed event retry every 5 min
  ├── _run_conversation_sync_loop()  — replied_externally detection every 3 min
  ├── _run_telegram_poll_loop()      — Telegram bot long-poll every 5 sec
  ├── _run_report_loop()             — Telegram digest every 4 hours
  ├── _run_prompt_refresh_loop()     — Prompt template refresh weekly
  ├── _run_sheet_sync_loop()         — Google Sheets sync every 5 min
  └── _run_watchdog()                — Health monitoring every 60 sec, resurrects dead tasks
```

---

## Reply Pipeline

### How replies arrive

1. **SmartLead Webhooks** (primary, real-time, ~5s latency)
   - SmartLead fires webhook → `POST /api/smartlead/webhook`
   - Handler: `smartlead.py:receive_webhook()`
   - Dedup via `WebhookEventModel` table + in-memory bounded cache
   - Classify (GPT-4o-mini) → Generate draft → Create `ProcessedReply`
   - Notify via Telegram (per-project routing)

2. **SmartLead Polling** (fallback, 3–10 min latency)
   - `crm_scheduler._run_reply_loop()` → `crm_sync_service.sync_smartlead_replies()`
   - Uses `GET /campaigns/{id}/statistics` (paginated)
   - Adaptive interval: fast (3 min) during startup or webhook failure, slow (10 min) steady state

3. **GetSales LinkedIn** (webhook + polling)
   - Webhook: `POST /api/crm-sync/webhook/getsales` → `crm_sync.py:getsales_webhook()`
   - Polling fallback: `crm_sync_service.sync_getsales_replies()`
   - Source="getsales", channel="linkedin"

### Webhook endpoints (canonical, single source of truth)

| Endpoint | Handler | Purpose |
|----------|---------|---------|
| `POST /api/smartlead/webhook` | `smartlead.py:receive_webhook()` | SmartLead email events |
| `POST /api/crm-sync/webhook/getsales` | `crm_sync.py:getsales_webhook()` | GetSales LinkedIn events |
| `POST /api/crm-sync/webhook/getsales/bulk-import` | `crm_sync.py:getsales_bulk_import_webhook()` | GetSales bulk contact import |

All webhooks support optional token authentication via `?token=<WEBHOOK_SECRET>` query parameter.

### Webhook registration

Managed centrally by `setup_crm_webhooks_on_startup()` in `crm_scheduler.py`. Called:
- On startup (once)
- Every hour by `_run_webhook_loop()` (safety net)
- After auto-assign discovers new campaigns

**Never register webhooks from API endpoints or other services.** The `POST /api/crm-sync/setup-webhooks` endpoint delegates to the same central function.

---

## Key Data Models

### ProcessedReply (central reply record)

| Field | Type | Notes |
|-------|------|-------|
| lead_email | str | Unique with campaign_id |
| campaign_id | int | SmartLead campaign |
| category | str | GPT classification (13 categories) |
| approval_status | str | NULL → pending → approved/dismissed/replied_externally |
| source | str | smartlead / getsales |
| channel | str | email / linkedin |
| draft_reply | text | AI-generated draft |

### WebhookEventModel (event log + recovery)

Stores raw webhook payloads. Recovery loop retries failed events with exponential backoff (5min → 15min → 45min → 2h → 6h, max 5 retries).

### Project (saved filter preset)

Links campaigns to business units via `campaign_filters` (list of campaign name prefixes). `webhooks_enabled` controls whether webhooks are registered for this project's campaigns.

---

## Shared Utilities

Shared normalization functions live in `app/utils/normalization.py`:
- `normalize_email()` — lowercase + strip
- `normalize_linkedin_url()` — extract handle from any LinkedIn URL format
- `calculate_name_similarity()` — SequenceMatcher ratio
- `truncate()` — safe string truncation

**Import from here. Do not duplicate these functions.**

---

## Concurrency Safety

| Resource | Protection | File |
|----------|-----------|------|
| `_project_cache` | `asyncio.Lock` | `notification_service.py` |
| `_verified_webhooks` | Bounded TTL dict (max 2000, 1h TTL) | `crm_sync_service.py` |
| SmartLead API | `asyncio.Semaphore` in sync loops | `crm_scheduler.py` |

---

## Deployment

```
Server: Hetzner (ssh hetzner)
Path:   ~/magnum-opus-project/repo
Stack:  Docker Compose (v1)

Containers:
  leadgen-backend   — FastAPI app, volume-mounted from repo/backend → /app
  leadgen-postgres   — PostgreSQL
  redis              — Redis (caching, dedup)
  leadgen-frontend   — Nginx serving built frontend
```

### Deploy procedure

```bash
ssh hetzner
cd ~/magnum-opus-project/repo
git pull
docker restart leadgen-backend

# Frontend (if changed):
cd frontend
npm install && npm run build
docker restart leadgen-frontend
```

### Running scripts

```bash
docker exec -w /app -e PYTHONPATH=/app leadgen-backend python3 scripts/<script>.py
```

---

## Architecture Decisions (why things are this way)

1. **Single webhook handler per service** — SmartLead webhooks go to `smartlead.py`, GetSales to `crm_sync.py`. No duplicates.

2. **Centralized webhook registration** — All webhook URLs are registered by `setup_crm_webhooks_on_startup()` only. API endpoints delegate to it.

3. **Adaptive polling** — Reply polling starts fast (3 min) and slows to 10 min when webhooks are healthy. This prevents both stale data and API waste.

4. **Webhook health monitoring** — If no webhook events arrive in 15 min, the system assumes webhooks are broken and switches to fast polling.

5. **Event recovery** — Raw webhook payloads are stored in `webhook_events` table. A recovery loop retries failed events with exponential backoff. No data loss even if processing fails.

6. **Project-campaign mapping** — Projects define campaign name prefixes in `campaign_filters`. The scheduler auto-discovers new campaigns matching these prefixes and assigns them.

---

## File Map (key files only)

```
backend/
  app/
    api/
      smartlead.py         — SmartLead webhook handler + API endpoints
      crm_sync.py          — GetSales webhooks + CRM sync API
      replies.py           — Reply management API (list, approve, send)
    services/
      crm_scheduler.py     — Background scheduler (all loops)
      crm_sync_service.py  — SmartLead/GetSales API clients + sync logic
      notification_service.py — Telegram notifications + project routing
      reply_processor.py   — GPT classification + draft generation
    models/
      contact.py           — Contact, Project, ProcessedReply, etc.
    utils/
      normalization.py     — Shared email/LinkedIn/name normalization
    core/
      config.py            — All settings (Pydantic BaseSettings)

frontend/
  src/
    pages/
      TasksPage.tsx        — Main reply management UI
      HomePage.tsx          — Dashboard
    api/
      index.ts             — API client
      tasks.ts             — Reply/task API calls
```

---

## Common Mistakes to Avoid

1. **Do not create duplicate webhook handlers.** Check existing endpoints before adding new ones.
2. **Do not hardcode webhook URLs in API endpoints.** Use `setup_crm_webhooks_on_startup()`.
3. **Do not duplicate normalization functions.** Import from `app.utils.normalization`.
4. **Do not store credentials in docs or code.** Use `.env` file only.
5. **Do not create unbounded caches.** Use TTL + max-size limits.
6. **Do not skip `asyncio.Lock` for shared mutable state** in concurrent loops.
7. **After git pull on server, restart the container** — Python caches imported modules.
