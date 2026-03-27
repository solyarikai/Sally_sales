# Resume Lead By Campaign ID - API Documentation

## Endpoint Overview

**Title:** Resume Lead By Campaign ID

**Description:** This endpoint resumes a lead from a campaign based on the lead and campaign ID

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/resume`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID to resume lead for |
| `lead_id` | string | Yes | `lead_id` | Lead to resume campaign for |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `resume_lead_with_delay_days` | integer | No | 0 | Can be null and defaults to 0. Number of days to delay before resuming |

---

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}/resume?api_key={API_KEY} \
  --data '{"resume_lead_with_delay_days": 10}'
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
- `ok` (boolean): Indicates successful execution
- `data` (string): Operation result message
