# GetSales — CSV Format Rules

## Source of Truth

Format defined in `magnum-opus/scripts/sofia/onsocial_universal_pipeline.py` → `GETSALES_HEADERS` (line ~1879) + `export_getsales()` function.

Generated files go to: `sofia/get_sales_hub/{DD_MM}/`  
Filename pattern: `GetSales — {SEGMENT}_without_email — {DD.MM}.csv`

---

## 49 Columns — Exact Order

| # | Column | Source | Notes |
|---|--------|--------|-------|
| 1 | `system_uuid` | — | always empty |
| 2 | `pipeline_stage` | — | always empty |
| 3 | `full_name` | `first_name + " " + last_name` | generated |
| 4 | `first_name` | `first_name` | required |
| 5 | `last_name` | `last_name` | required |
| 6 | `position` | `title` | note: source field is `title`, not `position` |
| 7 | `headline` | — | always empty |
| 8 | `about` | — | always empty |
| 9 | `linkedin_id` | extract from `linkedin_url` | same as `linkedin_nickname` |
| 10 | `sales_navigator_id` | — | always empty |
| 11 | `linkedin_nickname` | extract `/in/{nickname}` from URL | generated, required for GetSales |
| 12 | `linkedin_url` | `linkedin_url` | must start with `https://`; required identifier |
| 13 | `facebook_nickname` | — | always empty |
| 14 | `twitter_nickname` | — | always empty |
| 15 | `work_email` | `email` | empty for LinkedIn-only contacts |
| 16 | `personal_email` | — | always empty |
| 17 | `work_phone` | — | always empty |
| 18 | `personal_phone` | — | always empty |
| 19 | `connections_number` | — | always empty |
| 20 | `followers_number` | — | always empty |
| 21 | `primary_language` | — | always empty |
| 22 | `has_open_profile` | — | always empty |
| 23 | `has_verified_profile` | — | always empty |
| 24 | `has_premium` | — | always empty |
| 25 | `location_country` | `country` or `company_country` | use if available |
| 26 | `location_state` | — | always empty |
| 27 | `location_city` | `city` | use if available |
| 28 | `active_flows` | — | always empty |
| 29 | `list_name` | `"{SEGMENT} Without Email {YYYY-MM-DD}"` | e.g. `INFPLAT Without Email 2026-03-31` |
| 30 | `tags` | `segment` | e.g. `INFLUENCER_PLATFORMS`, `IM_FIRST_AGENCIES` |
| 31 | `company_name` | `company_name` | run through `normalize_company()` |
| 32 | `company_industry` | — | always empty |
| 33 | `company_linkedin_id` | — | always empty |
| 34 | `company_domain` | `domain` | |
| 35 | `company_linkedin_url` | — | always empty |
| 36 | `company_employees_range` | `employees` | use if available |
| 37 | `company_headquarter` | — | always empty |
| 38 | `cf_location` | `company_country` or `country` | custom field for sequences |
| 39 | `cf_competitor_client` | `social_proof` | e.g. "Modash, Captiv8, and Lefty" |
| 40 | `cf_message1` | — | sequence variable, filled later |
| 41 | `cf_message2` | — | sequence variable, filled later |
| 42 | `cf_message3` | — | sequence variable, filled later |
| 43 | `cf_personalization` | — | sequence variable, filled later |
| 44 | `cf_compersonalization` | — | sequence variable, filled later |
| 45 | `cf_personalization1` | — | sequence variable, filled later |
| 46 | `cf_message4` | — | sequence variable, filled later |
| 47 | `cf_linkedin_personalization` | — | sequence variable, filled later |
| 48 | `cf_subject` | — | sequence variable, filled later |
| 49 | `created_at` | today's date `YYYY-MM-DD` | |

---

## Required Fields (GetSales won't accept without these)

- `linkedin_url` OR `work_email` — at least one identifier required
- `first_name` + `last_name` — for contact creation
- `linkedin_nickname` — extracted from URL, must match `/in/{nickname}`

## Key Rules

1. **`linkedin_url` must start with `https://`** — pipeline adds prefix if missing
2. **`linkedin_nickname` = `linkedin_id`** — both extracted from URL via regex `linkedin\.com/in/([^/?]+)`
3. **`cf_location` ≠ `location_country`** — cf_location is for sequence personalization (company geo), location_country is the person's geo
4. **`tags` = segment code** — use raw segment value: `INFLUENCER_PLATFORMS`, `IM_FIRST_AGENCIES`, `AFFILIATE_PERFORMANCE`, `SOCIAL_COMMERCE`
5. **`position` source is `title`** — in pipeline data the field is named `title`, GetSales column is `position`
6. **All 49 columns must be present** — even if empty, GetSales CSV import requires exact schema
7. **Encoding**: UTF-8, newline=`""` (csv.DictWriter default)

## When Preparing Manually (Google Sheets)

Column names in Sheets must match the 49-column schema above exactly.  
Do NOT use: `linkedin_url` as `linkedin`, `title` as `title`, `domain` as `domain` — rename all to GetSales names.

Mapping from standard pipeline sheet → GetSales:
| Pipeline | GetSales |
|----------|---------|
| `title` | `position` |
| `linkedin_url` | `linkedin_url` (keep name, ensure https://) |
| `domain` | `company_domain` |
| `country` | `location_country` + `cf_location` |
| `city` | `location_city` |
| `employees` | `company_employees_range` |
| `segment` | `tags` |
| `social_proof` | `cf_competitor_client` |

Plus generate: `full_name`, `linkedin_nickname`, `linkedin_id`, `list_name`, `created_at`.
