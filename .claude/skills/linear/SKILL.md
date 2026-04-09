---
name: linear
description: "Управление задачами в Linear для Sales Engineer. Используй ВСЕГДА когда пользователь говорит: \"linear\", \"задача\", \"задачи\", \"создай задачу\", \"статус задач\", \"что в работе\", \"отчёт по задачам\", \"заблокировано\", \"закрой проект\", \"новая кампания\", \"new campaign\", \"weekly report\", \"добавь таск\", \"обнови статус\", \"linear status\", \"покажи задачи\", \"что делать\", \"план работы\", \"трекер\", \"запиши в лайнер\". Также при: \"создай проект\", \"project\", \"issues\", \"blocked\", \"backlog\", \"triage\"."
---

# Linear — Sales Engineer Task Hub

Управление задачами sales-команды OnSocial/Sally.
Workspace: **Getsally** (linear-getsally MCP).

## Язык

Общение с пользователем на русском. Issues, descriptions, comments в Linear — на английском.

## Workspace Constants

```
Team ID:    30338bf7-a6ea-4d20-a1c2-e2a5d94db079 (Getsally)
Project ID: 40777ae1-c4f3-42fb-940b-5958febc4ac6 (OnSocial)
```

### State IDs

| State | ID | Type |
|-------|-----|------|
| Backlog | `cf577c9f-3755-479b-b470-03519746184a` | backlog |
| Todo | `16512d7a-f933-4dfd-b244-3757e30ade26` | unstarted |
| In Progress | `19d8dcf4-dcab-490c-9b56-c03905d27a06` | started |
| Done | `344a7a00-7d04-4f4b-af24-d135040efaa9` | completed |
| Canceled | `868476e5-b045-43e3-b33d-c40c1bae952e` | canceled |
| Duplicate | `0124a9c9-889b-489d-8912-daf4b6e396f9` | canceled |

### Label IDs

| Label | ID | Color |
|-------|-----|-------|
| Bug | `dc6214ba-919a-4aa9-80d8-e0d37635801b` | red |
| Improvement | `80b29d1e-aede-4f09-936f-0cdbc3d15e5a` | blue |
| Feature | `022014fe-d12d-41b3-ad7f-fdfb99c1c3f3` | purple |

### Priority

| Value | Meaning |
|-------|---------|
| 0 | No priority |
| 1 | Urgent |
| 2 | High |
| 3 | Medium |
| 4 | Low |

## MCP Tools

| Tool | Когда | Особенности |
|------|-------|-------------|
| `linear_create_issue` | Создать задачу | НЕ поддерживает projectId, labelIds, parentId — добавляй через bulk_update |
| `linear_bulk_update_issues` | Обновить статус, проект, приоритет | Принимает любые поля через update (stateId, projectId, labelIds, parentId, priority) |
| `linear_create_comment` | Добавить комментарий | issueId = UUID, не identifier |
| `linear_search_issues` | Фильтр по states, teamIds, priority | `query` параметр НЕ РАБОТАЕТ (GraphQL баг). Фильтруй по states. |
| `linear_search_issues_by_identifier` | Найти по GET-XX | Принимает массив identifiers |
| `linear_list_projects` | Список проектов | |
| `linear_get_project` | Детали проекта | |
| `linear_create_project_with_issues` | Создать проект + issues | Единственный способ bulk create issues |
| `linear_delete_issue` | Удалить задачу | |

## Известные баги MCP (workarounds)

1. **`create_issue` не принимает projectId/labelIds/parentId** — создай issue, затем `bulk_update_issues` чтобы добавить в проект и навесить labels.
2. **`create_issues` (bulk) — сломан** — GraphQL mutation неправильная (массив вместо single input). Используй `create_issue` в цикле.
3. **`search_issues` с query — ошибка** — `search` field не существует в `IssueFilter`. Используй фильтры: `states`, `teamIds`, `priority`, `assigneeIds`.
4. **`bulk_update_issues` schema неполная** — в схеме только stateId/assigneeId/priority, но handler прокидывает `args.update` напрямую в GraphQL. Поэтому `projectId`, `labelIds`, `parentId` тоже работают через update.

## Команды

### Создать задачу (add)

**Шаг 1 — Dedup check (ОБЯЗАТЕЛЬНО):**
```
linear_search_issues(states: ["Backlog", "Todo", "In Progress"], teamIds: ["30338bf7-..."])
```
Просмотри результаты на предмет похожих задач. Если нашлась — покажи пользователю и спроси: обновить или создать новую. НЕ создавай дубли.

**Шаг 2 — Parse:**
Пользователь часто говорит голосом — осмысли input.
- Определи тип: bug → label Bug, feature → label Feature, improvement → label Improvement
- Определи приоритет: urgent/blocker → 1, high → 2, medium → 3, low → 4
- Если задача содержит подзадачи — создай parent + sub-issues

**Шаг 3 — Structure:**
- **Title** — английский, action-oriented (Build X, Fix Y, Run Z, Write X)
- **Description** — Goal + конкретные deliverables

**Шаг 4 — Create + bind:**
```
1. linear_create_issue(title, description, teamId, priority)
2. linear_bulk_update_issues(
     issueIds: ["GET-XX"],
     update: {
       projectId: "40777ae1-c4f3-42fb-940b-5958febc4ac6",
       labelIds: ["dc6214ba-..."]   // if applicable
     }
   )
```

**Шаг 5 — Subtasks (если нужны):**
Для каждой подзадачи:
```
1. linear_create_issue(title, description, teamId)
2. linear_bulk_update_issues(
     issueIds: ["GET-YY"],
     update: {
       parentId: "<parent issue UUID>",
       projectId: "40777ae1-..."
     }
   )
```

### Создать несколько задач (batch add)

Когда пользователь даёт список задач (например, результаты сессии):
1. Dedup check — загрузи все открытые issues
2. Для каждой задачи: `create_issue` → `bulk_update_issues` (project + labels)
3. Если задачи связаны parent-child — сначала parent, потом children с parentId
4. В конце — summary таблица со всеми созданными issues

### Обновить статус (update)

Маппинг: `todo` → Todo, `wip/start` → In Progress, `done` → Done, `cancel` → Canceled
```
linear_search_issues_by_identifier(identifiers: ["GET-XX"])
→ получи UUID
linear_bulk_update_issues(issueIds: ["GET-XX"], update: {stateId: "..."})
```

### Добавить комментарий (comment)

Для обновлений по задаче без смены статуса:
```
linear_search_issues_by_identifier(identifiers: ["GET-XX"])
→ получи UUID (не identifier!)
linear_create_comment(issueId: "<UUID>", body: "Update: ...")
```

### Dashboard (status)

```
linear_search_issues(states: ["In Progress"], teamIds: ["30338bf7-..."])
linear_search_issues(states: ["Todo"], teamIds: ["30338bf7-..."])
linear_search_issues(states: ["Backlog"], teamIds: ["30338bf7-..."])
```
Покажи сгруппированно:
```
## In Progress
- GET-XX: Title [priority]

## Todo
- GET-YY: Title [priority]

## Backlog (last 10)
- GET-ZZ: Title
```

### Недельный отчёт (report)

```
linear_search_issues(states: ["Done"], teamIds: ["30338bf7-..."])
```
+ In Progress + Todo. Сгруппируй: Done this week / In Progress / Blocked / New.

### Закрыть проект (close)

1. `linear_search_issues` — все issues проекта
2. Покажи: сколько Done, сколько открытых
3. Дождись подтверждения
4. `linear_bulk_update_issues` — закрой все в Done/Canceled

### Поиск (search)

`search_issues` с `query` не работает. Вместо этого:
- По identifier: `linear_search_issues_by_identifier`
- По статусу: `linear_search_issues(states: [...])`
- По приоритету: `linear_search_issues(priority: N)`

## Правила

- ВСЕГДА привязывай issues к проекту OnSocial через bulk_update после создания
- ВСЕГДА проверяй дубли перед созданием
- Не создавай issues без подтверждения пользователя (кроме batch записи результатов сессии по просьбе)
- Issues и descriptions — на английском
- Ставь labels где применимо (Bug для фиксов, Feature для нового, Improvement для улучшений)
- При ошибке API — покажи ошибку, предложи workaround
- Используй ТОЛЬКО `mcp__linear-getsally__*` tools
