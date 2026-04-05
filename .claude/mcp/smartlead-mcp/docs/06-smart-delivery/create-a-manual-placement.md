# Create a Manual Placement Test

## Endpoint Overview

**Description:** Create and run a manual spam/placement test using Smartlead mailboxes via the Smart Delivery platform.

**HTTP Method:** POST

**Full Endpoint:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/manual`

---

## Authentication

**Security Scheme:** API Key (Query Parameter)
- **Parameter Name:** `api_key`
- **Location:** Query string
- **Required:** Yes

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API Key for authentication |
| `test_name` | string | Yes | — | Name of your test |
| `description` | string | No | — | Description for reference later |
| `spam_filters` | array (string) | Yes | `["spam_assassin"]` | Spam filters to test across |
| `link_checker` | boolean | Yes | `true` | Enable domain blacklist checking for links |
| `campaign_id` | integer | Yes | — | Campaign ID for sequence selection |
| `sequence_mapping_id` | integer | Yes | — | Sequence or variant ID to test |
| `provider_ids` | array (integer) | Yes | — | Email provider IDs for test distribution |
| `sender_accounts` | array (string) | Yes | — | Sender email addresses to use |
| `all_email_sent_without_time_gap` | boolean | Yes | `false` | Send all emails simultaneously if true |
| `min_time_btwn_emails` | integer | Yes | `10` | Time gap between emails (when not simultaneous) |
| `min_time_unit` | string | Yes | `"min"` | Time unit: `minutes`, `hours`, or `days` |
| `is_warmup` | boolean | Yes | `false` | Enable warmup mode for positive intent responses |

---

## Request Body

**Content-Type:** `application/json`

### Example Request Body
```json
{
  "test_name": "Email Deliverability Test 2",
  "description": "Testing deliverability across multiple spam filters.",
  "spam_filters": ["spam_assassin"],
  "link_checker": true,
  "campaign_id": 4957,
  "sequence_mapping_id": 4347,
  "provider_ids": [27, 28],
  "all_email_sent_without_time_gap": false,
  "min_time_btwn_emails": 5,
  "min_time_unit": "minutes",
  "is_warmup": true,
  "sender_accounts": ["harrisonmarganza@outlook.com"]
}
```

---

## cURL Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/manual?api_key=${API_KEY}' \
--data-raw '{
  "test_name": "Email Deliverability Test 2",
  "description": "Testing deliverability across multiple spam filters.",
  "spam_filters": ["spam_assassin"],
  "link_checker": true,
  "campaign_id": 4957,
  "sequence_mapping_id": 4347,
  "provider_ids": [27, 28],
  "all_email_sent_without_time_gap": false,
  "min_time_btwn_emails": 5,
  "min_time_unit": "minutes",
  "is_warmup": true,
  "sender_accounts": ["harrisonmarganza@outlook.com"]
}'
```

---

## Success Response (200 OK)

```json
{
  "created_at": "2024-11-21T13:51:45.011Z",
  "updated_at": "2024-11-21T13:51:45.011Z",
  "id": 6194,
  "test_name": "Email Deliverability Test 2",
  "description": "Testing deliverability across multiple spam filters.",
  "spam_filters": ["spam_assassin"],
  "link_checker": true,
  "campaign_id": 4957,
  "sequence_mapping_id": 4347,
  "all_email_sent_without_time_gap": false,
  "min_time_btwn_emails": 5,
  "min_time_unit": "minutes",
  "is_warmup": true,
  "test_with_sl_account": true,
  "has_seed_mapping": 1,
  "status": "ACTIVE",
  "user_id": 95,
  "test_type": "manual",
  "email_track_id": "fad7294a-6c22-sd47-4e05-aff8-133a6d09c326",
  "provider_id": [27, 28],
  "folder_id": null,
  "custom_email_content": null,
  "scheduler_cron_value": null,
  "cron_exp": null,
  "client_id": null,
  "separator": null,
  "last_added_trigger_time": null,
  "schedule_start_time": null,
  "custom_email_subject": null,
  "test_end_date": null,
  "test_allowed_number": null,
  "sequence_variant_id": null,
  "share_report_hash": null,
  "is_campaign_paused": false,
  "test_run_no": 0,
  "charged_test_run_no": 0,
  "every_days": null
}
```

### Response Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique spam test identifier |
| `test_name` | string | Name assigned to the test |
| `status` | string | Current test status (ACTIVE, COMPLETED, etc.) |
| `email_track_id` | string | Tracking ID for seed list emails |
| `provider_id` | array | List of provider IDs used in test |
| `test_type` | string | Test category: "manual" or "auto" |
| `created_at` | string | ISO 8601 creation timestamp |
| `updated_at` | string | ISO 8601 last update timestamp |

---

## Error Response (400 Bad Request)

```json
{
  "message": "\"test_name\" is required"
}
```

### Common Error Messages

| Error | Meaning |
|-------|---------|
| `"test_name" is required` | Missing required test name parameter |
| `"campaign_id" is required` | Missing campaign identifier |
| `"sequence_mapping_id" is required` | Missing sequence variant identifier |
| `"provider_ids" is required` | Missing provider identifiers array |
