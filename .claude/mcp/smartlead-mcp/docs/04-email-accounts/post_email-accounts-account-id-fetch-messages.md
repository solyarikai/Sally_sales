# Fetch Messages for Email Account

## Overview
Retrieves recent messages from a given email account's mailbox by proxying the request directly to the mailbox.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/{account_id}/fetch-messages`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | number | Yes | The unique identifier of the email account |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

## Request Body

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | number | No | 100 | Messages per account (range: 1-500) |
| `folder` | string | No | all folders | Specific folder to fetch from |
| `includeBody` | boolean | No | false | Include message body content |
| `from` | string (ISO date-time) | No | now - 24 hours | Start time range for messages |
| `to` | string (ISO date-time) | No | now | End time range for messages |

---

## Request Example

```bash
curl --location 'https://server.smartlead.ai/api/v1/email-accounts/{account_id}/fetch-messages?api_key={API_KEY}' \
--header 'Content-Type: application/json' \
--data '{
  "limit": 2,
  "folder": "SENT",
  "includeBody": true,
  "from": "2025-08-06T00:00:00.000Z",
  "to": "2025-08-08T23:59:59.000Z"
}'
```

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "accountId": "11137698",
  "data": {
    "messages": [
      {
        "messageId": "198234f5df9fb252",
        "threadId": "198845f9fb252",
        "gmailMessageId": "<3f04eea3-fc24-slw94-4961-ab09-c8234e5961c9@asdsad.com>",
        "subject": "Annual Offer",
        "from": "Jon Doe <jon.doe@someone.com>",
        "to": "jane@recepient.com",
        "timestamp": "2025-08-08T14:56:54.000Z",
        "date": "Fri, 08 Aug 2025 14:56:54 +0000",
        "folders": [
          {
            "id": "SENT",
            "name": "SENT"
          }
        ],
        "labelIds": ["SENT"],
        "snippet": "Our annual discount offer is now live",
        "sizeEstimate": 1415,
        "historyId": "2169",
        "body": {
          "text": "Our annual discount offer is now live",
          "html": "Our annual discount offer is now live"
        }
      }
    ],
    "totalCount": 6,
    "processedCount": 2,
    "folders": [
      {
        "name": "SENT",
        "count": 2
      }
    ]
  }
}
```
