# Valuable Claude Code Patterns from everything-claude-code

Source: https://github.com/affaan-m/everything-claude-code
Extracted: 2026-03-31 — only patterns relevant to our project (FastAPI + React leadgen platform)

---

## 1. Hooks (settings.json)

Hooks are shell commands that run automatically before/after Claude Code tool calls.
Configure in `~/.claude/settings.json` under `"hooks"` key.

### Pre-commit quality gate
Blocks commits that contain debug statements or secrets:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "if echo \"$TOOL_INPUT\" | grep -q 'git commit'; then echo \"$TOOL_INPUT\" | python3 -c \"import sys,json; d=json.load(sys.stdin); exit(2 if 'console.log' in open(d.get('command','')).read() else 0)\" 2>/dev/null; fi",
        "timeout": 5000
      }
    ]
  }
}
```

### Auto-format after edits (practical)
Run prettier/biome automatically after Claude edits JS/TS files:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "FILE=$(echo \"$TOOL_INPUT\" | python3 -c \"import sys,json; print(json.load(sys.stdin).get('file_path',''))\"); if [[ \"$FILE\" == *.ts || \"$FILE\" == *.tsx || \"$FILE\" == *.js ]]; then npx biome format --write \"$FILE\" 2>/dev/null || npx prettier --write \"$FILE\" 2>/dev/null; fi",
        "timeout": 10000
      }
    ]
  }
}
```

### Desktop notification on task completion (macOS)
```json
{
  "hooks": {
    "Stop": [
      {
        "command": "osascript -e 'display notification \"Claude finished working\" with title \"Claude Code\"'",
        "timeout": 3000
      }
    ]
  }
}
```

### Session state preservation before context compaction
Saves working state so Claude doesn't lose track after auto-compact:
```json
{
  "hooks": {
    "PreCompact": [
      {
        "command": "mkdir -p ~/.claude/session-data && echo \"$(date -Iseconds) compact triggered\" >> ~/.claude/session-data/compact.log",
        "timeout": 5000
      }
    ]
  }
}
```

---

## 2. Session Save/Resume Pattern

When working on a long task that might span sessions, save state to a file:

**Save**: write to `~/.claude/session-data/YYYY-MM-DD-<id>-session.md`:
```markdown
## What We Are Building
[1-3 paragraphs]

## What WORKED
- [Specific evidence: test output, verified behavior]

## What Did NOT Work (CRITICAL — prevents retrying dead ends)
- Approach X failed because: [exact error]
- Approach Y failed because: [exact error]

## What Has NOT Been Tried Yet
- [Promising untested approaches]

## Current State of Files
| File | Status | Notes |
|------|--------|-------|
| backend/app/services/foo.py | Modified | Added X method |

## Decisions Made
- Chose approach A over B because [reason]

## Exact Next Step
[Precise instruction for resuming]
```

**Resume**: Read the session file at start of new conversation.

This is more structured than our current memory system for in-progress work.

---

## 3. Orchestration — Multi-Agent Workflows

Chain specialized agents with structured handoffs:

```
/orchestrate feature "Add user authentication"
→ planner → tdd-guide → code-reviewer → security-reviewer
```

Each agent produces a handoff document:
```markdown
## HANDOFF: planner -> implementer

### Context
[Summary of what was done]

### Findings
[Key discoveries]

### Files Modified
[List]

### Open Questions
[For next agent]

### Recommendations
[Suggested next steps]
```

**Applicable to us**: When doing complex features, chain:
1. Plan agent (architecture)
2. Implementation (code)
3. Review agent (quality check)
4. Deploy

Currently we do this implicitly. Making it explicit with handoff docs could help with large features.

---

## 4. Loop Patterns

Four loop modes for autonomous work:

| Pattern | Description | Use Case |
|---------|-------------|----------|
| `sequential` | Task list, one by one | Batch of independent fixes |
| `continuous-pr` | Loop: implement → test → PR → next | Feature backlog |
| `rfc-dag` | DAG of dependent tasks | Complex feature with dependencies |
| `infinite` | Keep running until stopped | Monitoring, polling |

Safety defaults:
- Verify tests pass before first iteration
- Explicit stop condition required
- Quality gates between iterations

**Applicable to us**: The `sequential` pattern for batch operations like "scrape and label 238K domains" — process in chunks with checkpoints.

---

## 5. Checkpoint System

Named save-points during development:

```
/checkpoint create "before-refactor"    # Save state
/checkpoint verify "before-refactor"    # Compare current vs saved
/checkpoint list                        # Show all checkpoints
```

Implementation: git stash/commit + log to `.claude/checkpoints.log` with timestamp + SHA.

**Applicable to us**: Before risky refactors, create a named checkpoint. Simpler than remembering git SHAs.

---

## 6. Context Budget Analysis

Analyze what's eating your context window:

1. **Inventory** all loaded components (CLAUDE.md, memory, MCP tools, rules)
2. **Classify** by type (system prompt, tool definitions, conversation)
3. **Detect issues** (oversized files, redundant tool schemas, bloated memory)
4. **Report** with optimization suggestions

**Applicable to us**: Our MEMORY.md is already at 240 lines (limit 200). We have 60+ MCP tools loaded. Worth periodically auditing what's consuming context.

---

## 7. DevFleet — Parallel Agents in Worktrees

Run multiple Claude agents in parallel, each in its own git worktree:

1. Describe project → generates mission DAG
2. Approve plan → dispatches first independent missions
3. Missions auto-chain as dependencies complete
4. Max 3 concurrent agents (configurable)

Requires DevFleet MCP server on localhost:18801.

**Applicable to us**: Could parallelize independent pipeline work — e.g., scrape domains in one worktree while building UI in another. High setup cost though.

---

## 8. Instinct System (Learned Patterns)

Automatically extract reusable patterns from sessions:

- **Project-scoped**: learned in one project
- **Promotable**: if pattern appears in 2+ projects, promote to global
- Stored in `~/.claude/homunculus/instincts/`
- Confidence thresholds prevent low-quality patterns from propagating

**Applicable to us**: Our memory system does something similar but manually. Auto-extraction could catch patterns we miss.

---

## Summary: What to Actually Adopt

### High value, low effort:
1. **macOS desktop notifications** on Stop hook — know when Claude finishes
2. **Auto-format hook** for frontend TypeScript files
3. **Session save template** — structured state preservation for multi-session work

### Medium value, medium effort:
4. **Checkpoint command** — named save-points before risky changes
5. **Context budget audit** — we're close to limits already

### Interesting but not urgent:
6. **Orchestration handoff docs** — useful for very large features
7. **Loop patterns** — useful for batch processing (domain scraping project)
8. **DevFleet parallel agents** — cool but high setup cost
