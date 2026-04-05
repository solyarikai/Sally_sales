# Forward a Reply API Documentation

## Overview

This endpoint allows you to forward an email reply to a lead using the Master Inbox API.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/campaigns/${campaign_id}/forward-email`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The campaign ID to reply lead from |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `email_stats_id` | string | Yes | — | Unique identifier per lead per email sequence per campaign (fetchable via "Fetch Lead Message History" endpoint) |
| `email_body` | string | Yes | — | Reply message email body content |
| `reply_message_id` | string | Yes | — | Message ID to which email will be sent as reply |
| `reply_email_time` | string | Yes | — | Time of the message to which reply is being sent |
| `reply_email_body` | string | Yes | — | The original message content to which reply is being sent |
| `cc` | string | No | — | Email address to carbon copy |
| `bcc` | string | No | — | Email address to blind carbon copy |
| `add_signature` | boolean | No | true | Whether to add email signature to reply |
| `to_first_name` | string | No | — | First name of the lead receiving the reply |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/campaigns/${campaign_id}/forward-email?api_key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_stats_id": "unique_stats_id_here",
    "email_body": "<p>Thanks for reaching out!</p>",
    "reply_message_id": "<message-id@outlook.com>",
    "reply_email_time": "2023-03-15T09:13:29.000Z",
    "reply_email_body": "<p>Original message content</p>",
    "cc": "cc@example.com",
    "bcc": "bcc@example.com",
    "add_signature": true,
    "to_first_name": "John"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "data": "success"
}
```

### Error Response (400)

```json
{
  "error": "Invalid campaign_id or missing required parameters"
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

---

## Notes

- All email identifiers (`email_stats_id`, `reply_message_id`) can be obtained from the "Fetch Lead Message History" endpoint
- Email body supports HTML formatting
- The `add_signature` parameter defaults to true if not specified
