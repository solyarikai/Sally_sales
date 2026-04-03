---
name: Git Pull
description: Pull latest changes from remote for sales_engineer (GitHub) or magnum-opus (GitLab)
invokable: true
---

Pull the latest changes from origin for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub (Yarik174/Sally_sales)
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Ask me which repo: sales or mo.
Then run: `cd <repo_path> && git pull origin $(git branch --show-current)`

If there are local uncommitted changes, warn me and ask whether to stash first.
Show the result.
