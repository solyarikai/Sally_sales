# rDNS Report

## Overview
Check if rDNS was correct for an IP sending the email. Use mxtoolbox to verify and fix the rDNS for your IP.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/rdns-details`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |
| `spamTestId` | integer | Yes | - | The ID of the Spam Test |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/rdns-details?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "from_email": "harrisonmarganza@yahoo.com",
    "seed_accounts": [
      {
        "to_email": "romal.smart.lead@gmail.com",
        "rdns_result": {
          "rdns": "mtaproxy3.free.mail.vip.gq1.yahoo.com",
          "status": true
        }
      },
      {
        "to_email": "t.carter@servicebuilderapps.com",
        "rdns_result": {
          "rdns": "mtaproxy3.free.mail.vip.gq1.yahoo.com",
          "status": true
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

| Field | Type | Description |
|-------|------|-------------|
| `from_email` | string | Sender email address |
| `seed_accounts` | array | Array of seed account results |
| `seed_accounts[].to_email` | string | Recipient email address |
| `seed_accounts[].rdns_result` | object | rDNS validation result |
| `seed_accounts[].rdns_result.rdns` | string | rDNS hostname |
| `seed_accounts[].rdns_result.status` | boolean | Whether rDNS validation passed (true/false) |
