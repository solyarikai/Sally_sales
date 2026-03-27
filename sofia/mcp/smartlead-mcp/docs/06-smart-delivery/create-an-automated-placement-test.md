# Create an Automated Placement Test

## Overview
Endpoint for creating an automated spam/placement test using Smart Delivery. This allows you to schedule recurring tests across multiple email providers to monitor deliverability.

## API Endpoint
```
POST https://smartdelivery.smartlead.ai/api/v1/spam-test/schedule
```

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |
| `schedule_start_time` | string (date) | Yes | Current DateTime | Start date/time to schedule or run the test |
| `test_end_date` | string (date) | Yes | — | Date to stop running the test |
| `every_days` | integer | Yes | 1 | Frequency in days for running new tests |
| `tz` | string | Yes | Campaign Timezone | Timezone for scheduling |
| `days` | array (int) | Yes | [1,2,3,4,5] | Days of week to run test (1-5=weekdays, 6-7=weekends) |
| `starHour` | string (date-time) | No | — | Test start time |
| `folder_id` | integer | No | — | Folder ID for test organization |

### Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `test_name` | string | Yes | — | Name of the test |
| `description` | string | No | — | Test description for reference |
| `spam_filters` | array | Yes | ["spam_assassin"] | Spam filters to test against |
| `link_checker` | boolean | Yes | true | Enable link blacklist checking |
| `campaign_id` | integer | Yes | — | Campaign ID for sequence selection |
| `sequence_mapping_id` | integer | Yes | — | Sequence/variant ID to test |
| `provider_ids` | array (int) | Yes | — | Provider IDs for test recipients |
| `all_email_sent_without_time_gap` | boolean | Yes | false | Send all emails simultaneously if true |
| `min_time_btwn_emails` | integer | Yes | 10 | Time gap between emails (throttle) |
| `min_time_unit` | string | Yes | "min" | Time unit: minutes, hours, or days |
| `is_warmup` | boolean | Yes | false | Enable warmup mode for positive intent responses |
| `sender_accounts` | array (string) | Yes | — | Sending mailbox email addresses |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/schedule?api_key=${API_KEY}' \
--data-raw '{
  "test_name": "Email Deliverability Test AT 1",
  "description": "Testing deliverability across multiple spam filters.",
  "folder_id": 456,
  "spam_filters": ["spam_assassin"],
  "link_checker": true,
  "campaign_id": 4957,
  "sequence_mapping_id": 4347,
  "provider_ids": [27, 28, 15, 21, 20],
  "all_email_sent_without_time_gap": false,
  "min_time_btwn_emails": 5,
  "min_time_unit": "minutes",
  "is_warmup": true,
  "sender_accounts": ["harrisonmarganza@outlook.com"],
  "schedule_start_time": "2024-12-02T06:50:00.000Z",
  "test_end_date": "2024-12-07",
  "every_days": 1,
  "scheduler_cron_value": {
    "tz": "Asia/Kolkata",
    "days": [1, 2, 3, 4, 5],
    "startHour": "06:50"
  }
}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "created_at": "2024-12-02T06:49:30.558Z",
  "updated_at": "2024-12-02T06:49:30.558Z",
  "id": 7268,
  "test_name": "Email Deliverability Test AT 1",
  "description": "Testing deliverability across multiple spam filters.",
  "spam_filters": ["spam_assassin"],
  "link_checker": true,
  "campaign_id": 4957,
  "sequence_mapping_id": 4347,
  "all_email_sent_without_time_gap": false,
  "min_time_btwn_emails": 5,
  "min_time_unit": "minutes",
  "is_warmup": true,
  "schedule_start_time": "2024-12-02T06:50:00.000Z",
  "test_end_date": "2024-12-07T00:00:00.000Z",
  "every_days": 1,
  "scheduler_cron_value": {
    "tz": "Asia/Kolkata",
    "days": [1, 2, 3, 4, 5],
    "startHour": "06:50"
  },
  "test_with_sl_account": true,
  "has_seed_mapping": 1,
  "status": "ACTIVE",
  "user_id": 95,
  "test_type": "auto",
  "email_track_id": "cc3a1e1d-c0df-sd93-44b2-b54d-7b7b2e1bfd81",
  "provider_id": [27, 28, 15, 21, 20],
  "folder_id": null,
  "is_campaign_paused": false,
  "test_run_no": 0,
  "charged_test_run_no": 0,
  "via_api": false
}
```

### Error Response (400)

```json
{
  "message": "Schedule start time must be greater than or equal to the current date and time."
}
```

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Spam test identifier |
| `test_name` | string | Test name |
| `test_type` | string | Type: "auto" for automated tests |
| `status` | string | Status: "ACTIVE", "COMPLETED" |
| `email_track_id` | string | ID for tracking test emails |
| `provider_id` | array | List of provider IDs included in test |
| `scheduler_cron_value` | object | Cron scheduling configuration |
