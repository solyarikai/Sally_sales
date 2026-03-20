# TAM Gathering Pipeline — Operator Guide

## What is this?

A reusable system for finding target companies across all projects. Instead of everyone writing separate scripts for Apollo/Clay/Google Sheets, there's now ONE pipeline that tracks everything: which searches were run, which companies were found, which were rejected, and why.

## Why use it?

- **No duplicate work.** If someone already searched "SaaS companies in Germany", the system knows and won't re-search.
- **No lost data.** Every search, every filter, every AI analysis is saved. You can always see what was tried before.
- **Project isolation.** Your work on Inxy doesn't affect EasyStaff RU. Different projects, different pipelines.
- **Cost control.** FindyMail (the expensive part) only runs after you explicitly approve the target list and the cost.

## How to use it

### Step 1: Open Claude Code in the magnum-opus repo

```bash
cd ~/magnum-opus-project/repo
claude
```

### Step 2: Tell Claude which project and what you need

**Always mention your project name.** This is the most important thing.

Examples:
- "Find digital agencies in UAE with 10-50 employees for **easystaff global**"
- "Import this Google Sheet into the pipeline for **inxy**: https://docs.google.com/spreadsheets/d/..."
- "Search Apollo for SaaS companies in Germany for **tfp**"
- "I have a Clay export, analyze it for **mifort**"

### Step 3: Follow the checkpoints

Claude will run the pipeline and stop at 3 checkpoints. You must approve each one.

**Checkpoint 1 — "Is this my project?"**
Claude shows you:
- Your project name and ID
- Your active campaigns and contact counts
- Which companies were rejected (already in your campaigns)

→ Confirm if the project and campaigns look correct.

**Checkpoint 2 — "Are these the right targets?"**
Claude shows you:
- The list of companies AI thinks are good targets
- Confidence scores and reasoning
- How many companies couldn't be analyzed (scraping failed)

→ Review the list. Remove any that don't fit. Confirm.

**Checkpoint 3 — "Approve the cost?"**
Claude shows you:
- How many emails to verify via FindyMail
- The estimated cost

→ Approve or reject.

### Step 4: Done

After all checkpoints, you have a verified target list ready for outreach.

## Available data sources

| Say this to Claude | What happens |
|---|---|
| "Search Apollo for [description]" | Uses Apollo People or Companies search |
| "Search Clay for [description]" | Uses Clay TAM export |
| "Import this Google Sheet: [URL]" | Reads the sheet (auto-detects columns) |
| "Import this CSV" | Reads CSV file |
| "Here's a list of domains: [...]" | Manual domain import |

## If Claude tries to write a script instead of using the pipeline

This can happen. If Claude starts writing a standalone Python script instead of calling the pipeline API, say:

> "Use the gathering pipeline, don't write a separate script. Check CLAUDE.md."

This redirects Claude to the pipeline system.

## If something goes wrong

| Problem | What to do |
|---|---|
| Claude picked the wrong project | At checkpoint 1, say "wrong project, cancel this run" |
| Blacklist rejected too many/too few | Check if campaign_filters are correct for your project |
| AI analysis gave bad results | At checkpoint 2, say "re-analyze with a different prompt" |
| Google Sheet won't import | Make sure the sheet is in the shared Google Drive folder, or share it with the service account |
| Pipeline is stuck | Say "check for in-progress runs for project [name]" — there might be a paused checkpoint |
| Want to start over | Say "cancel run [number]" |

## Best practices

1. **Always say your project name.** "For inxy", "for easystaff ru", "for tfp". Every time.
2. **Review checkpoint 1 carefully.** This is where you catch wrong project scope.
3. **Don't approve targets blindly at checkpoint 2.** Scan the list — AI makes mistakes.
4. **Check for paused runs** before starting new ones. Say "any in-progress runs for [project]?"
5. **Google Sheets**: just paste the URL. The system auto-detects column names.
