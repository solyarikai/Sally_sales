# Knowledge-Powered Auto-Reply System Architecture

## Overview

The knowledge system enables AI-generated reply suggestions that match real operator patterns by learning from qualified lead conversations. Knowledge is stored per-project and injected into draft generation prompts.

## Data Flow

```
1. Qualified leads arrive via SmartLead/GetSales webhooks
   ↓
2. Reply classification (GPT-4o-mini, temp=0.1)
   ↓
3. Project lookup by campaign_name → campaign_filters match
   ↓
4. Load project knowledge (ProjectKnowledge table)
   + Load reply prompt template (ReplyPromptTemplateModel)
   + Load sender identity (sender_name, position, company)
   ↓
5. Draft generation (GPT-4o-mini, temp=0.7)
   - Base prompt + template + knowledge context + sender identity
   ↓
6. Operator reviews draft → approves/edits → sends
   ↓
7. Learning system captures corrections (AI draft vs sent)
   ↓
8. Learning cycle analyzes corrections → updates template + ICP
```

## Components

### ProjectKnowledge (per-project key-value store)
- **Categories**: icp, outreach, contacts, gtm, notes, search
- **Source tracking**: manual, chat, pipeline, sync, learning
- **API**: `GET/PUT/DELETE /api/projects/{id}/knowledge/{category}/{key}`

### ReplyPromptTemplate (custom GPT prompt per project)
- Full template with `{subject}`, `{body}`, `{category}`, `{first_name}`, etc.
- Assigned to project via `reply_prompt_template_id`
- **API**: `GET/POST /api/replies/prompt-templates`

### Project Sender Identity
- `sender_name`, `sender_position`, `sender_company` on Project model
- Injected into draft prompt: "You are replying as {sender_name}..."
- **API**: `PATCH /api/contacts/projects/{id}` with sender fields

### Knowledge Injection Points
1. **SmartLead webhook** (reply_processor.py:730) — loads knowledge + template when processing inbound reply
2. **GetSales webhook** (reply_processor.py:1346) — same for LinkedIn replies
3. **Regenerate draft** (replies.py:2248) — re-generates with latest knowledge

### Learning Service
- **Manual trigger**: `POST /api/projects/{id}/learning/analyze`
- **Feedback trigger**: `POST /api/projects/{id}/learning/feedback`
- Analyzes conversations + operator corrections → updates template + ICP
- Requires MIN_QUALIFIED_THRESHOLD = 20 conversations

## EasyStaff RU (Project 40) Setup

### Knowledge Base (18 entries)
- **ICP**: target_market, target_roles, target_industries, positive/negative signals, qualification criteria
- **Outreach**: email sequence, value proposition, sender identity, ICE campaign context
- **Contacts**: operator team, reply channels
- **GTM**: campaign naming, pricing, competitors, objection handling
- **Notes**: operator reply style, follow-up patterns

### Template: "EasyStaff RU - Knowledge-Powered" (ID 129)
- Built from analysis of 46 qualified lead conversations
- Encodes real operator reply patterns by lead response type
- Handles: interested (presentation requests), meeting requests, ICE conference leads
- Always replies in Russian, matches lead tone
- Signs off as "Данила Соколов, Partner @ easystaff.io"

### Campaign Filters
41 campaigns covering:
- SmartLead: "Easystaff - Russian DM *" variants (Moscow, US, ICE)
- GetSales: "EasyStaff RU - *" sender profiles (9 LinkedIn accounts)

## Improvement Points

1. **Operator correction tracking** — currently 0 corrections recorded. Need operators to use approve-and-send flow to build training data.
2. **Automated learning cycles** — schedule periodic analysis once correction data accumulates.
3. **Per-category templates** — different reply templates for interested vs meeting_request vs question.
4. **Conversation history in prompt** — include recent thread messages for context-aware replies.
5. **Lead enrichment** — use Crona/Clay API to enrich warm leads before generating drafts.
6. **Google Sheets sync** — keep leads/replies spreadsheet in sync with knowledge base updates.
