# Final Review — targets_batch_aa

**Date**: 2026-03-21
**Total lines**: 100
**Duplicate domains** (same domain appears 2x with different reasoning): 5 (aaagrowth.net, carion.group, 11000ad.com, lumacreativeagency.com, merchnain.com)
**Unique companies**: 95

---

## Summary

| Metric | Count |
|--------|-------|
| Total unique companies reviewed | 95 |
| OK | 78 |
| FALSE POSITIVE | 17 |

---

## FALSE POSITIVES

| # | Domain | Name | Segment | Reason for Rejection |
|---|--------|------|---------|---------------------|
| 1 | aaagrowth.net | AAA Growth Agency | CONSULTING_FIRM | **Solo consultant** — website quotes a single person (Shawna) leading projects. No team page, no employee count. Appears to be a one-person growth consultancy, not a company that hires freelancers. |
| 2 | 11000ad.com | 11000AD | CREATIVE_STUDIO | **Location unknown** — no UAE, NYC, or LA address visible anywhere on the site. Reasoning says "unspecified location." Does not meet location criteria. |
| 3 | dejustified.com | The Justified | CONSULTING_FIRM | **Wrong segment** — this is a creative/entertainment agency (branded visuals for entertainers, Grammy winners, LA-based). Should be CREATIVE_STUDIO, not CONSULTING_FIRM. Also, reasoning is just "location + what they do" — lazy analysis. |
| 4 | fanofafan.co | Fan of a Fan LLC | CREATIVE_STUDIO | **Location unknown** — no address listed. Reasoning says "unspecified location." Also more of a merchandise/e-commerce company than a creative studio that hires freelancers. |
| 5 | h3m.studio | H3M | CREATIVE_STUDIO | **Location unknown** — reasoning says "unspecified location." Website is essentially a loading screen with no substantive content. Cannot verify this is a real operating company. |
| 6 | holdmedia.ae | Hold Media Agency | CREATIVE_STUDIO | **Solo operator** — website explicitly says "Hey, I'm Hold" and describes a single designer/filmmaker. Not a company that would need freelancer payment infrastructure. |
| 7 | gaga-photography.com | Gaga Photography Studio | CREATIVE_STUDIO | **Not a freelancer hirer** — this is a photography studio offering consumer services (maternity shoots, cake smash, flying dress). B2C business, not a company that hires/pays freelancers internationally. |
| 8 | pixelcraftstudio.ae | Pixel Craft Digital Studio | CREATIVE_STUDIO | **Not a freelancer hirer** — consumer photography studio in Dubai Silicon Oasis (family portraits, corporate headshots). Small B2C operation, unlikely to need international freelancer payments. |
| 9 | royaldigitaldxb.com | Royal Digital Studio & Stores LLC | CREATIVE_STUDIO | **Not a freelancer hirer** — consumer photography studio ("Experience the Art of Photography"). B2C service, not a company managing remote freelancer teams. |
| 10 | bidllc.ae | BIDllc | CREATIVE_STUDIO | **Niche physical production** — architectural model making and 3D animation. Very specialized physical craft, unlikely to hire international freelancers for payment through a platform. |
| 11 | sanatinteriordesign.com | Sanat Interior Design | CREATIVE_STUDIO | **Wrong segment** — this is an interior design firm, not a creative studio/agency. Interior design firms typically use local contractors, not international freelancers paid through platforms. |
| 12 | modesignuae.com | Modesign FZ LLC | CREATIVE_STUDIO | **Solo operator** — website text references "Monica" as a single person ("It is a great pleasure to work with Monica"). FZ LLC with a single designer, not a team hiring freelancers. |
| 13 | thethirdeye.ae | Third Eye Creative Studio | CREATIVE_STUDIO | **Minimal web presence** — website is essentially a landing page with service names and a "Book Now" button. No portfolio, no team, no clients listed. Cannot verify this is a real operating company of any scale. |
| 14 | scalableae.com | Scalable | CONSULTING_FIRM | **Wrong segment / not a freelancer hirer** — this is an event management + consulting company founded in 2020. Google Sites page with minimal content. Event management companies rarely hire international freelancers through payment platforms. |
| 15 | brickelldigital.com | Brickell Digital, Inc. | CREATIVE_STUDIO | **Wrong location** — based in Miami, FL (with offices in NYC and SF). While NYC is listed, the primary HQ is Miami. Borderline — could be OK if NYC office is real, but the company markets itself as Miami-based. |
| 16 | sugarhill.consulting | Sugar Hill Consulting LLC | CONSULTING_FIRM | **Location unknown** — reasoning says "based in the United States" but no specific city. Does not confirm UAE, NYC, or LA. Generic IT consulting, could be anywhere in the US. |
| 17 | atbc.co | ATBC | CONSULTING_FIRM | **Wrong location** — primary office is in Calicut, Kerala, India. Dubai appears to be a secondary/satellite presence. Website title: "Strategy Consultants in Calicut, Kerala & Middle East." India-HQ'd firm unlikely to need EasyStaff for freelancer payments. |

---

## DUPLICATE ENTRIES (same domain, 2 rows)

These 5 domains appear twice in the file. The second entry has lazy reasoning ("location + what they do"). Dedup needed before push:

- aaagrowth.net (lines 1-2) — already flagged as FALSE POSITIVE
- carion.group (lines 8-9)
- 11000ad.com (lines 29-30) — already flagged as FALSE POSITIVE
- lumacreativeagency.com (lines 58-59)
- merchnain.com (lines 62-63)

---

## NOTES

- **Segment labels are generally correct** for the OK companies. CONSULTING_FIRM, CREATIVE_STUDIO, and DIGITAL_AGENCY are well-applied.
- **UAE location dominance**: ~80% of companies are UAE-based (.ae domains), which checks out.
- **NYC/LA companies are sparse**: only ~5 companies (carion.group, lumacreativeagency.com, merchnain.com, brickelldigital.com, dejustified.com). Location verification is weaker for US-based entries.
- **Photography studios** are a recurring false positive pattern — consumer photo studios (weddings, maternity, cake smash) are not the same as creative agencies that hire freelancer teams.
