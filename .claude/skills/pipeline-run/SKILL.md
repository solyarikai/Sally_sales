---
name: pipeline-run
description: >-
  Запуск лидген-пайплайна через onsocial_universal_pipeline.py.
  12 шагов: gather → dedup → blacklist → prefilter → scrape → classify → verify → export → people → findymail → sequences → smartlead.
  Используй когда: "запусти пайплайн", "pipeline", "прогони лиды", "enrichment",
  "обогати контакты", "залей в SmartLead", "загрузи лиды", "pipeline-run",
  "universal pipeline", "собери компании".
---

# /pipeline-run — Universal Lead Generation Pipeline

## Поведение скилла

### Если пользователь НЕ предоставил данных (просто `/pipeline-run` или "запусти пайплайн")

Покажи обзор и помоги выбрать вариант:

```
Пайплайн поддерживает 4 способа поиска компаний:

1. Apollo (--mode apollo) — БЕСПЛАТНО
   Поиск по keyword_tags через внутренний API Apollo (Puppeteer).
   Нужно: keyword_tags + locations + sizes
   Когда: у тебя есть точные ключевые слова для поиска компаний

2. Clay Keywords (--mode keywords) — ~$0.01/компания
   Прямой поиск по description_keywords через Clay.
   Нужно: description_keywords + industries
   Когда: ищешь по описаниям компаний, а не по тегам Apollo

3. Clay ICP (--mode structured / --mode natural) — ~$0.01/компания
   AI (Gemini) конвертирует текстовое описание ICP в Clay фильтры.
   Для structured: сегмент должен быть в БД (kb_segments)
   Для natural: передай ICP текстом через --filters
   Когда: первый поиск, когда фильтры ещё не определены

4. Lookalike (--mode lookalike) — ~$0.01/компания
   Reverse-engineering фильтров по примерам доменов.
   Нужно: 3-10 доменов компаний-примеров
   Когда: знаешь хорошие компании, хочешь найти похожие

Дополнительные режимы:
- Expand (--mode expand) — клон предыдущего рана с изменёнными параметрами
- Resume (--from-step) — продолжить с любого шага
- Re-analyze (--re-analyze) — пересчитать классификацию с новым промптом

Для всех режимов (кроме lookalike/expand) нужен --segment.
Рекомендуется использовать --filter-file (JSON с company + people фильтрами).

Какой вариант подходит? Что ты хочешь найти?
```

Затем задавай уточняющие вопросы в зависимости от выбора:
- Какой проект? (узнай project-id из БД если не знаешь)
- Какой сегмент?
- Есть ли готовый filter-file или нужно создать?
- Есть ли файл с фильтрами (типа apollo-filters-v4.md), из которого сгенерировать JSON?

### Если пользователь предоставил данные

Переходи сразу к **Фаза 1**. Но перед запуском обязательно покажи:
- Какой filter-file будет использован (путь)
- Откуда взяты фильтры (из какого файла сгенерированы, или готовый JSON)
- Краткое содержание: сколько keyword_tags, какой segment, какие sizes/locations
- Какие ещё есть варианты источников фильтров:
  - Готовый filter-file в `magnum-opus/scripts/sofia/filters/` (если есть)
  - Документ с фильтрами в `sofia/projects/` (типа apollo-filters-v4.md) — сгенерировать JSON
  - Фильтры из БД (`kb_segments`) — если сегмент настроен в бэкенде
  - Inline через `--filters` — задать вручную
  - Создать новый filter-file с нуля — спросить параметры у пользователя

Пользователь должен видеть источник данных и альтернативы, затем подтвердить перед запуском.

---

## Фаза 1 — Определи параметры

Определи из контекста или спроси:

| Параметр | Обязательный | Описание |
|----------|-------------|----------|
| `--project-id` | да | ID проекта из БД |
| `--mode` | да | `structured`, `natural`, `keywords`, `apollo`, `lookalike`, `expand` |
| `--segment` | да (кроме expand/lookalike) | Slug сегмента (любой) |
| `--filter-file` | рекомендуется | JSON файл с company_filters + people_filters + segment |
| `--filters` | если нет filter-file | JSON с фильтрами (inline, мерджится поверх filter-file) |
| `--examples` | для lookalike | Домены через запятую |
| `--base-run` | для expand | ID рана для клонирования |
| `--from-step` | нет | Продолжить с шага: `start`, `people`, `findymail`, `sequences`, `smartlead` |
| `--run-id` | нет | Продолжить существующий ран |
| `--apollo-csv` | нет | Импорт контактов из Apollo CSV |

### Источники фильтров по mode

| Mode | Откуда фильтры | `--filter-file` | `--filters` inline |
|------|----------------|-----------------|-------------------|
| apollo | filter-file и/или inline | ✅ company_filters мерджится | ✅ поверх файла |
| keywords | filter-file и/или inline | ✅ company_filters мерджится | ✅ поверх файла |
| natural | filter-file и/или inline | ✅ company_filters мерджится | ✅ поверх файла |
| structured | БД (kb_segments) | не нужен | не нужен |
| lookalike | из примеров доменов | не нужен | не нужен |
| expand | из base run | не нужен | `--override` для изменений |

### People filters (для step 9 — People Search)

People filters (titles, seniorities для Apollo People Search) берутся из:
1. `--filter-file` → `people_filters` (приоритет)
2. Дефолт: CEO, Founder, Co-Founder, CTO, COO, Head of Product

Если пользователь предоставляет файл с фильтрами (типа apollo-filters-v4.md), создай из него JSON filter-file, включающий и company_filters, и people_filters.

---

## Фаза 2 — Покажи команду и жди подтверждения

Собери полную команду. Шаблоны:

```bash
# Filter-file (рекомендуемый)
python3 universal_pipeline.py --project-id <ID> --mode apollo \
  --filter-file path/to/filters.json

# Apollo inline
python3 universal_pipeline.py --project-id <ID> --mode apollo --segment <SEGMENT> \
  --filters '{"keyword_tags": [...], "locations": [...], "sizes": [...], "max_pages": 25}'

# Clay Keywords
python3 universal_pipeline.py --project-id <ID> --mode keywords --segment <SEGMENT> \
  --filters '{"description_keywords": [...], "industries": [...], "max_results": 5000}'

# Structured (из БД)
python3 universal_pipeline.py --project-id <ID> --mode structured --segment <SEGMENT>

# Lookalike
python3 universal_pipeline.py --project-id <ID> --mode lookalike \
  --examples "domain1.com,domain2.io"

# Resume
python3 universal_pipeline.py --project-id <ID> --from-step <STEP>

# Re-analyze
python3 universal_pipeline.py --project-id <ID> --re-analyze --run-id <RUN_ID> \
  --prompt-file new_prompt.txt

# Dry run (любой mode)
python3 universal_pipeline.py --project-id <ID> --mode <MODE> --dry-run \
  --filter-file path/to/filters.json
```

**Покажи собранную команду. Жди подтверждения перед запуском.**

Рекомендуй `--dry-run` для первого запуска с новыми фильтрами.

---

## Фаза 3 — Запуск и мониторинг

### Инфраструктура

- Скрипт: `/Users/user/sales_engineer/magnum-opus/scripts/sofia/onsocial_universal_pipeline.py`
- Выполняется на **Hetzner** (`ssh hetzner`), путь `~/magnum-opus-project/repo`
- Backend должен работать на localhost:8000
- Env: `set -a && source .env && set +a` перед запуском
- Python: `python3` (на Hetzner), `python3.11` (локально)

### Перед запуском проверь

1. Backend работает: `ssh hetzner "curl -s localhost:8000/health"`
2. SCP filter-file на Hetzner (новые файлы — прямой SCP):
   ```bash
   ssh hetzner "mkdir -p ~/magnum-opus-project/repo/scripts/sofia/filters"
   scp magnum-opus/scripts/sofia/filters/<filter>.json hetzner:~/magnum-opus-project/repo/scripts/sofia/filters/
   ```
3. SCP скрипт на Hetzner (файлы root — через docker workaround):
   ```bash
   scp magnum-opus/scripts/sofia/onsocial_universal_pipeline.py hetzner:/tmp/onsocial_universal_pipeline.py
   ssh hetzner "docker run --rm -v /home/leadokol/magnum-opus-project/repo/scripts/sofia:/target -v /tmp:/src alpine cp /src/onsocial_universal_pipeline.py /target/onsocial_universal_pipeline.py"
   ```
   Файлы на Hetzner принадлежат root — обычный SCP/cp не работает. Docker mount обходит это.

### Чекпоинты (★ CP)

Скрипт останавливается в 3 местах и ждёт одобрения:

| Чекпоинт | После шага | Что проверять |
|----------|-----------|---------------|
| ★ CP1 | Шаг 2 (Blacklist) | Правильный проект? Правильный scope? |
| ★ CP2 | Шаг 5 (Classify) | Список компаний корректный? Accuracy > 90%? |
| ★ CP3 | Шаг 9 (People Search) | Одобряешь расходы на FindyMail enrichment? |

### 12 шагов пайплайна

```
Шаг 0:  GATHER          [скрипт]     — поиск компаний (Clay/Apollo/Lookalike)
Шаг 1:  DEDUP           [backend]    — убрать дубли из предыдущих ранов
Шаг 2:  BLACKLIST       [backend]    — проверка по чёрному списку ★ CP1
Шаг 3:  PREFILTER       [backend]    — отсев мусора
Шаг 4:  SCRAPE          [backend]    — скрейпинг сайтов
Шаг 5:  CLASSIFY        [backend]    — AI классификация (GPT-4o-mini) ★ CP2
Шаг 6:  VERIFY          [ручной]     — проверка accuracy
Шаг 7:  ADJUST PROMPT   [ручной]     — правка промпта если accuracy < 90%
Шаг 8:  EXPORT TARGETS  [скрипт]     — выгрузка таргетов
Шаг 9:  PEOPLE SEARCH   [скрипт]     — поиск людей через Apollo (Puppeteer, бесплатно) ★ CP3
Шаг 10: FINDYMAIL       [скрипт]     — email enrichment ($0.01/email)
Шаг 11: SEQUENCES       [скрипт]     — загрузка email-секвенций
Шаг 12: SMARTLEAD       [скрипт]     — создание кампании, загрузка лидов
```

---

## Фаза 4 — Отчёт

```
Pipeline завершён.
Run ID: [id]
Компаний найдено: X → после dedup: Y → после classify: Z
Контактов: N → с email: M
Кампания SmartLead: [название] (ID: [id])
Google Sheets: [ссылка]
GetSales CSV: [путь] (контакты без email)
```

---

## Filter-file формат (JSON)

```json
{
  "segment": "<SEGMENT_SLUG>",
  "company_filters": {
    "keyword_tags": ["keyword1", "keyword2"],
    "locations": ["Country1", "Country2"],
    "sizes": ["10,50", "51,200"],
    "excluded_keywords": ["exclude1", "exclude2"],
    "max_pages": 25
  },
  "people_filters": {
    "titles": ["Title1", "Title2"],
    "seniorities": ["founder", "c_suite", "vp", "director", "owner", "head", "partner"],
    "excluded_titles": ["ExcludedTitle1", "ExcludedTitle2"]
  }
}
```

- `segment` — используется если не передан `--segment` (CLI имеет приоритет)
- `company_filters` — для step 0 (gather). Ключи зависят от mode:
  - Apollo: `keyword_tags`, `locations` **(обязательно, минимум 1 страна)**, `sizes`, `excluded_keywords`, `max_pages`
  - Keywords: `description_keywords`, `description_keywords_exclude`, `industries`, `max_results`
  - Natural: `icp_text` или любые Clay-фильтры
- `people_filters` — для step 9 (people search): `titles`, `seniorities`, `excluded_titles`
- `--filters` (inline) мерджится поверх `company_filters` из файла
- Файлы хранятся в `magnum-opus/scripts/sofia/filters/`
- Именование: `<project>_<segment>_<version>.json` (например `onsocial_imagency_v4.json`)
- Перед запуском — SCP на Hetzner: `scp filters/<file>.json hetzner:~/magnum-opus-project/repo/scripts/sofia/filters/`

---

## Правила

- **НИКОГДА не активировать кампании** в SmartLead — только вручную в UI
- **A/B варианты** email — только вручную в SmartLead UI
- **Dual Save**: CSV + Google Sheets (naming convention из project CLAUDE.md)
- Контакты без email → GetSales-ready CSV в `sofia/get_sales_hub/{dd_mm}/`
- Если скрипт упал — дебажь, не переключайся на другой подход
- `--dry-run` для проверки параметров без API вызовов
- Backend на Hetzner: `ssh hetzner`, путь `~/magnum-opus-project/repo`
