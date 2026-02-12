# Auto-Replies Flow — User Stories & Spec

## Overview

The auto-replies system tracks all inbound replies across Smartlead campaigns,
classifies them with AI, generates draft responses, and lets an operator review
& send them per project.

Each **project** (e.g. Rizzult, EasyStaff) has `campaign_filters` — a list of
Smartlead campaign names that belong to it. When an operator selects a project,
only replies from those campaigns are shown.

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
> my reply — not ones we already responded to.

**Acceptance:**
- "Needs Reply" filter is ON by default
- Logic: show reply only if there is NO outbound message (from us) sent AFTER the
  lead's reply `received_at` timestamp
- This is computed from `ContactActivity.direction` — no GPT needed
- Out-of-office and unsubscribe categories are auto-excluded from "needs reply"

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

---

## Data Model

### Key Tables
- `ProcessedReply` — each inbound reply: lead info, AI classification, draft, approval status
- `ContactActivity` — full conversation log: `direction` (inbound/outbound), `channel`, `activity_at`
- `Project` — has `campaign_filters[]` linking Smartlead campaign names

### "Needs Reply" Detection (no GPT)
```
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
```

---

## Current Numbers (Rizzult, Feb 2026)

| Metric | Count |
|---|---|
| Total replies | 942 |
| Needs reply (no outbound after) | 933 |
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
