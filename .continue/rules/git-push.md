---
name: Git Push
description: Push changes to remote for sales_engineer (GitHub) or magnum-opus (GitLab)
invokable: true
---

Всегда отвечай на русском языке.


Push the current branch to origin for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо: sales или mo.

1. `cd <repo_path>`
2. Проверь `git status --short` — если есть изменения:
   - Сгенерируй коммит-сообщение по диффу (префикс `fix:`, `feat:`, `update:`, `docs:`, `refactor:`, `chore:`)
   - `git add -A && git commit -m "<message>"` — без подтверждения
3. `git push origin $(git branch --show-current)`
4. Если ошибка "no upstream", повтори с `-u`
5. Покажи результат (коммит + пуш)
