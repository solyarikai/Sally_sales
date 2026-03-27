# Fetch Untracked Replies API Documentation

## Overview

Retrieve all untracked replies across all mailboxes connected to your instance.

**HTTP Method:** GET

**Full URL:** `https://server.smartlead.ai/api/v1/master-inbox/untracked-replies`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | - | Authentication key needed to verify your request |
| `limit` | integer | No | 10 | Maximum number of rows to retrieve (max 20) |
| `offset` | integer | No | 0 | Number of records to skip for pagination |
| `fetchAttachments` | boolean | No | false | Include attachments belonging to the email |
| `fetchBody` | boolean | No | false | Include the email content of untracked replies |
| `from_email` | string | No | - | Filter results by sender email address |
| `to_email` | string | No | - | Filter results by recipient email address |
| `subject_line` | string | No | - | Filter results by email subject line |

---

## Request Example

```bash
curl --location 'http://server.smartlead.ai/api/v1/master-inbox/untracked-replies?limit=10&offset=0&fetchAttachments=true&fetchBody=true&api_key=YOUR_API_KEY'
```

---

## Response Examples

### Success Response (200)

```json
{
  "success": true,
  "message": "Successfully retrieved master inbox untracked replies",
  "data": {
    "replies": [
      {
        "id": "reply-uuid-123",
        "account_id": 1234567,
        "message_id": "<example-message-id@provider.com>",
        "uid": "unique-message-uid",
        "sender_detail": "noreply@example.com",
        "recipient_detail": "user@exampledomain.com",
        "cc": "",
        "bcc": "",
        "subject": "Report domain: exampledomain.com",
        "visible_text": "",
        "reply_picked_time": "2025-08-07T10:57:53.615Z",
        "is_read": false,
        "has_attachment": true,
        "created_at": "2025-08-07T10:57:53.617Z",
        "updated_at": "2025-08-07T10:57:53.617Z",
        "body": {
          "text": "",
          "textAsHtml": ""
        },
        "attachments": [
          {
            "id": "attachment-uuid-123",
            "file_type": "application/zip",
            "file_size": 1024,
            "file_name": "example.com!exampledomain.com!timestamp1!timestamp2.zip",
            "charset": null,
            "file_url": "https://example-bucket.s3.amazonaws.com/attachments/...",
            "is_download_skipped": false,
            "created_at": "2025-08-07T10:57:53.617Z"
          }
        ]
      }
    ],
    "totalCount": 883,
    "pagination": {
      "limit": 10,
      "offset": 0,
      "totalCount": 883,
      "hasMore": true
    }
  }
}
```

### Error Response (401)

```json
{
  "message": "API key is required."
}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation status indicator |
| `message` | string | Descriptive status message |
| `data.replies` | array | Collection of untracked reply objects |
| `data.replies[].id` | string | Unique identifier for the reply |
| `data.replies[].account_id` | integer | Associated mailbox account identifier |
| `data.replies[].sender_detail` | string | Email address of message sender |
| `data.replies[].recipient_detail` | string | Email address of message recipient |
| `data.replies[].subject` | string | Email subject line content |
| `data.replies[].reply_picked_time` | string | ISO timestamp when reply was received |
| `data.replies[].is_read` | boolean | Read status of the message |
| `data.replies[].has_attachment` | boolean | Whether attachments exist |
| `data.replies[].attachments` | array | File attachment objects (if requested) |
| `data.replies[].body` | object | Email content (if fetchBody=true) |
| `data.pagination` | object | Pagination metadata |
| `data.pagination.hasMore` | boolean | Indicates if additional records exist |

---

## Notes

- Attachment and body content retrieval requires explicit parameter flags (`fetchAttachments`, `fetchBody`)
- Responses include comprehensive pagination metadata for handling large result sets
