# Sender Account List

## Overview
Retrieves a list of all sender accounts selected for a specific Spam Test.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/{spamTestId}/sender-accounts`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer (int32) | Yes | The ID of the Spam Test |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/sender-accounts?api_key=${API_KEY}'
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
          "message_id": "<cc3a1e1d-c0df-sd93-44b2-b54d-7b7b2e1bfd81@outlook.com>",
          "email_size": "14 kb",
          "mail_folder": "Inbox",
          "rdns_result": "",
          "spf_result": { "spf": "...", "status": "PASS" },
          "dkim_result": { "dkim": "...", "status": "PASS" },
          "dmarc_result": { "dmarc": "...", "status": "PASS" },
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

| Property | Type | Description |
|----------|------|-------------|
| `email` | string | The sender email account address |
| `details` | array | Array containing email delivery details |
| `details[].id` | integer | Unique identifier for the detail record |
| `details[].email` | string | Recipient email address |
| `details[].reply.id` | string | Message identifier |
| `details[].reply.uid` | string | Unique identifier in mailbox |
| `details[].reply.message_id` | string | RFC message ID |
| `details[].reply.email_size` | string | Size of the email |
| `details[].reply.mail_folder` | string | Folder where email was delivered |
| `details[].reply.spf_result` | object | SPF authentication result with status |
| `details[].reply.dkim_result` | object | DKIM authentication result with status |
| `details[].reply.dmarc_result` | object | DMARC authentication result with status |
| `details[].reply.sender_ip` | string | IP address of sending server |
| `details[].reply.delivered_in` | integer | Delivery time in seconds |
| `details[].reply.blacklist_status` | object | IP/domain blacklist status |
| `details[].reply.blacklist_status.totalBlacklist` | integer | Number of blacklists where domain appears |
| `details[].reply.blacklist_status.totalTestedOk` | integer | Successful blacklist tests |
| `details[].reply.blacklist_status.totalTests` | integer | Total blacklist tests performed |
| `details[].reply.blacklist_status.totalTimedOut` | integer | Tests that timed out |
