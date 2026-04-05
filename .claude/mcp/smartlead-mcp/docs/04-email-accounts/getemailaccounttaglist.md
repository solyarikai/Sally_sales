# Get Tag List by Email Addresses

## Overview

Returns email account IDs, email addresses, and aggregated tags for specified email addresses. All provided addresses must belong to the authenticated user.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/tag-list`

---

## Authentication

Two methods supported:
- Query parameter: `api_key`
- Header: `x-api-key`

## Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_ids` | array of strings | Yes | Array of email account addresses; minimum 1 item |

---

## Request Example

```bash
curl -X POST https://server.smartlead.ai/api/v1/email-accounts/tag-list \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "email_ids": ["user1@example.com", "user2@example.com"]
  }'
```

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "email_account_id": 123,
      "email_id": "user1@example.com",
      "tags": [
        {"tag_id": 1, "tag_name": "Sales"},
        {"tag_id": 2, "tag_name": "Support"}
      ]
    },
    {
      "email_account_id": 124,
      "email_id": "user2@example.com",
      "tags": []
    }
  ]
}
```

### Error Response (400)

```json
{
  "success": false,
  "message": "email_ids must be an array"
}
```

### Error Response (403)

```json
{
  "success": false,
  "message": "User not authenticated"
}
```

### Error Response (406)

```json
{
  "success": false,
  "message": "One or more email accounts do not belong to this user",
  "invalid_emails": ["other@example.com"]
}
```
