# Create an Email Account

## Overview

**Description:** "This endpoint creates/updates a specific email account based on the id provided in the JSON body"

**HTTP Method:** POST

**Full URL:** `https://server.smartlead.ai/api/v1/email-accounts/save`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | integer | No | `2849` | Email ID. Set null to create new email account |
| `from_name` | string | No | `Ramesh` | User's name |
| `from_email` | string | No | `example@email` | User email address |
| `user_name` | string | No | `ramesh12` | Username for authentication |
| `password` | string | No | `gjfsvtyrqpemuqzf` | User's password |
| `smtp_host` | string | No | `smtp.gmail.com` | Mail SMTP host |
| `smtp_port` | integer | No | `465` | Mail SMTP port |
| `imap_host` | string | No | `imap.google.com` | IMAP host URL |
| `imap_port` | integer | No | `993` | IMAP port number |
| `max_email_per_day` | integer | No | `100` | Maximum number of emails per day |
| `custom_tracking_url` | string | No | `""` | Custom email tracking URL |
| `bcc` | string | No | `''` | Email BCC address |
| `signature` | string | No | `""` | Email signature |
| `warmup_enabled` | boolean | No | `false` | Set true to enable warmup feature |
| `total_warmup_per_day` | integer | No | null | Total warmup emails per day |
| `daily_rampup` | integer | No | null | Daily rampup number; set to enable ramping |
| `reply_rate_percentage` | integer | No | null | Reply rate in percentage |
| `client_id` | integer | No | null | Client ID for assignment |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/save?api_key=${API_KEY} \
  --data '{
    "id": 2849,
    "from_name": "Ramesh",
    "from_email": "ramesh@five2one.com.au",
    "user_name": "ramesh@five2one.com.au",
    "password": "gjfsvtyrqpemuqzf",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "max_email_per_day": 100,
    "custom_tracking_url": "",
    "bcc": "",
    "signature": "",
    "warmup_enabled": false,
    "total_warmup_per_day": null,
    "daily_rampup": null,
    "reply_rate_percentage": null,
    "client_id": null
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Email account added/updated successfully!",
  "emailAccountId": 2849,
  "warmupKey": "apple-keyes"
}
```

### Error Response - Account Already Exists (400)

```json
{
  "ok": false,
  "message": "Email account already exist. Please pass id to update it",
  "errorCode": "ACCOUNT_ALREADY_EXIST",
  "emailAccountId": 123
}
```

### Error Response - Account Not Found (404)

```json
{
  "ok": false,
  "message": "Email account not found!",
  "errorCode": "ACCOUNT_NOT_FOUND"
}
```

### Error Response - Verification Failed (404)

```json
{
  "ok": false,
  "message": "Email account verification failed. Please verify account details.",
  "errorCode": "ACCOUNT_VERIFICATION_FAILED",
  "error": "error message"
}
```

---

## Notes

- Set `id` to `null` when creating a new email account
- Set `id` to an existing account number to update that account
- Set `warmup_enabled` to `true` to activate email warmup features
