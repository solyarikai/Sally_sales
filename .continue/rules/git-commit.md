---
name: Git Commit
description: Auto-commit with generated message for sales_engineer or magnum-opus
invokable: true
---

Всегда отвечай на русском языке.


Create a commit with an auto-generated message for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо: sales или mo.

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

НЕ спрашивай подтверждение — commit and push automatically.
Сообщение коммита: английский, 1 строка, макс 72 символа.
