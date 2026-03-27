---
name: project-manager
description: Создаёт структуру нового проекта, запускает скиллы по очереди и управляет MCP серверами. Используй когда пользователь говорит "новый проект", "создай проект", "начнём работу с клиентом", "добавь проект", или называет нового клиента в контексте аутрича.
---

# Project Manager

## Когда запускается

- "Новый проект [название]"
- "Начинаем работу с [клиент]"
- "Добавь проект"
- "Создай структуру для [клиент]"

---

## Шаг 1 — Создать структуру проекта

Создай папку `projects/[project-name]/` со следующими файлами:

```
projects/[project-name]/
├── README.md          ← главный файл проекта
├── analysis.md        ← заглушка, заполнит website-analysis
├── docs/
│   └── apollo-instruction.md   ← заглушка, заполнит apollo-search
└── starter-kit/
    ├── segmentation_prompt.md  ← заглушка
    ├── email_body_prompt.md    ← заглушка
    └── subject_line_prompt.md  ← заглушка
```

### Шаблон README.md

```markdown
# [Название проекта]

## Статус
active

## Описание
[Кратко: что продаёт клиент, 1-2 предложения]

## О компании
[Продукт, рынок, ключевые услуги]

## ICP — Идеальный клиент

### Сегменты
[Заполнить после анализа]

## Целевые сегменты
[Заполнить после анализа]

## Материалы
- `analysis.md` — анализ сайта
- `docs/apollo-instruction.md` — фильтры для поиска контактов в Apollo
- `starter-kit/segmentation_prompt.md` — классификация компаний для Crona
- `starter-kit/email_body_prompt.md` — шаблоны тел писем
- `starter-kit/subject_line_prompt.md` — шаблоны сабджектов

## Задачи
- [ ] Анализ сайта клиента
- [ ] Определить ICP — сегменты, ЛПР, триггеры
- [ ] Создать сегментационный промт для Crona
- [ ] Создать email body prompt
- [ ] Создать subject line prompt
- [ ] Подготовить инструкцию по фильтрам Apollo
- [ ] Найти контакты в Apollo → экспорт CSV
- [ ] Запустить Crona: сегментация + генерация писем
```

После создания структуры — добавь проект в `CLAUDE.md` в раздел **Активные проекты**.

---

## Шаг 2 — Запустить скиллы по очереди

После создания структуры запускай скиллы последовательно:

1. **`website-analysis`** → анализирует сайт клиента → сохраняет в `analysis.md`
2. **`apollo-search`** → генерирует фильтры Apollo → сохраняет в `docs/apollo-instruction.md`
3. **Apollo / UI / MCP** → экспорт компаний
4. **Crona** → фильтрация компаний по ICP
5. **Apollo / UI / MCP** → поиск людей только в filtered companies
6. **Clay / Findymail** → enrichment email
7. **Crona / Smartlead** → copy + отправка

Каждый следующий шаг запускай только после завершения предыдущего. Сообщай пользователю о переходе.

---

## Шаг 3 — MCP серверы

### Apollo MCP (`mcp/apollo-mcp/server.py`)

> ⚠️ Перед вызовами проверь, доступны ли `mcp__apollo__*` в текущем рантайме. Если нет — не выдумывай вызовы, а готовь инструкцию под UI/ручной запуск.

| Инструмент | Кредиты | Что делает |
|---|---|---|
| `search_organizations` | Уточнить перед запуском | Поиск компаний по индустрии, ключевым словам |
| `search_people` | Почти бесплатно по API calls | Поиск людей по должности, локации, компании |
| `enrich_person` | Платно | Email + полный профиль по имени + домену |
| `bulk_enrich_people` | Платно | До 10 человек за один запрос |
| `bulk_create_contacts` | Бесплатно | Импорт контактов в Apollo CRM |
| `export_contacts_csv` | Бесплатно | Выгрузка контактов в CSV |
| `add_to_sequence` | Бесплатно | Добавить контакты в email-последовательность |
| `view_api_usage` | Бесплатно | Проверить остаток кредитов |

**Флоу:**
1. компании → экспорт `Company Name + Website`
2. filtered companies возвращаются в Apollo
3. people search только внутри filtered companies
4. person enrich не делаем по умолчанию, если нет отдельной причины

---

### Crona MCP (`mcp/crona-mcp/server.py`)

> ⚠️ Перед вызовами проверь, доступны ли `mcp__crona__*` в текущем рантайме.

| Инструмент | Что делает |
|---|---|
| `create_project` | Создать проект в Crona |
| `upload_source_file` | Загрузить CSV из Apollo |
| `list_enricher_types` | Посмотреть доступные энричеры |
| `create_enricher` | Добавить шаг: сегментация, генерация письма, AI-вызов |
| `run_project` | Запустить обработку |
| `wait_for_project` | Дождаться завершения |
| `get_project_results` | Посмотреть результаты |
| `credits_balance` | Проверить баланс кредитов |

**Флоу:**
1. `create_project` → создать проект под клиента
2. `upload_source_file` → загрузить companies CSV
3. `create_enricher` → сегментация по `segmentation_prompt.md`
4. убрать `OTHER`, экспортировать filtered companies
5. после people/enrichment cleanup загрузить финальный people CSV
6. `create_enricher` → генерация email body по `email_body_prompt.md`
7. `create_enricher` → генерация subject line по `subject_line_prompt.md`
8. `run_project` + `wait_for_project` → запустить и дождаться
9. `get_project_results` → забрать результаты

---

### Прочие MCP

| MCP | Когда использовать |
|---|---|
| **Linear** | Создать задачи по чеклисту из README.md, обновить статус |
| **Notion** | Сохранить материалы, создать страницу проекта |
| **Transkriptor** | Транскрибировать звонки и встречи |

---

## Финал

После создания структуры скажи:
> "Проект [название] создан в `projects/[name]/`. Следующий шаг — анализ сайта. Дай ссылку на сайт клиента."
