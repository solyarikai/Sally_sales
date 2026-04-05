# Pause Lead By Campaign ID - API Documentation

## Overview
This endpoint pauses a lead from a campaign based on the lead and campaign ID.

**Endpoint:** `POST https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/pause`

---

## Parameters

### Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID to pause lead for |
| `lead_id` | string | Yes | N/A | The lead ID to pause |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Request Body
This endpoint accepts a POST request but does not require a request body.

---

## Request Examples

### cURL
```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/pause?api_key={API_KEY}
```

---

## Response Examples

### Success Response (200)
```json
{
  "ok": true,
  "data": "success"
}
```

**Response Schema:**
- `ok` (boolean): Confirmation flag, example: `true`
- `data` (string): Response message, example: `"success"`
