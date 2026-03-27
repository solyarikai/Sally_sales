# Bulk Fetch Messages for Multiple Email Accounts

## Overview
"Fetches recent messages from multiple email account mailboxes in parallel. Processes up to 10 accounts per request with individual success/failure tracking."

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/multi/fetch-messages`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body

JSON array (min 1, max 10 items):

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id` | number | Yes | — | Email account ID to fetch from |
| `limit` | number | No | 100 | Messages to retrieve (1-500) |
| `folder` | string | No | null | Specific folder name (e.g., INBOX) |
| `includeBody` | boolean | No | false | Include message body content |
| `from` | string (ISO 8601) | No | null | Start time for message range |
| `to` | string (ISO 8601) | No | null | End time for message range |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/email-accounts/multi/fetch-messages?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "account_id": 123,
      "limit": 50,
      "folder": "INBOX",
      "includeBody": false,
      "from": "2025-01-01T00:00:00Z",
      "to": "2025-01-02T00:00:00Z"
    },
    {
      "account_id": 456,
      "limit": 100,
      "folder": "SENT",
      "includeBody": true
    }
  ]'
```

## Response Examples

### Success Response (200)

```json
{
  "results": [
    {
      "account_id": 123,
      "status": "success",
      "data": {
        "messages": []
      }
    },
    {
      "account_id": 456,
      "status": "error",
      "error": "Account not found"
    }
  ],
  "summary": {
    "total": 2,
    "success": 1,
    "error": 1
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | Array of per-account results |
| `results[].account_id` | number | The account ID processed |
| `results[].status` | string | "success" or "error" |
| `results[].data` | object | Message data (on success) |
| `results[].error` | string | Error message (on failure) |
| `summary.total` | number | Total accounts processed |
| `summary.success` | number | Successful requests |
| `summary.error` | number | Failed requests |
