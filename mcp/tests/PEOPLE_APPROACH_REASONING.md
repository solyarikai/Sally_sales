# People Search Approach — Final Reasoning

## Test Date: 2026-04-01

## What was tested

5 Italian fashion companies (Versace, Etro, Dondup, GCDS, Casadei) with 4 approaches:
- A: person_seniorities only → 3-25 people (4-30 with email)
- B: person_titles only → 0-18 people (0-7 with email)  
- C: seniorities + titles combined → 0-3 (AND behavior kills it)
- D: no filter → 16-20 people (includes juniors)

## Key Findings

### 1. Seniorities search is the BEST single approach
Returns real C-level/directors/VPs: CFO, Commercial Director, Head of Sales, Executive Director.
These ARE decision makers even if titles don't match GPT's prediction exactly.

### 2. Title search adds almost nothing
GPT predicted: "CEO, CMO, Head of E-commerce, VP Retail"
Apollo actually has: "VP Human Resources, Sustainability Director, Global Commercial Director"
Title matching fails because Apollo titles are different from GPT predictions.
Titles returned 0-1 people vs seniorities returning 3-25.

### 3. Title MATCHING (substring) doesn't work
"cmo" NOT in "Chief Financial Officer" → false
"head of e-commerce" NOT in "Head of Communications" → false
0 preferred matches across all 5 companies.
Need SEMANTIC matching (GPT), not substring.

### 4. Combined seniorities+titles = AND (kills results)
Versace: 25+18 separate → only 3 combined. Apollo treats them as AND.

### 5. "No filter" gives everyone including interns
Not useful for finding decision makers.

## Raw Apollo Response Format

From /mixed_people/api_search (FREE):
```json
{
  "id": "54ec1f9b7468694311d4a954",
  "first_name": "Fabrizio",
  "last_name_obfuscated": "Co***o",
  "title": "Vice President Human Resources",
  "has_email": true,
  "has_city": true,
  "has_direct_phone": "Yes",
  "organization": {"name": "Versace", "has_industry": true}
}
```
NO actual email, NO full last name — that's behind bulk_match (1 credit).

## Final Approach Decision

### KEEP: Single seniority search per company
```
person_seniorities: ["owner", "founder", "c_suite", "vp", "head", "director"]
per_page: 25
```
This returns 3-25 people per company, all C-level/director/VP.

### DROP: Title search as separate request
Adds 0-1 people, not worth the extra API call.

### CHANGE: Prioritization from substring → semantic
Instead of: `if "cmo" in title.lower()` (fails)
Use: take all has_email=true people, sort by seniority level, take top 3.

Seniority priority order:
1. owner/founder (decision maker)
2. c_suite (CEO, CFO, CMO — budget authority)
3. vp (VP Sales, VP Marketing — influence)
4. head (Head of Sales, Head of Digital — operational)
5. director (Director of..., — execution)

### For offer-specific prioritization (future improvement):
Use GPT-4o-mini to rank the 5-25 seniority candidates:
"Given these people at {company} and the offer {offer}, which 3 are most likely to buy?"
Cost: ~$0.001 per company. But only needed when >3 candidates have emails.

## Cost Per Company (final)
- 1 FREE search (seniorities, per_page=25)
- Filter has_email=true → typically 3-10 candidates
- Take top 3 by seniority
- bulk_match those 3 → 3 credits
- **Total: 3 credits per company ($0.03)**

## Full Raw Apollo Responses
Saved to: tests/tmp/apollo_raw_people_{timestamp}.json
