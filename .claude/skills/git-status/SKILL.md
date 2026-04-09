---
name: git-status
description: "Show git status for both repos at once. Используй когда: \"статус\", \"status\", \"что изменилось\", \"какие изменения\", \"git status\"."
---

# /git-status

## Язык

Всегда отвечай на русском языке.

Покажи статус ОБОИХ репо сразу. Не спрашивай — просто выполни:

```bash
echo "=== sales_engineer (GitHub) ==="
cd /Users/user/sales_engineer && git branch --show-current && git status --short

echo ""
echo "=== magnum-opus (GitLab) ==="
cd /Users/user/sales_engineer/magnum-opus && git branch --show-current && git status --short
```

Покажи: текущая ветка, изменённые файлы, ahead/behind от remote.
