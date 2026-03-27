---
name: apollo-search
description: Генерирует инструкцию по фильтрам Apollo для поиска контактов под конкретный проект. Используй когда пользователь говорит "подготовь инструкцию по Apollo", "что искать в Apollo", "как настроить фильтры", или когда готов анализ сайта проекта.
---

# Apollo Search Instruction (MCP)

## Инструкции

1. Читай `projects/[project]/analysis.md` и `projects/[project]/README.md`
2. Перед генерацией ОБЯЗАТЕЛЬНО читай:
   - `.claude/memory/feedback/enrichment_pipeline.md`
   - `.claude/memory/feedback/apollo_export_fields.md`
   - `.claude/memory/tools/apollo_lessons.md`
3. Сгенерируй инструкцию под актуальный workflow: сначала компании, потом Crona фильтрация, потом люди
4. Сохрани в `projects/[project]/docs/apollo-instruction.md`
5. Если `mcp__apollo__*` доступны в текущем рантайме, делай инструкцию совместимой с MCP
6. Если live Apollo MCP недоступен, делай инструкцию для Apollo UI/ручного запуска, но НЕ меняй сам workflow

> ⚠️ Источник истины по порядку шагов: `companies -> Crona -> people -> Clay`, а не прямой people-first export.

---

## Шаг 1 — Сначала компании, не люди

Сначала оцени и опиши company-level фильтры по сегментам:

- industry / keyword logic
- geographies
- employee ranges
- exclusions

На первом экспорте нужны только:

- `Company Name`
- `Website`

Не тянуть людей, email и person enrich на этом шаге.

---

## Шаг 2 — Crona фильтрует компании

После Apollo companies export инструкция должна вести в Crona:

1. upload companies CSV
2. `Scrape Website`
3. `Call AI` с project-specific segmentation prompt
4. убрать `OTHER`
5. экспортировать filtered companies

---

## Шаг 3 — Люди только после filtered companies

После Crona:

1. импортируй filtered companies обратно в Apollo
2. ищи людей только внутри этих компаний
3. опиши job titles / seniorities для каждого сегмента

---

## Параметры фильтров для инструкции

При генерации инструкции под проект заполни по сегментам:

### Компании
- company search logic
- keyword logic
- страны / регионы
- диапазон сотрудников

### Люди
- `titles` — должности ЛПР
- `seniorities` — уровни: c_suite, vp, director, owner, partner

### MCP-заметки
- если используешь people search через MCP, предпочитай `organization_ids` / imported company lists
- если нужен keyword filter на people search, используй `organization_keyword_tags`, НЕ `keywords`
- не закладывайся на Apollo enrich как обязательный шаг

### Поля для people export
- `First Name`
- `Last Name`
- `Position / Job Title`
- `Company Name`
- `Company Website`
- `Employees`
- `Location / Country`
- `LinkedIn` по возможности

Email enrichment уходит в Clay / Findymail после cleanup.

---

## После экспорта

Итоговый flow в инструкции должен выглядеть так:

```text
Apollo (companies only)
    ↓
Crona (filter companies)
    ↓
Apollo (people from filtered companies)
    ↓
Cleanup / dedupe / blacklist
    ↓
Clay / Findymail
    ↓
Crona / Smartlead
```
