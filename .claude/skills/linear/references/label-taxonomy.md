# Label Taxonomy — Sales Engineer Linear

## Type Labels (обязательно, одна на issue)

| Label | Цвет | Описание | Примеры задач |
|-------|------|----------|---------------|
| `pipeline` | Blue | Шаги лидген-пайплайна | gather, dedup, blacklist, scrape, classify, verify, export, enrich |
| `campaign` | Green | Управление кампаниями | create campaign, upload leads, launch, monitor, pause |
| `sequence` | Purple | Email-копирайтинг | write sequences, review copy, A/B variants, social proof |
| `infra` | Red | Инфраструктура и деливерабилити | deploy, health check, spam report, warmup, inbox placement, domain |
| `research` | Yellow | Исследование рынка/сегментов | ICP analysis, competitor research, TAM, market sizing, platform eval |
| `ops` | Gray | Операционные задачи | blacklist sync, data cleanup, sheets, CSV, reporting, exclusion lists |
| `bug` | Red (dark) | Баги и ошибки | fix script, broken sync, API error, data corruption |

## Tool Labels (опционально, уточняющий)

| Label | Описание |
|-------|----------|
| `smartlead` | SmartLead campaigns, leads, sequences |
| `apollo` | Apollo search, filters, contacts |
| `clay` | Clay lookalike, enrichment |
| `findymail` | Findymail email verification |
| `instantly` | Instantly inbox tests, warmup, deliverability |
| `getsales` | GetSales LinkedIn outreach |
| `hetzner` | Server infrastructure |

## Segment Labels (опционально, привязка к ICP-сегменту)

| Label | Описание |
|-------|----------|
| `IMAGENCY` | IM-First Agencies |
| `INFPLAT` | Influencer Platforms (SaaS) |
| `AFFPERF` | Affiliate & Performance Networks |
| `SOCIAL-COMMERCE` | Social Commerce Platforms |

## Statuses

Рекомендуемый набор для команды:

| Status | Категория | Описание |
|--------|-----------|----------|
| Triage | Triage | Новые задачи, не разобранные |
| Todo | Backlog | Разобрано, готово к работе |
| In Progress | Started | В активной работе |
| Blocked | Started | Заблокировано внешней зависимостью |
| Done | Completed | Завершено |
| Canceled | Canceled | Отменено (не актуально) |

## Priority Mapping

| Linear Priority | Когда ставить |
|----------------|---------------|
| Urgent (1) | Production down, data loss, campaign stuck mid-launch |
| High (2) | Bug affecting active campaign, deliverability issue, deadline this week |
| Medium (3) | New campaign step, sequence writing, planned infra work |
| Low (4) | Research, docs update, nice-to-have improvements |
| No priority (0) | Triage — ещё не оценено |

## Auto-Triage Rules

Ключевые слова в title → автоматическое предложение labels:

```
pipeline|gather|dedup|scrape|classify|verify|export → type:pipeline
campaign|launch|activate|upload leads|monitor       → type:campaign
sequence|email|copy|A/B|variant|draft               → type:sequence
deploy|server|backend|health|webhook|docker          → type:infra
spam|deliverability|warmup|inbox|domain age          → type:infra + tool:instantly
research|ICP|TAM|competitor|market|analyze           → type:research
blacklist|sync|exclusion|CRM|sheets|csv              → type:ops
bug|fix|broken|error|fail|crash                      → type:bug

apollo|filter|contacts|people search                 → tool:apollo
clay|lookalike|enrich                                → tool:clay
findymail|verify email                               → tool:findymail
smartlead|campaign|lead upload                       → tool:smartlead
instantly|inbox test|warmup                          → tool:instantly
getsales|linkedin                                    → tool:getsales
hetzner|server|deploy                                → tool:hetzner

imagency|im-first|im agency                         → segment:IMAGENCY
infplat|influencer platform|saas                     → segment:INFPLAT
affperf|affiliate|performance                        → segment:AFFPERF
social commerce|social-commerce                      → segment:SOCIAL-COMMERCE
```

## Naming Conventions

- **Issue titles:** English, imperative form, concise
  - Good: `Fix blacklist sync script timeout`
  - Bad: `Нужно починить скрипт блеклиста который падает по таймауту`

- **Descriptions:** English, 1-3 sentences max. Link to relevant files/URLs.

- **Comments:** English for work discussion, Russian OK for internal notes.

- **Project names:** `[SEGMENT] [VERSION] [TYPE]` or `[TYPE]: [DESCRIPTION]`
  - `IMAGENCY v6 Campaign`
  - `Deliverability Audit 2026-04`
  - `Infra: Migrate Instantly MCP`
  - `Weekly Ops W15 2026`
