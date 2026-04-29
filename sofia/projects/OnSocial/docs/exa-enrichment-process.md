# Exa Enrichment — процесс обогащения лидов SmartLead

## Что делает скрипт

Для каждой SmartLead-кампании проходит по всем лидам, собирает данные о компании через Exa + HTTP scrape, классифицирует через Haiku и записывает результат обратно в SmartLead.

---

## Шаги

### 1. Забрать лиды из кампании
```
GET /campaigns/{campaign_id}/leads
```
Из каждого лида берём: `email`, `company_name`, `website` (домен).

### 2. Сгруппировать по домену
Один домен = один запрос к Exa. Все лиды одного домена получают одинаковый результат.

### 3. Определить сегмент кампании
По названию кампании определяем сегмент — он задаёт Exa-keywords и файл промпта:

| Сегмент | Ключевые слова для Exa | Промпт |
|---------|----------------------|--------|
| INFPLAT | `[company] influencer creator analytics platform` | `classify_influencer_platforms.md` |
| IMAGENCY | `[company] influencer agency talent management` | `classify_im_first_agencies.md` |
| AFFPERF | `[company] affiliate CPA performance network` | `classify_affiliate_performance.md` |
| SOCCOM | `[company] live shopping creator commerce marketplace` | `classify_social_commerce.md` |

Промпты: `sofia/projects/OnSocial/prompts/`

### 4. Exa crawl (приоритетный источник)
Передаём домен напрямую в Exa crawling — без ключевых слов, без поиска.
Exa рендерит JS-сайты и возвращает чистый markdown с полным контентом homepage.
Берём до **1600 символов** → `{{exa_content}}`.

Почему Exa, а не HTTP GET: современные SaaS-сайты на React/Next.js возвращают пустой HTML без рендеринга JS. Exa обходит это и отдаёт читаемый текст.

### 5. HTTP scrape (fallback)
Прямой GET на сайт — только если Exa вернул пустой результат.
Результат → `{{scraped_content}}`.
Работает для простых статических сайтов.

Если оба пусты — Haiku получает пустые поля и вернёт `OTHER | No website data`.

### 6. Классификация через Haiku
Загружаем нужный промпт (из маппинга выше), подставляем переменные:
- `{{company_name}}`
- `{{employees}}` (если есть в лиде)
- `{{exa_content}}`
- `{{scraped_content}}`

Haiku возвращает: `SEGMENT | TIER | observation`

Для TIER_0 `observation` — это готовый текст в формате:
`[что делает компания] + [операционная боль с creator data] + [стоимость боли]`

Именно этот текст и записывается в `cf_business_observation` на шаге 7.

### 7. Запись результата

**SmartLead** (только целевые):
- **TIER_0** → обновляем `cf_business_observation` для всех лидов домена через SmartLead API
- **TIER_1** → `cf_business_observation` оставляем пустым
- **OTHER** → в SmartLead не пишем вообще

**OTHER → отдельные JSON-файлы по сегменту:**
По завершению работы OTHER-компании сохраняются в отдельный файл на каждый сегмент:

```
sofia/projects/OnSocial/data/other/
  other_infplat.json
  other_imagency.json
  other_affperf.json
  other_soccom.json
```

Каждый файл — массив объектов с доменом, названием компании и evidence от Haiku.

### 8. Логирование
Пишем в JSONL-файл. При перезапуске — пропускаем домены, которые уже есть в логе (идемпотентность).

---

## Структура записи в JSONL

```json
{
  "domain": "example.com",
  "company_name": "Example Inc",
  "segment": "INFLUENCER_PLATFORMS",
  "tier": "TIER_0",
  "evidence": "Creator discovery SaaS with demo CTA and 50 brand logos",
  "exa_used": true,
  "scrape_used": false,
  "processed_at": "2026-04-29T10:00:00Z"
}
```

---

## Промпты

Каждый промпт заточен под один сегмент — содержит только нужное определение + Tier 0 критерии для этого сегмента. Haiku не видит лишних сегментов.

Файлы: `sofia/projects/OnSocial/prompts/classify_*.md`
