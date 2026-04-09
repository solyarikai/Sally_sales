---
name: git-sync
description: "Полная git-синхронизация sales_engineer + magnum-opus (сабмодуль). Статус, commit, push, pull, ветки, мердж, PR — всё с учётом сабмодуля. Используй когда: \"синкани\", \"git sync\", \"обнови репо\", \"git-sync\", \"статус репо\", \"запушь всё\", \"sync repos\", \"что с гитом\"."
---

# /git-sync — полная git-синхронизация sales_engineer + magnum-opus

## Репозитории

| Репо | Путь | Remote |
|------|------|--------|
| sales_engineer | `/Users/user/sales_engineer` | GitHub (origin) |
| magnum-opus | `/Users/user/sales_engineer/magnum-opus` | GitLab SSH (origin) — **САБМОДУЛЬ** |

---

## Шаг 1 — Полный статус обоих репо

Выполни параллельно:

```bash
# magnum-opus
cd /Users/user/sales_engineer/magnum-opus && \
  echo "branch: $(git branch --show-current)" && \
  git status --short && \
  git log --oneline -3 && \
  git rev-list --left-right --count origin/$(git branch --show-current)...HEAD 2>/dev/null

# sales_engineer
cd /Users/user/sales_engineer && \
  echo "branch: $(git branch --show-current)" && \
  git status --short && \
  git submodule status && \
  git log --oneline -3 && \
  git rev-list --left-right --count origin/$(git branch --show-current)...HEAD 2>/dev/null
```

Выведи:
```
magnum-opus (GitLab):
  Branch: main | Dirty: 3M 1U | Ahead: +2 | Last: abc1234 some message

sales_engineer (GitHub):
  Branch: main | Dirty: clean | Behind: -1 | Last: def5678 some message
  Submodule: magnum-opus @ abc1234 (dirty)
```

---

## Шаг 2 — Предложи действия

На основе статуса предложи конкретный план. Примеры:

**Если есть uncommitted changes:**
> Есть незакоммиченные изменения в magnum-opus (3 файла). Закоммитить и запушить?

**Если на ветке (не main):**
> magnum-opus на ветке `feature-x`. Запушить ветку? Создать MR/PR? Или сначала смерджить в main?

**Если ahead of remote:**
> magnum-opus впереди remote на 2 коммита. Запушить?

**Если behind remote:**
> sales_engineer отстаёт от remote на 1 коммит. Стянуть?

**Если всё чисто:**
> Оба репо синхронизированы, изменений нет.

**Жди ответа перед любым действием.**

---

## Шаг 3 — Выполни выбранное

### Commit + Push:
1. **magnum-opus ПЕРВЫМ** → `git add` → `git commit` → `git push origin <branch>`
2. **sales_engineer** → `git add` (включая submodule ref) → `git commit` → `git push origin <branch>`

### Pull:
1. `cd /Users/user/sales_engineer && git pull --recurse-submodules`

### Push ветки:
1. Запушить ветку: `git push -u origin <branch>`
2. Спросить: **"Создать PR/MR? Смерджить в main?"**

### Мердж ветки:
1. Спросить: **"В какую ветку мерджить?"** (обычно main)
2. `git checkout main && git merge <branch>`
3. Запушить main
4. Спросить: **"Удалить ветку `<branch>`?"**

### Создание PR/MR:
- GitHub (sales_engineer): `gh pr create`
- GitLab (magnum-opus): показать URL для создания MR вручную

---

## Шаг 4 — Отчёт

```
Git Sync:
  magnum-opus: [что сделано] (GitLab)
  sales_engineer: [что сделано] (GitHub)
```

---

## Правила

- Сабмодуль (magnum-opus) коммитить/пушить ПЕРВЫМ
- НИКОГДА не rebase, force push, или менять историю без спроса
- Конфликты — показать, НЕ резолвить автоматически
- Если на ветке — СПРОСИТЬ про мердж/PR, не мерджить молча
- Commit messages на английском
