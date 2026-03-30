# Inxy Batch 2 Analysis — 210 Conversations (Cumulative: 310 of 781 real replies)

## Confirmed: 3 Offers, Period.

Every single outbound sequence pitches some combination of:
1. **Paygate** — "принимать криптоплатежи от клиентов с выводом в фиат" / "accept crypto → receive fiat"
2. **Payout** — "массовые выплаты подрядчикам/партнерам по API" / "mass payouts to contractors"
3. **OTC** — "OTC-обмен для крупных сумм" / "crypto↔fiat exchange for treasury"

No other offers exist. Campaign names like "Trading", "Gaming", "SaaS", "eSIM" are **target segments**, not products.

## New Finding: Leads Sometimes Ask for REVERSE of What's Offered

Several replies reveal demand for products Inxy MAY or MAY NOT offer:
- **On-ramp** (fiat→crypto): "У нас обратная задача - нам надо покупать крипту с расчётных счетов" (Роман @ DCP)
- **On-ramp**: "Интересен только он рамп. Цели выводить в фиат нет" (Artem @ Mighty)
- **Fiat-to-fiat via crypto rails**: "Здравствуйте, в обратном порядке работаете, принимать злотые/евро и выплачивать тезер?" (Oleksandr @ Fridly)
- **Fiat payouts to RU cards**: "Нас больше интересует перевод фиатных платежей в РФ на карты МИР" (Александр @ IBIK)
- **USD settlement to custody account**: "Нам необходим сеттлемент в USD на наш кастоди счет" (Владимир @ Aramid)

→ These are actually high-value leads with adjacent needs. Should be flagged as "Adjacent demand" not just "not interested".

## Refined Intent Taxonomy (Simplified from Batch 1)

### WARM (lead wants to engage)
| Intent | Pattern | Count (est. in all 781) |
|---|---|---|
| `send_info` | "Пришлите предложение" / "send one pager" / "share details" | ~80 |
| `schedule_call` | "Давайте созвонимся" / "here's my Calendly" / specific time slot | ~60 |
| `interested_vague` | "Да интересно" / "sounds interesting" / "Sure" | ~30 |
| `redirect` | "Talk to my colleague" / forward to CFO/COO | ~15 |

### QUESTIONS (needs clarity before deciding)
| Intent | Pattern | Count (est.) |
|---|---|---|
| `pricing` | "Какие комиссии?" / "what are your rates?" / "процент за конвертацию?" | ~15 |
| `how_it_works` | "How does it work?" / "как происходит процесс?" | ~10 |
| `compliance` | "Что про комплаенс?" / "гарантии сохранности?" / "лицензии?" | ~8 |
| `specific_use_case` | Lead describes their exact need and asks if Inxy fits | ~15 |
| `reverse_demand` | Wants on-ramp or fiat-to-fiat — adjacent to Inxy's offer | ~8 |

### OBJECTIONS (declines)
| Intent | Pattern | Count (est.) |
|---|---|---|
| `not_relevant` | "Не актуально" / "not relevant" / "not our business" | ~100 |
| `no_crypto` | "Мы с криптой не работаем" / "we don't deal in crypto" | ~40 |
| `not_now` | "Пока нет, но буду иметь ввиду" / "maybe later" | ~30 |
| `have_solution` | "У нас свой процессинг" / "we have our own infra" | ~15 |
| `regulatory` | "В Узбекистане только через локальные биржи" / "Polish regulator not friendly" | ~10 |
| `hard_no` | "Нет" / "не пишите мне" / "remove from list" | ~30 |
| `spam_complaint` | "I don't respond to mass mailing" / "how did you get my email?" | ~15 |

### NOISE (not real engagement)
| Intent | Pattern | Count |
|---|---|---|
| `empty` | No reply text at all | ~1966 |
| `auto_response` | "I have received your email" / ticket systems / Mixmax routing | ~20 |
| `bounce` | "Не удалось выполнить доставку" / delivery failures | ~10 |
| `gibberish` | Single letters, broken encoding, signatures only | ~10 |
| `wrong_person_ack` | "Redirected to Shikha Patel" / forwarding notices | ~10 |

## Which Offer the Reply Responds To

Detection logic (confirmed from 310 conversations):

1. **If reply mentions specific product keyword** → that offer
   - Paygate keywords: "прием платежей", "accept payments", "paygate", "payment gateway", "платежный шлюз"
   - Payout keywords: "выплаты", "payouts", "mass payments", "подрядчикам", "contractors"
   - OTC keywords: "OTC", "обмен", "exchange", "treasury", "конвертация", "ликвидность"

2. **If reply is to Step 1** (position of inbound = 1, outbound at 0) → **Paygate** (Step 1 always leads with Paygate)

3. **If reply is to Step 2** (position of inbound after second outbound) → **Payout** (Step 2 pivots to Payout)

4. **If campaign explicitly names a product offer approach** → that product
   - "Inxy - Luma" = OTC focused pitch
   - "Inxy - Monetization" = Payout focused pitch
   - Most others = Paygate first

5. **If ambiguous** → **General** (the lead is interested in INXY broadly)

## Campaign Segments (Confirmed, Simplified)

| Cluster | Campaigns | Reply count |
|---|---|---|
| Russian DMs | Russian DM's *, RUS DMs *, Rus Data * | ~1400 (largest) |
| Conference | ICE, Token2049, Money20/20, IGB, Ecom Berlin, Luma, SEP, London | ~300 |
| Crypto/Payments | Crypto Payments, PSP, FinTech, Merchants, Companies using/accepting crypto | ~200 |
| Trading/Investment | Trading *, Investment *, Tokenization * | ~250 |
| Creator/Content | Creator *, Creators *, Monetization * | ~100 |
| Gaming | Gaming *, GameFi, GameZ, iGaming, E-Sport, P2E, Crypto games | ~100 |
| SaaS/Tech | SaaS *, Cloud, eSIM, EdTech, Hosting *, Mobile, CpaaS | ~150 |
| Other niches | Affiliate, Luxury, Shopify, Digital Marketplace, Ticketing, VAS, EOR | ~150 |
| Cross-sell | ES *, Baxity *, INXY-ES, feature-* | ~100 |

## Patterns Stabilized

After 310 conversations, no new offer types or fundamentally new intent patterns are appearing. The taxonomy is stable. Remaining 471 real replies will follow these same patterns — I'm confident enough to proceed with the UI/architecture plan.
