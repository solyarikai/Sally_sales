# Pipeline Page UI Redesign — Complete Feedback

## Source: User voice feedback + screenshots, Apr 1, 2026

---

### 1. Column Show/Hide — Match CRM Style
**Current**: Inline pill buttons that toggle columns on/off (takes full row, ugly)
**Wanted**: CRM-style vertical dropdown with checkboxes (Image #25)
- Small "Columns" icon in toolbar (same as CRM: `⊞ Columns`)
- Click → dropdown with vertical list of column names
- Each row has checkbox (blue = visible, empty = hidden)
- No text buttons, no pill toggles
- Reuse the SAME component from CRM page — don't build new UI

### 2. Remove Industry + Keywords Columns
**Problem**: Most companies have empty Industry/Keywords (from Apollo, very sparse data)
- Industry column: mostly `—` dashes, occasional "Wholesale", "Retail"
- Keywords column: almost entirely empty
- These columns waste horizontal space for near-zero information
**Fix**: Remove Industry + Keywords from optional columns entirely
**Keep**: Domain, Name, Status, Segment, Size, Country, City, Scraped, Analysis, People

### 3. Remove the Phase Stepper
**Current**: Visual dots: Collect → Check → Scrape → Analyze → Done
**Problem**: Pipeline is now fully parallel per company — scraping, classification, people extraction happen independently and concurrently. Global "phases" are meaningless.
**Fix**: Replace stepper with a simple stats line:
- Elapsed time (REAL-TIME ticking counter — seconds incrementing live)
- Companies found / targets / people
- Credits spent
- The timer must tick every second while user watches the page — no waiting for 15s poll

### 4. Table Jittering on Scroll/Load More
**Problem**: When scrolling down and clicking "Load more", the table layout shifts — columns resize, content jumps, the whole table "дрожит" (shakes/trembles)
**Cause**: Likely `table-layout: auto` recalculating column widths when new rows with different content lengths appear
**Fix**:
- Use `table-layout: fixed` always (not just after resize)
- Set explicit column widths on first render
- "Load more" should not cause re-layout — append rows to existing stable table

### 5. Consolidate Toolbar — Too Many Buttons
**Current toolbar** (Image #26): Iteration dropdown | Stepper | Prompts | Credits | People CRM link | Campaign | Columns | Company Filters | People Filters | User-MCP Conversation | Export CSV
**Problem**: 11 items in the toolbar — overwhelming, cluttered, not minimalist
**Redesign**:
- **Left side**: Iteration dropdown (keep), Live stats (timer + counts)
- **Right side**: Small icon buttons only (no text labels):
  - 🔍 Filters icon → opens modal with 2 tabs: Company Filters | People Filters
  - ⊞ Columns icon → dropdown with checkboxes (CRM-style)
  - 📄 Export CSV icon
  - 📝 Prompts link (or make it a modal too)
- **Remove entirely**:
  - "User-MCP Conversation" button — empty, useless
  - Stepper dots
  - Credits badge (move to stats line)
  - Separate "Company Filters" and "People Filters" buttons (merged into one Filters modal)

### 6. Filters Modal — Two Tabs
**Current**: Two separate expandable panels (Company Filters, People Filters) with inline JSON
**Wanted**: Single "Filters" icon button → modal with two tabs
- Tab 1: Company Filters (Apollo keywords, industries, locations, sizes)
- Tab 2: People Filters (roles, seniority, max per company)
- Show the filters in human-readable form, not raw JSON
- Advanced users can see the raw Apollo parameters
- For casual users: just show "Fashion brands in Italy, 1-200 employees"

### 7. Prompts Page Empty
**Current** (Image #27): "No prompts used yet. Run the analyze phase to see GPT prompts."
**Problem**: Analysis DID run (companies are classified as target/rejected with reasoning), but prompts page shows nothing
**Cause**: Streaming pipeline doesn't log prompts to the same table that the prompts page reads from
**Fix**: Streaming pipeline must write the classification prompt (via_negativa_system) to the prompts/processing_steps table so the UI can display it

### 8. Segment Labels Too Granular
**Current** (Image #29): FASHION, FASHION_BRANDS, FASHION_BRANDS_AND_RETAILERS, FASHION_BRANDS_RETAILERS, FASHION_RETAIL, FASHION_RETAILERS, OPTICAL_RETAIL
**Problem**: 7 different segment labels for one query ("fashion brands in Italy") — confusing, messy in UI
**Root cause**: Classification prompt tells GPT to create sub-segments like `{target_segment_label}_AGENCY` — GPT goes wild with variations
**Fix**:
- Classification prompt must produce ONE segment label that matches the user's query
- "fashion brands in Italy" → ALL targets get `FASHION_BRANDS`, period
- Remove the instruction about sub-segments from the via_negativa prompt
- The segment should be explainable to a child in natural language

### 9. MCP Chat — Simple Terms
**Current**: MCP shows technical details in chat: "INDUSTRY FIRST strategy", "organization_industry_tag_ids", filter hashes
**Wanted**: MCP should speak in simple terms in the chat
- "I'll search for fashion brands in Italy with 1-200 employees"
- NOT: "INDUSTRY (specific match — high target rate)"
- The strategy/filter details should be in the UI (Filters modal) for advanced users
- Chat should be conversational, not technical

### 10. People Column → CRM Link Not Working
**Current** (Image #26): People column shows count (e.g., "3") with link to CRM
**Problem**: Clicking takes to `/crm?pipeline=445` but CRM page doesn't show pipeline-specific columns (segment, analysis reasoning)
**Fix**: CRM page should accept `pipeline=` param and show relevant columns

### 11. Filter by Companies with People
**Current**: No way to filter pipeline table to show only companies that have people > 0
**Wanted**: Dropdown or toggle: "Has people" / "All" — so user can focus on companies with contacts gathered
**Also**: Status dropdown should allow filtering by "target" only (hide gathered, rejected)

### 12. Scraped Column — Mostly Empty
**Current** (Image #26): "Scraped" column shows `—` for most companies
**Problem**: If companies are scraped, the preview should show. If not scraped yet, show a spinner or "pending"
**Fix**: Ensure scraped_text_preview is populated during streaming pipeline, not just batch pipeline

### 13. Minimalist Philosophy
**Principle**: Hide everything by default. Show complexity only to those who seek it.
- Like Telegram: millions of features, clean surface
- Like Apple: depth underneath simplicity
- Pipeline page default: table + stats line + small icons
- Advanced: modals for filters, columns, prompts
- No inline expandable panels cluttering the page

### 14. Pipeline Runs List (Image #29)
**Current**: Shows segment badges with 7 different labels for one run
**Fix**: Show ONE segment label per run (the primary one)
**Also**: Should show elapsed time, not just date

---

## Implementation Priority

### P0 — Critical UX (do first)
1. Column dropdown (CRM-style checkboxes, replace pill buttons)
2. Remove stepper, add live timer + stats line
3. Consolidate toolbar to icon buttons
4. Remove Industry + Keywords columns

### P1 — Important
5. Filters modal (2 tabs, replace inline panels)
6. Fix table jittering (table-layout: fixed)
7. Fix segment label granularity (one label per query)
8. Remove "User-MCP Conversation"

### P2 — Nice to have
9. Fix prompts page (log prompts from streaming pipeline)
10. Add "has people" filter
11. Fix People → CRM link
12. Fix Scraped column data
13. Simplify MCP chat language
14. Clean up pipeline runs list segments
