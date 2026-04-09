---
name: git-pr
description: "Создать, посмотреть, замерджить Pull Request через gh CLI. Используй когда: \"пр\", \"pr\", \"pull request\", \"создай пр\", \"замерджи\", \"список пр\", \"статус пр\"."
---

# /git-pr

## Язык

Всегда отвечай на русском языке.

## Repos

| Alias | Path | Remote |
|-------|------|--------|
| `sales` | `/Users/user/sales_engineer` | GitHub `https://$GITHUB_TOKEN@github.com/solyarikai/Sally_sales.git` |
| `mo` | `/Users/user/sales_engineer/magnum-opus` | GitLab (sally-saas/magnum-opus) — PR через GitLab, не gh |

## Действия

Спроси: какое действие?

### create — создать PR
1. Спроси: sales или mo?
2. `cd <repo_path>`
3. Если есть незакоммиченные изменения — авто-коммит (как в /git-push)
4. `git push origin $(git branch --show-current)` (с `-u` если нужно)
5. `gh pr create --title "<заголовок>" --body "<описание>"` — сгенерируй заголовок и описание по диффу с main
6. Покажи результат

### list — список PR
1. `cd <repo_path> && gh pr list`
2. Покажи результат

### merge — замерджить PR
1. `cd <repo_path> && gh pr list`
2. Спроси какой PR замерджить (по номеру)
3. `gh pr merge <номер> --merge`
4. Покажи результат

### status — статус проверок
1. `cd <repo_path> && gh pr status`
2. Покажи результат

### view — посмотреть конкретный PR
1. Спроси номер PR
2. `cd <repo_path> && gh pr view <номер>`
3. Покажи результат

## Правила

- Для sales — используй `gh` CLI
- Для mo (GitLab) — `gh` не работает, предупреди что нужно через GitLab UI или `glab` CLI
- Заголовок PR: макс 70 символов, английский
- Описание: краткое, по диффу
