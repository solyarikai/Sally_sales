# Mailbox Count

## Overview
Shows the count of all the Mailboxes that were used for any Spam test.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/mailboxes-count`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/mailboxes-count?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

Returns mailbox count data.

```json
{
  "mailboxCount": 5
}
```

### Error Response (400)

```json
{
  "message": "error description"
}
```
