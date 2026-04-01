# Pipeline Exhaustion Verification Plan

## Requirements
1. At least 20 keywords generated before pipeline starts
2. Keywords regenerated when 20 consecutive pages yield 0 new companies
3. Pipeline stops after 5 regeneration attempts with 20 empty pages each
4. Each strategy gets its own regeneration budget

## Constants
- `EXHAUSTION_THRESHOLD = 20` — consecutive empty pages before regeneration
- `MAX_KEYWORD_REGENERATIONS = 5` — max regeneration attempts per strategy
- `MAX_PHASE2_PAGES = 200` — global safety cap (not counting exhaustion pages)

## Bugs Found & Fixed

### BUG 1 (CRITICAL): total_pages_all blocks regeneration
- `total_pages_all` never reset after regeneration, hits MAX_PHASE2_PAGES early
- **Fix**: Only count productive pages toward global cap. Exhaustion pages don't count.

### BUG 2 (HIGH): keyword_regenerations not reset between strategies
- If primary exhausts all 5 regenerations, backlog never tries
- **Fix**: Reset counter per strategy

### GAP 3: No minimum keyword count validation
- **Fix**: Warn in preview if <20 keywords

### GAP 4: Strategy message shows only first 5 keywords
- **Fix**: Show all keywords

## Verification
1. filter_mapper GPT prompt asks for 20-30 keywords
2. Unverified keywords added to reach 20 minimum
3. EXHAUSTION_THRESHOLD = 20 (not 2)
4. keyword_regenerations resets per strategy
5. Exhaustion pages don't count toward MAX_PHASE2_PAGES
6. Strategy message shows all keywords
7. Pipeline stops after 5 regenerations x 20 empty pages = 100 wasted pages max per strategy
