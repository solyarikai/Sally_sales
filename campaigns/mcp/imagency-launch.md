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

Global (all countries — Apollo CSV had strongest signal in US, UK, DE, IN, BR, FR, ES, UAE, AU, IT, TR, NL)

## Target Roles (decision makers)

- CEO, Founder, Co-founder, Managing Director
- Head of Influencer / Head of Creator / Head of Talent
- VP Client Services / Director of Client Services
- Head of Strategy
- Account Director
- Head of Growth

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

Use existing OnSocial IMAGENCY sequence from SmartLead library
(if not present — generate fresh via `god_generate_sequence` with IMAGENCY context).

5-step sequence, spacing: 3-4-5-5-7 days between emails.

Key angles:
1. Problem — fragmented creator vetting costs agency hours per pitch
2. Solution — OnSocial API = single source for audience + engagement + fraud
3. Case study / social proof — agencies we work with (verify with Yarik)
4. Soft push — "15-min demo?"
5. Break-up — "last email, keeping door open"

## Exclusions

- Automatic: dedup against already-contacted in OnSocial (project_blacklist, 11k+ domains)
- Automatic: skip active campaigns (same_project_campaigns)
- Manual: no Sally clients, no GetSally LLC, no agencies that replied negatively before
