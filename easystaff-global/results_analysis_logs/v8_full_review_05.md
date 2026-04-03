# V8 AE Batch Review — Full Manual Review

**Date**: 2026-03-22
**File**: `/tmp/v8_review_ae`
**Total entries**: 278

## Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 278 |
| OK (real service business) | 261 |
| False positives | 17 |
| FP rate | 6.1% |

### Breakdown by segment

| Segment | Total | OK | FP |
|---------|-------|----|----|
| DIGITAL_AGENCY | 61 | 60 | 1 |
| ECOMMERCE_COMPANY | 11 | 10 | 1 |
| EVENT_PRODUCTION | 1 | 1 | 0 |
| EVENTS_AGENCY | 1 | 1 | 0 |
| EVENTS_AND_DESIGN_AGENCY | 1 | 1 | 0 |
| GAME_STUDIO | 70 | 65 | 5 |
| IT_SERVICES | 133 | 123 | 10 |

---

## False Positives (16)

### DIGITAL_AGENCY (1 FP)

1. **xy.com.sa** | XY Marketing Labs — "Digital Marketing Agency Template Kit". This is a website template/kit, not an actual operating agency.

### ECOMMERCE_COMPANY (1 FP)

2. **themescamp.com** | ThemesCamp — Sells pre-built WordPress themes. Product company, not a service business that hires freelancers.

### GAME_STUDIO (5 FP)

3. **gamecookies.news** | Game Cookies — Gaming news blog/media site. Not a game studio, does not develop games.

4. **metica.com** | Metica — SaaS platform for game monetization and UA funding. Product company, not a studio that hires freelancers for development.

5. **iskra.world** | Iskra — Web3/blockchain game publishing platform with token-based reward system ("ActFi"). Platform/crypto project, not a traditional game studio.

6. **doodad.games** | Doodad Games — Solo developer (Bilal Akil) who "has hung up his indie hat". Explicitly states single person, no longer active.

7. **maintainaltitude.com** | Maintain Altitude — Single mobile game ("Loop Drop: A DJ game for mobile"). No team indicators, likely solo developer.

### IT_SERVICES (9 FP)

8. **autotask.ai** | AutoTask — RPA and data acquisition software product. SaaS platform, not a consulting/services business.

9. **brinqa.com** | Brinqa — AI-powered vulnerability and exposure management platform. SaaS product company.

10. **caxus.net** | CAXUS — Cybersecurity product ("QuantumShield"). Sells a product/framework, not consulting services.

11. **cmdzero.io** | Command Zero — AI-assisted cyber investigation platform. SaaS product.

12. **cybral.com** | Cybral — Data Security Posture Management product with "patented AI". SaaS product company with global R&D centers.

13. **eitechone.com** | Eagle Eye Tech One — Website filled with "Lorem ipsum" placeholder text. Template/demo site, not a real operating business.

14. **elite.cloud** | ELITE CLOUD — Automated cloud cost analysis tool/platform. SaaS product ("Free Cloud Check", automated reports).

15. **ensembleai.io** | Ensemble AI — AI-powered business automation platform ("Ensemble Cortex"). SaaS product company.

16. **faradaysec.com** | Faraday — All-in-one security platform for vulnerability management and attack simulations. SaaS product company.

17. **gatefy.com** | Gatefy — Email security SaaS product. Sells an email protection platform, not a services business.

---

### Notes

- DIGITAL_AGENCY segment is very clean (1.6% FP). Nearly all are legitimate multi-person agencies.
- GAME_STUDIO has a few non-studios (news site, SaaS tools, solo devs) but most are legitimate studios with teams.
- IT_SERVICES has the most FPs (7.5%), mainly SaaS product companies misclassified as service businesses. The distinction: if the website sells a platform/tool rather than offering consulting/implementation/staff, it is a product company.
- Two borderline calls kept as OK: headonarock.com (very small indie but has a studio identity), goldonstudios.com (web3 but builds platforms with teams).
