# Get Lead Category-wise Response API Documentation

## Endpoint Overview

**Title:** Get Lead Category-wise Response

**Description:** Retrieve lead responses organized by different response categories and sentiment types.

**HTTP Method:** `GET`

**Endpoint:** `https://server.smartlead.ai/api/v1/analytics/lead/category-wise-response`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | API authentication key for request validation |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (max 100) |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/lead/category-wise-response?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31&client_ids=123&campaign_ids=456"
```

---

## Response Format

### Success Response (200)

```json
{
  "success": true,
  "message": "Category-wise responses fetched successfully!",
  "data": {
    "lead_responses_by_category": {
      "filter": [
        {
          "sentiment_type": "positive"
        },
        {
          "sentiment_type": "neutral"
        },
        {
          "sentiment_type": "negative"
        }
      ],
      "leadResponseGrouping": [
        {
          "total_response": 20267,
          "name": "Uncategorized",
          "percentage": "87.71%"
        },
        {
          "total_response": 46,
          "name": "Interested",
          "sentiment_type": "positive",
          "percentage": "0.2%"
        },
        {
          "total_response": 4,
          "name": "Wrong Person",
          "sentiment_type": "neutral",
          "percentage": "0.02%"
        },
        {
          "total_response": 18,
          "name": "Do Not Contact",
          "sentiment_type": "negative",
          "percentage": "0.08%"
        }
      ]
    }
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `message` | string | Status message |
| `data.lead_responses_by_category.filter` | array | Available sentiment type filters |
| `data.lead_responses_by_category.leadResponseGrouping` | array | Array of response category objects |
| `data.lead_responses_by_category.leadResponseGrouping[].total_response` | integer | Count of responses in category |
| `data.lead_responses_by_category.leadResponseGrouping[].name` | string | Category name |
| `data.lead_responses_by_category.leadResponseGrouping[].sentiment_type` | string | Sentiment classification (positive/neutral/negative) |
| `data.lead_responses_by_category.leadResponseGrouping[].percentage` | string | Percentage of total responses |
