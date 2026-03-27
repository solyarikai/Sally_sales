# Add Tags to Email Accounts

## Overview

"Associate multiple tags with multiple email accounts. The API will create tag mappings for each email account and tag combination. If a mapping already exists, it will be skipped."

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/tag-mapping`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

## Request Body

| Parameter | Type | Required | Min/Max Items | Description |
|-----------|------|----------|---------------|-------------|
| `email_account_ids` | array (integer) | Yes | 1-25 | Array of email account IDs to tag (Max 25) |
| `tag_ids` | array (integer) | Yes | 1+ | Array of tag IDs to assign |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/email-accounts/tag-mapping?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_account_ids": [1, 2, 3],
    "tag_ids": [5, 10, 15]
  }'
```

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Tag mapping operation completed",
  "data": {
    "results": [
      {
        "email_account_id": 1,
        "tag_id": 5,
        "action": "added",
        "mapping_id": 123
      },
      {
        "email_account_id": 1,
        "tag_id": 10,
        "action": "skipped",
        "reason": "Mapping already exists"
      }
    ],
    "summary": {
      "total_processed": 3,
      "added": 2,
      "skipped": 1,
      "failed": 0
    }
  }
}
```

### Error Response (400)

```json
{
  "success": false,
  "message": "Validation error",
  "error": "email_account_ids must contain at least 1 item"
}
```
