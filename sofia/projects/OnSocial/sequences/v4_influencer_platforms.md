# Sequence v4: INFLUENCER PLATFORMS
> Segment: SaaS platforms building influencer/creator products
> Target: CTO, VP Engineering, Head of Product, Co-Founder
> Variable: {{social_proof}} - regional OnSocial clients
> A/B: Email 1 and Email 2 have two variants. Emails 3-5 are identical.

---

## Custom Variables (CSV columns)

| Variable | Example | Source |
|----------|---------|--------|
| {{first_name}} | John | Apollo |
| {{company_name}} | TRIBE | Apollo |
| {{social_proof}} | Whalar and Billion Dollar Boy | Region-based (see table) |

### Social proof by region

| Region | {{social_proof}} |
|--------|-----------------|
| UK | Whalar, InfluencerUK, LADbible, and Billion Dollar Boy |
| Germany | Zalando, Linkster, Intermate, and Gocomo |
| France | Kolsquare, Skeepers, Ykone, and Favikon |
| India | Phyllo, KlugKlug, Qoruz, and Tonic Worldwide |
| Australia | TRIBEGroup |
| Spain | SAMY Alliance |
| MENA | ArabyAds and Sociata |
| US/Canada | Modash, Captiv8, and Lefty |
| LATAM | Modash and Captiv8 |

---

## Email 1A - Build vs Buy (Day 0)

**Subject:** creator data - {{company_name}}

Hi {{first_name}},

Does {{company_name}} maintain its own creator data layer, or pull from a vendor?

Teams that switched to our API stopped maintaining scrapers entirely. Real-time data, all major platforms, one integration.

Worth a look?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}

---

## Email 1B - Cost of Inaction (Day 0)

**Subject:** engineering hours - {{company_name}}

Hi {{first_name}},

How much engineering time does {{company_name}} spend maintaining creator data? Scraping, deduplication, coverage gaps - it adds up fast.

Companies that moved to our API freed their eng team to work on product instead of data plumbing. Same coverage, zero maintenance.

Worth a look?

Kind regards,
Bhaskar Vishnu from OnSocial
Trusted by {{social_proof}}

---

## Email 2A - Case Study (Day 4)

**Subject:** Re: creator data - {{company_name}}

Hi {{first_name}}, one thing worth adding.

When Lefty plugged in our API, they freed 2 engineering roles that were just maintaining scrapers - and expanded from 3 to 5 social networks in a week.

If relevant for {{company_name}} - happy to walk through how they did it. 15 min.

Bhaskar

`50 words`

---

## Email 2B - API Playground (Day 4)

**Subject:** Re: creator data - {{company_name}}

Hi {{first_name}}, easier to show than tell.

Drop any creator handle in reply - I'll run it through our API and send you the raw output. Audience demographics, fraud score, engagement - all real-time.

No call needed. Just a handle.

Bhaskar

`42 words`

---

## Email 3 - Social Proof + Stat (Day 8)

**Subject:** Re: creator data - {{company_name}}

Hi {{first_name}},

One data point: platforms that build their own creator data layer spend 4-6 months before they have coverage beyond Instagram. We cover IG, TikTok, and YouTube from day one - 450M+ profiles.

{{social_proof}} started with the same decision. Happy to share what they learned.

Bhaskar

`50 words`

---

## Email 4 - Competitive Edge (Day 14)

**Subject:** Re: creator data - {{company_name}}

Hi {{first_name}},

Two things most creator data vendors won't tell you: their profiles update weekly (ours update every 24-48h), and they don't cover LATAM or MENA at city level (we have 25M+ LATAM creators alone).

If data freshness or regional coverage matters for {{company_name}} - worth comparing. Here's my calendar: [link]

Bhaskar

`55 words`

---

## Email 5 - Break-up (Day 21)

**Subject:** Re: creator data - {{company_name}}

Hi {{first_name}}, last one from me.

If creator data isn't on the roadmap - totally fine. But if I'm reaching the wrong person, who handles data infrastructure at {{company_name}}? Usually CTO or Head of Product.

Either way - good luck with what you're building.

Bhaskar

`44 words`

---

## Summary

| Step | Day | Variant A | Variant B | Test hypothesis |
|------|-----|-----------|-----------|-----------------|
| Email 1 | 0 | Build vs buy question | Cost of eng hours | Which pain resonates: control or cost? |
| Email 2 | 4 | Lefty case study (2 roles freed) | Drop a handle - live demo | Which CTA converts: story or action? |
| Email 3 | 8 | 4-6 months stat + social proof | - | New angle: time to coverage |
| Email 4 | 14 | Data freshness + regional coverage | - | Competitive differentiation |
| Email 5 | 21 | Break-up + redirect | - | Last chance + referral |

## SmartLead Setup

1. Create campaign: `INFLUENCER PLATFORMS v4`
2. Add sequence with 5 steps
3. Steps 1 and 2: add A/B variants (paste both versions)
4. Steps 3-5: single version
5. Timing: Day 0 → +4 → +4 → +6 → +7
6. Upload CSV with columns: email, first_name, company_name, social_proof
