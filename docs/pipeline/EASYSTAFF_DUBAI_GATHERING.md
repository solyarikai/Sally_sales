# EasyStaff Global — Dubai Agencies TAM Gathering

## Project: easystaff global (ID: 9, company_id: 1)

## Current State (March 20, 2026)

### Data in the gathering system

| Run | Source | Strategy | Raw results | New companies | Status |
|-----|--------|----------|-------------|---------------|--------|
| #1 | apollo.people.emulator | strategy_b (seniority) | 5,602 | 3,867 | completed (migrated) |
| #2 | apollo.companies.emulator | industry_tags | 7,782 | 7,782 | completed (migrated) |
| #3 | apollo.people.emulator | strategy_a (80+ keywords) | IN PROGRESS | — | running on Hetzner |

**Total in system: 11,649 discovered companies.**

### Gathering run #1 — Apollo People Tab, Strategy B (seniority)

**Filters applied:**
- Cities: Dubai, Abu Dhabi, Sharjah
- Seniorities: founder, c_suite, owner
- Size ranges: 1-10, 11-20, 21-50, 51-100, 101-200
- Total search configs: 3 cities × 3 seniorities × 5 sizes = 45 searches
- Max pages per search: 10

**Results:** 5,602 raw → 3,867 unique with domains

**What it captures:** ALL founders/CEOs/owners at small companies in UAE. No keyword filtering — catches everything, including offline businesses. Needs PRE-FILTER to remove restaurants/construction/hotels.

### Gathering run #2 — Apollo Companies Tab, Industry Tags

**Filters applied:**
- Location: United Arab Emirates
- Industry tags: IT Services (`5567cd4773696439b10b0000`), Marketing & Advertising (`5567cd467369644d39040000`)
- Keywords: software company, web development, creative agency, digital marketing, social media marketing, event management, staffing, outsourcing, fintech, etc.
- Size ranges: 1-10, 11-20, 21-50, 51-100, 101-200

**Results:** 7,782 companies (NO domains — Companies Tab DOM doesn't expose them)

**Limitation:** Companies have LinkedIn URLs but no domains. Need RESOLVE phase to get domains from LinkedIn.

### Gathering run #3 — Apollo People Tab, Strategy A (80+ keywords) — IN PROGRESS

**Filters (running now on Hetzner):**
- 80+ company name keywords × 3 UAE cities = 321 search configs
- Max pages: 10 per search

**Keywords include:**
- Original 32: marketing agency, digital agency, media production, staffing agency, creative agency, advertising agency, event production, branding agency, consulting firm, design agency, production house, film production, video production, animation studio, PR agency, social media agency, UX agency, content agency, SEO agency, web design, software development, IT services, game studio, talent management, influencer agency, photography studio, SaaS, tech startup, app development, e-commerce, motion graphics, web development
- Professional services: recruitment agency, HR consultancy, HR outsourcing, management consulting, BPO, IT outsourcing, IT consulting, accounting firm, translation services, architecture firm, engineering consultancy, legal services
- Digital/tech: digital marketing, performance marketing, growth agency, data analytics, AI consulting, cloud consulting, cybersecurity, DevOps, mobile development, product design, UI design, PPC agency, email marketing, CRM consulting, software house
- Tech verticals: fintech, edtech, healthtech, proptech, martech, insurtech, logistics tech
- Media: podcast production, music production, VFX studio, CGI, 3D studio, content creation, broadcast
- Broader: digital solutions, creative studio, innovation lab, digital transformation, media agency, communications agency, strategy consulting, market research, technology company

**Expected yield:** 1,500-2,000 new unique companies WITH domains

## What's still untapped in Apollo

### People Tab — more seniorities
- Done: founder, c_suite, owner
- NOT done: vp, director, manager
- Potential: +3,000-5,000 companies (VP/Directors at agencies we missed because they don't have founder-level people)

### People Tab — more cities
- Done: Dubai, Abu Dhabi, Sharjah
- NOT done: Al Ain, Ras Al Khaimah, Ajman, Fujairah, Umm Al Quwain
- Potential: +500-1,000 companies (smaller emirates)

### People Tab — larger companies
- Done: 1-200 employees
- NOT done: 201-500, 501-1000
- Potential: +200-500 companies (mid-size agencies, potential enterprise clients)

### Companies Tab — more industry tags
- Done: IT Services, Marketing & Advertising
- NOT done:
  - Media Production
  - Design
  - E-commerce & Internet
  - Management Consulting
  - Human Resources
  - Events Services
  - Public Relations
  - Education Management / E-Learning
  - Staffing & Recruiting
  - Computer Software
  - Graphic Design
  - Animation
  - Writing & Editing
  - Photography
  - Market Research
  - Translation & Localization
- Potential: +5,000-10,000 companies

### Companies Tab — more keywords
Beyond the 18 already searched:
- "digital transformation", "cloud services", "managed services"
- "creative services", "media buying", "programmatic"
- "conversion optimization", "lead generation"
- "employer branding", "talent acquisition"
- "UX research", "product management"
- Potential: +1,000-3,000 companies

## Target: 20,000 new companies

| Source | Expected yield | Status |
|--------|---------------|--------|
| Strategy B (seniority) — DONE | 3,867 | Migrated |
| Companies Tab (IT + Marketing) — DONE | 7,782 | Migrated |
| Strategy A (80+ keywords) — RUNNING | ~2,000 | In progress on Hetzner |
| Strategy B + more seniorities (vp, director) | ~4,000 | Next |
| Companies Tab + more industry tags | ~5,000 | After Strategy A |
| Companies Tab + more keywords | ~2,000 | After industry tags |
| More UAE cities | ~500 | Last |
| **TOTAL PROJECTED** | **~25,000** | |

## Offline industry exclusion list

These patterns are rejected in PRE-FILTER phase (no AI needed):
restaurant, cafe, catering, food, bakery, kitchen, hotel, hospitality, resort, spa, salon, beauty, construction, contracting, building, real estate, property, trading, import, export, wholesale, retail, supermarket, shipping, freight, cargo, logistics, warehouse, oil, gas, petroleum, mining, steel, metals, medical, hospital, clinic, pharmacy, dental, school, university, nursery, kindergarten, laundry, cleaning, maintenance, plumbing, electrical, car, auto, garage, vehicle, transport, furniture, textile, garment, fabric, jewelry, gold, diamond, watch, travel, tourism, airline, cruise, bank, insurance, exchange, government, ministry, municipality, police, military, church, mosque, temple
