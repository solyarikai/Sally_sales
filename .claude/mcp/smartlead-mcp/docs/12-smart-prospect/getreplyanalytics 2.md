# Get Reply Analytics API Documentation

## Overview

Returns reply analytics: replied count for current month vs previous month, percentage change, and trend.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/reply-analytics`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/reply-analytics?api_key=YOUR_API_KEY"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "currentMonth": {
      "replied": 150
    },
    "previousMonth": {
      "replied": 120
    },
    "percentage_change": "+25%",
    "trend": "increase"
  }
}
```

### Error Response (401)

```json
{
  "statusCode": 401,
  "success": false,
  "message": "Unauthorized",
  "error": "User not authenticated"
}
```

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `data.currentMonth.replied` | number | Reply count for current month |
| `data.previousMonth.replied` | number | Reply count for previous month |
| `data.percentage_change` | string | Percentage change (e.g., "+25%", "-10%") |
| `data.trend` | string | "increase", "decrease", or "no_change" |
