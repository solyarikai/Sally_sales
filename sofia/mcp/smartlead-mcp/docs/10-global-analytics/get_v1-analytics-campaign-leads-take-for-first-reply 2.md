# Get Leads Take for First Reply API

## Overview

Retrieve statistics on how many leads it takes to achieve the first reply in your campaigns.

**HTTP Method:** `GET`

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/campaign/leads-take-for-first-reply`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | API authentication key for authorization |
| `start_date` | string (date) | Yes | - | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | - | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/campaign/leads-take-for-first-reply?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31&client_ids=123,456&campaign_ids=789,101112"
```

---

## Response

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "First reply stats fetched successfully!",
  "data": {
    "leads_take_for_first_reply": 9
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Descriptive message about the response |
| `data.leads_take_for_first_reply` | number | Average number of leads contacted to achieve first reply |
