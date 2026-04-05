# Remove Email Account from a Campaign

## Overview

This endpoint allows you to delete an email account from a campaign.

**HTTP Method:** `DELETE`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign_id` | string | Yes | `campaign_id` | The campaign ID where the email account belongs |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_accounts_ids` | array (integer) | Yes | Array of email account IDs to remove from the campaign |

```json
{
  "email_accounts_ids": [2907]
}
```

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/email-accounts?api_key=${API_KEY} \
  --request DELETE \
  --data '{"email_accounts_ids": [2907]}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "result": 1
}
```

### Error Response (400)

```json
{
  "error": "Email account id - 297 not allowed. Permission Error."
}
```

### Error Response (404)

```json
{
  "error": "Campaign not found - Invalid campaign_id."
}
```
