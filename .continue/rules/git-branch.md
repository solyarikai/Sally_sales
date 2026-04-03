---
name: Git Branch
description: Create, switch, or list branches for sales_engineer or magnum-opus
invokable: true
---

Всегда отвечай на русском языке.


Manage branches for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Спроси какой репо и какое действие:
- **create** — ask for branch name, create from current branch: `git checkout -b <name>`
- **switch** — show existing branches with `git branch -a`, ask which to switch to
- **delete** — show local branches, ask which to delete: `git branch -d <name>`
- **list** — show all local and remote branches

Branch naming convention: `type/short-description` (e.g. `feat/new-pipeline`, `fix/blacklist-bug`)
