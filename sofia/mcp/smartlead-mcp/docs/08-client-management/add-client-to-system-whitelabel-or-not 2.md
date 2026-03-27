# Add Client To System (Whitelabel or not)

## Overview

Endpoint to add new clients to your system with optional whitelabel configuration.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/client/save`

---

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body

**Content-Type:** `application/json`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | "Ramesh Kumar" | Client name |
| `email` | string | Yes | "hello@myemail.com" | Client email address |
| `permission` | array | Yes | `["reply_master_inbox"]` | Client's permissions array |
| `logo` | string | No | "SmartGen Outreach" | Client logo text/name |
| `logo_url` | string | No | null | Logo URL (can be null) |
| `password` | string | Yes | "Test1234" | Client password |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/client/save?api_key={API_KEY} \
  --data '{
    "name": "Ramesh Kumar",
    "email": "ramesh+15@five2one.com.au",
    "permission": [
      "reply_master_inbox"
    ],
    "logo": "SmartGen Outreach",
    "logo_url": null,
    "password": "Test1234!"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "clientId": 299,
  "name": "Ramesh Kumar",
  "email": "ramesh+15@five2one.com.au",
  "password": "Test1234!"
}
```

**Response Schema:**

| Field | Type | Example |
|-------|------|---------|
| `ok` | boolean | true |
| `clientId` | integer | 299 |
| `name` | string | "Ramesh Kumar" |
| `email` | string | "ramesh+15@five2one.com.au" |
| `password` | string | "Test1234!" |

### Error Response (400)

```json
{}
```

---

## Notes

- For full access permissions, use: `"permission": ["full_access"]`
- Passwords should meet security requirements
- Email must be unique in the system
