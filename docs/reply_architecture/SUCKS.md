# Reply System — Bug Log

Bugs that happened, why, and what was done so they don't happen again.

---

## 1. Deep link `reply_id` sticks when switching tabs (2026-03-25)

**What sucked:** Operator opens reply from Telegram deep link (`?reply_id=44300&project=inxy`). Reply loads. Operator clicks "Meetings" or any other tab — still sees only that one reply because `reply_id` stays in the URL.

**Root cause:** `setCategoryFilter` (tab click handler) updated the `category` URL param but never cleared `reply_id` or `lead` deep link params.

**Fix:** Clear `reply_id` and `lead` from URL params when user clicks any category tab.

```
// ReplyQueue.tsx — setCategoryFilter
next.delete('reply_id');
next.delete('lead');
```

---

## 2. Deep link shows "All caught up" on first load (2026-03-25)

**What sucked:** Operator clicks "Open in Replies UI" from Telegram. Page shows "All caught up" instead of the reply.

**Root cause:** Race condition. `currentProject` comes from zustand (persisted from previous session, e.g. "archistruct"). The URL says `project=inxy`, but the URL-to-project sync effect hasn't fired yet when the first `loadReplies` runs. API query: `reply_id=44300 AND project_id=archistruct_id` → 0 results.

**Fix:** When `reply_id` is present, skip `project_id` filter entirely. `reply_id` is unique — no project scoping needed.

---

## 3. GetSales send succeeds but UI shows no feedback (2026-03-25)

**What sucked:** Operator clicks "Send" on a LinkedIn reply. GetSales API accepts the message (it's sent to the lead). But the UI shows nothing — no toast, no card removal. DB still shows `approval_status=NULL`. If operator clicks Send again → duplicate message.

**Root cause:** GetSales `send_linkedin_message` had 3 retries x 60s timeout = 186s worst case. nginx `proxy_read_timeout` is 120s. When GetSales was slow, nginx cut the connection before the backend could commit the DB update. The message was sent but the system didn't know.

**Fix:**
- Reduced send timeout to 20s x 2 retries = 44s max (fits within nginx 120s)
- Frontend: when `send_error` or `status=send_failed`, keep card in queue (don't optimistically remove)
- Error toast duration increased from 4s to 10s
- Outbound history entry only added after confirming send succeeded

---

## 4. Duplicate messages in conversation thread history (2026-03-29)

**What sucked:** The conversation history view showed "Будет интересно" twice at the same timestamp. Operator sees duplicate bubbles.

**Root cause:** The `full-history` endpoint merges activities from THREE independent sources without deduplication:
1. `ThreadMessages` — cached from GetSales API at reply processing time
2. Safety net — adds the reply's own inbound message if missing from ThreadMessages
3. `ContactActivity` — LinkedIn activities from the `contact_activities` table

When a GetSales reply is processed, the system creates BOTH a `ThreadMessage` (cached thread) AND a `ContactActivity` (LinkedIn activity record) for the same inbound message. Both get added to the `activities` list → duplicate bubble.

**Architecture problem:** The history endpoint treats each source as authoritative and concatenates them without checking for overlap. Any new data source added in the future would cause the same bug.

**Fix:** Added dedup step after merging all sources, keyed on `(direction, content[:100], timestamp[:16])`. This is a permanent architectural safeguard — no matter how many sources feed into the history, duplicates are always removed before rendering.

```python
# Deduplicate: ThreadMessages + ContactActivity + safety net can overlap
seen = set()
deduped = []
for a in activities:
    key = (a["direction"], a["content"].strip()[:100], a["timestamp"][:16])
    if key not in seen:
        seen.add(key)
        deduped.append(a)
activities = deduped
```

**Architecture fixes (3 layers):**

**Layer 1 — Single writer:** SmartLead webhook handler NO LONGER creates ContactActivity for inbound replies. Only the reply processor creates it (with `processed_reply_id` dedup key). One writer = no dual-creation.

**Layer 2 — Merge-time dedup:** `full-history` builds an `existing_keys` set from ThreadMessages BEFORE merging ContactActivity. ContactActivity records that match an existing ThreadMessage are skipped at merge time. Dedup happens at the source, not after.

**Layer 3 — Safety net:** Final dedup pass on the merged list (kept as defense-in-depth for any future source).

**Rule:** ContactActivity is an AUDIT LOG. ThreadMessages is the CONVERSATION DISPLAY source. `full-history` uses ThreadMessages as canonical, ContactActivity only fills gaps.
