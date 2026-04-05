# Fetch all Campaigns Using Lead ID

## Overview

**Description:** This endpoint lets you fetch all the campaigns a Lead belongs to using the Lead ID

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/leads/{lead_id}/campaigns`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_id` | string | Yes | The target lead ID |

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/leads/<lead_id>/campaigns?api_key=${API_KEY}
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 2911,
    "status": "COMPLETED",
    "name": "SL - High Intent Leads guide"
  },
  {
    "id": 5055,
    "status": "DRAFTED",
    "name": ""
  }
]
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Campaign identifier |
| `status` | string | Campaign status (e.g., "COMPLETED", "DRAFTED") |
| `name` | string | Campaign name |

---

## Notes

- No request body is required for this endpoint
- Authentication is performed via the `api_key` query parameter
- The response is an array of campaign objects the lead is enrolled in
