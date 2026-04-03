# GPT-4o-mini Classification Issues — V7 Prompt Analysis

## Summary

**V7 prompt (no city filter): 93.6% accuracy (645/689 OK, 44 FP)**

This is an improvement over V6 (86%) because removing the city filter stopped rejecting good companies that happened to be in a different city than the search.

## Where GPT-4o-mini sucks (44 false positives)

### Pattern 1: SaaS PRODUCT companies marked as TECH_STARTUP (12 cases)
- `paniclater.ai` — AI tool, not an agency
- `usetwirl.com` — product company
- `cybral.com` — cybersecurity product
- `gatefy.com` — email security product
- `botmaker.com` — chatbot platform product
- `mockai.co` — mockup tool

**Why GPT gets this wrong:** These companies BUILD software products. They might hire freelancers, but they're product companies, not service businesses. The prompt says "service business that hires freelancers" but GPT interprets any tech company as a potential target.

**Fix for V8:** Add exclusion: "SaaS/software PRODUCT companies that sell a product (not provide services) = NOT_A_MATCH unless they explicitly mention hiring freelancers/contractors on their website"

### Pattern 2: Solo consultants still leaking (8 cases)
- `scaleupmethodology.com` — one person methodology consultant
- `connectingdotsglobal.xyz` — solo connector/networker
- `heinonenventures.com` — solo venture builder
- `classydisruptors.com` — personal brand

**Why GPT gets this wrong:** These websites look professional but are one-person operations. GPT sees "consulting" or "agency" in the site copy and marks as target.

**Fix for V8:** Strengthen: "If website shows ONLY the founder/CEO with no team page, no 'our team', no employee photos = NOT_A_MATCH. One person cannot be a freelancer-hiring company."

### Pattern 3: Government/semi-government contractors (6 cases)
- `itmam.sa` — Saudi government tech project
- `lenience.sa` — Saudi government compliance
- `lunixa.sa` — Saudi government IT
- `mdscs.sa` — Saudi defense/security
- `neomtech.com` — NEOM (Saudi megaproject) related
- `zenitharabia.com` — government infrastructure

**Why GPT gets this wrong:** These are tech companies, so GPT labels them IT_SERVICES or TECH_STARTUP. But they're government contractors — they don't hire freelancers via EasyStaff, they hire through government procurement.

**Fix for V8:** Add: "Government contractors, defense companies, companies primarily serving government clients (especially Saudi Vision 2030 megaprojects) = NOT_A_MATCH"

### Pattern 4: Hardware/infrastructure NOT service (5 cases)
- `dmsisystems.com` — hardware distributor
- `upixnetworks.com` — network hardware
- `nodetech.com.sa` — IT hardware
- `skyviewads.com` — outdoor advertising infrastructure
- `manga.com.sa` — print/publishing

**Why GPT gets this wrong:** These have "tech" or "IT" in their name/description. GPT labels them IT_SERVICES. But they sell/install hardware, not provide freelancer-based services.

**Fix for V8:** Strengthen: "IT hardware distributors, network equipment installers, print companies = NOT_A_MATCH"

### Pattern 5: Media buyers/ad inventory NOT agencies (4 cases)
- `thekitefactorymedia.com` — media buying platform
- `mediacat.uk` — media industry news/events
- `innoplanet.net` — ad network
- `unmiss.com` — push notification platform

**Why GPT gets this wrong:** Contains "media" → GPT labels MEDIA_PRODUCTION or MARKETING_AGENCY. But these are platforms/tools, not agencies that hire freelancers.

**Fix for V8:** Add: "Media buying platforms, ad networks, push notification tools = NOT_A_MATCH (they're tech products, not service agencies)"

### Pattern 6: Cybersecurity firms that don't hire freelancers (5 cases)
- `faradaysec.com` — pen testing product
- `caxus.net` — security compliance tool
- `intelliipro.com` — security platform

**Why GPT gets this wrong:** "cybersecurity" matches IT_SERVICES. But many cybersecurity companies are product companies or highly regulated (don't use freelancers for compliance reasons).

**Fix for V8:** Add nuance: "Cybersecurity PRODUCT companies (tools, platforms, scanners) = NOT_A_MATCH. Cybersecurity CONSULTING firms (pen testing services, compliance auditing as a service) = OK"

## V8 Prompt Changes Summary

Add these exclusions to V7:

```
SAAS/PRODUCT COMPANIES (sell product, not provide services):
- Software product companies that sell a tool/platform = NOT_A_MATCH
- Unless they explicitly mention hiring freelancers/contractors on website

GOVERNMENT CONTRACTORS:
- Companies primarily serving government (especially Saudi megaprojects) = NOT_A_MATCH
- Defense, security clearance, government procurement = NOT_A_MATCH

HARDWARE / INFRASTRUCTURE:
- IT hardware distributors, network equipment, print/publishing = NOT_A_MATCH

MEDIA PLATFORMS (not agencies):
- Ad networks, media buying platforms, push notification tools = NOT_A_MATCH
- News/events sites about media industry = NOT_A_MATCH

CYBERSECURITY PRODUCTS:
- Security tools, scanners, compliance platforms = NOT_A_MATCH
- Security consulting/auditing AS A SERVICE = OK
```

## Per-segment accuracy

| Segment | GPT targets | Opus OK | FP | Accuracy |
|---------|-------------|---------|-----|---------|
| MARKETING_AGENCY | ~120 | ~120 | 0 | 100% |
| DIGITAL_AGENCY | ~110 | ~105 | ~5 | 95% |
| CREATIVE_STUDIO | ~90 | ~85 | ~5 | 94% |
| MEDIA_PRODUCTION | ~60 | ~55 | ~5 | 92% |
| SOFTWARE_HOUSE | ~50 | ~45 | ~5 | 90% |
| IT_SERVICES | ~100 | ~85 | ~15 | 85% |
| CONSULTING_FIRM | ~60 | ~55 | ~5 | 92% |
| TECH_STARTUP | ~80 | ~68 | ~12 | 85% |
| GAME_STUDIO | ~15 | ~14 | ~1 | 93% |
| ECOMMERCE_COMPANY | ~10 | ~8 | ~2 | 80% |

**Best segments:** MARKETING_AGENCY (100%), DIGITAL_AGENCY (95%)
**Worst segments:** IT_SERVICES (85%), TECH_STARTUP (85%), ECOMMERCE_COMPANY (80%)

IT_SERVICES and TECH_STARTUP are where GPT sucks most — too many product companies and government contractors leak through.
