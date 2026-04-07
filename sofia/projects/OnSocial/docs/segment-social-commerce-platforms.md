# Segment 4: Social Commerce Platforms

> Date: 2026-04-03
> Status: Proposed (not yet launched)
> Author: Sales Engineering team

---

## What It Is

Platforms where creators sell directly through content: live shopping, creator storefronts, "link in bio" monetization, shoppable video, UGC-to-commerce marketplaces. Not classic affiliate (link tracking) — these are **shopping experiences powered by creators**.

---

## Why We're Adding This Segment

### Signal 1: Our Own Data

Bazaarvoice, LTK, and ShopMy are already in our campaigns — they landed there accidentally through INFLUENCER_PLATFORMS and AFFILIATE_PERFORMANCE filters. This means our filters catch them, but they receive generic messaging instead of tailored copy.

| Company | Current Campaign | Status |
|---------|-----------------|--------|
| Bazaarvoice | INFLUENCER PLATFORMS #C | INPROGRESS (3 contacts) |
| LTK | IM agencies & SaaS_US&EU | 4 COMPLETED, 1 INPROGRESS |
| ShopMy | AFFILIATE & PERFORMANCE #C + flagship | Mixed (4 contacts) |
| Social Commerce Club | IM agencies & SaaS_US&EU | INPROGRESS |

### Signal 2: M&A Activity

| Deal | Value | Relevance |
|------|-------|-----------|
| Later acquired Mavely | $250M | Affiliate → creator commerce convergence |
| Publicis acquired Influential | $300M+ | Holding groups buying into creator commerce |
| H1 2025 total | 52 deals | Creator/influencer M&A at record pace |

### Signal 3: Market Convergence

- TikTok Shop connects 2M+ creators with brands in a single marketplace
- +46% higher conversion when affiliate + creator programs work together
- Live shopping GMV projected to exceed $50B in 2026 (China already proven, US/EU catching up)

### Signal 4: TAM Exhaustion in Core Segments

SaaS platforms (Segments 1+2) are nearly saturated — ~10K emails sent from a pool of ~3-6K companies. Social Commerce is an untapped adjacent pool with the same buyer profile.

### Signal 5: Underserved by Competitors

HypeAuditor, Modash, and CreatorIQ focus on classic IM platforms and agencies. Social commerce platforms are not targeted by any major creator data competitor.

---

## Example Companies

| Company | What They Do | Size |
|---------|-------------|------|
| Bazaarvoice | UGC, ratings & reviews, shoppable content | 1,000-5,000 |
| LTK (rewardStyle) | Creator storefronts, shoppable posts | 500-1,000 |
| ShopMy | Creator commerce, influencer product recommendations | 50-200 |
| Firework | Live shopping video for e-commerce | 200-500 |
| Bambuser | Live video commerce | 100-500 |
| CommentSold | Live selling for creators and brands | 50-200 |
| Whatnot | Live auction marketplace | 200-1,000 |
| TalkShopLive | Shoppable live video | 50-200 |
| Emplifi | Social commerce suite (UGC + shoppable) | 500-1,000 |
| Flip | Creator-led social commerce app | 50-200 |

---

## Why They Need Creator Data API (OnSocial)

| Use Case | Description |
|----------|-------------|
| **Creator verification** | Score creators at onboarding — real audience or inflated? |
| **Fraud detection** | Catch fake followers before they list on the marketplace |
| **Shoppable content analytics** | Link creator profile data (reach, engagement) to sales performance |
| **Brand safety for merchants** | Brands on the platform want creator analytics before collaborating |
| **Marketplace quality** | Higher-quality creators = higher GMV = better platform economics |

---

## Buyer Profile

| Role | Why They Buy |
|------|-------------|
| CTO / VP Engineering | API integration into product (same as Segment 1) |
| VP Product / Head of Product | New feature for marketplace — creator scoring, verification |
| Head of Marketplace / VP Commerce | Marketplace quality, seller/creator vetting |
| Head of Partnerships | Partner verification at scale |

---

## How It Differs from Existing Segments

| Segment | Core Business | OnSocial Use Case |
|---------|--------------|-------------------|
| **INFLUENCER_PLATFORMS** | Sell analytics/SaaS to marketers | Data powers their product |
| **AFFILIATE_PERFORMANCE** | Track links, commissions, payouts | Data verifies affiliate partners |
| **IM_FIRST_AGENCIES** | Run IM campaigns for clients | Data for campaign planning |
| **SOCIAL_COMMERCE** (new) | **Are the marketplace** where creators sell | Data for creator onboarding, fraud, quality |

The key difference: social commerce platforms don't just analyze creators — they **depend on creator quality for their own revenue**. Bad creators = bad GMV = platform dies.

---

## Launch Strategy

### Phase 1: Filters

Apollo filter set (validated 2026-04-07, see full version in `apollo-filters-v4.md` → Segment 4):

**Industry**
```
Computer Software, Internet, Marketing & Advertising,
Information Technology, E-commerce, Online Media, Retail
```

**Company Keywords — ANY of (21)**
```
live shopping platform, creator storefront, shoppable content,
social commerce marketplace, live video commerce, live selling platform,
creator monetization marketplace, UGC commerce, shoppable video,
creator-led commerce, social shopping platform,
live auction marketplace, shoppable livestream,
live commerce, video commerce, social selling platform,
creator marketplace, shoppable media, live stream shopping,
interactive video commerce, social commerce platform
```

**Excluded Keywords**
```
e-commerce platform, online store builder, shopping cart,
payment processing, logistics platform, dropshipping,
affiliate network, affiliate tracking,
video streaming platform, live streaming entertainment,
gaming streaming, sports streaming
+ standard exclusions (recruitment, healthcare, fintech, etc.)
```

**Company size:** 20–5,000 employees

**Location (20 countries)**
```
United States, United Kingdom, Germany, Netherlands, France,
Canada, Australia, Spain, Italy, Sweden, Denmark, Belgium,
India, Singapore, Japan, South Korea, United Arab Emirates,
Brazil, Mexico, Israel
```

**Titles (18)**
```
CTO, VP Engineering, VP of Engineering, Head of Engineering,
VP Product, Head of Product, Chief Product Officer,
Director of Engineering, Director of Product,
Head of Marketplace, VP Commerce, Director of Marketplace,
Head of Partnerships, VP Partnerships,
Co-Founder, Founder, CEO, COO
```

**Management Level:** c_suite, vp, director, owner, head, partner, founder

### Phase 2: Messaging Angle

**Pain:** "Your marketplace runs on creator trust. How do you verify who's real before they list?"

**Hook:** "Live shopping is growing 3x YoY — but so is creator fraud. One bad seller tanks buyer trust."

**Social proof:** "Teams like [peer companies] use our API to score 300M+ creator profiles in <50ms."

**CTA:** "Drop a creator handle — I'll run it through our verification API live."

### Phase 3: Dedicated Campaign

- Separate SmartLead campaign: `c-OnSocial_v5_SOCIAL_COMMERCE`
- 3-email sequence (Day 0/4/8) following v5 pattern
- Custom fields by geo (same 6 geo-clusters as IMAGENCY)

### TAM Estimate

| Metric | Estimate |
|--------|----------|
| Companies globally | 100-300 |
| Contacts (decision-makers) | 200-600 |
| Expected net-new after dedup | 150-400 |

Small but high-intent pool. Same buyer profile as our best-performing segment (INFLUENCER_PLATFORMS MENA+APAC: 8.7% meeting rate).

---

## Next Steps

- [ ] Build Apollo filters and validate with 25-company sample
- [ ] Estimate actual TAM via Apollo search
- [ ] Write dedicated v5 sequence with social commerce pain points
- [ ] Create SmartLead campaign
- [ ] Dedup against existing leads before upload
