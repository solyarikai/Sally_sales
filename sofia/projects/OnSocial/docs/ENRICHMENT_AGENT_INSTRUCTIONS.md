# Enrichment Agent — Полная инструкция

**Задача:** Обогатить `cf_business_observation` в SmartLead для заданного списка кампаний.  
**Автономность:** Полная. Не останавливаться и не запрашивать подтверждений в процессе работы.

---

## Окружение

- **Рабочая директория:** `/Users/sofia/code/Sally_sales`
- **Python:** `python3.11`
- **Env переменные** (нужны для скрипта):
  - `SMARTLEAD_API_KEY=eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5`
  - `EXA_API_KEY=9c2d6eb0-66d8-4163-b244-6b4e78525aa0`
- **SmartLead base URL:** `https://server.smartlead.ai/api/v1`
- **Exa base URL:** `https://api.exa.ai`
- **Haiku:** запускается через `claude -p "<prompt>" --output-format text --model claude-haiku-4-5-20251001`

---

## Список кампаний для обработки

Обрабатывать **ровно те кампании**, которые предоставлены пользователем (название + ID).  
Включать все статусы: ACTIVE, PAUSED, DRAFTED.

---

## Маппинг сегментов

По названию кампании определяй сегмент:

| Подстрока в названии | Сегмент | Файл промпта |
|---|---|---|
| `_INFPLAT_` | INFLUENCER_PLATFORMS | `sofia/projects/OnSocial/prompts/classify_influencer_platforms.md` |
| `_IMAGENCY_` | IM_FIRST_AGENCIES | `sofia/projects/OnSocial/prompts/classify_im_first_agencies.md` |
| `_AFFPERF_` | AFFILIATE_PERFORMANCE | `sofia/projects/OnSocial/prompts/classify_affiliate_performance.md` |
| `_SOCCOM_` | SOCIAL_COMMERCE | `sofia/projects/OnSocial/prompts/classify_social_commerce.md` |

Если ни одна подстрока не совпала → логировать `segment_unknown`, пропустить кампанию, продолжить.

---

## Алгоритм (на каждую кампанию)

### Шаг 1 — Забрать лиды из SmartLead

```
GET /campaigns/{campaign_id}/leads?api_key=...&offset=0&limit=100
```

Пагинация: повторять с `offset += 100` пока `len(page) == 100`.  
Из каждого лида извлечь: `id`, `email`, `company_name`, `website`, `custom_fields`.

### Шаг 2 — Сгруппировать по домену

- Домен = часть после `@` в email (если нет поля `website`)
- Пропустить free-mail домены: `gmail.com yahoo.com hotmail.com outlook.com icloud.com aol.com protonmail.com mail.com live.com msn.com`
- **Пропустить домен** если у первого лида в группе `custom_fields.cf_business_observation` уже не пустой → логировать `already_enriched`

### Шаг 3 — Получить контент о компании

**Приоритет 1 — Exa crawl (JS-рендеринг):**
```python
POST https://api.exa.ai/contents
{
  "ids": ["https://{domain}"],
  "text": {"maxCharacters": 1600}
}
```
Если вернул непустой `text` длиной > 100 символов → использовать как `exa_content`.

**Приоритет 2 — Exa search (если crawl пустой):**
```python
POST https://api.exa.ai/search
{
  "query": "{company_name} {segment_keywords}",
  "numResults": 3,
  "contents": {"text": {"maxCharacters": 1000}}
}
```
Где `segment_keywords` из маппинга выше (например `influencer creator analytics platform` для INFPLAT).  
Предпочитать результаты где URL или текст содержит корень домена.  
Объединить до 2 результатов, взять до 1600 символов → `exa_content`.

**Приоритет 3 — HTTP scrape (если оба пусты):**
```python
GET https://www.{domain}  # затем https://{domain}, затем http://{domain}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36
```
Вырезать `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`.  
Взять до 3000 символов текста → `scraped_content`.

**Если всё пусто:** `exa_content = ""`, `scraped_content = ""` — передать Haiku как есть, он вернёт `OTHER | No website data`.

### Шаг 4 — Классификация через Haiku

Прочитать нужный промпт-файл (по маппинг сегмента).  
Подставить переменные:
- `{{company_name}}` → company_name лида
- `{{employees}}` → поле employees лида (или пустая строка)
- `{{exa_content}}` → результат из шага 3
- `{{scraped_content}}` → результат из шага 3

Запустить:
```bash
claude -p "<промпт с подставленными значениями>" --output-format text --model claude-haiku-4-5-20251001
```

Таймаут: 60 секунд. При ошибке или таймауте — 2 retry, затем логировать `haiku_fail`, пропустить домен, продолжить.

**Парсинг ответа:**
Ожидаемый формат: `SEGMENT | TIER | evidence`  
Примеры:
- `IM_FIRST_AGENCIES | TIER_0 | Pure TikTok agency running 30+ brand campaigns...`
- `OTHER | Full-service agency listing influencer as one of 9 services`

### Шаг 5 — Записать результат

**Если TIER_0:**
- `observation` = текст после второго `|` (evidence)
- Обновить `cf_business_observation` для **всех лидов домена** через SmartLead:
```
POST /campaigns/{campaign_id}/leads/{lead_id}?api_key=...
{"email": "...", "custom_fields": {...existing_cf..., "cf_business_observation": "<observation>"}}
```
Retry: 3 попытки с backoff 5s / 15s / 30s на 429. При fail → логировать `update_fail`, продолжить.

**Если TIER_1:**
- Не писать в SmartLead. Только логировать.

**Если OTHER:**
- Не писать в SmartLead.
- Добавить в соответствующий JSON-файл сегмента (см. ниже).

### Шаг 6 — Логирование

JSONL-файл: `sofia/reports/exa_enrichment_{date.today()}.jsonl`

Каждая запись:
```json
{
  "domain": "example.com",
  "company_name": "Example Inc",
  "campaign_id": 3215181,
  "segment": "AFFILIATE_PERFORMANCE",
  "tier": "TIER_0",
  "evidence": "CPA network connecting...",
  "cf_business_observation": "CPA network connecting advertisers...",
  "exa_used": true,
  "scrape_used": false,
  "status": "ok",
  "processed_at": "2026-04-30T10:00:00Z"
}
```

`status` варианты: `ok`, `tier_1`, `other`, `already_enriched`, `content_fail`, `haiku_fail`, `update_fail`, `segment_unknown`

**Идемпотентность:** При старте читать существующий JSONL (если есть). Домены со статусом `ok` или `already_enriched` — пропускать.

---

## OTHER-файлы по сегментам

По завершению всех кампаний сохранить OTHER-компании по сегментам:

```
sofia/projects/OnSocial/data/other/other_infplat.json
sofia/projects/OnSocial/data/other/other_imagency.json
sofia/projects/OnSocial/data/other/other_affperf.json
sofia/projects/OnSocial/data/other/other_soccom.json
```

Формат каждого файла — массив:
```json
[
  {"domain": "example.com", "company_name": "Example Inc", "campaign_id": 3215181, "evidence": "PR agency..."},
  ...
]
```

Если файл уже существует — аппендить новые записи (не перезаписывать).

---

## Параллельность

- `ThreadPoolExecutor(max_workers=5)` — 5 доменов параллельно внутри одной кампании
- Кампании обрабатывать **последовательно** (одна за другой)
- Thread-safe логирование через `threading.Lock()`

---

## Обработка ошибок — правила

| Ошибка | Действие |
|---|---|
| Exa crawl пустой | Перейти к Exa search |
| Exa search пустой | Перейти к HTTP scrape |
| HTTP scrape упал | Передать Haiku пустой контент, не останавливаться |
| Haiku fail / timeout (3 попытки) | `haiku_fail`, следующий домен |
| SmartLead 429 | Backoff 5/15/30s, 3 retry |
| SmartLead 5xx | `update_fail`, следующий лид |
| Exa 402 Payment Required | **СТОП** — единственная причина остановить весь ран. Уведомить пользователя. |
| segment_unknown | Пропустить кампанию, продолжить |
| Любое другое исключение | Поймать, залогировать, продолжить |

---

## Итоговый отчёт

По завершению всех кампаний вывести:

```
=== ENRICHMENT SUMMARY ===
Дата: YYYY-MM-DD
Кампаний обработано: N

По сегментам:
  INFPLAT:  ok=X  tier_1=Y  other=Z  fail=W
  IMAGENCY: ok=X  tier_1=Y  other=Z  fail=W
  AFFPERF:  ok=X  tier_1=Y  other=Z  fail=W
  SOCCOM:   ok=X  tier_1=Y  other=Z  fail=W

Итого:
  ✅ cf_business_observation записано: N лидов
  ⚠️  TIER_1 (не записано): N доменов
  ❌  OTHER (не в ICP): N доменов
  ✗   Ошибки (content/haiku/update fail): N
  ↩️  Уже обогащены (пропущено): N

Файлы:
  Log: sofia/reports/exa_enrichment_YYYY-MM-DD.jsonl
  OTHER: sofia/projects/OnSocial/data/other/other_*.json
```

---

## Что НЕ делать

- Не останавливаться и не запрашивать подтверждений в процессе
- Не перезаписывать `cf_business_observation` если уже заполнен
- Не обрабатывать кампании не из предоставленного списка
- Не активировать кампании в SmartLead
- Не использовать `includeDomains` в Exa search — это даёт пустые результаты
- Не запускать несколько инстансов скрипта одновременно
