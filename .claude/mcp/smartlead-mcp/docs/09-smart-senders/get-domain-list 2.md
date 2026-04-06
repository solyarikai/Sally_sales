# Get Purchased Domain List

## Overview

Retrieve the complete list of domains purchased through SmartSenders platform.

**HTTP Method:** `GET`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/get-domain-list`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key used to authenticate and authorize the request |

---

## Request Example

```bash
curl --location 'https://smart-senders.smartlead.ai/api/v1/smart-senders/get-domain-list?api_key={api_key}'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 58147,
    "domain_name": "smartleadsuccessai.com",
    "vendor_id": 4,
    "created_at": "2025-06-23T11:12:57.727Z",
    "updated_at": "2025-08-25T11:40:03.472Z",
    "forwarding_domain": "smartlead.ai",
    "is_active": true,
    "order_id": "757915"
  }
]
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique ID of the purchased domain record in Smartlead |
| `domain_name` | string | The purchased domain name |
| `vendor_id` | integer | Vendor identifier from which the domain was purchased/managed |
| `created_at` | string (ISO 8601) | Timestamp when this domain record was created in the system |
| `updated_at` | string (ISO 8601) | Timestamp when this domain record was last updated |
| `forwarding_domain` | string | The domain to which this purchased domain is configured to forward |
| `is_active` | boolean | Indicates whether this domain is currently active and usable |
| `order_id` | string | Vendor/order reference ID associated with the domain purchase |

### Error Response (400)

```json
{}
```
