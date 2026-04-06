# Reconnect Failed Email Accounts

## Overview

**Description:** "This endpoint lets you bulk reconnect disconnected email accounts."

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/reconnect-failed-email-accounts`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key |

## Request Body

None (empty JSON object `{}`)

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/reconnect-failed-email-accounts?api_key={API_KEY} \
  --data '{}'
```

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Email account(s) added to the queue to reconnect. We will send you an email once completed."
}
```

### Rate Limit Error (400)

```json
{
  "ok": true,
  "message": "Bulk reconnect API cannot be consumed more than 3 times a day"
}
```

### No Failed Accounts (404)

```json
{
  "ok": true,
  "message": "No failed email account found!"
}
```

## Notes
- The API processes reconnection asynchronously; completion notification is sent via email
- Rate-limited to 3 requests per 24-hour period
