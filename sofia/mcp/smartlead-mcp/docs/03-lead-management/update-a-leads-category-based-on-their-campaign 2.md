# Update a Lead's Category Based on Their Campaign

## Overview
This endpoint allows you to update a lead's category assignment within a specific campaign.

**Description:** "This endpoint lets you update your leads category based on the campaign they belong to"

---

## Endpoint Details

| Property | Value |
|----------|-------|
| **HTTP Method** | POST |
| **URL** | `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/category` |
| **Authentication** | API Key (query parameter) |

---

## Parameters

### Path Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID the lead belongs to |
| `lead_id` | string | Yes | `lead_id` | The lead ID to update |

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Request Body Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `category_id` | integer | Yes | `143` | Category ID to assign to the lead |
| `pause_lead` | boolean | No | `false` | Whether to pause the lead (defaults to false if not provided) |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/category?api_key={API_KEY} \
  --data '{
    "category_id": 143,
    "pause_lead": true
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true
}
```
