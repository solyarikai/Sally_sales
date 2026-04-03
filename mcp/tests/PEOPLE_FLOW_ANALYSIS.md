# People Extraction Flow — Full Analysis

## The Flow (current)

```
Step 1: infer_people_roles (GPT-4o-mini)
  Input: project offer text
  Output: person_titles=["CMO","Head of E-commerce","Director of Retail"], person_seniorities=["c_suite","head","director"]
  Cost: ~$0.001

Step 2: /mixed_people/api_search (FREE)
  Input: domain, limit=6 (2x target to allow filtering)
  Output: partial profiles (name, title, LinkedIn, person_id) — NO emails yet
  Cost: FREE

Step 3: /people/bulk_match (1 credit per person)
  Input: person_ids from step 2
  Output: full profiles WITH emails, email_status, phone
  Cost: 1 credit per net-new email returned
  
Step 4: Smart filtering
  - Prefer people matching inferred titles
  - Take top 3 (max_people_per_company)
  
Step 5: Store in extracted_contacts table
```

## REAL EXTRACTED PEOPLE — Fashion Italy (Run #413, 150 people)

Sample from DB (first 20):

| Name | Email | Title | Company | Verified? |
|------|-------|-------|---------|-----------|
| Stefano Sica | s.sica@120percento.com | Group CFO | 120% Lino | true |
| Antonio Alvino | antonio.alvino@antonia.it | Men's Buyer | Antonia | true |
| Danilo Bergamini | danilo.bergamini@lucafaloni.com | Retail Operations Manager | Luca Faloni | true |
| Charlotte Jones | charlotte.jones@lucafaloni.com | Ecommerce Manager | Luca Faloni | true |
| Sabrina Fenoglio | s.fenoglio@aquazzura.com | Global HR Director | Aquazzura | true |
| Valeria Garbarino | valeria.garbarino@dondup.com | Global Commercial Director | Dondup | true |
| Sharon Vit | sharon.vit@slowear.com | Global Retail Director | Slowear | true |
| Giordano Calza | giordano@gcds.it | Executive Chairman | GCDS | true |
| Margherita Gigante | margherita.gigante@gcds.it | E-Commerce & Marketplace Store Manager | GCDS | true |

**ALL 20 have `is_verified: true` in source_data** — Apollo verified emails.

## PROBLEMS FOUND

### 1. email_verified column NOT populated
The `email_verified` column in `extracted_contacts` is NULL for all records.
The `is_verified` flag IS in `source_data` JSON but never extracted to the column.
**FIX**: Set `email_verified = source_data.is_verified` during extraction.

### 2. Titles are NOT filtered by offer
The GPT inferred titles for TFP should be: CMO, Head of E-commerce, Director of Retail Operations.
But actual extracted people include: HR Manager, Fashion Buyer, HR Coordinator, Product Developer, Store Manager.
**These are NOT decision makers for a resale platform.**

The `extract_people` handler searches WITHOUT titles first (for reliability), then does
smart filtering. But with only 3 people per company returned from bulk_match, there's
no room to filter — we take whatever Apollo gives us.

### 3. Credit cost per pipeline
For 150 people: ~150 bulk_match credits (1 per person).
For 50 target companies × 3 people = 150 credits just for email enrichment.
**This is expensive — $1.50 for emails alone.**

## APOLLO ENDPOINT OPTIMIZATION

| Endpoint | Cost | What you get |
|----------|------|-------------|
| `/mixed_people/api_search` | FREE | Name, title, LinkedIn, person_id — NO email |
| `/people/bulk_match` | 1 credit/person | Full profile + email + email_status |
| `/people/match` | 1 credit/person | Same as bulk_match but 1-at-a-time |

### Optimization: Search MORE people (free), enrich FEWER (paid)

Current: search 6 → enrich all 6 → keep 3 = waste 3 credits
Better: search 20 (free) → filter to best 3 by title match → enrich only those 3

```
OPTIMIZED FLOW:
Step 1: /mixed_people/api_search (per_page=20, FREE)
  → Get 20 people with names + titles (no emails)

Step 2: Client-side filter by inferred titles
  → Pick 3 best matches (CMO, VP Sales, Head of E-commerce)

Step 3: /people/bulk_match (3 credits)
  → Get emails only for the 3 selected people

SAVINGS: 150 people → 150 credits (was 300+ because 6 enriched per company)
FURTHER: If we only enrich 3 per company (the ones that match titles), 
  50 companies × 3 = 150 credits total (same cost but better people)
```

### Even better: batch across companies

```
/people/bulk_match accepts arrays.
Instead of 50 separate calls (1 per company, 3 IDs each),
send 1 bulk call with all 150 IDs at once.
→ Same cost (150 credits) but 1 API call instead of 50.
```

## WHAT THE MAIN APP DOES DIFFERENTLY
why 
Main backend (`backend/app/services/apollo_service.py`):
- Same 2-step flow (search free → bulk_match paid)
- BUT populates `email_verified` column on ExtractedContact
- AND includes `email_status` in SmartLead campaign upload

MCP lost the `email_verified` column population in the refactor.

## RECOMMENDATIONS

1. **Populate email_verified** from `source_data.is_verified` during extraction
2. **Search 20 people free, filter to 3 by title, enrich only 3** — saves credits
3. **Batch bulk_match calls** — 1 call for all 150 IDs instead of 50 calls
4. **Filter by email_status="verified" before storing** — only keep verified emails
5. **Show email verification status in pipeline UI and CRM**
