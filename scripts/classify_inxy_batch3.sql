-- Batch 3: All remaining warm+questions+adjacent+pricing+compliance+regulatory+specific_use_case

-- === ADJACENT DEMAND ===
-- Fiat-fiat payments company, doesn't need on/off-ramp
UPDATE reply_analysis SET interests = 'Fiat-to-fiat payments company (gateway for Amazon, Coinbase, Binance, UK iGaming). No need for crypto on-ramp/off-ramp themselves', tags = '{"have-solution","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22196;
-- ONLY wants on-ramp (fiat→crypto)
UPDATE reply_analysis SET interests = 'Only interested in on-ramp (fiat-to-crypto). No need for off-ramp to fiat. Will consider if INXY adds on-ramp product', tags = '{"on-ramp","fiat-to-crypto"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22435;
-- Wants fiat payments to Russia on MIR cards
UPDATE reply_analysis SET interests = 'Not interested in crypto. Wants fiat-to-fiat transfer to Russia on MIR cards — asking if INXY can facilitate this through crypto rails', tags = '{"fiat-to-fiat"}', geo_tags = '{"russia"}', analyzer_model = 'opus-manual' WHERE id = 22456;
-- Wants crypto as transport rail, users only in fiat, need exchange both ends
UPDATE reply_analysis SET interests = 'Wants crypto as transport rail for payments but end-users transact only in fiat. Needs exchange to crypto at on-ramp AND exchange from crypto at off-ramp', tags = '{"on-ramp","off-ramp","crypto-to-fiat","fiat-to-crypto"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22753;

-- === COMPLIANCE ===
UPDATE reply_analysis SET interests = 'Looking for colocation space — misrouted, not interested in crypto payments', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22215;
-- Russia — asking about VAT/simplified tax payments
UPDATE reply_analysis SET interests = 'Asking about crypto payments for Russia market with VAT/USN (simplified tax) implications', tags = '{"payment-gateway"}', geo_tags = '{"russia"}', analyzer_model = 'opus-manual' WHERE id = 22285;
UPDATE reply_analysis SET interests = 'Wants product demo or test login for crypto payment platform', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22751;

-- === HAVE SOLUTION ===
UPDATE reply_analysis SET interests = 'Fully covered with current payment methods and banking partners at minimum cost. Already has USDC crypto capability', tags = '{"have-solution","stablecoin-settlement"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22766;

-- === HOW IT WORKS ===
UPDATE reply_analysis SET interests = 'Wants detailed explanation of tokenization payment product', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22325;
-- Henry Kwok — HK/Taiwan/Singapore/Malaysia markets
UPDATE reply_analysis SET interests = 'Digital marketplace company in HK/Taiwan/Singapore/Malaysia asking how crypto payment integration works', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22922;
UPDATE reply_analysis SET interests = 'Binderr CEO asking about technical details of crypto payment integration', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23652;

-- === INTERESTED VAGUE ===
-- Dubai, OTC trading
UPDATE reply_analysis SET interests = 'OTC trading company in Dubai scheduling call', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22658;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22685;
-- Payomatix India, OTC
UPDATE reply_analysis SET interests = 'Indian payment platform (Payomatix) exploring OTC crypto-fiat exchange', tags = '{"fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22687;
UPDATE reply_analysis SET interests = 'PSP company interested in crypto payment solutions', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22695;
-- GOLD: Altpaynet Philippines, central bank licensed
UPDATE reply_analysis SET interests = 'Philippine central bank-licensed payment company (Altpaynet) wants to utilize INXY technologies and payment rails for their customers. Exploring technology partnership and collaboration areas', tags = '{"payment-gateway","white-label","api-integration","fintech"}', geo_tags = '{"philippines"}', analyzer_model = 'opus-manual' WHERE id = 22723;
-- ZenPay Malaysia
UPDATE reply_analysis SET interests = 'Malaysian payment platform (ZenPay) scheduling call', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22746;
-- Spanish — fund for SME credit via crypto?
UPDATE reply_analysis SET interests = 'Asking about creating a fund to finance SME credit operations through crypto — exploring DeFi lending or crypto-backed credit', tags = '{"treasury-management","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22747;
-- Octaloop India, Token2049
UPDATE reply_analysis SET interests = 'Indian events/tech company interested in INXY after Token2049', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22757;
-- UAE accounts/finance
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22758;
-- GOLD: Settlement/Payment/Collection + White-Label
UPDATE reply_analysis SET interests = 'Looking for Settlement, Payment, Collection partner AND White-Label Platform provider. Wants comprehensive overview of all services', tags = '{"payment-gateway","white-label","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22769;
-- YellowCard Africa
UPDATE reply_analysis SET interests = 'YellowCard (Africa crypto platform) scheduling follow-up after Token2049', tags = '{"fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22817;
-- Mass payouts to artists
UPDATE reply_analysis SET interests = 'Exploring crypto mass payouts to network of artists and collaborators', tags = '{"mass-disbursements","contractor-payouts"}', geo_tags = '{}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22855;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22880;
-- Uses escrow between financial institutions
UPDATE reply_analysis SET interests = 'Currently uses escrow service for payments between financial institutions. Wants to understand where crypto payments could fit their cases', tags = '{"treasury-management","fx-conversion"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22897;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22911;
-- Tax advice spam — misclassified
UPDATE reply_analysis SET interests = 'Tax advice newsletter — not a reply to INXY outreach, misrouted content', tags = '{}', geo_tags = '{}', intent = 'gibberish', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 23340;
-- Kseniia, checking with partners
UPDATE reply_analysis SET interests = 'Head of Finance checking with partners about crypto payment interest', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23454;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23496;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23965;

-- === PRICING ===
-- GOLD: Italy — EU compliance, crypto payment acceptance, documented fiat conversion
UPDATE reply_analysis SET interests = 'Needs EU compliance documentation and fund security guarantees. Primary interest: receiving crypto payments with properly documented conversion to fiat and bank withdrawal. Key requirement: legality, transparency, and safety under Italian law', tags = '{"payment-gateway","crypto-to-fiat","kyc-kyb"}', geo_tags = '{"europe"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22308;
UPDATE reply_analysis SET interests = 'SaaS company requesting payment methods supported, pricing structure, and real-world implementation examples', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22322;
-- GOLD: Russia OTC — USD→USDT conversion rate
UPDATE reply_analysis SET interests = 'Asking about Russia operations and USD-to-USDT conversion rates. OTC crypto exchange need', tags = '{"fx-conversion","stablecoin-settlement"}', geo_tags = '{"russia"}', offer_responded_to = 'otc', analyzer_model = 'opus-manual' WHERE id = 22422;
-- GOLD: Full due diligence — license, KYC/KYB, AML, products, core assets
UPDATE reply_analysis SET interests = 'Full due diligence: license jurisdiction, KYC/KYB process, AML/sanctions screening tools, product coverage (spot/derivatives/options/structured), core asset flow (BTC/ETH/stables/altcoins)', tags = '{"kyc-kyb","treasury-management","fx-conversion"}', geo_tags = '{}', offer_responded_to = 'otc', analyzer_model = 'opus-manual' WHERE id = 22588;
UPDATE reply_analysis SET interests = 'Interested if rates are competitive — ready to proceed based on pricing', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22736;
UPDATE reply_analysis SET interests = 'Requesting high-level pricing structure and detailed service information', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22777;

-- === REGULATORY ===
UPDATE reply_analysis SET interests = 'Government contract prevents crypto adoption currently. May return later if situation changes', tags = '{"regulatory-block"}', geo_tags = '{"russia"}', analyzer_model = 'opus-manual' WHERE id = 22205;
-- Uzbekistan — only local crypto exchanges allowed
UPDATE reply_analysis SET interests = 'Uzbekistan regulation only allows crypto operations through local exchanges and exchangers. INXY scheme does not fit regulatory requirements', tags = '{"regulatory-block"}', geo_tags = '{"uzbekistan"}', analyzer_model = 'opus-manual' WHERE id = 22377;
-- Bedford Pay — would need new crypto license
UPDATE reply_analysis SET interests = 'Would require obtaining crypto license and setting up new institution with compliance, systems, etc. Not feasible in near future', tags = '{"regulatory-block","licensing"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22832;

-- === SEND INFO (remaining) ===
-- Suisse Bank, Head of Payments
UPDATE reply_analysis SET interests = 'Suisse Bank Head of Payments & Partnerships interested in crypto payment solutions for banking clients', tags = '{"payment-gateway","fintech","white-label"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22705;
UPDATE reply_analysis SET interests = 'PSP company requesting more service details', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22772;
-- FX rates for payouts
UPDATE reply_analysis SET interests = 'Asking about FX rates charged on crypto payout transactions', tags = '{"fx-conversion","mass-disbursements"}', geo_tags = '{}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22780;
-- GOLD: Finmo — white-label crypto-fiat for global clients
UPDATE reply_analysis SET interests = 'Finmo interested in white-label crypto-fiat exchange and settlement infrastructure for their global clients. Exploring how INXY infrastructure could benefit their platform', tags = '{"white-label","crypto-to-fiat","fx-conversion","api-integration"}', geo_tags = '{}', offer_responded_to = 'otc', analyzer_model = 'opus-manual' WHERE id = 22798;
-- Uses Stripe/PayPal, wants to see crypto gateway alongside
UPDATE reply_analysis SET interests = 'Currently uses Stripe and PayPal. Wants to see crypto gateway setup alongside existing payment methods. Asking about implementation effort and integration approach', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 23022;
-- Platform rates and demo for creator payouts
UPDATE reply_analysis SET interests = 'Requesting platform rates and demo booking for creator economy payouts', tags = '{"mass-disbursements","contractor-payouts"}', geo_tags = '{}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 23039;
-- Public info on payout platform
UPDATE reply_analysis SET interests = 'Wants public information about crypto payout platform to evaluate before proceeding', tags = '{"mass-disbursements"}', geo_tags = '{}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 23123;

-- === SPECIFIC USE CASE ===
-- Referral programme for clients
UPDATE reply_analysis SET interests = 'Wants to offer INXY crypto payments to their clients via referral programme. Already has another provider but not actively using it', tags = '{"white-label","payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22113;
-- GOLD: Off-ramping to Big 5 Canadian banks in USD
UPDATE reply_analysis SET interests = 'Asking specifically about off-ramping crypto to Big 5 Canadian banks. Wants to know if USD off-ramp is available', tags = '{"off-ramp","crypto-to-fiat","wire-transfer"}', geo_tags = '{"canada"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22130;
UPDATE reply_analysis SET interests = 'Asking about referral/partnership agreements for crypto payment services', tags = '{"white-label"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22166;
-- GOLD: Legal freelancer payouts from RU company in crypto or to foreign cards
UPDATE reply_analysis SET interests = 'Asking if INXY can legally handle freelancer payouts from Russian company bank account in crypto OR to foreign bank cards. Key: legal compliance for RU entity', tags = '{"contractor-payouts","crypto-to-fiat","mass-disbursements"}', geo_tags = '{"russia"}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22183;
UPDATE reply_analysis SET interests = 'Asking about referral source — memory jog needed', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22185;
-- GOLD: Large travel sums, KYC concerns, crypto payment acceptance
UPDATE reply_analysis SET interests = 'Travel company with large transaction amounts. KYC concerns and questions about compliance process. Interested in crypto payment acceptance but not for cost savings — driven by customer demand to pay in crypto', tags = '{"payment-gateway","kyc-kyb"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22263;
-- Just forwarded original email back
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', intent = 'empty', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22301;
-- "Where did you get such old profiles?" — data source question
UPDATE reply_analysis SET interests = 'Asking about data source for lead contact — not interested in product', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22310;
-- "How did you get my contact data?"
UPDATE reply_analysis SET interests = 'Asking about data source for contact — not interested in product', tags = '{}', geo_tags = '{}', intent = 'spam_complaint', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22354;
-- "And what would you want me to do with this?"
UPDATE reply_analysis SET interests = 'Confused about relevance of crypto payment pitch — not interested', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22395;
-- Tourism, tiny transactions 35-70 EUR
UPDATE reply_analysis SET interests = 'Tourism company with small transactions (35-70 EUR) and budget tourists. Not sure crypto adoption applies. Never researched the use case', tags = '{"payment-gateway"}', geo_tags = '{}', intent = 'not_now', warmth_score = 1, analyzer_model = 'opus-manual' WHERE id = 22439;
-- GOLD: Razlet.KG — airline tickets, SWIFT only, asking about crypto payment acceptance
UPDATE reply_analysis SET interests = 'Online airline ticket agency (Razlet.KG) currently using SWIFT for all transfers. Asking if INXY means crypto payment acceptance on their website for ticket purchases', tags = '{"payment-gateway","swift-settlement"}', geo_tags = '{"kyrgyzstan"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22453;
-- "Did we send you a request?" — confused
UPDATE reply_analysis SET interests = 'Confused about contact — did not send inquiry', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22483;
-- Asking about conditions, website slow
UPDATE reply_analysis SET interests = 'Interested in pricing and conditions but could not find info on website. Also noting slow website performance due to animations', tags = '{"payment-gateway"}', geo_tags = '{}', intent = 'pricing', analyzer_model = 'opus-manual' WHERE id = 22488;
-- GOLD: Licensing concern — "у вас лицензии нет"
UPDATE reply_analysis SET interests = 'Previously discussed but concern was INXY lacked proper license. Asking if licensing issue has been resolved', tags = '{"licensing","regulatory-block"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22530;
-- Outbound email text — misclassified as reply
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', intent = 'empty', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22581;
-- GOLD: Crypto-to-fiat withdrawal in Russia for freelancers
UPDATE reply_analysis SET interests = 'Asking about crypto-to-fiat withdrawal options specifically for freelancers in Russia', tags = '{"crypto-to-fiat","contractor-payouts"}', geo_tags = '{"russia"}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22589;
-- GOLD: FCA regulation, jurisdictions, e-money accounts
UPDATE reply_analysis SET interests = 'Asking critical compliance questions: FCA regulation for UK payment services, restricted jurisdictions (money send/receive), e-money accounts in client name', tags = '{"licensing","kyc-kyb","payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22624;
-- GOLD: FINTRAC verification — can not find INXY registration
UPDATE reply_analysis SET interests = 'Verified FINTRAC (Canada MSB) database and could not find INXY registration. Requesting clarification on regulatory status', tags = '{"licensing","regulatory-block"}', geo_tags = '{"canada"}', analyzer_model = 'opus-manual' WHERE id = 22738;
-- Flutter app + Stripe, wants integration
UPDATE reply_analysis SET interests = 'Has Flutter mobile app using Stripe as payment gateway. Asking about crypto payment integration alongside existing Stripe setup', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22873;
-- "What do you mean with OpenPay Send?"
UPDATE reply_analysis SET interests = 'Asking for clarification about OpenPay Send platform capabilities', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23586;
-- "clue me in about what you discussed with Kliment"
UPDATE reply_analysis SET interests = 'Wants context about previous discussion with Kliment before proceeding with GameZ crypto payment evaluation', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23685;

-- === BULK UPDATE: noise replies — set empty interests/tags/geo ===
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual'
WHERE project_id = 48 AND analyzer_model != 'opus-manual'
AND intent IN ('empty', 'gibberish', 'auto_response', 'bounce', 'wrong_person_forward');

-- === BULK UPDATE: hard_no, not_relevant, no_crypto, not_now, spam_complaint ===
-- These get simple objection tags but no detailed interests
UPDATE reply_analysis SET tags = '{"no-crypto"}', geo_tags = '{}', analyzer_model = 'opus-manual'
WHERE project_id = 48 AND analyzer_model != 'opus-manual' AND intent = 'no_crypto';

UPDATE reply_analysis SET tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual'
WHERE project_id = 48 AND analyzer_model != 'opus-manual'
AND intent IN ('hard_no', 'not_relevant', 'not_now', 'spam_complaint');
