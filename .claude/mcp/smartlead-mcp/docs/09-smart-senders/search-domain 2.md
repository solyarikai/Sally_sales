# Search Domain

## Overview

This API searches for available domains priced at $15 or less from specified vendors.

**HTTP Method:** `GET`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/search-domain`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Authentication key for API request authorization |
| `domain_name` | string | No | Domain name for which availability is being requested |
| `vendor_id` | integer (int32) | No | Unique identifier of the vendor processing the domain request |

---

## Request Example

```bash
curl --location --globoff 'https://smart-senders.smartlead.ai/api/v1/smart-senders/search-domain?api_key={api_key}&vendor_id=1&domain_name=techbuildemo' \
--data ''
```

---

## Response Examples

### Success Response (200)

```json
{
  "domain": "techbuildemo.com",
  "available": true,
  "suggestions": [
    {"domain": "techbuildemo24.com"},
    {"domain": "thetechbuildemo.com"},
    {"domain": "techbuildemoweb.com"},
    {"domain": "techbuildemogroup.com"},
    {"domain": "techbuildemostudio.com"}
  ]
}
```

**Response Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | The domain name that was searched for |
| `available` | boolean | Indicates whether domain is available for registration |
| `suggestions` | array | Alternative available domain suggestions |
| `suggestions[].domain` | string | Suggested domain name |

### Error Response (400)

```json
{
  "status": "error",
  "message": "\"domain_name\" is required",
  "context": "Error searching domain"
}
```
