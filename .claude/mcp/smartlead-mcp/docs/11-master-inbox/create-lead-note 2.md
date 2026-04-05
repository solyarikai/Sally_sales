# Create Lead Note API Documentation

## Overview

Create a new note for a lead in the master inbox.

**HTTP Method:** POST

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/create-note`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication key for API access |

## Request Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | integer | Yes | Unique ID of the email lead mapping record |
| `note_message` | string | Yes | Content of the note |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/create-note?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "note_message": "Lead showed interest in enterprise features during our call"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Note created successfully",
  "data": {
    "success": true,
    "note": [
      {
        "id": "129523",
        "created_at": "2025-08-01T03:47:19.577Z"
      }
    ]
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
