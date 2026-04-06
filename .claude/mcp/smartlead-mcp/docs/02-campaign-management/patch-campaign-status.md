# Patch Campaign Status API Documentation

## Endpoint Overview

**Title:** Patch campaign status

**Description:** This endpoint changes the status of a campaign

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign you want to patch |

## Query Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `status` | string | Yes | `PAUSED` | Campaign status to set. Allowed values: `PAUSED`, `STOPPED`, `START` |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/${campaign_id}/status?api_key={API_KEY} \
  --data '{"status": "PAUSED"}'
```

---

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true
}
```

---

## Notes

- The endpoint accepts status values: `PAUSED`, `STOPPED`, or `START`
- API key must be provided as a query parameter
- Campaign ID is a required path parameter
