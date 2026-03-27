# Blacklists

## Overview

Provides the list of all the blacklists, per IP per email sent.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/blacklist`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer | Yes | The ID of the spam test |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Your API Key for authentication |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/blacklist?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "from_email": "harrisonmarganza@outlook.com",
    "details": [
      {
        "id": 93,
        "email": "sydney.m@alwaysinprimary.com",
        "reply": {
          "blacklist_status": {
            "domain": "outlook.com",
            "totalBlacklist": 11,
            "totalTestedOk": 210,
            "totalTests": 222,
            "totalTimedOut": 1
          }
        }
      }
    ]
  }
]
```

### Error Response (400)

```json
{
  "message": "error message"
}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `from_email` | string | Sender email address |
| `details` | array | Array containing test results per recipient |
| `details[].id` | integer | Record identifier |
| `details[].email` | string | Recipient email address |
| `details[].reply.blacklist_status.domain` | string | Domain being tested |
| `details[].reply.blacklist_status.totalBlacklist` | integer | Count of blacklist detections |
| `details[].reply.blacklist_status.totalTestedOk` | integer | Count of successful tests |
| `details[].reply.blacklist_status.totalTests` | integer | Total tests performed |
| `details[].reply.blacklist_status.totalTimedOut` | integer | Count of timed-out tests |
