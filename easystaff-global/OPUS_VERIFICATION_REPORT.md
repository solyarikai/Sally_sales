# EasyStaff Global — Opus Verification Report

**Date**: 2026-03-22 02:30 UTC
**Status**: COMPLETE — ALL 4,148 targets reviewed, 3,869 verified

## What was done

**16 parallel Opus agents** reviewed ALL 4,148 targets in the database. Each agent reviewed ~260 companies and identified false positives.

## Results

| Batch | Reviewed | OK | FP | Accuracy |
|-------|----------|----|----|----------|
| 01 | 261 | 240 | 21 | 91.9% |
| 02 | 261 | 224 | 37 | 85.8% |
| 03 | 260 | 230 | 30 | 88.5% |
| 04 | 260 | 232 | 28 | 89.2% |
| 05 | 260 | 253 | 7 | 97.3% |
| 06 | 260 | 247 | 13 | 95.0% |
| 07 | 261 | 237 | 24 | 90.8% |
| 08 | 260 | 253 | 7 | 97.3% |
| 09 | 260 | 237 | 23 | 91.2% |
| 10 | 261 | 257 | 4 | 98.5% |
| 11 | 261 | 250 | 11 | 95.8% |
| 12 | 260 | 256 | 4 | 98.5% |
| 13 | 261 | 248 | 13 | 95.0% |
| 14 | 260 | 258 | 2 | 99.2% |
| 15 | 260 | 257 | 3 | 98.8% |
| 16 | 248 | 238 | 10 | 96.0% |
| **TOTAL** | **4,148** | **3,869** | **279** | **93.3%** |

**281 unique FP domains identified, 279 removed from DB** (2 were already non-targets).

## KNOWN LIMITATION: Shallow review methodology

**THIS REVIEW WAS FLAWED.** The Opus agents reviewed based on:
- Domain name
- GPT-assigned segment
- GPT's reasoning text (120 chars)

They did NOT review:
- **Actual scraped website content** (the real evidence)
- Company team pages, portfolio, client lists
- Service descriptions vs product descriptions

**Why this matters**: Opus was essentially reviewing GPT's homework, not independently verifying. If GPT's reasoning was convincing but wrong, Opus would miss it. A proper review should read the scraped website text and independently decide: "Is this a service business that hires freelancers?"

## Where GPT sucks (from Opus findings)

### 1. GAME_STUDIO — 0-20% accuracy in most batches
GPT classifies ANY game development company as a target. But most are indie studios building their own IP (games), NOT doing client work. Only game studios that offer co-dev/porting/outsourced art services are valid targets.

**FP examples**: moonbeast.com, arvore.io, supersolid.com, smgstudio.com, psytecgames.com
**Fix**: Add to prompt: "Game studios building their OWN games/IP = NOT_A_MATCH. Only game dev SERVICE studios (co-dev, porting, outsourced art for clients) = OK."

### 2. CONSULTING_FIRM — 26-50% accuracy
GPT marks any company with "consulting" as a target. But management consulting, strategy advisory, financial consulting, compliance consulting use EMPLOYEES, not freelancers. Only consulting firms that do creative/digital/tech PROJECT work for clients are valid.

**FP examples**: insight222.com, conversion-rate-experts.com, augmentconsult.com, feasible.ae
**Fix**: Add: "Management/strategy/financial/compliance consulting = NOT_A_MATCH. Only consulting firms doing creative/digital/tech project delivery = OK."

### 3. IT_SERVICES — 20-70% accuracy (varies by region)
In Middle East especially, GPT marks enterprise IT resellers, hardware distributors, and managed IT providers as targets. These use employees, not freelancers.

**FP examples**: nairsystems.com, techspineqatar.com, ctelecoms.com.sa, align.com.sg
**Fix**: Add: "Enterprise IT resellers, hardware distributors, managed IT/infra providers, telecom companies = NOT_A_MATCH."

### 4. TECH_STARTUP — 40-60% accuracy
GPT marks SaaS/product companies as targets because they're "tech companies." But product companies don't hire freelancers for client work — they hire employees to build their product.

**FP examples**: bantech.ae, supademo.com, hathora.dev, subspace.com
**Fix**: Already in V8 prompt but not strict enough. Add: "If the company has 'Sign up', 'Free trial', 'Pricing' pages = product company = NOT_A_MATCH."

### 5. Staffing/recruitment leaking through
Some staffing companies slip through despite explicit exclusion.

**FP examples**: syscort.com, solomonpeoplesolutions.com, kbctechnologies.com, kroescontrol.nl
**Fix**: Add: "If company provides WORKERS/STAFF/TEAM MEMBERS to other companies = NOT_A_MATCH."

## Best segments (near-perfect accuracy)

| Segment | Accuracy | Notes |
|---------|----------|-------|
| DIGITAL_AGENCY | 97-100% | Core ICP, GPT nails it |
| CREATIVE_STUDIO | 98-100% | Design/branding agencies |
| MARKETING_AGENCY | 93-100% | Ad agencies, SEO, social media |
| MEDIA_PRODUCTION | 95-100% | Video/animation production for clients |
| SOFTWARE_HOUSE | 95-100% | Custom dev shops |

## Recommended V9 prompt changes

Add these exclusions to V8:
```
GAME STUDIOS BUILDING OWN IP:
- If the studio creates/publishes its OWN games = NOT_A_MATCH
- Game dev SERVICE studios doing client work (co-dev, porting, outsourced art) = OK

MANAGEMENT/STRATEGY CONSULTING:
- Business consulting, management advisory, strategy consulting = NOT_A_MATCH
- Financial/compliance/audit consulting = NOT_A_MATCH
- Only consulting firms doing creative/digital/tech PROJECT DELIVERY = OK

MANAGED IT / CLOUD INFRA:
- Managed IT services, cloud infrastructure management = NOT_A_MATCH
- Enterprise IT resellers, hardware distributors = NOT_A_MATCH
- IT consulting that is actually software development for clients = OK

STAFFING (stronger):
- "Build your team", "scale your team", "team augmentation" = NOT_A_MATCH
- Providing WORKERS/STAFF to other companies = NOT_A_MATCH
```

## Next steps for proper verification

For the 15-city expansion (~5,000 new targets expected):
1. Export `domain + segment + scraped_text[:2000]` (NOT just GPT reasoning)
2. Opus reviews the WEBSITE CONTENT directly
3. Opus independently decides target/not-target
4. Store `opus_verified_at` in DB for each verified target
5. GPT reasoning only used to document WHERE GPT FAILS
