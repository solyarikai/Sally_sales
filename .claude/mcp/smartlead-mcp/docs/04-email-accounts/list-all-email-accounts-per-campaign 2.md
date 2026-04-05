# List all email accounts per campaign

## Overview
This endpoint fetches all the email accounts used for sending emails to leads in the campaign.

**HTTP Method:** `GET`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts`

### Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The ID of the campaign for which to fetch email accounts |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts?api_key={API_KEY}
```

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 24,
    "created_at": "2022-05-26T03:47:31.448094+00:00",
    "updated_at": "2022-05-26T03:47:31.448094+00:00",
    "user_id": 123,
    "from_name": "Cristiano Rolando",
    "from_email": "cristiano@mufc.com",
    "username": "cristiano@mufc.com",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 993,
    "smtp_port_type": "SSL",
    "message_per_day": 100,
    "different_reply_to_address": "",
    "is_different_imap_account": false,
    "imap_username": "cristiano@mufc.com",
    "imap_host": "imap.gmail.com",
    "imap_port": 495,
    "imap_port_type": "SSL",
    "signature": "",
    "custom_tracking_domain": "http://emailtracking.goldenboot.com",
    "bcc_email": "",
    "is_smtp_success": true,
    "is_imap_success": true,
    "smtp_failure_error": "",
    "imap_failure_error": "",
    "type": "GMAIL",
    "daily_sent_count": 48
  }
]
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Email account identifier |
| `created_at` | timestamp | Account creation timestamp |
| `updated_at` | timestamp | Last update timestamp |
| `user_id` | integer | Associated user identifier |
| `from_name` | string | Display name for sender |
| `from_email` | string | Sender email address |
| `username` | string | SMTP username |
| `smtp_host` | string | SMTP server hostname |
| `smtp_port` | integer | SMTP port number |
| `smtp_port_type` | string | Port encryption type (SSL/TLS) |
| `message_per_day` | integer | Daily sending limit |
| `type` | string | Account type (GMAIL, OUTLOOK, ZOHO, SMTP) |
| `daily_sent_count` | integer | Emails sent today |
| `is_smtp_success` | boolean | SMTP connection status |
| `is_imap_success` | boolean | IMAP connection status |
