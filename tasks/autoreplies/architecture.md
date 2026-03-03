# Auto-Replies Architecture

## Current Flow (On-Demand, Mar 3 2026)

```
NEW REPLY ARRIVES (webhook: SmartLead EMAIL_REPLY / GetSales LinkedIn message)
  |
  1. CLASSIFY intent ─── GPT-4o-mini ($0.003, ~1s)
  |   Output: category (interested/meeting_request/question/not_interested/...)
  |
  2. GENERATE DRAFT ─── Gemini 2.5 Pro ($0.05, ~15-20s)
  |   Inputs assembled:
  |     a) Base prompt (DRAFT_REPLY_PROMPT) with lead info + sender identity
  |     b) Project knowledge (ProjectKnowledge table: ICP, templates, files, golden examples)
  |     c) 20 reference examples from thread_messages (operator's REAL past replies)
  |        - Only qualified categories: interested, meeting_request, question
  |        - Sorted: same category first, then longest (most detailed) first
  |        - Deduplicated by content prefix
  |     d) Reply prompt template (if project has one assigned)
  |   Output: JSON {subject, body, tone}
  |
  3. DETECT LANGUAGE + TRANSLATE ─── GPT-4o-mini ($0.003, ~1s)
  |   If language is not English or Russian → translate to English
  |   Stores: detected_language, translated_body, translated_draft
  |
  4. STORE + NOTIFY
      - Save to processed_replies table
      - Send to Slack / Telegram

OPERATOR OPENS REPLIES PAGE
  |
  Replies loaded from DB, displayed as cards
  Both original message and draft shown
  If non-en/ru language: original + English translation shown inline (no toggle)

  ON-DEMAND ACTIONS:
  - Click "Regenerate" → POST /api/replies/{id}/regenerate-draft
    Uses Gemini 2.5 Pro (default) or ?model=gpt-4o-mini for fast mode
  - Edit draft → inline text editor
  - Send → approve-and-send endpoint
  - Skip → dismiss
```

## Model Selection (A/B Tested Mar 3 2026)

| Model | Cost/reply | Quality (KPI: error vs operator) | Speed |
|-------|-----------|----------------------------------|-------|
| GPT-4o-mini | $0.003 | 7/10 - good structure, sometimes compresses pricing | ~1-2s |
| GPT-4o | $0.05 | 5/10 - over-summarizes, skips pricing details | ~3-5s |
| **Gemini 2.5 Pro** | **$0.05** | **9.5/10 - near-perfect operator style match** | ~15-20s |

Winner: Gemini 2.5 Pro. Copies operator's exact phrasing, full pricing breakdowns, no placeholders.

### Token usage (Gemini 2.5 Pro per reply):
- Input: ~8,500 tokens (prompt + knowledge + 20 reference examples)
- Thinking: ~3,000 tokens (internal reasoning, billed as output)
- Output: ~450 tokens (the actual reply)
- Total: ~12,000 tokens

### Cost estimates:
- Per reply: $0.06 (classify + draft + translate)
- 10 replies/day: $0.60/day
- Monthly: ~$18/month

## Reference Examples System

Primary data source: `thread_messages` table (outbound messages from SmartLead conversations).

Why NOT `contact_activities`: body truncated at 500 chars.
Why NOT `OperatorCorrection`: operators reply directly in SmartLead, not through our Send button. Only 2 records for EasyStaff RU.

`thread_messages.body` has full text (up to 4000+ chars) — the actual operator replies with full pricing, bullet points, CTAs.

### Loading strategy:
1. Fetch 100 most recent outbound messages for this project
2. Filter: only qualified categories (interested, meeting_request, question)
3. Filter: skip short follow-ups (<400 chars after HTML stripping)
4. Deduplicate by content prefix (150 chars)
5. Sort: same category as current lead first, then by length (longest = most detail)
6. Return top 20

EasyStaff RU has 1,112 outbound messages, 219 from qualified categories.

## What Changed: Auto-Regen → On-Demand

### BEFORE (auto-regeneration, removed Mar 3):
- IntersectionObserver tracked which reply cards were visible in viewport
- When knowledge updated (via Cmd+K feedback), system detected "stale" drafts
  (draft_generated_at < MAX(knowledge.updated_at))
- Stale visible drafts were auto-regenerated in background (max 2 concurrent)
- Problem: with Gemini 2.5 Pro (~20s/reply), this blocked the UI and wasted API calls
- Problem: complexity with no clear user benefit — operator didn't ask for regeneration

### NOW (on-demand):
- No automatic regeneration. Zero background API calls.
- Operator clicks "Regenerate" button when they want a fresh draft.
- Page loads instantly (just DB query, no AI calls).
- Learning still works: Cmd+K feedback updates knowledge, new replies use updated knowledge.
- Old replies keep their existing drafts until operator explicitly refreshes them.

### Why on-demand is better:
1. **Fast**: page loads in <1s, no 20s Gemini calls blocking
2. **No wasted cost**: only regenerate what operator actually needs
3. **Simple**: no staleness tracking, no IntersectionObserver, no queue management
4. **Predictable**: operator controls when AI runs, not the system

## Translation UX

For non-English/non-Russian messages:
- Lead message: original shown first, English translation shown below (dashed divider)
- Draft suggestion: original draft shown first, English translation below
- Both always visible — no toggle button, no extra clicks
- Language badge shown on card header

## Files

- `backend/app/services/reply_processor.py` — core: classify, generate draft, translate, reference examples
- `backend/app/api/replies.py` — API endpoints: list, regenerate-draft, send, dismiss
- `backend/app/services/gemini_client.py` — Gemini API client
- `backend/app/services/learning_service.py` — Cmd+K feedback processing, golden examples extraction
- `frontend/src/components/ReplyQueue.tsx` — replies UI
- `frontend/src/api/replies.ts` — frontend API client
