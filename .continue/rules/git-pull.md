---
name: Git Pull
description: Pull latest changes from remote for sales_engineer (GitHub) or magnum-opus (GitLab)
invokable: true
---

Всегда отвечай на русском языке.


Pull the latest changes from origin for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо: sales или mo.
Выполни: `cd <repo_path> && git pull origin $(git branch --show-current)`

Если есть незакоммиченные изменения - предупреди и спроси, сделать ли stash.
Покажи результат.
