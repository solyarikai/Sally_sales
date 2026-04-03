# Intelligence V2 — Testing & Verification Guide

## Production Access

- **URL**: http://46.62.210.24
- **Username**: ilovesally
- **Password**: BdaP31NNXX4ZCyvU
- **Session cookie**: b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46
- **Test project**: INXY (id=48, 2742 analyzed replies)

## Running E2E Tests

```bash
cd frontend
npx playwright test e2e/intelligence-v2.spec.ts --reporter=list
```

All 13 tests pass against production (http://46.62.210.24).

### Test Infrastructure Notes

- Use `domcontentloaded` NOT `networkidle` — background polling never stops
- Knowledge page mounts ALL panels simultaneously — use unique text selectors (e.g. "Warm Replies", "Soft Objections") not generic ones (e.g. "Questions", "30d") that may match hidden Analytics/Chat panels
- Auth requires both HTTP credentials (nginx) AND session cookie AND localStorage state injection

---

## Use Cases & Test Matrix

### UC1: Route Redirect
- **Action**: Navigate to `/intelligence`
- **Expected**: Redirects to `/knowledge/intelligence`
- **Test**: #1 — verifies URL contains `/knowledge/intelligence`

### UC2: Intelligence Tab in Knowledge
- **Action**: Navigate to `/knowledge/intelligence?project=inxy`
- **Expected**: Intelligence tab highlighted in Knowledge tab bar, "Reply Intelligence" header visible, "Analyze (AI)" button present
- **Test**: #2

### UC3: Summary Cards
- **Action**: Page loads with analyzed data
- **Expected**: 5 intent group cards (Warm Replies, Questions, Soft Objections, Hard Objections, Noise) with counts
- **Test**: #3
- **Current**: Warm=127, Questions=36, Soft=38, Hard=199, Noise=2342

### UC4: Period Selector
- **Action**: Click 7d / 30d / 90d / All time buttons
- **Expected**: Data reloads filtered by date, counts update, "Clear" appears
- **Test**: #4
- **Note**: `date_from` ISO string passed to both `/intelligence/` and `/intelligence/summary/`

### UC5: Intent Group Filter
- **Action**: Click summary card (e.g. "Warm Replies")
- **Expected**: Table filtered to only warm intent rows, card highlighted with ring
- **Test**: #5

### UC6: Multi-Select Filters (Offer, Intent, Segment, Tags, Geo)
- **Action**: Click "Offer" dropdown → select "paygate" checkbox
- **Expected**: Dropdown shows all options with counts, selected gets blue checkbox, data filtered
- **Test**: #6
- **Dropdowns**: Offer | Intent | Segment | Tags | Geo (Tags/Geo only appear when data has tags)

### UC7: Search Filter
- **Action**: Type "crypto" in search box, press Enter
- **Expected**: Data filtered by text match in reply, lead name, company
- **Test**: #7

### UC8: Table Columns
- **Expected columns**: LEAD | COMPANY | WEBSITE | OFFER | INTENT | W | INTERESTS | DATE | CRM
- **Website**: Clickable domain from Contact table (left join)
- **Interests**: AI-extracted summary (truncated in row, full in expanded)
- **W**: Warmth dots (1-5, color-coded)
- **CRM**: External link icon to contact page
- **Test**: #8

### UC9: Expanded Row Detail
- **Action**: Click a table row
- **Expected**: Expanded section shows:
  - Full reply text
  - AI interests summary (full text)
  - Tags as clickable violet chips
  - Geo tags as clickable emerald chips
  - Campaign name
  - Segment
  - Approval status
  - Model (Rules vs Gemini AI)
  - "Open in CRM" deep link
- **Test**: #9

### UC10: CRM Deep Links
- **Action**: Click "Open in CRM" in expanded row
- **Expected**: Opens `/contacts/{id}?tab=conversation` (direct to conversation tab)
- **Fallback**: If no contact_id, opens `/contacts?project_id=48&search={email}`
- **Test**: #10

### UC11: Group Collapse/Expand
- **Default**: Noise group collapsed, all others expanded
- **Action**: Click group header → toggles collapse
- **Test**: #11

### UC12: Group "View in CRM" Link
- **Action**: Click "View in CRM" next to group header
- **Expected**: Opens `/contacts?project_id=48&replied=true&reply_category={categories}`
- **Test**: #12

### UC13: Full Page Scrolling
- **Action**: Scroll table area
- **Expected**: Headers remain visible, data scrolls
- **Test**: #13

---

## AI Analysis Verification (Opus Self-Check)

### How to Run AI Analysis

```bash
# Trigger AI analysis for INXY project
curl -X POST "http://localhost:8000/api/intelligence/analyze/?project_id=48&rebuild=true&use_ai=true" \
  -H "X-Company-ID: 1"
```

### Golden Test Cases

| Lead | Expected Intent | Expected Interests | Expected Tags | Expected Geo |
|------|----------------|-------------------|---------------|-------------|
| Stephane Meng (REasy) | specific_use_case or pricing | Crypto→fiat SWIFT settlement for China suppliers | swift-settlement, crypto-to-fiat, third-party-beneficiaries, payout | china |
| "не работаем с криптой" | no_crypto | Company doesn't use crypto | no-crypto | (none) |
| "созвонимся в среду" | schedule_call | Ready to meet, discuss [offer] | ready-to-meet | (none) |
| "пришлите предложение" | send_info | Wants pricing/details | needs-info | (none) |
| "обратная задача — покупать крипту" | adjacent_demand | Needs on-ramp (fiat→crypto) | on-ramp, adjacent-demand | (none) |

### Verification Process

1. Run `rebuild=true` AI analysis
2. Check summary: tags should appear in `by_tag`, geos in `by_geo`
3. Spot-check 20 random warm replies: interests should be concrete, not generic
4. Search tags: "swift-settlement" should find leads wanting SWIFT
5. Filter geo: "china" should find leads mentioning China operations

---

## Architecture

### Backend

| File | Purpose |
|------|---------|
| `backend/app/models/reply_analysis.py` | Model: +interests, +tags, +geo_tags columns |
| `backend/app/services/intelligence_service.py` | AI classification via Gemini 2.5 Pro, batch processing |
| `backend/app/api/intelligence.py` | API: date/tag/geo filters, Contact join, /tags endpoint |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/components/knowledge/IntelligencePanel.tsx` | Main panel (moved from IntelligencePage) |
| `frontend/src/pages/KnowledgePage.tsx` | Added 'intelligence' tab |
| `frontend/src/api/intelligence.ts` | API types + methods |
| `frontend/src/App.tsx` | Route redirect |
| `frontend/src/components/Layout.tsx` | Sidebar nav link |
| `frontend/src/components/ContactDetailModal.tsx` | +initialTab prop |

### Database

New columns on `reply_analysis`:
- `interests` TEXT — AI-extracted summary
- `tags` TEXT[] — Searchable tags (GIN indexed)
- `geo_tags` TEXT[] — Geography tags (GIN indexed)
