# Follow-Up Architecture

## How Follow-Up Candidates Are Identified

Follow-ups are a **query/view** on existing `ProcessedReply` records — not separate entities.
A reply needs follow-up when: operator sent a message, but lead hasn't responded.

### The Query (`needs_followup=true`)

```sql
WHERE approval_status IN ('approved', 'auto_resolved')  -- operator replied
  AND approved_at < NOW() - INTERVAL '{delay_days} days'  -- enough time passed
  AND parent_reply_id IS NULL                              -- not a follow-up itself
  AND category IN ('meeting_request', 'interested', 'question')  -- actionable only
  AND NOT EXISTS (newer inbound from same lead)            -- lead hasn't replied
  AND NOT EXISTS (follow-up child record)                  -- not already followed up
```

### Two Sources of "Operator Replied"

| Source | Status | Detection Speed |
|--------|--------|----------------|
| **System-sent** (approve-and-send in UI) | `approved` | Instant |
| **External** (operator replied directly in SmartLead/GetSales) | `auto_resolved` | ~3 minutes |

## Detection Pipeline

```
Lead sends reply
  → ProcessedReply created (status: pending)
  → Operator sees in Replies tab

Operator replies (one of two paths):

Path A: Via our UI (approve-and-send)
  → approved_at = now(), approval_status = 'approved'
  → Follow-up eligible after delay_days ✓

Path B: Directly in SmartLead/GetSales
  → sync_conversation_histories (every 3 min)
     ├── Checks SmartLead thread API: last message outbound?
     ├── YES → sets auto_resolved + approved_at = now()
     └── Creates ContactActivity records for CRM
  → Follow-up eligible after delay_days ✓
```

## Scheduled Tasks That Power This

### 1. `sync_conversation_histories` — Fast Track (SmartLead)
- **Runs**: Every 3 minutes
- **Scope**: Last 7 days of pending replies, SmartLead only
- **Batch**: 100 unique leads per run
- **What it does**:
  1. Queries pending replies received in last 7 days
  2. Fetches SmartLead message-history API per lead
  3. If last message is outbound (operator replied externally):
     - Sets `approval_status = 'auto_resolved'`, `approved_at = now()`
     - Creates missing `ContactActivity` records for CRM timeline
  4. If last message is inbound (lead's reply still latest): skips
- **API calls**: ~5-10 per run (deduped by campaign+email)
- **Rate limiting**: SmartLead semaphore (10 concurrent, 150/min sliding window)

### 2. `deep_cleanup_needs_reply` — Full Sweep (SmartLead + GetSales)
- **Runs**: Every 6 hours
- **Scope**: ALL pending replies (no date limit, oldest first)
- **Batch**: 200 API calls per run
- **What it does**:
  1. Queries ALL pending replies (oldest first, batch of 200)
  2. For SmartLead: same thread API check as sync
  3. For GetSales: checks LinkedIn conversation messages API
  4. If operator replied externally:
     - Sets `approval_status = 'auto_resolved'`, `approved_at = now()`
     - Writes `ReplyCleanupLog` per project (audit trail)
- **API calls**: Up to 200 (SmartLead + GetSales combined)
- **Rate limiting**: SmartLead same as above; GetSales 200ms min between requests

### Why Two Tasks?
- `sync_conversation_histories`: **Speed** — catches SmartLead external replies within 3 minutes
- `deep_cleanup_needs_reply`: **Coverage** — handles GetSales + old backlog that sync missed

## Follow-Up UI Flow

```
Operator opens Follow-ups tab
  → GET /replies/?needs_followup=true (query above)
  → Sees cards with "Sent X days ago" badge

Operator clicks "Generate Follow-up"
  → POST /replies/{id}/generate-followup-draft
  → AI generates draft with context (original message, days elapsed)
  → Calendar slots available if project has calendly_config

Operator reviews draft, clicks "Send Follow-up"
  → POST /replies/{id}/send-followup
  → Creates child ProcessedReply (parent_reply_id = original)
  → Sends via SmartLead or GetSales
  → Original reply no longer appears in follow-up query

Operator clicks "Skip"
  → POST /replies/{id}/dismiss-followup
  → Creates dismissed child record
  → Original reply no longer appears in follow-up query
```

## Configuration

Per-project `follow_up_config` JSON column:
```json
{
  "enabled": true,
  "delay_days": 3
}
```

Currently enabled for project 40 (easystaff ru) with 3-day delay.

## Data Flow Diagram

```
                     ┌─────────────┐
                     │  Lead Reply  │
                     │ (inbound)   │
                     └──────┬──────┘
                            │
                    ProcessedReply created
                    (status: pending)
                            │
              ┌─────────────┴─────────────┐
              │                           │
     Operator replies              Operator replies
     via our UI                    via SmartLead/GetSales
              │                           │
     approve-and-send              sync_conversation_histories
     status = 'approved'           (3 min) detects outbound
     approved_at = now()           status = 'auto_resolved'
              │                    approved_at = now()
              │                           │
              └─────────────┬─────────────┘
                            │
                   After delay_days (3d)
                            │
                   needs_followup query
                   finds this reply
                            │
                   Appears in Follow-ups tab
                            │
              ┌─────────────┴─────────────┐
              │                           │
     "Generate Follow-up"          "Skip"
     → AI draft with context       → dismissed child
     → "Send Follow-up"             (removed from queue)
     → child ProcessedReply
       (removed from queue)
```
