---
name: publora
description: "Publora API — schedule and publish social media posts across 10 platforms (X/Twitter, LinkedIn, Instagram, Threads, TikTok, YouTube, Facebook, Bluesky, Mastodon, Telegram). Use this skill when the user wants to post, schedule, draft, bulk-schedule, manage workspace users, configure webhooks, or retrieve LinkedIn analytics via Publora."
---

# Publora API — Core Skill

Publora is an affordable REST API for scheduling and publishing social media posts across 10 platforms (Pinterest is listed internally but not yet supported). Base URL: `https://api.publora.com/api/v1`

## Plans & API Access

| Plan | Price | Posts/Month | Platforms |
|------|-------|-------------|-----------|
| Starter | Free | 15 | LinkedIn & Bluesky |
| Pro | $2.99/account | 100/account | All |
| Premium | $5.99/account | 500/account | All |

Starter gives API access for LinkedIn and Bluesky. Twitter/X requires Pro or Premium (explicitly excluded from Starter). See publora.com/pricing.

## Authentication

All requests require the `x-publora-key` header. Keys start with `sk_` (format: `sk_xxxxxxx.xxxxxx...`).

```
curl https://api.publora.com/api/v1/platform-connections \
  -H "x-publora-key: sk_YOUR_KEY"
```

Get your key: publora.com -> Settings -> API Keys -> Generate API Key.

## Step 0: Get Platform IDs

Always call this first to get valid platform IDs before posting.

```
const res = await fetch('https://api.publora.com/api/v1/platform-connections', {
  headers: { 'x-publora-key': 'sk_YOUR_KEY' }
});
const { connections } = await res.json();
// connections[i].platformId -> e.g. "linkedin-ABC123", "twitter-456"
// Also returns: tokenStatus, tokenExpiresIn, lastSuccessfulPost, lastError
```

Platform IDs look like: `twitter-123`, `linkedin-ABC`, `instagram-456`, `threads-789`, etc.

## Post Immediately

Omit `scheduledTime` to publish right away:

```
await fetch('https://api.publora.com/api/v1/create-post', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' },
  body: JSON.stringify({
    content: 'Your post content here',
    platforms: ['twitter-123', 'linkedin-ABC']
  })
});
```

## Schedule a Post

Include `scheduledTime` in ISO 8601 UTC - must be in the future:

```
await fetch('https://api.publora.com/api/v1/create-post', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' },
  body: JSON.stringify({
    content: 'Scheduled post content',
    platforms: ['twitter-123', 'linkedin-ABC'],
    scheduledTime: '2026-03-16T10:00:00.000Z'
  })
});
// Response: { postGroupId: "pg_abc123", scheduledTime: "..." }
```

## Save as Draft

Omit `scheduledTime` - post is created as draft. Schedule it later:

```
// Create draft
const { postGroupId } = await createPost({ content, platforms });

// Schedule later
await fetch(`https://api.publora.com/api/v1/update-post/${postGroupId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' },
  body: JSON.stringify({ status: 'scheduled', scheduledTime: '2026-03-16T10:00:00.000Z' })
});
```

## List Posts

Filter, paginate and sort your scheduled/published posts:

```
// GET /api/v1/list-posts
// Query params: status, platform, fromDate, toDate, page, limit, sortBy, sortOrder
const res = await fetch(
  'https://api.publora.com/api/v1/list-posts?status=scheduled&platform=twitter&page=1&limit=20',
  { headers: { 'x-publora-key': 'sk_YOUR_KEY' } }
);
const { posts, pagination } = await res.json();
// pagination: { page, limit, totalItems, totalPages, hasNextPage, hasPrevPage }
```

Valid statuses: `draft`, `scheduled`, `published`, `failed`, `partially_published`

## Get / Delete a Post

```
# Get post details
GET /api/v1/get-post/:postGroupId

# Delete post (also removes media from storage)
DELETE /api/v1/delete-post/:postGroupId
```

## Bulk Schedule (a Week of Content)

```python
from datetime import datetime, timedelta, timezone
import requests

HEADERS = { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' }
base_date = datetime(2026, 3, 16, 10, 0, 0, tzinfo=timezone.utc)

posts = ['Monday post', 'Tuesday post', 'Wednesday post', 'Thursday post', 'Friday post']

for i, content in enumerate(posts):
    scheduled_time = base_date + timedelta(days=i)
    requests.post('https://api.publora.com/api/v1/create-post', headers=HEADERS, json={
        'content': content,
        'platforms': ['twitter-123', 'linkedin-ABC'],
        'scheduledTime': scheduled_time.isoformat()
    })
```

## Media Uploads

All media (images and videos) use a 3-step pre-signed upload workflow:

Step 1: `POST /api/v1/create-post` -> get `postGroupId`
Step 2: `POST /api/v1/get-upload-url` -> get `uploadUrl`
Step 3: `PUT {uploadUrl}` with file bytes (no auth needed for S3)

For carousels: call `get-upload-url` N times with the same `postGroupId`.

## Cross-Platform Threading

X/Twitter and Threads support threading. Three methods:

- Auto-split: Content over the char limit is split automatically at paragraph/sentence/word breaks.
- Manual `---`: Use `---` on its own line to define exact split points.
- Explicit `[n/m]`: Use `[1/3]`, `[2/3]` markers.

## LinkedIn Analytics

```
// Post statistics
await fetch('https://api.publora.com/api/v1/linkedin-post-statistics', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' },
  body: JSON.stringify({
    postedId: 'urn:li:share:7123456789',
    platformId: 'linkedin-ABC123',
    queryTypes: ['IMPRESSION', 'MEMBERS_REACHED', 'RESHARE', 'REACTION', 'COMMENT']
  })
});

// Profile summary (followers + aggregated stats)
await fetch('https://api.publora.com/api/v1/linkedin-profile-summary', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-publora-key': 'sk_YOUR_KEY' },
  body: JSON.stringify({ platformId: 'linkedin-ABC123' })
});
```

Available analytics endpoints:

| Endpoint | Description |
|----------|-------------|
| `POST /linkedin-post-statistics` | Impressions, reactions, reshares for a post |
| `POST /linkedin-account-statistics` | Aggregated account metrics |
| `POST /linkedin-followers` | Follower count and growth |
| `POST /linkedin-profile-summary` | Combined profile overview |
| `POST /linkedin-create-reaction` | React to a post |
| `DELETE /linkedin-delete-reaction` | Remove a reaction |

## Webhooks

Get real-time notifications when posts are published, fail, or tokens are expiring.

Valid events: `post.scheduled`, `post.published`, `post.failed`, `token.expiring`

Max 10 webhooks per account.

## Platform Limits Quick Reference (API)

| Platform | Char Limit | Max Images | Video Max | Text Only? |
|----------|-----------|------------|-----------|-----------|
| Twitter/X | 280 (25K Premium) | 4 x 5MB | 2 min / 512MB | Yes |
| LinkedIn | 3,000 | 10 x 5MB | 30 min / 500MB | Yes |
| Instagram | 2,200 | 10 x 8MB (JPEG only) | 3 min Reels / 60s Stories / 300MB | No |
| Threads | 500 | 20 x 8MB | 5 min / 500MB | Yes |
| TikTok | 2,200 | Video only | 10 min / 4GB | No |
| YouTube | 5,000 desc | Video only | 12h / 256GB | No |
| Facebook | 63,206 | 10 x 10MB | 45 min / 2GB | Yes |
| Bluesky | 300 | 4 x 1MB | 3 min / 100MB | Yes |
| Mastodon | 500 | 4 x 16MB | ~99MB | Yes |
| Telegram | 4,096 (1,024 captions) | 10 x 10MB | 50MB (Bot API) | Yes |

## Post Statuses

- `draft` - Not scheduled yet
- `scheduled` - Waiting to publish
- `published` - Successfully posted
- `failed` - Publishing failed (check `/post-logs`)
- `partially_published` - Some platforms failed

## Errors

| Code | Meaning |
|------|---------|
| 400 | Invalid request (check `scheduledTime` format, required fields) |
| 401 | Invalid or missing API key |
| 403 | Plan limit reached or Workspace API not enabled |
| 404 | Post/resource not found |
| 429 | Platform rate limit exceeded |
