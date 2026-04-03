# Final Review — Batch 2 (targets_batch_ab)

**Date**: 2026-03-21
**Total lines**: 100
**Deduplicated companies**: 78 (22 lines are duplicates of the same domain with slightly different reasoning)

## Summary

| Metric | Count |
|--------|-------|
| Total unique companies reviewed | 78 |
| OK | 55 |
| FALSE_POSITIVE | 23 |

## Duplicate entries (same domain appears twice)

These 11 domains appear twice — count them once each:
anewgames.com, astridentertainment.com, braveturtles.com, gamebreaking.com, openoceangames.com, orangecomet.com, soulmission.io, soundromeda.com, techupware.com, zeptta.com, e-comfashion.com

## FALSE POSITIVES (23)

### Wrong Location (not UAE/MENA — appears to be US/unspecified)

| # | Domain | Name | Segment | Reason |
|---|--------|------|---------|--------|
| 1 | e-comfashion.com | E-Com Fashion | DIGITAL_AGENCY | Based in **New York, NY** — not UAE. Also described as "consulting services", likely solo/micro operation. |
| 2 | triluxe.com | Triluxe | DIGITAL_AGENCY | Based in **New York, NY** — not UAE. Minimal website ("top of page / bottom of page"), unclear if real agency or placeholder. |
| 3 | axonuscorp.com | Axon US Corporation | ECOMMERCE_COMPANY | Based in **New York City, NY** — not UAE. Name literally has "US" in it. |
| 4 | fullsteam.la | Fullsteam | ECOMMERCE_COMPANY | Based in **Los Angeles, CA** — not UAE. Private label apparel agency. |
| 5 | sirahthelabel.com | Sirah The Label | ECOMMERCE_COMPANY | Based in **New York City** — not UAE. Small DTC fashion brand selling dresses/jumpsuits, unlikely to hire international freelancers. |
| 6 | openoceangames.com | Open Ocean Games | GAME_STUDIO | Based in **United States** — not UAE. Co-dev studio. |
| 7 | orangecomet.com | Orange Comet, Inc. | GAME_STUDIO | Based in **Burbank, CA** — not UAE. |
| 8 | silverjaystudio.com | Silverjay Studio | GAME_STUDIO | Based in **New York/Hangzhou, China** — not UAE. Indie studio with angel funding from ZhenFund, Chinese-language site. |

### Solo Consultant / Too Small

| # | Domain | Name | Segment | Reason |
|---|--------|------|---------|--------|
| 9 | kris.life | KH Game Design | GAME_STUDIO | **Solo freelancer** — website literally says "I'm a Freelance Game Designer". Not a company. |
| 10 | soundromeda.com | Soundromeda | GAME_STUDIO | Single game in development, no team visible, no indication of company structure or freelancer hiring. |
| 11 | techupware.com | TechUpWare | GAME_STUDIO | Extremely small — one released game ("Seep Guru"), "More Coming Soon", no visible team. |
| 12 | soulmission.io | SOUL MISSION | GAME_STUDIO | Self-describes as "a small animation team you can outsource" — they ARE the freelancers, not a company that hires them. |
| 13 | salvo.gg | SALVO.gg | GAME_STUDIO | Single social sports game in beta, no visible team or company structure. |
| 14 | playstorygames.com | Story Games Inc | GAME_STUDIO | Single AI-driven RPG in development, unspecified location, no visible team size. |

### Wrong Segment

| # | Domain | Name | Segment | Reason |
|---|--------|------|---------|--------|
| 15 | abrandagency.com | Ambassador Brand Agency | ECOMMERCE_COMPANY | This is a **brand/merch agency** (product design, fulfillment, touring/pop-ups). Not an ecommerce company — should be CREATIVE_AGENCY or removed. Location also unspecified. |
| 16 | appush.com | Appush (NASDAQ: FORTY) | GAME_STUDIO | **Ad-tech platform** (game advertising network), not a game studio. They serve game developers, they don't make games. |
| 17 | graffitigames.com | Graffiti Games | GAME_STUDIO | **Game publisher/distributor**, not a studio. They fund and distribute indie games. Different business model — less likely to hire freelancers directly for game dev. |
| 18 | zeptta.com | Zeptta | GAME_STUDIO | **Game-tech consulting firm** — cloud infrastructure for game publishers. Tagline: "Game-Tech without the Games". They're IT consultants, not a game studio. |
| 19 | uncharted.gg | Uncharted | GAME_STUDIO | **Crypto/GameFi platform** — builds blockchain gambling/casual games. "Crypto's Gamification Layer." More DeFi than game studio. |

### Not a Real Freelancer-Hiring Company

| # | Domain | Name | Segment | Reason |
|---|--------|------|---------|--------|
| 20 | commercelabs.co | CommerceLabs | ECOMMERCE_COMPANY | AI-powered brand operator doing $45M+ in sales. Unspecified location. Likely runs lean with internal team + AI, not a typical freelancer hirer. Also no UAE connection. |
| 21 | thewallpaperkids.com | The Wallpaper Kids | ECOMMERCE_COMPANY | Niche single-product **ecommerce shop** (kids wallpapers in Dubai). Very small retail operation — unlikely to need international freelancer payment infrastructure. |
| 22 | amihan.gg | Amihan Entertainment | GAME_STUDIO | Unspecified location (likely Philippines based on name "Amihan"). Single game "Farm Frens" — unclear company size. |
| 23 | lunacystudios.com | Lunacy Studios | GAME_STUDIO | "Globally distributed" narrative game studio — no UAE presence indicated. Unspecified primary location. |

## Notes

- The DIGITAL_AGENCY segment (lines 1-59) is very clean — nearly all are legitimate Dubai/UAE digital agencies. Only 2 false positives (e-comfashion.com and triluxe.com are NY-based).
- The ECOMMERCE_COMPANY segment (lines 60-66) is weak — most entries are either US-based or mis-segmented.
- The GAME_STUDIO segment (lines 67-96) has the most issues: many duplicates, many with unspecified/US locations, several solo operators, and several mis-segmented (ad-tech, publishers, consulting).
- The IT_SERVICES segment (lines 97-99, only 3 visible) looks clean — all UAE-based.
- **Recommendation**: Re-run game studio and ecommerce gathering with stricter location filtering (UAE/MENA only) and minimum team size requirements.
