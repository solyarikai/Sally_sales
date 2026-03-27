# Add Lead/Domain to Global Block List

## Description
"This endpoint adds a lead/domain to the global block list"

## Endpoint Details

**HTTP Method:** POST

**URL:** `https://server.smartlead.ai/api/v1/leads/add-domain-block-list`

---

## Parameters

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

### Request Body

**Content-Type:** `application/json`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain_block_list` | array of strings | Yes | Array of email addresses or domains to add to block list |
| `client_id` | integer/null | No | Client-specific ID; null if domains apply globally |

**Example Request Body:**
```json
{
  "domain_block_list": ["rambo+1001@five2one.com.au", "apple.com"],
  "client_id": null
}
```

---

## Request Examples

### cURL
```bash
curl -X POST "https://server.smartlead.ai/api/v1/leads/add-domain-block-list?api_key=API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_block_list": ["apple.com"],
    "client_id": null
  }'
```

---

## Response Examples

### Success Response (200)
```json
{
  "uploadCount": 1,
  "totalDomainAdded": 1
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `uploadCount` | integer | Number of entries uploaded |
| `totalDomainAdded` | integer | Total domains/emails added to block list |

---

## Notes
- Supports both individual email addresses and entire domains
- When `client_id` is null, the block applies globally across the account
- When `client_id` is specified, the block applies only to that specific client
