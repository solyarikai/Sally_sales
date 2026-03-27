# Stop an Automated Smart Delivery Test

## Overview

This endpoint allows you to halt an active automated spam/deliverability test before its scheduled end date. Note: This functionality applies only to automated tests and cannot be used on manual tests, which can only be deleted to stop them.

## Endpoint Details

**HTTP Method:** `PUT`

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/{spamTestId}/stop`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer (int32) | Yes | The ID of the spam test to stop |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl --location -g --request PUT \
  'https://smartdelivery.smartlead.ai/api/v1/spam-test/512/stop?api_key=${API_KEY}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "message": "ED test stopped successfully"
}
```

### Error Response (400)

```json
{
  "message": "Test not found"
}
```
