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
- Uses **bulk statistics endpoint** (GET /campaigns/{id}/statistics, 500/page) to
  resolve email→lead_id — NOT individual per-lead API calls
- Fetches message-history only for matched pending leads (~20 calls, not thousands)
- If last message is outbound (not a REPLY), marks `replied_externally`
- Creates missing outbound `ContactActivity` records for permanent tracking
- Adaptive delay: starts at 1.5s, doubles on 429, eases down on success
- Manual trigger via `POST /sync-outbound-status?project_id=X&auto_dismiss=true`
- Optional GPT-4o-mini auto-dismiss: classifies inbound replies as
  needs_reply / ooo / unsubscribe / bounce / not_interested / already_handled

### US15: Smartlead Stats Match
> As an operator, I see campaign reply statistics that match Smartlead's
> analytics page (unique replied, replied w/OOO, positive replies).

**Acceptance:**
- `GET /replies/campaign/{id}/analytics-summary` returns same stats as Smartlead
- Shows: unique_replied, unique_replied_with_ooo, unique_positive, by_category
- Data comes from bulk statistics endpoint (same as US10)
- Frontend stat badges reflect these numbers per selected project/campaign

### US11: Search Projects
> As an operator, I search for a project by name on the projects list page
> so I can quickly find the right project even with many entries.

**Acceptance:**
- Search input at top of `/projects` page
- Filters project list by name in real time (client-side)
- Shows "No projects matching ..." message when no results
- Clearing search shows all projects again

### US12: View Project Page (shareable URL)
> As an operator, I open a dedicated project page with a shareable URL
> (`/projects/:id`) to see and manage all project settings in one place.

**Acceptance:**
- Each project card in the list links to `/projects/:id`
- Project page shows: editable name, campaigns with source badges, Telegram connect
- Campaigns show `SL` (blue) badge for Smartlead, `GS` (green) badge for GetSales
- Add/remove campaigns with autocomplete search dropdown
- Back button returns to project list
- Delete project button with confirmation
- URL is shareable — visiting `/projects/22` directly opens the Rizzult project

### US13: See Campaign Sources
> As an operator, I can see which campaigns are from Smartlead vs GetSales
> at a glance, both on the project page and in the campaign picker.

**Acceptance:**
- Each campaign has a source badge: `SL` (blue, Smartlead) or `GS` (green, GetSales)
- Visible on project page campaign chips and in the campaign search dropdown
- Source data comes from `/api/contacts/campaigns` endpoint (already returns `{name, source}`)

### US14: Select Project on Replies Page
> As an operator, I switch between projects directly on the Replies page
> using a prominent tab bar, without navigating to settings or opening a dropdown.

**Acceptance:**
- Horizontal row of project tabs at top of Replies page header
- "All Projects" tab + one tab per project
- Active tab highlighted with violet background
- Clicking a tab sets `currentProject` in global store and filters replies
- Tab bar scrolls horizontally if many projects

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

## Smartlead Reference Numbers (Rizzult Fintech 22.11.25 Aleks, campaign 2703961)

| Metric | Smartlead Analytics | Our Target |
|---|---|---|
| Total Leads Contacted | 2,380 | — |
| Unique Replied | 46 (1.93%) | Match via statistics API |
| Unique Replied w/OOO | 114 (4.79%) | Match via statistics API |
| Unique Positive Replies | 14 (30.43%) | Match via GPT classification |

### Architecture Decision: Bulk Statistics (Feb 12 2026)

**Problem:** Previous sync fetched ALL 2,380 leads via `/campaigns/{id}/leads`
(24+ API calls at 100/page) just to build email→lead_id map. Then individual
message-history calls per pending lead. Hit 429 rate limits constantly, skipped
leads, reported wrong counts.

**Solution:** Use `GET /campaigns/{id}/statistics?limit=500` (the same endpoint
the reply poller already uses). Returns ALL leads with `reply_time`, `lead_id`,
`lead_category` in ~5 pages. Build email→lead_id map from this. Then fetch
message-history only for the ~20 leads that are pending in our DB.

**GPT auto-dismiss:** Don't trust Smartlead's `lead_category` auto-labeling.
Use GPT-4o-mini to classify the actual reply text into needs_reply / ooo /
unsubscribe / bounce / not_interested / already_handled. Cost: ~$0.01 per sync.

---

## Auto-Tests (Playwright)

E2E tests in `frontend/e2e/projects-replies.spec.ts`:

1. **Projects list**: loads, search filters projects by name
2. **Project navigation**: clicking project card goes to `/projects/:id`
3. **Project page**: shows campaigns with source badges, Telegram, editable name
4. **Back button**: returns to projects list
5. **Replies project selector**: shows tab bar, clicking filters replies
6. **Telegram button**: visible on project page (connect or connected state)

---

## Future Enhancements
- [ ] Editable draft before sending
- [ ] Bulk approve/dismiss by category
- [x] Auto-dismiss out_of_office & unsubscribe (via GPT-4o-mini, `auto_dismiss=true`)
- [x] Campaign analytics matching Smartlead (`/campaign/{id}/analytics-summary`)
- [ ] Reply quality scoring
- [ ] Operator assignment (multi-user)
- [ ] Reply templates per category
- [ ] Analytics: response time, conversion rate
