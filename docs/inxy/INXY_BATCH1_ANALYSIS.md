# Inxy Batch 1 Analysis — 100 Conversations with Real Data

## Key Finding: INXY Has 3 Core Offers (Not 15)

From analyzing actual outbound sequences, INXY pitches **exactly 3 products**:

### 1. Paygate (Crypto Payment Acceptance)
- "Accept crypto from customers → receive EUR/USD on your bank account"
- "Your client pays in crypto → you get fiat on your bank account, fully legal"
- Pitched in Step 1 of Russian DMs, Step 1 of most English campaigns
- Commission: from 0.4%, "less than 1% all-in"
- This is the PRIMARY offer in almost every campaign

### 2. Payout (Mass Crypto Payouts)
- "Mass payouts to contractors/partners abroad via API"
- "Automate mass crypto distributions"
- Pitched as Step 2 in Russian DM sequences ("Пишу коротко с другим вопросом: насколько актуальна задача выплат подрядчикам?")
- Positioned as alternative to SWIFT/Wise (3-5% fees, multi-day delays)
- Some campaigns lead with this: Monetization, Creator Payouts, F&P Platforms

### 3. OTC (Over-The-Counter Crypto-Fiat Exchange)
- "OTC exchange for large sums" / "crypto-fiat settlement for treasury"
- "Crypto↔fiat exchange and treasury management"
- Mentioned in Step 1 alongside Paygate as a tertiary service
- Some campaigns lead with this: Luma, Trading
- Positioned for large-volume treasury operations

### Sequence Pattern (Russian DMs — largest campaign)
- **Step 1**: Paygate pitch ("принимать криптоплатежи от клиентов с выводом в фиат")
  - Also mentions Payout + OTC briefly at the end
- **Step 2**: Payout pivot ("задача выплат подрядчикам или партнерам за рубежом")
  - Switches angle in case Paygate wasn't relevant
- **Step 3**: Soft close ("не буду больше отвлекать, если встанет вопрос — напишите")

### Sequence Pattern (English campaigns)
- **Step 1**: Paygate/Payout (varies by campaign, often tailored to segment)
- **Step 2**: Follow-up, mentions all 3 offers ("crypto acceptance, mass payouts, OTC")
- **Step 3**: Last chance close

---

## Reply Intent Taxonomy (From Real Data)

### WARM — Lead wants to engage

| Intent | Example | Count in Batch 1 |
|--------|---------|-------------------|
| **Send info** | "Пришлите предложение с ценами" / "Please share the one pager" | ~15 |
| **Schedule call** | "Давайте созвонимся" / "Here is my Calendly" | ~12 |
| **Explore synergy** | "Happy to explore potential synergies" | ~5 |
| **Interested (vague)** | "Да, интересно" / "Sounds interesting" | ~8 |
| **Redirect to colleague** | "Talk to my colleague X" / "Направьте нашему CFO" | ~3 |
| **Interested in specific offer** | "Что касается выплат — уже более интересно" (interested in Payout specifically) | ~4 |

### QUESTIONS — Lead needs more info before deciding

| Intent | Example | Count |
|--------|---------|-------|
| **Pricing** | "Can you share rates?" / "Комиссия от 0.4% — а что ещё?" | ~3 |
| **How it works** | "How does it work?" / "Как происходит работа с НДС?" | ~3 |
| **Compliance/Legal** | "Что про комплаенс в ЕС?" / "Polish supervisor is not crypto friendly" | ~2 |
| **Integration/Technical** | "Can you show me a setup where your gateway is used like Stripe?" | ~1 |

### OBJECTIONS — Lead declines

| Intent | Example | Count |
|--------|---------|-------|
| **Not relevant / don't use crypto** | "Мы с криптой не работаем" / "We don't deal in crypto" | ~12 |
| **Not now / maybe later** | "Пока не актуально" / "Not interested for now" | ~8 |
| **Already have solution** | "We have our own crypto infrastructure" | ~3 |
| **Regulatory/Geo block** | "В Узбекистане крипто только через локальные биржи" / "Polish regulator not crypto friendly" | ~3 |
| **Generic rejection** | "Нет" / "Not interested" | ~5 |
| **Hostile/Spam complaint** | "I don't respond to mass mailing" / "перестаньте писать" | ~3 |

### NOISE — Not real human engagement

| Intent | Example | Count |
|--------|---------|-------|
| **Bounce/Delivery failure** | "Не удалось выполнить доставку" | ~2 |
| **Auto-response** | "I have received your email and will get back to you" | ~2 |
| **Acknowledgment only** | "Thanks for connecting" (no substance) | ~3 |
| **Gibberish** | "v" / empty | ~1 |
| **Wrong person forwarding** | "Your email has been redirected to..." | ~2 |

---

## Which Offer Did the Lead Respond To?

Critical insight: the **campaign name does NOT tell you the offer**. The campaign name tells you the **segment** (Trading, Gaming, SaaS, etc.), but the outbound sequence always pitches the same 3 products.

However, the **reply text** often reveals which offer resonated:

| Reply signal | Offer responded to |
|---|---|
| "принимать платежи" / "accept payments" / "paygate" | **Paygate** |
| "выплаты подрядчикам" / "payouts" / "mass payments" | **Payout** |
| "обмен" / "OTC" / "treasury" / "exchange" / "large sums" | **OTC** |
| "да интересно" (replied to Step 1) | **Paygate** (Step 1 is always Paygate) |
| "выплаты — уже более интересно" (replied to Step 2) | **Payout** (Step 2 is the Payout pivot) |
| Generic "send info" without specifics | **General** (interested in INXY, offer TBD) |

### For classification, we need:
1. Which step triggered the reply (position of last outbound before first inbound)
2. Keywords in reply text matching specific product
3. If ambiguous → "General" (the meeting will clarify)

---

## Campaign Segments (Not Offers!)

The campaigns target different **market segments**, all getting pitched the same 3 INXY products:

| Segment cluster | Example campaigns | Notes |
|---|---|---|
| **General (Russian DMs)** | Russian DM's, RUS DMs [ES], Rus Data | Broad outreach to CIS businesses |
| **Payments/PSP/FinTech** | PSP, FinTech (Paygate), Merchants, Crypto Payments | Companies already in payments space |
| **Conference leads** | ICE collegue, Token2049, Money20/20, IGB, Ecom Berlin, Luma, SEP, London Tech Week | Event follow-ups |
| **Gaming/iGaming** | Gaming Marketplaces, Gaming Platform, iGaming, GameFi, GameZ, E-Sport, P2E | Game companies needing crypto |
| **Creator/Content** | Creator Economy, Creator Payouts, Creators Platform, Monetization | Content platforms, royalty payouts |
| **Trading/Investment** | Trading, Investment, Tokenization | Crypto-native firms |
| **E-commerce** | Shopify, Digital Marketplace, Ecom Berlin | Online merchants |
| **SaaS/Tech** | SaaS, Cloud, CpaaS, Mobile, eSIM, EdTech, Hosting | Tech companies |
| **Affiliate** | Affiliate, Affiliate Networks | Affiliate marketers |
| **Luxury/Niche** | Luxury, Luxury Real Estate, Ticketing, VAS | Niche verticals |
| **Cross-sell (EasyStaff)** | ES *, Baxity lookalike, INXY-ES | Cross-sell from EasyStaff leads |

---

## What's Still Needed (Batch 2+)

1. **"Other" category (2016 replies!)** — this is the largest bucket. Need to sample heavily from "other" to understand what's in there. Many are likely noise (bounces, auto-responses, acknowledgments) that should be reclassified.
2. **More LinkedIn conversations** — only 40 LinkedIn replies, need to see the DM offer structure
3. **Approval_status distribution** — how many warm replies were actually acted on?
4. **Time patterns** — are certain campaigns/segments producing better response rates?
