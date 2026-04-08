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

Полноценное управление задачами для sales-команды OnSocial/Sally.
Два Linear workspace: **SolYarik** (личный) и **Sally** (рабочий, linear-getsally).

## Язык

Общение на русском. Issues и комментарии в Linear — на английском.

## Инструменты

Два набора MCP tools:

| Набор | Prefix | Когда использовать |
|-------|--------|--------------------|
| Claude.ai Linear | `mcp__claude_ai_Linear__*` | Основной: CRUD issues/projects, documents, milestones, cycles, labels, attachments, `research` (AI-запросы) |
| linear-getsally | `mcp__linear-getsally__*` | Sally workspace: bulk ops, delete issues, resolve/unresolve comments, create project+issues атомарно |

**Правило выбора:** используй `claude_ai_Linear` по умолчанию. Переключайся на `linear-getsally` для:
- Bulk update/delete (несколько issues за раз)
- Atomic project creation (проект + issues одним вызовом)
- Resolve/unresolve комментариев

## Шаг 0: Auto-Discovery (первый запуск)

При первом использовании скилла:

1. Получи список команд: `mcp__claude_ai_Linear__list_teams`
2. Получи список статусов: `mcp__claude_ai_Linear__list_issue_statuses` (для каждой команды)
3. Получи список labels: `mcp__claude_ai_Linear__list_issue_labels`
4. Получи текущего пользователя: `mcp__claude_ai_Linear__get_user` (query: "me")
5. Получи список проектов: `mcp__claude_ai_Linear__list_projects`

Сохрани результаты в `references/workspace-state.md` для быстрого доступа в будущих сессиях.

Если `references/workspace-state.md` уже существует — прочитай его вместо API-вызовов. Обновляй файл раз в сессию если данные устарели.

## Шаг 1: Определи команду

Пользователь может сказать:
- `/linear new campaign IMAGENCY v6` → команда `new`, шаблон `campaign`
- `/linear status` → команда `status`
- `/linear add Fix blacklist sync` → команда `add`
- `/linear update ENG-42 done` → команда `update`
- `/linear report` → команда `report`
- `/linear close IMAGENCY v5` → команда `close`
- `/linear search deliverability` → команда `search`
- `/linear blocked` → команда `blocked`
- Свободная форма: "создай задачу на починку спам-репорта" → команда `add`

## Команды

### `new <template> <name>` — Создать проект из шаблона

1. Прочитай `references/templates.md` — найди нужный шаблон
2. Покажи пользователю план: название проекта, список issues, milestones
3. Дождись подтверждения
4. Создай проект через `mcp__linear-getsally__linear_create_project_with_issues` (атомарно)
5. Если нужны milestones — добавь через `mcp__claude_ai_Linear__save_milestone`
6. Если нужны labels — добавь через `mcp__claude_ai_Linear__save_issue`
7. Покажи результат: ссылку на проект, список созданных issues

**Доступные шаблоны:** `campaign`, `segment`, `deliverability`, `infra`, `weekly-ops`, `sequence`

Если шаблон не указан — спроси какой нужен, покажи список.

### `status` — Dashboard

1. Получи все проекты: `mcp__claude_ai_Linear__list_projects` (state: active)
2. Для каждого проекта получи issues: `mcp__claude_ai_Linear__list_issues` (project filter)
3. Сгруппируй по статусу (Todo / In Progress / Done / Blocked)
4. Покажи в формате:

```
## Active Projects

### IMAGENCY v5 Campaign (3/12 done)
  In Progress: Findymail enrichment, Sequence writing
  Blocked: SmartLead upload (waiting for deliverability check)
  Next: A/B variants

### Deliverability Audit Q2 (1/5 done)
  In Progress: Inbox placement test
  ...
```

### `add <title>` — Smart-создание issue

Пользователь часто надиктовывает задачи голосом — сырой, неструктурированный текст. Скилл должен осмыслить input и выдать чистую задачу.

**Шаг 1 — Parse intent:**
1. Определи тип: feature, bug, research, ops task, idea
2. Извлеки суть: что именно нужно сделать, какой результат ожидается
3. Если input слишком размытый — задай 1 уточняющий вопрос (не больше)

**Шаг 2 — Quick research (Exa):**
1. Сделай 1-2 запроса через `web_search_exa` или `get_code_context_exa` по ключевой теме
2. Найди: есть ли готовые решения, API, инструменты, best practices
3. Сожми findings в 2-3 bullet points для description

**Шаг 3 — Structure:**
1. **Title** — чистый, на английском, action-oriented (Build X, Fix Y, Research Z)
2. **Description** — 3 блока:
   - **Goal:** 1-2 предложения, что и зачем
   - **Research findings:** 2-3 bullets из Exa (API, tools, approaches)
   - **Scope:** конкретные deliverables или open questions
3. **Auto-triage:**
   - **Labels:** по ключевым словам (pipeline → `pipeline`, spam/deliverability → `infra`, sequence → `sequence`)
   - **Project:** по сегменту или текущему контексту
   - **Priority:** по срочности (bug/fix → High, research/idea → Low)

**Шаг 4 — Confirm:**
1. Покажи предложение пользователю:
   ```
   Issue: "Build LinkedIn Content Factory skill"
   Project: —
   Labels: feature
   Priority: Normal

   Goal: Auto-generate LinkedIn posts from templates/rules, optionally auto-publish
   Research:
   - LinkedIn API supports posting via /ugcPosts (OAuth2)
   - Popular formats: carousel (highest engagement), story-driven, contrarian
   - Tools: Taplio, AuthoredUp — но можно заменить Claude skill
   Scope: skill with format templates, tone rules, optional scheduling
   ```
2. Дождись подтверждения (или пользователь поправит)
3. Создай через `mcp__claude_ai_Linear__save_issue`

**Когда НЕ делать research:** если задача чисто операционная и конкретная ("загрузи лидов в SmartLead", "почини blacklist sync"). Research только для features, ideas, и research-type задач.

**Правила авто-triage (прочитай `references/label-taxonomy.md` для полного списка):**

| Ключевые слова в title | Type label | Tool label |
|------------------------|------------|------------|
| pipeline, gather, dedup, scrape, classify | `pipeline` | — |
| campaign, launch, activate, upload leads | `campaign` | `smartlead` |
| sequence, email, copy, A/B, variant | `sequence` | `smartlead` |
| deploy, server, backend, health, webhook | `infra` | — |
| spam, deliverability, warmup, inbox, domain | `infra` | `instantly` |
| research, ICP, TAM, competitor, market | `research` | — |
| blacklist, sync, exclusion, CRM | `ops` | — |
| bug, fix, broken, error, fail | `bug` | — |
| apollo, search, filter, contacts | `pipeline` | `apollo` |
| clay, lookalike, enrich | `pipeline` | `clay` |
| findymail, verify email | `pipeline` | `findymail` |
| getsales, linkedin | `pipeline` | `getsales` |
| sheets, csv, export, import | `ops` | — |

### `update <identifier> <status>` — Обновить статус

1. Найди issue по identifier (ENG-123) или по поисковому запросу
2. Если по запросу — покажи найденные, попроси выбрать
3. Маппинг статусов (пользователь говорит → Linear status):
   - `todo`, `надо` → Todo
   - `wip`, `в работе`, `start` → In Progress
   - `done`, `готово`, `закрыто` → Done
   - `blocked`, `заблокировано` → Blocked (если есть)
   - `triage` → Triage
4. Обнови через `mcp__claude_ai_Linear__save_issue`
5. Если пользователь добавил комментарий — сохрани через `mcp__claude_ai_Linear__save_comment`

### `report [weekly]` — Отчёт

1. Получи все issues обновлённые за последнюю неделю: `mcp__claude_ai_Linear__list_issues` (updatedAt: "-P7D")
2. Сгруппируй:
   - **Завершено:** issues перешедшие в Done
   - **В работе:** issues в In Progress
   - **Заблокировано:** issues в Blocked
   - **Новое:** issues созданные за неделю
3. Добавь метрики: всего issues, % завершения, velocity
4. Формат — краткий markdown, пригодный для отправки коллеге

```markdown
## Weekly Report: Apr 1-8, 2026

### Completed (5)
- [ENG-42] Findymail enrichment IMAGENCY v5
- [ENG-43] Blacklist sync — added 1,906 domains
...

### In Progress (3)
- [ENG-50] Sequence writing — Creative segment
...

### Blocked (1)
- [ENG-55] SmartLead upload — waiting for deliverability

### New (4)
- [ENG-60] Social Commerce segment research
...

**Velocity:** 5 issues/week | **Completion:** 62%
```

### `close <project>` — Закрыть проект

1. Найди проект по имени: `mcp__claude_ai_Linear__list_projects` (query)
2. Получи все issues проекта
3. Покажи summary: сколько Done, сколько ещё открытых
4. Если есть открытые — спроси: закрыть все или только Done?
5. Bulk-закрытие через `mcp__linear-getsally__linear_bulk_update_issues`
6. Обнови статус проекта через `mcp__claude_ai_Linear__save_project` (state: completed)

### `search <query>` — Поиск

1. Используй `mcp__claude_ai_Linear__list_issues` с query параметром
2. Или `mcp__claude_ai_Linear__research` для сложных запросов на естественном языке
3. Покажи результаты в компактном формате

### `blocked` — Заблокированные задачи

1. Получи issues со статусом Blocked (или аналог): `mcp__claude_ai_Linear__list_issues` (state: "Blocked")
2. Для каждой покажи: issue, проект, кто заблокирован, комментарий (если есть)
3. Предложи action: "Разблокировать ENG-55? Что изменилось?"

## Правила

- **Не создавай** issues/projects без подтверждения пользователя
- **Suggest, don't decide** — предлагай labels/priority/project, пользователь подтверждает
- **Issues на английском** — title и description пишутся на английском
- **Комментарии** — язык контекстуальный (английский для рабочих, русский если для себя)
- При ошибке API — покажи ошибку, предложи альтернативу (другой MCP набор)
- Если workspace-state.md устарел — обнови автоматически при следующем запуске
