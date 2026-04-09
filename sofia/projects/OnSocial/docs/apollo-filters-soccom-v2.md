# Apollo Filters — SOCIAL_COMMERCE v2

> Дата: 2026-04-09
> Цель: net-new компании, которые v1 не поймал
> Стратегия: четыре смежных угла атаки (см. ниже)
> Деплой: после дедупа против v1-экспорта

---

## Почему v1 дал только 500

v1 бил в очень узкий центр: `live shopping platform`, `creator storefront`, `shoppable video`. Это прямые игроки. Смежные категории — commerce infrastructure, conversational commerce, retail media, visual/AR commerce — выпали, потому что их компании не используют эти слова в описании.

v2 бьёт в **четыре смежных кластера**, которые не пересекаются по ключевым словам с v1.

---

## Кластер A — Commerce Infrastructure for Creators

Инструменты, на которых строится creator commerce: checkout, payouts, storefronts-as-a-service, product feeds для создателей.

**Ключевые слова:**
```
creator checkout, creator payments infrastructure, creator payout platform,
storefront as a service, headless commerce creators, product feed creators,
shoppable link platform, link in bio shopping, social selling tools,
social buy button, in-app checkout, one-click checkout social,
checkout experience platform, creator billing platform,
embedded commerce, native checkout social
```

---

## Кластер B — Conversational & Messaging Commerce

Продажи через мессенджеры, чат-боты, голос, WhatsApp, SMS. Индустрия быстро сливается с creator commerce.

**Ключевые слова:**
```
conversational commerce, chat commerce, messaging commerce,
WhatsApp commerce, SMS commerce, chatbot commerce,
voice commerce platform, live chat shopping,
customer messaging commerce, social messaging platform commerce,
conversational AI shopping, chatbot shopping assistant,
omnichannel messaging commerce, RCS commerce
```

---

## Кластер C — Visual & AR Commerce

AR-примерка, визуальный поиск, shoppable фото/видео от брендов (не creator-first, но покупают creator data для таргетинга).

**Ключевые слова:**
```
visual commerce platform, augmented reality shopping, AR try-on,
virtual try-on platform, visual search shopping, shop the look platform,
shoppable photography, visual discovery shopping,
3D product visualization, AR commerce, immersive commerce,
virtual fitting room, digital showroom platform,
visual product discovery, image recognition commerce
```

---

## Кластер D — Retail Media & Social Proof Commerce

Retail media networks и платформы социального доказательства — закупают creator/influencer данные для targeting и reviews.

**Ключевые слова:**
```
retail media network platform, retail media technology, in-store media platform,
shoppable ads platform, social proof platform ecommerce,
reviews commerce platform, UGC commerce platform,
user generated commerce, community commerce platform,
customer content commerce, social reviews platform,
product review platform ecommerce, ratings reviews platform,
advocacy platform ecommerce, brand advocacy commerce,
co-shopping platform, group buying platform, social gifting platform
```

---

## Company filters (единые для всех кластеров)

**Industry**

```
Computer Software, Internet, Marketing & Advertising,
Information Technology, E-commerce, Online Media, Retail,
Financial Services
```

> Добавили Financial Services — туда попадают платёжные инфраструктурные компании (кластер A).

**Company Keywords — ANY of**

Все ключевые слова кластеров A + B + C + D (полный список):

```
creator checkout, creator payments infrastructure, creator payout platform,
storefront as a service, headless commerce creators, product feed creators,
shoppable link platform, link in bio shopping, social selling tools,
social buy button, in-app checkout, one-click checkout social,
checkout experience platform, creator billing platform,
embedded commerce, native checkout social,
conversational commerce, chat commerce, messaging commerce,
WhatsApp commerce, SMS commerce, chatbot commerce,
voice commerce platform, live chat shopping,
customer messaging commerce, social messaging platform commerce,
conversational AI shopping, chatbot shopping assistant,
omnichannel messaging commerce, RCS commerce,
visual commerce platform, augmented reality shopping, AR try-on,
virtual try-on platform, visual search shopping, shop the look platform,
shoppable photography, visual discovery shopping,
3D product visualization, AR commerce, immersive commerce,
virtual fitting room, digital showroom platform,
visual product discovery, image recognition commerce,
retail media network platform, retail media technology, in-store media platform,
shoppable ads platform, social proof platform ecommerce,
reviews commerce platform, UGC commerce platform,
user generated commerce, community commerce platform,
customer content commerce, social reviews platform,
product review platform ecommerce, ratings reviews platform,
advocacy platform ecommerce, brand advocacy commerce,
co-shopping platform, group buying platform, social gifting platform
```

**Excluded Company Keywords**

```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, SEO only, PPC only, print,
antivirus, cybersecurity, IT infrastructure, ERP, payroll, HRIS,
payment gateway only, payments processing only, acquiring bank,
logistics platform, dropshipping platform, fulfillment center,
affiliate network, affiliate tracking,
video streaming platform, live streaming entertainment,
gaming streaming, sports streaming, dating platform,
online store builder only, shopping cart software
```

> Исключили `payment processing only` — не хотим Stripe-клоны. Хотим тех, кто строит поверх него для creators.

**# Employees:** 5–3,000

> Сдвинули нижнюю границу до 5 — стартапы в AR/conversational commerce маленькие. Верхнюю уменьшили до 3000 — крупные retailer-сами нас не купят.

**Location:** ALL GEO (no filter)

> v1 был ограничен 20 странами. v2 снимает фильтр — APAC (Китай, Япония, Ю.Корея, SEA) генерит много conversational/live commerce стартапов.

---

## People filters

**Job Titles**

```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
VP Product, Head of Product, Chief Product Officer,
Director of Engineering, Director of Product,
Head of Commerce, VP Commerce, Director of Commerce,
Head of Marketplace, VP Marketplace, Director of Marketplace,
Head of Partnerships, VP Partnerships, Director of Partnerships,
Head of Growth, VP Growth, Director of Growth,
Co-Founder, Founder, CEO, COO,
Head of Data, VP Data, Chief Data Officer
```

**Management Level:** c_suite, vp, director, owner, head, partner, founder

**Excluded Titles**

```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Account Manager, Customer Success, Support, HR, Recruiter,
Content Writer, Designer, Social Media Manager,
Affiliate Manager, Partner Manager, Community Manager,
Solutions Architect, Technical Architect,
Staff Engineer, Principal Engineer, Lead Engineer, Lead Developer
```

---

## Как дедуплицировать против v1

1. Выгрузить v2 из Apollo → CSV
2. Запустить против существующего blacklist + exclusion list (стандарт)
3. Дополнительно: убрать домены, которые уже были в v1-экспорте
4. Оставшееся = net-new SOCCOM pipeline

---

## Ожидаемый объём

| Кластер | Оценка компаний |
|---------|----------------|
| A — Commerce Infrastructure | 300–600 |
| B — Conversational Commerce | 200–400 |
| C — Visual / AR Commerce | 150–300 |
| D — Retail Media / Social Proof | 400–800 |
| **Итого (до дедупа)** | **~1,050–2,100** |
| После дедупа с v1 (~20% overlap) | **~850–1,700 net-new** |
