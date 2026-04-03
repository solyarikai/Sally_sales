# V5 Review: TECH_STARTUP / SOFTWARE_HOUSE / GAME_STUDIO / ECOMMERCE_COMPANY

## Summary by Segment

### ECOMMERCE_COMPANY (4 unique companies, 7 lines)
| Verdict | Count |
|---------|-------|
| OK | 4 |
| BORDERLINE | 0 |
| FALSE_POSITIVE | 0 |

### GAME_STUDIO (3 unique companies, 5 lines)
| Verdict | Count |
|---------|-------|
| OK | 3 |
| BORDERLINE | 0 |
| FALSE_POSITIVE | 0 |

### SOFTWARE_HOUSE (22 unique companies, 45 lines)
| Verdict | Count |
|---------|-------|
| OK | 21 |
| BORDERLINE | 1 |
| FALSE_POSITIVE | 0 |

### TECH_STARTUP (42 unique companies, 93 lines)
| Verdict | Count |
|---------|-------|
| OK | 35 |
| BORDERLINE | 5 |
| FALSE_POSITIVE | 2 |

---

## Grand Total: 71 unique companies, 150 lines
- **OK: 63**
- **BORDERLINE: 6**
- **FALSE_POSITIVE: 2**

---

## Issues Only

### FALSE_POSITIVE

1. **fikra.ventures | Fikra Ventures | TECH_STARTUP**
   - This is a VC/venture builder, not an operating tech company. "We build the winners. We create category-defining AI companies." They originate ideas, co-build with founders, and plug in capital. This is an investment/VC firm, not a tech startup that would hire freelancers.

2. **chainporthub.com | Chainport | TECH_STARTUP**
   - Crypto asset visibility and organization platform. "Not a wallet. Not an exchange." but functionally a crypto portfolio tracker/withdrawal tool. Borderline crypto exchange territory -- built specifically to "get [crypto] out when you need to." Falls under the crypto exchange/tool exclusion.

### BORDERLINE

1. **eziline.com | Eziline Software House Pvt Ltd | SOFTWARE_HOUSE**
   - Website title says "Best Software House" but the domain is .com, company is "Pvt Ltd" (Pakistan/India entity type), and no UAE address is visible on the page. Reasoning says "likely based in the UAE" with no concrete evidence. Probably a Pakistan-based software house.

2. **aptaecho.com | AptaEcho | TECH_STARTUP**
   - No UAE location mentioned in the website text or reasoning. Reasoning explicitly says "The website does not explicitly mention a UAE location." Generic AI company with no geographic anchor.

3. **getonex.ai | OneX | TECH_STARTUP**
   - Reasoning explicitly states: "does not mention a specific UAE address" and "it does not explicitly state its location." AI observability platform with no confirmed UAE presence.

4. **prismxai.com | PrismX | TECH_STARTUP**
   - Reasoning explicitly says: "does not explicitly mention a UAE location." Digital transformation platform with no geographic confirmation.

5. **collabute.com | Collabute | TECH_STARTUP**
   - No UAE address or location mentioned in website text. "Download for Mac" product -- appears to be a SaaS tool with no confirmed UAE base. No .ae domain, no +971 phone, no UAE address visible.

6. **comera financialholding.com | Comera Financial Holding | TECH_STARTUP**
   - Described as "a premier financial holding company." While it does have tech products (VoIP app, payment platform), the parent entity is a financial holding company (RSC LTD in Abu Dhabi). Borderline between a holding/investment entity and an operating tech company.

---

## Notes

- Heavy duplication in the input: most companies appear 2-3x with near-identical reasoning. Deduped to unique domains for review.
- All ECOMMERCE_COMPANY entries are clean UAE-based companies (drawdeck.com in Dubai, farfill.com UAE hub, shopnaseem.com UAE, thewallpaperkids.com Dubai).
- All GAME_STUDIO entries are clean (rumbling-games.com UAE, thejinnstudios.com UAE AAA studio, yallaplay.com UAE mobile gaming).
- SOFTWARE_HOUSE segment is very clean -- nearly all have .ae domains or explicit UAE addresses (Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah). Only eziline.com lacks UAE evidence.
- TECH_STARTUP has the most issues due to a few entries lacking any UAE location evidence and Fikra Ventures being a VC firm.
- Dubatech (dubatech.ae) appears once as SOFTWARE_HOUSE (line 23) and once as TECH_STARTUP (line 93) -- duplicate company across segments. Both are OK but should be deduped to one segment (SOFTWARE_HOUSE is more accurate for an ERP/web dev shop).
- Mirchandani Technologies (mirchandani.ae) appears as both SOFTWARE_HOUSE (line 37) and TECH_STARTUP (lines 117-118) -- same issue, should pick one segment.
