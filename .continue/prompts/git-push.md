---
name: Git Push
description: Push changes to remote for sales_engineer (GitHub) or magnum-opus (GitLab)
invokable: true
---

Push the current branch to origin for the specified repo.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub (Yarik174/Sally_sales)
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus)

Ask me which repo: sales or mo.
Then run: `cd <repo_path> && git push origin $(git branch --show-current)`

If push fails with "no upstream", run with `-u` flag.
Show the result.
