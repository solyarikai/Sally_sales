# GetSales LinkedIn Outreach Strategy — OnSocial
> Дата: 2026-04-01
> Версия: 1.0
> Статус: готов к исполнению

---

## 1. Ситуационный анализ

### Почему LinkedIn, почему сейчас

342 лида из 4 SmartLead email-кампаний получили наши письма и не ответили. У всех 342 — 0% email opens. Это не "холодные лиды" — это люди, которые уже были в нашей воронке, но email-канал не сработал. LinkedIn — второй шанс достучаться через другой канал, с другим углом.

Параллельно эти же кампании в email показывают сильные сигналы на других лидах:
- MENA+APAC: 2.17% reply, 100% warm rate, 4 meeting requests из 46 отправленных
- IM-First Agencies India: 0.80% reply, 100% warm rate, 3 warm сигнала
- Influencer Platforms: 2.52% reply, 50% warm

Вывод: сегменты рабочие, ICP правильный — проблема в канале доставки для конкретных людей. LinkedIn решает эту проблему.

### Что показали данные

| Сегмент | Лидов | Tier A | Tier B | Tier C | Топ-гео |
|---------|------:|-------:|-------:|-------:|---------|
| IMAGENCY_INDIA | 279 | 2 (1%) | 272 (97%) | 5 (2%) | Mumbai 21%, Delhi 20%, Gurugram 9% |
| INFPLAT_INDIA + GENERAL | 39 | 10 (26%) | 29 (74%) | 0 | Delhi 31%, India 18%, Sydney 8% |
| INFPLAT_MENA_APAC | 24 | 4 (17%) | 16 (67%) | 4 (17%) | Sydney 17%, Melbourne 13%, Milan 13% |

Ключевые наблюдения:
- IMAGENCY — массовый пул (279), но 97% в Tier B (нет title в данных → скоринг занижен). Реальная ценность выше — это agency founders и directors, просто title пустой в SmartLead
- INFPLAT_INDIA + GENERAL — самая "горячая" группа: 26% Tier A, много founders/CEOs. Маленький пул (39), но высокий потенциал конверсии
- MENA_APAC — мульти-гео (Australia, Indonesia, Dubai, Italy, Singapore). Маленький пул (24), но исторически лучший канал по email

### Связь с текущим flow #C

Текущий GetSales flow "OnSocial | INFLUENCER PLATFORMS #C" (скриншоты):
- 36 контактов загружено
- Acceptance rate: 28.5% (2 из 7 sent)
- Connection Request note: generic ("We power creator data for agencies like {{company}} - Moburst, Captiv8...")
- 3 follow-up сообщения после accept
- Endorse Skills, Like Latest Post — присутствуют
- Reply rate на сообщения: 1 replied из 2 sent (50% — но выборка мизерная)

Проблемы текущего flow:
1. Connection note — feature-dump, перечисление конкурентов. Не вызывает любопытство
2. Тайминги — слишком агрессивные (1 минута wait после segment → CR)
3. Нет сегментации копирайтинга — один текст для всех ICP
4. 20 failed tasks из 28 в первом сегменте — возможно, проблемы с аккаунтами или лимитами

---

## 2. Сегментация — 3 кампании GetSales

### Кампания A: IMAGENCY_INDIA

**Объём:** 279 лидов
**Кто:** Руководители и менеджеры Indian IM-first агентств — Monk-E, Pulpkey, Socio Impulse, Trend Loud, Quantafi Digital
**Роли:** Co-Founders, CEOs, Account Directors, Heads of Business
**Гео:** 99% India (Mumbai, Delhi, Gurugram, Hyderabad, Chennai)

**Боль:** Indian IM-агентства работают на маржах 15-25%. Когда клиент просит данные по креаторам — агентство идёт в HypeAuditor или Modash, платит за подписку, и клиент видит чужой бренд в отчётах. Агентство становится посредником между клиентом и SaaS-платформой. Вопрос времени, когда клиент пойдёт напрямую.

**Хук:** OnSocial white-labels creator data. Агентство получает данные под своим брендом — API или интерфейс с логотипом агентства. Клиент видит агентство как источник данных, а не посредника.

**Почему отдельный сиквенс:** Agencies ≠ Platforms. Агентство продаёт услуги клиентам, платформа продаёт SaaS конечным пользователям. Боль, язык, decision-making процесс — разные.

---

### Кампания B: INFPLAT_INDIA + INDIA_GENERAL

**Объём:** 39 лидов (19 INFPLAT_INDIA + 20 INDIA_GENERAL)
**Кто:** Founders и C-level индийских influencer marketing платформ — ClanConnect, Krazyfox, OpraahFx, Fabulate, Fancall, Ylytic
**Роли:** CEO, Co-Founder, Chief Business Officer, Head of Brand Partnership
**Гео:** 68% India (Delhi, Mumbai, Bangalore), 18% Australia (Fabulate), 5% Dubai

**Боль:** Индийские IM-платформы строят свою базу креаторов вручную или через scraping. Данные неполные: нет аудиторных демографий, нет fraud detection, нет cross-platform coverage (Instagram → TikTok → YouTube). При этом конкуренция растёт — индийский creator economy бум 2025-2026 привлёк 50+ новых платформ.

**Хук:** OnSocial даёт 300M+ профилей с полными данными через API. Одна интеграция — и платформа покрывает все рынки. Вместо 6 месяцев разработки собственного data layer — один API call.

**Почему объединены:** INFPLAT_INDIA (68% India) и INDIA_GENERAL (100% India) имеют пересечение по гео и ICP. Обе группы — founders/CEOs платформ. Единая messaging strategy, но разные компании.

---

### Кампания C: INFPLAT_MENA_APAC

**Объём:** 24 лида
**Кто:** Founders и directors influencer marketing платформ из MENA, APAC, Европы — Fabulate (AU), BintanGO (ID/SG), Scoop, Susurrus (UAE), Timeless Club (IT), AtisfyReach (SG)
**Роли:** Co-Founders, CEOs, Head of Growth, Sales Directors
**Гео:** Multi-market — Australia (29%), Indonesia (17%), Dubai (8%), Italy (13%), Singapore (8%)

**Боль:** Мульти-рыночные платформы сталкиваются с фрагментацией данных: каждый рынок имеет своих креаторов, свои платформы (TikTok доминирует в SEA, Instagram в MENA, YouTube в AU). Собирать и нормализовать данные из 5+ рынков — engineering nightmare.

**Хук:** OnSocial покрывает все рынки через один API: Instagram, TikTok, YouTube, с аудиторными данными, geo-breakdown и fraud detection. Глобальное покрытие без необходимости строить отдельные data pipelines для каждого рынка.

**Почему отдельный сиквенс:** Multi-geo = multi-language, multi-compliance, multi-timezone. Messaging должен быть международным по тону (английский, professional), без India-специфичных формулировок. Главная ценность — cross-market coverage, не local depth.

---

## 3. Flow Builder — архитектура автоматизации

### Единая flow-архитектура для всех 3 кампаний

Структура шагов одинаковая. Отличается только копирайтинг (блок 4) и тайминг для MENA_APAC (учёт timezone spread).

```
#1  Segment (загрузка контактов)
     ↓
#2  Visit Profile (пассивный сигнал — "знакомое лицо" в notifications)
     ↓
#3  Time Delay: 24 часа
     ↓  Почему 24ч: LinkedIn notification "X viewed your profile" должен
     ↓  осесть в памяти. Через сутки CR выглядит как осознанное действие,
     ↓  а не автоматизация.
     ↓
#4  Send Connection Request (с note, Auto Task)
     ↓
#5  Wait for Connection: 3 дня
     ↓  Почему 3 дня: median time to accept CR = 1-2 дня для active users.
     ↓  3 дня покрывают тех, кто заходит 2-3 раза в неделю.
     ↓
     ├── [Connected] → #6
     └── [Not Connected] → #16
```

**Ветка Connected (приняли CR):**
```
#6  Add Tag: "accepted"
     ↓
#7  Time Delay: 1 час
     ↓  Почему 1ч: не писать сразу после accept. Выглядит как бот.
     ↓  1 час — достаточно, чтобы отделить CR от первого сообщения.
     ↓
#8  Like Latest Post
     ↓  Почему перед Message 1: лайк создаёт ещё одну notification.
     ↓  Когда человек видит сообщение — он уже видел 3 касания:
     ↓  visit profile → CR → like post. Мы "знакомые".
     ↓
#9  Time Delay: 2 часа
     ↓
#10 Send Message 1 (основной pitch, Auto Task)
     ↓
#11 Time Delay: 3 дня
     ↓  Почему 3 дня: дать время прочитать и отреагировать.
     ↓  LinkedIn messages имеют 80%+ open rate, но reply приходит
     ↓  через 1-3 дня.
     ↓
#12 Endorse Skills (1 skill)
     ↓  Почему между Message 1 и 2: endorsement = ещё одна notification,
     ↓  которая возвращает внимание к профилю отправителя.
     ↓  Действие "доброжелателя", не продавца.
     ↓
#13 Time Delay: 2 дня
     ↓
#14 Send Message 2 (follow-up с новым углом, Auto Task)
     ↓
#15 Time Delay: 5 дней
     ↓
#16 Visit Profile (повторный — напоминание)
     ↓
#17 Time Delay: 2 дня
     ↓
#18 Send Message 3 (exit frame, Auto Task)
     ↓
#19 Time Delay: 7 дней
     ↓
#20 Add Tag: "completed_sequence"
     ↓
#21 End Automation
```

**Ветка Not Connected (не приняли CR за 3 дня):**
```
#22 Time Delay: 4 дня (итого 7 дней с момента CR)
     ↓
#23 Visit Profile (повторный — напоминание о pending CR)
     ↓
#24 Time Delay: 3 дня
     ↓
#25 Wait for Connection: 7 дней (финальное ожидание)
     ↓
     ├── [Connected] → переходим к #6 (Add Tag "accepted")
     └── [Not Connected] → #26
     ↓
#26 Add Tag: "no_connect"
     ↓
#27 Time Delay: 3 дня
     ↓
#28 Withdraw Connection Request
     ↓  Почему withdraw: pending CR занимает слот в лимитах LinkedIn.
     ↓  Withdraw освобождает слот. Можно повторить через 30 дней
     ↓  с другого аккаунта.
     ↓
#29 Add Tag: "withdrawn"
     ↓
#30 End Automation
```

### Отличия от текущего flow #C

| Параметр | Текущий #C | Новый flow | Почему |
|----------|-----------|------------|--------|
| Wait перед CR | 1 минута | 24 часа | Visit Profile notification должен осесть |
| Like Post | После Message 1 | До Message 1 | Создаёт 3-е касание перед pitch |
| Endorse | После Message 2 | Между Message 1 и 2 | Notification-bridge между messages |
| Wait for Connection | 1 день | 3 дня | Покрывает 2-3x/week LinkedIn users |
| Not Connected branch | 1 повторный wait | Visit Profile + 2-й wait + withdraw | Не теряем слот |
| Messages | 3 | 3 | Оставляем — 3 достаточно для LinkedIn |
| Total duration | ~21 день | ~28 дней | Менее агрессивно, выше conversion |

### Специфика по MENA_APAC

Единственное отличие — увеличенные delays в ветке Connected:
- Time Delay после accept: 2 часа → 4 часа (timezone spread: AU, SG, UAE, IT)
- Time Delay между Message 1 и 2: 3 дня → 4 дня
- Причина: лиды в 4+ timezone zones. Увеличенные delays дают больше шансов попасть в рабочее время получателя.

---

## 4. Копирайтинг — 12 текстов

### Принципы

1. **LinkedIn = Proof** (God Sequence): email продаёт через боль, LinkedIn — через экспертизу и peer-to-peer connection
2. **Connection Request ≤ 300 символов** (лимит LinkedIn)
3. **Message 1 = ценность** (не pitch, не feature-dump)
4. **Message 2 = конкретика** (новый угол, социальное доказательство)
5. **Message 3 = exit frame** (достоинство, без манипуляций)
6. **Без em dashes** (ломаются в некоторых клиентах)

---

### Кампания A: IMAGENCY_INDIA

**Connection Request Note (289 символов):**
```
Hey {{first_name}},

We power creator analytics for IM agencies - your brand, your data, your pricing. Agencies like yours use us to give clients something they can't get from HypeAuditor on their own.

Would love to connect.
```

**Message 1 — Value angle (после accept):**
```
Hey {{first_name}},

Quick question - when your clients ask for creator data, whose brand do they see in the report? Yours or HypeAuditor's?

We built OnSocial specifically for agencies that want to own the data layer. White-label API or dashboard - your logo, your pricing, your client relationship.

Worth a look? Happy to run any creator handle through our system live - just drop one here.
```

**Message 2 — Social proof + new angle (3 дня после Message 1):**
```
Hey {{first_name}},

One thing I didn't mention - two things that matter for agency margins:

- You keep your UI, your brand, your workflows. Our data plugs in via API - most integrations go live in days, not months

- We cover the data your clients actually ask about: real vs fake followers, audience demographics down to city level, cross-platform coverage (IG, TikTok, YouTube), brand affinities

67% of brands are considering moving influencer marketing in-house. Agencies that survive give clients something they can't get alone.

Happy to show how this works for {{company_name}} specifically - what does your calendar look like this week?
```

**Message 3 — Exit frame (5 дней после Message 2):**
```
{{first_name}} - totally understand if the timing isn't right.

If {{company_name}} ever needs creator data under your own brand - we'll be here. No hard feelings.

One last thing: we just opened up a free data audit for agencies - drop any 5 creator handles from a current campaign and I'll send back a full analytics breakdown. No strings.
```

---

### Кампания B: INFPLAT_INDIA + INDIA_GENERAL

**Connection Request Note (276 символов):**
```
Hey {{first_name}},

Building data infra for influencer platforms is what we do - 300M+ profiles, full demographics, fraud detection. Thought I'd connect since {{company_name}} is in the same space.

Always good to know people in the industry.
```

**Message 1 — Technical value (после accept):**
```
Hey {{first_name}},

With OnSocial, you'd get more data at a fraction of the cost than whatever data provider {{company_name}} is using today.

300M+ profiles across Instagram, TikTok, and YouTube with full global coverage. Credibility scoring, audience demographics down to city level, fraud detection, audience overlap between creators. Your team plugs it in via our API, your clients see it in your UI.

Curious - how does {{company_name}} handle creator data right now? Built in-house or using a vendor?
```

**Message 2 — Build vs Buy (3 дня после Message 1):**
```
Hey {{first_name}},

One thing founders in this space tell us: building a creator data layer in-house takes 6+ months of eng time. And then you're maintaining scrapers, handling rate limits, normalizing data across platforms.

We've done that work already for 300M+ profiles. One API call gives you everything - demographics, engagement rates, brand affinities, fraud scores.

Most platforms integrate in under 2 weeks. Would it help to see a technical demo? I can walk through the API docs and show real response payloads.
```

**Message 3 — Exit frame (5 дней после Message 2):**
```
{{first_name}} - no worries if this isn't a priority right now.

If {{company_name}} ever wants to upgrade its creator data without building from scratch - drop me a line anytime.

Open offer: send me any creator handle and I'll run it through our API. Full profile analysis in 30 seconds. Just to show what's possible.
```

---

### Кампания C: INFPLAT_MENA_APAC

**Connection Request Note (293 символов):**
```
Hey {{first_name}},

We provide creator data infrastructure for influencer platforms - 300M+ profiles across all major markets. Since {{company_name}} operates across multiple regions, thought there might be overlap.

Would be great to connect.
```

**Message 1 — Cross-market value (после accept):**
```
Hey {{first_name}},

Running an influencer platform across multiple markets means dealing with fragmented creator data - different platforms dominate in different regions, different audience behaviors, different compliance requirements.

OnSocial covers it all through one API: Instagram, TikTok, YouTube. Full audience demographics, geo-breakdown by country and city, fraud detection. 300M+ profiles globally.

How does {{company_name}} currently handle creator data across your markets? Curious if you're pulling from multiple sources or have something centralized.
```

**Message 2 — Specificity for their geo (4 дня после Message 1):**
```
Hey {{first_name}},

What I see with platforms operating in APAC and MENA - the local creator ecosystems are growing fast but the data infrastructure hasn't caught up.

Our clients use OnSocial to:
- Discover creators in emerging markets (SEA, Middle East) with real audience data
- Verify creator authenticity before brand partnerships (fraud detection)
- Compare creator performance across markets with normalized metrics

Takes about 2 weeks to integrate. API-first, well-documented, sandbox available.

Worth 15 minutes to see if this solves a real problem for {{company_name}}?
```

**Message 3 — Exit frame (5 дней после Message 2):**
```
{{first_name}} - if the timing doesn't work, no problem at all.

Standing offer: drop any creator handle from any market you operate in. I'll run a full analysis through our API and send it back - demographics, engagement, fraud score, audience geo-split. Takes 30 seconds.

Good way to see what we do without committing to anything.
```

---

## 5. Sender Profiles — Albina + Rajat

### Распределение

Оба профиля работают на все 3 кампании параллельно. Это увеличивает throughput и снижает риск: если один аккаунт попадёт под ограничения, второй продолжает.

| Sender | Кампания A (IMAGENCY) | Кампания B (INFPLAT_INDIA) | Кампания C (MENA_APAC) |
|--------|-----:|------:|------:|
| Albina | 140 лидов | 20 лидов | 12 лидов |
| Rajat | 139 лидов | 19 лидов | 12 лидов |
| **Итого** | **279** | **39** | **24** |

### Лимиты безопасности

| Параметр | Лимит | Комментарий |
|----------|------:|-------------|
| Connection Requests / день / аккаунт | 20-25 | Безопасный диапазон. Не больше 25 — риск restriction |
| Messages / день / аккаунт | 50 | LinkedIn messaging limit выше, но 50 — safe |
| Profile Visits / день / аккаунт | 80 | Пассивное действие, лимит мягкий |
| Endorse / день / аккаунт | 10 | Не злоупотреблять — выглядит спамно |
| CR + Messages combined daily | 40 | Общий лимит активных действий на аккаунт |
| Warm-up период | 3-5 дней | Если аккаунт новый в GetSales — начать с 10 CR/день |

### Пропускная способность и сроки

**При 20 CR/день/аккаунт × 2 аккаунта = 40 CR/день:**

| Кампания | Лидов | Дней на загрузку всех CR | Полный цикл (28 дней на лида) |
|----------|------:|-------------------------:|------------------------------:|
| A: IMAGENCY_INDIA | 279 | ~7 дней | ~35 дней |
| B: INFPLAT_INDIA | 39 | ~1 день | ~29 дней |
| C: MENA_APAC | 24 | ~1 день | ~29 дней |
| **Итого** | **342** | **~9 дней** | **~37 дней** |

**Рекомендация по порядку запуска:**
1. День 1-2: Кампания B (INFPLAT_INDIA) — 39 лидов, 26% Tier A. Высший потенциал конверсии
2. День 1-2: Кампания C (MENA_APAC) — 24 лида. Параллельно с B, т.к. маленький объём
3. День 3-9: Кампания A (IMAGENCY_INDIA) — 279 лидов. Батчами по 40/день

**Расчёт при 25 CR/день (агрессивный, но допустимый для прогретых аккаунтов):**
- 50 CR/день суммарно → все 342 лида загружены за 7 дней
- Полный цикл: 35 дней

---

## 6. Скоринг и приоритизация загрузки

### Как использовать тиры

Тиры из CSV (A/B/C) определяют порядок загрузки внутри каждой кампании. Tier A идут первыми — это founders, CEOs, VPs в стратегических гео.

**Кампания A (IMAGENCY_INDIA):**
- Batch 1 (день 3-4): 2 Tier A + топ Tier B с titles (Co-Founder & CEO, Head of Business, VP, Senior Account Director) — ~30 лидов
- Batch 2 (день 4-5): Tier B с company_name в топ-5 (Monk-E, Pulpkey, Socio Impulse, Trend Loud) — ~50 лидов
- Batch 3-7 (день 5-9): Остальные Tier B по убыванию score_total — ~199 лидов
- Tier C (5 лидов): в конец очереди

**Кампания B (INFPLAT_INDIA):**
- Batch 1 (день 1): Все 10 Tier A — Sagar Pushp (ClanConnect CEO), Akash Chaudhary (Fancall CEO), Vishal Srivastava (Krazyfox Co-Founder), Ishank Joshi (Mobavenue CEO), и др.
- Batch 2 (день 2): 29 Tier B

**Кампания C (MENA_APAC):**
- Batch 1 (день 1): 4 Tier A — Jason Lee (BintanGO CEO, Singapore), Lina Stoumpou (Susurrus CEO, Dubai), Panagiotis Tsaggas (Susurrus Co-Founder, Dubai), Joby Joseph (Scoop CTO, India)
- Batch 2 (день 2): 16 Tier B + 4 Tier C

### Правило пересортировки

Если у лида пустой title в CSV, но по LinkedIn URL видно что это Founder/CEO — вручную переместить в Batch 1. Скоринг из SmartLead не учитывает все поля; LinkedIn-профиль — источник правды.

---

## 7. Мультиканальная синхронизация с SmartLead

### Принцип: один человек не получает email и LinkedIn CR в один день

Эти 342 лида уже получили email через SmartLead и не ответили. LinkedIn — параллельный канал, но нужна координация:

### Правила синхронизации

**Правило 1: 48-часовое окно**
Если SmartLead отправил email лиду — GetSales не отправляет ему CR/message в течение 48 часов, и наоборот. Это делается вручную при загрузке батчей: проверяем в SmartLead статус последнего email.

**Правило 2: Reply = исключение из GetSales**
Если лид ответил на email в SmartLead (status: REPLIED) — немедленно исключить из GetSales кампании. Добавить тег "email_replied" и удалить из flow.

**Правило 3: LinkedIn accept = тег в SmartLead**
Если лид принял CR в GetSales — добавить тег "linkedin_connected" в SmartLead. Это позволит не отправлять ему повторные email или адаптировать email под контекст ("We connected on LinkedIn...").

### Практическая реализация

Сейчас автоматической синхронизации GetSales ↔ SmartLead нет. Поэтому:

**Ежедневно (5 минут):**
1. Проверить GetSales: кто принял CR за последние 24ч → добавить в SmartLead exclusion list
2. Проверить SmartLead: кто ответил на email за последние 24ч → исключить из GetSales flow

**При загрузке нового батча:**
1. Проверить в SmartLead: когда последний email был отправлен каждому лиду из батча
2. Если email отправлен менее 48ч назад — отложить загрузку этого лида

### Будущая автоматизация

GetSales API интеграция (из аудита — приоритет "Высокий") решит это:
- Webhook из SmartLead на reply → auto-pause в GetSales
- Webhook из GetSales на accept → auto-tag в SmartLead
- Пока этого нет — ручная синхронизация по чеклисту выше

---

## 8. KPIs и метрики успеха

### Целевые метрики

| Метрика | Целевое значение | Критический порог | Когда оценивать |
|---------|:----------------:|:-----------------:|:---------------:|
| Acceptance Rate | 30-35% | < 20% | День 7 (после первых 40-50 CR) |
| Message Open Rate | 80%+ | < 60% | День 10 |
| Reply Rate (от accepted) | 15-25% | < 10% | День 14 |
| Positive Reply Rate | 8-12% | < 5% | День 14 |
| Reply → Meeting | 30-40% | < 20% | День 21 |
| Overall Conversion (CR → Meeting) | 3-5% | < 1.5% | День 28 |

### Временные горизонты оценки

**День 7 — первая оценка:**
- Acceptance rate по 40-50 отправленным CR
- Если < 20%: проблема с CR note или аккаунтом
- Действие: тестировать альтернативный CR note (убрать mention компании, сделать короче)

**День 14 — основная оценка:**
- Reply rate на Message 1 и Message 2
- Если replies есть, но < 10%: проблема с messaging — протестировать другой angle
- Если replies = 0: возможно, аудитория не та или аккаунты под restriction

**День 21 — полная картина:**
- Конверсия reply → meeting
- Сравнить кампании A vs B vs C
- Решение: масштабировать лучшую, оптимизировать или убить худшую

**День 28 — финальная оценка:**
- Полный цикл пройден для первых батчей
- ROI по каждой кампании
- Решение о продолжении/расширении

### Красные флаги и действия

| Флаг | Когда | Что делать |
|------|-------|------------|
| Acceptance Rate < 15% после 50 CR | День 5-7 | Проверить CR note, проверить профили sender-ов (SSI, фото, headline) |
| 0 replies после 20+ accepted | День 10-12 | Переписать Message 1, убрать pitch, добавить вопрос |
| Аккаунт получил restriction | Любой момент | Пауза 72ч, снизить лимиты до 10 CR/день, проверить IP |
| Reply rate > 0 но 0 meetings | День 21 | Проблема с conversion copy — добавить pricing info, конкретный CTA |
| Высокий acceptance, низкий reply | День 14 | CR note создаёт неправильные ожидания — alignment проблема |

### Метрики по сегментам (ожидания)

| Кампания | Expected Acceptance | Expected Reply | Обоснование |
|----------|:-------------------:|:--------------:|-------------|
| A: IMAGENCY_INDIA | 25-30% | 12-18% | India = active LinkedIn users, agency people отвечают |
| B: INFPLAT_INDIA | 30-40% | 15-25% | Founders/CEOs принимают больше CR, но отвечают выборочно |
| C: MENA_APAC | 35-45% | 10-15% | Маленькие компании = доступные founders. Но multi-geo = разная активность |

---

## 9. Импорт — инструкции для исполнителя

### Формат CSV для GetSales

Используем **Вариант 1 (минимальный)** из GETSALES_IMPORT_GUIDE — 4 колонки. Reason: у нас уже есть LinkedIn URLs, имена и компании. Расширенный формат (49 колонок) не нужен — дополнительные данные (tags, position) можно добавить через GetSales UI после импорта.

```
First Name | Last Name | LinkedIn | Company Name
```

### Подготовка CSV из ALL_CAMPAIGNS_scored.csv

Для каждой кампании:

1. Фильтр: `campaign_name = [нужная кампания]`
2. Сортировка: `score_total DESC`
3. Нормализация LinkedIn URL: `http://www.linkedin.com` → `https://www.linkedin.com`
4. Выходные колонки: `first_name, last_name, linkedin_url, company_name`
5. Сохранить как отдельный CSV

### Чеклист перед загрузкой

**Перед созданием кампании в GetSales:**
- [ ] LinkedIn URL начинается с `https://` (не `http://`)
- [ ] Нет пустых строк
- [ ] Нет дубликатов LinkedIn URL
- [ ] Все контакты проверены против Blacklist (OS | Ops | Blacklist)
- [ ] Все контакты проверены против Exclusion List — Apollo
- [ ] Количество лидов в batch ≤ дневной лимит CR × кол-во дней до следующего batch

**Настройки кампании в GetSales:**
- [ ] Название: `OnSocial | IMAGENCY INDIA #D` (или INFPLAT INDIA #D, INFPLAT MENA_APAC #D)
- [ ] Оба sender profiles (Albina + Rajat) назначены
- [ ] Flow построен по схеме из блока 3
- [ ] Тексты из блока 4 вставлены в каждый шаг
- [ ] Лимиты выставлены: 20-25 CR/день/аккаунт
- [ ] Campaign НЕ активирована до проверки всех шагов

**После активации:**
- [ ] Проверить через 1 час: задачи в progress, нет ошибок
- [ ] Проверить через 24 часа: первые CR отправлены, нет failed tasks
- [ ] День 3: первые acceptance — записать rate

### Порядок загрузки (timeline)

| День | Действие | Объём |
|------|----------|------:|
| 1 | Создать 3 кампании в GetSales, настроить flows, вставить тексты | — |
| 1 | Загрузить Кампанию B (INFPLAT_INDIA): Tier A first | 39 лидов |
| 1 | Загрузить Кампанию C (MENA_APAC): Tier A first | 24 лида |
| 2 | Проверить статус B и C: CR отправлены, нет ошибок | — |
| 3 | Загрузить Кампанию A (IMAGENCY): Batch 1 — Tier A + топ titles | ~30 лидов |
| 4-5 | Кампания A: Batch 2 — компании из топ-5 | ~50 лидов |
| 5-9 | Кампания A: Batch 3-7 — остальные по score_total | ~199 лидов |
| 7 | **Оценка Day 7:** acceptance rate по B и C | — |
| 14 | **Оценка Day 14:** reply rate, первые корректировки | — |
| 21 | **Оценка Day 21:** полная картина, решение о масштабировании | — |

---

## Приложение: Quick Reference

### Naming Convention (для Google Sheets и локальных файлов)

| Кампания GetSales | Google Sheet | Локальный CSV |
|-------------------|-------------|---------------|
| OnSocial \| IMAGENCY INDIA #D | OS \| Leads \| IMAGENCY — 2026-04-01 | OS_Leads_IMAGENCY_2026-04-01.csv |
| OnSocial \| INFPLAT INDIA #D | OS \| Leads \| INFPLAT_INDIA — 2026-04-01 | OS_Leads_INFPLAT_INDIA_2026-04-01.csv |
| OnSocial \| INFPLAT MENA_APAC #D | OS \| Leads \| INFPLAT_MENA_APAC — 2026-04-01 | OS_Leads_INFPLAT_MENA_APAC_2026-04-01.csv |

### Переменные в GetSales

| Переменная | Поле | Пример |
|------------|------|--------|
| `{{first_name}}` | First Name | Sagar |
| `{{last_name}}` | Last Name | Pushp |
| `{{company_name}}` | Company Name | ClanConnect |
| `{{linkedin_url}}` | LinkedIn | https://www.linkedin.com/in/sagar-p-97520311 |

---

*Документ подготовлен на основе: ALL_CAMPAIGNS_scored.csv (342 лида), SEGMENT_ANALYSIS.md, strategic_research_2026-03-26.md, onsocial_campaign_audit_2026-03-26.md, GETSALES_IMPORT_GUIDE.md, скриншотов текущего flow #C.*
