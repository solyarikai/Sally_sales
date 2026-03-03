# Auto-Replies Architecture

## Business Use Cases

### UC1: New reply arrives (webhook/polling)
- **Trigger**: SmartLead EMAIL_REPLY webhook or GetSales LinkedIn message polling
- **Action**: Classify → Generate draft (Gemini 2.5 Pro) → Translate if needed → Store
- **Model**: Gemini 2.5 Pro (best quality, $0.05, ~15-20s — happens in background before operator opens page)
- **Result**: Reply card has `draft_generated_at` = now

### UC2: Operator provides knowledge feedback (Cmd+K)
- **Trigger**: Operator opens Spotlight, types feedback about reply quality / style
- **Action**: Learning service processes → updates ProjectKnowledge entries
- **Effect**: All existing drafts where `draft_generated_at < knowledge_updated_at` become **stale**
- **UX**: Visible stale replies auto-regenerate (GPT-4o-mini, ~1-2s). "Updating draft..." overlay → "Updated" flash

### UC3: Operator sends reply via system (approve-and-send)
- **Trigger**: Operator clicks Send (with or without edits)
- **Data captured**: OperatorCorrection record (original draft vs final sent, was_edited flag)
- **Learning signal**: If edited → system learns what operator always changes

### UC4: Operator dismisses reply
- **Data captured**: OperatorCorrection (action_type=dismissed)
- **Learning signal**: Draft was bad or reply unnecessary

### UC5: Operator clicks Regenerate (manual)
- **Trigger**: Operator explicitly wants a fresh draft
- **Model**: Gemini 2.5 Pro (default, best quality)
- **Data captured**: OperatorCorrection (action_type=regenerated)
- **Use case**: Old reply with outdated draft that wasn't auto-regenerated (not in viewport), or operator just wants another take

### UC6: Learning cycle runs (from accumulated corrections)
- **Trigger**: Manual `/learning/analyze` or future scheduled trigger
- **Action**: Analyzes patterns across all OperatorCorrections → updates template + ICP knowledge
- **Effect**: Same as UC2 — knowledge updated, stale drafts auto-regenerate when visible

### When NOT to regenerate (avoid waste):
- No knowledge change since draft was generated
- Reply already approved/dismissed/sent
- Operator is actively editing the draft
- Same reply already queued for regeneration

## Current Flow (Mar 3 2026)

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

Winner: Gemini 2.5 Pro for ALL draft generation. GPT-4o-mini ONLY for classification.
Quality is the KPI — never downgrade model for speed.

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

## Smart Auto-Regeneration (Mar 3 2026)

### Architecture: Single model for quality
- **All drafts (initial + auto-regen + manual)**: Gemini 2.5 Pro — 9.5/10 quality ($0.05, ~15-20s)
- **Classification only**: GPT-4o-mini — fast, cheap ($0.003, ~1s)

### Staleness detection:
- Each draft stores `draft_generated_at` timestamp
- Knowledge timestamp: `MAX(ProjectKnowledge.updated_at)` for the project
- Stale = `draft_generated_at < knowledge_updated_at`

### When knowledge updates:
1. Operator provides feedback via Cmd+K → learning service processes → ProjectKnowledge updated
2. ReplyQueue polls learning status → detects completion → refreshes knowledge timestamp
3. IntersectionObserver tracks which reply cards are in viewport
4. Stale + visible → auto-queue for regeneration (Gemini 2.5 Pro, max 1 concurrent)
5. Card shows "Updating draft..." overlay while regenerating
6. "Updated" flash badge for 3s after completion

### Safeguards:
- Skip replies being edited (operator's edits take priority)
- Skip approved/dismissed replies
- `everQueuedRef` prevents re-queueing same reply (resets when knowledge timestamp changes)
- Manual "Regenerate" button still works → uses Gemini 2.5 Pro (default model) for best quality

### Why this approach:
1. **Zero operator friction**: stale drafts update automatically when visible
2. **Best quality always**: Gemini 2.5 Pro for ALL drafts — 9.5/10 KPI, never compromise
3. **Cost-efficient**: auto-regen only fires when knowledge actually changed, only for visible replies
4. **Transparent latency**: "Updating draft..." overlay for ~15-20s — operator sees it's working
5. **GPT-4o-mini only for easy tasks**: classification ($0.003, ~1s) — no reasoning needed

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
