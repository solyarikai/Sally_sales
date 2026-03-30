# Reply Intelligence — Full Architecture

> Deterministic reply classification engine for B2B outreach analysis.
> Built for Inxy (crypto payments), extensible to any project.
> Route: `/intelligence` | API: `/api/intelligence/`

---

## 1. System Overview

Reply Intelligence classifies incoming replies by **intent**, **warmth**, **offer type**, **campaign segment**, **sequence type**, and **language** — all using deterministic rules (no AI cost). It sits as a read-only analytical layer on top of the existing Replies pipeline.

```
Reply received (webhook/sync)
        ↓
ProcessedReply created (existing pipeline)
        ↓
Operator clicks "Analyze" or scheduled batch
        ↓
classify_reply() — 4-phase deterministic rules
        ↓
ReplyAnalysis record (1:1 with ProcessedReply)
        ↓
Intelligence UI — grouped, filtered, searchable
```

---

## 2. Database Schema

### `reply_analysis` table

```sql
CREATE TABLE reply_analysis (
    id SERIAL PRIMARY KEY,
    processed_reply_id INTEGER UNIQUE NOT NULL REFERENCES processed_replies(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Classification
    offer_responded_to VARCHAR(20),   -- paygate | payout | otc | general
    intent VARCHAR(30),               -- 16 intent types (see taxonomy below)
    warmth_score SMALLINT,            -- 0-5 (0=noise, 1=hostile, 2=polite decline, 3=question, 4=interested, 5=ready to meet)
    campaign_segment VARCHAR(30),     -- russian_dms | conference | payments | trading | creator | gaming | saas | ecommerce | cross_sell | other
    sequence_type VARCHAR(20),        -- cold_email | cold_linkedin | conference_followup | personalized
    language VARCHAR(10),             -- en | ru | unknown

    -- Metadata
    reasoning TEXT,                   -- "deterministic_v1"
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analyzer_model VARCHAR(50),       -- "rules_v1"

    -- Indexes
    INDEX ix_project (project_id),
    INDEX ix_offer (offer_responded_to),
    INDEX ix_intent (intent),
    INDEX ix_warmth (warmth_score)
);
```

**Key constraint**: `UNIQUE(processed_reply_id)` — each reply has at most one analysis. Cascade delete keeps integrity.

---

## 3. Intent Taxonomy

### 5 Groups, 16 Intents

| Group | Intent | Warmth | Business Meaning |
|-------|--------|--------|------------------|
| **warm** | `send_info` | 4 | "Send me details/one-pager" |
| | `schedule_call` | 5 | "Let's meet" / Calendly / time slot |
| | `interested_vague` | 4 | "Sounds interesting" / "Sure" |
| | `redirect_colleague` | 3 | "Talk to my colleague X" |
| **questions** | `pricing` | 3 | "What are your rates?" |
| | `how_it_works` | 3 | "How does it work?" |
| | `compliance` | 3 | "Are you regulated?" / "Licenses?" |
| | `specific_use_case` | 3 | Describes exact need, asks if it fits |
| | `adjacent_demand` | 3 | Wants on-ramp, fiat-to-fiat, reverse of offer |
| **soft_objection** | `not_now` | 2 | "Not now, maybe later" |
| | `have_solution` | 2 | "We have our own infrastructure" |
| **hard_objection** | `not_relevant` | 1 | "Not relevant to us" |
| | `no_crypto` | 1 | "We don't deal in crypto" |
| | `regulatory` | 1 | "Regulator doesn't allow this" |
| | `hard_no` | 1 | Short rejection, "don't write me" |
| | `spam_complaint` | 1 | "How did you get my email?" / hostile |
| **noise** | `empty` | 0 | No reply text |
| | `auto_response` | 0 | OOO, ticket system, auto-forward |
| | `bounce` | 0 | Delivery failure |
| | `gibberish` | 0 | Single chars, broken encoding |
| | `wrong_person_forward` | 0 | "Redirected to X" |

---

## 4. Classification Engine

**File**: `backend/app/services/intelligence_service.py`

### 4-Phase Pipeline

```
Phase 1: Global Guards     → catches bounces, auto-responses, gibberish (any category)
Phase 2: Cold Category Gate → subclassifies not_interested / unsubscribe / wrong_person
Phase 3: Warm Patterns      → pattern-matches interested / meeting / question categories
Phase 4: Other Fallback     → applies same patterns to "other" category at lower confidence
```

### Phase 1: Global Guards

Fires regardless of AI category. Catches system-level noise:

| Pattern | Intent | Warmth |
|---------|--------|--------|
| "delivery failed", "undeliverable", "returned to sender" | `bounce` | 0 |
| "out of the office", "auto-reply", "автоответ" | `auto_response` | 0 |
| Text < 5 chars, no alphabetic | `gibberish` | 0 |

### Phase 2: Cold Category Gate

For replies already categorized as `not_interested`, `unsubscribe`, `wrong_person`:

- **wrong_person** → `wrong_person_forward` (0)
- **unsubscribe** → check spam signals → `spam_complaint` (1) or `hard_no` (1)
- **not_interested** → subclassify:
  - Spam complaint patterns → `spam_complaint` (1)
  - "don't work with crypto" → `no_crypto` (1)
  - Regulatory blocker → `regulatory` (1)
  - "not now" / "maybe later" → `not_now` (2)
  - "have our own solution" → `have_solution` (2)
  - Short/vague → `hard_no` (1) or `not_relevant` (1)

### Phase 3: Warm & Question Patterns

**Critical**: Text is first cleaned via `_strip_quoted_and_signature()` to remove:
- Quoted outbound messages (`>`, `&gt;` prefixed lines)
- Quote headers ("wrote:", "пишет:", "From: serge")
- Email signatures (after `--`, image CIDs)
- HTML entities

Pattern matching runs on **cleaned text only** to prevent false positives from keywords in INXY's own outbound sequences.

**Warmth hierarchy** (highest match wins):

1. `schedule_call` (5) — "созвонимся", "let's meet", Calendly link, `HH:MM` + day
2. `send_info` (4) — "пришлите", "send me details", "готов рассмотреть"
3. `interested_vague` (4) — "да интересно", "sounds interesting"
4. `pricing` (3) — "rates", "pricing", "комиссия", "сколько стоит"
5. `how_it_works` (3) — "как это работает", "can you explain"
6. `compliance` (3) — "комплаенс", "лицензии", "regulated"
7. `adjacent_demand` (3) — "on-ramp", "fiat to crypto", "обратная задача"
8. `specific_use_case` (3) — question category + text length > 50
9. `redirect_colleague` (3) — "talk to my colleague", "переслал коллеге"

**Guard patterns** (filtered out as noise):
- LinkedIn connection noise: "join your professional network"
- Auto-forwards: "forwarded to the team"
- Counter-pitches: "join our", "can you introduce"

### Phase 4: "Other" Category

Same warmth hierarchy but less aggressive. Catches miscategorized replies.

---

## 5. Offer Detection

**Function**: `detect_offer(reply_text, campaign_name) → str`

Priority order:

1. **Keywords in cleaned reply text**:
   - Payout: "выплат", "payout", "contractor", "mass payment", "payroll"
   - OTC: "otc", "exchange", "treasury", "ликвидност"
   - Paygate: "accept payment", "payment gateway", "принимать платеж"

2. **Campaign name defaults**:
   - "monetization", "creator", "eor", "f&p" → payout
   - "luma", "trading" → otc
   - Everything else → general

### INXY's 3 Actual Products

| Offer | What it is | Outbound pitch |
|-------|-----------|----------------|
| **Paygate** | Accept crypto → receive EUR/USD on bank | Step 1 in every sequence. Commission from 0.4% |
| **Payout** | Mass crypto payouts to contractors via API | Step 2 pivot in Russian DMs. Alternative to SWIFT/Wise |
| **OTC** | Over-the-counter crypto↔fiat exchange | Mentioned alongside Paygate. Some campaigns lead with it |

Campaign names (Trading, Gaming, SaaS) are **target segments**, not products. Every segment gets pitched the same 3 products.

---

## 6. Segment Detection

**Function**: `detect_segment(campaign_name) → str`

Deterministic pattern match on campaign name:

| Segment | Campaign patterns |
|---------|-------------------|
| `russian_dms` | "Russian DM", "RUS DM", "Rus Data", "ES - Rus" |
| `conference` | "ICE", "Token2049", "Money20", "Ecom Berlin", "London Tech" |
| `payments` | "Crypto Payments", "PSP", "FinTech", "Merchants" |
| `trading` | "Trading", "Investment", "Tokenization" |
| `creator` | "Creator", "Monetization" |
| `gaming` | "Gaming", "GameFi", "iGaming", "E-Sport", "P2E" |
| `saas` | "SaaS", "Cloud", "EdTech", "Hosting", "eSIM" |
| `ecommerce` | "Shopify", "Digital Marketplace" |
| `cross_sell` | "ES ", "ES-", "Baxity", "INXY-ES", "lookalike" |
| `other` | Everything else |

---

## 7. Other Detectors

### Language Detection
Count Cyrillic vs Latin characters. Cyrillic > Latin → "ru", else → "en".

### Sequence Type Detection
- Conference patterns → "conference_followup"
- "personalization" in name → "personalized"
- channel == "linkedin" → "cold_linkedin"
- Default → "cold_email"

---

## 8. Backend API

**File**: `backend/app/api/intelligence.py`
**Router prefix**: `/intelligence`

### GET /intelligence/

List analyzed replies with filtering and sorting.

| Param | Type | Description |
|-------|------|-------------|
| `project_id` | int (required) | Project scope |
| `intent_group` | str | warm \| questions \| soft_objection \| hard_objection \| noise |
| `offer` | str | Comma-separated: paygate, payout, otc, general |
| `segment` | str | Comma-separated segment names |
| `warmth_min` | int (0-5) | Minimum warmth |
| `warmth_max` | int (0-5) | Maximum warmth |
| `language` | str | en \| ru |
| `search` | str | Full-text in reply text, lead name, company |
| `sort_by` | str | warmth_desc (default) \| date_desc \| intent_group |
| `page` | int | Default 1 |
| `page_size` | int | Default 50, max 200 |

**Response**: `ReplyAnalysisItem[]` — joined data from `reply_analysis` + `processed_replies`.

### GET /intelligence/summary/

Aggregated statistics for dashboard cards.

| Param | Type | Description |
|-------|------|-------------|
| `project_id` | int (required) | Project scope |

**Response**:
```json
{
  "total": 781,
  "by_group": { "warm": 185, "questions": 65, "soft_objection": 75, "hard_objection": 200, "noise": 256 },
  "by_offer": { "paygate": 120, "payout": 35, "otc": 15, "general": 15 },
  "by_segment": { "russian_dms": 400, "conference": 80, ... },
  "by_intent": { "schedule_call": 60, "send_info": 80, ... }
}
```

### POST /intelligence/analyze/

Trigger batch classification of unanalyzed replies.

| Param | Type | Description |
|-------|------|-------------|
| `project_id` | int (required) | Project scope |
| `rebuild` | bool | Delete existing + re-classify all |

**Logic**:
1. Fetch project, verify `campaign_filters` configured
2. Query unanalyzed replies matching campaign_filters, excluding out_of_office
3. For each: `classify_reply()` → create `ReplyAnalysis` record
4. Batch flush, return count

### GET /intelligence/count/

Simple count of analyzed replies for a project.

---

## 9. Frontend UX

**File**: `frontend/src/pages/IntelligencePage.tsx`
**Route**: `/intelligence`

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  🧠 Reply Intelligence   [Project: Inxy]    [Analyze]       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Warm 185] [Questions 65] [Soft Obj 75] [Hard Obj 200]     │  ← clickable filter cards
│  ────────────────────────────────────────                    │
│  Paygate 68%  |  Payout 18%  |  OTC 8%  |  General 6%      │  ← clickable offer breakdown
│                                                              │
│  [Search...________________________]  [Clear filters]        │
│                                                              │
│  ▼ WARM (185)                                    [CRM →]     │  ← collapsible group
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Lead         Company       Offer    Intent    W Date │    │
│  │ Nadezhda B.  Volchek Cap.  General  Schedule  5 Mar5 │    │
│  │ Alexey V.    Far Rainbow   Paygate  Schedule  5 Mar5 │    │
│  │ ▼ [expanded row with full reply text + metadata]     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ▼ QUESTIONS (65)                                            │
│  ▼ SOFT OBJECTIONS (75)                                      │
│  ▶ NOISE (256)                                  ← collapsed  │
└─────────────────────────────────────────────────────────────┘
```

### State Management

```typescript
// Core data
const [items, setItems] = useState<ReplyAnalysisItem[]>([]);
const [summary, setSummary] = useState<IntelligenceSummary | null>(null);

// Filters
const [intentGroupFilter, setIntentGroupFilter] = useState<string | null>(null);
const [offerFilter, setOfferFilter] = useState<string | null>(null);
const [searchText, setSearchText] = useState('');

// UI state
const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['noise']));
```

### Grouping (client-side `useMemo`)

Items grouped by `intent_group` field. 5 groups rendered as collapsible sections. Noise collapsed by default.

### Visual Design

- **Intent group colors**: green (warm), blue (questions), yellow (soft obj), red (hard obj), zinc (noise)
- **Warmth indicator**: 5 dots, colored gradient red→orange→yellow→green→green
- **Offer badges**: blue chip (paygate), green (payout), orange (otc), zinc (general)
- **Dark mode**: uses `themeColors(isDark)` tokens

### Expanded Row Detail

Shows on click:
- **Left panel**: Full reply text (scrollable, max 200px height)
- **Right panel**: Campaign name, original category, approval status, sequence type, language
- **CRM link**: `/contacts?project_id=X&search=LEAD_EMAIL`

### CRM Deep Links

Each group header links to CRM filtered by reply categories:
- warm → `reply_category=interested,meeting_request`
- questions → `reply_category=question`
- soft_objection → `reply_category=not_interested` (warmth 2)
- hard_objection → `reply_category=not_interested,unsubscribe` (warmth 1)

---

## 10. API Client

**File**: `frontend/src/api/intelligence.ts`

```typescript
export const intelligenceApi = {
  list(params: { project_id, intent_group?, offer?, segment?, warmth_min?, warmth_max?, language?, search?, sort_by?, page?, page_size? }): Promise<ReplyAnalysisItem[]>
  summary(project_id: number): Promise<IntelligenceSummary>
  analyze(project_id: number): Promise<{ classified: number; project_id: number }>
  count(project_id: number): Promise<{ count: number }>
};
```

---

## 11. Data Flow End-to-End

```
1. INGESTION
   SmartLead webhook / GetSales webhook / polling sync
   → ProcessedReply record (reply_text, lead metadata, campaign, category)

2. ANALYSIS TRIGGER
   Manual: "Analyze" button in UI
   Batch: scheduled job (not yet implemented as auto)
   → POST /intelligence/analyze/?project_id=X

3. CLASSIFICATION (per reply)
   → _strip_quoted_and_signature(reply_text) — clean text
   → classify_reply(cleaned_text, category, campaign_name, channel)
   → 4-phase pipeline → {intent, warmth_score}
   → detect_offer(cleaned_text, campaign_name) → offer_responded_to
   → detect_segment(campaign_name) → campaign_segment
   → detect_sequence_type(campaign_name, channel) → sequence_type
   → detect_language(cleaned_text) → language
   → CREATE ReplyAnalysis record

4. QUERY
   GET /intelligence/?project_id=X&intent_group=warm&...
   → JOIN reply_analysis + processed_replies
   → Compute intent_group from intent
   → Filter, sort, paginate
   → Return joined items

5. DISPLAY
   Frontend groups by intent_group
   → Summary cards with counts
   → Collapsible grouped table
   → Expandable row details
   → CRM deep links
```

---

## 12. Key Design Decisions

### Why Deterministic Rules (No AI)?

- **Zero cost** — no API calls per classification
- **Transparent** — every pattern is explicit, auditable
- **Reproducible** — same input always gives same output
- **Fast** — classifies hundreds of replies in <1 second
- **Extensible** — add patterns per project without retraining

Original plan had Claude Haiku as fallback for ambiguous cases (~20%). The deterministic engine proved sufficient for >95% accuracy, so AI fallback was never implemented.

### Why Text Cleaning Matters

INXY's outbound sequences contain the exact keywords used for offer detection ("принимать криптоплатежи", "выплаты подрядчикам"). Without stripping quoted outbound text, every reply to Step 2 would false-positive match "payout" keywords from the quoted outbound message — not from the lead's actual reply.

### Why 1:1 Mapping (Not Embedded in ProcessedReply)

- Separation of concerns: reply processing vs. analytical classification
- Can re-analyze without touching the reply pipeline
- Can extend with multiple analysis versions/models later
- Cascade delete means no orphaned analysis records

### Why Project-Scoped

Classification patterns (offer detection, segment detection) are project-specific. INXY has 3 products; EasyStaff Global has different products. The taxonomy is the same (intent groups are universal for B2B outreach), but detection patterns vary per project.

---

## 13. Inxy-Specific Findings

From analysis of 310 real conversations (of 781 non-empty human replies, of 2,747 total):

### Reply Landscape

| Bucket | Count | % |
|--------|-------|---|
| Empty/ghost replies (no text) | 1,966 | 72% |
| Real human replies | 781 | 28% |
| — Warm | ~185 | |
| — Questions | ~65 | |
| — Objections | ~275 | |
| — Noise (with text) | ~50 | |
| — Wrong person | ~120 | |
| — Unsubscribe | ~66 | |

### Adjacent Demand (Surprise Finding)

Some leads want the **reverse** of what INXY pitches:
- **On-ramp** (fiat→crypto): "У нас обратная задача - нам надо покупать крипту"
- **Fiat-to-fiat via crypto rails**: "принимать злотые/евро и выплачивать тезер?"
- **Payouts to RU cards**: "перевод фиатных платежей в РФ на карты МИР"
- **USD custody settlement**: "сеттлемент в USD на наш кастоди счет"

These are classified as `adjacent_demand` (warmth 3) — warm leads with needs that may or may not be serviceable.

### Outbound Sequence Pattern (Russian DMs)

- **Step 1**: Paygate pitch → "принимать криптоплатежи от клиентов с выводом в фиат"
- **Step 2**: Payout pivot → "задача выплат подрядчикам за рубежом"
- **Step 3**: Soft close → "не буду отвлекать, если встанет вопрос — напишите"

---

## 14. File Map

```
backend/
  app/
    api/intelligence.py              # API endpoints
    models/reply_analysis.py         # SQLAlchemy model
    services/intelligence_service.py # Classification engine
    schemas/reply.py                 # Pydantic schemas (ReplyAnalysisItem, IntelligenceSummary)

frontend/
  src/
    pages/IntelligencePage.tsx       # Main UI component
    api/intelligence.ts              # API client

docs/inxy/
  REPLY_INTELLIGENCE_ARCHITECTURE.md # This document
  REPLY_INTELLIGENCE_UX.md           # Original UX spec (v2, data-driven)
  INXY_ANALYSIS_PLAN.md              # Data extraction plan
  INXY_BATCH1_ANALYSIS.md            # First 100 conversations analysis
  INXY_BATCH2_ANALYSIS.md            # Cumulative 310 conversations analysis
```
