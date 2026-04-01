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

## All Bugs Found & Fixed (4 verification passes)

### Pass 1
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | Critical | Exhaustion pages ate global page cap | Only productive pages count |
| 2 | High | Regeneration counter carried across strategies | Reset per strategy |

### Pass 2
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 3 | High | Regeneration repeated previously tried keywords | `all_tried_keywords` set tracks globally |
| 4 | Medium | `UserServiceContext` got string user_id | `int()` with fallback |
| 5 | Medium | No keyword count warning in preview | Warning if <20 keywords |
| 6 | Medium | Strategy message truncated to 5 keywords | Show all keywords |

### Pass 3
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 7 | High | Industry tags stayed after regen (AND narrowed) | Pop industry_tag_ids after regen |
| 8 | Low | Progress not persisted after regen | Added persist before continue |

### Pass 4
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 9 | Medium | GPT regen prompt only showed first 50 exhausted keywords — could repeat 51+ | Increased to 100 + max_tokens to 1000 |

## Verified Correct (Pass 4)
- Parallel page fetching (10/batch): consecutive_empty correctly accumulates across batches
- backlog_industry strategy after regen: correctly transforms to keyword-only (sets keywords, drops industry tags)
- Apollo API down: failed pages count as empty → triggers regen → GPT generates keywords → retries Apollo → 5 regen limit → stops
- Duplicate keywords from GPT filtered by `k.lower() not in all_tried` post-generation

## Verification Checklist
- [x] filter_mapper GPT prompt asks for 20-30 keywords
- [x] Unverified keywords added to reach 20 minimum
- [x] EXHAUSTION_THRESHOLD = 20
- [x] keyword_regenerations resets per strategy
- [x] Exhaustion pages don't count toward MAX_PHASE2_PAGES
- [x] all_tried_keywords tracks everything across all regenerations
- [x] GPT regeneration prompt shows up to 100 previously tried keywords
- [x] UserServiceContext gets int user_id
- [x] Strategy message shows all keywords
- [x] Warning if <20 keywords
- [x] Industry tags dropped after regeneration
- [x] Progress persisted after regeneration
- [x] Parallel batch fetching doesn't break consecutive_empty counting
- [x] backlog_industry strategy works correctly after regen

## Worst Case Apollo Credits
- Per strategy: 5 regenerations x 20 empty pages = 100 wasted pages
- Two strategies = 200 wasted pages max
- Plus MAX_PHASE2_PAGES = 200 productive pages
- **Absolute worst: ~400 pages = ~400 credits ($4.00)**
