# Get Search Analytics API Documentation

## Overview

Returns search analytics: leads found, emails fetched (current vs previous month with trend), available credits, leads found today, and optional filter-specific data.

**HTTP Method:** GET

**URL:** `https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-analytics`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | API key for authentication |
| `filter_id` | string | No | Optional filter ID to get analytics for a specific filter |

---

## Request Example

```bash
curl -X GET "https://prospect-api.smartlead.ai/api/v1/search-email-leads/search-analytics?api_key=YOUR_API_KEY&filter_id=327105"
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "leadsFound": {
      "current": 1200,
      "previousMonth": 1000,
      "percentageChange": 20,
      "percentageChangeText": "+20%",
      "trend": "increase",
      "total": 5000
    },
    "emailsFetched": {
      "current": 1100,
      "previousMonth": 950,
      "percentageChange": 15.79,
      "percentageChangeText": "+15.79%",
      "trend": "increase",
      "total": 4500
    },
    "availableCredits": {
      "available": 500,
      "total": 1000,
      "used": 500
    },
    "leadsFoundToday": 50,
    "filterData": {
      "leadsFound": 200,
      "emailsFetched": 180
    },
    "maxDailyFetchLimit": 1000,
    "maxSingleFetchLimit": 500
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
| `data.leadsFound.current` | number | Current month leads |
| `data.leadsFound.previousMonth` | number | Previous month leads |
| `data.leadsFound.trend` | string | "increase", "decrease", or "no_change" |
| `data.leadsFound.total` | number | Total leads found |
| `data.emailsFetched` | object | Same structure as leadsFound |
| `data.availableCredits.available` | number | Available credits |
| `data.availableCredits.total` | number | Total credits |
| `data.availableCredits.used` | number | Used credits |
| `data.leadsFoundToday` | number | Leads found today |
| `data.filterData` | object | Present only when filter_id provided |
| `data.maxDailyFetchLimit` | number | Maximum daily fetch limit |
| `data.maxSingleFetchLimit` | number | Maximum single fetch limit |
