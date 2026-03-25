# Урок 4 — Строим пайплайн с нуля для нового проекта

> Контекст: мы уже изучили `pipeline_onsocial.py` (уроки 1-3) и реализовали улучшения (prompt versioning, --validate, Opus fallback, CSV export, run protocol). Теперь — как запустить всё это для **нового** проекта, не копипастя код.

---

## Что значит "с нуля"

Для нового проекта нужно:

1. **Понять ICP** — кого ищем, по каким сигналам
2. **Настроить Apollo** — какие фильтры, сколько компаний
3. **Написать classification prompt** — под конкретный продукт
4. **Создать конфиг** — пути, сегменты, ключевые слова
5. **Подключить к общей инфраструктуре** — shared website cache, та же логика шагов

Ключевой принцип: **один `pipeline.py` + N JSON-конфигов** вместо копипасты кода под каждый проект.

---

## Шаг 0 — Документируй ICP до написания кода

Прежде чем открывать редактор — ответь на 5 вопросов:

```
Кто наш идеальный клиент?
  → тип бизнеса, размер, регион

Какие сигналы на сайте говорят "это наш"?
  → слова, разделы, продукты, признаки

Что нас точно дисквалифицирует?
  → явные признаки "не наш" (без GPT)

На какие сегменты делим целевых?
  → 2-4 сегмента с чёткими критериями

Что делаем с пограничными случаями (OTHER)?
  → игнорируем? второй прогон?
```

Для OnSocial это заняло несколько недель итераций. Для нового проекта — запиши хотя бы черновик в `projects/[NAME]/README.md` перед тем как писать prompt.

---

## Шаг 1 — Структура файлов

```
magnum-opus/
├── state/
│   ├── onsocial/          ← уже есть
│   └── [newproject]/      ← создаём
│       ├── campaign_blacklist.json
│       ├── all_companies.json
│       ├── classifications.json
│       ├── targets.json
│       └── runs/
│
├── sofia/
│   ├── input/
│   │   └── [newproject]/  ← Apollo экспорты
│   ├── output/
│   │   └── [NewProject]/
│   │       ├── Leads/
│   │       ├── Targets/
│   │       ├── Import/
│   │       └── Archive/
│   └── scripts/
│       ├── pipeline_onsocial.py   ← референс
│       └── pipeline_[name].py     ← новый
```

Создаём папки заранее — это занимает 1 минуту и избавляет от ошибок в рантайме:

```python
STATE_DIR = REPO_DIR / "state" / "newproject"
STATE_DIR.mkdir(parents=True, exist_ok=True)
```

---

## Шаг 2 — Копируем скелет, меняем только конфиг

Не нужно писать с нуля весь пайплайн. Структура шагов 0-8 универсальна:

| Шаг | Что делает | Специфично для проекта? |
|-----|------------|------------------------|
| 0   | Load blacklist | ❌ нет |
| 1   | Load companies from input JSON | ✅ да — имена файлов |
| 2   | Dedup by domain | ❌ нет |
| 3   | Apply blacklist | ❌ нет |
| 4   | Deterministic filter | ✅ да — размер, индустрия |
| 5   | DNS check | ❌ нет |
| 6   | Scrape websites | ❌ нет |
| 7   | GPT classify | ✅ да — **промпт** |
| 8   | Output targets + CSV | ✅ да — имена сегментов |

Значит, при создании нового пайплайна меняем три вещи:
- **PATHS** — `STATE_DIR`, `INPUT_DIR`, `CSV_OUTPUT_DIR`
- **Фильтры в step4** — размер компании, индустрия
- **`CLASSIFICATION_PROMPT`** — полностью под новый ICP

Всё остальное — copy-paste из `pipeline_onsocial.py`.

---

## Шаг 3 — Пишем Classification Prompt

Это самая важная часть. Плохой промпт = плохие таргеты = деньги выброшены.

### Структура хорошего промпта

```
КОНТЕКСТ ПРОДУКТА
Кто мы, что продаём, кому это нужно.

СЕГМЕНТЫ (перечислить все, которые хотим)
SEGMENT_A: [критерии] — [примеры]
SEGMENT_B: [критерии] — [примеры]
OTHER: не подходит ни под один сегмент

ПРАВИЛА КЛАССИФИКАЦИИ
- Что делает компанию TARGET
- Что делает компанию OTHER
- Что делает компанию DISQUALIFIED (жёстко нет)

ФОРМАТ ОТВЕТА
SEGMENT_NAME | reasoning на 1 предложение
```

### Пример для OnSocial

```python
CLASSIFICATION_PROMPT = """
You are classifying marketing agencies and platforms for OnSocial — a platform
for managing influencer marketing campaigns.

SEGMENTS:
IM_FIRST_AGENCIES: Agencies where influencer marketing is PRIMARY service
  (not just one of 10 services). Look for: "influencer marketing agency",
  creator campaigns, UGC production, talent management.

INFLUENCER_PLATFORMS: SaaS/tech platforms for IM — marketplace, analytics,
  discovery tools, campaign management software.

AFFILIATE_PERFORMANCE: Performance marketing with creator/affiliate components —
  CPA networks, affiliate platforms with influencer programs.

OTHER: Doesn't fit above — full-service agencies where IM is minor,
  pure SEO/PPC, media buying, PR firms, publishers.

Company: {company_name}
Domain: {domain}
Website text: {website_text}

Respond: SEGMENT | one sentence reasoning
"""
```

### Ошибки при написании промпта

**1. Слишком широкие критерии** — всё попадает в цель:
```
❌ "любые маркетинговые агентства"
✅ "агентства где influencer marketing — основная услуга, не одна из 10"
```

**2. Нет примеров пограничных случаев**:
```
❌ не объяснять разницу IM_AGENCY vs FULL_SERVICE_AGENCY
✅ "Full-service agency that offers IM as one of many services → OTHER"
```

**3. Расплывчатый OTHER** — GPT не знает куда класть сомнительных:
```
❌ "не подходит" (без деталей)
✅ "OTHER: media publishers, tech companies using influencers internally,
   brands (not agencies), consulting firms"
```

---

## Шаг 4 — Deterministic фильтры (до GPT!)

Принцип **Layered Via Negativa**: убираем явную дичь ДЁШЕВО, до дорогого GPT-шага.

```python
def step4_filter(companies):
    result = []
    disqualified = []

    for c in companies:
        employees = c.get("employees", 0)
        industry = c.get("industry", "").lower()

        # Размер: слишком маленькие или слишком большие
        if employees < 10 or employees > 10000:
            c["disqualify_reason"] = f"size={employees}"
            disqualified.append(c)
            continue

        # Индустрия: явно не наши
        BAD_INDUSTRIES = ["staffing", "recruiting", "legal", "accounting",
                          "real estate", "insurance", "healthcare"]
        if any(bad in industry for bad in BAD_INDUSTRIES):
            c["disqualify_reason"] = f"industry={industry}"
            disqualified.append(c)
            continue

        result.append(c)

    print(f"  Filter: {len(companies)} → {len(result)} (disqualified {len(disqualified)})")
    return result, disqualified
```

**Правило**: каждый компания, отсеянная здесь — это ~$0.0003 сэкономлено на GPT. На 10,000 компаний — $3. Кажется мало, но если фильтры убирают 40% — это $120 на 100K компаний.

---

## Шаг 5 — Тестируем на малой выборке

Перед запуском на всей базе — всегда тест на 20-50 компаниях:

```bash
# Запуск только до step 4 (без GPT) — мгновенно, бесплатно
python pipeline_newproject.py --from-step 0 --step 4

# Смотрим сколько осталось после фильтров
cat state/newproject/normal.json | python -c "import json,sys; d=json.load(sys.stdin); print(len(d))"

# Тестовый прогон GPT на 20 компаниях
python pipeline_newproject.py --from-step 6 --limit 20

# Проверяем качество классификации
python pipeline_newproject.py --validate 20
```

`--validate 20` выведет 20 случайных таргетов с reasoning и preview сайта. Смотришь глазами — правильно ли GPT классифицирует. Если нет — правишь промпт, бампаешь `PROMPT_VERSION`.

---

## Шаг 6 — Итерация промпта

Схема итерации:

```
Запуск на 20 компаниях
  → --validate 20
    → видишь ошибки классификации
      → правишь промпт
        → бампаешь PROMPT_VERSION (v1 → v2)
          → --force запуск на те же 20
            → повторяешь пока доволен
              → полный запуск
```

Почему важен `PROMPT_VERSION`:

```python
PROMPT_VERSION = "v1"  # ← бамп при изменении промпта!

# При запуске скрипт проверяет:
prompt_file = PROMPT_VERSIONS_DIR / f"{PROMPT_VERSION}.txt"
if prompt_file.exists():
    if prompt_file.read_text() != CLASSIFICATION_PROMPT:
        print("⚠️  WARNING: промпт изменился, но версия та же!")
```

Если ты изменил промпт и не бампнул версию — старые результаты в кеше смешаются с новыми. Это тихая ошибка, которую трудно заметить.

---

## Шаг 7 — Run Protocol

Каждый прогон сохраняет метаданные:

```json
// state/newproject/runs/run_001.json
{
  "run_id": "run_001",
  "started_at": "2026-03-25T14:00:00Z",
  "prompt_version": "v2",
  "companies_processed": 200,
  "targets_found": 87,
  "segments": {
    "SEGMENT_A": 45,
    "SEGMENT_B": 42
  },
  "cost_usd": 0.06,
  "notes": "первый реальный прогон"
}
```

Зачем это нужно:
- Знаешь сколько денег потрачено суммарно
- Можешь откатиться к результатам конкретного прогона
- Видишь тренд: run1 → run2 → run3, конверсия растёт/падает
- Если промпт был v1 в run1 и v2 в run2 — видишь разницу в качестве

---

## Шаг 8 — Подключаем shared website cache

Если для OnSocial уже спарсили 2,000+ сайтов — не нужно парсить их снова для нового проекта:

```python
# В обоих пайплайнах используем один и тот же путь:
WEBSITE_CACHE_DIR = REPO_DIR / "state" / "shared" / "website_cache"
```

Логика в `step6_scrape()`:

```python
async def scrape_website(domain, cache):
    if domain in cache:
        return cache[domain]  # уже есть → берём из кеша

    # Парсим только новые
    text = await fetch_website_text(domain)
    cache[domain] = text
    return text
```

Экономия реальная: у OnSocial после 7 прогонов в кеше ~2,000 доменов. Если новый проект пересекается с теми же индустриями — большая часть уже готова.

---

## Итог: чеклист для нового пайплайна

```
[ ] README.md с ICP и сегментами
[ ] Структура папок создана (state/, input/, output/)
[ ] Apollo экспорт загружен в input/
[ ] SHEET_FILES настроен (имена файлов)
[ ] STATE_DIR, CSV_OUTPUT_DIR обновлены
[ ] Deterministic фильтры (размер, индустрия) настроены
[ ] CLASSIFICATION_PROMPT написан под ICP
[ ] PROMPT_VERSION = "v1"
[ ] PROJECT_CODE для CSV naming
[ ] Тест на 20 компаниях → --validate → итерация промпта
[ ] Полный прогон
[ ] --finalize-rejects (OTHER → blacklist)
[ ] CSV в output/ → в работу
```

---

## Вопрос для размышления

Сейчас у нас два пайплайна (`pipeline_onsocial.py` и будущий `pipeline_newproject.py`). Большая часть кода одинакова.

Как бы ты переделал архитектуру чтобы не копипастить? Подумай — в следующем уроке разберём это.

*(Подсказка: config-based подход — один `pipeline.py` + `config_onsocial.json` + `config_newproject.json`)*
