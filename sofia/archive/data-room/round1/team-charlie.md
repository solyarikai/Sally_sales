# TEAM CHARLIE — Full Analysis & Recommendations

**Date:** 2026-03-16
**Scope:** OnSocial outreach performance Feb-Mar 2026, all channels
**Data sources:** SmartLead campaigns, Google Sheet dashboard, replied leads log, reply scripts, gap analysis

---

## 1. COPYWRITER

### Diagnosis

**What's working:**
- The flagship "IM agencies & SaaS" campaign (2947684) achieves 6.2% reply rate — 4x the overall average. This sequence (TEST B, shorter/punchier) is the clear winner.
- The social proof approach ("Modash, Captiv8, Kolsquare... all run on our API") generates genuine interest. Leads like Atul (The Shelf) and Johan (impact.com) converted to strong-fit meetings.
- Touch 4 ("Are you the right person...") generates useful redirects (5 redirects logged), which is a low-cost lead gen channel in itself.

**What's broken:**

1. **Reply scripts are from a completely different product.** The "replies examples" sheet contains scripts for The Fashion People (branded resale platform for fashion). Nastya is responding to OnSocial leads — asking about API pricing, HypeAuditor comparisons, SEA coverage — using scripts about "resale platforms" and "LTV & AOV." This is a catastrophic mismatch. Every mishandled reply from a warm lead is a wasted $5-15 of acquisition cost (based on ~$50 per genuine reply at current volumes).

2. **PR firms sequence is tone-deaf to the segment.** The PR firms variant opens with "We power creator data for PR firms like {{company_name}} — NeoReach, Buttermilk, Gushcloud..." But NeoReach, Buttermilk, and Gushcloud are NOT PR firms — they are influencer marketing platforms/agencies. A PR firm Head of Digital reading this will think "you don't even know what I do." Result: 0.20% reply rate on 1,000 contacts. The copy name-drops irrelevant companies to a segment that cares about earned media, journalist relationships, and brand reputation — not creator sourcing volume.

3. **Personalization failures.** Some leads received "Hi ," with blank first_name (Pierre-Antoine Leroux, Anna Lukaszewicz, Gabrielle Backman). At 9,677 emails sent, even 2% empty fields = ~194 leads getting a broken email. This tanks credibility instantly, especially with CTOs and VPs who will dismiss sloppy outreach.

4. **No closing language in LinkedIn messages.** 20 LinkedIn replies, 0 meetings. The email sequences end with clear CTAs ("15 min to look at the actual output?"), but the LinkedIn follow-up apparently lacks a conversion step. Two LinkedIn leads explicitly said "happy to see a demo" (Chad Smalley) and "send over a one pager" (Georg Broxtermann) — were these actioned? If not, that is pure waste.

5. **5 warm leads misclassified as "other" are dying.** Norbert (PFR Group) asked "How is your data different from HypeAuditor or SocialData?" — this is a buying signal masked as a question. Jacob (KJ Marketing) literally said "Your talking to the right person!" Melker (BrandNation) asked for pricing. Georg (GameInfluencer) asked for more info. Bronson (Luxe Latam) went OOO and needs follow-up. These 5 leads are sitting uncategorized and likely un-responded-to.

### Recommendations

#### R1. Write 9 OnSocial-specific reply scripts immediately (Effort: 3 hours | ROI: Recover 10-15 warm leads = 2-4 additional meetings at current 16.4% reply-to-meeting rate)

**Script 1: "What's the pricing?"** (highest priority — 6 leads asked this)

> Hi {{first_name}},
>
> Pricing depends on your volume and data needs, but to give you a range:
>
> - API access starts at $X/month for up to Y lookups
> - Enterprise plans with unlimited lookups are custom-quoted based on usage
>
> Rather than guess what {{company_name}} needs — can we do 15 minutes this week? I'll pull a live demo with a creator your team is actually evaluating, and we can talk pricing against your real use case.
>
> Here's my calendar: {{calendar_link}}

*Note: Fill in actual pricing tiers from OnSocial's pricing model. If pricing is not standardized yet, use: "Pricing is usage-based — I can give you an exact quote after a 15-min scoping call."*

**Script 2: "Send more info / one pager"**

> Hi {{first_name}},
>
> Attached is a one-pager covering what our API returns, integration timeline, and which platforms we cover.
>
> One thing a doc can't show: the actual data output for a creator your team cares about. If you send me a handle, I'll pull the full breakdown — credibility score, audience demographics, overlap — and send it back. Takes 2 minutes and is worth more than any PDF.
>
> Or we can do it live in 15 min: {{calendar_link}}

*Requires: Create a one-pager PDF. This is a blocker — Georg and Roland both asked for this and without it, you lose them.*

**Script 3: "How are you different from [competitor]?"**

> Hi {{first_name}},
>
> Good question — here's the honest breakdown vs. HypeAuditor/SocialData:
>
> 1. **Coverage:** 450M+ profiles vs. HypeAuditor's ~75M. We cover IG, TikTok, AND YouTube in a single endpoint.
> 2. **API-first:** We don't sell a dashboard — we sell the data layer. You wrap it in your own product. HypeAuditor wants you to use their UI.
> 3. **Audience overlap:** We calculate cross-creator audience overlap — critical for campaign planning. Most competitors don't offer this.
> 4. **Pricing:** Usage-based, not per-seat. Scales with your actual needs.
>
> Easiest to compare with a live test — pick a creator, I'll pull our data and you can benchmark it against what you're getting now. 15 min: {{calendar_link}}

**Script 4: "We already have a partner/system"**

> Hi {{first_name}},
>
> Understood — most platforms we work with had a provider before switching or adding us as a second source. The two reasons they usually explore us:
>
> 1. **Coverage gaps** — their current provider doesn't cover TikTok well, or misses creators under 100K followers
> 2. **Cost** — they're paying per-seat or per-report when usage-based API pricing would cut their bill 30-50%
>
> If neither applies, no hard feelings. But if either sounds familiar, happy to do a 15-min side-by-side comparison. No commitment.

**Script 5: "Do you cover [region/platform]?"**

> Hi {{first_name}},
>
> Yes/No — [specific answer to their question].
>
> For Southeast Asia specifically: we have strong coverage across IG and TikTok. YouTube coverage is global. China (Douyin, Xiaohongshu) is not in scope currently — we focus on Instagram, TikTok, and YouTube.
>
> If SEA coverage is your priority, I can pull sample data for creators in your target markets. Worth a 15-min look?

**Script 6: "Let's schedule a call"**

> Great — here's my calendar link: {{calendar_link}}
>
> If none of those times work, just suggest a slot and I'll make it happen.
>
> Before the call, is there a specific creator or use case you'd like me to prepare data for? Helps make the 15 min count.

**Script 7: "Adding colleagues" (multi-stakeholder)**

> Hi {{first_name}}, and welcome {{colleague_names}} —
>
> Quick context for the thread: OnSocial provides creator and audience data via API — 450M+ profiles, credibility scoring, audience demographics, fraud detection, and creator overlap. Your team wraps it in your own product UI.
>
> I'd suggest a 20-min call so everyone can see the live API output and ask questions together. Here's my calendar: {{calendar_link}}
>
> {{first_name}}, does [suggested time] work for your team?

**Script 8: "Wrong person, try X"**

> Hi {{first_name}}, thanks for the redirect.
>
> {{redirected_name}}, {{original_name}} suggested you'd be the right person to discuss creator data infrastructure at {{company_name}}.
>
> Quick version: we provide creator and audience data via API (450M+ profiles, IG/TikTok/YouTube). Your team integrates it as a native feature. Most integrations go live in under a week.
>
> Would you be open to a 15-minute walkthrough?

**Script 9: "OOO with return date"**

> [Set calendar reminder for return date + 1 business day]
>
> Hi {{first_name}},
>
> Hope you had a good [trip/break]. Picking up where we left off — we provide creator data via API for platforms like {{company_name}}.
>
> Worth a 15-min look this week? {{calendar_link}}

**Cost justification:** 9 scripts x 20 min average = 3 hours of copywriting. At current conversion rates, recovering even 3 of the 5 misclassified warm leads into meetings = ~$0 incremental cost, $15K-50K potential deal value each.

---

#### R2. Rewrite PR firms sequence from scratch (Effort: 2 hours | ROI: lift reply rate from 0.20% to 1.5%+ = 12-15 additional replies from 1,000 remaining contacts)

The current PR firms sequence fails because it positions OnSocial as an influencer marketing tool to people who don't think of themselves as doing influencer marketing. PR firms care about:
- Earned media amplification
- Brand reputation monitoring
- Journalist/creator credibility verification
- Campaign measurement beyond vanity metrics

**Rewritten PR Firms Sequence:**

**Subject:** Creator vetting for {{company_name}}'s earned media campaigns

**Step 1:**
> Hi {{first_name}},
>
> When {{company_name}} recommends a creator for a brand partnership, how do you verify their audience is real?
>
> We provide an API that returns credibility scoring, audience demographics (country, city, age, gender), and fraud signals for 450M+ creators across IG, TikTok, and YouTube. PR firms use it to vet creator partners before putting them in front of clients.
>
> The pitch to your client becomes "we checked — this creator's audience is 87% real, 62% female, 45% US-based" instead of "they have 500K followers."
>
> Worth a 15-min look?

**Step 2:**
> Hey {{first_name}},
>
> One metric PR teams tell us matters most: audience overlap.
>
> Before recommending 3 creators for a campaign, you can check if they share 60% of the same audience. Catches wasted reach before the brief goes out — and gives your client a reason to trust your recommendations over an influencer marketplace.
>
> Quick look at a sample report? {{calendar_link}}

**Step 3:**
> Hey {{first_name}},
>
> Last note — if {{company_name}} already has a reliable way to verify creator audiences before recommending them to brands, ignore me.
>
> If not, 15 min to see the data: {{calendar_link}}

**Key changes:**
- Removed irrelevant social proof (NeoReach, Buttermilk are not PR firms)
- Reframed value prop around "vetting" and "credibility" (PR language) instead of "sourcing" and "data pipelines" (SaaS language)
- Positioned creator data as a tool for client trust, not operational efficiency
- Shorter, less feature-heavy

---

#### R3. Fix personalization failures (Effort: 30 min | ROI: prevent ~194 broken emails per 10K sent)

- Add a fallback in SmartLead: if `{{first_name}}` is empty, use "Hi there" or "Hey"
- Before uploading any lead list, run a validation check: filter for rows where first_name is blank or company_name is blank
- For leads already contacted with blank fields: no recovery possible, mark as burned

---

#### R4. Add a CTA close to LinkedIn follow-up scripts (Effort: 30 min | ROI: convert 2-4 of 20 LinkedIn replies into meetings = 2-4 meetings at $0 incremental cost)

After any positive LinkedIn reply, the response should include:

> Thanks {{first_name}} — would you be open to a quick 15-min call this week to see the API output live?
>
> Here's my calendar: {{calendar_link}}
>
> Or if you prefer, I can send a one-pager first.

Every warm LinkedIn reply without a calendar link or concrete next step is a missed meeting.

---

## 2. ANALYST

### Diagnosis

**Funnel math (email channel):**

| Stage | Count | Rate | Benchmark | Status |
|-------|-------|------|-----------|--------|
| Sent | 9,677 | — | — | — |
| Replied | 148 | 1.53% | 2-5% | Below average |
| Genuine replies (excl. OOO/auto) | ~55 | 0.57% | — | — |
| Meetings booked | 9 | 6.08% of all replies / 16.4% of genuine | 15-25% of genuine | OK |
| Meetings held | 5 | 55.6% of booked | 60-80% | Below average |
| Strong fit | 5 | 100% of held* | 30-50% | Excellent |

*Excluding not-a-fit and waiting status.

**Key insight:** The funnel is NOT broken at the top or bottom — it's broken in the MIDDLE. The qualification rate of held meetings is actually outstanding (5/5 strong fits from properly held meetings). The problem is:
1. Too few replies (1.53% overall, dragged down by PR firms at 0.20%)
2. Too many replies are OOO/auto (21/148 = 14.2%) or unactionable
3. Reply-to-meeting conversion is losing leads in the handoff (66 unlogged replies = leads falling through cracks)

**Segment-level economics:**

| Segment | Contacts | Cost/Contact* | Replies | Cost/Reply | Meetings | Cost/Meeting | Strong Fits |
|---------|----------|---------------|---------|------------|----------|--------------|-------------|
| Marketing agencies | 1,640 | ~$0.15 | 34 | ~$7.24 | 3 | ~$82 | 1 (Brighter Click) |
| IM platforms & SaaS | 1,156 | ~$0.15 | 22 | ~$7.88 | 1 | ~$173 | 1 (The Shelf) |
| Agencies + IM (combined) | 2,950 | ~$0.15 | 50 | ~$8.85 | 3 | ~$148 | 2 (MediaLabel, impact.com) |
| IM platforms (wk3-4) | 2,931 | ~$0.15 | 40 | ~$10.99 | 2 | ~$220 | 1 (Peersway) |
| PR firms | 1,000 | ~$0.15 | 2 | ~$75.00 | 0 | N/A | 0 |
| **Total** | **9,677** | — | **148** | **$9.80** | **9** | **$161** | **5** |

*Estimated at $0.15/contact (email tool cost + lead sourcing amortized). Actual cost may be higher if including SDR time.*

**PR firms are burning money.** At $75 per reply and 0 meetings, this segment has negative ROI. Every dollar spent on PR firms could generate 10x more pipeline in the IM platforms & SaaS segment.

**LinkedIn channel economics:**

| Metric | Value | Comment |
|--------|-------|---------|
| Invites sent | 568 | — |
| Accepted | 107 (18.8%) | Healthy |
| Replies | 20 (3.5% of invites) | Decent |
| Meetings | 0 | Catastrophic |
| Cost/invite | ~$0 (organic) | Only SDR time |
| SDR time/invite | ~2 min | Estimated |
| Total SDR time | ~19 hours | 568 invites x 2 min |
| ROI | $0 revenue from 19 hours | Negative |

LinkedIn is producing warm conversations but zero pipeline. 19 hours of SDR time with 0 meetings is a process failure, not a channel failure.

**WANNA TALK list — trapped enterprise value:**

19 enterprise leads (Kantar 10,000+ employees, Patreon 500-1000, Spotter 200-500, inDrive 1,000-5,000, Jellysmack 200-500) are sitting in "Messaged" status. If even 1 of these converts, the deal value likely exceeds all other pipeline combined. Conservative estimate:

- Enterprise API contract: $50K-200K/year
- Probability of converting 1 of 19 with proper follow-up: 10-15%
- Expected value: $5K-30K
- Cost of follow-up sequence: ~2 hours of work

This is the single highest-ROI activity available right now.

### Recommendations

#### R1. Reallocate PR firms budget to IM platforms & SaaS (Impact: save ~$150/week in wasted contacts, redirect to 10x higher-performing segment)

Stop the PR firms campaign immediately. The 0.20% reply rate with 1,000 contacts and 0 meetings is below statistical significance for "working." Before investing more:
- Rewrite the sequence entirely (see Copywriter R2)
- Test with a micro-cohort of 100 PR firms with the new copy
- Only scale back up if reply rate exceeds 1.0%

Redirect those 1,000 planned weekly contacts to IM platforms & SaaS, which produces meetings at 4-6x better rates.

#### R2. Build a reply classification system (Impact: recover 5-10 warm leads from existing data, prevent future leakage)

Current classification has 35 of 77 replies in "other" — 45% of all replies are unactionable because nobody can tell what they are. Implement a 5-category system:

| Category | Action | SLA |
|----------|--------|-----|
| INTERESTED | Send relevant script, book call | Within 4 hours |
| COMPARING (asking about competitors/pricing) | Send comparison script, book call | Within 4 hours |
| OOO | Set calendar reminder for return date +1 day | Within 24 hours |
| WRONG PERSON | Send redirect script to new contact | Within 24 hours |
| NOT INTERESTED | Mark closed, do not re-contact | None |

#### R3. Track A/B test results properly (Impact: 20-50% improvement in reply rate over 2 months through systematic optimization)

Current state: A/B testing protocol is documented (cohort sizes, timing, metrics) but results are not tracked. The testing protocol calls for min 100 per variant to declare a winner — but there's no dashboard showing which variant is winning.

Action: Add 3 columns to the Google Sheet dashboard:
- Variant (A/B)
- Reply rate per variant
- Meeting rate per variant

The campaign "IM agencies & SaaS" (2947684) appears to run TEST B and gets 6.2% reply rate. Is TEST A running anywhere? If not, why was it designed? If it ran in an archived campaign, what was its reply rate? This data exists somewhere — find it.

#### R4. Implement a "show rate" improvement process (Impact: increase held/booked from 55.6% to 75% = 1-2 additional meetings per month)

Current show rate is 55.6% (5 held / 9 booked). Industry benchmark is 60-80%. Each no-show is a wasted meeting slot worth ~$161 in acquisition cost.

Actions:
- Send confirmation email 24 hours before the call
- Send reminder 1 hour before
- Include a brief agenda: "I'll show you live API output for a creator in your space — bring a handle if you have one"
- If no-show, send same-day follow-up: "Missed you today — here's a new link to reschedule: {{calendar_link}}"

William Jourdain (FanStories) no-showed on Mar 9. Was he followed up? If not, he's a recoverable lead.

---

## 3. STRATEGIST

### Diagnosis

**Segment performance ranking (by cost-per-strong-fit):**

| Rank | Segment | Strong Fits | Approx. Cost | Cost/Strong Fit | Verdict |
|------|---------|-------------|--------------|-----------------|---------|
| 1 | IM agencies & SaaS (flagship) | 2 | ~$443 | ~$221 | **Scale aggressively** |
| 2 | Marketing agencies | 1 | ~$246 | ~$246 | **Maintain** |
| 3 | IM platforms (wk3-4) | 1 | ~$440 | ~$440 | **Optimize copy** |
| 4 | Agencies + IM combined | 1 | ~$443 | ~$443 | **Maintain** |
| 5 | PR firms | 0 | ~$150 | N/A (infinite) | **Pause** |

The flagship campaign (2947684) with TEST B is the undisputed winner. It produces strong fits at 2x the rate of any other segment and has the highest reply rate (6.2%).

**ICP clarity problem:**

The current ICP targets 5 segments simultaneously (IM platforms, affiliate/performance, IM agencies, PR firms, brands). With a team of 2 (Sally + Nastya), this is too fragmented. Each segment requires:
- Unique sequence copy (different pain points)
- Unique reply scripts (different objections)
- Unique social proof (different reference customers)
- Unique LinkedIn messaging

At 5 segments x 4 items = 20 distinct content assets needed. Currently, there are 4 sequence frameworks + 0 working reply scripts + 0 LinkedIn scripts = massive gaps.

**Social proof analysis:**

The strongest-performing emails mention real customer names. But the claims are inconsistent:

- PR firms sequence claims: "NeoReach, Buttermilk, Gushcloud, Influencer.com, Obviously all run on our API" — but these are NOT PR firms
- IM platforms sequence claims: "Modash, Captiv8, Kolsquare, Influencity, Phyllo, Lefty all run on our API" — if true, this is very strong social proof
- The BRIEF lists actual customers as: Viral Nation, Whalar, Billion Dollar Boy

Are all of these actually customers? If the social proof is fabricated or exaggerated, this is a legal and reputational risk with enterprise buyers who will verify claims.

**WANNA TALK list — strategic analysis:**

The 19 WANNA TALK leads are disproportionately enterprise (10,000+ employee companies). This is a completely different sales motion than the SMB/mid-market leads booking meetings today:

| Company | Employees | Why they matter |
|---------|-----------|-----------------|
| Kantar | 10,000+ | World's largest data/insights company. Could be $500K+ annual contract. |
| Patreon | 500-1,000 | Creator economy infrastructure. Natural product fit. |
| Spotter | 200-500 | YouTube-focused creator economy company. Raised $200M+. |
| Jellysmack | 200-500 | Creator management. Raised $300M+. |
| inDrive | 1,000-5,000 | Ride-hailing + creator marketing expansion. |

These are NOT leads you email once and forget. These require multi-threaded outreach (multiple contacts per company), personalized research, and potentially warm introductions. The current "Messaged once, no follow-up" approach is negligence given the potential deal sizes.

### Recommendations

#### R1. Concentrate on 2 segments only for the next 4 weeks (Effort: 0 — this is a subtraction, not addition | ROI: 2x pipeline velocity through focus)

**Primary segment: IM Platforms & SaaS** (CTO, VP Engineering, Head of Product)
- Highest deal values (API contracts scale with usage)
- Strongest social proof (if Modash, Captiv8 etc. are real customers)
- Best reply rate in flagship campaign (6.2%)
- 3 of 5 strong fits come from this segment

**Secondary segment: IM-First Agencies** (CEO, Founder, Head of IM)
- Lower deal values but faster sales cycles
- Good reply rates (2.07% for marketing agencies)
- Provides case studies and logos for platform sales

**Pause: PR firms** (0.20% reply rate, 0 meetings)
**Pause: Affiliate & Performance** (not enough data to evaluate, and stretches copy resources thin)
**Later: Brands Direct** (requires a different sales motion entirely)

#### R2. Launch a dedicated WANNA TALK enterprise sequence (Effort: 4 hours | ROI: 10-15% chance of landing 1 enterprise deal worth $50K-200K+)

These 19 leads need a separate approach:

**Week 1: Research & personalization**
- For each of the 19 leads, find 1 specific business reason they need creator data (product launch, feature gap, competitor move)
- Draft 19 personalized emails (not template-based)
- Identify secondary contacts at each company

**Week 2: Multi-channel outreach**
- Personalized email to primary contact
- LinkedIn connection request to primary + 1 secondary contact
- If possible, warm introduction through existing network

**Week 3: Follow-up**
- Second email with different angle
- LinkedIn message referencing the email

This is NOT mass outreach. This is targeted enterprise prospecting. 19 leads, each getting 3-4 personalized touches across 2 channels. Cost: ~4 hours of research + writing. Expected return: 2-3 meetings, 1 strong fit, potential for 1 deal worth 10-50x the cost of the entire outreach program to date.

#### R3. Validate social proof claims before scaling (Effort: 1 hour | ROI: avoid reputational damage that could cost $100K+ in lost deals)

If "Modash, Captiv8, Kolsquare, Influencity, Phyllo, Lefty" are NOT current paying customers, do NOT claim they "run on our API." Enterprise buyers will verify this. Options:

- If they are customers: keep and expand the social proof
- If they are free/trial users: change wording to "have integrated" or "have tested"
- If they are not customers at all: remove immediately and replace with actual customer names (Viral Nation, Whalar, Billion Dollar Boy)

The PR firms sequence is the worst offender — claiming IM platforms as PR firm clients is not just wrong positioning, it signals the sender doesn't understand the prospect's industry.

#### R4. Add pre-qualification to the booking process (Effort: 30 min | ROI: eliminate 2-3 wasted meetings per month = save 1.5 hours of founder/sales time)

BrandNation (MVP only, too small) and Yagency (can't afford) both took meeting slots. A simple pre-qualification step would filter these:

Before confirming any meeting, ask:
1. "How many creator lookups does your team run per month?" (filters for volume/budget fit)
2. "Are you evaluating API providers or exploring the concept?" (filters for timeline)

If the answer is <100 lookups/month or "just exploring," offer a recorded demo instead of a live call. This preserves the relationship without burning a live meeting slot.

---

## 4. OPERATIONS

### Diagnosis

**Process failures costing real money:**

1. **66 unlogged replies.** SmartLead shows 143 replies; Google Sheet has 77. That's 66 replies — many potentially warm leads — that exist only in SmartLead's inbox. Nobody is tracking them, nobody is responding to them, and they're aging out. At the current genuine-reply rate (~37% of all replies are actionable), that's ~24 potentially actionable leads that are rotting.

2. **No reply logging automation.** The current process is: Nastya manually copies replies from SmartLead inbox to Google Sheet. This is error-prone (proven by the 66-reply gap) and slow (delays response time). SmartLead has webhook/API capabilities that could push replies directly to the sheet.

3. **No OOO follow-up system.** 21 OOO responses with return dates. Zero calendar reminders set. These are people who implicitly acknowledged the email (auto-reply) and will be back at their desk — but nobody will re-contact them because there's no system for scheduling delayed follow-ups.

4. **Cross-campaign lead deduplication missing.** Luis Carrillo (Adsmurai) appears in BOTH campaign 2947684 AND 2990385. This means the same person is getting sequences from two campaigns simultaneously — a fast track to spam complaints and domain reputation damage. With 6 active campaigns and 6,287 total leads, there could be dozens of duplicates.

5. **SmartLead API limitations unaddressed.** `fetch_inbox_replies` returns 400 errors; `list_campaign_leads` returns N/A. This means the team can't programmatically extract reply data, forcing manual processes. These API issues have been identified but not escalated to SmartLead support.

6. **LinkedIn reply tracking is almost non-existent.** Only 7 of 20 LinkedIn replies are logged. That's 13 unlogged LinkedIn conversations. LinkedIn doesn't have API access for extraction — this is purely a manual logging discipline issue.

**Time audit (estimated weekly):**

| Task | Current Time | Optimized Time | Savings |
|------|-------------|----------------|---------|
| Manual reply logging (email) | 2 hours | 15 min (with automation) | 1.75 hours |
| Reply classification | 1 hour | 20 min (with scripts + categories) | 40 min |
| Response writing (no scripts) | 3 hours | 1 hour (with scripts) | 2 hours |
| OOO tracking (currently: 0) | 0 hours | 15 min (with reminders) | -15 min (new task) |
| LinkedIn reply logging | 30 min (incomplete) | 30 min (complete) | 0 |
| Lead dedup checking | 0 hours | 15 min (with dedup tool) | -15 min (new task) |
| **Total** | **6.5 hours** | **2.5 hours** | **4 hours/week** |

4 hours/week saved = 16 hours/month = 2 full working days that Nastya can redirect to actually selling.

### Recommendations

#### R1. Automate reply logging from SmartLead to Google Sheet (Effort: 4-6 hours one-time setup | ROI: save 7 hours/month + recover 66 lost replies)

**Option A (recommended): SmartLead webhook + Google Apps Script**
- SmartLead supports webhooks for new replies
- Set up a Google Apps Script that receives the webhook payload and writes it to the Google Sheet
- Columns auto-populated: lead name, email, company, campaign, reply text, timestamp
- SDR only needs to classify (1-click category selection)

**Option B (if webhook not available): Scheduled SmartLead API pull**
- Every 4 hours, a script calls `get_campaign_analytics` for each active campaign
- Compares against existing sheet entries
- Adds new replies automatically

**Option C (minimum viable): Daily manual sync with checklist**
- Create a daily checklist: open each active campaign in SmartLead, filter by "replied," compare against sheet
- Not ideal, but better than the current ad-hoc approach

Regardless of option chosen, the IMMEDIATE action is: go through SmartLead right now and log the 66 missing replies. At least 20-25 of these could be actionable leads that are 2-4 weeks old and need immediate attention.

#### R2. Set up OOO follow-up reminders for all 21 OOO leads (Effort: 45 min | ROI: 3-5 additional replies, 1-2 meetings)

For each OOO reply with a return date:
1. Open Google Calendar
2. Create a reminder for return date + 1 business day
3. Include the lead's name, company, and original reply in the reminder
4. When the reminder fires, send Script 9 (OOO follow-up from Copywriter R1)

If return dates are not specified in the OOO, use +2 weeks from the OOO date as default.

Estimated recovery: 21 OOO leads x 15% re-engagement rate = 3 replies, x 16.4% meeting rate = ~1 meeting. Cost: 45 minutes. This is a near-zero effort, high-probability win.

#### R3. Implement lead deduplication before campaign upload (Effort: 1 hour to set up | ROI: avoid spam complaints and protect domain reputation)

Before uploading any lead list to SmartLead:
1. Export all active campaign leads (6,287 across 6 campaigns)
2. Match on email address
3. Flag and remove duplicates from the new list

SmartLead does NOT deduplicate across campaigns automatically. This is the sender's responsibility. A single spam complaint from a duplicate-emailed lead can damage the sending domain's reputation and reduce deliverability for ALL campaigns.

Tool: a simple Google Sheet formula (COUNTIF across all campaign tabs) or a quick script.

#### R4. Fix SmartLead API issues by contacting support (Effort: 30 min to file ticket | ROI: enable all automation in R1)

The `fetch_inbox_replies` 400 error and `list_campaign_leads` N/A issue are blocking all automation. File a support ticket with:
- API endpoint called
- Exact error message
- Campaign IDs affected
- Expected vs. actual behavior

If SmartLead support is unresponsive, escalate through the account manager. If the API is genuinely broken, consider Zapier as a workaround (SmartLead has a Zapier integration that may expose reply data through a different path).

#### R5. Create a one-pager PDF (Effort: 2-3 hours | ROI: unblock 2+ leads who explicitly asked for it)

Georg (GameInfluencer) and Roland (styleranking media) both asked for "more information" or "a presentation." Without a one-pager, Nastya either sends nothing (loses the lead) or writes a custom email each time (wastes 30 min per lead).

The one-pager should include:
- What OnSocial does (3 sentences)
- Data coverage (450M+ profiles, 3 platforms)
- Key features (credibility scoring, demographics, fraud detection, overlap)
- Integration (API, white-label, <1 week)
- Social proof (actual customer logos)
- Contact info / calendar link

This is a sales enablement basic that is currently missing.

---

## 5. TEAM PRIORITY MATRIX

**Top 5 actions ranked by ROI (expected return / effort required):**

| Rank | Action | Owner | Effort | Expected Return | ROI Score |
|------|--------|-------|--------|-----------------|-----------|
| **1** | **Recover 66 unlogged replies + classify 5 misclassified warm leads** | Operations + SDR | 3 hours (one-time) | 5-10 warm leads recovered, 2-3 meetings, potential $50K-150K in pipeline | **Extreme** — zero cost, pure recovery of existing value |
| **2** | **Write 9 OnSocial reply scripts** | Copywriter | 3 hours (one-time) | Every future reply handled faster and better; prevents lead loss from ad-hoc responses; 10-15% improvement in reply-to-meeting rate | **Very High** — one-time effort, permanent improvement |
| **3** | **Launch WANNA TALK enterprise sequence (19 leads)** | Strategist + Copywriter | 4 hours (one-time) | 10-15% chance of 1 enterprise deal ($50K-200K+); expected value $5K-30K | **Very High** — tiny effort relative to potential deal sizes |
| **4** | **Pause PR firms, reallocate to IM platforms & SaaS** | Strategist | 30 min (settings change) | Stop wasting ~$150/week on 0-meeting segment; redirect to segment producing meetings at 6.2% reply rate | **High** — saves money immediately, no new work required |
| **5** | **Set up OOO follow-up reminders (21 leads)** | Operations | 45 min (one-time) | 3-5 re-engaged replies, 1-2 meetings from leads already warmed | **High** — minimal effort, leads are pre-qualified by having replied once |

**Honorable mentions (do next week):**
- Rewrite PR firms sequence (only after pausing current one and doing post-mortem)
- Automate reply logging (SmartLead webhook to Google Sheet)
- Create one-pager PDF
- Add pre-qualification step to meeting booking
- Implement cross-campaign lead deduplication
- Fix LinkedIn closing process (add calendar link to every warm reply)

---

## APPENDIX: Unit Economics Summary

| Metric | Current | Target (4 weeks) | Target (8 weeks) |
|--------|---------|-------------------|-------------------|
| Email reply rate | 1.53% | 2.5% (via better copy + segment focus) | 3.5% |
| Reply-to-meeting (genuine) | 16.4% | 20% (via scripts + faster response) | 25% |
| Meeting show rate | 55.6% | 70% (via reminders) | 75% |
| Cost per meeting | ~$161 | ~$100 | ~$80 |
| LinkedIn meeting rate | 0% | 5% of replies | 10% of replies |
| Meetings/week | ~1.5 | 3 | 4-5 |
| Strong fit rate | 5/5 held | Maintain | Maintain |
| Pipeline value/month | ~$250K (5 strong fits x $50K avg) | $400K | $600K |

**Bottom line:** The outreach machine is generating interest but leaking value at every handoff point — unlogged replies, missing scripts, no follow-up systems, wasted spend on wrong segments. The product-market fit signal is strong (5/5 strong fits from held meetings). The fix is not "do more outreach" — it is "capture the value from the outreach you're already doing."

Total investment to implement all Priority 1-5 recommendations: ~11 hours of work.
Expected return: 5-15 additional meetings over the next 4 weeks, plus 1 enterprise pipeline opportunity worth $50K-200K+.

That is the definition of high-leverage work.
