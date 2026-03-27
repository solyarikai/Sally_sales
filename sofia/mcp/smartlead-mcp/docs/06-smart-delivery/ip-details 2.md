# IP Details

## Overview

The list of all the blacklists per IP.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/sender-account-wise/$(replyId)/ip-details`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer (int32) | Yes | The ID of the spam test |
| `replyId` | string | Yes | The reply ID for which IP details are being retrieved |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API key for authentication |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/sender-account-wise/$(replyId)/ip-details?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
{
  "domain": "outlook.com",
  "totalBlacklist": 0,
  "totalTestedOk": 213,
  "totalTests": 222,
  "totalTimedOut": 9
}
```

### Error Response (400)

```json
{}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | Domain information |
| `totalBlacklist` | integer | Total blacklist count |
| `totalTestedOk` | integer | Total tested OK count |
| `totalTests` | integer | Total tests conducted |
| `totalTimedOut` | integer | Total timed out count |
