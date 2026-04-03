# Reply Intelligence Dashboard — UX & Architecture (v2, data-driven)

> Based on analysis of 310 real Inxy conversations (of 781 non-empty human replies, of 2,747 total).
> All conversations cached at `/tmp/inxy_all_conversations.json` for reuse.

---

## 1. What We Learned From the Data

### INXY has exactly 3 product offers:

| Offer | What it is | How it's pitched |
|-------|-----------|-----------------|
| **Paygate** | Accept crypto from customers → receive EUR/USD on bank account | Step 1 in every sequence. "Принимать криптоплатежи от клиентов с выводом в фиат." Commission from 0.4%. |
| **Payout** | Mass crypto payouts to contractors/partners via API | Step 2 pivot in Russian DMs. "Выплаты подрядчикам или партнерам за рубежом." Alternative to SWIFT/Wise. |
| **OTC** | Over-the-counter crypto↔fiat exchange for large sums | Mentioned alongside Paygate in Step 1. Some campaigns lead with it (Luma, Trading). Treasury management. |

Campaign names (Trading, Gaming, SaaS, etc.) are **target segments**, not offers. Every segment gets pitched the same 3 products.

### Reply landscape (Inxy, 2,747 total):

| Bucket | Count | % | Notes |
|--------|-------|---|-------|
| Empty/ghost replies (no text) | 1,966 | 72% | Mostly "other" category — opened email but no text |
| Real human replies | 781 | 28% | Actual text content to classify |
| — Warm (interested + meeting) | ~185 | | Send info, schedule call, vague interest |
| — Questions | ~65 | | Pricing, how it works, compliance, specific use cases |
| — Objections | ~275 | | Not relevant, no crypto, not now, have solution |
| — Noise (with text) | ~50 | | Auto-responses, bounces, acknowledgments |
| — Wrong person | ~120 | | Forwarded or redirected |
| — Unsubscribe | ~66 | | Explicit opt-out |

### Surprise finding: "Adjacent demand" replies

Some leads want the REVERSE of what Inxy pitches — they want **on-ramp** (fiat→crypto) or **fiat-to-fiat via crypto rails** or **payouts to Russian cards**. These aren't rejections — they're warm leads with adjacent needs that may or may not be serviceable.

---

## 2. Data Model

### New table: `reply_analysis`

```sql
CREATE TABLE reply_analysis (
    id SERIAL PRIMARY KEY,
    processed_reply_id INTEGER UNIQUE REFERENCES processed_replies(id),
    project_id INTEGER REFERENCES projects(id),

    -- Which INXY product did the lead respond to?
    offer_responded_to VARCHAR(20),  -- paygate | payout | otc | general
    -- How did we determine this?
    -- 1. Keywords in reply text ("выплаты" → payout, "прием платежей" → paygate)
    -- 2. Which sequence step triggered the reply (step1 = paygate, step2 = payout)
    -- 3. Campaign-specific pitch (Luma = OTC, Monetization = Payout)
    -- 4. Ambiguous → general

    -- What is the lead's intent?
    intent VARCHAR(30),
    -- WARM: send_info | schedule_call | interested_vague | redirect_colleague
    -- QUESTION: pricing | how_it_works | compliance | specific_use_case | adjacent_demand
    -- OBJECTION: not_relevant | no_crypto | not_now | have_solution | regulatory | hard_no | spam_complaint
    -- NOISE: empty | auto_response | bounce | gibberish | wrong_person_forward

    -- Warmth 1-5
    warmth_score SMALLINT,  -- 1=hostile, 2=polite decline, 3=neutral/question, 4=interested, 5=ready to meet

    -- What target segment was the campaign aimed at?
    campaign_segment VARCHAR(30),  -- russian_dms | conference | payments | trading | creator | gaming | saas | ecommerce | other

    -- What kind of outreach?
    sequence_type VARCHAR(20),  -- cold_email | cold_linkedin | conference_followup | personalized

    -- Language
    language VARCHAR(5),  -- en | ru | es | de | etc.

    -- Metadata
    reasoning TEXT,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analyzer_model VARCHAR(50)
);

CREATE INDEX idx_reply_analysis_project ON reply_analysis(project_id);
CREATE INDEX idx_reply_analysis_intent ON reply_analysis(intent);
CREATE INDEX idx_reply_analysis_warmth ON reply_analysis(warmth_score);
CREATE INDEX idx_reply_analysis_offer ON reply_analysis(offer_responded_to);
```

No separate `campaign_cluster_rules` table — campaign→segment mapping is done algorithmically (strip prefix, normalize, pattern match). Simple enough to hardcode per project; editable via project settings later if needed.

---

## 3. UX — The Dashboard

### 3.1 Access

New route: `/intelligence?project_id=48`

Accessible from:
- Sidebar: "Intelligence" tab (below Replies, above God Panel)
- Project dropdown: auto-filters to selected project

### 3.2 Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Reply Intelligence          [Project: Inxy ▾]    [Analyze All]  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────┐ │
│  │ Warm   │  │ Quest. │  │ Object.│  │ Noise   │  │ Total    │ │
│  │  185   │  │   65   │  │  275   │  │  256    │  │  781     │ │
│  │ ████   │  │ ██     │  │ █████  │  │ ████    │  │ real     │ │
│  └────────┘  └────────┘  └────────┘  └─────────┘  └──────────┘ │
│                                                                  │
│  Offer breakdown (warm + questions only):                        │
│  Paygate ████████████████████  68%                               │
│  Payout  ██████  18%                                             │
│  OTC     ███  8%                                                 │
│  General ██  6%                                                  │
│                                                                  │
│  ┌─ Filters ──────────────────────────────────────────────────┐  │
│  │ [Intent group ▾] [Offer ▾] [Segment ▾] [Warmth ≥ ▾]      │  │
│  │ [Language ▾] [Date range] [Search...]                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Table ────────────────────────────────────────────────────┐  │
│  │ Group: WARM (185)                                    [▼]   │  │
│  │                                                            │  │
│  │  Lead          Company       Offer    Intent     W  Date   │  │
│  │  ─────────────────────────────────────────────────────────  │  │
│  │  Nadezhda B.   Volchek Cap.  General  Schedule   5  Mar 5  │  │
│  │  Alexey V.     Far Rainbow   Paygate  Schedule   5  Mar 5  │  │
│  │  Denis A.      DACO          General  Schedule   5  Mar 5  │  │
│  │  Oleksandra P. Transcryptio  General  Schedule   5  Feb 25 │  │
│  │  Marcelo B.    Buckzy        Paygate  Explore    4  Mar 12 │  │
│  │  Sergey F.     BoardMaps     Payout   Send info  4  Mar 10 │  │
│  │  Andrei G.     Get Inn       Paygate  Send info  4  Mar 5  │  │
│  │  ...                                                       │  │
│  │                                                            │  │
│  │ Group: QUESTIONS (65)                                [▼]   │  │
│  │  ─────────────────────────────────────────────────────────  │  │
│  │  Ден K.        Regolith      Paygate  Pricing    3  Feb 10 │  │
│  │  Роман D.      Forrards      Payout   Use case   3  Feb 10 │  │
│  │  Alexey V.     Far Rainbow   Paygate  Compliance 3  Mar 3  │  │
│  │  Роман          DCP          Payout   Adjacent   3  Jan 13 │  │
│  │  ...                                                       │  │
│  │                                                            │  │
│  │ Group: SOFT OBJECTIONS (warmth 2) (75)               [▼]   │  │
│  │  ─────────────────────────────────────────────────────────  │  │
│  │  Маша N.       Bolder        General  Not now    2  Mar 14 │  │
│  │  Антон А.      Etton         General  Not now    2  Feb 24 │  │
│  │  ...                                                       │  │
│  │                                                            │  │
│  │ Group: HARD OBJECTIONS (warmth 1) (200)              [▼]   │  │
│  │  ─────────────────────────────────────────────────────────  │  │
│  │  Валерий T.    Aigorithmics  General  No crypto  1  Mar 14 │  │
│  │  Roman          -            General  Hard no    1  Feb 11 │  │
│  │  ...                                                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Table Columns

| Column | Source | Notes |
|--------|--------|-------|
| Lead | `lead_first_name + lead_last_name` | Clickable → opens row detail |
| Company | `lead_company` | |
| Offer | `offer_responded_to` | Chip: blue=Paygate, green=Payout, orange=OTC, gray=General |
| Intent | `intent` | Human-readable label |
| W | `warmth_score` | 1-5, color gradient red→orange→green |
| Segment | `campaign_segment` | Tag |
| Date | `received_at` | |
| CRM | Link icon | `/contacts?project_id=48&search={lead_email}` |

### 3.4 Row Expansion (click to expand)

```
┌─────────────────────────────────────────────────────────────┐
│ Sergey Fedorov — BoardMaps                                   │
│ Campaign: Inxy - Russian DM's 2 [static]                     │
│ Offer: Payout  |  Intent: Send info  |  Warmth: 4            │
│                                                               │
│ REPLY:                                                        │
│ "По приёму от клиентов на данный момент не актуально.         │
│  Что касается выплат из РФ зарубежным партнерам — уже более  │
│  интересно. Направьте информацию о ваших условиях."          │
│                                                               │
│ THREAD (3 messages):                                          │
│   → Step 1: Paygate pitch (crypto→fiat on bank account)       │
│   → Step 2: Payout pivot (mass payouts to contractors)        │
│   ← Reply: Interested in Payout specifically                  │
│                                                               │
│ Status: Not yet actioned  |  [Open in CRM →]                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.5 Grouping Logic

Default: grouped by intent quality, sorted by warmth desc within each group.

| Group | Includes | Color |
|-------|----------|-------|
| **Warm** | send_info, schedule_call, interested_vague, redirect_colleague | Green |
| **Questions** | pricing, how_it_works, compliance, specific_use_case, adjacent_demand | Blue |
| **Soft Objections** | not_now, have_solution (warmth=2, may convert) | Yellow |
| **Hard Objections** | not_relevant, no_crypto, regulatory, hard_no, spam_complaint | Red |
| **Noise** | empty, auto_response, bounce, gibberish, wrong_person_forward | Gray, collapsed by default |

User can:
- Toggle grouped ↔ flat view
- Sort by any column
- Filter by any dimension
- Collapse/expand groups

---

## 4. Classification Logic

### 4.1 Offer Detection (deterministic first, AI fallback)

```python
def detect_offer(reply_text, thread_messages, campaign_name):
    text = reply_text.lower()

    # 1. Keyword match in reply text
    if any(kw in text for kw in ['выплат', 'payout', 'подрядчик', 'contractor', 'mass payment']):
        return 'payout'
    if any(kw in text for kw in ['otc', 'обмен', 'exchange', 'treasury', 'ликвидност']):
        return 'otc'
    if any(kw in text for kw in ['прием платеж', 'accept payment', 'paygate', 'payment gateway', 'платежный']):
        return 'paygate'

    # 2. Which sequence step triggered the reply?
    if thread_messages:
        last_outbound_pos = max(m.position for m in thread_messages if m.direction == 'outbound')
        first_inbound_pos = min(m.position for m in thread_messages if m.direction == 'inbound')
        if first_inbound_pos == 1:  # Reply to step 1
            return 'paygate'
        elif first_inbound_pos > 1:  # Reply to step 2+
            return 'payout'

    # 3. Campaign-specific defaults
    if 'monetization' in campaign_name.lower() or 'creator' in campaign_name.lower():
        return 'payout'
    if 'luma' in campaign_name.lower() or 'trading' in campaign_name.lower():
        return 'otc'

    return 'general'
```

### 4.2 Intent + Warmth (AI classification for non-obvious cases)

Most intents can be classified by simple pattern matching on reply text:
- Schedule call: contains Calendly link, time slots, "созвонимся", "let's meet"
- Send info: "пришлите", "send one pager", "share details"
- Not relevant: "не актуально", "not relevant", "not interested"
- No crypto: "не работаем с криптой", "don't deal in crypto"
- Etc.

For ambiguous cases (~20% of replies), use Claude Haiku batch classification:

```
Classify this reply to a B2B crypto payments outreach.
INXY offers: Paygate (accept crypto→fiat), Payout (mass crypto disbursements), OTC (large crypto↔fiat exchange).

Reply: "{reply_text}"
Campaign: "{campaign_name}"

Return JSON: {"intent": "...", "warmth": 1-5, "offer": "paygate|payout|otc|general"}
Intent options: send_info, schedule_call, interested_vague, redirect_colleague,
  pricing, how_it_works, compliance, specific_use_case, adjacent_demand,
  not_relevant, no_crypto, not_now, have_solution, regulatory, hard_no, spam_complaint,
  empty, auto_response, bounce, gibberish, wrong_person_forward
```

### 4.3 Campaign Segment (deterministic)

```python
SEGMENT_PATTERNS = {
    'russian_dms': ['Russian DM', 'RUS DM', 'Rus DM', 'Rus Data', 'ES - Rus'],
    'conference': ['ICE', 'Token2049', 'Token 2049', 'Money20', 'IGB', 'Ecom Berlin', 'Luma', 'SEP', 'London Tech'],
    'payments': ['Crypto Payments', 'PSP', 'FinTech', 'Merchants', 'Companies using', 'Companies Acc', 'Cryptwerk'],
    'trading': ['Trading', 'Investment', 'Tokenization'],
    'creator': ['Creator', 'Creators', 'Monetization'],
    'gaming': ['Gaming', 'GameFi', 'GameZ', 'iGaming', 'E-Sport', 'P2E', 'Crypto games'],
    'saas': ['SaaS', 'Cloud', 'eSIM', 'EdTech', 'Hosting', 'Mobile', 'CpaaS'],
    'ecommerce': ['Shopify', 'Digital Marketplace', 'Ecom'],
    'cross_sell': ['ES ', 'ES-', 'Baxity', 'INXY-ES', 'feature-', 'lookalike'],
}
```

---

## 5. API Endpoints

```
GET /api/intelligence/?project_id=48
    &intent_group=warm|questions|soft_objection|hard_objection|noise
    &offer=paygate,payout,otc,general
    &segment=russian_dms,conference
    &warmth_min=3
    &language=ru,en
    &date_from=2025-01-01
    &search=<text search in reply + lead name>
    &page=1&page_size=50
    &sort_by=warmth_desc|date_desc|intent_group

GET /api/intelligence/summary?project_id=48
    → { warm: 185, questions: 65, soft_objection: 75, hard_objection: 200, noise: 256,
        by_offer: {paygate: 120, payout: 35, otc: 15, general: 15},
        by_segment: {...} }

POST /api/intelligence/analyze?project_id=48
    → Runs classification on all unanalyzed replies. Returns count processed.

GET /api/intelligence/{reply_id}
    → Full detail: reply + thread + analysis + operator actions
```

---

## 6. Implementation Plan

### Phase 1: DB + Classification (backend only)
1. Alembic migration: `reply_analysis` table
2. Classification service: deterministic rules + Haiku batch fallback
3. Run on all 781 non-empty Inxy replies
4. Verify quality on 50 random samples

### Phase 2: API + Frontend
1. Intelligence API endpoints (list, summary, detail)
2. Frontend page: summary cards, filterable grouped table, row expansion
3. CRM deep links
4. Project selector integration

### Phase 3: Live pipeline
1. Auto-classify new replies on webhook (5-min debounce)
2. Re-analyze button for manual overrides
3. Extend to other projects

---

## 7. What This Is NOT

- Not a replacement for Replies page (operator work queue stays)
- Not a CRM redesign (CRM stays as contact-level grid)
- Not real-time — analytical/read-only layer
- No campaign_cluster_rules table — segment mapping is code, not config

---

## 8. Open Questions

1. **Adjacent demand leads** — should they get a special highlight? These are warm leads wanting on-ramp/fiat-to-fiat that Inxy might serve.
2. **Empty replies (1,966)** — hide completely or show as a "Ghost opens" counter?
3. **Override classifications?** Manual re-labeling in UI?
4. **Export** — CSV/Google Sheets export needed from day 1?
