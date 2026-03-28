# MCP Conversation Tests

## Architecture

Each test file = one user journey as a conversation.

```
tests/conversations/
  01_new_user_easystaff.json        — User 1: existing campaigns, 2 segments
  02_new_user_fashion.json          — User 2: no campaigns, fashion brands Italy
  03_add_more_targets.json          — User asks to gather more for existing pipeline
  04_edit_sequence.json             — User edits sequence after reviewing
  05_activate_campaign.json         — User approves and activates
  06_campaigns_page.json            — Campaign management scenarios
  07_project_page_stats.json        — Project stats and analytics
  08_pipeline_stepper.json          — Pipeline phase stepper UI
  09_multi_source_csv_first.json    — [NEW] User 2: CSV source → Result project, custom prompt
  10_multi_source_sheet_add.json    — [NEW] User 2: Google Sheet → "add to existing pipeline" (40 dups)
  11_multi_source_drive_add.json    — [NEW] User 2: Google Drive folder → "add to existing" (70 dups)
  12_custom_prompt_chain.json       — [NEW] User 2: Multi-step classification (classify → filter → classify)
  13_blacklist_isolation.json       — [NEW] Blacklist project isolation + same-project dedup
  14_source_suggestion_edges.json   — [NEW] Source suggestion edge cases (7 scenarios)
```

## Multi-Source Pipeline Test Flow (09–13)

**User**: services@getsally.io
**Project**: Result (LATAM fashion/apparel)

```
09: CSV Import (110 companies)
    ↓ user provides draft classification prompt
    ↓ MCP improves to god-level via-negativa prompt
    ↓ full pipeline: gather → blacklist → scrape → analyze
    ↓ Result: 110 companies classified

10: Google Sheet Import (110 companies)
    ↓ MCP detects existing pipeline, ASKS "new or existing?"
    ↓ User says "add to existing"
    ↓ Dedup: 40 overlap with CSV → 70 new
    ↓ Result: 180 total in project

11: Google Drive Import (105 companies across 3 files)
    ↓ MCP asks "new or existing?" again
    ↓ User says "add to existing"
    ↓ Dedup: 35 from CSV + 35 from Sheet = 70 dups → 35 new
    ↓ Result: 215 total in project

12: Custom Prompt Chain
    ↓ User provides 3-step chain: classify → filter → size
    ↓ MCP improves each prompt to god-level
    ↓ Re-analyzes with prompt_steps

13: Blacklist Isolation
    ↓ Create separate project B
    ↓ Verify project B NOT affected by Result's blacklist
    ↓ Re-gather same CSV for Result → 100% duplicates
```

### Dedup Matrix (verified in tests)

| Source | Total | New | Dup (from) |
|--------|-------|-----|------------|
| CSV | 110 | 110 | 0 |
| Sheet | 110 | 70 | 40 (CSV) |
| Drive | 105 | 35 | 35 (CSV) + 35 (Sheet) |
| **Total unique** | **215** | | |

### Critical MCP Behaviors Tested

1. **"New or existing?" question** — When user provides a new source for a project that already has pipeline runs, MCP MUST ask whether to create new or add to existing. Must NOT auto-launch.

2. **Prompt improvement** — User provides rough draft prompt. MCP builds god-level classification prompt with: detailed criteria, exclusion rules, edge cases, examples, output format. Like the Drive JSON enricher prompts.

3. **Project-scoped blacklist** — Different projects can contact same company. Same project deduplicates. No cross-project leakage.

4. **Source suggestion** — MCP detects source type from user input: file paths → CSV, Sheet URLs → Sheet, Drive URLs → Drive, keyword queries → Apollo (if key available).

## Test File Structure

```json
{
  "id": "09_multi_source_csv_first",
  "description": "...",
  "user_email": "services@getsally.io",
  "project_name": "Result",

  "steps": [
    {
      "step": 1,
      "phase": "source_selection",
      "user_prompt": "I have a CSV with LATAM fashion companies. Here: /data/take-test-100.csv",
      "user_prompt_variants": ["...", "...", "..."],
      "expected_tool_calls": ["tam_gather"],
      "expected_behavior": {
        "source_type": "csv.companies.file",
        "response_must_contain": ["CSV", "companies"],
        "response_must_not_contain": ["error"]
      },
      "critical_requirement": "..."
    }
  ],

  "final_verification": {
    "db_checks": ["..."],
    "ui_checks": [{"page": "/pipeline/{run_id}", "check": "..."}],
    "dedup_matrix": {}
  }
}
```

## How Testing Works

1. **Load test file** — get user prompts and expected behavior
2. **Shuffle prompts** — pick random variant (same intent, different wording)
3. **Execute via REAL MCP SSE protocol** — connect to `http://46.62.210.24:8002/mcp/sse`, send JSON-RPC messages via `/mcp/messages?session_id=X`. This is how a real Claude agent connects.
4. **Compare actual vs expected**:
   - Did the right tools get called? (tool_calls match)
   - Did the response contain required fields? (must_contain)
   - Were links included where expected? (links_expected)
   - Were segments correctly split? (segment_labels)
   - Did dedup counts match? (new_companies, duplicates)
5. **Score** — percentage match on each dimension
6. **Screenshot UI pages** — verify visual state matches expected
7. **Check conversations page** — all messages visible

## Scoring

| Dimension | Weight | How scored |
|-----------|--------|------------|
| Correct tools called | 25% | Exact match on tool sequence |
| Response structure | 20% | Must-contain fields present |
| Dedup accuracy | 20% | Exact match on new/dup counts |
| Prompt quality | 15% | Improved prompt is longer, has criteria/examples |
| Source detection | 10% | Correct source_type selected |
| No errors | 10% | No error/failed in response |

**Pass threshold**: 80% overall score
**God threshold**: 95% overall score
