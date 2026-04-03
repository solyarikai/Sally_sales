# V4 Opus Full Review — Improvements Needed for V5

## Reviewed by: 4 parallel Opus agents analyzing all 546 targets

## False Positive Patterns Found (for V5 prompt)

### Pattern 1: SOLO CONSULTANTS still passing (V4 didn't fully fix)
Despite V4 adding "solo consultant = NOT_A_MATCH", these still pass:
- caledonia-resources.com — "Fractional CoS/CHRO" = IS a freelancer, not a hirer
- creighton-consultancy.com — one person, "50 years experience"
- maataraglobal.com — solo founder advisory, ex-Apple
- mandalus.com — sole "Managing Owner", deal broker
- sl-partners.co — IFZA free zone (cheapest setup), no team
- stratand.com — no team, minimal web presence
- performancefacilitiesmanagement.com — 1 person FM consultant

**V5 fix:** Add specific patterns:
- "Fractional" in company description = solo freelancer = NOT_A_MATCH
- IFZA/RAKEZ free zone with no team page = likely solo = NOT_A_MATCH
- Only one person named on entire website = NOT_A_MATCH
- "Managing Owner" as only title = solo = NOT_A_MATCH

### Pattern 2: NON-UAE still leaking through
- aquilagroup.biz — Singapore-based
- ignitedigital.com — CANADIAN (Toronto-based)
- lubnanona.com — "Our Lebanon" in Arabic
- omanad.net — Oman (different country!)
- brandacy.in — .in domain = India
- techcybers.com — India/Pakistan-based
- webkatalyst.com — Indian naming pattern
- penta-technology.ch — Swiss
- cmsitservices.com — Indian HQ (Mumbai/Bangalore)
- flentas.com — Indian HQ

**V5 fix:** Stronger domain TLD rules:
- .in = India = NOT_A_MATCH
- .ch = Swiss = NOT_A_MATCH
- .com.au = Australia = NOT_A_MATCH
- Company name contains "India", "Pakistan", "Pvt Ltd", "Private Limited", "LLP" = likely NOT UAE
- "Pvt Ltd" / "Private Limited" = Indian/Pakistani company designation, NOT UAE entity type

### Pattern 3: INVESTMENT/HOLDING still leaking
- 01lab.ae — venture studio / investment fund
- healthtechnology.consulting — MedTech investment advisory, M&A
- dhowholding.com — investment & venture-building firm

**V5 fix:** Expand exclusion:
- "Venture studio", "venture capital", "angel investment" = NOT_A_MATCH
- "M&A", "capital raising", "fund management" = NOT_A_MATCH
- Any company focused on INVESTING in other companies = NOT_A_MATCH

### Pattern 4: GOVERNMENT-LINKED / TOO LARGE
- mubadala-related entities — sovereign wealth fund, enterprise procurement
- Very large enterprises with 1000+ employees

**V5 fix:** Add:
- Sovereign wealth funds, government entities = NOT_A_MATCH
- Companies with 1000+ employees = too large for EasyStaff

### Pattern 5: MISCLASSIFIED business types
- mone.ae — "M One Computers" = hardware store, not digital agency
- mysearchglobalrewards.com — rewards platform, not agency
- thepromotars.com — e-commerce reseller, not agency

**V5 fix:** Add to exclusion:
- Computer/hardware stores = NOT_A_MATCH
- Rewards/loyalty platforms = NOT_A_MATCH
- E-commerce resellers = NOT_A_MATCH (different from e-commerce agencies)

## Quantified Impact

| Segment | Reviewed | OK | Borderline | False Positive | FP Rate |
|---------|----------|-----|-----------|----------------|---------|
| CONSULTING_FIRM | 49 | 20 | 13 | 16 | 33% |
| DIGITAL_AGENCY | 95 | 64 | 18 | 13 | 14% |
| IT_SERVICES | 127 | 88 | 22 | 17 | 13% |
| Others | ~275 | TBD | TBD | TBD | TBD |
| **Total (3 segments)** | **271** | **172** | **53** | **46** | **17%** |

## Estimated accuracy: 83% (was thought to be 97% from small sample)

The V4 small-batch test showed 97% but full-corpus review shows ~83%. The prompt needs V5 iteration.

## V5 Prompt Changes Required

Add to EXCLUSION section:
```
COMPANY STRUCTURE SIGNALS (NOT_A_MATCH):
- "Pvt Ltd", "Private Limited", "LLP" in company name = Indian/Pakistani entity, not UAE
- "Fractional CxO", "Fractional leadership" = solo freelancer, not a company
- Only ONE person identifiable on entire website = solo consultant
- IFZA, RAKEZ free zone with no team page = likely 1-person setup
- Company name is a person's name (e.g., "John Smith Consulting") = solo

INVESTMENT (NOT_A_MATCH):
- Venture studios, VCs, angel investors, fund managers
- M&A advisory, capital raising, investment banking
- Sovereign wealth funds, government investment vehicles

TOO LARGE (NOT_A_MATCH):
- Companies with 1000+ employees
- Government-linked mega-corporations

WRONG COUNTRY (NOT_A_MATCH):
- Oman (.om), Lebanon, Singapore, Canada — neighboring/similar but NOT UAE
- Company name contains country name: "India", "Pakistan", "Oman", "Lebanon"
- .in, .pk, .ch, .com.au, .ca domains without explicit Dubai/Abu Dhabi/UAE address on site
```
