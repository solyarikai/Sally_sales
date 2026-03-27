# What changed vs original prompt

## Structure
- **Before**: One giant wall of text, stream-of-consciousness
- **After**: 5 numbered phases with clear headers, sub-steps, and a rules section

## Clarity improvements (NO meaning removed)
- "Write all answers to questions in requirements_source.md" → Phase 2 with explicit instruction to quote original + answer with rationale
- "Write all LEFT implementation plan" → Phase 3 with explicit "check actual source code, not assumptions"
- "LOOK FOR DONE ALREADY" → "If a feature exists in code, it's DONE — mark it as such"
- "TEST TEST FLOW FOR IMAGINING I'M REGISTERING" → Phase 4 broken into 8 numbered steps with exact inputs/outputs
- "ensure via mcp (test only real mcp connection)" → bolded rule: "Test via REAL MCP connection"
- "extend suck.md with any new issps" → "Extend with any NEW issues found during testing"
- "DON'T STOP UNTIL DONE, ACT AS GOD" → "Don't stop until EVERY step is tested with NO issues"
- Campaign quality requirements → Step 6 with explicit 90% accuracy gate and remediation instructions
- "up to 3 target people" → marked as "HARD LIMIT — make it a configurable requirement"
- Eleonora signature requirement → Step 4 with explicit filter + signature instruction
- Website scraping for project context → Step 2, explicit flow
- Subject line normalization → Step 5, explicit rule
- Browser testing → Step 8 + test requirements section with specific checks

## Additions (implied in original, made explicit)
- "Resume where you left off" — since this runs every 30 min on cron
- "Read suck.md FIRST" — was at the end, moved to top (more effective)
- Output files table — same files, clearer format
- "Don't wait for user input — simulate responses as defined above" — agent needs this to run autonomously

## Nothing removed
Every sentence, intention, and requirement from the original is preserved. Nothing was deleted or softened.
