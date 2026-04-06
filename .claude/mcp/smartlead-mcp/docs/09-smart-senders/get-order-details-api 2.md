# Get Order Details

## Overview

This API retrieves the current status and details of a specific order placed through the Smart Senders platform, including payment status and related messages.

**HTTP Method:** `GET`

**URL:** `https://smart-senders.smartlead.ai/api/v1/smart-senders/order-details`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key used to authenticate and authorize the request |
| `order_id` | string | Yes | Unique order reference ID for which details are being requested |

---

## Request Example

```bash
curl --location --globoff \
'https://smart-senders.smartlead.ai/api/v1/smart-senders/order-details?api_key={api_key}&order_id=SS-285381070623283-1948-49' \
--header 'Content-Type: application/json'
```

---

## Response Examples

### Success Response (200)

```json
{
  "status": "success",
  "message": "Order details retrieved successfully",
  "data": {
    "order_id": "SS-285381070623283-1948-49",
    "status": "Payment Pending",
    "message": "Your payment has not yet been received. Please check your card details and try again."
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" for successful requests, "error" for failed requests |
| `message` | string | Human-readable message describing the result of the request |
| `data` | object | Object containing detailed order information |
| `data.order_id` | string | Unique order reference ID |
| `data.status` | string | Current order status (e.g., "Payment Pending", "Completed", "Failed", "Cancelled") |
| `data.message` | string | Detailed message explaining current state or required user action |
