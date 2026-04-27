# Instantly Inbox Placement Tests — Setup Guide

**Audience:** Sales engineers at Sally
**Purpose:** correctly configure Instantly inbox placement tests (IPT) so that
results actually reflect mailbox deliverability — not silent failures, not
self-confirming warmup numbers.

This guide documents what we learned debugging the OnSocial monitoring on
2026-04-23..27 and bringing it from "0 records, 27 silent" to a working
per-provider deliverability report.

---

## TL;DR

A correctly configured IPT requires four things:
1. Workspace on **Inbox Placement Growth** plan (`pid_ip_g`, ~$47/mo)
2. All sender mailboxes in `status=1` (active) **at the moment the test is created**
3. `recipients_labels` populated with the 3 available ESP options (Google Pro,
   Google Personal, Outlook Pro) — this gives you Instantly's built-in seed pool
4. Realistic subject/body matching production campaigns (spam filters score content)

If any of those is missing, you'll get one of the failure modes documented in
[Troubleshooting](#troubleshooting).

---

## Two ways to run a test

| Approach | When to use |
|---|---|
| **API / Claude Code** | Recurring, automated monitoring (cron), large mailbox lists, programmatic alerts to Slack |
| **UI (app.instantly.ai)** | One-off check, manual investigation, when you don't have/don't need scripts |

Both produce the same kind of test and same data — choose by workflow fit.

---

## Prerequisites (both paths)

### 1. Confirm billing is active

Inbox Placement is sold separately from Outreach. Workspace must have
`product_type: inbox_placement` subscription. Without it, every API endpoint
related to IPT returns `402 Payment Required: Workspace does not have an active
paid plan` — including read-only endpoints.

**Check via API:**

```bash
curl -s https://api.instantly.ai/api/v2/workspace-billing/subscription-details \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" | jq .
```

Expected:
```json
{
  "subscriptions": [
    {
      "product_id": "pid_ip_g",
      "product_type": "inbox_placement",
      "plan_type": "plt_primary",
      "current_period_end": 1779735707,
      "price_in_dollars": 47,
      "all_subs_cancelled": false
    }
  ]
}
```

If `subscriptions: []` or `all_subs_cancelled: true` — IPT will not work, fix
billing first via the UI billing page before continuing.

**Check via UI:** open `https://app.instantly.ai`, top-right user menu →
**Billing** (or **Settings → Billing**). Look for a section titled
"Inbox Placement" with an active subscription. If you only see Outreach plan
listed and no separate Inbox Placement entry — it's not paid for.

### 2. Activate all sender mailboxes

**This is the most common failure mode.** When a test is created, Instantly
locks in the list of active senders. If a mailbox is `status=2` (paused) or
`status=-1/-2/-3` (errored) at that exact moment, it's silently excluded — the
test runs without it and you get no analytics records for that sender. By the
time you check results, even if you've activated the mailbox, it's too late
for the running test.

For a 27-mailbox OnSocial test created while all 27 were paused: 0 records
across the whole test. After activating all 27 and re-creating: 100% of senders
returned data within the first batch.

**Account status codes:**
- `1` = active (will send)
- `2` = paused (will be excluded)
- `-1` = connection error (excluded)
- `-2` = soft bounce error (excluded)
- `-3` = sending error (excluded)

#### Via API

List all OnSocial mailboxes and their status:

```bash
curl -s "https://api.instantly.ai/api/v2/accounts?limit=100" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  | jq '.items[] | select(.email | test("onsocial|crona")) | {email, status, warmup_status}'
```

Resume each paused mailbox:

```bash
curl -X POST "https://api.instantly.ai/api/v2/accounts/$EMAIL/resume" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Mark each errored mailbox as fixed (after you've confirmed the underlying
issue is gone):

```bash
curl -X POST "https://api.instantly.ai/api/v2/accounts/$EMAIL/mark-fixed" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Important notes:
- Both endpoints **require an empty JSON body `{}`**. Sending no body returns
  `400 FST_ERR_CTP_EMPTY_JSON_BODY`.
- Email goes URL-encoded in the path (`@` → `%40`).
- Different API keys have different scopes. The reader key
  (`...:RIBVujbQqgXU` for our workspace) handles both list and account
  modifications. The writer key (`...:sykqgmaZLtul`) is needed for creating
  tests but returns 401 on `GET /accounts`. If something fails with 401, try
  another key.

A reusable script lives at `magnum-opus/infra/` (see scripts referenced in the
"OnSocial example" section below).

#### Via UI

1. Open `https://app.instantly.ai/app/accounts`
2. Search/filter the mailboxes you intend to put in the test
3. For each row showing **Paused** badge: open the row's `…` menu → **Resume**
4. For each row in error state (red badge): open `…` menu → **Mark as fixed**
   (only do this after fixing the underlying SMTP/IMAP issue, otherwise it
   will go back to error within minutes)
5. After the action, the row no longer shows a Paused/error badge — that
   means `status=1`. Verify by counting active rows for the project.

### 3. Have a realistic subject and body ready

The recipient ESPs (Gmail/Outlook) score the test email's content as if it
were a real cold email. If you test with placeholder text or a different
project's content, you measure that content's deliverability — not your
mailboxes'. Pull a recent subject line and body from the production campaign
in SmartLead and paste them in.

---

## Variant 1 — API / Claude Code

### Step 1: create the test

`POST /api/v2/inbox-placement-tests` with the following payload:

```javascript
{
  "name": "ProjectName auto " + new Date().toISOString().slice(0, 10),
  "type": 1,                    // one-time test (not automated/recurring)
  "delivery_mode": 1,           // one by one (not all-together)
  "sending_method": 1,          // send from Instantly (not external)
  "email_subject": "<your real subject from production campaign>",
  "email_body": "<HTML body from production campaign>",
  "emails": [
    "sender1@yourdomain.com",
    "sender2@yourdomain.com",
    // ... all senders you want tested
  ],
  "recipients_labels": [
    {"region": "North America", "sub_region": "US", "type": "Professional", "esp": "Google"},
    {"region": "North America", "sub_region": "US", "type": "Personal",     "esp": "Google"},
    {"region": "North America", "sub_region": "US", "type": "Professional", "esp": "Outlook"}
  ]
}
```

What each parameter does:

- **`type`** — `1` for a single test, `2` for an automated recurring test
  managed by Instantly. Use `1` and drive recurrence yourself via cron.
- **`delivery_mode`** — `1` sends one email at a time, `2` sends all in
  parallel. Use `1` to look organic.
- **`sending_method`** — `1` uses Instantly's relay through your authenticated
  mailboxes (what you want), `2` is for "send manually and report what you
  did". Always `1`.
- **`emails`** — your sender mailboxes. Each must be `status=1` in
  `/accounts` at this exact moment (see Prerequisites #2).
- **`recipients_labels`** — Instantly's built-in seed pool. The 3 entries
  above are everything available on the `pid_ip_g` plan; use all three to
  get per-provider distribution.
- **`recipients`** — leave it out. When you submit `recipients_labels`,
  Instantly auto-generates 22 actual recipient inboxes covering the labels
  (10× Google Pro on Sally seed domains, 2× Google Personal on free Gmail,
  10× Outlook Pro on Sally seed domains). You'll see them populated in the
  response.

**Response** includes the test `id` (UUID) and `status: 1` (active). Save the
ID — you need it to query analytics.

### Step 2: wait

The test runs through several phases:
1. Send emails (~1–10 min depending on size)
2. Recipient mailboxes receive the messages
3. Instantly polls each recipient via IMAP every ~25 min and tags each message
   inbox vs spam

Records appear in `/inbox-placement-analytics` only after the IMAP poll fires.
Don't expect data in the first 20 min even if the test is small.

For our 26-sender × 22-recipient = 572-pair OnSocial test, records arrived in
batches of ~26 every ~25 min, full coverage took ~2.5 hours. A 1-sender ×
1-recipient probe still took ~25 min for the first record.

### Step 3: pull analytics

Paginated:

```bash
curl -s "https://api.instantly.ai/api/v2/inbox-placement-analytics?test_id=$TID&limit=100" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY"
```

Each record looks like:

```json
{
  "test_id": "...",
  "sender_email": "bhaskar@onsocial-platform.com",
  "recipient_email": "avery@gofynor.com",
  "is_spam": false,
  "spf_pass": true,
  "dkim_pass": true,
  "dmarc_pass": true,
  "recipient_esp": 1,             // 1=Google, 2=Outlook
  "recipient_type": 1,            // 1=Professional, 2=Personal
  "recipient_geo": 1,
  "authentication_failure_results": null,
  "record_type": 2
}
```

### Step 4: aggregate and report

Group by `sender_email`, count total vs spam, compute deliverability:

```javascript
deliverability(sender) = (1 - spam_count / total_count) * 100
```

**Filter strictly to configured `emails` from your test config** — Instantly
sometimes leaks records from other tests in the same workspace into your
analytics, and sometimes substitutes one mailbox for another on the same
domain (e.g. our test specified `petr@crona-force.com` but Instantly returned
data for `eleonora@crona-force.com`). Always reconcile against the
`detail.emails` array of the test, drop foreign senders.

Buckets to report:

- **Healthy** — sender has records and deliverability ≥ 80%
- **Problematic** — sender has records and deliverability < 80%
- **Silent** — sender is in test config but has zero records (means it didn't
  send: paused at creation, OR substituted, OR genuinely blocked)

For each problematic sender, do a per-recipient breakdown by `recipient_esp`
+ `recipient_type` to find which provider rejects them. Domain-reputation
issues at Google look like: 6 Google rcpts → all spam, 4 Outlook rcpts → all
inbox.

### Step 5: schedule the cron

Pattern we use for OnSocial on the main Hetzner server:

```cron
# Create test (~3h before report so IMAP polling has time to populate)
0 3 * * 2,5 cd /home/leadokol/scripts && node instantly-onsocial-start-test.js \
    >> /home/leadokol/logs/instantly-onsocial-start.log 2>&1

# Read analytics, post to Slack
0 6 * * 2,5 cd /home/leadokol/scripts && node instantly-spam-report-onsocial.js \
    >> /home/leadokol/logs/instantly-spam-report-onsocial.log 2>&1
```

Choose Tue/Fri to match standard outreach schedules. Don't run more often
than once per (Tue/Fri) — IPT credits are not unlimited and small daily
fluctuations don't carry signal.

---

## Variant 2 — UI (app.instantly.ai)

### Step 1: open the test creator

Sidebar → **Inbox Placement** (icon resembles an inbox tray). On the inbox
placement page, click **Create Test** (top right).

### Step 2: fill in the form

- **Test name** — `<ProjectName> auto YYYY-MM-DD`. The auto-prefix matters
  if you're going to query the latest test by name.
- **Test type** — choose **One-time test** (matches API `type=1`).
- **Delivery mode** — choose **One by one** (matches `delivery_mode=1`).
- **Sending method** — choose **Send from Instantly** (matches
  `sending_method=1`).
- **Email subject** — paste the exact subject line you use in the production
  campaign for this project.
- **Email body** — paste the exact HTML body. The UI editor accepts both
  rich-text and HTML source views; use HTML to avoid auto-formatting.
- **Senders** — multi-select your project's mailboxes. Each one MUST show
  active state in the dropdown (no Paused/error badge). If you see a Paused
  mailbox in the dropdown, abort, go fix it on the Email Accounts page, come
  back.
- **Recipients section** — this is where most setups go wrong.
  - Look for a tab/toggle labeled **Use Instantly seed pool** or
    **Recipient labels** (different UI builds name it differently).
  - Select all 3 labels available:
    - **Google · Professional · US**
    - **Google · Personal · US**
    - **Outlook · Professional · US**
  - **Do not** add custom recipient emails on top — they don't add per-provider
    visibility and complicate analytics filtering.

Hit **Create**. Status badge shows **Active** while the test runs.

### Step 3: wait

Same timing as the API path: ~25 min for first records, ~1–3h for full
results, depending on sender count. The UI shows a progress bar; refresh it
or close the tab and come back.

### Step 4: read the results

When the test finishes (status badge **Completed**), the test detail page
shows several panels:

- **Overall placement** — single number: % inbox vs % spam aggregated across
  all (sender, recipient) pairs. Sanity check.
- **Per-sender table** — one row per sender mailbox with columns: emails sent,
  inbox, spam, deliverability %. Sort ascending by deliverability to see worst
  offenders. Anything < 80% is your action list.
- **Per-recipient/provider breakdown** — typically shown as a chart with
  Google Pro / Google Personal / Outlook Pro columns. For each problematic
  sender, click into it to see per-recipient details — a sender that's all
  spam at Google but inbox at Outlook has a Google domain-reputation issue,
  not a content/auth issue.
- **Authentication results** — SPF/DKIM/DMARC pass rate. Anything other than
  100% pass means a DNS misconfiguration somewhere.

### Step 5: action on results

For each problematic sender:
- **Spam at Google + inbox at Outlook** → check Google Postmaster Tools for
  that domain (https://postmaster.google.com), look at IP/Domain reputation
  panels. Fix may take days.
- **Spam everywhere** → likely SPF/DKIM/DMARC issue. Cross-check with the
  authentication panel.
- **Silent** (sender has zero data in the test) → one of:
  1. Was paused at creation time → resume, recreate test
  2. Instantly substituted a different sender on the same domain (visible in
     the per-sender table — you'll see an unexpected mailbox) → check what
     other accounts you have on that domain
  3. SMTP-level rejection by all 22 recipients → severe deliverability
     failure, the domain is on a major blacklist

---

## OnSocial — concrete example

Our reference test (2026-04-27):
- Senders: 27 mailboxes (14 `bhaskar@onsocial-*.com`, 3 `bhaskar@onsocial*.com`
  no-dash, 10 `petr@crona-*.com`)
- Recipients: built-in seed pool via `recipients_labels` (3 ESP) → 22 actual
  recipient inboxes auto-generated
- Subject: copied from active OnSocial cold campaign in SmartLead
- Cron: 03:00 UTC create, 06:00 UTC report (Tue/Fri)

Scripts live in `magnum-opus/infra/` (source of truth, in git) and deployed
to `/home/leadokol/scripts/` on the main Hetzner server (`hetzner` SSH alias):

- `instantly-onsocial-start-test.js` — creates the test
- `instantly-spam-report-onsocial.js` — reads latest completed test, posts
  bucketed report to Slack (`#onsocial` webhook)

Findings from this test:
- 24 of 26 senders → **100% inbox** at every Google/Outlook recipient
- `eleonora@crona-b2b.com` → 60% (Google → spam, Outlook → inbox)
- `eleonora@cronaaipipeline.com` → 33% (Google → spam, Outlook → inbox)
- 1 mailbox (`petr@prospects-crona.com`) → not in Instantly accounts at all,
  needs to be added before next test

These two `eleonora@*` results pinpointed Google-only domain-reputation
problems. Without per-provider breakdown (which requires `recipients_labels`,
which requires paid plan) we'd have seen "60%" and "33%" but not WHERE to
fix.

---

## Troubleshooting

### `402 Payment Required: Workspace does not have an active paid plan`
Inbox Placement subscription is missing or expired. Check
`/workspace-billing/subscription-details`. Fix in UI Billing page, then retry.
Note: this 402 hits both reads AND writes — even listing existing tests
fails. Don't confuse with rate limiting (which returns 429).

### `400 FST_ERR_CTP_EMPTY_JSON_BODY`
You called `POST /accounts/{email}/resume` (or similar) without a request
body. Send `{}`. If using `curl`, add `-d '{}'`.

### Test is `status=1` for 30+ min, 0 records in analytics
Most likely cause: senders were paused when test was created. Check current
status of each sender in your test config — if any are `status≠1`, the test
won't recover. Delete it (`DELETE /inbox-placement-tests/{id}` — must omit
Content-Type header to avoid the empty-body issue), activate the senders,
recreate.

### Records show senders not in your test config (foreign senders)
Instantly leaks records across tests in the same workspace, and substitutes
mailboxes on the same domain. Always intersect analytics with your configured
`emails` list before computing deliverability. Use that filter consistently
across all tooling.

### `warmup_reputation` shows 100% but mailboxes are clearly in spam
SmartLead's `warmup_reputation` measures Superwarm internal traffic
(SmartLead users sending to each other), where everyone has filters set to
keep these messages out of spam. It's a closed loop and reports ~100% even
when external Gmail blocks the same sender 100% of the time. **Never use
`warmup_reputation` as a deliverability signal** — use IPT.

### `open_rate` is 0% even though replies are non-zero
Apple Mail Privacy Protection, corporate firewalls, and modern email clients
strip or pre-fetch tracking pixels. A 0% open rate with non-zero replies
means open tracking is broken, not that the emails went to spam. Don't act
on `open_rate` alone.

### Coverage is high for some projects but silent for others (in the same workspace)
Most often: silent project's senders are paused. Sometimes: the test config
list is wrong (typo, mailbox renamed, or never existed in Instantly accounts —
visible by `MISSING` flag in our activation script). Verify each sender by
listing `/accounts` and intersecting with your test config.

---

## API reference quick links

- `POST /api/v2/inbox-placement-tests` — create test
- `GET /api/v2/inbox-placement-tests/{id}` — test detail (status, configured
  emails, recipients, recipients_labels)
- `GET /api/v2/inbox-placement-tests/{id}/email-service-provider-options` —
  available ESP labels for your plan tier
- `GET /api/v2/inbox-placement-analytics?test_id={id}` — paginated records
- `DELETE /api/v2/inbox-placement-tests/{id}` — cancel/delete (omit
  Content-Type header)
- `POST /api/v2/accounts/{email}/resume` — unpause mailbox (body: `{}`)
- `POST /api/v2/accounts/{email}/mark-fixed` — clear error state (body: `{}`)
- `GET /api/v2/workspace-billing/subscription-details` — verify IP plan active
- `GET /api/v2/workspaces/current` — workspace plan IDs

Rate limit: 100 req/sec, 6000 req/min, returns 429 (not 402) when exceeded.
