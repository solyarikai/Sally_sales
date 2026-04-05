# Update Email Account Tag

## Overview
Endpoint for updating an email account tag with a new name and color.

**HTTP Method:** `POST`

**URL:** `https://server.smartlead.ai/api/v1/email-accounts/tag-manager`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | API key required for authentication |

## Request Body

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Tag ID to update |
| `name` | string | Yes | Name of the tag |
| `color` | string | Yes | The color of the tag in HEX format |

---

## Request Example

```bash
curl --location --request POST 'https://server.smartlead.ai/api/v1/email-accounts/tag-manager?api_key={API_KEY}' \
--header 'Content-Type: application/json' \
--data '{
  "id": 81526,
  "name": "PC_TEST",
  "color": "#FCFBB1"
}'
```

---

## Response Examples

### Success Response (200)

```json
{
  "ok": true,
  "message": "Tag updated successfully!",
  "data": 1
}
```

### Error Response (400)

```json
{}
```
