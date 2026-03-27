# DKIM Details

## Overview

Authentication - Pass or Fail. Note DKIM for the same sender mailbox can Pass for few receiver accounts and Fail for some due to several reasons.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/dkim-details`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer | Yes | Unique identifier for the spam test |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/dkim-details?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "from_email": "harrisonmarganza@outlook.com",
    "seed_accounts": [
      {
        "to_email": "romal.smart.lead@gmail.com",
        "dkim_result": {
          "dkim": "mx.google.com; dkim=pass header.i=@outlook.com header.s=selector1 header.b=OQ2JynO8; arc=pass (i=1); spf=pass (google.com: domain of harrisonmarganza@outlook.com designates 2a01:111:f403:2c14::825 as permitted sender) smtp.mailfrom=harrisonmarganza@outlook.com; dmarc=pass (p=NONE sp=QUARANTINE dis=NONE) header.from=outlook.com",
          "status": "PASS"
        }
      },
      {
        "to_email": "sydney.m@alwaysinprimary.com",
        "dkim_result": {
          "dkim": "dkim=pass (signature was verified) header.d=outlook.com",
          "status": "PASS"
        }
      }
    ]
  }
]
```

### Error Response (400)

```json
{}
```

---

## Response Schema

| Property | Type | Description |
|----------|------|-------------|
| `from_email` | string | Sender's email address |
| `seed_accounts` | array | Array of test recipient accounts |
| `to_email` | string | Recipient email address for the test |
| `dkim_result` | object | DKIM authentication result |
| `dkim_result.dkim` | string | Detailed DKIM authentication header information |
| `dkim_result.status` | string | Authentication status (PASS or FAIL) |

## Notes

- Multiple recipients may show different DKIM results for the same sender mailbox
- DKIM authentication can pass for some recipients while failing for others depending on recipient email provider configurations
