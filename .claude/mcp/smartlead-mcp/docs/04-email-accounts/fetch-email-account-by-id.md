# Fetch Email Account By ID

## Overview

**Description:** "This endpoint gets all email details by Account ID"

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/{account_id}/`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id` | string | Yes | `account_id` | User's account ID |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |
| `fetch_campaigns` | boolean | No | — | Fetches campaigns associated to the mailbox |
| `fetch_tags` | boolean | No | — | Fetches tags associated to the mailbox |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/{account_id}/?api_key={API_KEY}
```

---

## Success Response (200)

```json
{
  "id": 106466,
  "created_at": "2023-04-18T09:02:46.060Z",
  "updated_at": "2023-05-30T06:06:20.587Z",
  "user_id": 2,
  "from_name": "Vaibhav",
  "from_email": "vaibhav@five2one.engineering",
  "username": "vaibhav@five2one.engineering",
  "password": "xuF_aj4u",
  "smtp_host": "smtp.zoho.com.au",
  "smtp_port": 465,
  "smtp_port_type": "SSL",
  "message_per_day": 200,
  "different_reply_to_address": "",
  "is_different_imap_account": false,
  "imap_username": "",
  "imap_password": "",
  "imap_host": "imap.zoho.com.au",
  "imap_port": 993,
  "imap_port_type": "SSL",
  "signature": null,
  "custom_tracking_domain": "",
  "bcc_email": null,
  "is_smtp_success": true,
  "is_imap_success": true,
  "smtp_failure_error": null,
  "imap_failure_error": null,
  "type": "SMTP",
  "daily_sent_count": 0,
  "client_id": null,
  "warmup_details": {
    "id": 99200,
    "status": "INACTIVE",
    "created_at": "2023-04-18T09:02:54.822507+00:00",
    "reply_rate": 20,
    "warmup_key_id": "brass-sleep",
    "blocked_reason": null,
    "total_sent_count": 7,
    "total_spam_count": 0,
    "warmup_max_count": 40,
    "warmup_min_count": 3,
    "is_warmup_blocked": false,
    "max_email_per_day": 40,
    "warmup_reputation": "100%"
  }
}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Account identifier |
| `from_name` | string | Sender's display name |
| `from_email` | string | Sender's email address |
| `smtp_host` | string | SMTP server hostname |
| `smtp_port` | integer | SMTP port number |
| `message_per_day` | integer | Daily message limit |
| `type` | string | Account type (SMTP, GMAIL, ZOHO, OUTLOOK) |
| `is_smtp_success` | boolean | SMTP connection status |
| `is_imap_success` | boolean | IMAP connection status |
| `warmup_details` | object | Email warmup configuration and stats |
| `warmup_details.status` | string | Warmup status (ACTIVE/INACTIVE) |
| `warmup_details.warmup_reputation` | string | Reputation percentage |
