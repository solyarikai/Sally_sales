# Enrichment Pipeline v2 — Полный гайд

> **Для кого:** Sales Engineer, уровень Python: новичок
> **Файл:** `sofia/scripts/pipeline_onsocial.py` (1320 строк)
> **Язык гайда:** русский | **Код:** английский

---

## Часть 0. Что такое enrichment-пайплайн и зачем он нужен

Enrichment-пайплайн — это конвейер, который берёт «сырой» список компаний из Apollo (75 000+) и превращает его в готовый, сегментированный список целевых компаний (~4 000–5 000 таргетов). Зачем? Потому что Apollo отдаёт всё подряд: нерелевантные индустрии, мёртвые сайты, дубликаты. Руками это фильтровать невозможно — значит, автоматизируем.

**Аналогия:** Представь золотодобычу. Apollo — это порода (руда). Пайплайн — промывочный лоток, который убирает камни (дубли), песок (нерелевантные индустрии), глину (мёртвые сайты), и в конце у тебя — чистое золото (таргеты).

### Философия: Layered Via Negativa

Ключевой принцип из документации `SCORING_PIPELINE.md` — **Layered Via Negativa**: не ищи подходящих, а послойно убирай неподходящих. Каждый слой дешевле предыдущего:

1. **Дешёвые детерминированные фильтры** — employees, industry, blacklist (бесплатно, мгновенно)
2. **DNS-проверка** — жив ли домен (бесплатно, 3 секунды на домен)
3. **Regexp-фильтры** — парковка, FSA-паттерны на тексте сайта (бесплатно, мгновенно)
4. **GPT-классификация** — только для тех, кто прошёл все предыдущие слои ($0.12 / 1000 компаний)

Каждый слой убирает 10–30% оставшихся. Если бы мы сразу прогоняли все 75K через GPT — это $9+. После фильтров до GPT доходит ~15K → $1.80.

---

## Часть 1. Архитектура скрипта

### 1.1. Структура файла (строки 1–244)

Файл `pipeline_onsocial.py` организован так:

```
Строки 1–16    — docstring с usage (как запускать скрипт)
Строки 17–30   — импорты
Строки 32–59   — PATHS (пути к файлам состояния)
Строки 62–68   — SHEET_FILES (входные файлы Apollo)
Строки 73–98   — CONSTANTS (ключевые слова, индустрии, FSA-паттерны)
Строки 100–130 — Константы улучшений (parked patterns, skip-scrape thresholds)
Строки 132–244 — CLASSIFICATION_PROMPT (промпт для GPT)
Строки 246–330 — HELPERS (вспомогательные функции)
Строки 331–567 — STEPS 0–4 (детерминированные шаги)
Строки 569–725 — STEPS 5–6 (DNS + скрейпинг)
Строки 727–892 — STEPS 6.5, 6.7 (regexp pre-filter, deep scrape)
Строки 894–1053 — STEP 7 (GPT-классификация)
Строки 1056–1167 — STEPS 7b, 8 (импорт, выход)
Строки 1170–1321 — MAIN (CLI + оркестрация)
```

### 1.2. Паттерн кэширования: JSON State Machine

Каждый шаг сохраняет результат в JSON-файл в `state/onsocial/`. При повторном запуске шаг видит файл и пропускается:

```python
# Паттерн из step1_load (строка 354):
def step1_load(force: bool = False):
    if ALL_COMPANIES.exists() and not force:       # ← файл есть?
        companies = load_json(ALL_COMPANIES)        # ← загрузить из кэша
        print(f"  already exists: {len(companies)} companies (skip)")
        return companies
    # ... иначе выполняем логику шага
    save_json(ALL_COMPANIES, companies)             # ← сохраняем для следующего раза
    return companies
```

**Зачем?** Скрейпинг 15K сайтов занимает ~2 часа. Если на Step 7 произойдёт ошибка — не начинать заново. Просто `--from-step 7`.

Файлы состояния (строки 50–59):

| Файл | Что хранит |
|------|-----------|
| `campaign_blacklist.json` | Домены, куда уже писали |
| `all_companies.json` | Все загруженные компании |
| `after_blacklist.json` | Компании после дедупликации + blacklist |
| `priority.json` | Компании с позитивными сигналами |
| `normal.json` | Компании без сигналов |
| `disqualified.json` | Отфильтрованные |
| `classifications.json` | Результаты GPT (и regexp) классификации |
| `targets.json` | Финальные таргеты |
| `rejects.json` | Финальные реджекты |

### 1.3. CLI-интерфейс (строки 1172–1184)

```bash
python pipeline_onsocial.py                      # все шаги 0→8
python pipeline_onsocial.py --from-step 6        # продолжить с шага 6
python pipeline_onsocial.py --step 4             # только один шаг
python pipeline_onsocial.py --limit 20           # остановиться после 20 таргетов
python pipeline_onsocial.py --force              # игнорировать кэш
python pipeline_onsocial.py --import-existing    # импорт старых прогонов

# Новые флаги v2:
python pipeline_onsocial.py --no-prefilter       # отключить regexp pre-filter
python pipeline_onsocial.py --no-deep-scrape     # отключить deep scrape
python pipeline_onsocial.py --no-skip-scrape     # не пропускать скрейпинг для high-signal
```

Парсинг (строка 1172):

```python
def main():
    parser = argparse.ArgumentParser(description="OnSocial Enrichment Pipeline (v2 — improved)")
    parser.add_argument("--step", type=int, help="Run only this step (0-8)")
    parser.add_argument("--from-step", type=int, default=0, help="Start from this step")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N targets found")
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists")
    parser.add_argument("--no-prefilter", action="store_true")
    parser.add_argument("--no-deep-scrape", action="store_true")
    parser.add_argument("--no-skip-scrape", action="store_true")
```

Логика `should_run` (строки 1198–1201):

```python
run_step = args.step
from_step = args.from_step if run_step is None else run_step

def should_run(n):
    if run_step is not None:
        return n == run_step        # --step 4 → только шаг 4
    return n >= from_step           # --from-step 6 → шаги 6,7,8
```

---

## Часть 2. Шаги пайплайна (Step 0–8)

### Step 0: Blacklist (строки 333–349)

**Что делает:** Загружает список доменов, куда мы уже писали. Эти домены нельзя обрабатывать повторно — получатели будут раздражены.

**Откуда берётся:** `input/campaign_blacklist.json` — экспорт из SmartLead (все домены, которым мы уже отправляли письма).

```python
def step0_blacklist(force: bool = False):
    if BLACKLIST_FILE.exists() and not force:
        bl = load_json(BLACKLIST_FILE)
        return bl
    src = INPUT_DIR / "campaign_blacklist.json"
    if src.exists():
        bl = load_json(src)
        save_json(BLACKLIST_FILE, bl)
        return bl
    print("  ERROR: campaign_blacklist.json not found in input/")
    sys.exit(1)                                     # ← без blacklist нет запуска
```

**Почему `sys.exit(1)`?** Если забыть blacklist, мы напишем повторно тем же людям. Это критическая ошибка, поэтому пайплайн просто не запустится.

---

### Step 1: Load & Normalize (строки 352–426)

**Что делает:** Загружает 5 JSON-файлов от Apollo (US, UK/EU, LATAM, India, Mixed), нормализует домены и собирает в единый массив.

Ключевой момент — нормализация домена (функция `norm_domain`, строки 248–259):

```python
def norm_domain(raw: str) -> str:
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)    # убрать протокол
    d = re.sub(r"^www\.", "", d)         # убрать www.
    d = d.split("/")[0]                  # убрать путь
    d = d.split("?")[0]                  # убрать query string
    d = d.split("#")[0]                  # убрать якорь
    d = d.split(":")[0]                  # убрать порт
    return d.strip()
```

**Зачем?** Apollo может дать `https://www.example.com/`, `http://example.com`, `example.com:443` — всё это один и тот же домен. Без нормализации будут ложные дубликаты.

Маппинг колонок (строки 371–388) — каждый JSON-файл от Apollo имеет свои заголовки. Функция `col()` ищет заголовок по имени, возвращая индекс:

```python
ci_name     = col(["Company Name"])
ci_emp      = col(["# Employees"])
ci_industry = col(["Industry"])
ci_website  = col(["Website"])
# ... и т.д.
```

Каждая компания сохраняется как dict (строки 401–415) с обрезкой длинных полей: `keywords[:500]`, `description[:1000]`. Это экономит RAM и ускоряет JSON-операции.

**Self-check** (строки 420–424): если загружено <5000 компаний — предупреждение. Ожидаемый диапазон: 20K–100K.

---

### Step 2: Deduplicate (строки 429–452)

**Что делает:** Удаляет дубликаты по домену. Apollo часто возвращает одну компанию из разных поисков.

```python
seen = {}
for c in companies:
    d = c["domain"]
    if d not in seen:
        seen[d] = c
    else:
        dupes += 1
deduped = list(seen.values())
```

Простая логика: первое вхождение побеждает. Self-check: дупликат-рейт обычно 1–30%.

---

### Step 3: Blacklist Filter (строки 455–479)

**Что делает:** Удаляет компании, чьи домены есть в blacklist из Step 0.

```python
bl_set = set(blacklist["domains"])        # O(1) lookup — быстро
for c in companies:
    if c["domain"] in bl_set:
        removed += 1
    else:
        passed.append(c)
```

**Два self-check:**
- Если `removed == 0` — предупреждение: «Проверь нормализацию доменов»
- Диапазон: 0.5–15% должны быть удалены

---

### Step 4: Deterministic Filter (строки 482–566)

Самый сложный детерминированный шаг. Три под-фильтра:

**4a. Employee filter** (строки 499–510):
```python
if emp < 5:
    disq_reason = "Too small"
elif emp > 5000:
    disq_reason = "Enterprise"
```

**4b. Industry disqualifier** (строки 513–525):

30 запрещённых индустрий (строки 83–90): staffing, real estate, mining, banking и т.д. Но есть **позитивное переопределение**: если у компании есть ключевое слово "influencer" в keywords — индустрия НЕ дисквалифицирует.

```python
has_positive = has_positive_signal(combined)
if not has_positive:
    for bad in DISQUALIFY_INDUSTRIES:
        if bad in industry_lower:
            disq_reason = f"Industry: {c['industry']}"
```

**Зачем переопределение?** Компания из «staffing», которая занимается подбором инфлюенсеров — это таргет.

**4c. FSA filter** (строки 528–531):

FSA = Full-Service Agency. Компании типа «SEO + PPC + web design + social media». Они предлагают всё подряд, influencer marketing у них — 5% бизнеса. Не таргет.

Паттерны (строки 93–98):
```python
FSA_PATTERNS = [
    r"\bseo\b.*\bppc\b",
    r"\bfull.?service\b.*\bagency\b",
    r"\bdigital marketing agency\b.*\bseo\b",
    r"\bpr agency\b",
    # ...
]
```

**4d. Priority queue** (строки 537–549):

Компании, прошедшие все фильтры, делятся на две очереди:
- **Priority** — есть хотя бы 1 позитивный сигнал (слово из `POSITIVE_KEYWORDS` в keywords/description)
- **Normal** — нет сигналов, но и не дисквалифицированы

Priority сортируется по `signal_count` (убывание) — компании с наибольшим числом сигналов обрабатываются первыми.

**Self-checks** (строки 556–561):
- Priority queue: 5–25% от общего числа
- Disqualified: 2–30%
- Если оба пусты — критическая ошибка

---

### Step 5: DNS Pre-check (строки 569–614)

**Что делает:** Проверяет, жив ли домен (отвечает ли DNS).

```python
socket.setdefaulttimeout(3)
socket.getaddrinfo(domain, None)     # ← если не отвечает → gaierror
```

**Кэш:** `dns_cache.json` — чтобы не проверять одни и те же домены при повторном запуске. Также если домен уже есть в `classifications.json` — значит, он когда-то был жив, пропускаем проверку.

**Автосохранение:** Каждые 100 проверок кэш сохраняется на диск (строки 603–605) — если скрипт упадёт, не начинать с нуля.

---

### Step 6: Website Scraping (строки 617–724)

**Что делает:** Скачивает homepage каждого домена, извлекает текст для GPT-классификации.

#### Функция `scrape_domain` (строки 619–672)

```python
async def scrape_domain(client: httpx.AsyncClient, domain: str) -> dict:
    cache_file = WEBSITE_CACHE_DIR / f"{domain}.json"
    if cache_file.exists():
        return load_json(cache_file)         # ← кэш: один файл на домен
```

**Кэш — отдельный файл на домен** (а не один большой JSON). Почему? Если 15K доменов в одном файле — это ~500MB JSON, который надо парсить целиком. Отдельные файлы можно читать по одному.

**Shared cache** (строки 37–41, Improvement E):
```python
SHARED_CACHE_DIR = REPO_DIR / "state" / "shared"
WEBSITE_CACHE_DIR = SHARED_CACHE_DIR / "website_cache"
```

Кэш общий для всех проектов (OnSocial, ArchiStruct). Если `example.com` скрейпили для OnSocial — ArchiStruct его не будет скрейпить заново.

**Очистка HTML** (строки 646–653):

```python
soup = BeautifulSoup(response.text, "html.parser")
for tag in soup(["nav", "footer", "script", "style", "noscript", "header", "aside"]):
    tag.decompose()                           # ← удаляем «шум»
text = soup.get_text(separator=" ", strip=True)
text = re.sub(r"\s+", " ", text).strip()
result["content"] = text[:5000]               # ← обрезаем до 5K символов
```

Зачем удалять nav/footer/script? GPT получает текст и должен понять, чем занимается компания. Навигация, копирайт, скрипты — это мусор.

#### Async-параллелизм (строки 675–724)

```python
async def step6_scrape(companies: list, concurrency: int = 8) -> dict:
    sem = asyncio.Semaphore(concurrency)

    async def scrape_with_sem(c):
        async with sem:                        # ← не более 8 одновременных запросов
            result = await scrape_domain(client, c["domain"])

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=concurrency * 2)) as client:
        await asyncio.gather(*[scrape_with_sem(c) for c in to_scrape])
```

**Semaphore** ограничивает параллелизм: `concurrency=8` значит максимум 8 HTTP-запросов одновременно. Без этого 15K одновременных соединений убьют и сеть, и IP может быть забанен.

**Прогресс:** Каждые 50 доменов выводится скорость и ETA:
```
    150/3200 scraped (2.3/s, ~1326s remaining)
```

---

### Step 6.5: Regexp Pre-filter (строки 727–795) — Improvement A

**Зачем:** Между скрейпингом и GPT есть возможность отфильтровать очевидный мусор **бесплатно**, без API-вызовов. Экономия ~10–15% GPT-вызовов.

Два вида фильтрации:

**1. Парковочные/мёртвые домены** (функция `is_parked_or_dead`, строки 288–298):

```python
PARKED_DOMAIN_PATTERNS = [
    r"this domain is for sale",
    r"domain is parked",
    r"buy this domain",
    r"godaddy",
    r"hugedomains",
    r"dan\.com",
    # ...
]
```

Если текст сайта содержит "this domain is for sale" — не тратить GPT-токены, сразу `OTHER`.

Также: если весь текст сайта < 100 символов — это заглушка:
```python
if len(t) < 100:
    return f"Placeholder site ({len(t)} chars)"
```

**2. FSA на полном тексте сайта** (функция `is_fsa_website`, строки 301–306):

В Step 4 FSA-проверка работает только по Apollo-данным (keywords, description). Здесь — по тексту всего сайта. Паттерны жёстче (строки 121–125):

```python
FSA_WEBSITE_PATTERNS = [
    r"\bseo\b.*\bppc\b.*\b(web design|social media)\b",        # SEO + PPC + ещё сервис
    r"\bfull.?service\b.*\b(digital|marketing|creative)\b.*\bagency\b",
    r"\b(seo|ppc|web design|email marketing|social media)\b.*\b(seo|...)\b.*\b(seo|...)\b",  # 3+ сервиса
]
```

**Автоклассификация** сохраняется в тот же `classifications.json` с пометкой `classified_by: "regexp_prefilter"`:
```python
auto_classified[domain] = {
    "segment": "OTHER",
    "reasoning": parked_reason,
    "classified_by": "regexp_prefilter",   # ← чтобы GPT не пересчитывал
}
```

Выводится оценка сэкономленных денег:
```
  → saved 847 auto-classifications (saved ~$0.10 GPT cost)
```

---

### Step 6.7: Deep Scrape (строки 798–891) — Improvement D

**Зачем:** Иногда homepage не даёт ясности. Компания «Agency XYZ» — а чем именно занимается? Страницы /about, /team, /services могут дать ответ.

**Кто попадает в deep scrape?** (строки 841–852):
- Есть текст homepage (>200 символов)
- Нет позитивных сигналов (`signal_count == 0`)
- Ещё не классифицирован
- Лимит: 200 компаний максимум

```python
async def deep_scrape_domain(client, domain) -> str:
    for path in ["/about", "/about-us", "/team", "/our-team", "/services", "/contact"]:
        url = f"https://{domain}{path}"
        response = await client.get(url, timeout=10.0, follow_redirects=True)
        if response.status_code == 200 and len(text) > 50:
            extra_texts.append(f"[{path}] {text[:2000]}")
    return "\n".join(extra_texts)
```

Дополнительный текст **дописывается** к существующему кэшу homepage:
```python
website_cache[domain]["content"] = existing_content + "\n" + extra[:3000]
website_cache[domain]["deep_scraped"] = True
```

GPT получает больше контекста → точнее классификация.

---

### Step 7: AI Classification (строки 894–1053)

Главный шаг — GPT-4o-mini классифицирует каждую компанию в один из сегментов.

#### Промпт (строки 132–244)

Промпт структурирован в 4 шага (для GPT):
1. **INSTANT DISQUALIFIERS** — пустые данные, парковка, >5000 / <10 сотрудников → `OTHER`
2. **SEGMENTS** — описание 4 категорий: `INFLUENCER_PLATFORMS`, `AFFILIATE_PERFORMANCE`, `IM_FIRST_AGENCIES`, `OTHER` + поддержка `NEW:` для открытия новых сегментов
3. **FIND EVIDENCE** — какие маркеры искать в тексте
4. **CONFLICT RESOLUTION** — правила приоритета: сайт > Apollo, ambiguous → OTHER

#### Формат ответа GPT

```
SEGMENT | one-sentence evidence
```

Парсинг (строки 935–941):
```python
if "|" in text:
    segment, reasoning = text.split("|", 1)
else:
    segment = text.strip()
    reasoning = ""
```

#### Параллелизм GPT (строки 1005–1034)

```python
sem = asyncio.Semaphore(concurrency)     # concurrency=20 по умолчанию

async def classify_with_sem(company):
    async with sem:
        if limit_targets and targets_found >= limit_targets:
            return                          # ← early stop
        result = await classify_company(client, company, website_cache)
        classifications[company["domain"]] = result
```

20 одновременных запросов к OpenAI API. Каждые 100 классификаций — автосохранение.

**Early stop** (строки 1026–1028): если `--limit 20` — останавливается после 20 таргетов:
```python
if limit_targets and targets_found >= limit_targets:
    raise StopAsyncIteration()
```

#### Self-checks (строки 1039–1051)

```python
self_check("Step 7", others, total_cls, 50, 95, "OTHER classification rate")
self_check("Step 7", errors, total_cls, 0, 5, "ERROR rate")
```

- OTHER rate 50–95% — нормально (большинство компаний нерелевантны)
- ERROR rate >5% — проблема с API
- 0 таргетов после 100+ классификаций — промпт слишком строгий

**Оценка стоимости:**
```python
total_tokens = sum(v.get("tokens_used", 0) for v in classifications.values())
est_cost = total_tokens * 0.15 / 1_000_000
print(f"  💰 Estimated GPT cost: ~${est_cost:.2f}")
```

---

### Skip-Scrape: Improvement B (строки 127–130, 309–313, 1259–1271)

**Идея:** Компании с 3+ позитивными сигналами и описанием ≥100 символов в Apollo — почти наверняка таргеты. Зачем скрейпить их сайт? GPT может классифицировать по Apollo-данным.

```python
SKIP_SCRAPE_MIN_SIGNALS = 3        # минимум 3 ключевых слова
SKIP_SCRAPE_MIN_DESC_LEN = 100     # минимум 100 символов описания

def can_skip_scraping(company: dict) -> bool:
    signals = company.get("signal_count", 0)
    desc = company.get("description", "") or company.get("short_description", "")
    return signals >= SKIP_SCRAPE_MIN_SIGNALS and len(desc) >= SKIP_SCRAPE_MIN_DESC_LEN
```

В `main()` (строки 1259–1271):
```python
if should_run(6) and not args.no_skip_scrape:
    scrape_queue = []
    for c in process_queue:
        if can_skip_scraping(c):
            skip_scraped.append(c)      # ← не скрейпим, сразу на GPT
        else:
            scrape_queue.append(c)
```

Настраивается через env-переменные:
```bash
SKIP_SCRAPE_MIN_SIGNALS=5 SKIP_SCRAPE_MIN_DESC_LEN=200 python pipeline_onsocial.py
```

---

### Step 8: Output (строки 1095–1167)

**Что делает:** Собирает результаты в `targets.json`, `rejects.json`, `pipeline_stats.json`.

Каждый таргет — обогащённая запись (строки 1113–1138) со всеми полями: домен, имя, сегмент, reasoning, employees, country, keywords, website_content_preview, LinkedIn URL, source_sheet, scrape_status, prompt_version, и т.д.

Сортировка: таргеты с наибольшим `signal_count` — вверху.

---

## Часть 3. Self-checks (Improvement C)

Self-check — это автоматическая проверка здоровья пайплайна. После каждого шага скрипт сравнивает метрику с ожидаемым диапазоном. Если выходит за границы — печатает `⚠️ ALERT`.

Функция (строки 318–329):

```python
def self_check(step_name, value, total, expected_min_pct, expected_max_pct, metric_name):
    pct = value * 100 / total
    if pct < expected_min_pct:
        print(f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — below expected {expected_min_pct}%")
    elif pct > expected_max_pct:
        print(f"  ⚠️  ALERT [{step_name}]: {metric_name} = {pct:.1f}% — above expected {expected_max_pct}%")
```

**Таблица self-checks в пайплайне:**

| Шаг | Метрика | Ожидаемый диапазон |
|-----|---------|--------------------|
| Step 1 | Companies loaded | 20,000+ |
| Step 2 | Duplicate rate | 0–40% |
| Step 3 | Blacklist removal rate | 0.5–15% |
| Step 4 | Priority queue % | 5–25% |
| Step 4 | Disqualified % | 2–30% |
| Step 6 | Scrape success rate | 30–95% |
| Step 7 | OTHER classification rate | 50–95% |
| Step 7 | ERROR rate | 0–5% |

**Зачем это нужно?** Представь: ты случайно загрузил не тот blacklist — и 80% компаний удалилось. Или промпт слишком строгий — 100% OTHER. Без self-checks это можно заметить только вручную, просматривая тысячи строк.

---

## Часть 4. Вспомогательные скрипты (Post-Pipeline)

После `pipeline_onsocial.py` → `targets.json`. Но нам нужны **email-адреса конкретных людей** в этих компаниях.

### 4.1. Скрипт 2: findymail_to_smartlead.py

**Файл:** `sofia/scripts/findymail_to_smartlead.py`
**Назначение:** Обогащение контактов email-ами через Findymail + создание кампании в SmartLead.

#### Нормализация имени компании (строки 63–83)

5 правил нормализации:

```python
LEGAL_SUFFIXES = re.compile(
    r'\s*[,.]?\s*(GmbH|Ltd\.?|Limited|LLC|Inc\.?|Corp\.?|SAS|...)\s*$',
    re.IGNORECASE,
)

def normalize_company(name: str) -> str:
    # 1. Удалить юридические суффиксы: "Acme Ltd." → "Acme"
    name = LEGAL_SUFFIXES.sub("", name).strip().rstrip(".,")
    # 2. Слаг с дефисами: "cool-agency" → "cool agency"
    if "-" in name and name == name.lower():
        name = name.replace("-", " ")
    # 3. Всё строчные: "coolcompany" → "Coolcompany"
    if name == name.lower() and len(name) > 4:
        name = name.title()
    # 4. Всё заглавные: "ACME CORP" → "Acme Corp"
    elif name == name.upper() and len(name) > 4:
        name = name.title()
    # 5. Финальная обрезка пробелов
    return name.strip()
```

#### Findymail API — двойной метод

**Phase 1** — по LinkedIn URL (строки 92–120):
```python
async def find_email(client, linkedin_url) -> dict:
    r = await client.post(
        f"{FINDYMAIL_BASE}/api/search/linkedin",
        json={"linkedin_url": url},
    )
```

Hit rate Phase 1: ~50–60%.

**Phase 2** (отдельный скрипт `enrich_without_email.py`) — по имени + домену:
```
POST /api/search/name
{"first_name": "John", "last_name": "Doe", "domain": "example.com"}
```

Phase 2 подхватывает тех, кого Phase 1 не нашла.

**Phase 3** (скрипт `enrich_domain_retry.py`) — Apollo domain lookup + повторный Findymail по новым данным.

#### Генерация without_email.csv (строки 227–233)

```python
# Контакты без email, но с LinkedIn URL → передаём в Phase 2
without_email = [r for r in rows if not r.get("Email", "").strip()
                 and r.get("Profile URL", "").strip()]
without_email_csv = emails_csv.parent / (
    emails_csv.stem.replace(" - emails", "") + " - without_email.csv"
)
```

**Зачем?** Phase 2 (`enrich_without_email.py`) берёт этот файл как вход. Раньше его приходилось создавать вручную.

#### SmartLead интеграция (строки 246–350+)

После обогащения:
1. `create_campaign()` — создаёт кампанию в SmartLead
2. `add_sequences()` — загружает email-последовательность из JSON
3. `add_email_accounts()` — привязывает почтовые аккаунты
4. `upload_leads()` — загружает контакты пакетами

Rate limit: SmartLead иногда возвращает 429. Скрипт делает retry с экспоненциальным backoff.

---

## Часть 5. Полная воронка (числа для OnSocial)

```
Apollo Export:           ~75,000 компаний
  ↓ Step 1 (load)
Loaded:                  ~75,000
  ↓ Step 2 (dedup)
After dedup:             ~50,000  (−33% дубликатов)
  ↓ Step 3 (blacklist)
After blacklist:         ~47,000  (−6%)
  ↓ Step 4 (filter)
Priority:                ~3,500   (7% — с позитивными сигналами)
Normal:                  ~28,000  (60%)
Disqualified:            ~15,500  (33%)
  ↓ Step 5 (DNS)
Alive:                   ~27,000  (−15% мёртвых DNS)
  ↓ Step 6 (scrape)
Successfully scraped:    ~18,000  (67% success rate)
  ↓ Step 6.5 (prefilter)
Removed by regexp:       ~1,800   (parked + FSA)
To GPT:                  ~16,200
  ↓ Step 6.7 (deep scrape)
Enriched borderline:     ~150/200
  ↓ Step 7 (GPT)
Targets found:           ~4,200   (~26% of GPT-classified)
OTHER:                   ~12,000  (~74%)
  ↓ Step 8 (output)
targets.json:            ~4,200
```

**Стоимость GPT:** ~16,200 × ~500 tokens × $0.15/M = ~$1.22

---

## Часть 6. Резюме улучшений v2

| # | Улучшение | Строки | Экономия |
|---|-----------|--------|----------|
| A | Regexp pre-filter (parked/FSA) | 100–125, 288–306, 727–795 | ~10–15% GPT calls |
| B | Skip-scrape для high-signal | 127–130, 309–313, 1259–1271 | ~5–10% scraping time |
| C | Self-checks на каждом шаге | 316–329, + в каждом step | Раннее обнаружение проблем |
| D | Deep scrape для borderline | 798–891, 1289–1295 | +2–5% accuracy |
| E | Shared website cache | 37–41 | Экономия при нескольких проектах |
| F | without_email.csv | findymail_to_smartlead.py:227–233 | Автоматизация Phase 2 |

Все улучшения обратно совместимы: `--no-prefilter`, `--no-deep-scrape`, `--no-skip-scrape` отключают каждое по отдельности.

---

## Часть 7. Ключевые паттерны для создания новых пайплайнов

Когда будешь создавать пайплайн для нового проекта (например, ArchiStruct), используй эти принципы:

1. **JSON State Machine** — каждый шаг сохраняет результат. `--force` для пересчёта, `--from-step N` для продолжения.

2. **Layered Via Negativa** — дешёвые фильтры первыми. Порядок: deterministic → DNS → regexp → GPT.

3. **Shared cache** — `state/shared/website_cache/`. Один домен скрейпится один раз для всех проектов.

4. **Semaphore для async** — ограничивай параллелизм. 8 для HTTP, 20 для API, 4 для deep scrape.

5. **Self-checks** — добавляй ожидаемые диапазоны для каждой метрики. Это спасёт от «тихих» ошибок.

6. **Progress + autosave** — каждые N итераций сохраняй промежуточный результат.

7. **Промпт = код** — GPT-промпт определяет точность. Сохраняй версии (`prompt_version`), итерируй: score → scrape → GPT → verify 100 → fix → repeat.

8. **3-phase enrichment** — LinkedIn URL → name+domain → Apollo retry. Каждый проход добавляет ~10–15% email'ов.
