# Remove Tags from Email Accounts

## Overview

Remove tag associations from email accounts. The system will delete tag mappings for each email account and tag combination. Non-existent mappings are skipped.

**HTTP Method:** DELETE

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/tag-mapping`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

## Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_account_ids` | array (integer) | Yes | Array of email account IDs to remove tags from (Max 25) |
| `tag_ids` | array (integer) | Yes | Array of tag IDs to remove |

---

## Request Example

```bash
curl -X DELETE "https://server.smartlead.ai/api/v1/email-accounts/tag-mapping?api_key={API_KEY}" \
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
  "message": "Tag removal operation completed",
  "data": {
    "results": [
      {
        "email_account_id": 1,
        "tag_id": 5,
        "action": "deleted",
        "mapping_id": 123
      },
      {
        "email_account_id": 1,
        "tag_id": 10,
        "action": "skipped",
        "reason": "Mapping does not exist"
      }
    ],
    "summary": {
      "total_processed": 3,
      "deleted": 2,
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
