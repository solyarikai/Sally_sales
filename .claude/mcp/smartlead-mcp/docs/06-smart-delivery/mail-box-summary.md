# Mailbox Summary

## Overview
Retrieves a list of mailboxes used for Smart Delivery Tests along with their overall performance metrics across all tests.

## Endpoint

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/mailboxes-summary`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/mailboxes-summary?api_key=YOUR_API_KEY'
```

---

## Response Examples

### Success Response (200)

Returns mailbox summary information containing overall performance data across tests.

```json
{
  "mailbox_data": [
    {
      "mailbox_id": "string",
      "mailbox_name": "string",
      "total_tests": "integer",
      "inbox_count": "integer",
      "spam_count": "integer",
      "performance_metrics": "object"
    }
  ]
}
```

### Error Response (400)

```json
{
  "message": "Error description"
}
```

## Notes

- This endpoint provides aggregate mailbox performance data
- Results include statistics from all associated Smart Delivery Tests
