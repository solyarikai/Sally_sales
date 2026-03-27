# Fetch Lead Categories

## Description

This endpoint retrieves all lead categories from your account, including sentiment classifications for each category.

## Endpoint

```
GET https://server.smartlead.ai/api/v1/leads/fetch-categories
```

## Authentication

- **Type**: API Key (Query Parameter)
- **Parameter Name**: `api_key`
- **Required**: Yes

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API key for authentication |

## Path Parameters

None

## Request Body

Not applicable (GET request)

## Request Examples

### cURL

```bash
curl https://server.smartlead.ai/api/v1/leads/fetch-categories?api_key=${API_KEY}
```

## Response Examples

### Success Response (200)

```json
[
  {
    "id": 1,
    "created_at": "2022-08-30T12:32:48.645Z",
    "name": "Interested",
    "sentiment_type": "positive"
  },
  {
    "id": 2,
    "created_at": "2022-08-30T12:32:55.159Z",
    "name": "Meeting Request",
    "sentiment_type": "positive"
  },
  {
    "id": 3,
    "created_at": "2022-08-30T12:33:02.286Z",
    "name": "Not Interested",
    "sentiment_type": "negative"
  },
  {
    "id": 6,
    "created_at": "2022-08-30T12:33:22.323Z",
    "name": "Out Of Office",
    "sentiment_type": null
  }
]
```

## Response Schema

### Array Item Properties

| Property | Type | Example | Description |
|----------|------|---------|-------------|
| `id` | integer | 1 | Unique category identifier |
| `created_at` | string (ISO 8601) | "2022-08-30T12:32:48.645Z" | Category creation timestamp |
| `name` | string | "Interested" | Category name |
| `sentiment_type` | string or null | "positive" | Sentiment classification: "positive", "negative", or null |
