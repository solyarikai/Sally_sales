# Add Email Account to a Campaign

## Overview

This endpoint enables users to attach an email account to a specific campaign for sending outreach emails.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | N/A | The ID of the campaign to which the email account will be added |

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Request Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `email_account_ids` | array (integer) | Yes | `[2907]` | Array of email account IDs to add to the campaign |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts?api_key=${API_KEY} \
  --data '{"email_account_ids": [2907]}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "result": [
    {
      "id": 46417,
      "email_campaign_id": 1353,
      "email_account_id": 2907,
      "updated_at": "2022-11-07T15:28:18.171Z"
    }
  ]
}
```

### Error Response (400)

```json
{
  "error": "Email account id - 297 not allowed. Permission Error."
}
```
