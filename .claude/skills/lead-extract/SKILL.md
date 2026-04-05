---
name: lead-extract
description: >-
  Извлечение и обогащение контактов из Apollo, Clay, или CSV через скрипты
  в magnum-opus/scripts/sofia/. Отдельный шаг 0 из universal pipeline.
  Используй когда: "найди лиды", "extract leads", "собери контакты",
  "Apollo search", "Clay export", "обогати через FindyMail",
  "lead-extract", "найди компании", "поиск по Apollo".
---

# /lead-extract — извлечение контактов

## Скрипты

Все в `/Users/user/sales_engineer/magnum-opus/scripts/sofia/`:

| Скрипт | Что делает |
|--------|-----------|
| `onsocial_apollo_companies_search.js` | Поиск компаний через Apollo internal API (Puppeteer, бесплатно) |
| `onsocial_apollo_people_search.js` | Поиск людей/контактов через Apollo |
| `onsocial_apollo_scraper.js` | Скрейпинг данных из Apollo |
| `onsocial_clay_tam_export.js` | Экспорт из Clay (TAM) |
| `onsocial_clay_lookalike_export.js` | Clay lookalike поиск |
| `onsocial_clay_people_search.js` | Clay поиск людей |
| `onsocial_universal_pipeline.py` | Полный пайплайн (если нужен весь цикл — используй `/pipeline-run`) |

Новые скрипты создавать тоже здесь.

---

## Шаг 0 — Уточни что нужно

1. **Что ищем**: компании или людей?
2. **Источник**: Apollo (бесплатно), Clay (~$0.01/компания), или готовый CSV
3. **Фильтры**: keywords, гео, размер, индустрия
4. **Сегмент**: INFPLAT, IMAGENCY, AFFPERF, или кастомный
5. **Лимит**: сколько результатов

---

## Шаг 1 — Собери команду

### Apollo компании (бесплатно):
```bash
node onsocial_apollo_companies_search.js \
  --keywords "influencer marketing platform" \
  --locations "United Kingdom,France" \
  --sizes "5,50|51,200|201,500"
```

### Apollo люди:
```bash
node onsocial_apollo_people_search.js \
  --domains "impact.com,modash.io" \
  --titles "CEO,CTO,VP Marketing"
```

### Clay экспорт:
```bash
node onsocial_clay_tam_export.js \
  --keywords "influencer marketing" \
  --max-results 5000
```

### Или через universal pipeline (шаг 0 only):
```bash
python3 onsocial_universal_pipeline.py --project-id 42 --mode apollo \
  --filters '{"keyword_tags": ["influencer marketing"], "max_pages": 25}' \
  --dry-run
```

**Покажи команду → жди подтверждения.**

---

## Шаг 2 — Запуск и валидация

После запуска проверь:
- count > 0
- Обязательные поля есть (domain/company_name для компаний, name/linkedin для людей)
- Нет явного мусора

---

## Шаг 3 — Сохранение (Dual Save)

- **Локально**: `sofia/output/[PROJECT]_[TYPE]_[SEGMENT]_[DATE].csv`
- **Google Sheets**: `[PROJECT] | [TYPE] | [SEGMENT] — [DATE]`

---

## Правила

- `python3.11` локально, `python3` на Hetzner
- Blacklist-проверка перед любой загрузкой
- Новые скрипты → `magnum-opus/scripts/sofia/`
- Если нужен полный цикл (gather → smartlead) — используй `/pipeline-run`