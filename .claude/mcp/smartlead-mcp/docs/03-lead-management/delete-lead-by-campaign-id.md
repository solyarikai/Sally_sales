# Delete Lead By Campaign ID

## Overview

Endpoint to remove a lead from an email campaign using campaign and lead identifiers.

## API Endpoint

**Method:** `DELETE`

**URL:** `https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}`

---

## Parameters

### Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_id` | string | Yes | The identifier of the campaign from which to delete the lead |
| `lead_id` | string | Yes | The identifier of the lead to be deleted |

### Query Parameters

| Name | Type | Required | Description | Default |
|------|------|----------|-------------|---------|
| `api_key` | string | Yes | Authentication credential for API access | `API_KEY` |

---

## Request

### cURL Example

```bash
curl https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{lead_id}?api_key={API_KEY} \
  -X DELETE
```

---

## Response

### Success Response (200)

```json
{
  "ok": true
}
```

**Response Schema:**
- `ok` (boolean): Confirmation status of deletion operation

### Error Response (400)

```json
{}
```

---

## Notes

- This operation permanently removes the specified lead from the campaign
- The lead identifier and campaign identifier must both be valid
- Authentication via API key is required for all requests
