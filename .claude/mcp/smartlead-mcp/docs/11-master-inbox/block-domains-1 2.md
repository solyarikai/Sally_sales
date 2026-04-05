# Block Domains API Documentation

## Overview

Add domains to the global block list.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/block-domains`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body (JSON)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domains` | array(string) | Yes | List of domain names to block (min 1 item) |
| `source` | string | Yes | Source of the block request |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/block-domains?api_key={API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["example-spam.com", "unwanted-domain.net"],
    "source": "manual"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Domains blocked successfully",
  "data": {
    "blocked_domains": 2
  }
}
```

### Error Response (400)

```json
{}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```
