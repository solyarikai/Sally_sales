# SPF Details

## Overview

Check if your SPF Authentication was a Pass or Fail.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/spf-details`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |
| `spamTestId` | integer | Yes | — | The ID of the Spam Test |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/spf-details?api_key=$(API_KEY)'
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
        "spf_result": {
          "spf": "google.com: domain of harrisonmarganza@outlook.com designates 2a01:111:f403:2c14::825 as permitted sender",
          "status": "PASS"
        }
      },
      {
        "to_email": "sydney.m@alwaysinprimary.com",
        "spf_result": {
          "spf": "Pass (protection.outlook.com: domain of outlook.com designates 40.92.22.84 as permitted sender)",
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
| `from_email` | string | The sender email address used in the test |
| `seed_accounts` | array | Array of seed account test results |
| `seed_accounts[].to_email` | string | The recipient/seed email address |
| `seed_accounts[].spf_result` | object | SPF authentication result object |
| `seed_accounts[].spf_result.spf` | string | Detailed SPF check result message |
| `seed_accounts[].spf_result.status` | string | Authentication status (PASS or FAIL) |

## Notes

- SPF results are provided for each seed account tested
- A "PASS" status indicates proper SPF authentication
- Results vary by recipient due to different ISP implementations
