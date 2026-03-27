# Sender Account Wise Report

## Overview

This endpoint provides test results broken down by each mailbox from a Smart Delivery spam test. It delivers detailed information about emails from each sender account.

## API Endpoint

**Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/sender-account-wise`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `spamTestId` | integer | Yes | — | The ID of the spam test |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/sender-account-wise?api_key=${API_KEY}'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "email": "harrisonmarganza@outlook.com",
    "details": [
      {
        "id": 5,
        "email": "romal.jam.list@gmail.com",
        "reply": {
          "id": "23153",
          "uid": "882",
          "message_id": "<cc3a1e1d-c0df-sd93-44b2-b54d-7b7b2e1bfd81-e543ab0c-d1cc-433e-82f2-391e825ecaba@outlook.com>",
          "email_size": "14 kb",
          "mail_folder": "Inbox",
          "rdns_result": "",
          "spf_result": {
            "spf": "google.com: domain of harrisonmarganza@outlook.com designates 2a01:111:f403:2c14::825 as permitted sender",
            "status": "PASS"
          },
          "dkim_result": {
            "dkim": "mx.google.com; dkim=pass header.i=@outlook.com...",
            "status": "PASS"
          },
          "dmarc_result": {
            "dmarc": "mx.google.com; dkim=pass...",
            "status": "PASS"
          },
          "sender_ip": "",
          "delivered_in": 3,
          "blacklist_status": {
            "domain": "outlook.com",
            "totalBlacklist": 0,
            "totalTestedOk": 213,
            "totalTests": 222,
            "totalTimedOut": 9
          }
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
| `email` | string | Sender email address |
| `details` | array | Array of email delivery details |
| `details[].id` | integer | Unique identifier |
| `details[].email` | string | Recipient email address |
| `details[].reply.id` | string | Reply message ID |
| `details[].reply.uid` | string | Unique identifier in mailbox |
| `details[].reply.message_id` | string | RFC 2822 message identifier |
| `details[].reply.email_size` | string | Message size |
| `details[].reply.mail_folder` | string | Folder location (e.g., Inbox) |
| `details[].reply.spf_result` | object | SPF authentication result with status |
| `details[].reply.dkim_result` | object | DKIM authentication result with status |
| `details[].reply.dmarc_result` | object | DMARC authentication result with status |
| `details[].reply.sender_ip` | string | Sending IP address |
| `details[].reply.delivered_in` | integer | Delivery time in seconds |
| `details[].reply.blacklist_status` | object | Domain blacklist check results |
| `details[].reply.blacklist_status.totalBlacklist` | integer | Count of blacklist hits |
| `details[].reply.blacklist_status.totalTestedOk` | integer | Successful tests |
| `details[].reply.blacklist_status.totalTests` | integer | Total tests run |
