# Push Lead To Subsequence

## Overview

Push a lead automatically to a subsequence that belongs to the campaign from which the reply was received.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/push-to-subsequence`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication key needed to verify your request |

## Request Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `email_lead_map_id` | integer | Yes | — | The ID of the lead in the master inbox to push to subsequence |
| `sub_sequence_id` | integer | Yes | — | ID of the campaign (subsequence) to push the lead to |
| `sub_sequence_delay_time` | integer | No | 0 | Delay in days before starting subsequence for this lead |
| `stop_lead_on_parent_campaign_reply` | boolean | No | false | Whether to stop if lead replies to parent campaign |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/push-to-subsequence?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 1982614021,
    "sub_sequence_id": 1456278,
    "sub_sequence_delay_time": 3,
    "stop_lead_on_parent_campaign_reply": true
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead pushed to subsequence successfully",
  "data": {
    "success": true,
    "sub_sequence_id": 1456278,
    "delay_days": 3
  }
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```
