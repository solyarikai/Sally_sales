# Intelligence v2 — AI Analysis + UX Overhaul

> Replace deterministic regex classification with AI-powered analysis that extracts structured insights, free-text interests, and searchable tags from every reply.

---

## Problem

The current Intelligence page uses **regex pattern matching** to classify replies. It catches intent (interested/not_interested) and offer (paygate/payout/otc) but completely misses the **specific needs** that make data actionable.

**Example — Stephane Meng (REasy, reasy.fr)**:
- Current system: offer=`general`, intent=`Pricing`, warmth=3
- What he actually wants: **crypto→fiat settlement via SWIFT to pay suppliers in China/rest of world in USD. Needs third-party beneficiary support, not just off-ramp to own accounts.**
- Follow-up reveals: suppliers don't use crypto, need SWIFT off-ramp specifically
- Business value: this is a **product feature request** shared by multiple leads — INXY could decide whether to add SWIFT settlement based on demand

Without extracting this level of detail, Intelligence is just a fancier category filter. With it, you can **search across all replies for "SWIFT settlement"** and find every lead with this need, estimate demand, and make product decisions.

---

## Part A: AI Analysis Engine

### A1. Database: New columns on `reply_analysis`

**File**: `backend/app/models/reply_analysis.py`

```python
# AI-extracted insights
interests = Column(Text, nullable=True)
# Free-text: "Crypto→fiat settlement via SWIFT to pay suppliers in China.
#             Needs third-party beneficiary support, not off-ramp to own accounts."

tags = Column(ARRAY(String), nullable=True)
# Searchable: ["swift-settlement", "china-suppliers", "crypto-to-fiat",
#              "third-party-beneficiaries", "payout", "ready-to-meet"]
```

Alembic migration: `ALTER TABLE reply_analysis ADD COLUMN interests TEXT, ADD COLUMN tags TEXT[]`

### A2. AI Classification Function

**File**: `backend/app/services/intelligence_service.py`

New async function `ai_classify_reply()` using **Gemini 2.5 Pro** via existing `gemini_generate()` client (`backend/app/services/gemini_client.py`).

**Why Gemini 2.5 Pro?**
- Already used for draft generation ($0.05/reply)
- Handles bilingual (EN/RU) content natively
- JSON output mode available
- ~8.5K input tokens, ~450 output tokens per classification

**Prompt** (system + user):

```
SYSTEM:
You are an intelligence analyst for INXY.io, a crypto payment infrastructure company.
INXY offers exactly 3 products:
1. Paygate — accept crypto payments from customers, convert to EUR/USD on bank account. Commission from 0.4%.
2. Payout — mass crypto payouts to contractors/partners abroad via API. Alternative to SWIFT/Wise.
3. OTC — over-the-counter crypto↔fiat exchange for large sums, treasury management.

Analyze the lead's reply to our outreach and extract structured intelligence.

USER:
OUTBOUND (what we pitched):
{last_outbound_message}

LEAD REPLY:
{cleaned_reply_text}

Campaign: {campaign_name} | Channel: {channel}

Return ONLY valid JSON:
{
  "intent": "schedule_call|send_info|interested_vague|redirect_colleague|pricing|how_it_works|compliance|specific_use_case|adjacent_demand|not_relevant|no_crypto|not_now|have_solution|regulatory|hard_no|spam_complaint|auto_response|bounce|gibberish|wrong_person_forward|empty",
  "warmth_score": 0-5,
  "offer_responded_to": "paygate|payout|otc|general",
  "interests": "<STRICTLY FINANCIAL. 1-2 concrete sentences about what specific financial product/service the lead needs. Mention: settlement methods (SWIFT, SEPA, wire), crypto products (on-ramp, off-ramp, OTC), currencies (USDT, USD, EUR), volumes, corridors (where money flows from→to). Do NOT write 'wants to schedule a call' or 'interested in learning more' — describe the financial need. If rejection — describe what alternative they use or why no fit.>",
  "tags": ["<lowercase-hyphenated financial tags only>"],
  "geo_tags": ["<money-flow-corridor countries, NOT where the person lives>"],
  "language": "en|ru|other"
}

CRITICAL — interests rules:
- GOOD: "Needs crypto→fiat settlement via SWIFT to pay suppliers in China. Third-party beneficiaries required."
- GOOD: "Wants on-ramp for purchasing crypto with EUR. Currently uses Binance P2P but needs compliant solution."
- BAD: "The lead is interested in scheduling a call to discuss solutions."
- BAD: "Wants to learn more about the product and see pricing."

CRITICAL — geo_tags rules:
- geo_tags = money flow corridors, NOT the person's location
- Capture WHERE money needs to flow (sender→receiver geography)
- GOOD: ["china", "hong-kong"] — because lead wants to PAY suppliers in China/HK
- GOOD: ["cis", "turkey"] — because lead wants to SEND payouts to CIS/Turkey contractors
- BAD: ["france"] — just because the lead is French (that's their location, not a corridor)
- If lead says "pay suppliers in Asia" → ["china", "southeast-asia", "india"]
- If no money flow direction mentioned, return empty array

Tag categories (STRICTLY FINANCIAL — no outreach/status tags):
- Settlement methods: swift-settlement, sepa-settlement, wire-transfer, local-bank-transfer, ach
- Crypto flow: on-ramp, off-ramp, crypto-to-fiat, fiat-to-crypto, stablecoin-settlement, usdt, usdc
- Financial products: supplier-payments, contractor-payouts, mass-disbursements, treasury-management, fx-conversion
- Payment infra: payment-gateway, merchant-acceptance, white-label, api-integration, pos-terminal
- Compliance: kyc-kyb, licensing, regulatory-block, sanctions-risk, aml
- Industry: gaming, fintech, trading, ecommerce, marketplace, luxury, saas, affiliate, remittance
- Objection: no-crypto, have-solution, not-priority, budget-constraint
- Specific needs: third-party-beneficiaries, multi-currency, high-volume, recurring-payments, invoicing

IMPORTANT: Do NOT use outreach-status tags like "ready-to-meet", "needs-info", "referred-colleague", "wants-pricing".
These are already captured by the intent field. Tags must describe WHAT the lead needs financially.
```

**Key design decisions**:
- Include last outbound message for context (fetch from `thread_messages` table)
- Clean reply text via existing `_strip_quoted_and_signature()` before AI call
- `campaign_segment` and `sequence_type` stay **deterministic** (campaign name-based) — no AI waste
- Fall back to existing `classify_reply()` regex engine if Gemini is unavailable/fails
- Parse JSON with `extract_json_from_gemini()` (existing helper handles markdown fences)

### A3. Batch Processing

**File**: `backend/app/services/intelligence_service.py`

Modify `analyze_project_replies()`:

```python
async def analyze_project_replies(session, project_id, use_ai=True):
    # 1. Get unanalyzed replies (existing query)
    # 2. For each reply, pre-fetch thread_messages for outbound context
    # 3. Process in batches of 10 with asyncio.gather()
    # 4. For each:
    #    - If use_ai and Gemini available: ai_classify_reply()
    #    - Else: classify_reply() (deterministic fallback)
    # 5. Store interests + tags alongside existing fields
    # 6. analyzer_model = "gemini-2.5-pro" or "rules_v1"
```

Batch size 10 (not 20) — Gemini rate limits at ~100 RPM, and each call takes ~2s.

**Cost estimate**: 781 real INXY replies × $0.05 = ~$39 for full re-analysis. Marginal cost for new replies.

### A4. Re-analyze Endpoint

**File**: `backend/app/api/intelligence.py`

`POST /intelligence/analyze/?project_id=X&rebuild=true` already exists. When `rebuild=true`:
1. Delete all existing `ReplyAnalysis` for project
2. Re-classify with AI
3. Return count

Add `use_ai=true` param (default true). If false, uses fast deterministic rules.

### A5. Backend API Enhancements

**File**: `backend/app/api/intelligence.py`

New query params on `GET /intelligence/`:
| Param | Type | Description |
|-------|------|-------------|
| `date_from` | str (ISO date) | Filter `received_at >=` |
| `date_to` | str (ISO date) | Filter `received_at <` |
| `intent` | str (comma-sep) | Individual intent filter (not just group) |
| `tags` | str (comma-sep) | PostgreSQL array overlap: `tags && ARRAY[...]` |
| `interests_search` | str | ILIKE search in interests column |

New response fields on `ReplyAnalysisOut`:
```python
interests: Optional[str] = None
tags: Optional[List[str]] = None
lead_domain: Optional[str] = None
contact_id: Optional[int] = None
```

New summary fields on `SummaryOut`:
```python
by_tag: dict  # Top 30 tags by frequency, sorted desc
```

New endpoint:
```
GET /intelligence/tags/?project_id=X
→ [{"tag": "swift-settlement", "count": 5}, {"tag": "china-suppliers", "count": 3}, ...]
```

**Contact lookup** for domain + contact_id (optimized — batch lookup, not JOIN):
```python
# Main query: ReplyAnalysis + ProcessedReply only (fast indexed FK join)
# After results: batch-lookup contacts by email set (single IN query)
emails = {row.lead_email.lower() for row in rows if row.lead_email}
contact_q = select(Contact.id, Contact.email, Contact.domain).where(
    func.lower(Contact.email).in_(list(emails))
)
# Map results by email.lower() → (contact_id, domain)
```
This replaces the old `outerjoin(Contact, func.lower(...) == func.lower(...))` which
caused full table scans on 194K contacts. The batch IN query is ~50x faster.

---

## Part B: UX Overhaul

### B1. Move Intelligence to Knowledge Sub-Tab

**Current**: Standalone page at `/intelligence`
**Target**: Tab inside Knowledge page at `/knowledge/intelligence`

| File | Change |
|------|--------|
| `IntelligencePage.tsx` → `components/knowledge/IntelligencePanel.tsx` | Convert to panel component, props: `{ projectId, isDark, t }` |
| `KnowledgePage.tsx` | Add `'intelligence'` to TABS array after 'analytics' |
| `App.tsx` | Remove `/intelligence` route, redirect to `/knowledge/intelligence` |
| `Layout.tsx` | Update sidebar link to `/knowledge/intelligence` |

Project context comes from Knowledge page's `currentProject` — no more separate `?project_id=` URL param.

### B2. Period Selector (Date Filter)

Same visual pattern as AnalyticsPanel (`components/knowledge/AnalyticsPanel.tsx`):

```
[7d] [30d] [90d] [All time]  ← pill button group, top-right of panel
```

- Default: **"All time"** (differs from analytics which defaults to 30d — intelligence needs full history)
- Computes `date_from` ISO string, passes to API
- **Carries to CRM links**: appends `&reply_since={dateFrom}` — ContactsPage already supports this param

### B3. Table Column Layout + Sticky Headers + Column Filters

**Current**: Lead | Company | Website | Offer | Intent | W | Interests | Tags | Geo | Date | CRM

**Column headers are STICKY** — they stick to the top when scrolling down the table.
This is critical for 200+ rows — user must always see which column is which.

**Filters are EMBEDDED IN COLUMN HEADERS** (not in a separate filter bar):
- Remove the filter dropdowns (Offer/Intent/Segment) from next to the search input
- Instead, each column header that supports filtering has a clickable dropdown icon
- When clicked, shows a dropdown with checkboxes + search (same MultiSelectFilter component)
- Active filters show a dot/badge on the column header

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Search replies, leads, companies...]                [7d][30d][90d][All]│
├──────────────────────────────────────────────────────────────────────────┤
│ LEAD  │ COMPANY │ WEBSITE │ OFFER▾ │ INTENT▾ │ W │ INTERESTS │ TAGS▾ │ GEO▾ │ DATE │  │  ← STICKY
├───────┼─────────┼─────────┼────────┼─────────┼───┼───────────┼───────┼──────┼──────┼──┤
│ ...   │ ...     │ ...     │ paygate│ pricing │ ●●│ Needs...  │ [tag] │ [cn] │ 5 Mar│ →│
```

**Behaviour**:
- Click column header "OFFER▾" → dropdown shows paygate/payout/otc/general with counts + checkboxes
- Click column header "INTENT▾" → dropdown shows all intents with counts + checkboxes
- Click column header "TAGS▾" → dropdown shows top 30 tags with counts + search + checkboxes
- Click column header "GEO▾" → dropdown shows geo corridors with counts + checkboxes
- Active filter shows blue dot on header: "OFFER●▾"
- Clicking a cell value (e.g., a tag chip) ALSO toggles that filter
- Search input remains at top (not in a column) — it searches across all text fields

| Column | Source | Render | Filterable |
|--------|--------|--------|-----------|
| Lead | ProcessedReply.lead_name | Truncated text | Search only |
| Company | ProcessedReply.lead_company | Truncated text | Search only |
| Website | Contact.domain via batch lookup | Clickable link | No |
| Offer | ReplyAnalysis.offer_responded_to | Coloured chip, clickable | Column dropdown |
| Intent | ReplyAnalysis.intent | Label, clickable | Column dropdown |
| W | ReplyAnalysis.warmth_score | Dot indicators | No |
| Interests | ReplyAnalysis.interests | Truncated (40ch), full in expanded | Search only |
| Tags | ReplyAnalysis.tags[] | Violet chips, clickable | Column dropdown |
| Geo | ReplyAnalysis.geo_tags[] | Emerald chips, clickable | Column dropdown |
| Date | ProcessedReply.received_at | Short date | Period selector |
| CRM | Contact.id | Link icon | No |

### B4. Expanded Row Detail (Updated)

```
┌──────────────────────────────────────────────────────────────────┐
│ Stephane Meng — REasy (reasy.fr)                                 │
│ Campaign: Inxy - PSP  |  Sequence: cold_email  |  Language: en   │
│                                                                   │
│ INTERESTS:                                                        │
│ Crypto→fiat settlement via SWIFT to pay suppliers in China and    │
│ rest of world in USD. Needs third-party beneficiary support,      │
│ not just off-ramp to own REasy accounts. Suppliers don't accept   │
│ crypto — need clean fiat wires.                                   │
│                                                                   │
│ TAGS: [swift-settlement] [crypto-to-fiat]                         │
│       [third-party-beneficiaries] [supplier-payments]             │
│                                                                   │
│ GEO (corridors): [china] — supplier payment destination           │
│                                                                   │
│ REPLY:                                                            │
│ "Hello, I understand that crypto native solutions are more        │
│  efficient but none of the suppliers use crypto, nor are they     │
│  interested in using crypto. Do you offer SWIFT settlement for    │
│  off-ramp? If not I'm sorry but your product won't be a match    │
│  for us."                                                         │
│                                                                   │
│ Status: pending  |  [Open Conversation →]                         │
└──────────────────────────────────────────────────────────────────┘

NOTE: Tags are STRICTLY financial — no "ready-to-meet" or "needs-info".
      Geo is corridors — "china" because he pays SUPPLIERS there, not because he's Chinese.
```

### B5. Column-Embedded Filters (replaces separate filter bar)

**REMOVED**: Separate filter dropdowns next to search (Offer/Intent/Segment/Tags).
**ADDED**: Filters embedded directly in column headers.

Each filterable column header renders as a button with dropdown:

```tsx
// Column header component
function FilterableHeader({ label, options, selected, onToggle, isDark }) {
  // Renders: "OFFER▾" with optional blue dot when filters active
  // On click: opens MultiSelectFilter dropdown below the header
  // Dropdown: search input + scrollable checkbox list with counts
}
```

**Which columns are filterable**:
| Column | Filter source | Dropdown content |
|--------|--------------|-----------------|
| Offer | `summary.by_offer` | paygate, payout, otc, general with counts |
| Intent | `summary.by_intent` | All 21 intents with labels + counts |
| Tags | `summary.by_tag` | Top 30 tags with search + counts |
| Geo | `summary.by_geo` | Corridor countries with counts |

**Non-filterable columns**: Lead, Company, Website, W, Interests, Date, CRM
(Lead/Company/Interests are covered by the global search input)

**Active filter indicators**:
- Blue dot on column header when filter is active
- Active filter chips shown below search bar (with X to remove each)
- "Clear all" button when any filter is active

### B6. Summary Cards (Updated)

```
┌──────────────────────────────────────────────────────────────────┐
│  [Warm 185] [Questions 65] [Soft 75] [Hard 200] [Noise 256]     │  ← intent groups
│  ────────────────────────────────────────                        │
│  Top tags: [swift-settlement 5] [crypto-to-fiat 12]              │  ← FINANCIAL tags only
│            [on-ramp 8] [supplier-payments 3] [no-crypto 45]      │
│  ────────────────────────────────────────                        │
│  Top corridors: [china 8] [cis 6] [uae 4] [india 3]             │  ← GEO = money corridors
└──────────────────────────────────────────────────────────────────┘
```

### B7. "View in CRM" → Direct Conversation

**Problem**: Currently clicking "Open in CRM" goes to ContactsPage → shows empty table → find contact → click → Details tab → click Conversation tab. 4 clicks.

**Solution**: Open ContactDetailModal directly on Conversation tab.

| File | Change |
|------|--------|
| `ContactDetailModal.tsx` | Add `initialTab?: 'details' \| 'conversation' \| 'source'` prop |
| `ContactsPage.tsx` | Read `?tab=conversation` URL param, pass to modal |
| `IntelligencePanel.tsx` | CRM links: `/contacts?contact_id={id}&tab=conversation` |

Per-row link (when `contact_id` available from join):
```
/contacts?contact_id=12345&tab=conversation
```

Fallback (no contact_id):
```
/contacts?project_id=10&search=stephane.meng@reasy.fr
```

Date carry-through: when period filter is active (e.g., 30d), append `&reply_since={dateFrom}`.

### B8. Debug Panel (Collapsible, Bottom)

A collapsible debug panel at the bottom of the Intelligence page for verifying data integrity.

```
┌──────────────────────────────────────────────────────────────────┐
│ ▾ Debug Panel  │  14 campaigns  │  2772 replies  │  ✓ Checksums  │
├──────────────────────────────────────────────────────────────────┤
│ Campaign Name                          │ Channel  │ Replies      │
│────────────────────────────────────────┼──────────┼──────────────│
│ Inxy - PSP — Paygate en               │ 📧 Email │ 342          │
│ Inxy - Russian DMs en                 │ 📧 Email │ 285          │
│ EasyStaff - Russian DM [>500 connects]│ 🔗 LI    │ 149          │
│ ...                                    │          │              │
├──────────────────────────────────────────────────────────────────┤
│ Checksums:                                                       │
│   Summary total: 2772  │  Campaign sum: 2772  │  List loaded: 200│
│   ✓ Summary = Campaign sum (consistent)                          │
│   ℹ List shows page 1 of 200 (not all replies)                   │
└──────────────────────────────────────────────────────────────────┘
```

**Features**:
- Collapsed by default — just shows summary line
- Click to expand full campaign table
- Each campaign shows: name, source (smartlead/getsales), channel (email/linkedin), reply count
- Checksums compare: `summary.total` vs `sum(campaign.reply_count)` vs `items.length`
- Mismatch highlighted in red
- Loads on-demand when opened (separate API call to `/intelligence/campaigns/`)
- Respects date filter (passes same `date_from/date_to`)

**New API endpoint**: `GET /intelligence/campaigns/?project_id=X`
Returns: `{ campaigns: [{campaign_name, source, channel, reply_count}], total_replies, campaign_count }`

### B9. Performance Optimizations

**Backend**:
1. **Removed Contact JOIN** — was doing `func.lower()` on both sides, defeating all indexes, causing full table scan on 194K contacts. Replaced with batch `IN` lookup after main query.
2. **Staggered loading** — summary endpoint (fast) returns before list endpoint (slower)
3. **New campaigns endpoint** — lightweight GROUP BY for debug panel

**Frontend**:
1. **Sticky column headers** — `position: sticky; top: 0` on header row
2. **Debounced search** — 300ms delay before API call (was instant on every keystroke)
3. **Staggered render** — summary cards shown immediately while table data loads
4. **On-demand debug panel** — only fetches campaign data when opened

---

## Implementation Order

| Phase | What | Estimate |
|-------|------|----------|
| 1 | DB migration: +interests, +tags columns | 5 min |
| 2 | AI engine: `ai_classify_reply()` + batch processing | 30 min |
| 3 | Backend API: date/tag/interests params, contact batch lookup, tags endpoint | 20 min |
| 4 | Panel extraction + Knowledge tab + route cleanup | 15 min |
| 5 | UX: period selector, website + interests + tags columns, sticky headers | 25 min |
| 6 | UX: column-embedded filters (replacing separate filter bar) | 25 min |
| 7 | UX: ContactDetailModal initialTab + conversation deep links | 10 min |
| 8a | Backend: `/intelligence/campaigns/` debug endpoint | 10 min |
| 8b | Frontend: debug panel at bottom with campaign breakdown + checksums | 15 min |
| 9 | Update AI prompt: financial-only tags, corridor geo, specific interests | 10 min |
| 8 | Run full AI re-analysis on INXY project | 10 min (781 replies × ~2s) |

---

## Critical Files

| File | Changes |
|------|---------|
| `backend/app/models/reply_analysis.py` | +interests TEXT, +tags TEXT[] |
| `backend/app/services/intelligence_service.py` | +ai_classify_reply(), modify analyze_project_replies() |
| `backend/app/services/gemini_client.py` | Reuse existing gemini_generate() + extract_json_from_gemini() |
| `backend/app/api/intelligence.py` | +date/tag/interests params, contact join, tags endpoint, summary by_tag |
| `frontend/src/components/knowledge/IntelligencePanel.tsx` | New file (moved from IntelligencePage) |
| `frontend/src/pages/KnowledgePage.tsx` | +intelligence tab |
| `frontend/src/api/intelligence.ts` | +interests, +tags, +lead_domain, +contact_id, +date params |
| `frontend/src/components/ContactDetailModal.tsx` | +initialTab prop |
| `frontend/src/pages/ContactsPage.tsx` | +tab URL param → initialTab |
| `frontend/src/App.tsx` | Route redirect: /intelligence → /knowledge/intelligence |
| `frontend/src/components/Layout.tsx` | Sidebar link update |

---

## Verification

### AI Quality
- Run on INXY → Stephane Meng should get:
  - interests: "Crypto→fiat settlement via SWIFT to pay suppliers in China and globally in USD. Needs third-party beneficiary support, not just off-ramp to own accounts."
  - tags: `["swift-settlement", "china-suppliers", "crypto-to-fiat", "third-party-beneficiaries", "payout", "ready-to-meet"]`
- Spot-check 20 random classifications against manual analysis
- Verify bilingual handling (RU + EN replies)

### UX Flow
- `/knowledge/intelligence` loads with project context
- `/intelligence` redirects to `/knowledge/intelligence`
- Period: 30d → data + summary cards update, CRM links include `reply_since`
- Click tag "swift-settlement" in table → tag filter activates, shows all matching leads
- Multi-select: select 2 offers → table filters to those
- "Open Conversation" → ContactsPage opens modal on Conversation tab directly
- Website column shows domains, clickable to open site

### Business Value
- Search "swift-settlement" → find all 5 leads wanting SWIFT → assess product demand
- Search "on-ramp" → find all leads wanting reverse of what INXY pitches → partner opportunity
- Filter tags "ready-to-meet" + offer "payout" → high-priority payout leads to follow up
- Export tag frequency → present to product team as market demand data

---

## Part C: Testing Strategy

Tests run against **production** (http://46.62.210.24) after deploy. Two layers:

### C1. Backend API Tests (Python httpx)

**File**: `tests/test_intelligence_v2.py`

Run directly via `ssh hetzner` against live API.

| Test | What it verifies |
|------|-----------------|
| `test_analyze_with_ai` | `POST /intelligence/analyze/?project_id=48` returns `classified > 0`, `analyzer_model` includes "gemini" |
| `test_interests_populated` | `GET /intelligence/?project_id=48&warmth_min=3` → all items have non-empty `interests` |
| `test_tags_populated` | Same query → all items have non-empty `tags` array |
| `test_stephane_meng_tags` | `GET /intelligence/?project_id=48&search=stephane` → tags contain `"swift-settlement"` and `"china-suppliers"` |
| `test_tag_filter` | `GET /intelligence/?project_id=48&tags=swift-settlement` → returns only matching leads |
| `test_interests_search` | `GET /intelligence/?project_id=48&interests_search=SWIFT` → finds Stephane |
| `test_date_filter` | `GET /intelligence/?project_id=48&date_from=2025-11-01&date_to=2025-12-01` → filters by received_at |
| `test_summary_has_tags` | `GET /intelligence/summary/?project_id=48` → response has `by_tag` dict with counts |
| `test_tags_endpoint` | `GET /intelligence/tags/?project_id=48` → returns array of `{tag, count}`, sorted by count desc |
| `test_contact_join` | `GET /intelligence/?project_id=48` → items have `lead_domain` and `contact_id` |
| `test_date_carries_to_summary` | Summary with date_from returns different counts than all-time |

### C2. Playwright E2E Tests (UI)

**File**: `frontend/e2e/intelligence-v2.spec.ts`

Tests run against production after deploy. Use existing auth pattern from `intelligence.spec.ts`.

#### Test Cases

**TC1: Knowledge tab navigation**
```
1. Go to /knowledge/intelligence
2. Assert Intelligence tab is active
3. Assert project name visible in Knowledge header
4. Assert data loads (summary cards show counts > 0)
5. Screenshot: screenshot_intel_v2_knowledge_tab.png
```

**TC2: Period selector**
```
1. Load /knowledge/intelligence
2. Assert "All time" is active by default
3. Click "30d" → wait for API response
4. Assert summary card counts changed (likely fewer)
5. Click "All time" → counts restore
6. Screenshot both states
```

**TC3: Interests column visible**
```
1. Load page with data
2. Assert column header "Interests" exists
3. Find a Warm row → assert interests text is non-empty
4. Click row to expand → assert full interests text visible in detail panel
5. Screenshot expanded row
```

**TC4: Tags column + click-to-filter**
```
1. Load page with data
2. Find a row with tags → assert tag chips rendered
3. Click a tag chip (e.g., "swift-settlement")
4. Assert tag filter activates (visible in filter bar)
5. Assert table shows only rows with that tag
6. Clear filters → table shows all rows again
7. Screenshot filtered state
```

**TC5: Multi-select filter — Offer**
```
1. Click "Offer" filter dropdown
2. Assert dropdown opens with search input + checkbox list
3. Select "paygate" checkbox
4. Assert table filters to paygate rows
5. Select "payout" checkbox too
6. Assert table shows paygate + payout
7. Close dropdown, clear filters
```

**TC6: Multi-select filter — Tags**
```
1. Click "Tags" filter dropdown
2. Type "swift" in search input
3. Assert filtered list shows "swift-settlement"
4. Check it → table filters
5. Screenshot
```

**TC7: Website column**
```
1. Find a row with lead_domain
2. Assert domain is rendered as clickable link
3. Assert link href starts with "https://"
```

**TC8: "Open Conversation" deep link**
```
1. Expand a Warm row (e.g., Stephane Meng)
2. Find "Open Conversation" link
3. Assert href contains "contact_id=" and "tab=conversation"
4. Click link (opens new tab)
5. On new tab: assert ContactDetailModal opens
6. Assert "Conversation" tab is active (not "Details")
7. Assert conversation messages are visible
8. Screenshot: screenshot_intel_v2_conversation.png
```

**TC9: Group "View in CRM" with date carry**
```
1. Set period to "30d"
2. Find group header "Warm Replies" → click "View in CRM"
3. Assert link href contains "reply_since="
4. Navigate to link in new tab
5. Assert CRM loads with date filter applied
6. Screenshot
```

**TC10: Stephane Meng specific (golden test)**
```
1. Load page, search "stephane" or "reasy"
2. Assert Stephane Meng row appears
3. Assert interests contain "SWIFT" or "settlement"
4. Assert tags include "swift-settlement"
5. Expand row → verify full interests text mentions China suppliers
6. Click "Open Conversation" → verify conversation loads
7. Screenshot: screenshot_intel_v2_stephane.png
```

**TC11: Old URL redirect**
```
1. Navigate to /intelligence
2. Assert redirected to /knowledge/intelligence
3. Assert page loads correctly
```

### C3. AI-Powered Quality Verification (Opus Self-Test)

After AI analysis runs on all 781 INXY replies, Opus verifies quality by:

1. **Fetch 20 random classified replies** via API with `page_size=20`
2. **For each reply**, read the raw reply_text and AI-assigned interests+tags
3. **Assess**: Does the interests summary accurately capture the lead's needs? Are tags relevant and not hallucinated?
4. **Flag misclassifications**: any warmth=5 that's actually noise, any "general" offer that's clearly payout
5. **Check tag consistency**: same concept should use same tag across replies (e.g., not "swift-settlement" and "swift-payout" for the same concept)
6. **Iterate**: If accuracy < 90%, adjust the Gemini prompt and re-analyze the failures

**Specific golden examples to verify**:

| Lead | Expected interests | Expected tags | Expected geo_tags |
|------|-------------------|---------------|-------------------|
| Stephane Meng (REasy) | Crypto→fiat settlement via SWIFT to pay suppliers in China/globally in USD. Needs third-party beneficiary support, not off-ramp to own accounts. Suppliers don't accept crypto. | `swift-settlement, crypto-to-fiat, third-party-beneficiaries, supplier-payments` | `china` |
| A "не работаем с криптой" reply | Company policy prohibits cryptocurrency. Uses traditional banking for payments. | `no-crypto` | `[]` |
| A "созвонимся в среду" reply | Interested in paygate for accepting crypto payments from customers. Wants EUR settlement on bank account. | `paygate, crypto-to-fiat` | (depends on corridor) |
| A "пришлите предложение" reply | Evaluating crypto payment gateway options. Needs pricing for paygate integration with e-commerce platform. | `payment-gateway, api-integration` | (depends on corridor) |
| An "обратная задача — нам надо покупать крипту" reply | Needs on-ramp (fiat→crypto) — reverse of INXY's core offering. Wants to purchase crypto with fiat for treasury/operations. | `on-ramp, fiat-to-crypto, treasury-management` | (depends on corridor) |
| A "выплаты подрядчикам за рубежом" reply | Needs mass crypto payouts to foreign contractors. Currently using SWIFT but looking for faster/cheaper alternative. | `contractor-payouts, mass-disbursements, swift-settlement` | (depends on where contractors are — e.g., `cis, turkey, india`) |

**ANTI-PATTERNS to catch**:
| Bad interests | Why bad | Should be |
|---------------|---------|-----------|
| "Wants to schedule a call" | That's intent, not financial need | "Interested in paygate for EUR settlement" |
| "Needs more information" | Generic, no financial specifics | "Evaluating off-ramp for USDT→EUR conversion" |
| "Referred to colleague" | That's intent | "Company needs mass payouts to CIS contractors" |
| "Ready to meet" | That's intent | "Looking for OTC crypto↔fiat for treasury above $100K" |

**ANTI-PATTERNS for geo_tags**:
| Bad geo_tags | Why bad | Should be |
|--------------|---------|-----------|
| `["france"]` for Stephane | That's where HE is, not the money corridor | `["china"]` — where his SUPPLIERS are |
| `["uk"]` for a London-based lead | Lead location, not payment corridor | `[]` unless they mention paying someone in UK |
| `["russia"]` just because reply is in Russian | Language ≠ corridor | Only if they mention RU as payment destination |

### C4. Iterative Improvement Loop

```
1. Deploy backend + frontend changes
2. Run AI analysis: POST /intelligence/analyze/?project_id=48&rebuild=true
3. Run backend API tests (C1) → fix any failures
4. Run Playwright E2E tests (C2) → fix any UI issues
5. Run Opus quality check (C3) → if accuracy < 90%:
   a. Identify failure patterns (e.g., tags too generic, interests too vague)
   b. Adjust Gemini prompt (add examples, tighten tag taxonomy)
   c. Re-analyze failed replies only
   d. Re-check quality
6. Repeat steps 3-5 until all tests pass and quality ≥ 90%
7. Take final screenshots for visual verification
```

### C5. Test Commands

```bash
# Backend API tests
ssh hetzner "cd ~/magnum-opus-project/repo && python -m pytest tests/test_intelligence_v2.py -v"

# Playwright E2E (from local, against production)
cd frontend && PW_BASE_URL=http://46.62.210.24 npx playwright test e2e/intelligence-v2.spec.ts --headed

# AI quality check (from local, via API)
python scripts/verify_intelligence_quality.py --project-id 48 --sample-size 20
```
