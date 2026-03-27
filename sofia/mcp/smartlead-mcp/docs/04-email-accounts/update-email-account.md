# Update Email Account

## Overview
This endpoint modifies settings for an existing email account.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}`

---

## Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `email_account_id` | string | Yes | ID of the email account to update |

## Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `max_email_per_day` | integer | No | `100` | Maximum number of emails to send daily |
| `custom_tracking_url` | string | No | `""` | Custom email tracking URL |
| `bcc` | string | No | `hello@smartlead.com` | Email BCC address |
| `signature` | string | No | `Thanks,<br>Ramesh Kumar M` | Email signature |
| `client_id` | integer | No | `22` | Client ID (null if not needed) |
| `time_to_wait_in_mins` | integer | No | `3` | Minimum minutes between emails using this account |
| `is_suspended` | boolean | No | — | Optional field to suspend account |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}?api_key={API_KEY} \
  --data '{
    "max_email_per_day": 100,
    "custom_tracking_url": "",
    "bcc": "ramesh@five2one.com.au",
    "signature": "Thanks,<br>Ramesh Kumar M",
    "client_id": 22,
    "time_to_wait_in_mins": 3,
    "is_suspended": false
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Email account details updated successfully!",
  "emailAccountId": 10607
}
```
