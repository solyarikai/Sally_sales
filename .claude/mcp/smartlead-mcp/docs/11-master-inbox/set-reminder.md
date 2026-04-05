# Set Reminder API Documentation

## Overview

Add a reminder to a reply to action later on.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/set-reminder`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication key to verify your request |

## Request Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | string | Yes | Master Inbox ID identifying the lead |
| `email_stats_id` | string | Yes | Unique identifier of the reply to associate the reminder with |
| `message` | string | Yes | Contents/text of the reminder |
| `reminder_time` | string | Yes | When you want to be reminded (ISO 8601 format) |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/set-reminder?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": "1982614021",
    "email_stats_id": "a61aa4d2-1ac5-4278-b7e6-c2a46310fd04",
    "message": "Follow up with this lead about pricing discussion",
    "reminder_time": "2025-08-05T09:30:00.000Z"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Reminder set successfully",
  "data": {
    "success": true,
    "reminder": {
      "id": "12345",
      "created_at": "2025-08-01T10:30:00.000Z"
    }
  }
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

- All body parameters must be provided in the request
- `reminder_time` should be in ISO 8601 format
- The `email_stats_id` links the reminder to a specific email reply thread
