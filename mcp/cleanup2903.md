# MCP Directory Cleanup Plan — 2026-03-29

**Goal:** Remove redundant/useless files, keep essentials, make directory beautiful.
**Rule:** PLAN ONLY. Do NOT execute. Review before acting.
**Safety:** Move to `mcp/.archive/` first (not delete). Hard-delete after 1 week if no issues.

---

## Current State: 38 files + 11 dirs at mcp/ root

### Files by category:

**KEEP (essential, actively used):**

| File | Why keep |
|---|---|
| `requirements_source.md` | Source of truth. NEVER touch. |
| `audit29_03.md` | Current audit — active reference |
| `docker-compose.mcp.yml` | Infrastructure — required to run |
| `.env.example` | Setup reference |
| `.gitignore` | Git config |
| `suck.md` | Living issue tracker — referenced by scheduled_task |
| `KEYWORDS_EXAMPLE.png` | Test data — referenced for Apollo filter testing |

**KEEP (operational docs, referenced by scheduled_task or codebase):**

| File | Why keep | Notes |
|---|---|---|
| `answers2603.md` | Decision log — referenced by implementation_plan | Append-only history |
| `testruns2603.md` | Test results — requirements satisfaction matrix | Referenced by scheduled_task |
| `implementation_plan.md` | Remaining work items | Referenced by scheduled_task Phase 3 |
| `execution_plan.md` | Architecture diagram (MCP vs main app ports) | Quick reference |
| `PERFORMANCE.md` | Performance metrics | Required by requirements_source |
| `tools.md` | Tool reference (26 tools) | Referenced by CONNECT.md |
| `CONNECT.md` | How to connect to MCP | Setup guide for users |

**ARCHIVE (were useful, now superseded by audit29_03.md):**

| File | Superseded by | Action |
|---|---|---|
| `GAP_AUDIT.md` | `audit29_03.md` | → `.archive/` |
| `ARCHITECTURE_FIX.md` | `audit29_03.md` Part 6B | → `.archive/` |
| `block_fix.md` | `suck.md` (issues tracked there) | → `.archive/` |
| `audit29_03_solution.md` | `audit29_03.md` (merged into main audit) | → `.archive/` |
| `SECURITY.md` | `audit29_03.md` Part 5 | → `.archive/` |

**ARCHIVE (duplicates — same content exists in ui-plan/):**

| File | Duplicate of | Action |
|---|---|---|
| `EXTENDED_REQUIREMENTS.md` | `ui-plan/EXTENDED_REQUIREMENTS.md` | Keep ui-plan/ version → archive root |
| `SHARED_CODE_STRATEGY.md` | `ui-plan/SHARED_CODE_STRATEGY.md` | Keep ui-plan/ version → archive root |
| `PIPELINE_PAGE_UI_REQUIREMENTS.md` | `ui-plan/PIPELINE_PAGE_UI_REQUIREMENTS.md` | Keep ui-plan/ version → archive root |

**ARCHIVE (one-time docs, served their purpose):**

| File | Why archive |
|---|---|
| `requirements.md` | Superseded by `requirements_source.md` (the raw transcript is the real source) |
| `APOLLO_MCP_BEHAVIOUR.md` | Research doc — findings already applied to filter_intelligence.py |
| `GATHERING_REFERENCE.md` | Reference notes — pipeline docs in docs/pipeline/ are the real reference |
| `NEW_USER_FLOW.md` | Superseded by conversation test 01 + HOW_TO_TEST.md |
| `ONBOARDING_FLOW.md` | Superseded by conversation tests 01-02 |
| `TEST_GUIDE.md` | Superseded by `tests/conversations/README.md` + `tests/HOW_TO_TEST.md` |
| `TELEGRAM_BOT_ARCHITECTURE.md` | Architecture applied — code in telegram/bot.py is the source of truth |
| `ENTITY_SCHEMA.md` | Schema visible in models/*.py — code is the real schema |
| `CLAUDE_CODE_COMPLETE_GUIDE.md` | Setup guide — not MCP-specific, doesn't belong here |

**DELETE (junk, no value):**

| File | Why delete |
|---|---|
| `Untitled` | Near-empty file — 24 bytes, no meaningful content |
| `test_mcp_flow.py` | Stale test script at root — real tests in tests/ |
| `SOLVE.png` | Screenshot — no context, no reference |
| `approach.png` | Screenshot — no context, no reference |
| `to_build.png` | Screenshot — no context, no reference |

**DECISION NEEDED (ask user):**

| File | Question |
|---|---|
| `take-test-100.csv` | 969 companies, 1.9MB. Used to generate test data in tests/test_data/. Still needed? Or archive since test data already extracted? |

---

### Directories:

**KEEP (essential):**

| Dir | Why |
|---|---|
| `backend/` | The MCP backend — core code |
| `frontend/` | The MCP frontend — core code |
| `tests/` | Test suite (194 unit + 23 conversation + 2 telegram) |
| `telegram/` | Telegram bot |
| `cron_build/` | Scheduled task + progress tracking |

**KEEP (useful reference):**

| Dir | Why | Notes |
|---|---|---|
| `test_ground_truth/` | Ground truth for offer discovery evaluation | Used by scheduled_task Step 2 |
| `apollo_filters/` | Apollo filter selection plan | Referenced for filter_intelligence approach |

**ARCHIVE (served their purpose):**

| Dir | Why archive |
|---|---|
| `ui-plan/` | UI specs now implemented in frontend/. Keep as reference but not needed at root level. |
| `use_cases/` | Use case descriptions — now covered by conversation tests + requirements_source |

**DELETE:**

| Dir | Why |
|---|---|
| `tmp/` | 91 screenshot PNGs (9.5MB). Test artifacts from previous runs. Screenshots should be regenerated per run, not stored permanently. |
| `.pytest_cache/` | Auto-generated cache — recreated on test run |

---

## Execution Plan

```bash
# Step 1: Create archive directory
mkdir -p mcp/.archive

# Step 2: Move superseded docs
mv mcp/GAP_AUDIT.md mcp/.archive/
mv mcp/ARCHITECTURE_FIX.md mcp/.archive/
mv mcp/block_fix.md mcp/.archive/
mv mcp/audit29_03_solution.md mcp/.archive/
mv mcp/SECURITY.md mcp/.archive/

# Step 3: Move duplicates (keep ui-plan/ versions)
mv mcp/EXTENDED_REQUIREMENTS.md mcp/.archive/
mv mcp/SHARED_CODE_STRATEGY.md mcp/.archive/
mv mcp/PIPELINE_PAGE_UI_REQUIREMENTS.md mcp/.archive/

# Step 4: Move one-time docs
mv mcp/requirements.md mcp/.archive/
mv mcp/APOLLO_MCP_BEHAVIOUR.md mcp/.archive/
mv mcp/GATHERING_REFERENCE.md mcp/.archive/
mv mcp/NEW_USER_FLOW.md mcp/.archive/
mv mcp/ONBOARDING_FLOW.md mcp/.archive/
mv mcp/TEST_GUIDE.md mcp/.archive/
mv mcp/TELEGRAM_BOT_ARCHITECTURE.md mcp/.archive/
mv mcp/ENTITY_SCHEMA.md mcp/.archive/
mv mcp/CLAUDE_CODE_COMPLETE_GUIDE.md mcp/.archive/

# Step 5: Move stale dirs
mv mcp/ui-plan mcp/.archive/
mv mcp/use_cases mcp/.archive/

# Step 6: Delete junk (truly worthless)
rm mcp/Untitled
rm mcp/test_mcp_flow.py
rm mcp/SOLVE.png
rm mcp/approach.png
rm mcp/to_build.png
rm -rf mcp/.pytest_cache

# Step 7: Delete tmp/ screenshots (9.5MB of test artifacts)
rm -rf mcp/tmp/

# Step 8: Add .archive/ to .gitignore
echo ".archive/" >> mcp/.gitignore
```

---

## After Cleanup: Clean Directory Structure

```
mcp/
├── backend/                    # MCP backend (FastAPI + SQLAlchemy)
├── frontend/                   # MCP frontend (React + Vite)
├── tests/                      # Test suite (194 unit + 23 conversation + telegram)
│   ├── conversations/          # 23 JSON conversation tests + README.md
│   ├── telegram/               # Telegram bot E2E tests (2 scripts + suck.md)
│   ├── test_data/              # CSV/Sheet/Drive test fixtures (test_csv_source.csv, test_sheet_source.csv, test_metadata.json, drive_folder/)
│   ├── conftest.py
│   ├── test_multi_source_pipeline.py
│   ├── test_processing_steps.py
│   ├── run_conversation_tests.py
│   └── HOW_TO_TEST.md
├── telegram/                   # Telegram bot (aiogram + GPT-4o-mini)
├── cron_build/                 # Scheduled task + progress tracking
│   ├── scheduled_task_v1.md
│   ├── progress.md
│   ├── build_log.md
│   └── DIFF_FROM_ORIGINAL.md
├── test_ground_truth/          # Ground truth for evaluation
├── apollo_filters/             # Filter selection strategy
├── .archive/                   # Archived docs (not deleted, recoverable)
│
├── docker-compose.mcp.yml      # Infrastructure
├── .env.example                # Setup template
├── .gitignore
│
├── requirements_source.md      # THE source of truth (NEVER touch)
├── audit29_03.md               # Current audit (90 issues)
├── suck.md                     # Living issue tracker
├── answers2603.md              # Decision log
├── testruns2603.md             # Requirements satisfaction matrix
├── implementation_plan.md      # Remaining work
├── execution_plan.md           # Architecture diagram
├── PERFORMANCE.md              # Performance metrics
├── CONNECT.md                  # How to connect to MCP
├── tools.md                    # Tool reference
├── KEYWORDS_EXAMPLE.png        # Apollo filter test data
├── take-test-100.csv           # Source test data (ask user if archive)
└── cleanup2903.md              # This plan (delete after execution)
```

**Result: 38 files → 14 files + 7 dirs (+`.archive/`). Clean, purposeful, no junk.**

---

## Risk Mitigation

1. **`.archive/` not `.deleted/`** — everything recoverable
2. **Add to .gitignore** — archive doesn't pollute git
3. **Review before executing** — user approves this plan first
4. **`take-test-100.csv` decision deferred** — ask user
5. **tmp/ screenshots** — can be regenerated by running tests again
6. **No code files touched** — only docs and artifacts

---

*Plan created 2026-03-29. Do NOT execute without user approval.*
