---
name: Git Status
description: Show git status for both repos at once
invokable: true
---

Show git status for both repos in one view.

Run these commands and format the output clearly:

```
echo "=== sales_engineer (GitHub) ==="
cd /Users/user/sales_engineer && git branch --show-current && git status --short

echo ""
echo "=== magnum-opus (GitLab) ==="
cd /Users/user/sales_engineer/magnum-opus && git branch --show-current && git status --short
```

Show: current branch, modified/untracked files count, ahead/behind remote status.
