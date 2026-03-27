# Move Leads to Inactive from Campaign Lead List Page

## Overview

"This endpoint will move the selected leads to inactive from campaign - lead list page"

## API Details

**HTTP Method:** POST

**Base URL:** `https://server.smartlead.ai/api/v1/leads`

**Endpoint Path:** `/campaign/push-to-list`

**Full URL:** `https://server.smartlead.ai/api/v1/leads/campaign/push-to-list`

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

### Request Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `campaignId` | string | Yes | ID of the campaign from which leads will be moved/copied |
| `listId` | string | Yes | ID of the destination list where selected leads should be pushed |
| `leadMapIds` | number | No | IDs of email_campaign_leads_mappings entries (1-10,000 entries). Forbidden when allLeads is true |
| `allLeads` | boolean | No (default: false) | When true, ignores leadMapIds and pushes every lead from campaign matching filters |
| `filters` | object | No | Campaign filtering options (status, leadCategoryIds, teamMemberId, emailStatus, etc.). Applies only when allLeads is true |
| `archivedFromAllCampaign` | boolean | No (default: false) | When true, allows pushing leads archived across the campaign |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/leads/campaign/push-to-list?api_key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "campaignId": "123",
    "listId": "456",
    "leadMapIds": [789, 790],
    "allLeads": false,
    "filters": {
      "status": "INPROGRESS",
      "leadType": "active"
    },
    "archivedFromAllCampaign": false
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Leads pushed to list successfully"
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Indicates successful operation |
| `message` | string | Human-readable success message |

---

## Notes

- Accepts between 1 and 10,000 lead IDs when using `leadMapIds`
- When `allLeads` is true, `leadMapIds` must not be provided
- `filters` parameter reuses campaign filtering helpers and supports standard filtering options
