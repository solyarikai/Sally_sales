# Pipeline Page UI Redesign — Complete Feedback

## Source: User voice feedback + screenshots, Apr 1, 2026

---

### 1. Column Show/Hide — Match CRM Style ✅ DONE
- CRM-style vertical dropdown with checkboxes
- Small ⊞ icon in toolbar → dropdown
- Reuse same component pattern as CRM

### 2. Remove Industry + Keywords Columns ✅ DONE
- Removed from optional columns

### 3. Remove the Phase Stepper ✅ DONE
- Replaced with live stats line (timer ticks every second)

### 4. Table Jittering on Scroll/Load More ✅ DONE
- `table-layout: fixed` always, minWidth 900

### 5. Consolidate Toolbar ✅ DONE
- Icon buttons: 📝 ⚙ ⊞ ↓
- Removed User-MCP Conversation, stepper, inline pill buttons

### 6. Filters Modal ✅ DONE
- Single ⚙ button → modal with Company/People tabs

### 7. Prompts Page Empty
- Streaming pipeline doesn't log prompts
- **TODO**: Write via_negativa_system prompt to processing_steps during streaming pipeline

### 8. Segment Labels Too Granular
- 7 labels for one query (FASHION, FASHION_BRANDS, FASHION_RETAIL, etc.)
- **TODO**: Classification prompt must produce ONE segment matching user's query

### 9. MCP Chat — Simple Terms
- **TODO**: Simplify strategy message in MCP chat

### 10. People Column → CRM Link Not Working
- **TODO**: CRM page should handle `?pipeline=` param

### 11. Filter by Companies with People
- **TODO**: Add "has people" filter toggle

### 12. Scraped Column — Mostly Empty
- **TODO**: Ensure scraped_text_preview populated in streaming pipeline

### 13. Minimalist Philosophy ✅ DONE
- Clean surface, depth in modals

### 14. Pipeline Runs List Segments
- **TODO**: Show ONE segment per run, not 7 badges

---

## Feedback Round 2 (Apr 1, 2026 — Images #34-#37)

### 15. Company Count Jumping on Lazy Load
**Problem**: Shows "50 companies" → scroll down → load more → scroll back → "100 companies" → back to "50"
**Root cause**: Stats line shows `filtered.length` which changes as pages load
**Fix**: Show only `totalCompanies` (total from API), not the currently-loaded filtered count

### 16. "114 people" Duplicated
**Problem**: "114 people" appears TWICE — once in stats line (left) and once as green button (right: "114 people →")
**Fix**: Remove the green button. Make "114 people" in the stats line a clickable link to CRM. One instance only.

### 17. Iteration Starts at 0
**Problem**: "Iteration 0" shown in KPI banner — confusing, should start at 1
**Fix**: Display `iteration + 1` or start counter at 1 in backend

### 18. KPI Progress Banner — Make Collapsible
**Problem**: KPI banner with progress bars takes vertical space even after pipeline completes
**Fix**: Make it collapsible/expandable. Collapsed by default when pipeline is completed. Show minimal summary when collapsed.

### 19. ⚙ Icon is Settings, Not Filters
**Problem**: Gear icon (⚙) suggests "settings", not "filters". Filters icon should be a funnel.
**Fix**: Change ⚙ to 🔍 or ≡ (filter lines) or use actual funnel character. Or keep ⚙ but relabel as "Settings" since it shows search strategy config.

### 20. Company Filters Modal — Missing Strategy Reasoning
**Problem**: Company Filters tab (Image #36) shows keywords and industries but NO reasoning about WHY this strategy was chosen
**Fix**: Add the reasoning text from `_build_strategy_message` — explain why industry_first vs keywords_first

### 21. People Filters Tab — Empty
**Problem**: People Filters tab (Image #37) shows "People filters not set. Will use defaults from offer analysis."
**Root cause**: `run.people_filters` is null even though people were extracted (114 people found)
**Fix**: People filters should be populated from offer analysis defaults (roles, seniority). If not stored on run, read from project's offer_summary.target_roles

### 22. 96 Credits Duplicated
**Problem**: "96 credits" shown in BOTH stats line AND KPI banner
**Fix**: Show credits only in stats line. KPI banner should show progress bars only.

### 23. People Count Mismatch — 114 vs 86
**Problem**: Stats line says "114 people" but KPI progress bar says "86/100 (86%)"
**Root cause**: `totalContacts` (from API response, counts all extracted contacts) ≠ `run.total_people_found` (from KPI progress tracking). They use different queries.
**Fix**: Use ONE source of truth. `total_people_found` on the run should match the actual contact count. Or at minimum, display the same number in both places.

### 24. Reuse Same Table Components as CRM
**Problem**: Pipeline table is custom HTML table. CRM uses AG Grid or similar.
**Wanted**: Same table component, same interaction patterns (column resize, sort, filter dropdowns)
**Note**: Not necessarily AG Grid — just consistent behavior between pages

---

## Status (verified with real browser screenshots Apr 2, 2026)

### DONE ✅ (verified in browser)
1. Column dropdown (CRM-style checkboxes) ✅
2. Remove Industry/Keywords columns ✅
3. Remove stepper + live timer ✅
4. Consolidate toolbar to icons ✅
5. Filters modal (Company/People tabs) ✅
6. table-layout:fixed ✅
7. Prompts page — logs classification prompt from streaming pipeline ✅
8. Segment labels — targets ONE label, rejected get real segment ✅
9. MCP chat simple terms ✅
13. Minimalist philosophy ✅
14. Pipeline runs list — ONE segment badge ✅
15. Company count stable (totalCompanies) ✅
16. People — one link, no duplicate button ✅
17. Iteration 1-based ✅
18. KPI banner collapsible ✅
19. Filter icon ≡ (not ⚙) ✅
20. Strategy reasoning in filters modal ✅
21. People filters fallback from offer_summary ✅
22. Credits not duplicated ✅
23. People count priority fixed (live DB first) ✅

### DONE (Apr 2, round 2)
11. "Has people" filter — People column dropdown with "has_people" option ✅
12. Scraped column — falls back to DiscoveredCompany.scraped_text when CompanyScrape empty ✅

### REMAINING GAPS (architectural)
10. CRM ?pipeline= param — MCP pipeline contacts (ExtractedContact in MCP DB) are separate from main app contacts (Contact in main DB). CRM page talks to main backend API which has no access to MCP pipeline data. Fix requires either: (a) sync MCP contacts to main DB, or (b) build MCP-native CRM page.
24. Table components — CRM uses AG Grid (main app), Pipeline uses HTML table (MCP). Unifying requires AG Grid migration = major refactor.
