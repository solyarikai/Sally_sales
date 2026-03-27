# Fetch All Clients

## Overview

Retrieve a list of all clients in the system.

**HTTP Method:** `GET`

**URL:** `https://server.smartlead.ai/api/v1/client/`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/client/?api_key={API_KEY}
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 6,
    "name": "Ramesh Client",
    "email": "ramesh+client@five2one.com.au",
    "uuid": "1e19fcb7-6651-444a-8495-e1a4bda16611",
    "created_at": "2022-08-25T04:24:04.656Z",
    "user_id": 288,
    "logo": null,
    "logo_url": null,
    "client_permision": {
      "permission": ["reply_master_inbox"],
      "retricted_category": []
    }
  },
  {
    "id": 298,
    "name": "Ramesh Kumar",
    "email": "ramesh+14@five2one.com.au",
    "uuid": "d86864b6-c6aa-4ca8-970c-01be63494322",
    "created_at": "2022-11-25T14:29:04.742Z",
    "user_id": 288,
    "logo": "SmartGen Outreach",
    "logo_url": "",
    "client_permision": {
      "permission": ["reply_master_inbox"],
      "retricted_category": []
    }
  }
]
```

### Error Response (400)

```json
{}
```

## Response Schema

Array of client objects, each containing:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Client identifier |
| `name` | string | Client name |
| `email` | string | Client email address |
| `uuid` | string | Unique universal identifier |
| `created_at` | string | Creation timestamp |
| `user_id` | integer | Associated user ID |
| `logo` | string/null | Logo name |
| `logo_url` | string/null | Logo URL |
| `client_permision` | object | Permissions configuration |
