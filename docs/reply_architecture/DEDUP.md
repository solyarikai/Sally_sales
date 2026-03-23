# Reply Dedup Architecture

## Dedup Key

```sql
UNIQUE(
    COALESCE(lead_email, getsales_lead_uuid),  -- lead identity
    COALESCE(campaign_id, ''),                  -- campaign scope
    message_hash                                -- content identity
)
WHERE message_hash IS NOT NULL
```

`message_hash` = `MD5(body[:500].lower())`

## How It Works

| Lead Type | Dedup Key | Example |
|-----------|-----------|---------|
| Email (SmartLead) | `(john@acme.com, 3029626, abc123)` | Email + campaign + hash |
| LinkedIn (GetSales) | `(d6a8d593-..., '', 7e271d...)` | UUID + empty campaign + hash |
| LinkedIn with email | `(john@acme.com, '', 7e271d...)` | Email takes priority via COALESCE |

## Race Condition: Sync vs Webhook

GetSales replies can arrive via two paths:
1. **Webhook** (real-time) — has `automation.name`, `automation.uuid`, `sender_profile`
2. **Sync poll** (every 3 min) — has `automation: "synced"` (no campaign info)

The sync may arrive BEFORE the webhook. The upsert pattern handles this:

```
Sync arrives first:
    → INSERT with campaign_id=NULL, campaign_name=NULL

Webhook arrives second:
    → Check for existing (lead_identifier, message_hash)
    → Found with empty campaign → ENRICH (update campaign_id, campaign_name)
    → Not a duplicate — just fills in missing metadata
```

## Content-Based Dedup

Each unique message body gets its own `ProcessedReply` record. If a lead sends the same text twice, it's deduped. If they send different messages, each gets a record.

The hash uses only the first 500 chars of the body (lowercased) to avoid false negatives from email signatures or thread quoting.

## Group By Contact

The Replies UI shows one card per lead using `group_by_contact=true`:

```sql
SELECT DISTINCT ON (COALESCE(lead_email, getsales_lead_uuid))
    *
FROM processed_replies
ORDER BY COALESCE(lead_email, getsales_lead_uuid),
    received_at DESC,
    category_priority ASC
```

This picks the newest, highest-priority reply per lead, whether they have an email or not.

## Campaign Count Per Contact

After fetching the page of grouped replies, the system counts how many campaigns each lead appears in:

```sql
SELECT COALESCE(lead_email, getsales_lead_uuid) as identifier,
       COUNT(DISTINCT campaign_name) as count
FROM processed_replies
WHERE identifier IN (:page_identifiers)
GROUP BY identifier
```

This powers the "(+2 campaigns)" badge on the reply card.
