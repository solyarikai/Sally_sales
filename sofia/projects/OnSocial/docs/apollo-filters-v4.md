# Apollo Filters v4 — OnSocial (3 segments, expanded)

> Date: 2026-03-31
> Based on: v3 filters (exhausted), same 3 segments with expanded reach
> Changes from v3: ALL GEO (no location filter), expanded management levels (+senior), broader excluded titles, reworked company keywords to catch adjacent companies missed by v3
> Purpose: filters only — apply cross-segment exclusions from v3 (competitor blacklist, negative responders, active pipeline)

---

## What changed from v3


| Parameter        | v3                       | v4                                                                                |
| ---------------- | ------------------------ | --------------------------------------------------------------------------------- |
| Location         | 10-12 priority countries | **ALL GEO** (no location filter)                                                  |
| Management Level | varied per segment       | **Unified: c_suite, vp, director, owner, head, partner, founder**                 |
| Excluded Titles  | basic list               | **Expanded** — covers senior ICs that slip through with "senior" management level |
| Company Keywords | original set             | **Reworked** — adjacent keywords to catch companies v3 missed                     |


---

## Segment 1 — INFLUENCER_PLATFORMS (expanded)

SaaS companies building influencer/creator products, social listening tools, creator marketplaces, analytics platforms — plus adjacent companies in social intelligence, earned media, and content analytics that v3 missed.

### Company filters

**Industry**

```
Computer Software, Internet, Marketing & Advertising,
Information Technology, Online Media
```

**Company Keywords — ANY of**

```
influencer marketing platform, creator analytics, creator marketplace,
influencer platform, social media analytics, UGC platform,
creator economy, audience analytics, influencer API,
social listening, brand monitoring, creator data,
influencer discovery, creator tools, influencer intelligence,
audience intelligence, social data,
social intelligence platform, content intelligence,
earned media platform, earned media analytics,
digital PR platform, media monitoring platform,
creator CRM, creator relationship management,
talent marketplace technology, social ROI platform,
reputation management platform, sentiment analysis platform,
social media intelligence, brand intelligence,
content analytics platform, engagement analytics,
creator economy infrastructure, social proof platform,
review management platform, word of mouth platform
```

> New keywords (not in v3): social intelligence, earned media, digital PR platform, media monitoring, creator CRM, talent marketplace technology, social ROI, reputation management, sentiment analysis, brand intelligence, content analytics, social proof, review management, word of mouth. These target adjacent companies that need creator/audience data but don't describe themselves as "influencer marketing."

**Excluded Company Keywords**

```
recruitment, staffing, accounting, legal, healthcare,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
web design only, SEO only, PPC only, print,
freelance, solo consultant,
antivirus, cybersecurity, network monitoring,
IT infrastructure, cloud hosting, data center,
ERP, payroll, HRIS, applicant tracking
```

**# Employees:** 5-5,000

**Location:** ALL GEO (no filter)

### People filters

**Job Titles**

```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
Head of Product, Chief Product Officer, VP Product,
Director of Engineering, Director of Product,
Co-Founder, Founder, CEO, COO,
Senior Director of Engineering, Senior Director of Product,
Senior VP Engineering, Senior VP Product,
Head of Data, VP Data, Chief Data Officer,
Head of Platform, VP Platform
```

**Management Level:** c_suite, vp, director, owner, head, partner, founder

**Excluded Titles**

```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Customer Success, Support, HR, People, Recruiter,
Content Writer, Designer, Social Media Manager,
Solutions Architect, Technical Architect, Enterprise Architect,
Staff Engineer, Principal Engineer, Lead Engineer, Lead Developer
```

> Expanded exclusions: since management level now includes "senior," we must explicitly exclude senior individual contributors (engineers, designers, analysts, sales reps, recruiters, etc.) who are NOT decision-makers for API/data purchases.

---

## Segment 2 — AFFILIATE_PERFORMANCE (expanded)

Affiliate networks, performance marketing platforms, partnership platforms — plus adjacent loyalty, rewards, cashback, and attribution platforms converging with the creator/affiliate space.

### Company filters

**Industry**

```
Computer Software, Internet, Marketing & Advertising,
Information Technology, E-commerce, Online Media
```

**Company Keywords — ANY of**

```
affiliate marketing, affiliate network, affiliate platform,
performance marketing platform, partner marketing,
partnership platform, social commerce, creator commerce,
influencer affiliate, referral marketing, affiliate tracking,
partner ecosystem, performance partnerships,
affiliate management platform, commission tracking,
creator monetization, link in bio, creator storefront,
loyalty platform, loyalty program technology,
rewards platform, cashback platform, coupon platform,
deal platform, offer platform,
attribution platform, marketing attribution,
multi-touch attribution, conversion tracking platform,
partner relationship management, channel partner platform,
reseller platform, marketplace monetization,
creator payments platform, payout platform creators,
referral program platform, ambassador platform technology,
revenue sharing platform
```

> New keywords (not in v3): loyalty/rewards/cashback/coupon/deal platforms (converging with affiliate), attribution/conversion tracking (performance measurement), partner relationship management, channel partner, marketplace monetization, creator payments, ambassador platform tech, revenue sharing. These capture the affiliate-adjacent ecosystem.

**Excluded Company Keywords**

```
affiliate agency, affiliate management service,
SEO agency, PPC agency, web design, software development,
recruitment, HR, staffing, healthcare, legal, accounting,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, print, media buying agency,
antivirus, cybersecurity, network monitoring,
IT infrastructure, cloud hosting, data center,
ERP, payroll, HRIS, applicant tracking,
banking, credit union, lending platform,
crypto exchange, blockchain wallet
```

**# Employees:** 20-5,000

**Location:** ALL GEO (no filter)

### People filters

**Job Titles**

```
CTO, VP Engineering, VP of Engineering, VP Product,
Head of Product, Chief Product Officer, Head of Engineering,
Director of Engineering, Director of Product,
VP Partnerships, Head of Partnerships, Director of Partnerships,
Co-Founder, Founder, CEO, COO,
Senior Director of Engineering, Senior Director of Product,
Senior Director of Partnerships, Senior VP Partnerships,
Head of Data, VP Data, Chief Data Officer,
Head of Platform, VP Platform,
Head of Growth, VP Growth, Director of Growth
```

**Management Level:** c_suite, vp, director, owner, head, partner, founder

**Excluded Titles**

```
Intern, Junior, Assistant, Student, Freelance,
Marketing Manager, Sales Representative, Account Executive,
Account Manager, Customer Success, Support, HR, People,
Recruiter, Content Writer, Designer, Social Media Manager,
Affiliate Manager, Partner Manager, Solutions Architect, Technical Architect, Enterprise Architect,
Staff Engineer, Principal Engineer, Lead Engineer, Lead Developer
```

> Same expanded IC exclusions plus segment-specific: Senior Affiliate Manager, Senior Partner Manager (execution roles, not product/API decision-makers).

---

## Segment 3 — IM_FIRST_AGENCIES (expanded)

Agencies where influencer marketing is the core business — plus adjacent creative studios, content studios, and talent management firms that v3 missed.

### Company filters

**Industry**

```
Marketing & Advertising
```

> Still intentionally narrow — only Marketing & Advertising. PR firms = 0 conversions (unchanged from v3).

**Company Keywords — ANY of**

```
influencer marketing agency, influencer agency,
creator agency, influencer management, creator campaigns,
influencer marketing, creator partnerships,
TikTok agency, influencer talent, creator talent,
influencer strategy, UGC agency,
creator studio, content studio influencer,
branded content studio, creative studio influencer,
talent management agency creator, digital talent agency,
creator representation, influencer representation,
social-first agency, creator-first agency,
influencer activation agency, creator activation,
micro-influencer agency, nano-influencer agency,
influencer seeding agency, gifting agency,
creator network agency, influencer collective
```

> New keywords (not in v3): creator/content/branded content studio, talent management/representation, social-first/creator-first agency, influencer activation, micro/nano-influencer agency, seeding/gifting agency, creator network/collective. These catch agencies that don't use the exact phrase "influencer marketing agency" but do IM as core business.

**Excluded Company Keywords**

```
SEO agency, PPC agency, web design, software development,
recruitment, HR, staffing, healthcare, legal, accounting,
logistics, manufacturing, real estate, fintech, insurance,
construction, education, nonprofit, government, defense,
food service, restaurant, hospitality, travel agency,
freelance, solo consultant, print, media buying only,
PR agency, public relations, crisis communications,
web development, app development, branding only,
market research, consulting firm, management consulting,
antivirus, cybersecurity, IT infrastructure,
modelling agency, casting agency, event management only,
photography studio only, video production only,
translation agency, localization agency
```

> Added: modelling/casting agency, event management, photography/video production only, translation/localization — these sometimes appear in "Marketing & Advertising" but are not IM agencies.

**# Employees:** 10-500

**Location:** ALL GEO (no filter)

### People filters

**Job Titles**

```
CEO, Founder, Co-Founder, Managing Director, Managing Partner,
Head of Influencer Marketing, Director of Influencer,
Head of Influencer, VP Strategy, Head of Partnerships,
Director of Client Services, Head of Strategy,
General Manager, Partner, Owner,
Senior Partner, Senior Managing Director,
Head of Creator Partnerships, Director of Creator,
Head of Talent, Director of Talent,
Head of Growth, Director of Business Development,
Head of Operations, Director of Operations
```

**Management Level:** c_suite, vp, director, owner, head, partner, founder

**Excluded Titles**

```
Intern, Junior, Assistant, Student, Freelance,
Campaign Manager, Campaign Coordinator,
Social Media Manager, Content Creator, Designer,
Account Coordinator, Media Planner, Media Buyer,
PR Manager, Communications Manager,
HR, People, Recruiter, Finance, Accounting,
Executive Assistant, Office Manager, Operations Coordinator,
Community Manager, Senior Community Manager,
Influencer Coordinator, Senior Influencer Coordinator,
Talent Coordinator, Senior Talent Coordinator
```

> Added: senior versions of all execution roles, plus Influencer/Talent Coordinator (junior roles at agencies that slip through with "senior" management level).

---

## Cross-segment exclusions

Same as v3 — apply competitor blacklist, negative responder blacklist, and active pipeline blacklist from apollo-filters-v3.md to ALL segments.

---

## Volume estimates (v4 vs v3)


| Segment               | v3 est. contacts | v4 est. contacts | Delta                                        |
| --------------------- | ---------------- | ---------------- | -------------------------------------------- |
| INFLUENCER_PLATFORMS  | 1,500-2,500      | 3,000-5,000      | +2x (all geo + adjacent keywords)            |
| AFFILIATE_PERFORMANCE | 400-800          | 800-1,500        | +2x (all geo + loyalty/attribution keywords) |
| IM_FIRST_AGENCIES     | 800-1,500        | 1,500-3,000      | +2x (all geo + studio/talent keywords)       |
| **Total**             | **2,700-4,800**  | **5,300-9,500**  | **~2x expansion**                            |


> Estimates assume ~40-50% of new contacts are net-new (not already in v3 exports). Real unique contacts: ~2,500-4,500 incremental.

---

## Important: deduplication

Since v3 filters were already exhausted, v4 results WILL overlap with v3 exports. Before uploading to SmartLead:

1. Export v4 results
2. Deduplicate against existing blacklist + leads + exclusion list
3. Only process net-new contacts

---

## Filter validation checklist (same as v3)

Before launching any segment, verify with a 25-company sample:

- Run `search_people` with `per_page=1` to get actual `total_count`
- Scrape 25 websites from the Apollo export
- Manually check: does this company actually match the segment?
- If <70% match — tighten keywords or add exclusions
- If >90% match — proceed
- Cross-check against Sally's successful leads — would they have been caught?
- Cross-check against Sally's failures — would they have been excluded?

