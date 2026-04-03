---
name: Git Commit
description: Auto-commit with generated message for sales_engineer or magnum-opus
invokable: true
---

Create a commit with an auto-generated message for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub (Yarik174/Sally_sales)
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Ask me which repo: sales or mo.

Steps:
1. `cd <repo_path>`
2. Run `git status` and `git diff --staged` (if nothing staged, run `git diff`)
3. Based on the changes, generate a short commit message in this format:
   - `fix:` for bugfixes
   - `feat:` for new features
   - `update:` for changes to existing code
   - `docs:` for documentation
   - `refactor:` for refactoring
   - `chore:` for maintenance tasks
4. Stage all changes with `git add -A`, commit, and push to origin immediately
5. Show the commit message and push result

Do NOT ask for confirmation — commit and push automatically.
Message language: English, 1 line, max 72 chars.
