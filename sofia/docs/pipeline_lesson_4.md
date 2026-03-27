# Урок 4 — Запуск пайплайна для нового проекта

> **Для кого:** Sales Engineer, уровень Python: новичок
> **Контекст:** Уроки 1-3 разобрали как работает pipeline_onsocial.py изнутри. Теперь — как запустить такой же пайплайн для нового проекта с нуля.
> **Пример:** Притворяемся что OnSocial — новый проект. Данных нет, ничего не настроено. Начинаем с нуля.
> **Язык гайда:** русский | **Код:** английский

---

## Часть 0. Что означает "новый проект"

Когда мы говорим "запустить пайплайн для нового проекта" — это значит три вещи:

1. **Новая папка состояния** — `state/onsocial/` уже занята OnSocial. Для нового проекта нужна своя: `state/newproject/`
2. **Новый входной файл** — свой список компаний из Apollo (или другого источника)
3. **Новый classification prompt** — под конкретный ICP нового клиента

Всё остальное — архитектура шагов 0-8, JSON state machine, async scraping, CSV export — **переиспользуется без изменений**.

**Аналогия:** Это как новый прогон на той же фабрике. Конвейер тот же. Меняется только сырьё на входе и критерии отбора на шаге 7.

---

## Часть 1. Структура папок

Первое что делаем — создаём структуру. Это занимает 2 минуты и избавляет от ошибок в рантайме.

### Что нужно создать

```
magnum-opus/
├── state/
│   └── onsocial/          ← новая папка состояния
│       └── runs/          ← история прогонов
│
└── sofia/
    ├── input/
    │   └── [project]/     ← входные файлы Apollo
    └── output/
        └── OnSocial/
            ├── Leads/
            ├── Targets/
            ├── Import/
            └── Archive/
```

### Почему папка состояния отдельная

Посмотри на строки 37-43 в `pipeline_onsocial.py`:

```python
STATE_DIR = REPO_DIR / "state" / "onsocial"   # ← привязано к проекту
WEBSITE_CACHE_DIR = SHARED_CACHE_DIR / "website_cache"  # ← общий для всех
```

`STATE_DIR` — уникальна для каждого проекта. Там хранятся `classifications.json`, `targets.json`, `runs/` — всё это специфично для конкретного ICP.

`WEBSITE_CACHE_DIR` — общая для всех проектов. Если для OnSocial уже спарсили `grin.co` — при запуске нового проекта этот домен не будет скрейпиться заново. Экономия реальная.

---

## Часть 2. Входной файл

### Откуда берётся

Источников может быть несколько — Apollo ручной поиск, Clay Lookalike, Clay TAM export. В этом уроке контекст — **ручной Apollo**. Но для пайплайна источник не важен: на входе всегда JSON с массивом компаний.

### Формат который ожидает пайплайн

Посмотри на строки 62-68 в `pipeline_onsocial.py`:

```python
SHEET_FILES = {
    "us":     INPUT_DIR / "sheet_us.json",
    "uk_eu":  INPUT_DIR / "sheet_uk_eu.json",
    "latam":  INPUT_DIR / "sheet_latam.json",
    "india":  INPUT_DIR / "sheet_india.json",
    "mixed":  INPUT_DIR / "sheet_mixed.json",
}
```

Каждый файл — JSON массив компаний. Минимальные поля которые нужны:

```json
[
  {
    "name": "Grin",
    "domain": "grin.co",
    "employees": 150,
    "industry": "Computer Software"
  },
  ...
]
```

### Apollo экспортирует CSV — что делать

Apollo даёт CSV, пайплайн ожидает JSON. Конвертация — простой скрипт:

```python
import csv, json
from pathlib import Path

def csv_to_sheet_json(csv_path: str, json_path: str):
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "name":     row.get("Company", ""),
                "domain":   row.get("Website", "").replace("https://", "").replace("http://", "").rstrip("/"),
                "employees": int(row.get("# Employees", 0) or 0),
                "industry": row.get("Industry", ""),
            })
    Path(json_path).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"Converted {len(rows)} companies → {json_path}")

csv_to_sheet_json("apollo_export.csv", "sofia/input/onsocial/sheet_us.json")
```

---

## Часть 3. Три вещи которые меняются в скрипте

Открываем `pipeline_onsocial.py`. Для нового проекта меняем только три блока.

### 3.1. PATHS — папки

Строки 34-48:

```python
# Было (OnSocial):
STATE_DIR = REPO_DIR / "state" / "onsocial"

# Для нового проекта:
STATE_DIR = REPO_DIR / "state" / "newproject"
```

И CSV output:

```python
# Было:
PROJECT_CODE = "OS"
CSV_OUTPUT_DIR = SOFIA_DIR / "output" / "OnSocial"

# Для нового проекта:
PROJECT_CODE = "NP"   # короткий код проекта
CSV_OUTPUT_DIR = SOFIA_DIR / "output" / "NewProject"
```

### 3.2. SHEET_FILES — входные файлы

```python
# Было:
SHEET_FILES = {
    "us":    INPUT_DIR / "sheet_us.json",
    "uk_eu": INPUT_DIR / "sheet_uk_eu.json",
    ...
}

# Для нового проекта (только один регион для начала):
SHEET_FILES = {
    "global": INPUT_DIR / "newproject" / "sheet_global.json",
}
```

### 3.3. CLASSIFICATION_PROMPT — самое важное

Строки 132-244 в `pipeline_onsocial.py` — это весь промпт для OnSocial. Для нового проекта его нужно написать с нуля под новый ICP.

Структура хорошего промпта (разберём в следующей части).

---

## Часть 4. Classification Prompt

Это самая важная часть. Плохой промпт = плохие таргеты = деньги выброшены на GPT.

### Структура

```python
CLASSIFICATION_PROMPT = """
[КОНТЕКСТ ПРОДУКТА]
Кто мы, что продаём, кому нужно.

[СЕГМЕНТЫ]
SEGMENT_A: критерии + примеры компаний
SEGMENT_B: критерии + примеры компаний
OTHER: все остальные

[ДИСКВАЛИФИКАТОРЫ]
Жёсткое нет — без GPT сразу OTHER.

[ФОРМАТ ОТВЕТА]
SEGMENT_NAME | reasoning в одном предложении
"""
```

### Как это выглядит в OnSocial (сокращённо)

```python
# pipeline_onsocial.py, строки 132-244
CLASSIFICATION_PROMPT = """
You are classifying companies for OnSocial — influencer marketing platform.

SEGMENTS:
IM_FIRST_AGENCIES: agencies where influencer marketing is the PRIMARY service
  Signs: "influencer marketing agency", creator campaigns, UGC production
  NOT this: full-service agency with IM as one of 10 services

INFLUENCER_PLATFORMS: SaaS/tech platforms for influencer marketing
  Signs: marketplace, analytics, campaign management software, discovery tool

AFFILIATE_PERFORMANCE: performance marketing with creator/affiliate component
  Signs: CPA network, affiliate platform with influencer program

OTHER: doesn't fit above categories

Company: {company_name}
Domain: {domain}
Website: {website_text}

Respond: SEGMENT_NAME | one sentence reasoning
"""
```

### Три типичных ошибки при написании промпта

**Ошибка 1: Широкие критерии — всё попадает в цель**
```
❌ "любые маркетинговые агентства"
✅ "агентства где influencer marketing — основная услуга, не одна из 10"
```

**Ошибка 2: Нет примеров пограничных случаев**
```
❌ не объяснять разницу IM_AGENCY vs FULL_SERVICE_AGENCY
✅ "Full-service agency that offers IM among 10 other services → OTHER"
```

**Ошибка 3: Расплывчатый OTHER**
```
❌ "другие" (без деталей)
✅ "OTHER: media publishers, PR firms, brands (not agencies), SEO/PPC shops"
```

### PROMPT_VERSION — обязательно

Посмотри как это реализовано в `pipeline_onsocial.py` после наших улучшений в Уроке 3:

```python
PROMPT_VERSION = "v1"   # ← бамп при изменении промпта!

# При запуске скрипт проверяет:
prompt_file = PROMPT_VERSIONS_DIR / f"{PROMPT_VERSION}.txt"
if prompt_file.exists():
    if prompt_file.read_text() != CLASSIFICATION_PROMPT:
        print("⚠️  WARNING: промпт изменился, но версия та же!")
```

Если изменил промпт и не бампнул версию — старые результаты в кеше смешаются с новыми. Это тихая ошибка которую очень трудно заметить.

---

## Часть 5. Первый запуск — правильная последовательность

### Шаг 1: Детерминистика без GPT

```bash
# Запускаем только шаги 0-4 — мгновенно, бесплатно
python sofia/scripts/pipeline_onsocial.py --from-step 0 --step 4
```

Что происходит:
- Шаг 0: загружает blacklist
- Шаг 1: загружает компании из `SHEET_FILES`
- Шаг 2: дедупликация по домену
- Шаг 3: применяет blacklist
- Шаг 4: детерминистические фильтры (размер, индустрия)

После этого смотришь сколько компаний прошло:

```bash
python -c "
import json
p = json.load(open('state/onsocial/priority.json'))
n = json.load(open('state/onsocial/normal.json'))
print(f'Priority: {len(p)}, Normal: {len(n)}, Total: {len(p)+len(n)}')
"
```

Если осталось 0 — проблема с форматом входного файла (домены, поля). Исправляй до GPT.

### Шаг 2: Тестовый GPT-прогон на 20 компаниях

```bash
python sofia/scripts/pipeline_onsocial.py --from-step 6 --limit 20
```

`--limit 20` останавливает после 20 **таргетов** (не компаний). Это стоит ~$0.01.

### Шаг 3: Валидация качества

```bash
python sofia/scripts/pipeline_onsocial.py --validate 20
```

Это наш флаг из Урока 3. Выводит 20 случайных таргетов с reasoning и preview сайта. Смотришь глазами — правильно ли GPT классифицировал.

Критерий: если больше 3 из 20 явно неправильные — промпт нужно улучшать.

### Шаг 4: Итерация промпта

```
Видишь ошибки в --validate
  → правишь CLASSIFICATION_PROMPT
    → бампаешь PROMPT_VERSION (v1 → v2)
      → --force запуск на те же 20
        → снова --validate
          → повторяешь пока доволен
            → полный запуск без --limit
```

### Шаг 5: Полный прогон

```bash
python sofia/scripts/pipeline_onsocial.py --from-step 6
```

Пайплайн сам возьмёт все компании из priority queue (и normal если priority закончился), скрейпит сайты, прогоняет через GPT, сохраняет в `targets.json`.

---

## Часть 6. После прогона

### Что получаем

```
state/onsocial/
├── targets.json          ← целевые компании
├── rejects.json          ← нецелевые (с reasoning)
├── classifications.json  ← весь кеш GPT
└── runs/run_001.json     ← метаданные прогона

output/OnSocial/
├── Targets/
│   ├── OS | Targets | ALL — Mar 25.csv
│   ├── OS | Targets | IM_FIRST_AGENCIES — Mar 25.csv
│   └── OS | Targets | INFLUENCER_PLATFORMS — Mar 25.csv
└── Archive/
    └── OS | Archive | Rejects — Mar 25.csv
```

### Следующие шаги

```bash
# Переносим rejects в blacklist (чтобы не прогонять повторно)
python sofia/scripts/pipeline_onsocial.py --finalize-rejects

# Ищем контакты в целевых компаниях
python sofia/scripts/targets_to_contacts.py

# Обогащаем emails и заливаем в SmartLead
python sofia/scripts/findymail_to_smartlead.py \
  --input "output/OnSocial/Import/OS | Import | Apollo — ALL — Mar 25.csv" \
  --campaign-name "c-OnSocial_IMAGENCY #C v1" \
  --sequence sequences/onsocial_default.json
```

---

## Часть 7. Реальные числа для планирования

Из боевых прогонов OnSocial:

```
Apollo выгрузка:           41,658 компаний
После дедупа:              27,270 уникальных
После blacklist:           27,249
После детерминистики:      ~26,800
Priority queue:             2,670  ← компании с сигналами
Обработано GPT:             2,230
Таргеты:                      981  ← 44% конверсия из priority
Стоимость:                  $1.05  ← за 2,000 компаний
```

**Правило для планирования:** хочешь 500 таргетов → нужно ~1,100 компаний пройти через GPT → нужно ~4,000-5,000 компаний в Apollo выгрузке (с учётом детерминистических фильтров).

---

## Чеклист для нового проекта

```
[ ] Папка state/[project]/ создана
[ ] Папка output/[Project]/{Leads,Targets,Import,Archive}/ создана
[ ] Apollo CSV сконвертирован в JSON (поля: name, domain, employees, industry)
[ ] JSON файлы в sofia/input/[project]/
[ ] В скрипте обновлены: STATE_DIR, CSV_OUTPUT_DIR, PROJECT_CODE, SHEET_FILES
[ ] CLASSIFICATION_PROMPT написан под новый ICP
[ ] PROMPT_VERSION = "v1"
[ ] Запуск --step 4 → проверить что компании загрузились
[ ] Запуск --from-step 6 --limit 20 → тест GPT
[ ] --validate 20 → проверить качество
[ ] Итерация промпта если нужно
[ ] Полный прогон
[ ] --finalize-rejects
[ ] CSV в output/ готовы к работе
```

---

## Вопрос для размышления

Сейчас для нового проекта нужно копировать `pipeline_onsocial.py` и менять три места. Если проектов станет 5 — это 5 копий одного скрипта.

Как бы ты решил эту проблему? В следующем уроке разберём config-based подход: один `pipeline.py` + отдельный конфиг для каждого проекта.
