---
name: git-push
description: "Push current branch to remote for sales_engineer (GitHub) or magnum-opus (GitLab). Используй когда: \"запушь\", \"push\", \"отправь в репо\", \"пуш\", \"залей\"."
---

# /git-push

## Repos

| Alias | Path | Remote |
|-------|------|--------|
| `sales` | `/Users/user/sales_engineer` | GitHub `https://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@github.com/solyarikai/Sally_sales.git` |
| `mo` | `/Users/user/sales_engineer/magnum-opus` | GitLab (sally-saas/magnum-opus) |

## Язык

Всегда отвечай на русском языке.

## Steps

1. Спроси: sales или mo?
2. `cd <repo_path>`
3. Проверь `git status --short` — если есть изменения:
   - Сгенерируй коммит-сообщение по диффу (префикс `fix:`, `feat:`, `update:`, `docs:`, `refactor:`, `chore:`)
   - `git add -A && git commit -m "<message>"` — без подтверждения
4. `git push origin $(git branch --show-current)`
5. Если ошибка "no upstream", повтори с `-u`
6. Покажи результат (коммит + пуш)
