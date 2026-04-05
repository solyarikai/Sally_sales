# Get One-Time Password for Admin Mailbox

## Overview

This endpoint generates a one-time password (OTP) for authentication purposes related to admin mailbox access within the Smart Senders system.

**HTTP Method:** `GET`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/auth-secret`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key used to authenticate and authorize the request |
| `email_account` | string | Yes | The email address for which the OTP should be generated |

## Request Body

No request body required.

---

## Request Example

```bash
curl --location 'https://smart-senders.smartlead.ai/api/v1/smart-senders/auth-secret?api_key=YOUR_API_KEY&email_account=test@smartlead.ai' \
--header 'accept: application/json'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "otp": "773283",
    "mailbox": "test@smartlead.ai",
    "order_id": "xx-xxxx-xxx-xx"
  }
}
```

### Response Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful request processing |
| `data.otp` | string | The one-time password generated for verification |
| `data.mailbox` | string | The email address for which the OTP was generated |
| `data.order_id` | string | Unique order reference ID associated with the request |

---

## Notes

- The OTP is temporary and intended for admin mailbox verification workflows
