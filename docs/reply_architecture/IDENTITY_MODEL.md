# Lead Identity Model — Email-Optional Architecture

## Rule: No Fake Emails. Ever.

`lead_email` is either a real validated email or NULL. Period.

LinkedIn leads have no email — that's fine. The system handles NULL emails natively via `getsales_lead_uuid`. **NEVER create placeholder/fake emails.** They were tried once, broke everything, and were permanently purged.

## Design: Dual-Key Identity

Every lead is identified by **whichever key exists**:

| Platform | Primary Key | Fallback | Example |
|----------|------------|----------|---------|
| SmartLead (email) | `lead_email` | — | `john@acme.com` |
| GetSales (LinkedIn) | `getsales_lead_uuid` | `lead_email` (if enriched later) | `d6a8d593-83ac-46d3-baea-87dbb6486b6f` |
| Both | `lead_email` | `getsales_lead_uuid` | Either or both |

### The `lead_identifier` Expression

Everywhere the system needs to group, dedup, or identify a lead, it uses:

```sql
COALESCE(lead_email, getsales_lead_uuid)
```

This is the **canonical grouping key**. It returns:
- The email if available (SmartLead leads, enriched LinkedIn leads)
- The GetSales UUID if no email (pure LinkedIn leads)

### Unique Constraint (Dedup)

```sql
CREATE UNIQUE INDEX uq_reply_dedup ON processed_replies (
    COALESCE(lead_email, getsales_lead_uuid),
    COALESCE(campaign_id, ''),
    message_hash
) WHERE message_hash IS NOT NULL;
```

This prevents duplicate messages regardless of whether the lead has an email.

## Deep Linking: `reply_id`

### Before (broken for LinkedIn)
```
/tasks/replies?lead=gs_uuid@linkedin.placeholder&project=easystaff-ru
```

### After (works for all leads)
```
/tasks/replies?reply_id=42595&project=easystaff-ru
```

Every `ProcessedReply` has a stable integer `id`. Telegram notification links and "Copy link" buttons use `reply_id` instead of `lead_email`. This works for:
- Email leads (SmartLead)
- LinkedIn leads without email (GetSales)
- Leads with both email and LinkedIn

### Deep Link Params

1. `?reply_id=` — the ONLY correct way. Works for all leads (email, LinkedIn, both).
2. `?lead=` — legacy, only works for leads with real email. Dead for LinkedIn-only leads.

**Placeholder emails (`gs_*@linkedin.placeholder`) are permanently gone.** Migration `j1_remove_placeholder_emails` converted them all to NULL. They were fake, broke everything, and no longer exist in the DB. All `lead_email` values are real validated emails or NULL.

## API Changes

### List Replies (`GET /api/replies/`)

New parameter: `reply_id: Optional[int]`

When `reply_id` is provided:
1. Fetch the specific reply
2. Extract its `lead_email` or `getsales_lead_uuid`
3. Filter to show all replies from that contact
4. Works identically to `lead_email` filter but for any lead type

### Group By Contact

`group_by_contact=true` uses `DISTINCT ON (COALESCE(lead_email, getsales_lead_uuid))` to show one card per lead.

### Contact Info Loading

The `contact-info-batch` endpoint accepts both emails and reply IDs. For LinkedIn leads without email, contact info is looked up by `getsales_lead_uuid` → `Contact.getsales_id`.

## Data Flow: GetSales Reply Processing

```
GetSales Webhook
    ↓
process_getsales_reply()
    ↓
Extract: getsales_lead_uuid, getsales_sender_uuid, getsales_conversation_uuid
    ↓
lead_email = contact.email (real email) or None (LinkedIn-only)
    ↓                                    ↓
    ↓ (has email)                        ↓ (no email)
    ↓                                    ↓
Dedup by (lead_email, hash)     Dedup by (getsales_lead_uuid, hash)
    ↓                                    ↓
    └──────────── ProcessedReply ────────┘
                       ↓
              Telegram notification
                       ↓
              ?reply_id={id}&project={name}
```

## Rules

1. **`lead_email` is a real email or NULL.** No placeholders, no fakes, no `@linkedin.placeholder`. Ever.
2. **ALWAYS use `reply_id` for deep links.** Not email, not UUID. `reply_id` is universal.
3. **ALWAYS use COALESCE for grouping.** `COALESCE(lead_email, getsales_lead_uuid)` is the grouping key.
4. **Contact lookup fallback.** When `lead_email` is NULL, look up by `getsales_lead_uuid` → `Contact.getsales_id`.
5. **Display name, not email.** For LinkedIn leads, show `lead_first_name + lead_last_name` where email would appear.
