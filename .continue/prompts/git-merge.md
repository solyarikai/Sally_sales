---
name: Git Merge
description: Merge branches for sales_engineer or magnum-opus
invokable: true
---

Merge a branch into the current branch for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub (Yarik174/Sally_sales)
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Ask me which repo: sales or mo.

Steps:
1. `cd <repo_path>`
2. Show current branch with `git branch --show-current`
3. Show available branches with `git branch -a`
4. Ask which branch to merge into current
5. Run `git merge <branch>`
6. If there are conflicts, show the conflicting files and ask how to resolve
7. Show the result
