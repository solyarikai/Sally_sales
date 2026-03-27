# Get Lead Sequence Details

## Overview

"This endpoint gives you sequence details for a particular lead"

## HTTP Method & Endpoint

```
GET https://server.smartlead.ai/api/v1/leads/:leadMapId/sequence-details
```

## Parameters

### Path Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `leadMapId` | string | Yes | - | The lead map ID for which sequence details are requested |

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Request Body

No request body required for this endpoint.

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/leads/:leadMapId/sequence-details?api_key={API_KEY}
```

## Response Examples

### Success Response (200 OK)

```json
{
  "ok": true,
  "message": "Lead sequence details fetched successfully",
  "data": [
    {
      "status": "SENT",
      "sent_time": "2025-06-26T09:55:27.852Z",
      "status_message": "Message sent successfully!",
      "email_campaign_seq_id": 10684
    },
    {
      "status": "SENT",
      "sent_time": "2025-06-26T10:30:37.823Z",
      "status_message": "Message sent successfully!",
      "email_campaign_seq_id": 10683
    },
    {
      "status": "SENT",
      "sent_time": "2025-06-27T11:06:29.048Z",
      "status_message": "Message sent successfully!",
      "email_campaign_seq_id": 10685
    }
  ]
}
```

### Response Schema

```json
{
  "ok": boolean,
  "message": string,
  "data": [
    {
      "status": string,
      "sent_time": string (ISO 8601 format),
      "status_message": string,
      "email_campaign_seq_id": integer
    }
  ]
}
```

## Notes

- The endpoint is categorized under "Lead Management"
- Authentication is required via API key query parameter
- Returns an array of sequence entries for the specified lead
