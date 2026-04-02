# Apollo Filters — OnSocial Project (Summary)

Все сборы для OnSocial используют **3 сегмента** с разными фильтрами Apollo/Clay.  
Версии: v3 (2026-03-15) → v4 (2026-03-31, расширенная 2x).

---

## Сегмент 1: INFLUENCER_PLATFORMS
SaaS-платформы для инфлюенсер-маркетинга, creator economy, social listening

### Компании
- **Industries:** Computer Software, Internet, Marketing & Advertising, IT, Online Media
- **Size:** 5–5,000 employees
- **Locations:** ALL GEO (v4), ранее v3 — US, UK, DE, NL, FR, CA, AU, ES, IT, SE, DK, BE
- **Keywords (34):** influencer marketing platform, creator analytics, creator marketplace, influencer platform, social media analytics, UGC platform, creator economy, audience analytics, influencer API, social listening, brand monitoring, creator data, influencer discovery, creator tools, influencer intelligence, audience intelligence, social data + v4: social intelligence platform, content intelligence, earned media platform/analytics, digital PR platform, media monitoring platform, creator CRM, creator relationship management, talent marketplace technology, social ROI platform, reputation management platform, sentiment analysis platform, social media intelligence, brand intelligence, content analytics platform, engagement analytics, creator economy infrastructure, social proof platform, review management platform, word of mouth platform
- **Excluded keywords (20):** recruitment, staffing, accounting, legal, healthcare, logistics, manufacturing, real estate, fintech, insurance, construction, education, nonprofit, government, defense, food service, restaurant, hospitality, travel agency, web design only, SEO only, PPC only, print, freelance, solo consultant, antivirus, cybersecurity, network monitoring, IT infrastructure, cloud hosting, data center, ERP, payroll, HRIS, applicant tracking

### Люди
- **Titles (22):** CTO, VP Engineering, VP of Engineering, Head of Engineering, Head of Product, Chief Product Officer, VP Product, Director of Engineering, Director of Product, Co-Founder, Founder, CEO, COO, Senior Director of Engineering/Product, Senior VP Engineering/Product, Head of Data, VP Data, Chief Data Officer, Head of Platform, VP Platform
- **Management levels:** c_suite, vp, director, owner, senior, head, partner, founder
- **Excluded:** intern, junior, assistant, student, freelance, marketing manager, sales rep, AE, CS, support, HR, recruiter, content writer, designer, social media manager, solutions/technical/enterprise architect, staff/principal/lead engineer/developer

---

## Сегмент 2: AFFILIATE_PERFORMANCE
Affiliate-сети, перформанс-маркетинг, social commerce, партнёрские платформы

### Компании
- **Industries:** Computer Software, Internet, Marketing & Advertising, IT, E-commerce, Online Media
- **Size:** 20–5,000 employees
- **Locations:** ALL GEO
- **Keywords (41):** affiliate marketing, affiliate network, affiliate platform, performance marketing platform, partner marketing, partnership platform, social commerce, creator commerce, influencer affiliate, referral marketing, affiliate tracking, partner ecosystem, performance partnerships + v4: affiliate management platform, commission tracking, creator monetization, link in bio, creator storefront, loyalty/rewards/cashback/coupon/deal/offer platform, attribution platform, marketing attribution, multi-touch attribution, conversion tracking, partner relationship management, channel partner platform, reseller platform, marketplace monetization, creator payments/payout platform, referral program platform, ambassador platform, revenue sharing platform
- **Excluded (31):** affiliate agency, affiliate management service, SEO/PPC agency, web design, software dev, recruitment, HR, staffing, healthcare, legal, accounting, logistics, manufacturing, real estate, fintech, insurance, construction, education, nonprofit, government, defense, food service, restaurant, hospitality, travel agency, freelance, solo consultant, print, media buying agency, antivirus, cybersecurity, network monitoring, IT infrastructure, cloud hosting, data center, ERP, payroll, HRIS, applicant tracking, banking, credit union, lending, crypto exchange, blockchain wallet

### Люди
- **Titles (27):** CTO, VP/Head/Director of Engineering, VP/Head/Director of Product, CPO, VP/Head/Director of Partnerships, Co-Founder, Founder, CEO, COO, Senior Director of Engineering/Product/Partnerships, Senior VP Partnerships, Head/VP of Data, CDO, Head/VP of Platform, Head/VP/Director of Growth
- **Excluded (17):** intern, junior, assistant, student, freelance, marketing manager, sales rep, AE, account manager, CS, support, HR, recruiter, content writer, designer, social media manager, affiliate manager, partner manager, solutions/technical/enterprise architect, staff/principal/lead engineer/developer

---

## Сегмент 3: IM_FIRST_AGENCIES
Агентства, где инфлюенсер-маркетинг — основной бизнес

### Компании
- **Industries:** Marketing & Advertising ONLY
- **Size:** 10–500 employees
- **Locations:** ALL GEO
- **Keywords (30):** influencer marketing agency, influencer agency, creator agency, influencer management, creator campaigns, influencer marketing, creator partnerships, TikTok agency, influencer/creator talent, influencer strategy, UGC agency + v4: creator/content/branded content/creative studio, talent management agency creator, digital talent agency, creator/influencer representation, social-first/creator-first agency, influencer/creator activation, micro/nano-influencer agency, influencer seeding/gifting agency, creator network agency, influencer collective
- **Excluded (32):** SEO/PPC/PR agency, web design, software dev, recruitment, HR, staffing, healthcare, legal, accounting, logistics, manufacturing, real estate, fintech, insurance, construction, education, nonprofit, government, defense, food service, restaurant, hospitality, travel agency, freelance, solo consultant, print, media buying only, public relations, crisis comms, web/app dev, branding only, market research, consulting, management consulting, antivirus, cybersecurity, IT infrastructure, modelling/casting agency, event management only, photography/video studio only, translation/localization agency

### Люди
- **Titles (25):** CEO, Founder, Co-Founder, Managing Director/Partner, Head/Director of Influencer Marketing, VP Strategy, Head of Partnerships, Director of Client Services, Head of Strategy, GM, Partner, Owner, Senior Partner/MD, Head/Director of Creator Partnerships, Head/Director of Talent, Head/Director of Growth, Head/Director of Business Development, Head/Director of Operations
- **Excluded (29):** intern, junior, assistant, student, freelance, campaign manager/coordinator, social media manager, content creator, designer, account coordinator, media planner/buyer, PR/comms manager, HR, recruiter, finance, accounting, EA, office manager, ops coordinator, community manager, influencer/talent coordinator

---

## Общие исключения (все сегменты)

### Конкуренты (blacklist)
Demographics Pro, HypeAuditor, Modash, Phyllo, CreatorIQ, GRIN, Aspire, Traackr, Upfluence, Heepsy, Influencity, Klear/Meltwater, Tagger/Sprout Social

### Negative responders
United Influencers, The Digital Dept, &Rosas, EvolveZ Agency, Croud, Creator Origin, Social Media Examiner

### Active pipeline (не контактировать повторно)
Brighter Click, The Shelf, impact.com, MediaLabel, Peersway, FanStories, Gordon Glenister Ltd, TWIC/The Wolf Is Coming, Kreatory

---

## API-параметры Apollo

| Параметр | Описание |
|----------|----------|
| `q_organization_domains` | Поиск по домену |
| `person_titles` | Фильтр по должности |
| `person_seniorities` | Уровень (c_suite, vp, director, owner, senior, head, partner, founder) |
| `q_organization_keyword_tags` | Ключевые слова компании |
| `organization_locations` | География |
| `organization_num_employees_ranges` | Размер компании ("5,50" / "51,200" и т.д.) |
| `per_page` | Результатов на страницу (макс 100) |

## Способ сбора

Всё через пайплайн и скрипты — без ручной работы в Apollo UI:

- **Apollo API** (`apollo_service.py`) — people search (бесплатный, без кредитов)
- **Apollo UI-скрейпер** (`apollo_companies_ui.py`, Puppeteer) — companies search (тоже бесплатный)
- **Clay** — Python-скрипты (`onsocial_clay_*_v4_allgeo_2026-03-31.py`)

## Откуда берутся фильтры

Два способа формирования фильтров перед запуском пайплайна:

1. **Из подготовленных .md-файлов** — заранее составленные и провалидированные наборы фильтров (`apollo-filters-v3.md`, `apollo-filters-v4.md`, `clay-filters-v1.md`). Скрипт парсит их и использует как есть. Для стабильных, отработанных сегментов.

2. **Генерация через GPT на основе ICP** — перед запуском скрипт отправляет описание ICP (ideal customer profile) в GPT, который генерирует набор фильтров (keywords, titles, exclusions). Для новых сегментов или быстрой адаптации под изменившийся ICP без ручной подготовки .md.

## Оценка объёмов (v4)

| Сегмент | Компании | Контакты |
|---------|----------|----------|
| INFLUENCER_PLATFORMS | 3,000–5,000 | 3,000–5,000 |
| AFFILIATE_PERFORMANCE | 800–1,500 | 800–1,500 |
| IM_FIRST_AGENCIES | 1,500–3,000 | 1,500–3,000 |
| **Всего** | **5,300–9,500** | **5,300–9,500** |
