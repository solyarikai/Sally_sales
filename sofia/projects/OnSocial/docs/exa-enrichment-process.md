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

### 4. Exa search
2 запроса на домен с сегментными keywords (без domain-фильтра).
Берём до **2 × 800 символов** контента → передаём в промпт как `{{exa_content}}`.

### 5. HTTP scrape fallback
Если Exa не вернул результат — прямой GET на сайт компании.
Результат → `{{scraped_content}}`.
Если оба пусты — Haiku получает пустые поля и вернёт `OTHER | No website data`.

### 6. Классификация через Haiku
Загружаем нужный промпт (из маппинга выше), подставляем переменные:
- `{{company_name}}`
- `{{employees}}` (если есть в лиде)
- `{{exa_content}}`
- `{{scraped_content}}`

Haiku возвращает: `SEGMENT | TIER | evidence`

### 7. Запись результата в SmartLead
- **TIER_0** → обновляем `cf_business_observation` для всех лидов домена через SmartLead API
- **TIER_1 / OTHER** → `cf_business_observation` оставляем пустым

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
