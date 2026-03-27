# OnSocial Strategic Research Report
> Дата: 2026-03-26
> Метод: 7 параллельных агентов-исследователей + структурированное интервью с оператором
> Охват: ~610K токенов исследования, синтезировано в единый документ

---

## Executive Summary

**Статус проекта:** 8 дней с момента запуска #C кампаний (18-19 марта). 5 booked meetings → 3 SQL (Bhaskar квалифицировал после звонка). KPI: 10 SQLs/мес. Текущий темп: ~11 SQLs/мес — **на траектории**.

**Главные находки:**
1. **MENA+APAC — 10x выше конверсия** чем US/EU (8.7% в meeting vs 0.05%). Ненасыщенный рынок.
2. **13-18 встреч потеряно** за первый месяц из-за отсутствия скриптов обработки ответов (6.1% reply→meeting при норме 15-25%)
3. **Каша в сиквенсах** — нет трекинга какой копирайт в какой кампании, не все #C на v3
4. **TAM по SaaS-платформам почти исчерпан** (10K sent из ~3-6K компаний). Рост — через новые гео и keywords
5. **Система magnum-opus недоиспользована** — Campaign Intelligence, prompt tracking, multiple source adapters, auto-pause не активны

---

## Часть 1: Анализ кампаний SmartLead

### Рейтинг эффективности

| # | Кампания | Reply % | Warm Rate | Meetings | Вердикт |
|---|----------|--------:|----------:|---------:|---------|
| 1 | INFLUENCER PLATFORMS MENA+APAC #C | 2.17% | **100%** | 4 | **ЗОЛОТО** — масштабировать |
| 2 | INFLUENCER PLATFORMS #C | 2.52% | 50% | 3 | Масштабировать |
| 3 | IM agencies & SaaS_US&EU | 2.01% | 10% | ~12 warm | Флагман, но разбить на подсегменты |
| 4 | IM-FIRST AGENCIES INDIA #C | 0.80% | **100%** | 3 | Масштабировать |
| 5 | platforms_1203 (LinkedIn) | — | **78%** | 1 | Изучить copy, воспроизвести |

### Мёртвые кампании (немедленно отключить)

| Кампания | Sent | Positive | Проблема |
|----------|-----:|--------:|----------|
| 1103_PR_firms | 433 | 0 | PR не в ICP |
| 0903_PLATFORMS | 915 | 0 | Старый копирайт, мёртвый |
| 0903_AGENCIES | 1,122 | 0 | Старый копирайт, мёртвый |
| MARKETING_AGENCIES | 604 | 0 | Generic SMM, не IM |
| IM-FIRST AGENCIES EUROPE #C | 468 | 0 | Европа молчит |
| AFFILIATE & PERFORMANCE #C | 348 | 0 | Wrong person + unsub |
| INDIA #C (обе) | 271 | 0 | Платформы ≠ агентства в Индии |
| UK_EU #C | 200 | 0 | Мало данных, но тренд нулевой |

**Суммарно освобождается:** ~19,645 лидов + ёмкость отправки

### Географический паттерн

| Регион | Работает | Не работает | Гипотеза |
|--------|----------|-------------|----------|
| MENA+APAC | Платформы (8.7% → meeting) | — | Мало конкурентов, растущий рынок |
| India | Агентства (100% warm) | Платформы (0%) | Агентства ищут инструменты; платформы — конкуренты |
| US+EU mixed | Флагман (2% reply) | — | Работает, но размыт — разбить |
| Europe solo | — | Всё (0% reply) | GDPR-настороженность, зрелый рынок |
| LATAM | 1 interested / 109 | — | Слишком рано судить |

---

## Часть 2: Воронка и потери

### Текущая воронка (8 дней #C кампаний)

```
~10,000 emails sent (все кампании)
     ↓
~153 replies (1.53% reply rate)
     ↓
~47 тёплых сигналов (interested/question/meeting)
     ↓
~9 booked meetings (6.1% reply→meeting)
     ↓  [только #C период: ~5 booked]
~5 held meetings
     ↓
3 SQLs (60% hold→SQL)
```

### Где теряются лиды

| Этап | Текущий | Бенчмарк | Потери | Причина |
|------|---------|----------|--------|---------|
| Reply rate | 1.53% | 3-4% SaaS | ~150 replies/мес упущено | Длинные письма, feature-dump, слабые subject lines |
| Reply→Meeting | 6.1% | 15-25% | **13-18 meetings/мес** | 70% просили pricing — CTA был только "book a call" |
| Meeting→SQL | 60% | 50-70% | Нормально | Bhaskar хорошо квалифицирует |

**Ключевой bottleneck: reply→meeting.** При 15% конверсии вместо 6.1% — это 22+ meetings вместо 9. При 60% SQL rate = 13 SQLs вместо 5. KPI выполняется с запасом.

### Правило 500 писем — нарушения

Sally: "500 emails без warm reply → немедленная пауза."

| Кампания | Sent | Перерасход |
|----------|-----:|----------:|
| 0903_AGENCIES | 1,122 | 622 писем |
| 0903_PLATFORMS | 915 | 415 писем |
| MARKETING_AGENCIES | 604 | 104 писем |
| **Итого** | | **1,141 писем в пустоту** |

---

## Часть 3: Отклонения от best practices Sally

### Критические отклонения

| # | Sally стандарт | OnSocial реальность | Влияние |
|---|---------------|---------------------|---------|
| 1 | JTBD-вопрос в Email 1 | Icebreaker + feature-dump | Reply rate ниже на 30-50% |
| 2 | Email 3: "2 problems where competitors fail" | "If not on radar, no worries" | Нет финального удара |
| 3 | A/B тест: менять ONE thing | A/B варианты идентичны | Месяц слепой работы |
| 4 | 500 emails → 0 warm = пауза | Продолжали до 1,122 | 1,141 писем потеряно |
| 5 | MillionVerifier перед каждой отправкой | Не используется | Bounce rate не контролируется |
| 6 | Еженедельная чистка SmartLead (пятницы) | Не проводится | 18,679 лидов на паузе |
| 7 | 25 компаний руками перед запуском сегмента | Не задокументировано | Качество списка не валидировано |
| 8 | Subsequences в SmartLead | Не настроены | Нет автоматических follow-up цепочек |
| 9 | Thunderbird/Spark для пропущенных replies | Не настроен | Потерянные ответы вне SmartLead |
| 10 | #review-sequences в Slack | Нет peer review | Качество копирайта не проверяется |

### Отклонения средней критичности

| # | Стандарт | Реальность |
|---|----------|------------|
| 11 | Разные subject lines per segment | Одинаковые ("Creator data API for {company}") |
| 12 | Нет трекинга какой копирайт где | "Каша" (ответ оператора) |
| 13 | ICP sheet утверждён клиентом | Нет формального JTBD alignment |
| 14 | LinkedIn SSI мониторинг | Нет данных |
| 15 | Multi-channel synergy (email+LinkedIn) | Каналы работают изолированно |

---

## Часть 4: Cold Outreach — Индустриальные бенчмарки 2026

### Email

| Параметр | Бенчмарк | OnSocial | Статус |
|----------|----------|----------|--------|
| Reply rate (SaaS B2B) | 3-5% (средний), 5-8% (хороший) | 1.53% | Ниже среднего |
| Длина письма | 75-100 слов (пик: 3.8% reply) | 80-100 слов | Норма |
| Формат | Plain text only | Plain text | Правильно |
| Touchpoints в sequence | 4-7 писем | 3 | Мало — добавить 1-2 follow-up |
| Лучший день отправки | Вторник-Среда | Нет данных | Проверить |
| Лучшее время | 10:00-12:00 в TZ получателя | Нет данных | Настроить |

### LinkedIn

| Параметр | Бенчмарк | OnSocial | Статус |
|----------|----------|----------|--------|
| CR acceptance rate | 24-30% | Нет данных | Начать трекать |
| Reply rate после accept | 25-35% | 3.52% (общий) | platforms_1203 = 78% warm |
| Voice notes | +30-40% к reply rate | Не используются | Рекомендуется |
| Безопасный лимит | 20-40 CR/день/аккаунт | 3 аккаунта | ~60-120 CR/день возможно |

### Для технических DM (CTO/VP Eng)

**Что работает:**
- Problem-first подход (не feature-dump)
- Конкретные метрики: "300M profiles, 50ms p95, 15 min integration"
- Developer-friendly CTA: sandbox, API playground, curl-примеры
- "Build vs Buy" фрейминг: "6 мес eng time OR 1 API call"

**Что убивает:**
- Feature dumps ("We have X, Y, Z, A, B, C")
- Маркетинговый язык ("revolutionary", "game-changing")
- Тяжёлые CTA на первом касании ("Book a 30-min demo")

---

## Часть 5: God Sequence Blueprint

### Принцип

Каждый канал — свой угол атаки:
- **Email** = Pain (вопрос о процессе)
- **LinkedIn** = Proof (peer-to-peer, социальное доказательство)
- **Telegram** = Urgency (только India/CIS/MENA)

### Универсальная раскладка

| День | Канал | Действие | Цель |
|------|-------|----------|------|
| 0 | Email | Touch 1: Pain-based вопрос + soft CTA | Открыть диалог |
| 2 | LinkedIn | View Profile (пассивный сигнал) | "Знакомое имя" |
| 4 | Email | Touch 2: Social proof + кейс + demo offer | Доказать ценность |
| 5-6 | LinkedIn | Connection Request (с заметкой, НЕ копия email) | Личный канал |
| 8 | Email | Touch 3: Exit frame + redirect question | Закрыть email-цикл |
| 11 | LinkedIn | Message (только если приняли CR) | Новый угол |
| 14 | Telegram | ТОЛЬКО India/CIS/MENA | Финальный шанс |

### Вариации по сегменту

**INFLUENCER_PLATFORMS (CTO, VP Eng):** Email-first. Технические DM читают email осознанно.
- Email 1: "Your data layer — yours or vendor?"
- LinkedIn CR: "Building data infra for IM platforms — thought I'd connect"
- LinkedIn Msg: "Drop any creator handle — I'll run it through our API live"

**AFFILIATE_PERFORMANCE (VP Partnerships):** LinkedIn-first для partnership roles.
- LinkedIn CR: "We help affiliate platforms verify creator quality before payouts"
- Email 1: "How do you verify a creator partner will drive real conversions?"

**IM_FIRST_AGENCIES (CEO, Founder):** Email-heavy + fear angle.
- Email 1: "When client asks for creator data — do they see YOUR brand or HypeAuditor?"
- Email 2: "67% brands going in-house. Agencies that survive give something they can't get alone"
- LinkedIn CR: "We white-label creator data for IM agencies (your logo, your pricing)"

### CTA Progression

| Touch | CTA | Механика |
|-------|-----|----------|
| Email 1 | "Worth a look?" | Вопрос — легче ответить чем "book a call" |
| Email 2 | "Drop a handle — I'll run it live. Or: calendar link" | Low + high commitment |
| Email 3 | "Wrong person or wrong time?" | Exit frame — безопасный CTA |
| LinkedIn CR | Нет CTA | CR с CTA = acceptance падает |
| LinkedIn Msg | "Drop a handle — I'll demo live" | Демонстрация > обещание |

### Pricing Response (решает 70% проблему)

70% положительных ответов просили pricing. Старый ответ: "let's hop on a call". Новый:

```
Pricing is pay-per-request — per successful API call, no monthly minimums.
Custom rates based on volume.

To give you an accurate number: how many creator profiles do you typically
analyze per month, and which platforms?

{calendar_link} if easier to talk through.
```

---

## Часть 6: Apollo/Clay — Оптимизация фильтров

### Пропущенные keywords (добавить в фильтры)

**Segment 1 (INFLUENCER_PLATFORMS):**
- `social commerce platform`, `creator economy`, `UGC platform`
- `creator management`, `brand ambassador platform`, `creator monetization`
- `creator intelligence`, `social media management` (частичный overlap)

**Segment 2 (AFFILIATE_PERFORMANCE):**
- `partner marketing platform`, `partnership management`
- `creator commerce`, `social selling`, `referral marketing platform`

**Segment 3 (IM_FIRST_AGENCIES):**
- `TikTok marketing agency`, `creator management agency`
- `content creator agency`, `brand partnership agency`

### Ключевое открытие: Apollo Keywords ≠ полнотекстовый поиск

Apollo Keywords — это AI-сгенерированные теги, НЕ поиск по тексту сайта. Если Apollo AI не распознал компанию как "influencer marketing platform", тег не назначен.

**Решение:** Параллельный run с Description search (ищет по SEO-описанию и bio). Даёт +10-15% компаний, пропущенных keyword-тегами.

### TAM — оценка объёма

| Сегмент | Всего компаний | Контактов в TAM | Уже отправлено | Остаток |
|---------|---------------|-----------------|---------------|---------|
| INFLUENCER_PLATFORMS | 200-350 | 1,500-3,000 | ~5,000 | **Основные охвачены** |
| AFFILIATE_PERFORMANCE | 80-140 | 800-1,500 | ~2,000 | Средний потенциал |
| IM_FIRST_AGENCIES | 500-800 | 1,000-2,000 | ~3,000 | **Наибольший рост** |
| **ИТОГО** | **780-1,290** | **3,300-6,500** | **~10,000** | Ограниченный |

**Критический вывод:** TAM по SaaS-платформам (Segments 1+2) почти исчерпан в текущих гео. Рост через:
1. **Новые гео** (Бразилия, ЮВА, Корея, Япония) — +30-50%
2. **Расширение keywords** — +15-25%
3. **Description search** — +10-15%
4. **Clay Ocean.io lookalike** от seed-компаний — +5-10%
5. **Новый сегмент: Social Commerce Platforms** (Bazaarvoice, LTK, ShopMy)

### Продвинутые стратегии

- **Technographic filters:** компании с Instagram API + TikTok API + Shopify
- **Hiring signals:** нанимают "Head of Influencer Marketing" = горячий сигнал
- **Funding signals:** Series A/B/C = бюджет на инструменты
- **Lookalike через Ocean.io (Clay):** 10 seed-доменов, семантический анализ > фирмографика Apollo

---

## Часть 7: Возможности системы magnum-opus

### Недоиспользованные функции

| Функция | Статус | Что даёт |
|---------|--------|----------|
| Campaign Intelligence (GOD_SEQUENCE) | Построено, не активно | Автоматические снимки перформанса, паттерны из лучших кампаний |
| Gathering Prompts с tracking | Построено, не используется для OnSocial | avg_target_rate по промптам, re-analyze на CP2 |
| Reply Automation с embedding | Построено | Каждый одобренный ответ = golden example для AI |
| Auto-discovery кампаний | Работает | Новые кампании автоматически подтягиваются |
| Multiple source adapters | 8 адаптеров, используется 1 | Clay, Apollo UI emulators — бесплатные |

### Что нужно починить

| Проблема | Влияние | Приоритет |
|----------|---------|-----------|
| sl_reply_count = 0 у главной кампании | Метрики сломаны | Высокий |
| GetSales API не интегрирован | LinkedIn данные ручные | Высокий |
| Campaign metadata пустая | Нет контекста для аналитики | Средний |
| Нет auto-pause мёртвых кампаний | Ручной мониторинг | Средний |

### Backend pipeline vs GOD_pipeline

| Когда | Backend (gathering_service) | GOD_pipeline |
|-------|----------------------------|--------------|
| Новый gathering run с нуля | Да — строгие checkpoints, DB | — |
| Быстрая итерация OnSocial | — | Да — Steps 9-11 только здесь |
| People Search (Apollo) | **Нет** — gap | Да (Step 9) |
| Cross-run dedup | Да (DB) | Нет (файлы) |
| Prompt effectiveness | Да (avg_target_rate) | Нет |

**Главный gap:** Backend pipeline обрывается после PUSH — нет People Search. GOD_pipeline не имеет prompt tracking и cross-run dedup. Нужно объединить.

---

## Часть 8: Action Plan — приоритеты

### НЕМЕДЛЕННО (сегодня-завтра)

| # | Действие | Ожидаемый эффект |
|---|----------|-----------------|
| 1 | Отключить 8 мёртвых кампаний | Освободить ёмкость + прекратить спам |
| 2 | Создать pricing response template и раздать Bhaskar | Reply→meeting с 6% до 15%+ |
| 3 | Масштабировать MENA+APAC — добавить IM Agencies | 4 meetings/46 sent → больше TAM |
| 4 | Каталогизировать: какой сиквенс в какой кампании | Понять что работает |

### ЭТА НЕДЕЛЯ

| # | Действие | Ожидаемый эффект |
|---|----------|-----------------|
| 5 | A/B тест: текущий копирайт vs JTBD-формат Sally | Найти оптимальный reply rate |
| 6 | Добавить пропущенные keywords в Apollo фильтры | +15-25% новых компаний |
| 7 | Запустить Description search параллельно keyword | +10-15% пропущенных |
| 8 | Настроить Thunderbird/Spark для 14 inbox'ов | Не терять ответы |
| 9 | Разбить flagship (IM agencies & SaaS_US&EU) на подсегменты | Повысить warm rate с 10% |

### СЛЕДУЮЩИЕ 2 НЕДЕЛИ

| # | Действие | Ожидаемый эффект |
|---|----------|-----------------|
| 10 | Внедрить God Sequence (email + LinkedIn sync) | +200-287% engagement |
| 11 | LinkedIn voice notes для Tier 1 лидов | +30-40% reply rate |
| 12 | LATAM + India agency — новые кампании #C | Расширение TAM |
| 13 | Clay Ocean.io lookalike от 10 seed-компаний | Нишевые компании |
| 14 | MillionVerifier в pipeline (Step 10.5) | Снижение bounce rate |

### МЕСЯЦ 2

| # | Действие | Ожидаемый эффект |
|---|----------|-----------------|
| 15 | Telegram outreach для India/CIS/MENA агентств | 3-й канал |
| 16 | Новый сегмент: Social Commerce Platforms | Расширение TAM |
| 17 | Campaign Intelligence activation | Автоматические паттерны |
| 18 | GetSales API интеграция | Автоматизация LinkedIn |
| 19 | Auto-pause: 500 sent + 0 warm = пауза | Предотвращение потерь |

---

## Часть 9: Прогноз при выполнении Action Plan

### Текущий темп (without changes)

```
750 emails/day × 30 days = 22,500 emails/month
× 1.53% reply = ~344 replies
× 6.1% reply→meeting = ~21 booked meetings
× 60% SQL rate = ~13 SQLs
```

**Прогноз: 13 SQLs/мес при текущем темпе. KPI (10) выполняется.**

### После Action Plan (conservative)

```
750 emails/day × 30 days = 22,500 emails/month
× 3.0% reply (от JTBD + keywords + multi-channel) = ~675 replies
× 15% reply→meeting (pricing response + scripts) = ~101 booked meetings
× 60% SQL rate = ~61 SQLs
```

**Это нереалистично оптимистично для всего объёма.** Более реалистично с учётом mixed quality:

```
Reply rate: 2.5% (реалистичный после оптимизации)
Reply→meeting: 12% (с pricing response + scripts)
= 22,500 × 2.5% × 12% × 60% = ~40 SQLs/мес
```

**Реалистичный прогноз: 25-40 SQLs/мес после полной оптимизации (месяц 2-3).**

---

## Часть 10: Ответы из интервью (зафиксировано)

| Вопрос | Ответ оператора |
|--------|----------------|
| #C = v3? | Каша. Не все #C на v3, нет трекинга какой копирайт где |
| Bhaskar | Продажник OnSocial. 3 LI аккаунта: Bhaskar, Sofia (SDR Sally), Sally (аутсорс) |
| Бюджет | Нет жёстких лимитов, принцип рационального использования |
| SQL | Post-call квалификация Bhaskar'ом. ~5 booked → 3 SQL (60%). KPI = 10/мес |
| MENA+APAC | Вероятно: маленькая выборка + ненасыщенный рынок. Нет трекинга копирайта |

---

## Приложения

### Приложение A: Полные отчёты агентов

Сохранены в:
- Agent 1 (SmartLead campaigns): `sofia/projects/OnSocial/research/agent_smartlead_campaigns.md`
- Agent 2 (System capabilities): `sofia/projects/OnSocial/research/agent_system_capabilities.md`
- Agent 3 (SDR best practices): `sofia/projects/OnSocial/research/agent_sdr_best_practices.md`
- Agent 4 (Cold outreach theory): `sofia/projects/OnSocial/research/agent_cold_outreach_theory.md`
- Agent 5 (Sally guides): `sofia/projects/OnSocial/research/agent_sally_guides.md`
- Agent 6 (God Sequence): `sofia/projects/OnSocial/research/agent_god_sequence.md`
- Agent 7 (Apollo/Clay filters): `sofia/projects/OnSocial/research/agent_apollo_clay_filters.md`

### Приложение B: Источники (из агента cold outreach theory)

- Instantly Cold Email Benchmark Report 2026
- Belkins Cold Email Response Rates 2025
- Expandi State of LinkedIn Outreach H1 2025
- Apollo Knowledge Base (Filters, Lookalikes, Technologies)
- Clay.com documentation (Claygent, Ocean.io, Pricing)
- InfluencerMarketingHub Market Reports 2026
- Statista: Number of IM companies worldwide
- Grand View Research: IM Platform Market Size
- 30+ дополнительных источников (полный список в отчёте Agent 4)

---

*Документ подготовлен системой magnum-opus. 7 параллельных агентов, ~610K токенов исследования.*
