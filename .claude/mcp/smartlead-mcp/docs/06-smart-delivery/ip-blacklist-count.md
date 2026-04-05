# Spam Test IP Blacklist Count

## Overview

Retrieve the total blacklist count identified in a spam delivery test.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/:spamTestId/ip-analytics`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spamTestId` | integer (int32) | Yes | The unique identifier of the spam test |

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/ip-analytics?api_key=${API_KEY}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "domain": "outlook.com",
  "totalBlacklist": 11,
  "totalTestedOk": 210,
  "totalTests": 222,
  "totalTimedOut": 1
}
```

### Error Response (400)

```json
{
  "message": "Error description"
}
```

## Notes

- Blacklist data becomes available after the test completes
