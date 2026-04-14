# Apollo Filters v5 — OnSocial (4 segments, core tags)

> Date: 2026-04-13
> Based on: v4 (2026-04-10)
> Status: **Active draft** — pre-run validation пропущена (Apollo auth был заблокирован). Валидация накатится натурально на следующем пайплайн-ране через Step 6 (VERIFY checkpoint). Если accuracy < 90% — Step 7 автотюнит prompt или правим фильтры.
> Purpose: максимальный охват за счёт сокращения keyword-фраз до ядра (1-2 слова), добавления смежных категорий и пересмотра exclusions.

---

## What changed from v4

| Parameter         | v4                                                  | v5                                                                            |
| ----------------- | --------------------------------------------------- | ----------------------------------------------------------------------------- |
| Keyword phrasing  | многословные (`influencer marketing platform`)      | **ядро 1-2 слова** (`influencer marketing`, `creator commerce`)               |
| Adjacent coverage | узко в рамках segment framing                       | **добавлены смежные теги** (retail tech, creator tools, content commerce)     |
| Exclusions        | over-restrictive (`e-commerce platform`, `print`)   | **rationalized** — убраны теги, ловящие релевантных игроков                   |
| SOCCOM keywords   | 33 длинные фразы                                    | **50 коротких тегов** + adjacent categories                                   |
| IMAGENCY          | длинные суффиксы `agency`                           | **короткие ядра** + суффикс только там где нужно отсечь B2B tools             |
| Industry (SOCCOM) | строго 7 + exclusion `e-commerce platform`          | **7 + убрали `e-commerce platform` exclusion** (ловит Flip, Whatnot, Bambuser)|
| Employee range    | 10-10,000 унифицированно                            | **same** — работает, не трогаем                                               |
| Location          | ALL GEO (55 стран)                                  | **same**                                                                      |
| People filter     | universal cross-segment                             | **same** — не трогаем, проверен                                               |

**Принцип v5:** Apollo/Clay keyword match = substring по company tags. Длинная фраза `live shopping platform` ловит только компании, которые *буквально* так себя описывают. Короткое `live shopping` ловит всех, кто использует этот термин в любом контексте.

---

## Segment 1 — INFLUENCER_PLATFORMS

SaaS, analytics, creator data API, social intelligence, earned media, audience measurement — всё, что строит инфру вокруг creator economy.

### Company filters

**Industry**
```
Computer Software, Internet, Marketing & Advertising,
Information Technology, Online Media
```

**Company Keywords — ANY of (50)**
```
influencer marketing, creator analytics, creator marketplace,
influencer platform, creator platform, creator economy,
creator tech, influencer tech, creator data, influencer data,
creator API, creator intelligence, influencer intelligence,
influencer discovery, creator discovery, creator search,
creator tools, influencer tools, creator CRM, influencer CRM,
brand ambassador, ambassador platform, talent marketplace,
social listening, social intelligence, social analytics,
social media analytics, social data, social ROI,
brand monitoring, brand intelligence, sentiment analysis,
reputation management, media monitoring, earned media,
digital PR, content analytics, content intelligence,
engagement analytics, audience analytics, audience intelligence,
audience data, UGC, UGC platform, user generated content,
review management, ratings and reviews, social proof,
word of mouth, creator measurement, influencer measurement
```

**Excluded Company Keywords**
```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant,
antivirus, cybersecurity, network monitoring,
IT infrastructure, cloud hosting, data center,
ERP, payroll, HRIS, applicant tracking
```

> Removed (v5): `web design only, SEO only, PPC only, print` — Apollo игнорирует `only`, из-за них вылетали легитимные agency-adjacent SaaS.

**# Employees:** 10-10,000

**Location:** ALL GEO (see Location list below)

---

## Segment 2 — AFFILIATE_PERFORMANCE

Affiliate/partner tech, performance marketing, loyalty/rewards, attribution — плюс creator-affiliate и commerce-attribution конвергенция.

### Company filters

**Industry**
```
Computer Software, Internet, Marketing & Advertising,
Information Technology, E-commerce, Online Media
```

**Company Keywords — ANY of (50)**
```
affiliate marketing, affiliate network, affiliate platform,
affiliate tracking, affiliate management, affiliate SaaS,
affiliate program, creator affiliate, influencer affiliate,
social affiliate, performance marketing, partner marketing,
partnership platform, partnerships platform, partner ecosystem,
partner tech, partner relationship, channel partner,
reseller platform, performance partnerships,
referral marketing, referral program, loyalty platform,
loyalty program, rewards platform, cashback, coupon platform,
deal platform, offer platform,
marketing attribution, conversion tracking, attribution platform,
multi-touch attribution, commerce attribution,
creator monetization, creator commerce, content commerce,
performance commerce, link in bio, creator storefront,
creator payments, creator payouts, creator shop,
creator checkout, revenue sharing, ambassador platform,
marketplace monetization, commission tracking,
social commerce, social shopping, performance SaaS
```

**Excluded Company Keywords**
```
affiliate agency, affiliate management service, media buying agency,
recruitment, HR, staffing, healthcare, legal, accounting,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant,
antivirus, cybersecurity, network monitoring,
IT infrastructure, cloud hosting, data center,
ERP, payroll, HRIS, applicant tracking,
banking, credit union, lending platform,
crypto exchange, blockchain wallet
```

> Removed (v5): `SEO agency, PPC agency, web design, software development, print` — over-broad, ловили affiliate networks с small consulting arm.

**# Employees:** 10-10,000

**Location:** ALL GEO

---

## Segment 3 — IM_FIRST_AGENCIES

Agencies где influencer marketing = core business. Включая specialized (TikTok, KOL, UGC), talent management, creator-led studios.

### Company filters

**Industry**
```
Marketing & Advertising
```

> Unchanged: PR = 0 conversions, держим узко.

**Company Keywords — ANY of (45)**
```
influencer marketing, influencer agency, creator agency,
influencer management, creator management,
creator campaigns, influencer campaigns,
influencer strategy, creator strategy,
influencer activation, creator activation,
UGC agency, TikTok agency, KOL agency, KOL management,
key opinion leader, micro-influencer, nano-influencer,
influencer seeding, product seeding, gifting agency,
talent management, creator representation,
influencer representation, digital talent,
creator collective, influencer collective,
creator network, influencer network,
creator studio, content studio, branded content,
creator-led, social-first agency, creator-first agency,
influencer PR, creator PR, performance influencer,
data-driven influencer, creator economy agency,
creator consultancy, influencer talent,
social media influence, digital influence,
creator partnerships
```

**Excluded Company Keywords**
```
SEO agency, PPC agency, web design, software development,
recruitment, HR, staffing, healthcare, legal, accounting,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, media buying only,
PR agency, public relations, crisis communications,
web development, app development, branding only,
market research, consulting firm, management consulting,
antivirus, cybersecurity, IT infrastructure,
modelling agency, casting agency,
translation agency, localization agency
```

**# Employees:** 10-10,000

**Location:** ALL GEO

---

## Segment 4 — SOCIAL_COMMERCE

Live shopping, creator storefronts, shoppable video, UGC-to-commerce marketplaces. Shopping experiences powered by creators.

### Company filters

**Industry**
```
Computer Software, Internet, Marketing & Advertising,
Information Technology, E-commerce, Online Media, Retail
```

**Company Keywords — ANY of (50)**
```
social commerce, live shopping, livestream shopping,
video commerce, shoppable video, creator commerce,
creator economy, creator monetization,
UGC, shoppable, live selling, livestream,
creator storefront, influencer commerce, influencer marketplace,
user generated content, ratings and reviews, community commerce,
discovery commerce, conversational commerce, retail media,
retail tech, creator tools, content commerce, brand community,
loyalty commerce, shoppable content, shoppable media,
shoppable app, live commerce, live shopping platform,
creator marketplace, social shopping, video shopping,
social selling, social storefront, creator checkout,
creator shop, influencer shop, live auction,
live video commerce, interactive commerce, live sale,
real-time commerce, social retail, creator-led commerce,
UGC commerce, fan commerce, live stream shopping,
creator-first marketplace
```

**Excluded Company Keywords**
```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant,
antivirus, cybersecurity, IT infrastructure, ERP, payroll,
payment processing, dropshipping,
affiliate network, affiliate tracking,
video streaming platform, gaming streaming, sports streaming
```

> Removed (v5): `e-commerce platform, online store builder, shopping cart, logistics platform, live streaming entertainment, SEO only, PPC only, print` — over-restrictive. Flip, Whatnot, Bambuser часто описывают себя как "e-commerce" + "creator". `Live streaming entertainment` исключение пересекалось с legit social commerce live платформами.

**# Employees:** 10-10,000

**Location:** ALL GEO

---

## Universal People Filter (cross-segment)

Unchanged from v4.

### Job Titles
```
CEO, Co-Founder, Founder, COO, Managing Director, Managing Partner, General Manager,
CTO, Chief Technology Officer,
CPO, Chief Product Officer,
CDO, Chief Data Officer,
CMO, VP Marketing,
VP Engineering, VP of Engineering, VP Technology,
VP Product, VP of Product,
VP Data, VP Analytics, VP Platform,
VP Partnerships, VP Growth,
Head of Engineering, Head of Technology,
Head of Product, Head of Data, Head of Analytics,
Head of Platform, Head of Integrations, Head of Digital,
Head of Partnerships, Head of Growth, Head of Martech,
Director of Engineering, Director of Technology,
Director of Product, Director of Data, Director of Analytics,
Director of Partnerships, Director of Growth, Director of Martech,
Technical Director, Technology Director,
Chief Architect,
Co-Founder CTO, Founding Engineer, Technical Co-Founder
```

### Management Level
```
c_suite, vp, director, head, partner, founder
```

### Excluded Titles
```
Intern, Junior, Assistant, Student, Freelance,
IT Support, IT Manager, IT Administrator, Desktop Support,
Systems Administrator, Network Administrator,
Help Desk, Helpdesk,
Marketing Technology Manager, MarTech Manager,
Content Creator, Designer, UX Designer, UI Designer,
QA Engineer, Junior Engineer, Software Tester,
HR, People, Recruiter, Finance, Accounting,
Social Media Manager, Community Manager,
Campaign Manager, Campaign Coordinator,
Account Manager, Account Executive, Sales,
Office Manager, Executive Assistant
```

---

## Location (ALL GEO — all segments)

```
United States, Canada,
United Kingdom, Germany, France, Netherlands, Spain, Italy, Belgium,
Switzerland, Austria, Denmark, Sweden, Norway, Finland, Ireland, Portugal, Luxembourg,
Poland, Czech Republic, Romania, Hungary, Ukraine, Serbia, Croatia, Bulgaria, Greece,
Slovakia, Slovenia, Estonia, Latvia, Lithuania,
Israel, United Arab Emirates, Turkey, Saudi Arabia, Egypt,
India, Singapore, Australia, New Zealand, Japan, South Korea,
Indonesia, Malaysia, Philippines, Thailand, Hong Kong, Taiwan,
Brazil, Mexico, Argentina, Colombia, Chile,
South Africa, Nigeria, Kenya
```

---

## Cross-segment exclusions

Same as v3/v4 — apply competitor blacklist, negative responder blacklist, active pipeline blacklist to ALL segments.

---

## Volume estimates (v5 vs v4)

| Segment               | v4 Apr 10 est.   | v5 est.            | Delta                                                     |
| --------------------- | ---------------- | ------------------ | --------------------------------------------------------- |
| INFLUENCER_PLATFORMS  | 3,500-6,000      | 5,000-8,500        | +40% (short tags ловят больше self-descriptions)          |
| AFFILIATE_PERFORMANCE | 1,000-2,000      | 1,500-3,000        | +50% (short tags + commerce-adjacent)                     |
| IM_FIRST_AGENCIES     | 2,000-4,000      | 2,800-5,000        | +30% (short ядра без `agency` суффикса)                   |
| SOCIAL_COMMERCE       | 400-500 actual   | 1,200-2,500        | +3-5x (50 тегов + rationalized exclusions)                |
| **Total**             | **~7,000-12,500**| **10,500-19,000**  | **+45-55% expansion**                                     |

> SOCCOM: главный unlock — снятие `e-commerce platform` exclusion + 50 коротких тегов вместо 33 длинных фраз.

---

## Important: deduplication

v5 результаты пересекутся с v3/v4 экспортами. Перед загрузкой в SmartLead:

1. Export v5 results
2. Deduplicate против blacklist + существующие leads + exclusion list
3. Обрабатывать только net-new

---

## Filter validation checklist

Перед запуском каждого сегмента:

- Run `search_people` с `per_page=1` — получить `total_count`
- Scrape 25 сайтов из Apollo export
- Manual check: compания реально match сегмент?
- <70% match → ужесточить keywords / добавить exclusions
- >90% match → proceed
- Cross-check vs Sally's successful leads — попали бы они в v5?
- Cross-check vs Sally's failures — исключились бы?

---

## Notes per segment

**INFPLAT**: короткие теги `creator economy`, `creator tech`, `social intelligence` ловят API-first и infra-companies, которые v4 не брал.

**AFFPERF**: добавлены `social commerce`, `social shopping`, `creator commerce` — overlap с SOCCOM намеренный, affiliate и social-commerce игроки часто пересекаются (Mavely/Later case).

**IMAGENCY**: убран суффикс `agency` из большинства тегов — компании часто описывают услуги как "influencer management" без слова "agency". Industry filter `Marketing & Advertising` продолжает держать ICP узко.

**SOCCOM**: самый большой unlock. Убраны exclusions `e-commerce platform`, `online store builder`, `shopping cart`, `live streaming entertainment` — все ловили legit targets (Flip, Whatnot, Bambuser, TalkShopLive).
