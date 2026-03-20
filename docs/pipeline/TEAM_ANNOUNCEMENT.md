# TAM Gathering Pipeline — What Changed & How to Use It

## For the team — March 2026

### What's new

We now have a **shared pipeline for finding target companies**. Instead of each person writing Apollo/Clay scripts, there's one system that everyone uses through Claude Code.

**What it gives you:**
- Automatic dedup (no more "we already contacted this company")
- Project-scoped blacklisting (your Inxy search won't block EasyStaff contacts)
- AI analysis with quality checkpoints before spending money
- Google Sheets import (just paste a URL)
- Full history of every search ever run

### How to start

1. `git pull origin main`
2. Open Claude Code: `cd ~/magnum-opus-project/repo && claude`
3. Tell Claude what you need. **Always mention your project name:**

> "Find 5000 digital agencies in UAE for **easystaff global**"

> "Import this Apollo export for **inxy**: https://docs.google.com/spreadsheets/d/..."

> "Search Clay for fintech companies in Singapore for **tfp**"

Claude handles the rest. It will pause at 3 checkpoints for your approval.

### The 3 checkpoints

1. **After blacklist** — Confirm this is your project + the right campaigns are being checked
2. **After AI analysis** — Review the target list before any money is spent
3. **Before FindyMail** — Approve the verification cost

You can't skip these. The system blocks until you approve.

### If Claude writes a script instead of using the pipeline

Say: **"Use the gathering pipeline, don't write a separate script. Check CLAUDE.md."**

### If something is stuck

Say: **"Check for in-progress runs for [my project name]"**

There might be a paused run waiting for your approval from a previous session.

### Full guide

See `docs/pipeline/OPERATOR_GUIDE.md` for troubleshooting and best practices.
