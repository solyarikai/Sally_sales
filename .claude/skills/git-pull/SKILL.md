---
name: git-pull
description: "Pull latest changes from remote for sales_engineer (GitHub) or magnum-opus (GitLab). Используй когда: \"пулл\", \"pull\", \"обнови репо\", \"стяни\", \"забери изменения\"."
---

# /git-pull

## Repos

| Alias | Path | Remote |
|-------|------|--------|
| `sales` | `/Users/user/sales_engineer` | GitHub `https://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@github.com/solyarikai/Sally_sales.git` |
| `mo` | `/Users/user/sales_engineer/magnum-opus` | GitLab (sally-saas/magnum-opus) |

## Язык

Всегда отвечай на русском языке.

## Steps

1. Спроси: sales или mo?
2. `cd <repo_path> && git pull origin $(git branch --show-current)`
3. Если есть незакоммиченные изменения — предупреди и спроси, сделать ли stash
4. Покажи результат
