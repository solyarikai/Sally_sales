# Rate Limits

## Overview

SmartLead provides a flexible API infrastructure for automating outbound email marketing systems with straightforward rate limiting.

## Core Rate Limit

**60 requests per 60 seconds per API key**

## Response Headers

GET request responses include three rate limit indicators in the headers:

- `x-ratelimit-limit`: Maximum requests allowed (shows 60)
- `x-ratelimit-remaining`: Requests available in current 60-second window
- `x-ratelimit-reset`: Unix timestamp when the window resets

## Batch Upload Limits

- **Maximum leads per upload**: 350 leads
- **Throughput capacity**: Approximately 21,000 leads per minute

## Special Arrangements

The documentation notes that "This will be improved to accommodate for more." Integration partners interested in custom rate limits should contact SmartLead directly.
