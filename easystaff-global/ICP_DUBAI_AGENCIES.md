# ICP: EasyStaff Global — Dubai Agencies Segment

## What EasyStaff sells
International freelancer/contractor payment platform. Companies use it to pay remote workers in other countries.

## Who we're gathering
Companies in UAE that deliver digital/creative/tech services and hire freelancers for their projects.

## Analysis approach: VIA NEGATIVA

**Primary job of GPT: find shit and exclude it.** If it's not shit, assign a segment.

GPT-4o-mini is NOT good at complex multi-dimensional scoring. It IS good at pattern matching: "is this a restaurant? yes → reject." So the prompt focuses on EXCLUSION PATTERNS, not scoring rubrics.

### Output format
```
SEGMENT_TAG
Reasoning: why this segment, what the company does
```

If rejected:
```
NOT_A_MATCH
Reasoning: why rejected (competitor/offline/irrelevant)
```

`SEGMENT_TAG` is ALWAYS the first line, CAPS_LOCKED with underscores. Parseable algorithmically: `segment = output.split('\n')[0].strip()`

## Target segments (CAPS_LOCKED constants)

| Segment | Description | Example |
|---------|-------------|---------|
| `DIGITAL_AGENCY` | Web dev, digital marketing, SEO, PPC | Agency doing Shopify stores |
| `CREATIVE_STUDIO` | Design, branding, video, photography | Branding agency in DIFC |
| `SOFTWARE_HOUSE` | Custom software, app development | Company building mobile apps |
| `IT_SERVICES` | Managed IT, cloud, DevOps, infra | Cloud consulting firm |
| `MARKETING_AGENCY` | Advertising, PR, social media, content | Social media management agency |
| `TECH_STARTUP` | SaaS, fintech, edtech, healthtech product | AI startup with 20 devs |
| `MEDIA_PRODUCTION` | Video, animation, audio, broadcasting | Animation studio |
| `GAME_STUDIO` | Game development, interactive media | Mobile game developer |
| `CONSULTING_FIRM` | Management, strategy, tech consulting | Digital transformation consultancy |
| `ECOMMERCE_COMPANY` | Online retail, D2C brands with tech teams | E-commerce brand with dev team |
| `NOT_A_MATCH` | **HARDCODED DEFAULT** — everything that doesn't fit above | Restaurant, bank, competitor |

GPT can propose NEW segment tags if a company doesn't fit existing ones but IS a legitimate target. New tags follow the same format: `CAPS_LOCKED_WITH_UNDERSCORES`.

## Exclusion patterns (via negativa — things that DEFINITELY SUCK)

### COMPETITORS (always NOT_A_MATCH)
- Staffing agencies, recruitment firms, headhunting
- Nearshoring/offshoring service providers (Toptal, BairesDev, Andela, Turing)
- EOR/PEO platforms (Deel, Remote.com, Oyster, Papaya Global, Multiplier)
- Freelance marketplaces (Fiverr, Upwork, Freelancer.com)
- HR tech companies selling workforce management tools
- Payroll providers (our direct competitors)
- Any company whose PRODUCT is "hire people" or "find talent"

### OFFLINE BUSINESSES (always NOT_A_MATCH)
- Restaurant, cafe, bakery, catering, food delivery
- Hotel, resort, spa, salon, beauty
- Construction, contracting, real estate, property management
- Trading, import/export, wholesale, retail store
- Shipping, freight, cargo, logistics, warehouse
- Oil, gas, petroleum, mining, metals
- Medical, hospital, clinic, pharmacy, dental
- School, university, nursery
- Car dealer, garage, auto repair
- Furniture, textile, garment, jewelry
- Travel agency, tourism, airline
- Church, mosque, temple

### INSTITUTIONAL (always NOT_A_MATCH)
- Government, ministry, municipality
- Banks, insurance, exchange
- Law firms (most don't use freelancers)
- Large enterprise (>500 employees, has internal HR)

### JUNK SITES (always NOT_A_MATCH)
- Aggregators, directories, listing sites
- Job boards, classifieds
- News sites, blogs, forums
- Domain parked, under construction, empty

## Anti-examples from actual pipeline results (things GPT wrongly marked as target)

| Domain | Name | Why it SUCKS |
|--------|------|-------------|
| crayonsys.com | CRAYONSYS Cloud Consulting | Has "flexible staffing capabilities" — borderline competitor |
| _any staffing site_ | Any "we provide talent" | COMPETITOR — they sell what we sell |

## Size filter
5-200 employees. Under 5 = solo freelancer. Over 200 = has HR department.

## Stored in DB
- Prompt: `gathering_prompts` table (create new version for each iteration)
- Results: `analysis_results.segment` = the CAPS_LOCKED tag
- Full output: `analysis_results.raw_output` (includes `_prompt_sent`)
- Filters: `gathering_runs.filters` (Apollo search parameters)

## Iteration workflow
1. Run analysis with current prompt
2. Review targets: `SELECT domain, name, segment, reasoning FROM analysis_results WHERE is_target = true`
3. Find false positives → add to anti-examples in this doc
4. Find false negatives → adjust exclusion patterns
5. Create new prompt version: `POST /api/pipeline/gathering/prompts`
6. Re-analyze: `POST /api/pipeline/gathering/runs/{id}/re-analyze`
7. Compare: `GET /api/pipeline/gathering/analysis-runs/{a}/compare/{b}`
