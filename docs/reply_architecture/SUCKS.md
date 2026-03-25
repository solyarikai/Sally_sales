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
