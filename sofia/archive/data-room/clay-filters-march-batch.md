# Clay — March Batch (3 сегмента, ~2,000 контактов)

**Дата:** 2026-03-16
**Цель:** 2,000 контактов → ~600 после отсева → ~400 чистых
**Стоимость поиска и выгрузки:** 0 кредитов (кредиты только на enrichment)

---

## Шаг 1: Find Leads (компании) — 3 поиска

### Поиск 1: INFLUENCER_PLATFORMS

Workbook: `OnSocial_INFPLAT_Mar`

**Company filters:**

- Industry: `Computer Software`, `Internet`, `Marketing & Advertising`, `Information Technology`, `Online Media`
- Keywords (ANY): `influencer marketing platform`, `creator analytics`, `creator marketplace`, `influencer platform`, `social media analytics`, `UGC platform`, `creator economy`, `audience analytics`, `influencer API`, `social listening`, `brand monitoring`, `creator data`, `influencer discovery`, `creator tools`, `influencer intelligence`, `audience intelligence`, `social data`
- Employees: 201–500, 1000-5000, 501-1000
- Location: `United States`, `United Kingdom`, `Germany`, `Netherlands`, `France`, `Canada`, `Australia`, `Spain`, `Italy`, `Sweden`, `Denmark`, `Belgium`

**Сколько выгружать:** до 1,000 компаний. Если результатов >5,000 — сузить по employee count (сначала 5-200, потом 200-5000, Save to existing table).

---

### Поиск 2: AFFILIATE_PERFORMANCE

Workbook: `OnSocial_AFFPERF_Mar`

**Company filters:**

- Industry: `Computer Software`, `Internet`, `Information Technology`, `Online Media`
- Keywords (ANY): `social commerce`, `creator commerce`, `influencer affiliate`, `creator monetization`, `link in bio`, `creator storefront`, `affiliate platform`, `affiliate network`, `affiliate tracking`, `affiliate management platform`, `performance partnerships`, `creator affiliate`, `creator program`, `influencer program`, `creator economy`, `influencer commerce`
- Employees: 20–5,000
- Location: `United States`, `United Kingdom`, `Germany`, `Netherlands`, `France`, `Canada`, `Australia`, `Sweden`, `Denmark`, `Belgium`, `Spain`, `Italy`

**Сколько выгружать:** до 600 компаний.

---

### Поиск 3: IM_FIRST_AGENCIES

Workbook: `OnSocial_IMAGENCY_Mar`

**Company filters:**

- Industry: `Marketing & Advertising`
- Keywords (ANY): `influencer marketing agency`, `influencer agency`, `creator agency`, `influencer management`, `creator campaigns`, `influencer marketing`, `creator partnerships`, `TikTok agency`, `influencer talent`, `creator talent`, `influencer strategy`, `UGC agency`
- Employees: 10–500
- Location: `United States`, `United Kingdom`, `Germany`, `Netherlands`, `France`, `Australia`, `Canada`, `Spain`, `Belgium`, `Denmark`

**Сколько выгружать:** до 400 компаний.

---

## Шаг 2: Find People (из таблиц компаний)

Для каждого Workbook → Find People с фильтрами ниже. Выгружать в новую таблицу внутри того же Workbook.

### People для INFPLAT и AFFPERF (технический buyer)

**Job Titles (ANY):**

```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
Head of Product, Chief Product Officer, VP Product,
Director of Engineering, Director of Product,
Co-Founder, Founder, CEO, COO
```

**+ для AFFPERF добавить:**

```
VP Partnerships, Head of Partnerships, Director of Partnerships
```

**Management Level:** C-Suite, VP, Director, Owner

**Исключить titles:**

```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Customer Success, Support, HR, People, Recruiter,
Content Writer, Designer, Social Media Manager
```

**+ для AFFPERF исключить:**

```
Affiliate Manager, Partner Manager
```

---

### People для IMAGENCY (agency buyer)

**Job Titles (ANY):**

```
CEO, Founder, Co-Founder, Managing Director, Managing Partner,
Head of Influencer Marketing, Director of Influencer,
Head of Influencer, VP Strategy, Head of Partnerships,
Director of Client Services, Head of Strategy,
General Manager, Partner, Owner
```

**Management Level:** C-Suite, Director, Owner, Partner

**Исключить titles:**

```
Intern, Junior, Assistant, Student, Freelance,
Campaign Manager, Campaign Coordinator,
Social Media Manager, Content Creator, Designer,
Account Coordinator, Media Planner, Media Buyer,
PR Manager, Communications Manager,
HR, People, Recruiter, Finance, Accounting,
Executive Assistant, Office Manager, Operations Coordinator
```

---

## Шаг 3: Ручная чистка перед enrichment

Перед тем как тратить кредиты на enrichment — пройтись глазами и убрать:

### Компании-конкуренты (удалить строки)

```
Demographics Pro, HypeAuditor, Modash, Phyllo,
CreatorIQ, GRIN, Aspire, Traackr, Upfluence,
Heepsy, Influencity, Klear, Meltwater,
Tagger, Sprout Social
```

### Уже ответили негативно (удалить строки)

```
United Influencers, The Digital Dept, &Rosas,
EvolveZ Agency, Croud, Creator Origin,
Social Media Examiner, In The Black Media,
AVEC, Octup
```

### Уже в pipeline (удалить строки)

```
Brighter Click, The Shelf, impact.com, MediaLabel,
Peersway, FanStories, Gordon Glenister Ltd,
TWIC / The Wolf Is Coming, Kreatory, Muse The Agency,
growi.io, Publifyer, styleranking media, Influee,
Linqia, PFR Group, GameInfluencer, KJ Marketing Sweden,
Clark Influence, Runway Influence, HK Digital Marketing,
Haulpack, Grg
```

### Домены (удалить строки где website содержит)

```
.gov, .edu
```

---

## Шаг 4: Dedup с Настиными списками

Экспортировать email из SmartLead (6,287 контактов из всех кампаний Насти) → сравнить с Clay выгрузкой → удалить пересечения.

**Кампании для деdup:**

- IM agencies & SaaS (1,977)
- IM_PLATFORMS (648)
- MARKETING_AGENCIES (265)
- 0903_AGENCIES (511)
- 0903_PLATFORMS (1,034)
- PR firms (1,852)

---

## Шаг 5: Enrichment (тут тратятся кредиты)

**Только после шагов 3-4** (чтобы не тратить кредиты на мусор).

1. **FindyMail** → Find work email (через свой API-ключ)
2. **AI-скоринг** → промпт из segmentation_prompt.md (через свой API-ключ GPT-4)
3. Отфильтровать результат: убрать OTHER, оставить TRUE
4. Экспорт → загрузка в SmartLead

---

## Распределение и почему


| Сегмент      | Компаний из Clay | После People search | После отсева 70% | Почему столько                                                                                                                 |
| ------------ | ---------------- | ------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **INFPLAT**  | 1,000            | ~800-1,000          | **~300**         | 83% всех actionable. Actionable rate 1.01% — в 5 раз выше остальных. 3 strong fits (The Shelf, MediaLabel, Peersway)           |
| **AFFPERF**  | 600              | ~400-600            | **~180**         | Не тестирован, но impact.com = strong fit (попал случайно). Later купил Mavely за $250M. Конкуренты не таргетируют — мы первые |
| **IMAGENCY** | 400              | ~300-400            | **~120**         | 1 strong fit (Brighter Click). Agencies конвертятся хуже платформ (1/5 vs 4/5). Минимум для поддержания                        |
| **Итого**    | **2,000**        | **~1,500-2,000**    | **~600**         | Цель 400 чистых + запас на dedup с 6,287 Настиными                                                                             |


### Почему 50/30/20 а не поровну

**INFPLAT получает больше всех** потому что это единственный сегмент с доказанными данными. IM agencies & SaaS дала 20 из 24 actionable (83%). Каждый контакт в INFPLAT в 5 раз ценнее чем в других сегментах.

**AFFPERF получает 30%** — не потому что доказан, а потому что нужен объём для валидации. impact.com — единственный data point, но сильный: два DM ответили независимо, affiliate-creator convergence = топ-тренд 2026, конкуренты не таргетируют. 600 контактов = минимум чтобы через 2-3 недели понять работает сегмент или нет.

**IMAGENCY получает минимум** — agencies конвертятся хуже. Из 5 strong fits только 1 = agency. Micro-agencies (<10 чел) не могут платить. Holdings (WPP, Omnicom) не отвечают. Оставляем только IM-first agencies 10-500 чел, но не вкладываем больше 20% объёма.