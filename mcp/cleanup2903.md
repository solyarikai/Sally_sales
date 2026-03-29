# MCP Directory Cleanup Plan — 2026-03-29

**Goal:** Remove only true junk and proven duplicates. Keep everything with value.
**Philosophy:** Better to have a doc than not. Only remove what's genuinely worthless.
**Rule:** PLAN ONLY. Do NOT execute. Review before acting.
**Safety:** Move to `mcp/.archive/` first (not delete). Hard-delete after 1 week if no issues.

---

## Current State: 38 files + 11 dirs at mcp/ root

### Why each file/dir is essential

The MCP has **four layers** of essential files:

1. **Runtime** — docker-compose mounts/builds: `backend/`, `frontend/`, `telegram/`, `docker-compose.mcp.yml`, `.env`
2. **Scheduled agent system** — `cron_build/scheduled_task_v1.md` drives autonomous cron agents. It references: `requirements_source.md`, `suck.md`, `answers2603.md`, `testruns2603.md`, `implementation_plan.md`, `audit29_03.md`, `test_ground_truth/`
3. **Testing** — `tests/` (194 unit + 23 conversation + 2 telegram), `test_ground_truth/`
4. **Specifications & reference** — use cases, UI plans, architecture docs, entity schemas. These contain concrete feature specs, architecture decisions, and research findings that are NOT fully captured in code.

---

### Files by category:

**KEEP (runtime — MCP won't start without these):**

| File | Why keep |
|---|---|
| `docker-compose.mcp.yml` | Infrastructure — orchestrates all 5 services |
| `.env.example` | Setup reference for .env |
| `.gitignore` | Git config |

**KEEP (scheduled agent system — cron agents read/write these every run):**

| File | Why keep |
|---|---|
| `requirements_source.md` | Source of truth. NEVER touch. Re-read by cron agent every run. |
| `suck.md` | Living issue tracker — read + extended every cron run |
| `answers2603.md` | Decision log — Phase 2 output, append-only |
| `testruns2603.md` | Test results log — every test logged with timestamps |
| `implementation_plan.md` | Remaining work items — Phase 3 output |
| `audit29_03.md` | Current audit — Phase 1 context |

**KEEP (operator reference — useful context for humans and agents):**

| File | Why keep |
|---|---|
| `execution_plan.md` | Architecture diagram (MCP vs main app ports) |
| `PERFORMANCE.md` | Performance metrics — required by requirements_source.md |
| `tools.md` | Tool reference (26 tools) — referenced by CONNECT.md |
| `CONNECT.md` | How to connect to MCP — setup guide for users |
| `KEYWORDS_EXAMPLE.png` | Apollo filter test data — visual reference |

**KEEP (specifications — concrete feature specs not fully in code):**

| File | Why keep |
|---|---|
| `ENTITY_SCHEMA.md` | Entity relationship diagram — quick visual reference, easier than reading 13 model files |
| `TELEGRAM_BOT_ARCHITECTURE.md` | Architecture + cost/quality tradeoff analysis for model selection |
| `ONBOARDING_FLOW.md` | System validation flow diagram — useful for onboarding new developers |
| `APOLLO_MCP_BEHAVIOUR.md` | Apollo tool testing results (9 tools, credit costs, rate limits) — unique research data |
| `GATHERING_REFERENCE.md` | Parameter specs and credit costs — handy reference |
| `requirements.md` | Structured version of requirements_source.md — easier to scan than raw transcript |

**ARCHIVE (superseded — content fully merged into audit29_03.md):**

| File | Superseded by | Evidence |
|---|---|---|
| `GAP_AUDIT.md` | `audit29_03.md` | All 5 gaps covered in audit sections |
| `ARCHITECTURE_FIX.md` | `audit29_03.md` Part 6B | MCP independence requirements merged |
| `audit29_03_solution.md` | `audit29_03.md` | Solution phases merged into main audit |
| `SECURITY.md` | `audit29_03.md` Part 5 | Security specs merged |
| `block_fix.md` | `suck.md` | Issue #29 tracked in living issue log |

**ARCHIVE (proven byte-identical duplicates — originals kept in ui-plan/):**

| File | Duplicate of | Verified |
|---|---|---|
| `EXTENDED_REQUIREMENTS.md` | `ui-plan/EXTENDED_REQUIREMENTS.md` | byte-identical (7,691 bytes each) |
| `SHARED_CODE_STRATEGY.md` | `ui-plan/SHARED_CODE_STRATEGY.md` | byte-identical (7,414 bytes each) |
| `PIPELINE_PAGE_UI_REQUIREMENTS.md` | `ui-plan/PIPELINE_PAGE_UI_REQUIREMENTS.md` | byte-identical (12,985 bytes each) |

**ARCHIVE (one-time docs — content captured elsewhere with no unique value remaining):**

| File | Why archive |
|---|---|
| `NEW_USER_FLOW.md` | Step-by-step covered by conversation test 01 + HOW_TO_TEST.md |
| `TEST_GUIDE.md` | Superseded by `tests/HOW_TO_TEST.md` + `tests/conversations/README.md` |
| `CLAUDE_CODE_COMPLETE_GUIDE.md` | Generic Claude Code setup — not MCP-specific, doesn't belong here |

**DELETE (genuinely worthless — zero information value):**

| File | Why delete |
|---|---|
| `Untitled` | 24 bytes, no meaningful content |
| `test_mcp_flow.py` | Stale test script at root — real tests in `tests/` |
| `SOLVE.png` | Screenshot — no context, no filename, no reference anywhere |
| `approach.png` | Screenshot — no context, no reference anywhere |
| `to_build.png` | Screenshot — no context, no reference anywhere |

**DECISION NEEDED (ask user):**

| File | Question |
|---|---|
| `take-test-100.csv` | 969 companies, 1.9MB. Used to generate test data in tests/test_data/. Still needed? Or archive since test data already extracted? |

---

### Directories:

**KEEP (runtime):**

| Dir | Why |
|---|---|
| `backend/` | MCP backend — mounted as volume by docker-compose |
| `frontend/` | MCP frontend — built by docker-compose |
| `telegram/` | Telegram bot — built by docker-compose |

**KEEP (scheduled agent system):**

| Dir | Why |
|---|---|
| `cron_build/` | **Scheduled agent brain** — instruction set + continuity tracking for autonomous cron agents |

**KEEP (testing):**

| Dir | Why |
|---|---|
| `tests/` | Test suite (194 unit + 23 conversation + 2 telegram) |
| `test_ground_truth/` | Ground truth for offer discovery — referenced by scheduled_task Step 2 |

**KEEP (specifications — contain unique feature specs and implementation strategies):**

| Dir | Contents | Why keep |
|---|---|---|
| `use_cases/` | `pages.md` (page-by-page UI requirements), `people_column.md` (CRM deep links, blacklist overrides), `pipeline_table.md` (column management, iteration filters) | Concrete feature specs with requirements not yet fully implemented. Better to have described than not. |
| `ui-plan/` | `EXTENDED_REQUIREMENTS.md`, `SHARED_CODE_STRATEGY.md`, `PIPELINE_PAGE_UI_REQUIREMENTS.md`, `IMPLEMENTATION_PLAN.md` (Vite alias architecture — unique, not duplicated at root) | UI implementation strategy + pipeline requirements. IMPLEMENTATION_PLAN.md exists ONLY here. |
| `apollo_filters/` | `PLAN.md` — filter selection strategy | Referenced for filter_intelligence approach |

**DELETE (auto-generated, no value):**

| Dir | Why |
|---|---|
| `tmp/` | 91 screenshot PNGs (9.5MB). Auto-generated test artifacts. Regenerated per test run. |
| `.pytest_cache/` | Auto-generated cache — recreated on next test run |

---

## Summary

| Action | Count | Size saved |
|---|---|---|
| KEEP | 23 files + 10 dirs | — |
| ARCHIVE (proven superseded/duplicate) | 8 files | ~50KB docs |
| DELETE (junk + auto-generated) | 5 files + 2 dirs | ~10MB |
| ASK USER | 1 file (`take-test-100.csv`) | 1.9MB |

---

## Execution Plan

```bash
# Step 1: Create archive directory
mkdir -p mcp/.archive

# Step 2: Move superseded docs (content fully merged into audit29_03.md)
mv mcp/GAP_AUDIT.md mcp/.archive/
mv mcp/ARCHITECTURE_FIX.md mcp/.archive/
mv mcp/audit29_03_solution.md mcp/.archive/
mv mcp/SECURITY.md mcp/.archive/
mv mcp/block_fix.md mcp/.archive/

# Step 3: Move proven byte-identical duplicates (originals stay in ui-plan/)
mv mcp/EXTENDED_REQUIREMENTS.md mcp/.archive/
mv mcp/SHARED_CODE_STRATEGY.md mcp/.archive/
mv mcp/PIPELINE_PAGE_UI_REQUIREMENTS.md mcp/.archive/

# Step 4: Delete junk (genuinely worthless)
rm mcp/Untitled
rm mcp/test_mcp_flow.py
rm mcp/SOLVE.png
rm mcp/approach.png
rm mcp/to_build.png

# Step 5: Delete auto-generated dirs
rm -rf mcp/.pytest_cache
rm -rf mcp/tmp/

# Step 6: Add .archive/ to .gitignore
echo ".archive/" >> mcp/.gitignore
```

---

## After Cleanup: Clean Directory Structure

```
mcp/
├── backend/                    # MCP backend (FastAPI + SQLAlchemy)
├── frontend/                   # MCP frontend (React + Vite)
├── tests/                      # Test suite (194 unit + 23 conversation + 2 telegram)
│   ├── conversations/          # 23 JSON conversation tests + README.md
│   ├── telegram/               # Telegram bot E2E tests (2 scripts + suck.md)
│   ├── test_data/              # CSV/Sheet/Drive test fixtures
│   ├── conftest.py
│   ├── test_multi_source_pipeline.py
│   ├── test_processing_steps.py
│   ├── run_conversation_tests.py
│   └── HOW_TO_TEST.md
├── telegram/                   # Telegram bot (aiogram + GPT-4o-mini)
├── cron_build/                 # Scheduled agent brain
│   ├── scheduled_task_v1.md    # Agent instruction set
│   ├── progress.md             # Agent continuity tracking
│   ├── build_log.md            # Agent work history
│   └── DIFF_FROM_ORIGINAL.md   # Delta from original requirements
├── use_cases/                  # Feature specifications
│   ├── pages.md                # Page-by-page UI requirements
│   ├── people_column.md        # CRM deep links, blacklist overrides
│   └── pipeline_table.md       # Column management, iteration filters
├── ui-plan/                    # UI implementation strategy
│   ├── EXTENDED_REQUIREMENTS.md
│   ├── SHARED_CODE_STRATEGY.md
│   ├── PIPELINE_PAGE_UI_REQUIREMENTS.md
│   └── IMPLEMENTATION_PLAN.md  # Vite alias architecture (unique to this dir)
├── test_ground_truth/          # Ground truth for evaluation
├── apollo_filters/             # Filter selection strategy
├── .archive/                   # 8 superseded/duplicate docs (recoverable)
│
├── docker-compose.mcp.yml      # Infrastructure
├── .env.example                # Setup template
├── .gitignore
│
├── requirements_source.md      # THE source of truth (NEVER touch)
├── audit29_03.md               # Current audit — cron agent Phase 1
├── suck.md                     # Living issue tracker
├── answers2603.md              # Decision log
├── testruns2603.md             # Test results log
├── implementation_plan.md      # Remaining work
├── execution_plan.md           # Architecture diagram
├── PERFORMANCE.md              # Performance metrics
├── CONNECT.md                  # How to connect
├── tools.md                    # Tool reference (26 tools)
│
├── requirements.md             # Structured version of requirements_source
├── ENTITY_SCHEMA.md            # Entity relationship diagram
├── TELEGRAM_BOT_ARCHITECTURE.md # Architecture + model cost analysis
├── ONBOARDING_FLOW.md          # System validation flow
├── APOLLO_MCP_BEHAVIOUR.md     # Apollo tool testing results
├── GATHERING_REFERENCE.md      # Parameter specs + credit costs
├── KEYWORDS_EXAMPLE.png        # Apollo filter visual reference
├── take-test-100.csv           # Source test data (ask user)
└── cleanup2903.md              # This plan (delete after execution)
```

**Result: 38 files → 30 files + 10 dirs. Only proven junk and duplicates removed.**

---

## What was NOT removed (and why)

| Previously proposed to archive | Now KEPT | Reason |
|---|---|---|
| `use_cases/` | KEEP | Contains concrete UI feature specs (people_column.md, pipeline_table.md) with requirements not yet fully implemented |
| `ui-plan/` | KEEP | `IMPLEMENTATION_PLAN.md` is unique here (no root copy). Contains Vite alias architecture strategy. |
| `requirements.md` | KEEP | Structured, scannable version of the raw transcript — easier to reference than requirements_source.md |
| `ENTITY_SCHEMA.md` | KEEP | Visual entity relationships — faster than reading 13 model files |
| `TELEGRAM_BOT_ARCHITECTURE.md` | KEEP | Model cost/quality tradeoff analysis — unique research |
| `ONBOARDING_FLOW.md` | KEEP | Flow diagram — useful for onboarding |
| `APOLLO_MCP_BEHAVIOUR.md` | KEEP | Apollo tool credit costs + rate limit data — unique research |
| `GATHERING_REFERENCE.md` | KEEP | Parameter defaults + costs — handy reference |
| `tests/` | KEEP | Essential testing infrastructure |

---

## Risk Mitigation

1. **Conservative approach** — only 8 files archived, 5 files deleted (all verified junk)
2. **`.archive/` not `.deleted/`** — everything recoverable
3. **Add to .gitignore** — archive doesn't pollute git
4. **No specs removed** — use_cases/, ui-plan/, research docs all preserved
5. **No code touched** — only docs and artifacts
6. **Scheduled agent system fully preserved** — cron_build/ + all referenced files
7. **Test infrastructure fully preserved** — tests/ + test_ground_truth/

---

*Plan created 2026-03-29. Do NOT execute without user approval.*
