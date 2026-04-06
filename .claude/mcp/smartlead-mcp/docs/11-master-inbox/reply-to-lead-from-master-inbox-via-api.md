# Reply To Lead From Master Inbox via API

## Overview

This endpoint allows you to reply to a lead using the Master Inbox API.

**Method:** POST
**URL:** `https://server.smartlead.ai/api/v1/campaigns/${campaign_id}/reply-email-thread`

---

## Parameters

### Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_id` | string | Yes | The campaign ID to reply to lead from |

### Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

### Request Body Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `email_stats_id` | string | Yes | Unique ID per lead per email sequence per campaign (fetchable via "Fetch Lead Message History" endpoint) |
| `email_body` | string | Yes | Reply message email body content |
| `reply_message_id` | string | Yes | Message ID to which email reply is sent (from "Fetch Lead Message History") |
| `reply_email_time` | string | Yes | Time of the message being replied to (from message history) |
| `reply_email_body` | string | Yes | Original message content being replied to (from message history) |
| `cc` | string | No | Email address(es) to carbon copy |
| `bcc` | string | No | Email address(es) for blind carbon copy |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/campaigns/${campaign_id}/reply-email-thread?api_key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_stats_id": "iuh2o3iuh3o2ih2-iuho3-edwhi92",
    "email_body": "<p>Thanks for your reply!</p>",
    "reply_message_id": "<message@outlook.com>",
    "reply_email_time": "2023-03-15T09:13:29.000Z",
    "reply_email_body": "<p>Original message content</p>",
    "cc": "example@email.com",
    "bcc": "ramesh@five2one.com.au"
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
  "error": "Invalid email_stats_id or campaign_id"
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```
