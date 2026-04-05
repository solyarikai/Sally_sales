# Move Leads to Inactive from All Leads Page

## Overview

Endpoint for moving selected leads to an inactive status from the all leads page interface.

## Endpoint Details

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/leads/push-to-list`

## Authentication

**Type:** API Key (Query Parameter)

- **Parameter Name:** `api_key`
- **Location:** Query string
- **Required:** Yes
- **Default:** `API_KEY`

## Request Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |

### Request Body

```json
{
  "listId": number,
  "leadIds": [number],
  "allLeads": boolean,
  "filters": {
    "leadType": string,
    "status": string,
    "campaignId": string,
    "leadCategoryIds": string,
    "unCategorized": string,
    "emailAccountId": string,
    "emailStatus": string,
    "teamMemberId": string,
    "emailCampaignSeqId": string,
    "campaignTagId": string,
    "clientId": string,
    "replyDateFrom": string,
    "replyDateTo": string,
    "importedDate": string,
    "leadEmail": string,
    "tagIds": string,
    "espDomainType": string,
    "segType": string
  },
  "action": string
}
```

#### Body Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `listId` | number | Yes | Destination list ID for lead movement |
| `leadIds` | array | Conditional | Individual lead IDs (1-10,000); forbidden if `allLeads` is true |
| `allLeads` | boolean | Yes | When true, processes all leads matching filters; ignores `leadIds` |
| `filters` | object | Conditional | Selection criteria when `allLeads` is true |
| `action` | string | No | Valid values: `copy` or `move` |

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/leads/push-to-list?api_key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "listId": 456,
    "leadIds": [1234, 1235],
    "allLeads": false,
    "filters": {
      "leadType": "active",
      "status": "INPROGRESS",
      "campaignId": "789"
    },
    "action": "move"
  }'
```

## Response Format

### Success Response

**HTTP Status:** 200

```json
{
  "ok": true,
  "message": "Leads inactivated from all leads successfully"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Operation success indicator |
| `message` | string | Status message describing the result |
