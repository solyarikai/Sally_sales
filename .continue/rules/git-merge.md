---
name: Git Merge
description: Merge branches for sales_engineer or magnum-opus
invokable: true
---

Всегда отвечай на русском языке.


Merge a feature branch into main for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо: sales или mo.

Steps:
1. `cd <repo_path>`
2. `git checkout main`
3. `git pull origin main` (чтобы всё было актуально)
4. Show current branch with `git branch --show-current` (должна быть main)
5. Show available branches with `git branch`
6. Спроси какую ветку влить в `main`
7. Run `git merge <branch>`
8. Если конфликты - покажи файлы и спроси как решать
9. `git push origin main` после успешного слияния (спроси подтверждение)
10. Show the result
