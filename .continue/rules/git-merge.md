---
name: Git Merge
description: Merge branches for sales_engineer or magnum-opus
invokable: true
---

Всегда отвечай на русском языке.


Merge a branch into the current branch for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо: sales или mo.

Steps:
1. `cd <repo_path>`
2. Show current branch with `git branch --show-current`
3. Show available branches with `git branch -a`
4. Спроси какую ветку влить в текущую
5. Run `git merge <branch>`
6. Если конфликты - покажи файлы и спроси как решать
7. Show the result
