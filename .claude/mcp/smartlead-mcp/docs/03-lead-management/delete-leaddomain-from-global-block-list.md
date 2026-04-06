# Delete Lead/Domain from Global Block List

## Overview

This endpoint removes a lead or domain from the global block list.

**Description:** "This endpoint deletes a lead/domain from the global block list"

---

## API Endpoint

```
DELETE https://server.smartlead.ai/api/v1/leads/delete-domain-block-list
```

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `id` | number | Yes | — | ID of the global block list entry to be deleted |

---

## Request Examples

### cURL

```bash
curl --location --request DELETE \
  'https://server.smartlead.ai/api/v1/leads/delete-domain-block-list?id=224318273&api_key=API_KEY'
```

---

## Response Examples

### Success Response (200)

```json
{}
```

**Response Schema:**
- `id` (integer): Entry identifier
- `email_or_domain` (string): Email address or domain removed
- `created_at` (string): Creation timestamp
- `source` (string): Origin of the block entry
- `client_id` (optional): Associated client identifier
