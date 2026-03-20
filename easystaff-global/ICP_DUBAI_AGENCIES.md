# ICP: EasyStaff Global — Dubai Agencies Segment

## What EasyStaff sells
International freelancer/contractor payment platform. Companies use it to pay remote workers in other countries — handles compliance, payroll, payments.

## Who we're gathering
**Digital agencies, tech companies, and creative studios in UAE** that hire freelancers and remote contractors for their projects.

These companies ARE the customers — they need EasyStaff to pay their freelancers internationally.

## Target criteria

### GOOD targets (score high)
- Digital marketing agency, 20 employees, does web development projects with freelancers
- Software development company, 15 people, likely has remote contractors
- Creative/branding agency, 30 employees, outsources design to freelancers
- SaaS startup, 10 people, has remote developers
- IT services company, 50 employees, uses contractors for projects
- Video/animation production studio with freelance artists
- Game studio with remote developers
- E-commerce agency managing campaigns with freelancers

### BAD targets (score 0, reject)
- **Staffing agencies, recruitment firms** — COMPETITORS (Toptal, BairesDev, Robert Half, etc.)
- **Nearshoring/offshoring providers** — COMPETITORS
- **EOR/PEO platforms** — COMPETITORS (Deel, Remote.com, Oyster, Papaya Global)
- **Freelance marketplaces** — COMPETITORS (Fiverr, Upwork)
- **HR tech companies** selling workforce tools — COMPETITORS
- Construction, real estate, restaurants, hotels — offline, no freelancers
- Government, schools, hospitals — institutional
- Banks, insurance — regulated, won't use EasyStaff
- Trading, logistics, shipping — offline operations

### Size
5-200 employees ideal. Under 5 = too small. Over 200 = likely has internal HR/payroll.

### Geography
UAE: Dubai, Abu Dhabi, Sharjah primarily. Also Ajman, RAK.

### Key signal
The company DELIVERS digital/creative services using a team that likely includes freelancers. NOT a company that SELLS staffing/recruitment services.

## Scoring rubric for GPT analysis
- `industry_match`: 1.0 = digital agency/tech/creative. 0.5 = adjacent (consulting). 0.0 = offline
- `service_match`: 1.0 = delivers project-based services (needs freelancers). 0.0 = sells products only
- `company_type`: 1.0 = operating agency/studio. 0.0 = aggregator/directory/marketplace
- `geography_match`: 1.0 = UAE based. 0.5 = regional. 0.0 = no UAE presence
- `language_match`: 1.0 = English or Arabic site. 0.0 = irrelevant language

## Current prompt (v1)
Stored in `gathering_prompts` table, ID 7, hash `ec6bd15b...`

## How to improve
After reviewing analysis results:
1. Check false positives (competitors marked as targets) → add to exclusion list
2. Check false negatives (good agencies rejected) → adjust scoring thresholds
3. Check `analysis_results.raw_output._prompt_sent` for the exact prompt used
4. Create new prompt version via `POST /api/pipeline/gathering/prompts`
5. Re-analyze via `POST /api/pipeline/gathering/runs/{id}/re-analyze`
