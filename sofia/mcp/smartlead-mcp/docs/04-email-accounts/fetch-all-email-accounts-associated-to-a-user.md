# Fetch all Email Accounts Associated to a User

## Overview

This endpoint retrieves all email accounts configured for sending emails to leads within campaigns.

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | API_KEY | Authentication credential |
| `offset` | integer | No | 0 | Pagination offset (minimum: 0) |
| `limit` | integer | No | 100 | Results per page (maximum: 100) |
| `username` | string | No | — | Filter by exact email username match |
| `client_id` | string | No | — | Required Client ID for filtering |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/?api_key={API_KEY}&offset=0&limit=10
```

---

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
    "is_different_imap_account": false,
    "imap_username": "cristiano@mufc.com",
    "imap_host": "imap.gmail.com",
    "imap_port": 495,
    "imap_port_type": "SSL",
    "type": "GMAIL",
    "daily_sent_count": 48,
    "client_id": 33,
    "warmup_details": {
      "id": 99200,
      "status": "INACTIVE",
      "total_sent_count": 7,
      "total_spam_count": 0,
      "warmup_reputation": "100%"
    }
  }
]
```
