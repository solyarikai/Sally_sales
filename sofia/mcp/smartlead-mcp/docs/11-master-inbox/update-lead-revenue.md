# Update Lead Revenue

## Overview

Update the revenue/deal value for a lead in the master inbox.

**HTTP Method:** `PATCH`

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/update-revenue`

---

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body

**Content-Type:** `application/json`

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `email_lead_map_id` | integer | Yes | — | The unique ID of the email lead mapping record |
| `revenue` | number | Yes | Minimum: 0 | The revenue amount to assign |

---

## Request Example

```bash
curl -X PATCH "https://server.smartlead.ai/api/v1/master-inbox/update-revenue?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "revenue": 500.50
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead revenue updated successfully",
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

---

## Notes

- Minimum revenue value is 0
- The `email_lead_map_id` can be obtained from master inbox API responses or webhooks
- Only one record is updated per request
