---
name: git-commit
description: >-
  Auto-commit with generated message and push for sales_engineer or magnum-opus.
  Используй когда: "закоммить", "commit", "коммит", "сохрани изменения", "зафиксируй код".
---

# /git-commit

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
3. Run `git status` and `git diff --staged` (if nothing staged, `git diff`)
4. Generate commit message using prefix:
   - `fix:` bugfix
   - `feat:` new feature
   - `update:` change to existing code
   - `docs:` documentation
   - `refactor:` refactoring
   - `chore:` maintenance
5. `git add -A && git commit -m "<message>"` — НЕ спрашивай подтверждение
6. `git push origin $(git branch --show-current)` — пушь сразу
7. Покажи сообщение коммита и результат пуша

## Правила

- НЕ спрашивай подтверждение — коммить и пушь автоматически
- Сообщение коммита: английский, 1 строка, макс 72 символа
