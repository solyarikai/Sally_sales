# Pipeline Exhaustion Verification Plan

## Requirements
1. At least 20 keywords generated before pipeline starts
2. Keywords regenerated when 20 consecutive pages yield 0 new companies
3. Pipeline stops after 5 regeneration attempts with 20 empty pages each
4. Each strategy gets its own regeneration budget

## Constants
- `EXHAUSTION_THRESHOLD = 20` — consecutive empty pages before regeneration
- `MAX_KEYWORD_REGENERATIONS = 5` — max regeneration attempts per strategy
- `MAX_PHASE2_PAGES = 200` — global safety cap (productive pages only)

## Bugs Found & Fixed

### BUG 1 (CRITICAL): total_pages_all blocks regeneration
- Exhaustion pages counted toward MAX_PHASE2_PAGES, causing premature stop
- **Fix**: Only productive pages (new_count > 0) count toward global cap

### BUG 2 (HIGH): keyword_regenerations not reset between strategies
- Primary exhausting all 5 regenerations blocked backlog from trying
- **Fix**: Reset counter per strategy loop iteration

### BUG 3 (HIGH): Regeneration repeats previously tried keywords
- Each regeneration only knew about the CURRENT strategy's old keywords
- Regeneration 3 could repeat keywords from regeneration 1
- **Fix**: Track ALL tried keywords in `all_tried_keywords` set across all strategies/regenerations. GPT prompt shows full exhausted list.

### BUG 4 (MEDIUM): UserServiceContext got string user_id instead of int
- `triggered_by.split(":")[-1]` returns "177" (string), UserServiceContext expects int
- **Fix**: `int(user_id_str)` with ValueError fallback to 0

### GAP 5: No keyword count warning in preview
- Pipeline could start with <20 keywords without user knowing
- **Fix**: Warning appended to strategy message: "⚠️ Only N keywords (recommended: 20+)"

### GAP 6: Strategy message showed only first 5 keywords
- **Fix**: Show all keywords in preview

## Verification Checklist
- [x] filter_mapper GPT prompt asks for 20-30 keywords
- [x] Unverified keywords added to reach 20 minimum
- [x] EXHAUSTION_THRESHOLD = 20
- [x] keyword_regenerations resets per strategy
- [x] Exhaustion pages don't count toward MAX_PHASE2_PAGES
- [x] all_tried_keywords tracks everything across all regenerations
- [x] GPT regeneration prompt shows ALL previously tried keywords
- [x] UserServiceContext gets int user_id
- [x] Strategy message shows all keywords
- [x] Warning if <20 keywords

## Worst Case Apollo Credits
- Per strategy: 5 regenerations × 20 empty pages = 100 wasted pages
- Two strategies (primary + backlog) = 200 wasted pages
- Plus MAX_PHASE2_PAGES = 200 productive pages
- **Absolute worst: ~400 pages = ~400 credits ($4.00)**
