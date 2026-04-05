# Update Team Member To Lead

## Overview

Associate a team member to a lead in your master inbox.

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/master-inbox/update-team-member`

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | Your API key for authentication |

## Request Body (JSON)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_lead_map_id` | integer | Yes | The map ID from the master inbox (found in master inbox API or webhooks) |
| `team_member_id` | integer | Yes | The ID of the team member to associate with this lead |

---

## Request Example

```bash
curl -X POST "https://server.smartlead.ai/api/v1/master-inbox/update-team-member?api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email_lead_map_id": 2034610437,
    "team_member_id": 3210
  }'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Lead team member updated successfully"
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

---

## Notes

- This endpoint allows assignment of leads to specific team members within your organization
- The `email_lead_map_id` uniquely identifies the lead-campaign mapping record
- Ensure both IDs exist in your system before making the request
