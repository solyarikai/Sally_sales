# Auto-Replies Flow — User Stories & Spec

## Overview

The auto-replies system tracks all inbound replies across Smartlead campaigns,
classifies them with AI, generates draft responses, and lets an operator review
& send them per project.

Each **project** (e.g. Rizzult, EasyStaff) has `campaign_filters` — a list of
Smartlead campaign names that belong to it. When an operator selects a project,
only replies from those campaigns are shown.

Operators receive Telegram notifications for new replies, configured with a
one-click setup flow directly in the project settings.

---

## User Stories

### US1: Select Project
> As an operator, I select a project (Rizzult, EasyStaff, etc.) from the header
> dropdown so I only see replies relevant to that project's campaigns.

**Acceptance:**
- Project selector in the top nav bar
- Selecting a project filters Replies, Stats, and all sub-views
- "All Projects" option shows everything
- Selection persists across page navigation

### US2: See Only Replies That Need Action
> As an operator, I want to see only conversations where the lead is waiting for
> my reply — not ones we already responded to or that are auto-dismissable.

**Acceptance:**
- "Needs Reply" filter is ON by default (button shows "Awaiting Reply (N)")
- Logic: show reply only if there is NO outbound message (from us) sent AFTER the
  lead's reply `received_at` timestamp
- This is computed from `ContactActivity.direction` — no GPT needed
- Out-of-office and unsubscribe categories are auto-excluded from "needs reply"
- Replies marked `replied_externally` (operator replied via Smartlead UI) are excluded

### US3: Triage by Category
> As an operator, I filter by reply category to prioritize high-value leads.

**Priority order:**
1. `meeting_request` — lead wants a call (highest priority)
2. `interested` — warm lead expressing interest
3. `question` — lead has questions, needs answers
4. `not_interested` — polite follow-up or dismiss
5. `wrong_person` — ask for referral or dismiss
6. `out_of_office` — auto-dismiss or wait
7. `other` — review individually
8. `unsubscribe` — auto-dismiss

### US4: Review AI Draft
> As an operator, I click a reply card to see the full conversation history,
> AI classification, and auto-generated draft reply.

**Acceptance:**
- Detail panel shows: lead name, email, company, campaign
- Full conversation thread (all inbound/outbound messages, chronological)
- AI classification: category, confidence, reasoning
- Draft reply text (editable in future)
- "Approve & Send" and "Dismiss" buttons

### US5: Approve & Send with Safety
> As an operator, I approve a draft and send it via Smartlead, with a
> confirmation dialog showing exactly what will be sent.

**Acceptance:**
- Confirmation dialog shows: recipient, campaign, full draft text
- On localhost: TEST MODE indicator, sends with `?test_mode=true`
  - Body prefixed with `[TEST — original recipient: <email>]`
  - Sends to `pn@getsally.io` instead of real lead
  - Status set to `approved_test`
  - Real leads never affected during testing
- On production: sends via Smartlead thread API, status = `approved`
- Toast notification confirms what happened

### US6: Dismiss
> As an operator, I dismiss replies that don't need action (OOO, unsubscribe,
> wrong person, not interested).

**Acceptance:**
- One-click dismiss moves reply out of pending queue
- Status badge shows "Skipped"
- Dismissed replies hidden from default view (pending filter)

### US7: Track Progress
> As an operator, I see stats showing how many replies need attention vs. handled.

**Acceptance:**
- Stats bar at top: total, pending, needs reply, approved, dismissed
- Breakdown by category with counts
- Today / this week counters

### US8: Connect Telegram Notifications (one-click)
> As an operator, I connect my Telegram account to a project so I receive
> instant notifications when new replies come in — without typing anything.

**Flow:**
1. Open the project card, click **Connect Telegram**
2. Telegram opens with the bot. Tap **Start**
3. Bot auto-links my chat to the project (via deep link `t.me/ImpecableBot?start=project_<id>`)
4. UI detects the connection within 2 seconds and shows "Connected as [name]"

**Acceptance:**
- Single "Connect Telegram" button on the project card (expanded view)
- Clicking opens `t.me/ImpecableBot?start=project_{id}` in a new tab
- UI polls `GET /telegram/project-status?project_id=X` every 2 seconds
- When connected, shows green "Connected as [name]" badge
- "Disconnect" button to remove the link
- No username input required — deep link carries the project ID
- Auto-timeout after 60 seconds if operator doesn't tap Start

### US9: Receive Telegram Notifications
> As an operator, I receive a Telegram message for every new reply in my
> project, so I can triage even when not in the app.

**Acceptance:**
- Notifications sent to the project's linked `telegram_chat_id`
- Format: emoji + category + lead name + company + message preview + draft preview
- Admin (global `TELEGRAM_CHAT_ID`) always receives ALL replies
- Project operator only receives replies for their project's campaigns
- Duplicate send avoided (admin chat != operator chat check)

### US10: Conversation History Sync
> As the system, I periodically check Smartlead message histories to detect
> when an operator has replied directly via Smartlead UI, so the "needs reply"
> count stays accurate without manual intervention.

**Acceptance:**
- Background loop runs every 10 minutes
- Checks pending replies without outbound `ContactActivity`
- Fetches Smartlead message-history API per lead
- If last message is outbound (not a REPLY), marks `replied_externally`
- Creates missing outbound `ContactActivity` records for permanent tracking
- Rate-limited to ~1.5 req/s to avoid Smartlead 429s
- Manual trigger via `POST /sync-outbound-status?project_id=X`

---

## Data Model

### Key Tables
- `ProcessedReply` — each inbound reply: lead info, AI classification, draft, approval status
  - `approval_status`: `NULL`/`pending` (needs action), `approved`, `approved_test`, `dismissed`, `replied_externally`
- `ContactActivity` — full conversation log: `direction` (inbound/outbound), `channel`, `activity_at`
- `Project` — has `campaign_filters[]`, `telegram_chat_id`, `telegram_first_name`
- `TelegramRegistration` — maps `@username` -> `chat_id` (for backward compat / plain /start)

### "Needs Reply" Detection (no GPT)
```sql
SELECT pr.*
FROM processed_replies pr
WHERE NOT EXISTS (
    SELECT 1 FROM contact_activities ca
    JOIN contacts c ON ca.contact_id = c.id
    WHERE LOWER(c.email) = LOWER(pr.lead_email)
      AND ca.direction = 'outbound'
      AND ca.activity_at > pr.received_at
)
AND (pr.approval_status IS NULL OR pr.approval_status = 'pending')
AND pr.category NOT IN ('out_of_office', 'unsubscribe')
```

---

## Current Numbers (Rizzult, Feb 12 2026)

| Metric | Count |
|---|---|
| Total replies | 942 |
| Pending (needs action) | 941 |
| Replied externally (detected by sync) | 1 |
| Needs reply (excl OOO/unsub/replied) | 742 |
| meeting_request | 63 |
| interested | 9 |
| question | 9 |
| not_interested | 20 |
| wrong_person | 160 |
| out_of_office | 189 |
| other | 487 |
| unsubscribe | 5 |

---

## Future Enhancements
- [ ] Editable draft before sending
- [ ] Bulk approve/dismiss by category
- [ ] Auto-dismiss out_of_office & unsubscribe
- [ ] Reply quality scoring
- [ ] Operator assignment (multi-user)
- [ ] Reply templates per category
- [ ] Analytics: response time, conversion rate
