# TEAM BRAVO — Full Analysis & Recommendations

Date: 2026-03-16
Data scope: 6 active campaigns, 9,677 emails sent, 568 LinkedIn invites, 148 email replies, 20 LI replies, 9 meetings booked, 5 held

---

## 1. COPYWRITER

### Diagnosis

**The sequences are good -- but they are solving the wrong problem for half the audience.**

The current sequences assume every prospect needs to be *educated* about what OnSocial does. All four frameworks (Generic, INFPLAT, IMAGENCY, AFFPERF) open with a product description. But looking at who actually replied "interested," a pattern emerges:

- 8 out of 12 interested replies came from the Generic/TEST B campaign (the shortest, punchiest version)
- The detailed frameworks (INFPLAT, IMAGENCY, AFFPERF) with tailored hypotheses are deployed to smaller cohorts and show no measurable lift over the generic
- The PR firms sequence -- which is the *most* aggressive on name-dropping ("NeoReach, Buttermilk, Gushcloud...") -- has the *worst* reply rate (0.2%)

**Core insight:** The name-dropping strategy backfires. When you say "NeoReach, Buttermilk, Gushcloud, Influencer.com, and Obviously all run on our API" to a PR firm, you're telling them "we work with your competitors, not with you." For platforms, competitor names signal validation. For agencies and PR firms, competitor names signal conflict of interest.

**The reply scripts are a crisis.** Nastya is responding to enterprise leads (impact.com, The Shelf, Peersway) ad hoc, from memory, using scripts designed for a fashion resale startup. Six of the most common reply types ("What's the pricing?", "Send more info", "How are you different from X?") have NO script at all. This is where deals die.

**Personalization bugs are deal-killers.** Empty `{{first_name}}` fields ("Hi ,") signal mass email to exactly the technical audience (CTOs, VP Engineering) who will blacklist you for it.

### Recommendations

#### A. New reply scripts -- full text for all 9 types

**Script 1: "What's the pricing?"** (highest priority -- 6 leads asked this)

> Hi {{first_name}},
>
> Pricing depends on three things: volume of lookups, which data modules you need (demographics vs. credibility vs. overlap), and whether you want API access or white-label reports.
>
> Ranges typically fall between $X-Y/mo for platforms processing [volume range], but the most useful thing I can do is pull a live sample with your actual requirements -- specific creators, geos, metrics -- so you're comparing apples to apples.
>
> Can we do 15 min this week? I'll come prepared with sample data relevant to {{company_name}}. Here's my calendar: {{calendar_link}}

**Why this works:** Doesn't dodge the pricing question (that kills trust), gives enough range to qualify without scaring off, but pivots to a demo where you control the narrative.

**Script 2: "Send more info / one-pager"**

> Hi {{first_name}},
>
> Attached is a one-pager covering our data coverage, integration approach, and sample output.
>
> The most useful thing is usually a live pull on a creator you're actually working with -- takes 2 minutes on a call and shows you exactly what the data looks like for your use case.
>
> Would [Day] or [Day] work for a quick 15-min walkthrough? {{calendar_link}}

**Attach:** A one-pager PDF must exist. If it doesn't, creating one is Operations priority #1.

**Script 3: "How are you different from HypeAuditor / SocialData / X?"**

> Hi {{first_name}},
>
> Good question. Three differences that matter in practice:
>
> 1. **Coverage:** 450M+ profiles vs. [competitor's ~Xm]. We cover creators below 10K followers where most campaign fraud hides.
> 2. **Data depth:** We include audience overlap between creators -- critical for preventing wasted reach on multi-creator campaigns. Most competitors don't offer this.
> 3. **Integration model:** Pure API, white-label ready. You're not locked into our UI or paying for features you don't use.
>
> The fastest way to compare is side-by-side: pick a creator, I'll pull our data live alongside whatever you're seeing from [competitor]. 15 min. {{calendar_link}}

**Script 4: "We already have a partner/system"**

> Hi {{first_name}},
>
> Makes sense -- most platforms at your stage do. The question is usually whether your current provider covers all three: data freshness (real-time vs. batch), coverage depth (450M+ profiles including micro-creators), and audience overlap.
>
> We're not asking you to switch. Many of our clients started by using us to fill gaps in their existing pipeline -- usually creator overlap or city-level demographics that their primary source doesn't cover.
>
> If the gaps sound familiar, worth a 15-min comparison. If not, no hard feelings. {{calendar_link}}

**Script 5: "Do you cover [region/platform]?"**

> Hi {{first_name}},
>
> Great question. Our current coverage:
> - **Platforms:** Instagram, TikTok, YouTube (450M+ profiles combined)
> - **Geographies:** Truly global -- we index creators and audience data worldwide, including [relevant region if covered]
>
> [If region IS covered:] Yes, we cover [region] -- I can pull sample data for creators in that market on a quick call.
> [If region is NOT covered:] [Region] is on our roadmap for [timeline]. In the meantime, if you need [covered region] data, happy to show you what we have.
>
> Worth a quick call to check coverage against your specific requirements? {{calendar_link}}

**Script 6: "Let's schedule a call"**

> Perfect, {{first_name}}. Here's my calendar: {{calendar_link}}
>
> To make the 15 minutes count -- is there a specific creator or campaign you're working on right now? I'll pull the full data breakdown before our call so you see real output, not slides.
>
> Looking forward to it.

**Script 7: "I'm interested, adding colleagues"**

> Thanks {{first_name}} -- great to have {{colleague_names}} looped in.
>
> Quick context for everyone: OnSocial provides creator and audience data via API -- 450M+ profiles, credibility scoring, audience demographics, fraud detection, and creator overlap. White-label ready, integrates in days.
>
> I'll prepare a walkthrough tailored to {{company_name}}'s specific use case. Would [Day] at [Time] work for the group? {{calendar_link}}
>
> If anyone has specific questions beforehand, feel free to reply here.

**Script 8: "Wrong person, try X"**

> Thanks {{first_name}} -- I appreciate the redirect.
>
> {{referred_name}}, I was referred to you by {{first_name}}. Quick context: OnSocial provides creator and audience data via API for platforms like {{company_name}} -- 450M+ profiles, credibility scoring, audience demographics, creator overlap. White-label ready.
>
> Worth 15 min to see if this fits your roadmap? {{calendar_link}}

**Script 9: OOO auto-reply follow-up**

> Hi {{first_name}},
>
> Hope you had a good [trip/break]. I reached out while you were away about OnSocial's creator data API -- 450M+ profiles, audience demographics, fraud detection, all available via API for platforms like {{company_name}}.
>
> Would this week work for a quick 15-min walkthrough? {{calendar_link}}

*Set calendar reminder for return date + 2 business days.*

#### B. Sequence rewrites

**Kill the PR firms name-dropping.** Replace the opening with a problem-first angle:

> Hi {{first_name}},
>
> When {{company_name}} recommends a creator for a PR campaign, how do you validate their audience is real and in the right market?
>
> Most PR firms we talk to either eyeball it (risky) or pay per-report fees that add up fast when you're vetting 20+ creators per campaign.
>
> We provide an API with audience demographics, credibility scoring, and fraud detection for 450M+ creators. Unlimited lookups, one price.
>
> Pick a creator you're vetting right now -- I'll pull the full breakdown on a 15-min call.

**For IM_PLATFORMS, swap name-dropping for a challenge:**

Current opener mentions "Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API." This triggers two reactions: (a) "they work with my competitors" and (b) "if everyone has this data, it's not a differentiator."

Replace with:

> Hi {{first_name}},
>
> Quick question: how many of the creator profiles in {{company_name}}'s database have verified audience demographics vs. estimated?
>
> We power the data layer for influencer marketing platforms -- 450M+ profiles with real-time credibility scoring, audience demographics down to city level, and creator overlap. API-native, white-label ready.
>
> Most platforms integrate in under a week. I can show you the actual API output with your required volume and filters -- worth 15 min?

#### C. Subject line fix

Current subjects are too long and feature-heavy. Data from the campaign shows TEST B (shorter subject: "450M influencer profiles for {{company_name}}") outperforms TEST A (longer: "{{first_name}}, 450M influencer profiles are ready for your API").

**New subject line variants to test:**

1. `Creator data infrastructure for {{company_name}}` (mirrors their internal language)
2. `Question about {{company_name}}'s creator data` (curiosity-driven)
3. `{{company_name}} + OnSocial` (partnership framing, ultra-short)

---

## 2. ANALYST

### Diagnosis

**The funnel is not broken where you think it is.**

Everyone is focused on the 1.53% email reply rate. But that number is misleading for three reasons:

1. **The reply rate varies 30x between segments.** The flagship campaign ("IM agencies & SaaS_US&EU") has a 6.2% reply rate -- which is excellent for cold outreach. The PR firms campaign has 0.2%. The blended 1.53% hides a segment that's working and a segment that's failing.

2. **Reply-to-meeting is actually the bottleneck, not reply rate.** 148 replies turned into only 9 meetings (6.08%). Even adjusting for OOO/auto-replies (21+) and explicit declines (6), you have ~55 genuine replies producing 9 meetings. That's 16.4% -- decent but not great. The real leak: **at least 17 "interested" or "warm" leads** (12 clean interested + 5 warm/misclassified) received replies that may or may not have been effective. With proper scripts, you should convert 50%+ of interested replies to meetings. You're at roughly 53% (9/17), which is OK but leaves room for improvement.

3. **The WANNA TALK list is a hidden goldmine worth more than the next 2,250 emails.** 19 enterprise leads (Kantar x5, Patreon x2, Spotter x2, Jellysmack x2, inDrive x3, Mindshare x2, Dovetail x1) are sitting in "Messaged" status. These are 500-10,000+ employee companies. ONE closed deal here is worth 50 small agency deals. Yet they have zero follow-up plan.

**The LinkedIn channel is leaking at the conversion step, not the engagement step.** 18.84% accept rate and 3.52% reply rate are strong numbers. But 0 meetings from 20 replies means the post-acceptance conversation flow is broken.

**PR firms is a waste of resources at current approach.** 1,000 contacts, 2 replies (0.2%), 0 meetings. The planned 250 more contacts next week will yield approximately 0.5 replies and 0 meetings. This is not a volume problem -- it's a targeting or messaging problem.

### Recommendations

#### A. Restructure the funnel tracking

Stop measuring "reply rate" as a single number. Break it into:

| Metric | Target | Current |
|--------|--------|---------|
| Email reply rate (Platforms & SaaS) | >5% | 6.2% (on track) |
| Email reply rate (Agencies) | >2% | 1.9% (close) |
| Email reply rate (PR firms) | >1% | 0.2% (FAILING) |
| Interested reply-to-meeting | >60% | ~53% |
| Meeting show rate | >70% | 55.6% (needs work) |
| Meeting-to-qualified rate | >50% | 100%* (great) |

*Excluding "not a fit" and "waiting"

#### B. Expected impact of fixing the reply script gap

Current state: ~55 genuine replies, 9 meetings (16.4% of all genuine, 53% of interested)
With proper scripts on all 9 reply types: expect 12-15 meetings from same 55 replies
Expected incremental meetings: 3-6 per month
At 100% qualified rate: 3-6 additional strong-fit leads per month

**This is the single highest-ROI fix.** It requires zero additional spend, zero additional contacts, zero additional tooling.

#### C. WANNA TALK conversion modeling

19 enterprise leads. Even at a conservative 10% conversion to meeting with proper multi-touch follow-up, that's 1-2 enterprise meetings. Given the size of these companies (Kantar: 10,000+, Patreon: 500-1000, Spotter: 200-500), one deal could be worth the entire SMB pipeline.

**Recommended sequence for WANNA TALK re-engagement:**

Week 1: Personalized email referencing their specific use case (research each company)
Week 2: LinkedIn connection request from the founder/CEO (not the SDR)
Week 3: Send a relevant case study or data sample unprompted
Week 4: "Breaking up" email with a clear ask

#### D. Kill or radically restructure PR firms

The data says stop. 0.2% reply rate is below the threshold where volume can save you. Two options:

1. **Kill it.** Reallocate the 250 planned contacts to Platforms & SaaS (which has 6.2% reply rate). Expected gain: 15+ additional replies, 2-3 meetings.
2. **Micro-test first.** Take 50 PR firms, rewrite the sequence completely (see Copywriter recommendation), and test for 2 weeks. If reply rate doesn't reach 1%+, kill the segment.

I recommend option 2, but with brutal honesty: 250 contacts on the current sequence is burning leads you can never contact again.

#### E. LinkedIn conversion fix

The problem is clearly post-reply. 20 people replied, 0 meetings. The data shows:
- 2 "Interested" (Chad Smalley, Georg Broxtermann)
- 2 "Warm" (Tatiana, Cristina)
- 2 "Not interested"
- 1 "Wrong person"

**That means 4 convertible LinkedIn replies produced 0 meetings.** This suggests:
- No follow-up after initial warm reply on LinkedIn
- No CTA or calendar link in LinkedIn messages
- Or the SDR doesn't have scripts for LinkedIn warm replies

**Fix:** Every LinkedIn reply categorized as "Warm" or "Interested" gets an immediate response with a calendar link within 2 hours.

#### F. Meeting show-rate improvement

55.6% show rate (5/9) is below industry standard of 70-80%. Two fixes:
1. Send calendar invite + confirmation email immediately after booking
2. Send reminder 24h before with a teaser: "I pulled {{company_name}}'s data ahead of our call -- interesting findings on your creator coverage gaps. See you tomorrow at [time]."

---

## 3. STRATEGIST

### Diagnosis

**The segmentation is fundamentally wrong -- and the data proves it.**

The current segmentation is by company *type* (Platforms & SaaS, Agencies, PR firms, Affiliate). But look at where the strong fits actually come from:

| Strong Fit | Company Type | Real Differentiator |
|------------|-------------|-------------------|
| Brighter Click | Marketing agency US | Small, tech-forward |
| The Shelf | Platform & SaaS US | Has existing data needs |
| MediaLabel | Platform & SaaS | Already has paid contract |
| impact.com | Platform & SaaS US | Large, expanding into creator |
| Peersway | Platform & SaaS US | Needs API data layer |

**Pattern:** 4 out of 5 strong fits are Platforms & SaaS. The one agency (Brighter Click) is a tech-forward agency that behaves like a platform. Zero strong fits from PR firms, zero from pure agencies without tech DNA.

**The real ICP is not "influencer marketing companies" -- it's "companies that need a data API layer."** This includes:
- Platforms building creator analytics features
- Tech-forward agencies with custom tooling
- Affiliate platforms adding creator intelligence
- Potentially: adtech, martech, e-commerce platforms adding influencer features

It does NOT include:
- Traditional PR firms (they buy tools, not APIs)
- Small agencies (<20 employees) who can't afford or integrate an API
- Agencies without technical teams

**The WANNA TALK list contradicts the ICP.** Half of those 19 leads are from companies (Kantar, Mindshare) that are media agencies, not influencer marketing companies. Are they there because someone thought "big company = good target"? Or because they actually have an influencer data need? This needs research before outreach.

**The competitor landscape is being ignored.** Norbert asked "How is your data different from HypeAuditor or SocialData?" and there's no script for this. More importantly, there's no competitive positioning document. OnSocial is entering a market with HypeAuditor, Modash, CreatorIQ, Phyllo, and others. The sequences mention none of this strategically.

### Recommendations

#### A. Redefine segmentation around buying behavior, not company type

New segments:

**Segment 1: API Buyers (PRIMARY -- 70% of resources)**
- Companies building products that need creator data infrastructure
- Titles: CTO, VP Engineering, Head of Product, CPO
- Company signals: has an engineering team, builds software, mentions "API" or "integration" on website
- Current reply rate: ~6.2% (flagship campaign)
- These are the people who wake up thinking "I need a data provider"

**Segment 2: Tool Buyers (SECONDARY -- 20% of resources)**
- Companies that want a dashboard/tool, not an API
- Titles: CEO, Head of Influencer Marketing, VP Marketing
- Company signals: <50 employees, no engineering team, uses other SaaS tools
- Current reply rate: ~2% (marketing agencies)
- Messaging must shift from "API" to "platform" / "dashboard" / "reports"
- **Critical insight:** These buyers don't care about API endpoints. They care about "show me the dashboard." The current messaging is wrong for them.

**Segment 3: Enterprise Strategic (EXPERIMENTAL -- 10% of resources)**
- Large companies expanding into creator/influencer space
- WANNA TALK list candidates (Kantar, Patreon, Spotter, etc.)
- Requires account-based marketing (ABM), not mass email
- Each target needs custom research and multi-channel approach

**Kill PR firms as a segment** until you have proof of concept with 2-3 manual wins.

#### B. Competitive positioning matrix

Create this document and use it in every sales conversation:

| Capability | OnSocial | HypeAuditor | Modash | Phyllo | CreatorIQ |
|-----------|----------|-------------|--------|--------|-----------|
| Profile coverage | 450M+ | ~75M | ~250M | API-focused | Enterprise |
| Audience overlap | Yes | Limited | No | No | Yes |
| White-label API | Yes | No | Limited | Yes | No |
| City-level demographics | Yes | Yes | No | No | Yes |
| Integration time | Days | N/A (SaaS) | Weeks | Days | Months |
| Pricing model | API-based | Subscription | Subscription | API-based | Enterprise |

*Populate with real competitive data. This is a template.*

#### C. Pre-qualification criteria

Stop booking meetings with companies that can't buy. Before confirming a meeting, verify:

1. Company has >20 employees (below this, they can't afford or integrate)
2. Company has at least one technical person (if targeting API buyers)
3. Company is in influencer marketing, affiliate, or adjacent space
4. Person has budget authority or direct access to budget holder

This would have filtered out BrandNation (too small, MVP only) and Yagency (can't afford), saving 2 meetings that produced nothing.

#### D. Account-Based approach for WANNA TALK

Stop treating enterprise leads like cold email targets. For each of the 19 WANNA TALK leads:

1. **Research:** 30 min per company. What is their current influencer marketing stack? Do they have a public API? Are they hiring for relevant roles?
2. **Disqualify ruthlessly:** Kantar assistants/EAs (Sarah Fernandes, Rachelle Minnis's assistants) are likely not decision-makers. Kantar has 5 contacts -- consolidate to 1-2 actual decision-makers.
3. **Multi-channel:** LinkedIn from the CEO (not SDR), followed by email, followed by warm intro if possible.
4. **Custom value prop:** "We noticed Kantar's recent expansion into creator analytics. Here's how our API could power that initiative" -- not the generic sequence.

#### E. Geographic focus

The data shows US-based companies convert better to strong fits (4/5 strong fits are US). Consider:
- Prioritize US time zones for outreach
- Adjust LinkedIn schedule to US business hours
- Test EU-specific messaging that acknowledges different market dynamics

---

## 4. OPERATIONS

### Diagnosis

**The outreach operation is running on duct tape and manual labor. Every manual step is a leak point.**

**Problem 1: 66+ unlogged replies.** This is not a "data gap" -- this is flying blind. You cannot optimize what you cannot measure. If 66 replies are missing, your real reply rate could be 2x what you think. More critically, some of those 66 replies might be interested leads that never received a follow-up.

**Problem 2: SmartLead API is broken for your use case.** The `fetch_inbox_replies` endpoint returns 400 errors. Manual replies from Nastya are invisible in the API. This means your CRM (Google Sheet) and your outreach tool (SmartLead) are disconnected systems with no bridge.

**Problem 3: No SLA on reply handling.** There's no defined timeline for when a reply should be (a) logged, (b) categorized, (c) responded to. Enterprise leads like impact.com or The Shelf could be waiting 24-48 hours for a response while Nastya manually processes everything.

**Problem 4: Cross-campaign deduplication is broken.** Luis Carrillo from Adsmurai appears in two campaigns. This means the same person could receive two different sequences simultaneously -- a guaranteed way to get marked as spam.

**Problem 5: Empty personalization fields.** Some leads have empty `{{first_name}}` fields, producing "Hi ," in the email. This is a data quality issue at the enrichment/import stage.

**Problem 6: No one-pager or sales collateral exists** (or if it does, it's not referenced anywhere). When Georg says "Send over a one pager" and Roland says "send us a presentation," what does Nastya send? If there's no standard document, every response is improvised.

**Problem 7: The A/B testing protocol exists on paper but not in practice.** The sheet defines cohort sizes (min 100 per variant), timing, and test sequence. But there's no tracking of which variant produced which results. The testing is performative, not functional.

### Recommendations

#### A. Fix reply logging TODAY (2 hours of work)

1. Export all 143 replies from SmartLead API (the endpoint works for outbound sequence replies, just not manual/inbox replies)
2. Cross-reference against the 77 in Google Sheet
3. Log the missing 66 with categories
4. Check for any interested/warm leads that were missed

**Process going forward:** Nastya logs every reply within 4 hours of receipt, with category. This is a non-negotiable SLA.

**Automation option:** Set up a Zapier/Make workflow: SmartLead webhook on new reply --> Google Sheet row. Cost: ~$20/month. Saves 30+ min/day of manual work.

#### B. Create response SLA

| Reply Category | Response Time | Action |
|---------------|---------------|--------|
| Interested (wants pricing/demo) | < 4 hours | Use pricing script, propose time |
| Warm (asking questions) | < 8 hours | Use relevant script, answer question |
| Wrong person (redirect) | < 24 hours | Send redirect script to new contact |
| OOO | Set calendar reminder | Follow up on return date + 2 days |
| Not interested | < 24 hours | Polite close, tag in sheet |

#### C. Fix personalization at source

Before any new campaign launch:
1. Filter lead list for empty `first_name` field -- exclude or manually fill
2. Filter for empty `company_name` field -- exclude or manually fill
3. Run dedup against all active campaigns -- remove duplicates

**This takes 15 minutes per campaign launch and prevents embarrassing "Hi ," emails to CTOs.**

#### D. Create the missing sales collateral

**Priority 1: One-pager (PDF)**
Content: What OnSocial does, key metrics (450M+ profiles, 3 platforms, real-time), integration model (API, days not months), sample output screenshot, 2-3 client logos (with permission), contact info.
Timeline: Should exist within 48 hours.

**Priority 2: Competitive comparison sheet**
Content: OnSocial vs. HypeAuditor vs. Modash vs. Phyllo (see Strategist section)
Use case: When leads ask "How are you different from X?"

**Priority 3: Sample report / data output**
Content: Example API response for a known creator, visualized
Use case: Attach to follow-ups, use in demos

#### E. Dedup process

Before launching any campaign:
1. Export all leads from all active campaigns
2. Match on email address
3. Remove duplicates from the newer campaign
4. Document in a "dedup log" tab in the Google Sheet

#### F. LinkedIn process fix

Current state: 20 replies, 0 meetings. The process is broken because:
1. No script exists for LinkedIn warm replies
2. No calendar link is being shared on LinkedIn
3. No follow-up cadence after initial LinkedIn reply

**New LinkedIn process:**
- Warm/Interested reply --> respond within 2 hours with: "Great to connect! I'd love to show you what our data looks like for [their company's use case]. Here's a quick link to grab 15 min: [calendar link]"
- If no response in 3 days --> follow up: "Just floating this back up -- would [specific day] work for a quick call?"
- If no response in 7 days --> move to email with reference: "We connected on LinkedIn last week..."

#### G. OOO tracking automation

Create a dedicated "OOO Follow-up" tab in Google Sheet:
| Lead | Company | OOO Until | Follow-up Date | Status |
Set calendar reminders for each follow-up date. 21 OOO replies = 21 potential re-engagements that are currently being lost.

---

## 5. TEAM PRIORITY MATRIX

**Top 5 actions ranked by (Impact x Urgency) / Effort:**

### #1. Write and deploy the 9 reply scripts (COPYWRITER)
- **Impact:** HIGH -- directly converts existing warm leads to meetings (3-6 incremental meetings/month)
- **Effort:** LOW -- 2-3 hours of writing, 30 min to train Nastya
- **Urgency:** CRITICAL -- leads are going cold RIGHT NOW
- **Expected result:** +40% improvement in interested-to-meeting conversion

### #2. Log the 66 missing replies and rescue lost leads (OPERATIONS)
- **Impact:** HIGH -- potentially 5-10 interested leads sitting in limbo
- **Effort:** LOW -- 2-4 hours one-time, then automate
- **Urgency:** CRITICAL -- every day without follow-up reduces conversion probability by ~10%
- **Expected result:** Recovery of 2-5 leads, establishment of data hygiene baseline

### #3. Launch WANNA TALK re-engagement with ABM approach (STRATEGIST + OPERATIONS)
- **Impact:** VERY HIGH -- one enterprise deal from this list (Kantar, Patreon, Spotter) could exceed total revenue from SMB pipeline
- **Effort:** MEDIUM -- requires 30 min research per lead (19 leads = ~10 hours), custom messaging, multi-channel coordination
- **Urgency:** HIGH -- these leads were messaged and then abandoned; window is closing
- **Expected result:** 2-4 enterprise meetings within 3 weeks

### #4. Kill PR firms sequence / reallocate to Platforms & SaaS (STRATEGIST + ANALYST)
- **Impact:** MEDIUM-HIGH -- stops burning leads at 0.2% reply rate, redirects to segment with 6.2% reply rate
- **Effort:** LOW -- decision + campaign adjustment, 1 hour
- **Urgency:** HIGH -- 250 more PR firm contacts planned for this week will be wasted
- **Expected result:** 15+ additional replies, 2-3 meetings from reallocated contacts

### #5. Fix LinkedIn post-reply flow + create sales collateral (OPERATIONS + COPYWRITER)
- **Impact:** MEDIUM -- converts existing LinkedIn warm leads + provides assets for all channels
- **Effort:** MEDIUM -- LinkedIn scripts (1 hour) + one-pager creation (4-6 hours)
- **Urgency:** MEDIUM -- LinkedIn has 20 replies producing 0 meetings; every new reply without a script is another lost opportunity
- **Expected result:** 1-2 meetings from LinkedIn per month, faster email reply handling

---

## CONTRARIAN TAKES -- Things the team should debate

1. **Stop A/B testing.** You don't have the volume for statistical significance. At 100+ contacts per variant minimum, and your current reply rates, you'd need 5,000+ contacts per test to get a reliable signal. Instead, pick the best-performing sequence (Generic TEST B) and iterate based on qualitative reply analysis, not split tests.

2. **The 450M number might be hurting you.** Multiple interested replies (Urban at Influee, Norbert at PFR Group) immediately questioned data quality/differentiation. When everyone claims massive numbers, the number becomes meaningless. Consider leading with *depth* (city-level demographics, audience overlap, real-time updates) rather than *breadth* (450M profiles).

3. **You might be targeting the wrong titles.** Your strong fits came from: a CEO (Brighter Click), a CTO (The Shelf -- Atul is technical), a founder (MediaLabel), a VP (impact.com), a CEO (Peersway). The common thread isn't the title -- it's that these are people who *personally understand the technical problem*. Target technical decision-makers, not marketing executives.

4. **Consider a "reverse demo" approach.** Instead of asking for a call, send them their own data unprompted. "I pulled {{company_name}}'s top 3 creator profiles through our API -- attached is what your audience overlap looks like. Worth discussing?" This is aggressive but would stand out dramatically in a crowded inbox.

5. **LinkedIn might be the wrong channel for this ICP.** Technical decision-makers (CTOs, VP Engineering) are notoriously unresponsive on LinkedIn. They respond to: GitHub, technical blog posts, developer community forums, and warm introductions. Consider shifting LinkedIn budget to content marketing or developer relations.

---

*Report generated by Team Bravo. All recommendations are based on data from the OnSocial data room as of 2026-03-16. Numbers are approximate where source data is incomplete (66 unlogged replies introduce uncertainty into all conversion metrics).*
