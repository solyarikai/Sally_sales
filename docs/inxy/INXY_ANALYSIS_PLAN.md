# Inxy Reply Analysis — Execution Plan

## Goal
Understand Inxy's REAL offers, objection patterns, and reply intents from actual conversation data — not guesses.

## Phase 1: Data Extraction
- Export ALL Inxy non-OOO replies with thread context from DB
- Store as `/tmp/inxy_conversations.json` — structured, reusable
- Track: total count, loaded count, which IDs loaded, thread availability

### Fields per conversation:
```json
{
  "reply_id": 123,
  "lead_email": "...",
  "lead_name": "First Last",
  "lead_company": "...",
  "campaign_name": "Inxy - Trading 3",
  "category": "interested",
  "reply_text": "...",
  "received_at": "2026-01-15",
  "channel": "linkedin",
  "thread_messages": [
    {"direction": "outbound", "body": "...", "position": 0},
    {"direction": "inbound", "body": "...", "position": 1}
  ],
  "approval_status": "approved|dismissed|pending",
  "draft_reply": "...",
  "has_thread": true
}
```

## Phase 2: Iterative Analysis (100 at a time)

### Batch 1 (conversations 1-100)
- Read all 100 conversations with full thread context
- Focus on: what was the OUTBOUND message offering? What did the lead respond to?
- Extract: actual Inxy product offers mentioned in outbound sequences
- Extract: reply patterns, objection types, interest signals
- Document findings in `/tmp/inxy_analysis_batch1.md`

### Batch 2 (101-200)
- Validate Batch 1 findings against new data
- Look for patterns missed in Batch 1
- Refine offer taxonomy, intent taxonomy
- Document delta in `/tmp/inxy_analysis_batch2.md`

### Batch N...
- Continue until patterns stabilize (no new offer types or intent types appearing)
- Each batch produces a delta document

## Phase 3: Synthesis
- Merge all batch findings into final taxonomy
- Rewrite REPLY_INTELLIGENCE_UX.md with facts-based classifications
- Present to user for review

## Tracking State: `/tmp/inxy_extraction_state.json`
```json
{
  "total_replies": 0,
  "extracted": 0,
  "analyzed_batches": [],
  "offers_found": [],
  "intents_found": [],
  "last_updated": "..."
}
```
