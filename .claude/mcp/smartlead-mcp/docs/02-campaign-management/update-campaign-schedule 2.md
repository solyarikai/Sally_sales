# Update Campaign Schedule API Documentation

## Endpoint Overview

**Title:** Update Campaign Schedule

**Description:** This endpoint updates a campaign's schedule

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`

**Full URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign-id}/schedule`

---

## Path Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `campaign-id` | string | Yes | - | The ID of the campaign you want to update |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

---

## Request Body Parameters

All parameters are sent as JSON in the request body.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `timezone` | string | No | `"America/Los_Angeles"` | Use timezones from the Smartlead timezone list |
| `days_of_the_week` | integer array | No | `null` | Days to run campaign (0-6 representing Monday-Sunday) |
| `start_hour` | string | No | `"01:11"` | Campaign start time in 24-hour format (HH:MM) |
| `end_hour` | string | No | `"02:22"` | Campaign end time in 24-hour format (HH:MM) |
| `min_time_btw_emails` | integer | No | `10` | Minutes between successive emails |
| `max_new_leads_per_day` | integer | No | `20` | Maximum number of new leads per day |
| `schedule_start_time` | string | No | `"2023-04-25T07:29:25.978Z"` | Standard ISO format accepted |

---

## Request Example (cURL)

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/schedule?api_key=${API_KEY} \
  --header "Content-Type: application/json" \
  --data '{
    "timezone": "America/Los_Angeles",
    "days_of_the_week": [1],
    "start_hour": "01:11",
    "end_hour": "02:22",
    "min_time_btw_emails": 10,
    "max_new_leads_per_day": 20,
    "schedule_start_time": "2023-04-25T07:29:25.978Z"
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true
}
```

### Error Response (400)

```json
{
  "error": "Invalid timezone - {timezone}"
}
```

```json
{
  "error": "Invalid start_hour - {startHour}"
}
```

```json
{
  "error": "Invalid end_hour - {endHour}"
}
```

```json
{
  "error": "startHour cannot be greater than endHour"
}
```

---

## Response Status Codes

| Code | Description |
|------|-------------|
| 200 | Successful update |
| 400 | Invalid request parameters |
