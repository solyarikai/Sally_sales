---
name: git-branch
description: "Create, switch, list, or delete branches for sales_engineer or magnum-opus. Используй когда: \"ветка\", \"branch\", \"создай ветку\", \"переключись\", \"покажи ветки\"."
---

# /git-branch

## Repos

| Alias | Path | Remote |
|-------|------|--------|
| `sales` | `/Users/user/sales_engineer` | GitHub `https://$GITHUB_TOKEN@github.com/solyarikai/Sally_sales.git` |
| `mo` | `/Users/user/sales_engineer/magnum-opus` | GitLab (sally-saas/magnum-opus) |

## Язык

Всегда отвечай на русском языке.

## Steps

1. Спроси: какой репо (sales/mo) и действие (create/switch/delete/list)?
2. `cd <repo_path>`
3. Действия:
   - **create** — спроси имя, `git checkout -b <name>`
   - **switch** — покажи ветки `git branch -a`, спроси какую, `git checkout <name>`
   - **delete** — покажи локальные ветки, спроси какую, `git branch -d <name>`
   - **list** — `git branch -a`

## Соглашение об именовании

`type/short-description` (напр. `feat/new-pipeline`, `fix/blacklist-bug`)
