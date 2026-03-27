# Retrigger Failed Events

## Overview

This API endpoint re-triggers all failed webhook events for a given campaign within a specified time duration. Re-triggers are processed in small batches, and status can be tracked via the GET endpoint.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks/retrigger-failed-events`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | N/A | The ID of the campaign for which to retrigger failed webhook events |

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

---

## Request Body

The endpoint accepts a JSON object with time duration parameters to filter which failed events to retrigger.

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks/retrigger-failed-events?api_key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Failed events retrigger initiated",
  "retrigger_id": "string"
}
```

### Error Response (400)

```json
{
  "error": "Invalid campaign ID or request parameters"
}
```

---

## Notes

- Re-triggers are processed in batches
- Track retrigger progress using the webhook summary GET endpoint
- Only failed webhook events within the specified timeframe are processed
