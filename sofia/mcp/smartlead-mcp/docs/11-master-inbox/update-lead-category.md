# Update Lead Category API Documentation

## Overview

Update the category assignment for a lead.

**HTTP Method:** PATCH

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/update-category`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body (JSON)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | integer | Yes | The unique ID of the email lead mapping record |
| `category_id` | integer | Yes | The category ID to assign (null to remove category) |

---

## Request Example

```bash
curl -X PATCH "https://server.smartlead.ai/api/v1/master-inbox/update-category?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "category_id": 1454
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead category updated successfully",
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

- Set `category_id` to `null` to remove a category assignment from a lead
- The `email_lead_map_id` uniquely identifies a lead within the system
