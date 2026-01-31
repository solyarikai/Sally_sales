# ⚠️ PRIORITY: READ TESTING_PRIORITY.md FIRST

**Current Phase: TESTING**

Before doing anything else:
1. Read TESTING_PRIORITY.md
2. Fix Slack notification to use BOT TOKEN (not webhook)
3. Test end-to-end flow
4. Slack Channel: #c-replies-test (ID: C09REGUQWTG)

---

# Reply Automation Feature

## Overview

Build a feature that replicates and improves the n8n email reply automation workflow. The goal is to automatically process email replies from Smartlead campaigns, classify them with AI, generate draft responses, and send notifications to Slack.

## Reference: n8n Workflow "EasyStaff Russian - Email"

The existing n8n automation does:
1. Receives webhook from Smartlead when email reply arrives
2. Fetches lead data from Smartlead API
3. Logs to Google Sheets
4. Classifies email intent with OpenAI
5. Categorizes lead (interested, not interested, out of office, etc.)
6. Researches company with Perplexity (if needed)
7. Generates draft reply with Claude
8. Sends notification to Slack with draft reply

## API Keys Available

- **Smartlead API:** `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5`
- **OpenAI API:** `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`

## Specific Implementation Tasks

### Phase 1: Backend - Smartlead Integration

Create `backend/app/services/smartlead_service.py`:
```python
# Service to interact with Smartlead API
# - List campaigns
# - Get campaign details
# - Fetch leads from campaign
# - Receive webhook events
```

Create `backend/app/api/smartlead.py`:
```python
# Endpoints:
# GET /api/smartlead/campaigns - List all campaigns
# GET /api/smartlead/campaigns/{id}/leads - Get leads for campaign
# POST /api/smartlead/webhook - Receive reply events
```

**Smartlead API Docs:** https://api.smartlead.ai/reference/get-all-campaigns

### Phase 2: Backend - Reply Processing

Create `backend/app/services/reply_processor.py`:
```python
# Process incoming email replies
# 1. Parse reply content
# 2. Classify intent (OpenAI)
# 3. Categorize lead
# 4. Generate draft reply (OpenAI)
# 5. Queue notification
```

Categories to classify:
- `interested` - Wants to learn more
- `meeting_request` - Wants to schedule call
- `not_interested` - Declines
- `out_of_office` - Auto-reply
- `wrong_person` - Not the right contact
- `unsubscribe` - Wants to opt out
- `question` - Has questions
- `other` - Uncategorized

### Phase 3: Backend - Notifications

Create `backend/app/services/notification_service.py`:
```python
# Send notifications to Slack
# - Format reply summary
# - Include draft response
# - Include lead info
```

### Phase 4: Frontend - Reply Automation Setup UI

Create `frontend/src/pages/ReplyAutomationPage.tsx`:

**UX Flow:**
1. User clicks "Create Reply Automation"
2. Step 1: Select Smartlead campaigns (checkboxes with search)
3. Step 2: Configure notification channels (Slack)
4. Step 3: Review and activate

**UI Components needed:**
- Campaign selector with search/filter
- Slack channel input
- Activation toggle
- Recent replies list with categories

### Phase 5: Frontend - Replies Dashboard

Create `frontend/src/pages/RepliesPage.tsx`:

Show:
- Recent replies from all monitored campaigns
- Category badges (interested, not interested, etc.)
- Draft reply preview
- Quick actions (view conversation, copy draft)

### Phase 6: Database Models

Create/update models in `backend/app/models/`:
```python
# ReplyAutomation - automation configuration
# - id, name, campaigns[], slack_webhook, active, created_at

# ProcessedReply - received replies
# - id, automation_id, lead_email, subject, body
# - category, draft_reply, processed_at, sent_to_slack
```

## File Structure to Create

```
backend/app/
├── api/
│   ├── smartlead.py        # Smartlead API endpoints
│   └── replies.py          # Reply automation endpoints
├── services/
│   ├── smartlead_service.py    # Smartlead API client
│   ├── reply_processor.py      # AI classification & reply generation
│   └── notification_service.py # Slack notifications
├── models/
│   └── reply.py            # ReplyAutomation, ProcessedReply models
└── schemas/
    └── reply.py            # Pydantic schemas

frontend/src/pages/
├── ReplyAutomationPage.tsx # Setup automation UI
└── RepliesPage.tsx         # View replies dashboard
```

## Definition of Done

- [ ] Can list Smartlead campaigns in UI
- [ ] Can create reply automation selecting campaigns
- [ ] Webhook endpoint receives Smartlead events
- [ ] Replies are classified by AI
- [ ] Draft replies are generated
- [ ] Notifications sent to Slack
- [ ] Replies visible in dashboard with categories
- [ ] Deployed and accessible at http://46.62.210.24

## Progress Tracking

Update `status.txt` with phases:
- `STARTING` - Beginning research
- `SMARTLEAD_INTEGRATION` - Building Smartlead API
- `REPLY_PROCESSING` - AI classification working
- `FRONTEND_SETUP` - Building UI
- `FRONTEND_DASHBOARD` - Replies dashboard
- `TESTING` - End-to-end testing
- `DONE` - Feature complete

## CRITICAL SAFETY RULES

1. **SMARTLEAD: READ-ONLY** - DO NOT send any messages via Smartlead API. Only READ campaigns, leads, and messages.
2. **NO AUTO-REPLIES** - Never automatically send emails. Only generate drafts for human review.

## Important Notes

1. **DO NOT send actual emails** - Only send Slack notifications
2. Use mock data if API rate limits hit
3. Focus on simple, clean UI
4. Each session: complete ONE phase, then update status.txt
