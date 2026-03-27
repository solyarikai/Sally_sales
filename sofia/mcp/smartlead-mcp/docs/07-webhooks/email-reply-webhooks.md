# Capturing Email Replies - API Documentation

## Overview

When an email sent through SmartLead receives a reply, the system triggers a webhook notification containing detailed information about the correspondence.

This endpoint enables tracking of email replies from multiple contacts within organizations through enhanced webhook payloads.

## Endpoint Information

**Type:** Webhook Event (Not a traditional REST endpoint)
**Event Type:** `EMAIL_REPLY`
**Trigger:** Automatically fires when a reply is received to a SmartLead campaign email

---

## Webhook Payload Structure

### Key Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `campaign_status` | string | Campaign status (e.g., "COMPLETED") |
| `stats_id` | string | Unique statistics identifier |
| `sl_email_lead_id` | string | SmartLead lead ID |
| `sl_email_lead_map_id` | integer | Lead-to-campaign mapping ID |
| `sl_lead_email` | string | Original target recipient email |
| `from_email` | string | Sender's email address |
| `to_email` | string | Recipient's email address |
| `to_name` | string | Recipient's name |
| `subject` | string | Email subject line |
| `time_replied` | string | Reply timestamp (ISO 8601) |
| `event_timestamp` | string | Event creation timestamp |
| `campaign_name` | string | Associated campaign name |
| `campaign_id` | integer | Campaign identifier |
| `sequence_number` | integer | Email sequence position |
| `message_id` | string | Unique message identifier |
| `preview_text` | string | Reply preview text |

### Enhanced Lead Correspondence Object

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `targetLeadEmail` | string | - | Original recipient who was targeted in your campaign |
| `replyReceivedFrom` | string | - | Actual responder's email address |
| `repliedCompanyDomain` | string | "SameCompany", "DifferentCompany", "Unknown" | Relationship between responder and target |

---

## Response Scenarios

### Scenario 1: Direct Reply
Target and responder are identical; same email addresses in both fields.

### Scenario 2: Colleague Reply (Same Company)
- `targetLeadEmail`: Original recipient
- `replyReceivedFrom`: Different colleague
- `repliedCompanyDomain`: "SameCompany"

### Scenario 3: Different Company Reply
- `targetLeadEmail`: Original recipient
- `replyReceivedFrom`: Person from different organization
- `repliedCompanyDomain`: "DifferentCompany"

---

## Example Webhook Payload

```json
{
  "campaign_status": "COMPLETED",
  "stats_id": "a891fe37-c45d-21e8-67ba-fcd44e9c33a8",
  "sl_email_lead_id": "1482956",
  "sl_email_lead_map_id": 1438627,
  "sl_lead_email": "jamesparker75+2@gmail.com",
  "from_email": "untracked@example.com",
  "to_email": "james@smartlead.ai",
  "to_name": "James Parker",
  "subject": "Some more conversions?",
  "time_replied": "2025-03-28T09:35:01+00:00",
  "event_timestamp": "2025-03-28T09:35:01+00:00",
  "campaign_name": "email sent",
  "campaign_id": 9181,
  "sequence_number": 1,
  "leadCorrespondence": {
    "targetLeadEmail": "jamesparker75+2@gmail.com",
    "replyReceivedFrom": "james@smartlead.ai",
    "repliedCompanyDomain": "DifferentCompany"
  },
  "event_type": "EMAIL_REPLY"
}
```

---

## Implementation Requirements

1. Prepare webhook endpoint to process `leadCorrespondence` object
2. Update integration logic to differentiate responders
3. Create personalized follow-up sequences based on actual respondents
4. Include responder data in attribution analytics

---

## Backward Compatibility

All previous webhook fields remain unchanged. The new `leadCorrespondence` object is simply an addition to the payload, ensuring existing integrations function without modification.

---

## Error Handling

When responder identity cannot be confidently determined, the system defaults to original recipient information with `repliedCompanyDomain` set to "Unknown".
