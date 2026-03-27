# Delete Campaign API Documentation

## Overview

**Description:** This endpoint deletes the campaigns in your account

**HTTP Method:** DELETE

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign you want to delete |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body

No request body required for this endpoint.

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}?api_key={API_KEY} \
  -X DELETE
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true
}
```

### Response Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Successfully deleted the campaign |
| 400 | Bad request / Invalid parameters |
| 404 | Campaign not found |
