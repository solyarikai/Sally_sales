# Exa Enrichment Report — AFFPERF + INFPLAT T2/T3
Generated: 2026-04-29  
Script: `sofia/scripts/icebreaker_exa_enrich.py`  
Log: `sofia/reports/icebreaker_exa_2026-04-29.jsonl`

---

## Процесс (как работает)

Для каждой кампании скрипт:
1. **Забирает все лиды из SmartLead** (GET `/campaigns/{id}/leads`)
2. **Группирует по домену** — один домен = один Exa-запрос
3. **Exa search** — 2 запроса по имени компании + keywords (`influencer creator affiliate marketing`), без domain-фильтра. Берёт до 2×800 символов контента
4. **HTTP scrape fallback** — если Exa не дал результата, прямой GET на сайт
5. **Haiku** (`claude-haiku-4-5-20251001`) — генерирует opener по формуле `[что делает компания] + [операционная боль с creator data] + [стоимость боли]`. Если нет специфичного сигнала — SKIP
6. **Обновляет `cf_business_observation`** через SmartLead API для всех лидов домена
7. **Логирует в JSONL** — идемпотентно, при перезапуске пропускает уже обогащённые домены

---

## Результаты

| Кампания | ID | OK | Skip | Content Fail | Total domains | Хит-рейт |
|---|---|---|---|---|---|---|
| AFFPERF | 3215181 | 3 | 82 | 13 | 98 | **3%** |
| INFPLAT T2 | 3215316 | 6 | 51 | 4 | 61 | **10%** |
| INFPLAT T3 | 3215317 | 4 | 29 | 0 | 33 | **12%** |
| **ИТОГО** | | **13** | **162** | **17** | **192** | **7%** |

*(IMAGENCY — отдельный ран: 37 ok / 246 skip / 48 fail из 331 leads, 11%)*

---

## Успешные наблюдения (13 ok)

### AFFPERF (3 leads)

**ginga.ag**  
> Managing creator operations at your scale for brands like Mercado Livre means manually verifying audience quality and reconciling creator data across IG and TikTok before each brand activation — overhead that compounds across every campaign cycle.

**boostified.se**  
> Brands managing UGC campaigns through your platform still verify creator audiences manually across Instagram, TikTok, and YouTube before adding them — 3 logins and manual reconciliation before each collaboration can actually move forward.

**drim.one**  
> Matching 250K+ microinfluencers to brand requirements across 8 platforms requires verifying audience authenticity across Instagram, TikTok, and YouTube — which typically means separate logins and vendor data pulls before each campaign launch.

---

### INFPLAT T2 (6 leads)

**bump.fr**  
> Pitching 60 exclusive creators across YouTube, Instagram, TikTok, and Twitch to brands requires manually pulling audience data from 4-5 separate sources and reconciling numbers whenever a creator spans multiple platforms — this manual verification step happens before every client brief.

**favored.live**  
> Recruiting affiliate creators for livestream shopping at scale means manually verifying audience authenticity and size across Instagram, TikTok, and YouTube before each onboarding — typically pulling data from multiple platforms before the partnership goes live.

**sociata.com**  
> Managing creator campaigns for MENA brands across IG, TikTok, and YouTube requires verifying audience quality and fraud signals before every brief — and keeping that data current across 3 platform APIs typically means building expensive integrations or relying on periodic data exports.

**the-secret-society.com**  
> Matching 150,000+ creators with venue partners across 8 cities requires verifying audience authenticity and brand-fit before each placement — something currently happening manually across separate IG and TikTok profiles.

**creatorsociety.com**  
> Managing creator-brand partnerships for affiliate programs means verifying each creator's audience across IG and TikTok for brand fit and fraud signals — a process that typically requires reconciling data across 2-3 vendor platforms before onboarding.

**lessie.ai**  
> Creator search tools across Instagram, TikTok, YouTube, and Twitter pull audience metrics from 5 platforms with different update intervals — and maintaining those integrations as APIs constantly change locks engineering into data work instead of product development.

---

### INFPLAT T3 (4 leads, включая дубль gamesight.io)

**gamesight.io** (×2 leads)  
> Matching game studios with creators through your programs at scale means vetting 10K+ influencer relationships annually — and confirming audience quality and game brand-fit for each creator involves manual research across IG, TikTok, and YouTube before every partnership.

**whalar.com**  
> Sourcing creators for premium global campaigns across IG, TikTok, and YouTube requires manually verifying audience quality and brand safety before each contract — a vetting process that happens creator-by-creator and delays campaign launches.

**hummingbirds.com**  
> Sourcing local creators for retail performance campaigns requires verifying that each creator's audience is actually concentrated in your target regions and demographics before contracts go out — a check that typically happens manually across IG and TikTok data outside your platform.

---

## Анализ: почему низкий хит-рейт

### AFFPERF — 3% (самый низкий)
База содержит много off-ICP компаний:
- Телеком/энергетика: `enel.com`, `freedomnet.nl`
- Корпораты без creator-контекста: `genesys.com`, `cegeka.com`, `lulus.com`
- Gambling/фин-тех: `entaingroup.com`, `rewardsnetwork.com`
- Generic маркетинг без influencer-специфики: 60+ доменов

### INFPLAT T2 — 10%
Более релевантная база, но много:
- SaaS без creator-вертикали: `clever.com`, `hive.com`, `mimik.com`
- Малые стартапы с нулевым публичным контентом
- Off-ICP: `imf.org`, `lussostone.com`, `kanefootwear.com`

### INFPLAT T3 — 12% (лучший)
Наиболее целевая база. Основные причины skip:
- Компании с релевантным доменом но без публичного creator-контента (storyclash, tubularlabs — известные платформы, но Exa не вернул достаточно текста)
- `walmart.com` — too big, generic signal

### Content fail (17 доменов)
Сайты недоступны или блокируют скрейпинг. Среди них есть потенциально релевантные: `atisfyreach.com`, `hypelinks.io`.

---

## Skip-домены для ручного разбора (потенциально релевантные)

Из 162 skip — часть имеют релевантные названия. Рекомендации по каждой кампании:

### AFFPERF — возможно релевантные из skip
`seen.io`, `sociability.app`, `stratmedia.io`, `smashloud.com`, `lockedinmedia.com`, `lookbooklink.com`

### INFPLAT T2 — возможно релевантные из skip
`fame.so`, `channelmeter.com`, `livad.stream`, `kawo.com`, `shopvision.ai`, `hypefy.ai`, `clip.mx`, `pickmyad.com`, `pixocial.com`

### INFPLAT T3 — возможно релевантные из skip
`storyclash.com`, `tubularlabs.com`, `audiencewatch.io`, `livewire.group`, `gamesquare.com`, `buzzmonitor.com.br`, `streamelements.com`, `opus.pro`

---

## Следующие шаги

1. **Sequences** — написать email-последовательности для AFFPERF + INFPLAT T2/T3
2. **SmartLead upload** — загрузить sequences + Variant B с `{{cf_business_observation}}`
3. **UI (ручные действия)**:
   - Активировать кампании
   - `send_as_plain_text = true`, `enable_ai_esp = true`, tracking off
   - Переименовать 3215316 → `[T2-BER]`, 3215317 → `[T3-BER]`
4. **Опционально**: ручной review skip-доменов выше → +10-15 personalized openers
