---
name: Git Branch
description: Create, switch, or list branches for sales_engineer or magnum-opus
invokable: true
---

Manage branches for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub (Yarik174/Sally_sales)
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Ask me which repo and what action:
- **create** — ask for branch name, create from current branch: `git checkout -b <name>`
- **switch** — show existing branches with `git branch -a`, ask which to switch to
- **delete** — show local branches, ask which to delete: `git branch -d <name>`
- **list** — show all local and remote branches

Branch naming convention: `type/short-description` (e.g. `feat/new-pipeline`, `fix/blacklist-bug`)
