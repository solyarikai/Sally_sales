# Get Provider-wise Overall Performance

## Overview
Retrieve provider-wise overall performance metrics for mailboxes across your account.

**HTTP Method:** GET

**URL:** `https://server.smartlead.ai/api/v1/analytics/mailbox/provider-wise-overall-performance`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (Max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (Max 100) |
| `full_data` | string | No | — | Set to "true" for detailed metrics |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/mailbox/provider-wise-overall-performance?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

---

## Response Format

### Success Response (200)

```json
{
  "success": true,
  "message": "Email providers performance overview fetched successfully",
  "data": {
    "email_providers_performance_overview": {
      "overall": [
        {
          "email_provider": "GMAIL",
          "sent": "3596",
          "opened": "0",
          "replied": "702",
          "positive_replied": "10",
          "bounced": "69",
          "unique_lead_count": "2325",
          "unique_open_count": "0",
          "open_rate": "0.00%",
          "reply_rate": "30.19%",
          "positive_reply_rate": "1.42%",
          "bounce_rate": "2.97%"
        },
        {
          "email_provider": "OUTLOOK",
          "sent": "9",
          "opened": "0",
          "replied": "2",
          "positive_replied": "0",
          "bounced": "0",
          "unique_lead_count": "5",
          "unique_open_count": "0",
          "open_rate": "0.00%",
          "reply_rate": "40.00%",
          "positive_reply_rate": "0.00%",
          "bounce_rate": "0.00%"
        }
      ],
      "tag_wise": [
        {
          "email_provider": "GMAIL",
          "tag_id": 52739,
          "tag_name": "MyTag1",
          "tag_color": "#FCC7B1",
          "sent": "290",
          "opened": "0",
          "replied": "24",
          "positive_replied": "0",
          "bounced": "3",
          "unique_lead_count": "79",
          "unique_open_count": "0",
          "open_rate": "0.00%",
          "reply_rate": "30.38%",
          "positive_reply_rate": "0.00%",
          "bounce_rate": "3.80%"
        }
      ]
    }
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates successful API call |
| `message` | string | Descriptive message about the response |
| `data.email_providers_performance_overview.overall` | array | Provider performance aggregates |
| `data.email_providers_performance_overview.tag_wise` | array | Provider performance broken down by tags |
| `[].email_provider` | string | Email provider name (GMAIL, OUTLOOK, etc.) |
| `[].sent` | string | Total emails sent |
| `[].opened` | string | Total emails opened |
| `[].replied` | string | Total email replies received |
| `[].positive_replied` | string | Positive responses received |
| `[].bounced` | string | Total bounced emails |
| `[].unique_lead_count` | string | Number of unique leads contacted |
| `[].unique_open_count` | string | Number of unique opens |
| `[].open_rate` | string | Open rate percentage |
| `[].reply_rate` | string | Reply rate percentage |
| `[].positive_reply_rate` | string | Positive reply rate percentage |
| `[].bounce_rate` | string | Bounce rate percentage |

---

## Notes

- The "overall" section provides aggregated metrics across all providers
- The "tag_wise" section breaks down performance by email account tags when available
- Responses include both counts and calculated percentage rates
