-- FIX: Remove fake interests and generic payment-gateway from scheduling-only replies
-- These leads said NOTHING specific about their financial needs

-- Pure scheduling / "send me info" / "let's call" — NO financial content to extract
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id IN (
  22160, -- "book a call" — calendly link only
  22180, -- "can we speak about partnership?" — no financial detail
  22241, -- scheduling with CEO/CTO — no product mentioned
  22294, -- "11 march at 14. Works?" — scheduling only
  22298, -- scheduling slots — no financial detail
  22295, -- "Понедельник в 10.00?" — scheduling
  22314, -- "Доброе утро. На след неделе" — scheduling
  22344, -- "давайте на следующей неделе" — scheduling
  22390, -- "напишите в tg" — redirect, no financial detail
  22412, -- "Feb24 16:00 CET?" — scheduling
  22442, -- "17.02 подходит" — scheduling
  22471, -- encoded scheduling text
  22525, -- "давай созвон, в телеге" — scheduling
  22542, -- "мы можем созвониться" — scheduling
  22645, -- "Friday works best" — scheduling
  22129, -- "Can we reconnect April 14?" — scheduling
  22134, -- "прислать one-pager" — request only
  22139, -- "Пришлите one pager" — request only
  22148, -- "Да, пришлите" — request only
  22149, -- calendly link — scheduling
  22167, -- "6pm Monday" — scheduling
  22171, -- "Sure exploratory call" — scheduling
  22176, -- "send one pager + linkedin" — request only
  22197, -- "Monday?" — scheduling
  22206, -- "соберем вопросы" — vague
  22208, -- "Пришлите тарифы" — request only
  22246, -- "Присылайте предложение" — request only
  22247, -- "надо проговорить детали" — vague
  22254, -- "высылай телегу" — scheduling
  22261, -- "присылайте условия" — request only
  22274, -- "send over information" — request only
  22276, -- "send one-pager" — request only
  22278, -- "go ahead, one pager" — request only
  22286, -- "да, было бы отлично" — vague
  22290, -- "календарь приглашение" — scheduling
  22293, -- "Пришлите материал" — request only
  22299, -- "Давайте запланируем" — scheduling
  22309, -- "предложите время" — scheduling
  22316, -- "пишите в телегу" — scheduling
  22317, -- "330pm CET" — scheduling
  22321, -- "send rates" — request only
  22324, -- "send more details" — request only
  22330, -- "пришлите посмотрю" — request only
  22353, -- "пришлите one-pager" — request only
  22370, -- "see pre info" — vague
  22392, -- "пришлите подробную информацию" — request only
  22407, -- "Пришлите" — request only
  22410, -- "отправьте one-pager" — request only
  22419, -- "Присылайте" — request only
  22454, -- "Жду на Zoom" — scheduling
  22490, -- "отправьте оффер" — request only
  22521, -- "связаться в мессенджере?" — redirect
  22557, -- "давайте на пятницу" — scheduling
  22610, -- "done" — confirmation
  22630, -- "suggest slot" — scheduling
  22643, -- "which meeting?" — confused
  22651, -- "find time here" — scheduling
  22656, -- "look forward to connecting" — vague
  22658, -- "4pm dubai time" — scheduling
  22685, -- "chat next week" — scheduling
  22687, -- "see you then" — scheduling
  22695, -- "interested to hear more" — vague
  22746, -- "Friday 5PM" — scheduling
  22817, -- "hop on call Nov 10-11" — scheduling
  22880, -- "send cal link" — scheduling
  22911, -- "rescheduled for Friday" — scheduling
  23454, -- "уточню у партнеров" — checking
  23496, -- "looking forward to meeting Pavel" — scheduling
  23520, -- "book meeting" — scheduling
  23658, -- "select time" — scheduling
  23886, -- "Изучим и вернемся" — will review
  23965  -- "вернемся к вашему предложению" — scheduling
);

-- ======================================================================
-- NOW: Enrich replies that DO have specific financial content
-- ======================================================================

-- 22357: Rainer Seyer, countr.de — POS terminals, white-label crypto, EU GDPR, fees <1%
UPDATE reply_analysis SET
  interests = 'POS terminal company needs white-label crypto payment integration for retail terminals across Europe. Requires EU server location (Frankfurt) for GDPR compliance. Commission under 1%. Exploring whether to offer crypto acceptance to their merchant clients via API.',
  tags = '{"white-label","crypto-to-fiat","pos-terminal","api-integration"}',
  geo_tags = '{"europe"}'
WHERE id = 22357;

-- 22358: Diamantis, MobiWeb — crypto acceptance + mass payouts + OTC
UPDATE reply_analysis SET
  interests = 'MobiWeb evaluating full crypto infrastructure stack: payment acceptance from customers, mass payout automation to partners, and OTC crypto-fiat exchange for treasury. ICE conference follow-up.',
  tags = '{"crypto-to-fiat","mass-disbursements","fx-conversion"}'
WHERE id = 22358;

-- 22434: Pay employee in Belarus via crypto → fiat on Belarus card
UPDATE reply_analysis SET
  interests = 'Needs to pay employee in Belarus — wants to send crypto and have fiat delivered to Belarusian bank card. Specific corridor: crypto→fiat settlement to Belarus banking system.',
  tags = '{"crypto-to-fiat","contractor-payouts"}',
  geo_tags = '{"belarus"}'
WHERE id = 22434;

-- 22437: QZen Family Office
UPDATE reply_analysis SET
  interests = 'Family office evaluating crypto payment infrastructure for treasury and investment operations.',
  tags = '{"treasury-management","fx-conversion"}'
WHERE id = 22437;

-- 22440: Tourism product, European market, crypto payments in 2026
UPDATE reply_analysis SET
  interests = 'Planning crypto payment integration for tourism product targeting European market in 2026. Needs: pricing/commissions, supported cryptocurrencies, fiat withdrawal options, API integration requirements. Actively comparing payment providers.',
  tags = '{"crypto-to-fiat","api-integration","multi-currency"}',
  geo_tags = '{"europe"}'
WHERE id = 22440;

-- 22466: Both acceptance AND payouts
UPDATE reply_analysis SET
  interests = 'Needs BOTH directions: crypto payment acceptance from customers (paygate) AND crypto payouts to partners/contractors. Dual-direction crypto-fiat infrastructure.',
  tags = '{"crypto-to-fiat","mass-disbursements"}'
WHERE id = 22466;

-- 22473: Regolith — USDT/USDC acceptance, networks, conversion fees
UPDATE reply_analysis SET
  interests = 'Regolith confirms crypto payments are relevant. Specific questions: commission on USDT and USDC acceptance, which blockchain networks supported, conversion fee from crypto to fiat. Comparing against current conditions.',
  tags = '{"stablecoin-settlement","crypto-to-fiat"}',
  offer_responded_to = 'paygate'
WHERE id = 22473;

-- 22111: Paul Goldfinch, Start Investments — wants to understand how it works
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id = 22111;

-- 22114: "а клиент только в крипте может платить?" — asking if ONLY crypto or also fiat
UPDATE reply_analysis SET
  interests = 'Asking whether customers can ONLY pay in crypto or also in fiat. Evaluating whether crypto payment acceptance fits their customer base.',
  tags = '{"crypto-to-fiat"}'
WHERE id = 22114;

-- 22115/22116: Finsupport — both options (acceptance + payouts)
UPDATE reply_analysis SET
  interests = 'Financial services company (Finsupport, Tallinn/Oslo) exploring both crypto payment acceptance and mass payout solutions for their clients.',
  tags = '{"crypto-to-fiat","mass-disbursements"}'
WHERE id = 22115;
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id = 22116; -- duplicate follow-up

-- 22124: Kea — banking + crypto for high-risk
UPDATE reply_analysis SET
  interests = 'Kea provides banking and crypto solutions to companies in high-risk industries. Exploring collaboration or white-label partnership with INXY.',
  tags = '{"white-label","fintech"}'
WHERE id = 22124;

-- 22144: HK+USA companies, Stripe/PayPal integrated, payouts to HK
UPDATE reply_analysis SET
  interests = 'Website in final development stage with Stripe and PayPal already integrated — ready to add crypto payment acceptance. Companies registered in Hong Kong and USA. All payouts through Hong Kong entity. Additional fintech product ideas to discuss.',
  tags = '{"crypto-to-fiat","api-integration"}',
  geo_tags = '{"hong-kong"}'
WHERE id = 22144;

-- 22146: Has own crypto infra, looking for competitive corridors + fiat banking
UPDATE reply_analysis SET
  interests = 'Already has crypto infrastructure and liquidity providers. Looking for more competitive payment corridors where INXY can beat current rates. Also offers full banking infrastructure for fiat custody worldwide — proposing go-to-market partnership.',
  tags = '{"have-solution","fx-conversion","multi-currency","treasury-management"}'
WHERE id = 22146;

-- 22168: Specifically interested in PAYOUTS
UPDATE reply_analysis SET
  interests = 'Specifically interested in crypto payout solutions for umowa.io. Wants detailed information about mass payout capabilities — sending payments to contractors/partners.',
  tags = '{"mass-disbursements","contractor-payouts"}',
  offer_responded_to = 'payout'
WHERE id = 22168;

-- 22195: Not POSMate but another business
UPDATE reply_analysis SET
  interests = 'Not relevant for POSMate (POS product) but has a separate business where crypto payments are applicable. Redirecting to Telegram for discussion.',
  tags = '{}'
WHERE id = 22195;

-- 22214: Fortris — crypto treasury platform
UPDATE reply_analysis SET
  interests = 'Fortris (crypto treasury and payout infrastructure) — Biz Dev exploring mutual opportunities after ICE conference. Either competitor or potential partnership for treasury management solutions.',
  tags = '{"treasury-management","mass-disbursements","fintech"}'
WHERE id = 22214;

-- 22244: BoardMaps — payouts FROM Russia TO foreign contractors, VAT
UPDATE reply_analysis SET
  interests = 'BoardMaps does NOT need payment acceptance. Specifically interested in payouts FROM Russia TO foreign partners and contractors via crypto. Key concern: how VAT is handled on cross-border crypto payouts from Russian entity.',
  tags = '{"contractor-payouts","mass-disbursements","crypto-to-fiat"}',
  geo_tags = '{"russia"}'
WHERE id = 22244;

-- 22245: Shopify merchant
UPDATE reply_analysis SET
  interests = 'Shopify-based e-commerce merchant evaluating crypto payment acceptance. Launching product soon, needs overview of integration approach.',
  tags = '{"crypto-to-fiat","ecommerce","api-integration"}'
WHERE id = 22245;

-- 22279: TinyAdz — payout to contractors abroad as SWIFT/Wise alternative
UPDATE reply_analysis SET
  interests = 'Thread discusses replacing SWIFT/Wise for foreign contractor payouts — 3-5% commission and multi-day delays. INXY positioned as faster and cheaper mass payout via API with full compliance.',
  tags = '{"contractor-payouts","mass-disbursements","swift-settlement"}'
WHERE id = 22279;

-- 22288: DACO project logistics — BOTH acceptance AND payouts
UPDATE reply_analysis SET
  interests = 'Logistics company (DACO, Germany) has both use cases: crypto payment acceptance from customers AND payouts to partners/suppliers. Needs dual-direction crypto-fiat infrastructure.',
  tags = '{"crypto-to-fiat","mass-disbursements"}'
WHERE id = 22288;

-- 22292: Get Inn — specifically payment acceptance
UPDATE reply_analysis SET
  interests = 'Get Inn (hotel/travel booking platform) specifically interested in crypto payment acceptance for hospitality bookings. Will review materials and revert.',
  tags = '{"crypto-to-fiat"}',
  offer_responded_to = 'paygate'
WHERE id = 22292;

-- 22315: US company, all operations through US entity
UPDATE reply_analysis SET
  interests = 'Company registered in USA, all operations through US entity. Interested in crypto payment infrastructure compatible with US business structure.',
  tags = '{}'
WHERE id = 22315;

-- 22319: UK company, UBO from Belarus with EU residency
UPDATE reply_analysis SET
  interests = 'UK-registered company, sole UBO from Belarus with EU residency permit. Interested in crypto payment infrastructure — compliance/jurisdictional context is important.',
  tags = '{"kyc-kyb"}'
WHERE id = 22319;

-- 22323: Trust Payments — offering THEIR services
UPDATE reply_analysis SET
  interests = 'Trust Payments offering their payment processing services TO INXY — reverse pitch, potential partner not customer.',
  tags = '{"fintech"}'
WHERE id = 22323;

-- 22464: Syntes/DigitalSync US — international payments for US companies
UPDATE reply_analysis SET
  interests = 'US-based company (Syntes/DigitalSync) needs effective international payment solutions via crypto for US companies. Wants English-language materials to share with partners for joint evaluation.',
  tags = '{"fx-conversion","crypto-to-fiat"}'
WHERE id = 22464;

-- 22590: Already uses crypto corporate cards + OTC MM desks
UPDATE reply_analysis SET
  interests = 'Already uses multiple crypto-fiat payment methods: crypto corporate cards, OTC market maker desks, and others. Exploring whether INXY offers better rates or capabilities as additional/alternative OTC solution.',
  tags = '{"have-solution","fx-conversion","crypto-to-fiat"}'
WHERE id = 22590;

-- 22608: ThinkTradeFinance — white-label for trade finance clients
UPDATE reply_analysis SET
  interests = 'Trade finance platform wants to RESELL INXY services to their clients. Interested in white-label crypto-fiat exchange infrastructure for cross-border trade finance settlements.',
  tags = '{"white-label","fx-conversion","crypto-to-fiat"}'
WHERE id = 22608;

-- 22644: UAE bank settlement — detailed product questions
UPDATE reply_analysis SET
  interests = 'Payment gateway company needs crypto-to-fiat settlement to UAE bank account. Detailed product questions: supported currencies, settlement flows, crypto-to-fiat conversion mechanism, fee structure, API integration approach, onboarding process. They receive payments on behalf of merchants.',
  tags = '{"crypto-to-fiat","api-integration","fx-conversion"}',
  geo_tags = '{"uae"}'
WHERE id = 22644;

-- 22694: TiltPayments US & Caribbean
UPDATE reply_analysis SET interests = NULL, tags = '{"fintech"}' WHERE id = 22694;

-- 22765: AnyCoin.cz — asking what paygate means
UPDATE reply_analysis SET
  interests = 'Crypto exchange platform (Anycoin.cz) asking what exactly "crypto payment acceptance" means — whether it is fiat transfer for crypto purchase. Needs product clarification before evaluating.',
  tags = '{"crypto-to-fiat"}'
WHERE id = 22765;

-- 22928: Bedford Pay EMI — partnership/revshare
UPDATE reply_analysis SET
  interests = 'UK FCA-regulated EMI (Bedford Pay, FCA Reference 900933) exploring crypto payment partnership or revenue share model. Open to both using INXY solutions and offering their own EMI capabilities.',
  tags = '{"white-label","fintech"}'
WHERE id = 22928;

-- 23886: Sub-1% commission interest
UPDATE reply_analysis SET
  interests = 'Interested in crypto payment acceptance with commission under 1% and direct fiat withdrawal to company account. Will study materials and return if interested.',
  tags = '{"crypto-to-fiat"}'
WHERE id = 23886;

-- 22554: Adjacent demand — buy crypto from bank accounts, send to contractors
UPDATE reply_analysis SET
  interests = 'Reverse need from what INXY pitches: wants to BUY crypto from company bank accounts (fiat→crypto on-ramp) and TRANSFER crypto to contractors/performers. Needs compliant fiat-to-crypto conversion for corporate accounts.',
  tags = '{"on-ramp","fiat-to-crypto","contractor-payouts"}'
WHERE id = 22554;

-- Additional specific replies from batch 3 that need enrichment:

-- 22723: Altpaynet Philippines — central bank licensed, wants INXY tech+rails
UPDATE reply_analysis SET
  interests = 'Philippine central bank-licensed payment company (Altpaynet, Banko Central ng Pilipinas license) wants to integrate INXY payment technologies and crypto rails for their customers. Exploring technology partnership, white-label, and collaboration on payment infrastructure.',
  tags = '{"white-label","api-integration","fintech"}',
  geo_tags = '{"philippines"}'
WHERE id = 22723;

-- 22747: Spanish — fund for SME credit via crypto
UPDATE reply_analysis SET
  interests = 'Exploring creation of a fund to finance SME credit operations through crypto. Potential DeFi lending or crypto-backed credit for small/medium enterprises.',
  tags = '{"treasury-management","fintech"}'
WHERE id = 22747;

-- 22769: Settlement + Payment + Collection + White-Label
UPDATE reply_analysis SET
  interests = 'Looking for comprehensive Settlement, Payment, and Collection partner PLUS White-Label Platform provider. Wants overview of all INXY services to evaluate full partnership.',
  tags = '{"white-label","crypto-to-fiat","api-integration"}'
WHERE id = 22769;

-- 22855: Mass payouts to artists/collaborators
UPDATE reply_analysis SET
  interests = 'Exploring crypto-based mass payouts to network of artists and collaborators. Current payout process likely involves cross-border transfers to content creators.',
  tags = '{"mass-disbursements","contractor-payouts"}'
WHERE id = 22855;

-- 22897: Uses escrow between financial institutions
UPDATE reply_analysis SET
  interests = 'Currently uses escrow service to process payments between financial institutions. Exploring where crypto-fiat settlement could fit as alternative or complement to current escrow-based flows.',
  tags = '{"treasury-management","fx-conversion"}'
WHERE id = 22897;

-- 22757: Octaloop India — set NULL (just scheduling after Token2049)
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id = 22757;
-- 22758: UAE — set NULL (just scheduling)
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id = 22758;
-- 23340: Tax stuff — misclassified
UPDATE reply_analysis SET interests = NULL, tags = '{}' WHERE id = 23340;
