# IMAGENCY Outreach — OnSocial April 2026

## Offer

OnSocial — B2B API providing creator/influencer data (audience demographics,
engagement analytics, fake follower detection, creator search) for Instagram,
TikTok, and YouTube.

Value for agencies: replace fragmented tools (Modash + HypeAuditor + manual
verification) with single API, automate creator vetting, speed up deal cycles.

## Target Audience

IM-first agencies — agencies where influencer/creator campaigns are THE primary
business, not a side service. Includes:

- Influencer-first agencies
- MCN (multi-channel networks)
- Creator talent management
- TikTok Shop agencies
- UGC production agencies
- Creator management companies

NOT this:
- Generic digital agencies ("full service" with SEO/PPC/PR/web design where influencers = one bullet)
- Brand-side marketing teams
- PR agencies without creator focus
- Modelling/casting agencies

Key test: **60%+ of visible offering (homepage, case studies, team titles) is about creator/influencer work**.

## Segment

Primary: `IMAGENCY` (IM-First Agencies)

## Employee Range

10-10,000

## Geo

US, India, UK, Germany, Canada, Brazil, France, Spain, UAE, Australia, Italy, Turkey, Netherlands, Poland, Mexico

## Target Roles

**Titles** (14):
- CEO, Founder, Co-Founder, Managing Director
- CTO, CPO, CMO, VP of Marketing
- Head of Product, Head of Partnerships, Head of Growth, Head of Influencer Marketing
- Director of Social Media
- Manager of Creator Partnerships

**Seniorities**: c_suite, vp, head, director, founder, partner, manager

**Reasoning**: Decision makers at influencer-first agencies who approve tool stack — founders drive budget, CPO/CTO approve API integration, Head of Influencer owns workflow.

## Campaign Settings

- Stop on reply: YES
- Link tracking: OFF
- Open tracking: OFF
- Plain text: YES (no HTML formatting)
- Daily limit: 35 per mailbox
- Send window: 9am-5pm recipient timezone, weekdays only

## Email Accounts

all OnSocial mailboxes

## Sequences

Generate fresh via `god_generate_sequence`.

5 steps, spacing 3-4-5-5-7 days (total ~24 days).

Angles per step:
1. Problem — fragmented creator vetting, hours wasted per pitch
2. Solution — OnSocial API: single source for audience + engagement + fraud detection
3. Social proof — agencies using OnSocial
4. Soft push — 15-min demo ask
5. Break-up — last email

## Previous Campaigns

Import all SmartLead campaigns with prefix `c-OnSocial_` as blacklist
(call `import_smartlead_campaigns` with rules={"prefixes": ["c-OnSocial_"]}).

Save as persistent rule via `set_campaign_rules` so future launches auto-import.

## Additional Manual Blacklist

Before launch, sync these 305 domains from main leadgen `project_blacklist`
(categories not covered by SmartLead campaign import):

- 83 OnSocial paid clients (never contact — active customers)
- 189 Known competitors (Modash, HypeAuditor, Captiv8, Lefty, etc.)
- 33 GPT-rejected domains (wrong industry, not influencer marketing)

Run `sync_onsocial_blacklist.py` before launching any OnSocial campaign via MCP.
