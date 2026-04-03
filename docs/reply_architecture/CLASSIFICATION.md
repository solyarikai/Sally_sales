# Reply Classification Architecture

## Two-Layer Classification

### Layer 1: AI Classifier (reply_processor.py)

Assigns `ProcessedReply.category` using GPT/Gemini with `CLASSIFICATION_PROMPT`.

**Categories:**

| Category | Color | Description |
|----------|-------|-------------|
| `meeting_request` | Green | Wants to schedule, shares availability, timezone, location |
| `interested` | Green | Any positive signal, shares contact info (Telegram/WhatsApp/phone) |
| `question` | Blue | Specific questions before deciding |
| `other` | Gray | Truly ambiguous (should be rare) |
| `not_interested` | Red | Explicit decline |
| `out_of_office` | Gray | Auto-reply |
| `wrong_person` | Red | Redirects to someone else (NOT sharing own contact info) |
| `unsubscribe` | Red | Opt-out request |

**Key rules in the prompt:**
- `meeting_request` includes availability sharing ("I'm free Thursday", "back in office Monday", timezone mentions)
- `interested` includes sharing own contact info (Telegram, WhatsApp, phone) — NOT wrong_person
- `wrong_person` is ONLY for redirecting to a different person
- Short positive replies ("ok", "yes", "давайте") → `interested`
- When in doubt → `interested`

### Layer 2: Intelligence Service (intelligence_service.py)

Assigns `intent` and `warmth_score` for analytics. Does NOT change the category.

**Phase flow:**
```
Phase 1: CATEGORY GATES
    → Trust AI classifier for cold categories
    → Rescue: contact-sharing in "wrong_person" → interested_vague (warmth 4)

Phase 2: COLD CATEGORIES (never promote to warm)
    → wrong_person → wrong_person_forward (warmth 0)
    → unsubscribe → hard_no or spam_complaint (warmth 1)
    → not_interested → subclassify: no_crypto, regulatory, not_now, have_solution, hard_no

Phase 3: WARM + QUESTION CATEGORIES
    → Schedule detection: patterns + calendly + time slots + availability sharing
    → Availability check: 2+ day names OR day name + timezone/location → schedule_call (warmth 5)
    → Send info patterns → send_info (warmth 4)
    → Pricing/compliance/how-it-works → warmth 3
    → Interested vague → warmth 4

Phase 4: "OTHER" CATEGORY
    → Check for negative signals first
    → Strong warm signals rescue → interested_vague (warmth 3)
    → Availability sharing rescue → schedule_call (warmth 4)
    → Default: auto_response (warmth 0)
```

### Warmth Scale

| Score | Meaning | Examples |
|-------|---------|----------|
| 0 | Noise/auto | Bounce, gibberish, connection ack |
| 1 | Hard no | Unsubscribe, spam complaint, explicit decline |
| 2 | Soft no | Not now, have solution |
| 3 | Warm question | Pricing, how it works, compliance |
| 4 | Interested | Send info, vague interest, contact sharing |
| 5 | Hot | Schedule call, calendly link, time slot offers |

## Common Misclassification Patterns (Fixed)

| Message Pattern | Wrong Label | Correct Label | Fix |
|----------------|-------------|---------------|-----|
| "I'll be on Singapore time Monday" | Other | Meeting | Availability sharing = meeting_request |
| "напишите в тг @handle" | Wrong Person | Interested | Sharing own contact = interested |
| "ok" / "давайте" | Other | Interested | Short positive = interested |
| "back in office Wednesday" | Other | Meeting | Location + day = availability |

## Frontend Tab Mapping

| Tab | Categories | Filter |
|-----|-----------|--------|
| Inbox | meeting_request + interested + question | `needs_reply=true` |
| Meetings | meeting_request | `needs_reply=true` |
| Interested | interested | `needs_reply=true` |
| Questions | question | `needs_reply=true` |
| Not Interested | not_interested | always visible |
| OOO | out_of_office | always visible |
| Wrong Person | wrong_person | always visible |
| Unsubscribe | unsubscribe | always visible |
