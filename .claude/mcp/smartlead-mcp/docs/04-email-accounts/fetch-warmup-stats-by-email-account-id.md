# Fetch Warmup Stats By Email Account ID

## Overview

This endpoint retrieves warmup statistics for the last 7 days associated with a specific email account.

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}/warmup-stats`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_account_id` | string | Yes | The unique identifier for the email account |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}/warmup-stats?api_key={API_KEY}
```

## Response Examples

### Success Response (200)

```json
{
  "id": 106466,
  "sent_count": "0",
  "spam_count": "0",
  "inbox_count": "0",
  "warmup_email_received_count": "0",
  "stats_by_date": [
    {
      "id": 1,
      "date": "2023-05-23",
      "sent_count": 0,
      "reply_count": 0,
      "save_from_spam_count": 0
    },
    {
      "id": 2,
      "date": "2023-05-24",
      "sent_count": 0,
      "reply_count": 0,
      "save_from_spam_count": 0
    }
  ]
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Email account identifier |
| `sent_count` | string | Total warmup emails sent |
| `spam_count` | string | Total emails marked as spam |
| `inbox_count` | string | Total emails in inbox |
| `warmup_email_received_count` | string | Total warmup replies received |
| `stats_by_date` | array | Daily breakdown of statistics |
| `stats_by_date[].date` | string | Date (YYYY-MM-DD format) |
| `stats_by_date[].sent_count` | integer | Emails sent on this date |
| `stats_by_date[].reply_count` | integer | Replies received on this date |
| `stats_by_date[].save_from_spam_count` | integer | Emails recovered from spam |
