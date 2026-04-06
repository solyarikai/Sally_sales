# Resume Lead API Documentation

## Overview

Resume a paused lead in a campaign.

**HTTP Method:** `PATCH`

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/resume-lead`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body (JSON)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | integer | Yes | — | The campaign ID to resume the lead in |
| `email_lead_map_id` | integer | Yes | — | The unique ID of the email lead mapping record |
| `resume_delay_days` | integer | No | 1 | Number of days to wait before resuming (minimum: 0) |

---

## Request Example

```bash
curl -X PATCH "https://server.smartlead.ai/api/v1/master-inbox/resume-lead?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": 400001,
    "email_lead_map_id": 1982614021,
    "resume_delay_days": 1
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead resumed successfully",
  "data": {
    "status": "success",
    "nextSeqId": 200001
  }
}
```

### Error Response (400)

```json
{
  "ok": false,
  "message": "This is the last sequence. You cannot resume this lead."
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

---

## Notes

- The `resume_delay_days` parameter is optional and defaults to 1 day
- Minimum value for `resume_delay_days` is 0
- Cannot resume a lead if it's on the final sequence in the campaign
- The `nextSeqId` indicates which email sequence will be sent next after the delay period
