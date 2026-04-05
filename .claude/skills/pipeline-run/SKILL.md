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

## Скрипт

`/Users/user/sales_engineer/magnum-opus/scripts/sofia/onsocial_universal_pipeline.py`

Выполняется на **Hetzner** (`ssh hetzner`). Backend должен работать на localhost:8000.
Env: `set -a && source .env && set +a` перед запуском.
Python: `python3` (на Hetzner), `python3.11` (локально).

---

## Шаг 0 — Определи параметры

Спроси или определи из контекста:

| Параметр | Обязательный | Описание |
|----------|-------------|----------|
| `--project-id` | да | ID проекта из БД (OnSocial = 42) |
| `--mode` | да | `structured`, `natural`, `keywords`, `apollo`, `lookalike`, `expand` |
| `--segment` | да (кроме expand/lookalike) | Slug сегмента (любой — не захардкожен) |
| `--filter-file` | рекомендуется | JSON файл с company_filters + people_filters + segment |
| `--filters` | для keywords/apollo (если нет filter-file) | JSON с фильтрами (inline, можно комбинировать с filter-file) |
| `--examples` | для lookalike | Домены через запятую |
| `--base-run` | для expand | ID рана для клонирования |
| `--from-step` | нет | Продолжить с шага: `start`, `people`, `findymail`, `sequences`, `smartlead` |
| `--run-id` | нет | Продолжить существующий ран |
| `--apollo-csv` | нет | Импорт контактов из Apollo CSV |

---

## Шаг 1 — Покажи команду запуска

Собери полную команду и покажи пользователю. Примеры:

```bash
# Apollo с filter-file (рекомендуемый способ)
python3 universal_pipeline.py --project-id 42 --mode apollo \
  --filter-file filters/imagency_v4.json

# Apollo с inline filters
python3 universal_pipeline.py --project-id 42 --mode apollo --segment IM_FIRST_AGENCIES \
  --filters '{"keyword_tags": ["influencer marketing platform"],
              "locations": ["United Kingdom", "France"],
              "sizes": ["10,50", "51,200", "201,500"],
              "max_pages": 25}'

# Clay Keywords
python3 universal_pipeline.py --project-id 42 --mode keywords --segment MY_SEGMENT \
  --filters '{"description_keywords": ["influencer marketing platform"],
              "description_keywords_exclude": ["recruitment"],
              "industries": ["Computer Software"],
              "minimum_member_count": 5, "maximum_member_count": 5000,
              "max_results": 5000}'

# Lookalike
python3 universal_pipeline.py --project-id 42 --mode lookalike \
  --examples "impact.com,modash.io"

# Resume с шага people
python3 universal_pipeline.py --project-id 42 --from-step people

# Re-analyze с новым промптом
python3 universal_pipeline.py --project-id 42 --re-analyze --run-id 198 --prompt-file new_prompt.txt
```

**Жди подтверждения перед запуском.**

---

## Шаг 2 — Запуск и мониторинг

Скрипт имеет 3 чекпоинта (★ CP) где ждёт одобрения:

| Чекпоинт | После шага | Что проверять |
|----------|-----------|---------------|
| ★ CP1 | Шаг 2 (Blacklist) | Правильный проект? Правильный scope? |
| ★ CP2 | Шаг 5 (Classify) | Список компаний корректный? Accuracy > 90%? |
| ★ CP3 | Шаг 9 (People Search) | Одобряешь расходы на FindyMail enrichment? |

### 12 шагов пайплайна:

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
Шаг 9:  PEOPLE SEARCH   [скрипт]     — поиск людей через Apollo ★ CP3
Шаг 10: FINDYMAIL       [скрипт]     — email enrichment ($0.01/email)
Шаг 11: SEQUENCES       [скрипт]     — загрузка email-секвенций
Шаг 12: SMARTLEAD       [скрипт]     — создание кампании, загрузка лидов
```

---

## Шаг 3 — Отчёт

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

## Правила

- **НИКОГДА не активировать кампании** в SmartLead — только вручную в UI
- **A/B варианты** email — только вручную в SmartLead UI
- **Dual Save**: CSV + Google Sheets (naming convention из project CLAUDE.md)
- Контакты без email → GetSales-ready CSV в `sofia/get_sales_hub/{dd_mm}/`
- Если скрипт упал — дебажь, не переключайся на другой подход
- `--dry-run` для проверки параметров без API вызовов
- Новые скрипты сохранять в `magnum-opus/scripts/sofia/`
- Backend на Hetzner: `ssh hetzner`, путь `~/magnum-opus-project/repo`
