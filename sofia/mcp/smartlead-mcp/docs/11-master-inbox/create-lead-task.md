# Create Lead Task - API Documentation

## Overview

Create a new task for a lead in the master inbox.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/create-task`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication credential for request verification |

## Request Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | integer | Yes | Unique identifier for the email lead mapping record |
| `name` | string | Yes | Task title/name |
| `description` | string | No | Detailed task description |
| `priority` | string | Yes | Task priority level: LOW, MEDIUM, or HIGH |
| `due_date` | string (ISO 8601) | Yes | Task deadline in ISO format |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/create-task?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "name": "Follow up with lead",
    "description": "Send pricing information and schedule demo",
    "priority": "HIGH",
    "due_date": "2025-02-01T10:00:00.000Z"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Task created successfully",
  "data": {
    "success": true,
    "task": [
      {
        "id": "77721",
        "created_at": "2025-08-01T03:47:18.577Z"
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
