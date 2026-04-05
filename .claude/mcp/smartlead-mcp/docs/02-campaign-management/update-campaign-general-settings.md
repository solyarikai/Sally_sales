# Update Campaign General Settings API Documentation

## Overview
Endpoint to modify a campaign's general configuration settings including tracking preferences, lead stopping conditions, and AI-enabled features.

## Endpoint Details

**HTTP Method:** POST
**Base URL:** `https://server.smartlead.ai/api/v1/campaigns`
**Path:** `/{campaign-id}/settings`

---

## Parameters

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaign_id` | string | Yes | The ID of the campaign to update |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API authentication key |

### Request Body Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | - | Campaign name (leave empty to skip update) |
| `track_settings` | array | `["DONT_TRACK_EMAIL_OPEN"]` | Tracking disabled for: `DONT_TRACK_EMAIL_OPEN`, `DONT_TRACK_LINK_CLICK`, `DONT_TRACK_REPLY_TO_AN_EMAIL` |
| `stop_lead_settings` | string | `"REPLY_TO_AN_EMAIL"` | Pause leads when: `REPLY_TO_AN_EMAIL`, `CLICK_ON_A_LINK`, `OPEN_AN_EMAIL` |
| `unsubscribe_text` | string | - | Custom unsubscribe message text |
| `send_as_plain_text` | boolean | `false` | Send emails as plain text format |
| `force_plain_text` | boolean | - | Convert all emails to plain text |
| `follow_up_percentage` | integer | `100` | Percentage of leads for follow-ups (0-100) |
| `client_id` | integer | `33` | Associated client ID (null if not applicable) |
| `enable_ai_esp_matching` | boolean | `false` | Enable AI-based ESP provider matching |
| `auto_pause_domain_leads_on_reply` | boolean | - | Auto-pause leads from same domain after reply |
| `ignore_ss_mailbox_sending_limit` | boolean | - | Ignore shared mailbox sending limits |
| `bounce_autopause_threshold` | string | - | Bounces threshold before auto-pause (cannot modify when active/paused) |
| `domain_level_rate_limit` | boolean | `false` | Activate domain-level rate limiting |
| `out_of_office_detection_settings` | object | - | OOO response handling configuration |
| `ai_categorisation_options` | array | - | IDs of AI categorization options (user must have access) |

#### Out of Office Detection Settings (Nested Object)

| Parameter | Type | Description |
|-----------|------|-------------|
| `ignoreOOOasReply` | boolean | Don't count OOO as replies (optional) |
| `autoReactivateOOO` | boolean | Auto-reactivate OOO leads (cannot be true if autoCategorizeOOO is true) |
| `reactivateOOOwithDelay` | string | Delay in days before reactivation (requires autoReactivateOOO false) |
| `autoCategorizeOOO` | boolean | Auto-categorize OOO replies (cannot be true if autoReactivateOOO is true) |

---

## Request Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/<campaign-id>/settings?api_key=${API_KEY} \
--header "Content-Type: application/json" \
--data '{
  "name": "Updated Campaign Name",
  "track_settings": [
    "DONT_TRACK_EMAIL_OPEN",
    "DONT_TRACK_LINK_CLICK"
  ],
  "stop_lead_settings": "REPLY_TO_AN_EMAIL",
  "unsubscribe_text": "Unsubscribe here",
  "send_as_plain_text": true,
  "force_plain_text": true,
  "enable_ai_esp_matching": true,
  "follow_up_percentage": 80,
  "client_id": null,
  "auto_pause_domain_leads_on_reply": true,
  "bounce_autopause_threshold": "5",
  "domain_level_rate_limit": false,
  "out_of_office_detection_settings": {
    "ignoreOOOasReply": false,
    "autoReactivateOOO": false,
    "reactivateOOOwithDelay": null,
    "autoCategorizeOOO": false
  },
  "ai_categorisation_options": [2, 7, 1]
}'
```

---

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true
}
```

### Error Response (400 Bad Request)

```json
{
  "error": "Invalid track_settings value - {trackSettings}"
}
```

```json
{
  "error": "Invalid stop_lead_settings value - {stopLeadSettings}"
}
```

---

## Notes

- OOO (Out of Office) category must be included in `ai_categorisation_options`
- `bounce_autopause_threshold` cannot be modified when campaign status is ACTIVE or PAUSED
- `autoReactivateOOO` and `autoCategorizeOOO` are mutually exclusive
- Pass `null` for `client_id` if campaign is not attached to a client
