# Delete Campaign Webhook

## Overview

This endpoint deletes a webhook from a campaign.

**HTTP Method:** `DELETE`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | N/A | The ID of the campaign from which to remove the webhook |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body

No request body required for this endpoint.

---

## cURL Request

```bash
curl -X DELETE \
  "https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/webhooks?api_key={API_KEY}"
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true
}
```

**Response Schema:**
- `ok` (boolean): Confirmation flag indicating successful deletion

---

## Notes

- This is a DELETE operation requiring proper authentication via API key
- The endpoint removes webhook configuration from a specified campaign
- Successful deletion returns a simple confirmation response with the `ok` field set to `true`
