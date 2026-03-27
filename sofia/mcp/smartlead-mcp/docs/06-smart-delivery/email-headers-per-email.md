# Email Reply Headers

## Overview

Details of the email headers for each email.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/:spamTestId/sender-account-wise/:replyId/email-headers`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `spamTestId` | integer | Yes | The ID of the spam test |
| `replyId` | string | Yes | The ID of the specific email reply to retrieve headers for |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/:spamTestId/sender-account-wise/:replyId/email-headers?api_key=$(API_KEY)'
```

---

## Response Format

### Success Response (200)

Returns email header details including:
- Message ID
- Email size
- Mail folder location
- RDNS result
- SPF authentication details (result and status)
- DKIM authentication details (result and status)
- DMARC authentication details (result and status)
- Sender IP address
- Delivery time
- Blacklist status information

### Error Response (400)

Standard error response with message field indicating the failure reason.
