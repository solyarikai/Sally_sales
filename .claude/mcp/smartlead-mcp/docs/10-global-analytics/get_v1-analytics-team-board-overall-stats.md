# Get Team Board Overall Stats

## Description

Retrieve team board overall statistics across campaigns and leads within a specified date range.

**Method:** `GET`

**URL:** `https://server.smartlead.ai/api/v1/analytics/team-board/overall-stats`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | — | Your API authentication key |
| `start_date` | string (date) | Yes | — | Start date in YYYY-MM-DD format |
| `end_date` | string (date) | Yes | — | End date in YYYY-MM-DD format |
| `client_ids` | string | No | "" | Comma-separated client IDs to filter (max 50) |
| `campaign_ids` | string | No | "" | Comma-separated campaign IDs to filter (max 100) |
| `full_data` | string | No | — | Set to "true" for detailed metrics |

---

## Request Example

```bash
curl -X GET "https://server.smartlead.ai/api/v1/analytics/team-board/overall-stats?api_key=YOUR_API_KEY&start_date=2024-01-01&end_date=2024-01-31"
```

---

## Response

### Success Response (200)

```json
{
  "success": true,
  "message": "Team board overall stats fetched successfully",
  "data": {
    "team_board_stats": [
      {
        "id": 7454,
        "name": "Team Member Name 1",
        "profile_pic_url": "https://myurl1.com",
        "lead_count": 0,
        "campaign_count": 0,
        "reply_count": 0,
        "positive_reply_count": 0,
        "reply_rate": 0,
        "positive_reply_rate": 0,
        "average_reply_time": 0,
        "unique_open_count": 0
      },
      {
        "id": 7323,
        "name": "Team Member Name 2",
        "profile_pic_url": "https://myurl2.com",
        "lead_count": 0,
        "campaign_count": 0,
        "reply_count": 0,
        "positive_reply_count": 0,
        "reply_rate": 0,
        "positive_reply_rate": 0,
        "average_reply_time": 0,
        "unique_open_count": 0
      }
    ]
  }
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Request success status |
| `message` | string | Response message |
| `data.team_board_stats` | array | Array of team member statistics |
| `data.team_board_stats[].id` | integer | Team member ID |
| `data.team_board_stats[].name` | string | Team member name |
| `data.team_board_stats[].profile_pic_url` | string | Profile picture URL |
| `data.team_board_stats[].lead_count` | integer | Total leads assigned |
| `data.team_board_stats[].campaign_count` | integer | Total campaigns managed |
| `data.team_board_stats[].reply_count` | integer | Total replies received |
| `data.team_board_stats[].positive_reply_count` | integer | Positive replies count |
| `data.team_board_stats[].reply_rate` | number | Reply rate percentage |
| `data.team_board_stats[].positive_reply_rate` | number | Positive reply rate percentage |
| `data.team_board_stats[].average_reply_time` | number | Average time to reply |
| `data.team_board_stats[].unique_open_count` | integer | Count of unique opens |
