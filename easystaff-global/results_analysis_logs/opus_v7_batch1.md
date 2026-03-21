# Opus v7 Batch 1 — GPT-4o-mini Target Review

**Date**: 2026-03-21
**Reviewer**: Claude Opus 4.6
**File**: /tmp/opus_review_aa (172 companies)

## Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 172 |
| OK | 155 |
| FALSE POSITIVE | 17 |
| FP rate | 9.9% |

## False Positives

### CONSULTING_FIRM segment

1. **agency-adventure.com** (The Agency Adventure) — This is a coaching/advisory business for agency founders, not an agency itself. One person (coach) advising other agency owners. They don't hire freelancers — they ARE the freelancer. Solo advisory, not a service business that needs to pay contractors internationally.

2. **classydisruptors.com** (Classy Disruptors) — Solo consultant (Alice McLaughlin). Personal brand website listing her background as brand manager, art collector, TV journalist. No indication of a team or hiring contractors. One-woman advisory practice.

3. **scaleupmethodology.com** (Scaleup Methodology) — This is a methodology/framework/course for startups, not a consulting firm that hires people. Sells a "Scaleup Masterclass" and "Scaleup Scorecard." Content/education product, not a service business with contractor needs.

4. **connectingdotsglobal.xyz** (.xyz TLD) — Extremely thin website with vague "professional advice" copy. No team, no portfolio, no clients listed. Looks like a placeholder or very early-stage one-person operation. Too small/unverified to be a real target.

5. **itmam.sa** (Itmam Consultancy) — Arabic-language Saudi consulting firm focused on government sector (Vision 2030 alignment, compliance evaluation, capacity building). Likely operates entirely with local Saudi staff due to government contract requirements. Low probability of international freelancer payments.

### CREATIVE_STUDIO segment

6. **paniclater.ai** (Panic Later) — Primarily a music label / music video production company ("Panic Later Music's music video"). Won an animation award for a music video. This is a music/entertainment company, not a creative studio that would hire international freelancers for client work.

7. **mawi.co** (MAWI) — This is a personal portfolio site for a single designer (sports branding — Nike, athletes). Lists individual athlete clients. Solo designer/freelancer, not a studio that hires other freelancers.

8. **upstage-studio.com** (upstage studio) — Extremely minimal website: just "We make it neat" + a Riyadh address. No team, no portfolio details, no clients. Too thin to validate as a real operating business.

### DIGITAL_AGENCY segment

9. **comparethecarrier.com** (CTC Stack) — This is a logistics tech platform / marketplace for carriers, not a digital agency. "Compare The Carrier" is a product (carrier comparison tool). They sell logistics SaaS, not agency services. The marketing services listed are secondary to their platform product.

10. **digitalagencyreseller.com** (Digital Agency Reseller) — White-label reseller platform. They sell pre-packaged SEO/marketing services for agencies to resell. This is a product/platform business, not a service agency that hires freelancers. Their model is the opposite — agencies buy FROM them.

11. **ladylingua.org** (LadyLingua Ltd) — Desktop publishing and typesetting service on a .org domain. While technically a service business, DTP/typesetting is extremely niche and low-margin. Very unlikely to be paying international freelancers through a platform like EasyStaff — this is a small specialist operation.

12. **codlinker.com** (Codlinker) — Very template-heavy website targeting "Florida small businesses" with local SEO. Generic agency template with stock descriptions. Appears to be a very small local operation or even a lead-gen site rather than an actual agency with international contractor needs.

13. **cyprawebdigital.com** (CypraWeb Digital) — Just a one-line title "Best Professional Web Development | Digital Marketing Agency" with no actual content visible. Too thin to validate. Could be a placeholder domain.

14. **innovatemarketers.com** (Innovate Marketers) — Generic "Best Digital Marketing Agency in USA" with template copy. Mentions "Online Reputation Management" and "sentiment analysis" in boilerplate language. Looks like a template/lead-gen site rather than an operating agency.

15. **247digitalmarketingagency.com** (247 Digital Marketing Agency) — WordPress template site ("My WordPress Blog" in subtitle). Generic service list copied from templates. No portfolio, no team, no real clients. Not a real operating agency.

16. **daksil.com** (Daksil) — Turkish-language software company website. While it could be a real digital agency, EasyStaff Global targets English/Arabic-speaking markets. A Turkish domestic agency is unlikely to need international freelancer payments through EasyStaff.

17. **graphictank.co.uk** (Graphictank Ltd) — Solo freelancer operation. Website credits "Dan" as the single person. "Working with Dan" in testimonial. This is a one-person freelancer, not a business that hires other freelancers.

## Notes

- The CONSULTING_FIRM and CREATIVE_STUDIO segments were generally well-classified. Most are legitimate service businesses with teams.
- The DIGITAL_AGENCY segment had the most false positives (9 out of 17), mostly from template/placeholder websites and solo operations that GPT couldn't distinguish from real agencies.
- Several Saudi (.sa) agencies are borderline — they likely have local teams, but Saudi Arabia's Vision 2030 is driving international hiring, so they remain OK.
- UK agencies (.co.uk) are strong targets — high likelihood of international freelancer use.
- The batch is heavy on DIGITAL_AGENCY (105 of 172). Segment labels are generally correct.
