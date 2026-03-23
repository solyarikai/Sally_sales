# Draft Generation Architecture

## Pipeline

```
New reply classified
    ↓
generate_draft()
    ↓
1. Load project knowledge (ICP, outreach, contacts, files, examples)
2. Load reference examples (semantic retrieval via pgvector)
3. Load thread history (SmartLead API or GetSales API)
4. Build DRAFT_REPLY_PROMPT
5. Call Gemini 2.5 Pro (fallback: GPT-4o-mini)
6. Store draft_reply, draft_subject, draft_generated_at
```

## Model Selection

| Model | Cost/reply | Quality | Usage |
|-------|-----------|---------|-------|
| Gemini 2.5 Pro | ~$0.05 | Best (A/B tested) | Default |
| GPT-4o-mini | ~$0.003 | Acceptable | Fallback |
| GPT-4o | ~$0.03 | Worse than Gemini | Not used |

Override via `?model=` query param on regenerate-draft endpoint.

Gemini config: `max_tokens=8000` (thinking tokens count against limit), ~8.5K input, ~3.5K thinking, ~450 output.

## Reference Examples (Semantic Retrieval)

1. **Embed the LEAD MESSAGE** (not the operator reply) using pgvector
2. **Semantic search** finds similar incoming situations
3. **Golden examples** always included regardless of similarity
4. **Quality-weighted re-ranking**: golden(5) > approved(5) > edited(4) > learned(3)

## Prompt Priority

1. **Golden examples** — exact template, copy structure/format/detail level
2. **Other reference replies** — tone and phrasing variation
3. **Project knowledge** — ICP, pricing, features
4. **Defaults** — if no examples exist, category-based generic response

## Draft Rules

- NEVER invent numbers (prices, percentages, timelines)
- NEVER use markdown formatting
- NEVER use placeholder brackets `[Your Name]`
- MIRROR the lead's format (numbered questions → numbered answers)
- Sign off with sender name from project config
- Match the language of the reply (auto-detected)

## Staleness Detection

When project knowledge changes after a draft was generated:
- `draft_generated_at` vs `MAX(ProjectKnowledge.updated_at)`
- If stale → auto-regenerate via IntersectionObserver when card enters viewport
- `everQueuedRef` prevents infinite regeneration loop

## Follow-Up Drafts

Same pipeline as regular drafts but:
- Generated proactively (scheduler every 3 min)
- Child `ProcessedReply` with `parent_reply_id`, `follow_up_number=1`
- SQL filter: no newer inbound from same lead, approved_at > 60 days ago
- No "Generate Follow-up" button — drafts always pre-loaded

## Approve and Send

```
Operator clicks Send
    ↓
POST /api/replies/{id}/approve-and-send
    ↓
1. Validate draft exists, not already sent
2. Email channel → SmartLead send_reply API
   LinkedIn channel → GetSales send_linkedin_message API (or manual copy)
3. Set approval_status = "approved", approved_at = now()
4. Record OperatorCorrection for learning system
5. Auto-embed as reference example (if project configured)
6. Create outbound ContactActivity
```

### Contact Lookup for Send

```python
# Email leads
if reply.lead_email:
    contact = Contact.email == reply.lead_email

# LinkedIn leads (no email)
elif reply.getsales_lead_uuid:
    contact = Contact.getsales_id == reply.getsales_lead_uuid
```

Both paths work — the system does NOT require email to send.
