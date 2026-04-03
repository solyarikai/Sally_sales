---
name: Git PR
description: Создать, посмотреть или замерджить Pull Request через gh CLI
invokable: true
---

Всегда отвечай на русском языке.

Управление Pull Requests через gh CLI.

Repos:
- `sales` = `/Users/user/sales_engineer` → GitHub `https://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@github.com/solyarikai/Sally_sales.git`
- `mo` = `/Users/user/sales_engineer/magnum-opus` → GitLab (sally-saas/magnum-opus) — gh не работает, только через GitLab UI

Спроси действие: create, list, merge, status, view.

**create:**
1. Спроси: sales или mo?
2. `cd <repo_path>`
3. Если есть изменения — авто-коммит + пуш
4. `gh pr create --title "<заголовок>" --body "<описание>"` — сгенерируй по диффу с main
5. Покажи результат

**list:** `gh pr list`
**merge:** `gh pr list` → спроси номер → `gh pr merge <номер> --merge`
**status:** `gh pr status`
**view:** спроси номер → `gh pr view <номер>`
