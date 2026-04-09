---
name: linear
description: >-
  Управление задачами в Linear для Sales Engineer. Используй ВСЕГДА когда
  пользователь говорит: "linear", "задача", "задачи", "создай задачу", "статус задач",
  "что в работе", "отчёт по задачам", "заблокировано", "закрой проект", "новая кампания",
  "new campaign", "weekly report", "добавь таск", "обнови статус", "linear status",
  "покажи задачи", "что делать", "план работы", "трекер". Также при: "создай проект",
  "project", "issues", "blocked", "backlog", "triage".
---

# Linear — Sales Engineer Task Hub

Управление задачами sales-команды OnSocial/Sally.
Один workspace: **Getsally** (linear-getsally MCP).

## Язык

Общение на русском. Issues и комментарии в Linear — на английском.

## Инструменты

Все операции через `mcp__linear-getsally__*`:

| Tool | Когда |
|------|-------|
| `linear_list_projects` | Список проектов |
| `linear_get_project` | Детали проекта |
| `linear_create_project_with_issues` | Создать проект + issues атомарно |
| `linear_search_issues` | Поиск issues |
| `linear_search_issues_by_identifier` | Найти по GET-123 |
| `linear_create_issue` | Создать одну задачу |
| `linear_create_issues` | Создать несколько задач |
| `linear_bulk_update_issues` | Bulk update (статус, приоритет) |
| `linear_delete_issue` | Удалить задачу |
| `linear_get_teams` | Список команд и статусов |
| `linear_get_user` | Текущий пользователь |

**Workspace constants:**
- Team ID: `30338bf7-a6ea-4d20-a1c2-e2a5d94db079` (Getsally)
- OnSocial Project ID: `40777ae1-c4f3-42fb-940b-5958febc4ac6`

## Шаг 0: Auto-Discovery (первый запуск)

Если `references/workspace-state.md` не существует:
1. `linear_get_teams` — получи статусы и labels
2. `linear_list_projects` — список проектов
3. `linear_get_user` — текущий пользователь
4. Сохрани в `references/workspace-state.md`

Если файл есть — читай оттуда.

## Команды

### `new <template> <name>` — Создать проект из шаблона

1. Прочитай `references/templates.md`
2. Покажи план: название, issues, структура
3. Дождись подтверждения
4. Создай через `linear_create_project_with_issues`
5. Покажи ссылку на проект и список issues

**Шаблоны:** `campaign`, `segment`, `deliverability`, `infra`, `weekly-ops`, `sequence`

### `status` — Dashboard

1. `linear_list_projects`
2. `linear_search_issues` с фильтром по teamId
3. Сгруппируй по статусу

```
## OnSocial

### GET-20: IMAGENCY v5 — finalize and launch [In Progress]
### GET-21: Write SOCCOM email sequence [Todo]
...
```

### `add <title>` — Создать задачу

Пользователь часто говорит голосом — осмысли input.

**Шаг 1 — Parse:**
- Определи тип: feature, bug, ops, research
- Извлеки суть и ожидаемый результат

**Шаг 2 — Structure:**
- **Title** — английский, action-oriented (Build X, Fix Y, Run Z)
- **Description** — Goal + конкретные шаги/deliverables
- **Project** — по умолчанию OnSocial (`40777ae1-c4f3-42fb-940b-5958febc4ac6`)

**Шаг 3 — Confirm:**
Покажи пользователю перед созданием:
```
Issue: "Run SOCCOM pipeline — Social Commerce platforms"
Project: OnSocial

Goal: Gather SOCCOM leads via universal pipeline using v4 filters.
Steps: Apollo keyword search → Findymail enrichment → dedup/blacklist → SmartLead upload
```
Дождись подтверждения → `linear_create_issue`

**Не делай research** для операционных задач ("загрузи лидов", "запусти пайплайн").

### `update <identifier> <status>` — Обновить статус

1. `linear_search_issues_by_identifier` → найди issue
2. Маппинг: `todo` → Todo, `wip/start` → In Progress, `done` → Done
3. `linear_bulk_update_issues` с нужным stateId

State IDs (Getsally):
- Backlog: `cf577c9f-3755-479b-b470-03519746184a`
- Todo: `16512d7a-f933-4dfd-b244-3757e30ade26`
- In Progress: `19d8dcf4-dcab-490c-9b56-c03905d27a06`
- Done: `344a7a00-7d04-4f4b-af24-d135040efaa9`
- Canceled: `868476e5-b045-43e3-b33d-c40c1bae952e`

### `report` — Недельный отчёт

1. `linear_search_issues` — все issues команды
2. Сгруппируй: Done / In Progress / Blocked / New
3. Короткий markdown

### `close <project>` — Закрыть проект

1. `linear_list_projects` — найди проект
2. `linear_search_issues` — все issues проекта
3. Покажи summary: сколько Done, сколько открытых
4. Дождись подтверждения
5. `linear_bulk_update_issues` — закрой все в Done/Canceled

### `search <query>` — Поиск

`linear_search_issues` с query параметром.

### `blocked` — Заблокированные задачи

`linear_search_issues` → filter states: ["Blocked"]

## Правила

- Не создавай issues/projects без подтверждения пользователя
- Issues и descriptions — на английском
- При ошибке API — покажи ошибку, не молчи
- Используй ТОЛЬКО `mcp__linear-getsally__*` tools — никаких других Linear MCP
