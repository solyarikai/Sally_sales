# Add/Update Warmup To Email Account

## Overview

**Description:** "This endpoint lets you add / update the warmup settings to an email account"

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}/warmup`

---

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_account_id` | string | Yes | The unique identifier for the email account to update |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `warmup_enabled` | string | No | `"true"` | Set to false to disable warmup functionality |
| `total_warmup_per_day` | integer | No | `35` | Total number of warmup emails to send daily |
| `daily_rampup` | integer | No | `2` | Daily increment value for warmup email volume |
| `reply_rate_percentage` | string | No | `"30"` | Target reply rate percentage |
| `warmup_key_id` | string | No | `"apple-juice"` | Custom identifier for warmup key tracking |
| `auto_adjust_warmup` | string | No | — | Enable/disable automatic adjustment of warmup-to-sending ratio |
| `is_rampup_enabled` | string | No | — | Enable or disable rampup functionality |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/email-accounts/{email_account_id}/warmup?api_key={API_KEY} \
  --data '{
    "warmup_enabled": true,
    "total_warmup_per_day": 35,
    "daily_rampup": 9,
    "reply_rate_percentage": 38,
    "auto_adjust_warmup": true,
    "is_rampup_enabled": false,
    "warmup_key_id": "apple-juice"
  }'
```

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Email warmup details updated successfully!",
  "emailAccountId": 10607,
  "warmupKey": "banan-apple"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Operation success indicator |
| `message` | string | Confirmation message |
| `emailAccountId` | integer | ID of the updated email account |
| `warmupKey` | string | Generated or updated warmup key identifier |
