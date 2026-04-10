---
name: git-merge
description: "Merge branches for sales_engineer or magnum-opus. Используй когда: \"мердж\", \"merge\", \"слей ветки\", \"объедини\", \"влей ветку\"."
---

# /git-merge

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
3. Покажи текущую ветку: `git branch --show-current`
4. Покажи доступные ветки: `git branch -a`
5. Спроси в какую ветку влить текущую (обычно main)
6. `git checkout <target>` → `git merge <current_branch>`
7. Если конфликты — покажи конфликтные файлы, спроси как решать
8. Покажи результат
