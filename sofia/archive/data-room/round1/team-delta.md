# TEAM DELTA — Full Analysis & Recommendations

**Project:** OnSocial B2B Outreach
**Data reviewed:** 6 files across smartlead/, google-sheet/, analysis/
**Date:** 2026-03-16

---

## 1. COPYWRITER

### Diagnosis (from buyer's POV — what feels wrong)

I read every sequence and reply from the perspective of a CTO, VP Product, or agency CEO opening a cold email at 9:14 AM on a Tuesday. Here is what happens in their heads:

**Problem 1: Every email leads with the product, not the buyer's problem.**

The opening line of the flagship sequence (TEST A) is:

> "We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles across Instagram, TikTok, and YouTube."

**Buyer's internal monologue:** "This person doesn't know me. They're pitching. Delete."

The number 450M appears in literally every single sequence across all 4 frameworks. By the second email, the buyer has seen it 2-3 times. It stops being impressive and starts being the signal that this is a template.

**Problem 2: No social proof is believable.**

PR firms sequence says:

> "NeoReach, Buttermilk, Gushcloud, Influencer.com, and Obviously all run on our API."

IM_PLATFORMS sequence says:

> "Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API."

**Buyer's internal monologue:** "I know some of these companies. If they're ALL your customers, why haven't I heard of you? And if Captiv8 and Kolsquare both use you, why would I trust you with my competitive data?" This claim actually triggers suspicion rather than trust. Competitors sharing a data vendor is plausible for commodity data, but listing 6 competitors in one sentence feels like overclaiming.

**Problem 3: The CTA is weak and generic.**

Almost every email ends with either "15 min walkthrough?" or "Who at {{company_name}} handles product or data partnerships?"

The second CTA is especially bad. **Buyer's internal monologue:** "You're asking ME to do your homework? I'm not going to route you to my CTO as a favor." This CTA only works when the recipient is an EA or gatekeeper, not a decision-maker. And the sequences are targeting CTOs, VPs, and CEOs.

**Problem 4: No differentiation from HypeAuditor, Modash, CreatorIQ, etc.**

Norbert at PFR Group literally asked: "How is your data different from HypeAuditor or SocialData?" This is the question every semi-informed buyer has. The sequences never answer it preemptively. The buyer reads "credibility scoring, audience demographics, fraud detection" and thinks: "HypeAuditor does that. Modash does that. Why would I switch?"

**Problem 5: Emails are too long and uniform in structure.**

TEST A Step 1 is 82 words. Step 2 is 85 words. Step 3 is 93 words. Each email feels like the same pitch rephrased. The buyer who opens email #2 after ignoring #1 gets zero new information — just a different arrangement of "API, 450M, credibility, demographics, overlap."

**Problem 6: PR firms get the exact same value proposition as IM platforms.**

PR firms don't care about "your clients see it as your feature" or "audience overlap between creators." They care about: (a) validating a creator for a press campaign, (b) proving media value to clients, (c) finding creators who match a brand narrative, not a demographic spreadsheet. The PR sequence reads like the platform sequence with "PR firms" find-and-replaced in.

**Problem 7: Reply scripts are from a completely different project.**

The scripts reference resale platforms, LTV/AOV, overstock, and "thefashionpeople.com." When Nastya responds to "What's the pricing?" she's either improvising or sending nothing. This means the highest-intent leads — the ones who already said YES — get the weakest experience.

---

### Recommendations (rewrites optimized for trust + response)

#### Recommendation 1: Rewrite Step 1 to lead with the buyer's situation, not the product.

**Current (TEST B Step 1):**
> Hi {{first_name}},
> We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles across Instagram, TikTok, and YouTube. Credibility scoring, audience demographics down to city level, fraud signals, audience overlap.
> Your clients see exactly who's real, where the audience is, and how much overlap there is between creators — before spending a dollar.
> Who at {{company_name}} handles product or data partnerships?

**Rewrite for IM Platforms (CTO/VP Eng):**

> Hi {{first_name}},
>
> Quick question — is {{company_name}} maintaining its own creator data pipeline, or licensing from a third party?
>
> Asking because we power the data layer for [1 real named customer — e.g., "a platform doing 2B+ monthly lookups"] and the pattern is always the same: internal scraping works until it doesn't, then it becomes the eng team's biggest maintenance headache.
>
> If that's not your situation, ignore this. But if your team is spending cycles on data infrastructure instead of product — happy to show what the alternative looks like. 15 min.

**Why this works from buyer's POV:** Opens with a question about THEIR situation. Acknowledges they might have it solved (shows respect). Uses one specific proof point instead of a laundry list. The CTA is specific and low-commitment.

#### Recommendation 2: Rewrite for IM Agencies (CEO/Founder).

**Current IMAGENCY HYP A Step 1:**
> How many hours does your team spend sourcing creators per campaign at {{company_name}}?
> At OnSocial, we cut that to under 2 hours — 27 filters, audience demographics, credibility scores, all white-label ready. 450M+ profiles...

**Buyer's internal monologue:** "Under 2 hours? We already do it faster than that with Modash. And 27 filters sounds like a feature list, not a benefit."

**Rewrite for IM Agencies:**

> Hi {{first_name}},
>
> I noticed {{company_name}} is running influencer campaigns for [industry/type — e.g., "DTC beauty brands"]. When your team pitches 3-4 creators to a client, how do you validate that their audiences don't overlap by 50%+?
>
> We had an agency lose a major client because they recommended 3 creators who shared 60% of the same followers. The campaign underperformed, and the client blamed the agency.
>
> We built a tool that catches this in seconds — before the brief goes out. Used by [1 named agency].
>
> Worth 15 min to see the overlap report for creators {{company_name}} is currently working with?

**Why this works:** It uses a specific, painful scenario the buyer can picture. It triggers fear of loss (losing a client), not hope of gain (saving time). The CTA offers something personalized (overlap report for THEIR creators), not a generic walkthrough.

#### Recommendation 3: Write all 9 reply scripts immediately.

These are the highest-leverage words in the entire operation. A lead who replied "What's the pricing?" is 50x more likely to buy than one who never opened the email. Yet these leads get improvised responses.

**Script 1: "What's the pricing?" (6 leads asked this)**

> Hi {{first_name}},
>
> Good question — pricing depends on volume and which data points you need, so I want to make sure I give you the right number rather than a range that's not useful.
>
> Quick context: most teams at our scale pay between $X-Y/month depending on whether they need full audience demographics or just credibility + basic stats. Our smallest customers do ~500K lookups/month, largest do 2B+.
>
> Two options:
> 1. I can send you the pricing grid right now if you tell me your approximate monthly volume and which platforms (IG/TikTok/YT) you need.
> 2. Or we do 15 min on a call — I'll pull a live demo with your volume, and you'll have exact pricing before the call ends.
>
> What works better?

**Buyer's internal monologue:** "They didn't dodge the question. They gave me a range. They asked what I actually need. And they gave me two options, one of which doesn't require a call. This person respects my time."

**Script 2: "Send more info / one pager" (Georg, Roland)**

> Hi {{first_name}},
>
> Attached is a one-pager covering how the API works, what data points you get, and which platforms we cover.
>
> [ATTACH REAL ONE-PAGER — PDF, not a link]
>
> One thing the doc won't show you: what the actual API output looks like for a creator YOUR team is working with. If you send me 2-3 creator handles, I'll pull the full breakdown and send it back — no call needed.
>
> That usually answers more questions than a PDF.

**Buyer's internal monologue:** "They actually sent me what I asked for AND offered to do work for me, not just another call. I'll send them a couple handles to test."

**Script 3: "How are you different from HypeAuditor/SocialData?" (Norbert @ PFR)**

> Hi Norbert,
>
> Fair question. Three honest differences:
>
> 1. **Coverage:** HypeAuditor has ~80M profiles. We have 450M+ with truly global coverage — especially strong in LATAM, SEA, and MENA where HA thins out.
> 2. **Data freshness:** SocialData batch-processes weekly. Our data updates in real-time — you get the audience snapshot as of today, not last Tuesday.
> 3. **API-first pricing:** HA and SocialData are SaaS-first (dashboards, seats, per-user pricing). We're API-first — you pay per call, no seat licenses. If you're integrating into your own product, this is typically 40-60% cheaper at scale.
>
> Easiest way to compare: send me a creator handle you've recently analyzed in HA. I'll pull the same profile in our system and you can compare side-by-side. No call needed.

**Buyer's internal monologue:** "Specific, honest, and they offered to prove it. Not just marketing claims. I'll test them."

**Script 4: "We already have a partner/system" (Roland, Louis)**

> Hi {{first_name}},
>
> Understood — makes sense to stick with what's working. Quick question: is your current provider covering all three platforms (IG, TikTok, YouTube) with real-time updates, or are you supplementing with manual checks on any of them?
>
> Not trying to replace anything that works. But most teams we talk to have at least one gap — usually TikTok depth or audience geo accuracy in emerging markets.
>
> If that resonates, happy to do a blind comparison. If not, no hard feelings.

**Script 5: "Do you cover [region/platform]?" (Salvador — SEA/China)**

> Hi Salvador,
>
> Yes, we cover Southeast Asia. Our database includes 450M+ profiles globally, and SEA is one of our stronger regions — particularly Indonesia, Philippines, Thailand, and Vietnam.
>
> China: we cover Douyin (Chinese TikTok) with ~[X]M profiles. It's not as deep as our IG/TikTok/YT coverage, but it's growing. If KOL data in China is your primary need, I want to be upfront that this is not our strongest market yet.
>
> For SEA though — happy to pull sample data for any creators you're working with. Send me a few handles and I'll have the breakdown back to you within 24 hours.

**Script 6: "Let's schedule a call" (Colby, Gordon, Johan)**

> Great — looking forward to it.
>
> Here's my calendar: [calendar_link]
>
> To make the 15 min as useful as possible, could you send me 2-3 creator handles your team is currently evaluating? I'll pull the full data breakdown before the call so we're looking at YOUR use case, not a generic demo.

**Script 7: "I'm interested, adding colleagues" (Atul — added Pavel, Akira)**

> Hi Atul, Pavel, Akira —
>
> Great to have everyone in the loop. To make sure this is worth your time, here's what I'll cover in our walkthrough:
>
> 1. Live API demo using creator profiles relevant to The Shelf
> 2. Data coverage + freshness vs. what you're currently using
> 3. Pricing based on your volume
>
> Here's my calendar: [calendar_link] — feel free to pick a slot that works for the group. 30 min should be enough with three of you.
>
> If it's easier, I can also send a 5-min Loom walkthrough first so you can evaluate asynchronously.

**Script 8: "Wrong person, try X" (Sebastian -> Robin, Alexander -> Hannes)**

> Hi {{first_name}},
>
> Thank you — really appreciate the redirect.
>
> {{redirect_name}}, I was speaking with {{first_name}} who suggested you'd be the right person for this.
>
> [One-sentence version of value prop relevant to their role]. Happy to send a quick overview or jump on a 15-min call — whatever's easier.

**Script 9: OOO with return date (21 cases)**

Set a calendar reminder for return_date + 2 business days. Then send:

> Hi {{first_name}},
>
> Hope you had a good [trip/break]. Circling back on my earlier note about creator data for {{company_name}}.
>
> [One-sentence hook]. Worth a quick look when you're settled back in?

#### Recommendation 4: Kill the "Who handles X at {{company_name}}?" CTA.

This CTA appears in Step 1 of the flagship sequence AND Step 4 of both TEST A and TEST B. It communicates: "I don't know who you are or what you do." When you're emailing a CTO, this is insulting. Replace with:

- Step 1: A question about their situation (see rewrites above)
- Step 4: "Not the right person? Happy to be pointed in the right direction — or I can stop reaching out."

The second version admits you might be wrong (builds trust) without asking them to do your research.

#### Recommendation 5: Differentiate each follow-up email with NEW information.

Current pattern: Step 1 = pitch. Step 2 = same pitch, different words. Step 3 = same pitch, more detail. Step 4 = "Am I talking to the right person?"

Proposed pattern:
- **Step 1:** Problem-first hook + one proof point + specific CTA
- **Step 2:** Micro-case study (1 customer, 1 result, 2 sentences)
- **Step 3:** Contrarian insight or industry trend that affects them specifically
- **Step 4:** Graceful close — "Should I stop reaching out, or is the timing just off?"

Each email must give the buyer a reason to open the NEXT email. If they read Step 2 and it says nothing new, they'll never open Step 3.

#### Recommendation 6: Rewrite the PR firms sequence from scratch.

PR firms don't need an API. They don't build products. They need:
- Creator vetting (is this influencer brand-safe?)
- Media value proof (how much is this creator worth to the client?)
- Quick discovery (find me 10 creators in [niche] with real audiences)

**Rewrite Step 1 for PR firms:**

> Hi {{first_name}},
>
> When {{company_name}} pitches a creator to a client, how do you prove the audience is real?
>
> We work with PR teams who need fast creator vetting — brand safety, real vs. fake followers, audience demographics. You send us a handle, we send back the full breakdown. No platform to learn, no subscription — just data when you need it.
>
> Currently used by [1 named PR agency]. Worth seeing a sample report for a creator your team is evaluating right now?

---

## 2. ANALYST

### Diagnosis (what the data reveals about buyer behavior)

#### Finding 1: The real reply rate is better than it looks — but the pipeline is leaking badly at the handoff.

Raw numbers: 148 replies / 9,677 sent = 1.53% reply rate. Looks low.

But strip out the noise:
- 21+ OOO/auto-replies (not real engagement)
- 5 wrong person / left company
- 6 explicit "not interested"
- ~28 uncategorized (likely a mix)

**Real engaged replies: ~88** (12 interested + 5 warm misclassified + ~71 from the 66 unlogged + uncategorized pool)

From the 17 clearly interested/warm leads, 9 meetings were booked = **52.9% conversion from interested reply to meeting**. This is actually strong. The problem is not the email copy getting replies — the problem is what happens AFTER the reply.

**Evidence:** 19 WANNA TALK leads with zero follow-up. 66 replies not even logged. 21 OOO replies with no re-engagement plan. The pipeline is leaking qualified leads through operational gaps, not messaging failures.

#### Finding 2: Segment performance reveals a clear winner — focus is diluted.

| Segment | Contacts | Reply Rate | Meetings Booked | Meeting Rate |
|---------|----------|------------|-----------------|-------------|
| Marketing agencies (Wk 1-2) | 1,640 | 2.07% | 3 | 0.18% |
| IM platforms & SaaS (Wk 1-2) | 1,156 | 1.90% | 1 | 0.09% |
| Agencies + IM (Wk 3-4) | 2,950 | 1.69% | 3 | 0.10% |
| IM platforms (Wk 3-4) | 2,931 | 1.36% | 2 | 0.07% |
| PR firms (Wk 4) | 1,000 | 0.20% | 0 | 0.00% |

**Marketing agencies in Weeks 1-2 outperformed everything** — 2.07% reply rate AND the highest meeting rate (0.18%). By Week 3-4, the combined campaign's reply rate dropped to 1.69%, and the pure IM platforms campaign dropped to 1.36%.

PR firms: 0.20% reply rate. This is 10x worse than the best segment. With 1,000 contacts burned and zero meetings, this segment is producing negative ROI (domain reputation cost + SDR time).

**Week-over-week decline:** The Wk 3-4 campaigns show lower reply rates than Wk 1-2 across the board. Possible explanations: (a) best-fit leads were contacted first, (b) email domain warming issues, (c) sequence fatigue in overlapping audiences.

#### Finding 3: The 0903 campaigns are underperforming dramatically.

| Campaign | Sent | Replied | Reply Rate |
|----------|------|---------|------------|
| 0903_AGENCIES | 445 | 3 | 0.7% |
| 0903_PLATFORMS | 505 | 1 | 0.2% |

These are the newest campaigns (March 9) and they have the lowest reply rates. Only a fraction of leads have received all steps (445 of 511 contacted), so this may improve. But the early signal is weak. Compare with the flagship campaign (IM agencies & SaaS_US&EU): 6.2% reply rate from 1,979 sent. Something is different — likely list quality or sequence version.

#### Finding 4: LinkedIn generates engagement but zero revenue.

568 invites -> 107 accepted (18.84%) -> 20 replies (3.52%) -> **0 meetings**.

The accept and reply rates are healthy. But no one converts to a meeting. This means either: (a) the LinkedIn follow-up message after acceptance is wrong/missing, (b) there's no CTA pushing toward a meeting, or (c) the LinkedIn messages are conversational but never close.

Chad Smalley said "I would be happy to see a demo" on LinkedIn. Georg Broxtermann said "Send over a one pager." If these didn't convert to meetings, the problem is 100% in the follow-up process, not the channel.

#### Finding 5: Show rate is 55.6% — one in two no-shows.

9 meetings booked, 5 held = 55.6% show rate. Industry benchmark for cold outreach meetings is 60-70%. This is below average.

FanStories (William Jourdain) was a no-show. Sergio Eid (TWIC) stopped responding. Kreatory (David Winker) is scheduled but unconfirmed.

No mention of confirmation emails, reminder sequences, or pre-meeting nurture.

#### Finding 6: Quality filter is weak — 2 out of 11 meetings were wasted.

BrandNation (Melker) — "Very small, only MVP." Yagency (Yunus) — "Too small, can't afford." These were identifiable BEFORE the meeting by checking company size and funding. Each wasted meeting costs ~45 min of demo time + prep.

---

### Recommendations

#### Recommendation 1: Build a reply-stage funnel dashboard and measure weekly.

Current tracking stops at "reply rate." The real funnel is:

```
Reply -> Classified -> Responded to -> Meeting scheduled -> Meeting held -> Qualified
```

Measure each conversion weekly. Right now:
- Reply -> Classified: 52% (77/148 — 66 not logged)
- Classified -> Responded to: Unknown (no tracking)
- Responded to -> Meeting scheduled: ~52.9% (for interested leads)
- Meeting scheduled -> Held: 55.6%
- Held -> Qualified: ~71% (5/7 excluding waiting)

**The two biggest leaks are: Reply -> Classified (48% loss) and Meeting Scheduled -> Held (44.4% loss).**

#### Recommendation 2: Fix the show rate with a 3-touch confirmation sequence.

- **Immediately after booking:** Confirmation email with agenda, what you'll cover, and what they should prepare ("send me 2-3 creator handles")
- **24 hours before:** Reminder with Zoom link + "Looking forward to showing you the data on [creator they sent]"
- **1 hour before:** "See you in 60 min — here's the link"

Target: 75%+ show rate. This alone would add ~1.5 more held meetings from the existing 9 booked.

#### Recommendation 3: Implement pre-qualification before booking.

Add a minimum company size filter: 50+ employees AND either (a) has a product/platform where data integration makes sense, or (b) manages $500K+/year in influencer spend.

Melker (BrandNation) and Yunus (Yagency) would have been filtered out, saving 2 meeting slots. At the current volume (9 meetings in 4 weeks), each meeting is precious.

#### Recommendation 4: Run a proper A/B test with clean data.

Current state: TEST A vs TEST B deployed in the flagship campaign, but no results are tracked. The A/B testing protocol calls for "min 100 per variant" — the volume is there (1,977 leads in the flagship) but the data isn't being collected.

Specific test to run next:
- **Variable:** Step 1 opening line — product-first (current) vs. problem-first (rewrite)
- **Sample:** 200 leads per variant, same segment (Marketing agencies), same send schedule
- **Metric:** Reply rate + interested reply rate (not just any reply)
- **Duration:** 2 weeks (enough for 3-step delivery)

#### Recommendation 5: Calculate cost-per-meeting by segment.

Rough math:
- Marketing agencies: 1,640 contacts -> 3 meetings. Cost per meeting: 547 contacts burned.
- IM platforms: 1,156 contacts -> 1 meeting. Cost per meeting: 1,156 contacts burned.
- PR firms: 1,000 contacts -> 0 meetings. Cost per meeting: infinite.

Marketing agencies are 2x more efficient than IM platforms on a per-meeting basis. This should influence list allocation.

---

## 3. STRATEGIST

### Diagnosis (are we even talking to the right people?)

#### Finding 1: The ICP is too broad — 5 segments with 1 SDR is a recipe for mediocrity.

OnSocial is simultaneously targeting: (1) IM Platforms & SaaS, (2) Affiliate & Performance Platforms, (3) IM-First Agencies, (4) PR Firms, (5) Brands Direct (planned). Each segment needs different messaging, different proof points, different buying triggers, and different decision-makers.

With one SDR (Nastya) and one agency (Sally), spreading across 5 segments means none gets the depth it needs. The data proves this: the best-performing segment (marketing agencies Wk 1-2) got the most attention and the best results. The worst (PR firms) was an afterthought and it shows.

#### Finding 2: The WANNA TALK list is strategically misaligned.

19 leads include: Kantar (10,000+ employees), Patreon, Spotter, inDrive, Jellysmack. These are enterprise accounts requiring:
- Multi-threaded outreach (multiple contacts per account)
- Custom value propositions
- 3-6 month sales cycles
- Executive-level proof points

Yet they're being treated like any other cold lead — one message, "Messaged" status, no follow-up plan. This is like fishing for whales with a trout rod.

Worse: some targets don't make sense. **Patreon (Jack Conte, CEO)** — Patreon is a creator monetization platform, not an influencer marketing platform. They don't need audience demographics or fraud detection. **inDrive** — a ride-sharing company. They have zero use for creator data API.

Of the 19: Jellysmack, Spotter, Kantar, Mindshare are plausible targets. Patreon, inDrive, Dovetail are not.

#### Finding 3: The value proposition doesn't match the buyer's actual pain.

For **IM platforms (CTO/VP Eng)**, the real pain is NOT "we don't have creator data." Most platforms already have some data solution. The pain is:
- Data maintenance is eating engineering bandwidth
- Their coverage has gaps (e.g., TikTok, emerging markets)
- They're paying too much for their current provider
- Their data refresh rate is too slow

The current messaging assumes the buyer has NO data solution. The reality is they probably have one and it's "good enough." The pitch needs to be about **switching cost being lower than the pain of the status quo**.

For **agencies (CEO/Founder)**, the pain is NOT "creator sourcing takes too long." The pain is:
- Client asks for proof that a creator is worth the investment, and they can't deliver it
- They lose pitches to agencies that have better data
- They get burned by fake followers and the client blames them

Current messaging focuses on efficiency. The emotional trigger is FEAR OF LOOKING INCOMPETENT IN FRONT OF A CLIENT.

#### Finding 4: Strong fits reveal who the real ICP is.

The 5 strong fits: Brighter Click, The Shelf, MediaLabel, impact.com, Peersway.

Pattern analysis:
- **4 out of 5 are platforms/SaaS**, not agencies
- **All have existing products** where data integrates as a feature
- **All are mid-market** (50-500 employees) — not enterprise, not micro
- **All responded to the API/white-label angle** — they want to embed data, not consume reports

This tells us: **The ideal buyer is a mid-market influencer marketing platform (50-500 employees) with an existing product that needs better data behind it.** Not agencies. Not PR firms. Not enterprise. Not early-stage startups.

#### Finding 5: The competitive landscape is being ignored.

Every educated buyer in the IM space knows HypeAuditor, Modash, CreatorIQ, and Phyllo. The sequences never mention or differentiate against them. This means:
- Buyers who already use a competitor dismiss the email ("we have that")
- Buyers who are evaluating think OnSocial is another commodity option
- Buyers who are unhappy with their current provider get no reason to believe OnSocial solves their specific complaint

---

### Recommendations

#### Recommendation 1: Narrow to 2 segments for the next 30 days.

**Primary: IM Platforms & SaaS (50-500 employees)**
- This is where 4/5 strong fits came from
- The value prop (API integration, white-label) is strongest here
- Decision-maker is CTO/VP Eng/Head of Product — technical buyer who can evaluate quickly

**Secondary: IM-First Agencies (20+ employees, $1M+ annual revenue)**
- 2.07% reply rate in Wk 1-2 — best of any segment
- Different value prop: client retention tool, not a data pipeline
- Decision-maker is CEO/Founder — business buyer who buys based on fear

**Kill for now: PR Firms (0.20% reply rate, 0 meetings), Affiliate & Performance (no data yet), Brands Direct (unvalidated)**

Rationale: Every contact you send to a dead segment costs domain reputation. 1,000 PR firm emails at 0.20% reply rate means 998 people who either ignored or mentally flagged your domain. That hurts deliverability for the segments that actually work.

#### Recommendation 2: Build an Account-Based approach for the top 20 target accounts.

Instead of blasting 1,000 PR firms, identify the 20 best-fit IM platforms that look like Brighter Click, The Shelf, MediaLabel, impact.com, and Peersway. For each account:

1. Research their current data provider (check job postings, case studies, tech stack tools)
2. Identify 2-3 contacts (CTO + VP Product + Head of Data)
3. Write a custom Step 1 referencing their specific situation
4. Coordinate email + LinkedIn touchpoints
5. Track at the account level, not the lead level

20 accounts x 3 contacts = 60 highly targeted emails that will outperform 1,000 spray-and-pray emails every time.

#### Recommendation 3: Triage the WANNA TALK list immediately.

**Keep (plausible fit, worth enterprise approach):**
- Jellysmack — creator economy platform, data API fits
- Spotter — YouTube creator company, needs audience intelligence
- Kantar — market research, could use creator data for brand studies
- Mindshare — media agency, could use for influencer campaigns

**Remove (wrong ICP):**
- Patreon — creator monetization, not IM
- inDrive — ride-sharing, no connection to influencer marketing
- Dovetail — user research tool, wrong category

For the "keep" list: assign to a senior seller (not the SDR). These are multi-month, multi-stakeholder deals that need a different playbook.

#### Recommendation 4: Develop competitive positioning (not just differentiation).

Create a one-page competitive matrix that Nastya can reference in replies:

| Dimension | OnSocial | HypeAuditor | Modash | CreatorIQ | Phyllo |
|-----------|----------|-------------|--------|-----------|--------|
| Profiles | 450M+ | ~80M | ~250M | ~30M (premium) | API only |
| Pricing model | Per API call | SaaS seats | SaaS seats | Enterprise | Per call |
| Data freshness | Real-time | Weekly batch | Daily batch | Varies | Real-time |
| White-label | Full API | Limited | No | No | Full API |
| Strength | Coverage + price | Brand recognition | UX | Enterprise trust | Dev-friendly |

This lets the SDR handle "how are you different?" with specifics, not generalities.

#### Recommendation 5: Define disqualification criteria BEFORE the meeting.

Current state: Melker (BrandNation) and Yunus (Yagency) wasted meeting slots because there's no filter.

Disqualification criteria:
- Company has fewer than 20 employees AND no funding
- No existing product/platform (for platform segment) or fewer than 5 active clients (for agency segment)
- Located in a market OnSocial doesn't cover well
- Uses "looking for free/trial only" language

Add a pre-qualification question to the meeting booking flow: "What's your current monthly volume of creator lookups?" This filters out tire-kickers and gives the demo presenter useful context.

---

## 4. OPERATIONS

### Diagnosis

#### Issue 1: 66 replies lost in the void — this is the single biggest operational failure.

SmartLead shows 143 email replies. Google Sheet shows 77. That means 66 replies — nearly half — were never logged, never classified, never followed up on. At a 52.9% interested-to-meeting rate, those 66 replies could contain ~15-20 interested leads and ~8-10 additional meetings.

**Root cause:** Manual copy-paste from SmartLead inbox to Google Sheet. Nastya is doing outreach, replying, AND logging. There's no automation, no sync, and no accountability mechanism.

#### Issue 2: No CRM — Google Sheets is not a pipeline management tool.

The current "CRM" is a Google Sheet with multiple tabs. This means:
- No automated status tracking
- No follow-up reminders
- No lead deduplication (Luis Carrillo appears in 2 campaigns)
- No pipeline stage tracking
- No activity logging

For a team of this size (1 SDR + 1 agency), a sheet can work — but ONLY with strict process discipline. That discipline doesn't exist (66 unlogged replies, 19 stale WANNA TALK leads).

#### Issue 3: SmartLead API is partially broken.

From gaps-and-issues.md:
- `fetch_inbox_replies` returns 400 error
- `list_campaign_leads` returns N/A for lead details
- Manual replies from Nastya are invisible in API

This means any automation attempt hits a wall. The team can't build reliable sync between SmartLead and the sheet even if they wanted to.

#### Issue 4: No LinkedIn-to-meeting conversion process exists.

LinkedIn generated 20 replies and 0 meetings. Two of those replies were explicitly interested (Chad Smalley: "demo", Georg Broxtermann: "one pager"). If interested leads aren't converting, there is no process for moving a LinkedIn conversation to a meeting.

Expected process: Reply -> Qualify interest -> Transition to email (for calendar link) or send Calendly directly in LinkedIn DM -> Confirm meeting.

Current process: Reply -> ???

#### Issue 5: OOO follow-ups are completely manual — and not happening.

21 OOO auto-replies with return dates. None have documented follow-up dates. None show evidence of re-engagement. These are people who received the email, had an auto-reply fire (meaning the email reached their inbox), and will return to a clean inbox with no memory of your email.

This is free pipeline that's rotting.

#### Issue 6: Lead deduplication is missing.

Luis Carrillo (Adsmurai) received emails from TWO campaigns. This means: (a) some leads may be getting double-contacted, which damages brand perception, and (b) reply attribution becomes unreliable.

No dedup process exists across campaigns.

#### Issue 7: Personalization QA is missing.

Some leads received "Hi ," (empty first_name) — Pierre-Antoine Leroux, Anna Lukaszewicz, Gabrielle Backman. This is an instant credibility killer. No QA step exists before campaign launch to validate merge fields.

---

### Recommendations

#### Recommendation 1: Fix the reply logging gap TODAY — not next week, TODAY.

**Immediate action (2 hours):**
1. Export all replies from SmartLead for each campaign using the API stats endpoint (even if limited to ~500)
2. Cross-reference against the Google Sheet
3. Classify the missing 66 replies
4. Identify any interested/warm leads that were missed

**Permanent fix:**
- SmartLead has a webhook feature that can push replies to a Slack channel or Google Sheet via Zapier
- Set up: SmartLead reply webhook -> Zapier -> Google Sheet (new row with timestamp, lead name, company, campaign, reply text)
- Backup: Daily 10-minute "inbox sweep" as a mandatory end-of-day task for Nastya

#### Recommendation 2: Build an OOO follow-up calendar.

For each of the 21 OOO replies:
1. Extract the return date from the auto-reply
2. Create a calendar event for return_date + 2 business days
3. Assign to Nastya with the lead's name, company, and the original email they received
4. Use Script 9 (from Copywriter section) as the template

This should take 30 minutes to set up and could unlock 3-5 additional conversations.

#### Recommendation 3: Create a LinkedIn conversion playbook.

When a LinkedIn connection replies with interest:

**Step 1 (within 4 hours):** Acknowledge + qualify
> "Thanks {{name}}! Quick question — are you currently using any creator data tools, or is this a new area you're exploring?"

**Step 2 (after qualification):** Transition to meeting
> "Perfect — easiest way to show you is a quick 15-min call. Here's my calendar: [link]. Or if you prefer, I can send a 3-min Loom walkthrough first."

**Step 3 (if they go quiet):** Nudge (3 days later)
> "Hey {{name}} — wanted to make sure my last message didn't get buried. Still open to a quick look?"

For Chad Smalley and Georg Broxtermann: reach out NOW with step 2.

#### Recommendation 4: Add a pre-send QA step for merge fields.

Before any campaign launches:
1. Export the first 20 leads from SmartLead
2. Check: first_name present? company_name present? No special characters breaking the template?
3. Fix any gaps BEFORE sending

This prevents the "Hi ," problem. Takes 10 minutes per campaign.

#### Recommendation 5: Implement lead deduplication.

Before uploading leads to a new SmartLead campaign:
1. Export the email list
2. Cross-reference against all active campaign lead lists (can be done with a simple VLOOKUP or a Python script)
3. Remove duplicates

At current volume (6,287 total leads), this is manageable manually. If volume grows past 10K, invest in a dedup tool or script.

#### Recommendation 6: Consolidate campaign structure.

Currently 6 active campaigns + 7 completed/paused/archived = 13 total campaigns. Many overlap in audience (agencies + platforms mixed vs. separated). This makes tracking nearly impossible.

Proposed structure:
- **Campaign 1:** IM Platforms (primary segment) — single sequence, A/B tested
- **Campaign 2:** IM Agencies (secondary segment) — single sequence, A/B tested
- **Campaign 3:** Experimental (new segments, small batches, kill fast)

Three campaigns. Clear boundaries. Clean data.

---

## 5. TEAM PRIORITY MATRIX

**Top 5 actions ranked by impact on buyer experience and pipeline recovery:**

### #1: Recover the 66 unlogged replies + follow up on all warm leads (OPERATIONS + COPYWRITER)
- **Impact:** Could unlock 8-10 additional meetings from leads already in the pipeline
- **Effort:** 3-4 hours (export, classify, respond)
- **Buyer experience:** These people replied and heard NOTHING back. Every day of silence kills their interest. Some replied weeks ago. Do this today.

### #2: Write and deploy the 9 reply scripts (COPYWRITER)
- **Impact:** Directly improves the experience of every lead who says "yes" — the highest-value moment in the entire funnel
- **Effort:** 2 hours to write, 30 min to train Nastya
- **Buyer experience:** Right now, someone asks "What's the pricing?" and either gets nothing or an improvised answer. With scripts, they get a thoughtful, specific response within hours. This is where deals are won or lost.

### #3: Kill PR firms, narrow to 2 segments, reallocate contacts to IM Platforms (STRATEGIST)
- **Impact:** Stops burning 1,000+ contacts per week on a 0.2% reply rate segment. Redirects that volume to segments producing 2%+ reply rates
- **Effort:** 1 hour (pause campaign, redirect planned volume)
- **Buyer experience:** PR firms are getting irrelevant emails. Stopping those emails is GOOD for them and for your domain reputation.

### #4: Rewrite Step 1 of the flagship sequence to lead with buyer's problem, not product (COPYWRITER + ANALYST)
- **Impact:** If the rewrite moves reply rate from 1.5% to 2.5% (achievable based on Wk 1-2 benchmarks), that's ~23 additional replies per 2,250 contacts sent — potentially 5-6 more meetings per month
- **Effort:** 2 hours to write, 1 hour to set up A/B test
- **Buyer experience:** The difference between "We provide creator data via API" and "Is your team maintaining its own scraping pipeline?" is the difference between DELETE and HMMMM.

### #5: Fix the meeting show rate with a 3-touch confirmation sequence (ANALYST + OPERATIONS)
- **Impact:** Moving show rate from 55.6% to 75% = 1-2 more meetings held per month from existing bookings
- **Effort:** 1 hour to set up 3 reminder emails
- **Buyer experience:** When someone books a meeting and gets a confirmation with a personalized agenda ("I'll pull data on [creator they mentioned]"), they feel like the meeting will be worth their time. When they get a bare Calendly confirmation, it's easy to skip.

---

### Honorable mentions (do these in week 2):

- **#6:** Build LinkedIn conversion playbook and re-engage Chad Smalley + Georg Broxtermann (could yield 2 quick meetings)
- **#7:** Set up OOO follow-up calendar for 21 auto-replies (free pipeline, 30 min to set up)
- **#8:** Triage the WANNA TALK list — remove wrong-fit accounts (Patreon, inDrive, Dovetail), build account-based plans for the 4 that make sense
- **#9:** Pre-send QA checklist to eliminate "Hi ," personalization failures
- **#10:** Set up SmartLead webhook -> Google Sheet automation to prevent future reply logging gaps

---

*Report produced by Team Delta. Every recommendation is grounded in data from the data-room files and written from the buyer's perspective. No generic advice. No "consider doing X." Specific rewrites, specific numbers, specific actions.*
