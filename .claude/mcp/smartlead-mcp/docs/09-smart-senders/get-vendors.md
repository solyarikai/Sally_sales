# Get Vendors

## Overview

Retrieves all active vendors with their corresponding IDs and performance metrics.

**HTTP Method:** `GET`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/get-vendors`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your Smartlead API Key for authentication and authorization |

---

## Request Example

```bash
curl --location --globoff 'https://smart-senders.smartlead.ai/api/v1/smart-senders/get-vendors?api_key={api_key}' \
--header 'accept: application/json'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Vendors retrieved successfully",
  "data": [
    {
      "id": 9,
      "vendor_name": "inboxkitGoogle",
      "priority": 1,
      "delivery_time": 7.18,
      "order_delivery_rate": 96.59,
      "total_orders": 88,
      "total_vendor_orders_contribution_percent": 40.74,
      "delivered_orders": 85,
      "undelivered_orders": 3,
      "pricing": {
        "domain_price": "13.00",
        "mailbox_price": "4.50",
        "currency": "USD"
      }
    },
    {
      "id": 5,
      "vendor_name": "zapmailGoogle",
      "priority": 2,
      "delivery_time": 10.76,
      "order_delivery_rate": 80,
      "total_orders": 70,
      "total_vendor_orders_contribution_percent": 32.41,
      "delivered_orders": 56,
      "undelivered_orders": 14,
      "pricing": {
        "domain_price": "13.00",
        "mailbox_price": "4.50",
        "currency": "USD"
      }
    }
  ]
}
```

### Error Response (400)

```json
{}
```

---

## Response Schema

### Root Level

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API execution |
| `message` | string | Status message describing the result |
| `data` | array | Array of vendor objects |

### Vendor Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique identifier assigned to the vendor |
| `vendor_name` | string | Name of the vendor providing services |
| `priority` | string | Rank based on system-defined priority |
| `delivery_time` | string | Average days vendor requires to deliver orders |
| `order_delivery_rate` | string | Percentage of successfully delivered orders |
| `total_orders` | string | Total number of assigned orders |
| `total_vendor_orders_contribution_percent` | string | Vendor's percentage share of total orders |
| `delivered_orders` | string | Count of successfully delivered orders |
| `undelivered_orders` | string | Count of undelivered orders |
| `pricing` | object | Vendor's pricing details |

### Pricing Object

| Field | Type | Description |
|-------|------|-------------|
| `domain_price` | string | Cost per domain purchase |
| `mailbox_price` | string | Cost per mailbox |
| `currency` | string | Currency code for pricing |
