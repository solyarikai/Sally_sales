# Change Read Status API Documentation

## Overview

Mark a lead as read or unread in the master inbox.

**HTTP Method:** PATCH

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/change-read-status`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body (JSON)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | integer | Yes | The unique ID of the email lead mapping record |
| `read_status` | boolean | Yes | Change it to read (true) or unread (false) |

---

## Request Example

```bash
curl -X PATCH "https://server.smartlead.ai/api/v1/master-inbox/change-read-status?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "read_status": true
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead marked as unread successfully",
  "data": {
    "success": true,
    "updated": 1
  }
}
```

### Error Response (400)

```json
{}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```
