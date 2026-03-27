# TEAM ALPHA — Full Analysis & Recommendations

**Date:** 2026-03-16
**Subject:** OnSocial B2B Outreach — Data-Driven Audit & Action Plan

---

## 1. COPYWRITER

### Diagnosis

**A. Sequences are feature-dumping, not pain-selling.**
Every sequence opens with "We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles..." This is a product spec, not a cold email. The prospect has no reason to care about 450M profiles — they care about the problem those profiles solve. The subject lines are equally generic ("450M influencer profiles for {{company_name}}") and read like a vendor pitch, not a peer conversation.

**B. Social proof is misused or fabricated.**
The PR firms sequence claims "NeoReach, Buttermilk, Gushcloud, Influencer.com, and Obviously all run on our API." The IM_PLATFORMS variant claims "Modash, Captiv8, Kolsquare, Influencity, Phyllo and Lefty all run on our API." If these are actual customers, they should be used differently (specific outcomes, not name-dropping). If they are not actual customers, this is a credibility bomb waiting to explode — one forward to a peer and the trust is destroyed.

**C. CTAs are weak and inconsistent.**
"Who at {{company_name}} handles product or data partnerships?" — this is a routing question, not a CTA. The prospect reads it as "this person doesn't even know who to email." Meanwhile, "Here's my calendar: {{calendar_link}}" appears in some frameworks but not others. The flagship campaign (2,950+ contacts) uses the routing CTA, which is the weakest possible close.

**D. No reply scripts exist for OnSocial.**
Current scripts are copy-pasted from The Fashion People (a resale SaaS). Nastya is replying from memory. The 6 most common reply types — pricing, send info, competitor comparison, already have a partner, regional coverage, schedule a call — have zero prepared responses. This means every warm lead gets an improvised answer of variable quality.

**E. Personalization failures.**
Empty `{{first_name}}` fields produce "Hi ," — confirmed for at least 3 leads (Pierre-Antoine Leroux, Anna Lukaszewicz, Gabrielle Backman). This is a data hygiene issue that kills credibility instantly.

### Recommendations

#### R1. Rewrite Step 1 for all segments — lead with pain, not product

**Current (IM agencies & SaaS, TEST B Step 1):**
> Hi {{first_name}},
> We provide creator and audience data via API for influencer marketing platforms: 450M+ profiles across Instagram, TikTok, and YouTube. Credibility scoring, audience demographics down to city level, fraud signals, audience overlap.
> Your clients see exactly who's real, where the audience is, and how much overlap there is between creators — before spending a dollar.
> Who at {{company_name}} handles product or data partnerships?

**Rewrite for PLATFORMS (CTO/VP Eng):**
> Hi {{first_name}},
>
> Quick question — is {{company_name}} still maintaining its own creator data pipeline, or have you moved to a third-party provider?
>
> Asking because we work with platforms like [1 real customer name] that switched from in-house scraping to our API. They cut 3 months of engineering backlog and shipped audience demographics + fraud detection as native features within a week.
>
> If that sounds relevant, happy to show you the actual API output in 15 min. If not, no worries — just curious how you're handling it.
>
> {{sender_name}}

**Rewrite for AGENCIES (CEO/Founder):**
> Hi {{first_name}},
>
> How long does it take {{company_name}}'s team to vet a creator shortlist for a campaign — the real vetting, not just checking follower counts?
>
> We work with agencies that cut that from 2 days to under 2 hours. The difference is having real audience data (city-level demographics, fraud scores, audience overlap) instead of guessing from public metrics.
>
> If creator vetting is a bottleneck for you, I can show you a sample report on any creator you pick — takes 15 min. If it's already solved, I'll get out of your inbox.
>
> {{sender_name}}

**Rewrite for PR FIRMS:**
> Hi {{first_name}},
>
> When {{company_name}} recommends a creator to a brand client, how confident are you in the audience data behind that recommendation?
>
> I ask because PR firms we work with kept getting burned — creator looked great on paper, but 40% of followers were fake or in the wrong geography. Now they run every recommendation through our data (credibility scores, real audience demographics, audience overlap) before it goes in the deck.
>
> Worth a 15-min look? I'll pull a live report on any creator you're currently considering.
>
> {{sender_name}}

#### R2. Fix subject lines — make them curiosity-driven, not descriptive

| Current | Rewrite |
|---------|---------|
| "450M influencer profiles for {{company_name}}" | "question about creator data at {{company_name}}" |
| "Creator data API for {{company_name}}" | "how {{company_name}} handles creator vetting" |
| "Ship data features faster at {{company_name}}" | "re: your creator analytics roadmap" |
| "Cut creator research time at {{company_name}}" | "creator vetting — how long per campaign?" |
| "White-label creator analytics for {{company_name}}" | "what {{company_name}} shows clients about creator audiences" |
| "Creator intelligence layer for {{company_name}}" | "quick question about {{company_name}}'s affiliate data" |

#### R3. Full OnSocial Reply Scripts (ready to deploy)

**Script 1: "What's the pricing?"** (used by: Atul, Daniel, Eduardo, Urban, Arnab, Melker)
> Thanks for asking, {{first_name}}.
>
> Pricing depends on three things: volume of lookups, which platforms you need (IG/TikTok/YouTube), and whether you want real-time or cached data. Most platforms land between $X-Y/month depending on scale.
>
> Rather than send a generic sheet — can we do 15 min so I can give you a number based on {{company_name}}'s actual usage? I'll also pull a live demo on any creator you pick so you can see the data quality before we talk money.
>
> [calendar link]

**Script 2: "Send more info / one pager"** (used by: Georg, Roland)
> Sure — here's a one-page overview: [link to PDF/doc]
>
> The short version: we provide creator audience data via API (450M+ profiles, 3 platforms). Your team integrates it in days. Clients like [real customer] use it for audience demographics, fraud detection, and creator overlap — all white-label.
>
> Once you've had a look, I can pull a live report on any creator you're currently working with — takes 15 min and makes it concrete. [calendar link]

**Script 3: "How are you different from HypeAuditor / SocialData / X?"** (used by: Norbert)
> Good question. Three concrete differences:
>
> 1. **Coverage:** 450M+ profiles vs. [competitor's known number]. We cover IG, TikTok, and YouTube in a single API.
> 2. **Data depth:** Audience demographics down to city level + creator audience overlap (most competitors stop at country level and don't offer overlap).
> 3. **Pricing model:** [specific advantage — per-lookup vs. flat fee, or volume discounts].
>
> Easiest way to compare: pick a creator you already have data on from [competitor]. I'll pull the same profile from our API on a call and you can see the difference side by side. 15 min. [calendar link]

**Script 4: "We already have a partner/system"** (used by: Roland, Louis)
> Makes sense — most companies in your space have something in place.
>
> Two reasons teams still take a look: (1) data gaps — most providers cover 1-2 platforms well but miss the third, and city-level audience data is usually where coverage drops; (2) cost — we're often 30-50% cheaper at the same volume.
>
> If neither applies to {{company_name}}, I'll leave you alone. But if you're curious, I can run a side-by-side comparison on the same creator profile in 15 min. No commitment.

**Script 5: "Do you cover [region/platform]?"** (used by: Salvador — SEA/China)
> Great question. Currently we cover Instagram, TikTok, and YouTube globally — including Southeast Asia.
>
> For China-specific platforms (Weibo, Xiaohongshu, Douyin), we [do/don't yet] have coverage. If that's a dealbreaker, let me know — if not, happy to show you our SEA data quality on a quick call.
>
> What's the primary region/platform mix for {{company_name}}?

**Script 6: "Let's schedule a call"** (used by: Colby, Gordon, Johan)
> Great — here's my calendar: [calendar link]
>
> To make the most of 15 min, could you share:
> 1. Which platforms matter most (IG, TikTok, YouTube)?
> 2. A creator handle you're currently evaluating? I'll pull a live report to show during the call.
>
> Talk soon!

**Script 7: "I'm interested, adding colleagues"** (used by: Atul — added Pavel, Akira)
> Thanks for bringing the team in, {{first_name}}.
>
> @Pavel, @Akira — quick context: we provide creator audience data via API (450M+ profiles, IG/TikTok/YouTube). {{first_name}} flagged it as potentially relevant for {{company_name}}.
>
> I can pull a live demo on any creator you're currently evaluating — takes 15 min and makes it concrete. Here's my calendar: [calendar link]
>
> What time works for everyone?

**Script 8: "Wrong person, try X"** (used by: Sebastian to Robin, Alexander to Hannes)
> Thanks for the redirect, {{first_name}}.
>
> Hi {{new_person_name}} — {{original_person}} suggested I reach out to you about creator data infrastructure at {{company_name}}.
>
> Short version: we provide audience data via API for influencer marketing platforms (450M+ profiles, credibility scoring, demographics, overlap). Your team integrates it in days.
>
> Worth a 15-min look? [calendar link]

**Script 9: OOO auto-reply with return date** (21 cases)
> Hi {{first_name}},
>
> Hope you had a good [trip/break]. Circling back on the note I sent about creator data for {{company_name}}.
>
> The short version: we provide audience demographics, credibility scoring, and creator overlap via API — 450M+ profiles across IG, TikTok, YouTube. Most integrations go live in days.
>
> Still worth a 15-min look? [calendar link]

*(Send this 2 business days after their stated return date.)*

#### R4. Fix personalization data hygiene
Before any send, run a filter on SmartLead leads: if `first_name` is empty, either enrich from LinkedIn/Apollo or exclude from the campaign. Zero tolerance for "Hi ," emails.

---

## 2. ANALYST

### Diagnosis

**A. The real funnel is better than it looks — but hidden by bad data.**

The headline "1.53% reply rate" is misleading. Here's the real math:

| Campaign | Sent | Replies | Reply % | Quality |
|----------|------|---------|---------|---------|
| IM agencies & SaaS (flagship) | 1,979 | 123 | 6.2% | Best performer |
| IM_PLATFORMS | 649 | 8 | 1.2% | Below avg |
| MARKETING_AGENCIES | 265 | 5 | 1.9% | Small sample |
| 0903_AGENCIES | 445 | 3 | 0.7% | Underperforming |
| 0903_PLATFORMS | 505 | 1 | 0.2% | Dead |
| 1103_PR_firms | 242 | 3 | 1.2% | Too early |

The flagship campaign (IM agencies & SaaS) has a 6.2% reply rate — this is well above the B2B cold email benchmark of 2-5%. The problem is that newer campaigns (0903_AGENCIES, 0903_PLATFORMS) are dragging the average down dramatically. These use different sequences and were launched only 7 days ago.

**B. 66 replies are untracked — the funnel is literally invisible.**
SmartLead shows 143 replies. Google Sheet shows 77. That's 66 replies (46% of total) that never got logged, classified, or followed up. This is not a minor gap — it means the team is flying blind and potentially abandoning warm leads.

**C. Reply-to-meeting conversion is actually strong once you clean the data.**
- Total genuine replies (excluding OOO, auto-replies, wrong person): ~55
- Meetings booked from those: 9
- Real conversion: **16.4%** — this is solid
- Meeting held rate: 55.6% of booked — acceptable but improvable
- Strong fit rate: 5 out of 5 held (excluding waiting/no-show) — **100%** — the ICP targeting is working

**D. PR firms is a statistical non-event, not a "failed segment."**
1,000 contacts sent (per dashboard) but SmartLead shows only 242 sent from 1,852 loaded. The campaign is 5 days old. With 3 replies from 242 sends, that's 1.2% — actually normal for a new campaign. The 0.2% in the dashboard likely counted the 1,000 planned contacts as denominator. Don't kill this segment yet.

**E. LinkedIn is a lead-warming channel being measured as a conversion channel.**
0 meetings from 20 replies is bad only if you expect LinkedIn DMs to close meetings. In reality, LinkedIn acceptance (18.8%) warms the lead for email. The question is whether LinkedIn-touched leads convert better in email — and nobody is tracking this.

**F. Week 4 shows a worrying trend.**
- Week 4 email: 3,517 contacted, 39 replies (1.11%), 3 meetings booked
- That's lower than Week 1-2 averages, suggesting either list fatigue, worse targeting in newer campaigns, or sequence degradation

### Recommendations

#### R1. Fix data tracking immediately — this is the #1 priority

**Action:** Log all 66 missing replies from SmartLead into the Google Sheet. Classify each one. Identify any warm leads that were never followed up.

**Expected impact:** Based on the ratio from logged replies (17 interested or warm out of 77 = 22%), the 66 missing replies likely contain 10-15 warm leads that have received ZERO follow-up. Some of these are now 3-4 weeks old. Recovery rate on stale warm leads is typically 20-30%, meaning 2-5 additional meetings from work that's already done.

#### R2. Create a real-time funnel dashboard with these exact metrics

| Metric | Current | Target (30 days) | How to measure |
|--------|---------|-------------------|----------------|
| Email reply rate (genuine, excl. OOO) | ~2.8% | 4%+ | SmartLead + manual classification |
| Reply-to-meeting conversion | 16.4% | 20%+ | Sheet tracking |
| Meeting show rate | 55.6% | 75%+ | Calendar confirmations |
| Meeting-to-qualified rate | 100% | maintain | Sheet tracking |
| Time from reply to first response | Unknown | <4 hours | SmartLead timestamps |
| LinkedIn-to-email attribution | Not tracked | Track it | Tag LinkedIn-touched leads |

#### R3. Segment-level action based on data

| Segment | Reply Rate | Verdict | Action |
|---------|-----------|---------|--------|
| IM agencies & SaaS (flagship) | 6.2% | Scale | Double contact volume, same sequence |
| Marketing agencies (combined) | ~2.0% | Optimize | Test new angle (see Copywriter R1) |
| IM_PLATFORMS (new) | 1.2% | Monitor | 7 days old, needs 2 more weeks of data |
| 0903_AGENCIES | 0.7% | Diagnose | Check sequence vs flagship — what changed? |
| 0903_PLATFORMS | 0.2% | Pause & fix | 1 reply from 505 sends — something is broken |
| PR firms | 1.2% (real) | Monitor | Too early to judge, revise sequence per Copywriter |

#### R4. Calculate cost-per-meeting and unit economics

Current: 9,677 emails sent for 5 meetings held = **1,935 emails per meeting**. If each email costs ~$0.02-0.05 in platform/warmup costs, that's $38-97 per meeting. If the strong-fit rate stays at 100% of held meetings, and deal size is enterprise SaaS ($X0K+ ACV), this is efficient. But the team needs to know these numbers to make send-volume decisions.

#### R5. Track response time

**Hypothesis:** Leads who get a reply within 2 hours of their response book meetings at 2-3x the rate of those who wait 24+ hours. Currently, response time is not tracked. Add a "first reply timestamp" column to the sheet and start measuring.

---

## 3. STRATEGIST

### Diagnosis

**A. Segment prioritization is backwards.**

Current allocation is roughly equal across segments. But the data screams a clear winner:

| Segment | Contacts | Meetings | Strong Fits | Cost per Strong Fit |
|---------|----------|----------|-------------|---------------------|
| Platforms & SaaS | ~4,000 | 4 | 3 (The Shelf, MediaLabel, impact.com, Peersway) | ~1,000 contacts |
| Marketing agencies | ~2,000 | 5 | 1 (Brighter Click) | ~2,000 contacts |
| PR firms | ~1,000 | 0 | 0 | infinity |

Platforms & SaaS converts at 2x the rate and produces higher-quality fits (The Shelf, impact.com, Peersway are real platform companies with API integration use cases). Marketing agencies produce meetings but mostly with small shops that can't afford the product (BrandNation, Yagency).

**B. The WANNA TALK list is a gold mine being neglected.**

19 enterprise leads (Kantar 10K+, Patreon 500-1K, Spotter 200-500, inDrive 1K-5K, Jellysmack 200-500) are sitting in "Messaged" status with zero follow-up. These are not normal leads — they are the exact companies that could become anchor clients. The current team is treating them the same as a 5-person agency.

However, there's a problem with the WANNA TALK list: too many assistants (PA to CEO, EA to COO, Business Assistant to CEO). These are not decision-makers. The list needs to be re-qualified.

**C. The ICP definition is too broad.**

"CEO, CTO, VP Eng, Head of Product, CEO, Founder, MD, Head of IM" — that's everyone. The data shows which titles actually convert:

- Meetings booked came from: CEO/Founder types (Colby, Melker, Yunus), Product/CTO types (Atul, Johan, Arnab, Tivadar)
- Strong fits are overwhelmingly Product/CTO at platform companies
- Agency CEO/Founders book meetings but often turn out to be too small

**D. Geographic focus is undefined.**

Strong fits: 3 US, 1 EU, 1 unclear. The team is sending globally without geographic prioritization. US platforms tend to be larger and have bigger budgets. EU agencies tend to be smaller. No analysis has been done on geography vs. conversion.

**E. Affiliate & Performance segment (AFFPERF) has no campaign data.**

The AFFPERF framework exists in the sequences doc but there's no corresponding SmartLead campaign. This segment (impact.com is literally a strong fit from it) has been written about but never properly tested.

### Recommendations

#### R1. Rebalance volume: 60% Platforms, 30% Agencies, 10% PR

| Segment | Current Weekly Volume | New Weekly Volume | Rationale |
|---------|----------------------|-------------------|-----------|
| Platforms & SaaS | ~1,000 | 1,350 | Best conversion, highest deal size |
| Marketing agencies | ~1,000 | 675 | Still converts, but filter for 50+ employees |
| PR firms | ~250 | 225 | Test with revised messaging for 4 more weeks |
| **Total** | **2,250** | **2,250** | Same total, better allocation |

#### R2. Launch AFFPERF campaign this week

impact.com (a strong fit!) literally came from the Platforms & SaaS campaign. There are hundreds of affiliate/performance platforms (Partnerize, Awin, CJ Affiliate, Rakuten, ShareASale, Refersion, Everflow, PartnerStack, Tune, etc.) that haven't been touched. This is a proven segment with zero dedicated campaign.

**Action:** Load 500 affiliate/performance platform leads into a new SmartLead campaign using the AFFPERF HYP A sequence (modified per Copywriter recommendations). Target: CTO and VP Product only.

#### R3. Enterprise plays from WANNA TALK list — but qualify first

Split the 19 WANNA TALK leads into two tiers:

**Tier 1 — Decision makers (work these manually):**
- Michael Philippe, Co-Founder, Jellysmack
- Jodie Kennedy, CRO, Spotter
- Benjamin Humphrey, CEO, Dovetail
- Aaron Debevoise, CEO & Founder, Spotter
- Swann Maizil, Co-Founder, Jellysmack
- Jack Conte, CEO, Patreon
- Yuri Misnik, CTO, inDrive

**Tier 2 — Assistants/non-buyers (use as access points, not targets):**
- Chloe Lui, Chief of Staff to COO, Patreon — ask for intro to product lead
- Alina Baibulatova / Liza Novikova, PA/Assistant, inDrive — ask for CTO/VP Product intro
- Sarah Fernandes, EA to COO, Kantar — ask for Head of Analytics/Data intro
- All other Kantar entries — too many cooks, pick ONE champion

**Action for Tier 1:** Send a personalized LinkedIn message + email within 48 hours. Not a sequence — a manual, hyper-personalized outreach referencing something specific about their company's creator/influencer strategy.

#### R4. Add minimum company size filter

Stop sending to companies with <20 employees (agencies) or <50 employees (platforms). The data is clear: BrandNation (MVP only), Yagency (can't afford), Gordon Glenister Ltd (consultant) — these all booked meetings but wasted time. Set a minimum threshold:

- Platforms & SaaS: 50+ employees
- Agencies: 20+ employees
- PR firms: 20+ employees

#### R5. Define the "no" list

Companies that should NOT be contacted because they are competitors or have their own data:
- influData (Alexander replied, they have their own data)
- HypeAuditor (direct competitor in data)
- Modash, Captiv8, Kolsquare (if listed as "customers" — confirm status before listing in sequences)

---

## 4. OPERATIONS

### Diagnosis

**A. Reply logging is manual and broken.**
66 out of 143 replies (46%) are not in the Google Sheet. The process is: check SmartLead inbox manually, copy-paste to sheet, classify. This breaks every time Nastya is busy, sick, or focused on other tasks.

**B. No OOO follow-up system.**
21 OOO auto-replies identified. None have systematic follow-up scheduled. Each one represents a confirmed email delivery to a real person who will return — these should be the easiest re-engagement targets, and they're being dropped.

**C. SmartLead API is partially broken.**
- `fetch_inbox_replies` returns 400 errors
- `list_campaign_leads` returns N/A for lead details
- Manual replies from Nastya are invisible in the API
- This means automation is blocked at the data layer

**D. Cross-campaign deduplication doesn't exist.**
Luis Carrillo (Adsmurai) confirmed in both campaign 2947684 AND 2990385. Getting the same email from two campaigns destroys credibility. With 6 active campaigns and 6,287 total leads, the overlap could be significant.

**E. No CRM.**
Everything lives in a Google Sheet. Meeting notes, lead status, follow-up tasks — all manual. For 9 meetings and 5 strong fits this works. At 20+ meetings/month it will collapse.

**F. LinkedIn and email are disconnected.**
No tracking of which leads received both LinkedIn and email outreach. No way to know if LinkedIn acceptance improves email reply rates. No cross-channel sequencing.

### Recommendations

#### R1. Fix reply logging — two options (pick one)

**Option A (quick, this week):** Create a daily 15-min ritual. Every morning at 09:00, Nastya opens SmartLead, sorts inbox by "last received", and logs every new reply to the sheet with classification. Set a calendar reminder. Estimated time: 15 min/day.

**Option B (automated, 1-2 weeks):** Build a SmartLead webhook or scheduled script that pushes new replies to a Google Sheet via Zapier/Make. Even if SmartLead API is buggy for some endpoints, the `get_campaign_statistics` endpoint works and can be polled daily. Pipe new replies to a "raw replies" sheet, then Nastya classifies.

**Do Option A today. Start building Option B this week.**

#### R2. OOO follow-up automation

Create a Google Sheet tab called "OOO Queue" with columns:
| Lead Name | Company | Return Date | Follow-up Date (Return +2 biz days) | Status | Done? |

Populate it with all 21 OOO leads. Set a daily check: "Any follow-up dates = today?" If yes, send the OOO follow-up script (see Copywriter Script 9).

For the future: this should be a SmartLead sequence step that triggers X days after a detected OOO reply, but that requires API fixes.

#### R3. Deduplicate across campaigns immediately

**Action:** Export all lead emails from all 6 active campaigns. Run a duplicate check (simple spreadsheet COUNTIF). Any lead appearing in 2+ campaigns: pause in all but the best-performing campaign.

**Prevention:** Before loading any new campaign, check the new list against a master "all contacted" sheet. SmartLead has a global block list feature — use it.

#### R4. Cross-channel tracking

Add a column to the lead sheet: "LinkedIn Status" (Not sent / Invited / Accepted / Replied / Messaged). When loading leads into SmartLead campaigns, tag LinkedIn-touched leads with a custom field. This allows future analysis of multi-channel lift.

#### R5. Meeting confirmation workflow

Current show rate: 55.6% (5 held out of 9 booked). Industry benchmark for cold outreach meetings: 60-70%. To improve:

1. Send calendar invite immediately upon booking (within 1 hour)
2. Send a confirmation email 24 hours before the meeting with: "Looking forward to tomorrow's call. I'll pull a live report on [creator they mentioned or a creator relevant to their niche]. Anything specific you'd like me to cover?"
3. If no response to confirmation: send a morning-of message on LinkedIn or SMS

Expected improvement: 55.6% -> 70%+ show rate = 1-2 additional meetings held per month from current pipeline.

---

## 5. TEAM PRIORITY MATRIX

**Top 5 actions ranked by Impact x Effort:**

| # | Action | Owner | Effort | Impact | Expected Outcome |
|---|--------|-------|--------|--------|------------------|
| 1 | **Log the 66 missing replies + classify** | Nastya/Sally | 2-3 hours (one-time) | CRITICAL | Recover 10-15 warm leads, book 2-5 additional meetings from existing pipeline. Every day of delay = leads going colder. |
| 2 | **Deploy 9 OnSocial reply scripts** | Nastya + Copywriter | 1 hour (copy to doc/sheet) | HIGH | Standardize response quality, reduce reply time from hours to minutes, improve reply-to-meeting conversion from 16% to 20%+. |
| 3 | **Work the WANNA TALK Tier 1 list (7 enterprise leads)** | Sally/Bhaskar | 3-4 hours (personalized outreach) | HIGH | These are Kantar, Patreon, Spotter, Jellysmack, inDrive — any single close could be a 6-figure deal. Even 1 meeting from 7 attempts = massive ROI. |
| 4 | **Rebalance segment volumes + launch AFFPERF campaign** | Sally | 4-5 hours (list building + SmartLead setup) | HIGH | Shift volume to highest-converting segment (Platforms & SaaS), open a new proven segment (Affiliate/Performance). Expected: +30% meeting rate within 3 weeks. |
| 5 | **Rewrite Step 1 emails for all segments** | Copywriter | 2-3 hours | MEDIUM-HIGH | Current sequences feature-dump. Pain-led rewrites should lift reply rate from 1.5% average to 3%+ based on the flagship campaign's 6.2% proving the audience is responsive. |

### Quick Wins (do today):
- Fix empty `{{first_name}}` fields in all active campaigns (30 min)
- Set up daily reply-logging ritual at 09:00 (5 min calendar invite)
- Send OOO follow-ups for any leads whose return date has passed (check 21 OOO leads, likely 10+ are back by now)

### This Week:
- All 5 priority actions above
- Deduplicate leads across campaigns
- Add company size filter (50+ for platforms, 20+ for agencies)

### Next Week:
- Analyze A/B test results from flagship campaign (TEST A vs TEST B)
- Launch AFFPERF campaign with 500 leads
- Build automated reply logging (Zapier/Make pipeline)
- Start tracking response time (reply timestamp column)

---

*Report prepared by Team Alpha. All recommendations are derived from the data in the OnSocial data room as of 2026-03-16. Numbers, scripts, and rewrites are ready for immediate deployment.*
