-- Batch 2: Remaining warm+questions replies — 60 replies

UPDATE reply_analysis SET interests = 'Wants one-pager overview of crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22139;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22140;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22142;

-- GOLD: HK+USA companies, Stripe/PayPal integrated, ready for crypto, payouts to HK
UPDATE reply_analysis SET interests = 'Final-stage website with Stripe and PayPal already integrated, ready to add crypto payments. Companies in Hong Kong and USA. All payouts through Hong Kong entity. Additional fintech ideas to discuss', tags = '{"payment-gateway","api-integration","crypto-to-fiat"}', geo_tags = '{"hong-kong"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22144;

-- GOLD: Has own crypto infra, looking for competitive corridors, offers fiat banking worldwide
UPDATE reply_analysis SET interests = 'Has existing crypto infrastructure and liquidity providers. Looking for more competitive payment corridors. Also offers full banking infrastructure for fiat custody worldwide — potential go-to-market partnership', tags = '{"have-solution","fx-conversion","multi-currency","treasury-management"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22146;

UPDATE reply_analysis SET interests = 'Wants materials on crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22148;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22149;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22167;

-- Specifically interested in PAYOUTS
UPDATE reply_analysis SET interests = 'Specifically interested in crypto payout solutions — wants detailed information about mass payouts', tags = '{"mass-disbursements","contractor-payouts"}', geo_tags = '{}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22168;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22171;
UPDATE reply_analysis SET interests = 'Wants one-pager and LinkedIn profile after ICE conference meeting', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22176;

-- Not for POSMate but another business
UPDATE reply_analysis SET interests = 'Not relevant for POSMate (POS product) but has another business where crypto payments are relevant', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22195;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22197;
UPDATE reply_analysis SET interests = 'Interested, collecting questions internally before engaging', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22206;
UPDATE reply_analysis SET interests = 'Wrong contact (not at SmartGen) but personally interested in crypto payment pricing and terms', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22208;

-- Fortris — crypto treasury platform, mutual opportunity
UPDATE reply_analysis SET interests = 'Fortris (crypto treasury/payout infrastructure) exploring mutual opportunities after ICE — potential partner or competitor', tags = '{"treasury-management","mass-disbursements","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22214;

-- GOLD: BoardMaps — payouts FROM Russia TO foreign contractors, VAT concern
UPDATE reply_analysis SET interests = 'Not interested in payment acceptance. Specifically needs payouts FROM Russia TO foreign partners and contractors. Key concern: VAT handling on cross-border crypto payouts', tags = '{"contractor-payouts","mass-disbursements","crypto-to-fiat"}', geo_tags = '{"russia"}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22244;

UPDATE reply_analysis SET interests = 'Shopify merchant evaluating crypto payment integration for e-commerce', tags = '{"payment-gateway","ecommerce"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22245;
UPDATE reply_analysis SET interests = 'TransCryptio (WAML app) requesting crypto payment proposal', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22246;
UPDATE reply_analysis SET interests = 'Wants to understand crypto payment process in detail', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22247;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22254;
UPDATE reply_analysis SET interests = 'Wants pricing and terms for crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22261;
UPDATE reply_analysis SET interests = 'Evaluating crypto payment solutions after ICE conference', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22274;
UPDATE reply_analysis SET interests = 'Wants one-pager for evaluation after ICE meeting', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22276;
UPDATE reply_analysis SET interests = 'Wants one-pager for evaluation after ICE meeting', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22278;

-- TinyAdz — payout to contractors abroad mentioned in thread
UPDATE reply_analysis SET interests = 'Reviewing crypto payment materials. Thread discusses relevance of payouts to foreign contractors as alternative to SWIFT/Wise', tags = '{"payment-gateway","contractor-payouts"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22279;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22286;

-- DACO project logistics — both payment acceptance AND payouts
UPDATE reply_analysis SET interests = 'Logistics company has both use cases — crypto payment acceptance AND payouts. Germany-based', tags = '{"payment-gateway","mass-disbursements"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22288;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22290;

-- Get Inn — specifically payment acceptance (paygate)
UPDATE reply_analysis SET interests = 'Get Inn (hospitality platform) specifically interested in crypto payment acceptance for hotel/travel bookings', tags = '{"payment-gateway","crypto-to-fiat"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22292;

UPDATE reply_analysis SET interests = 'Wants materials on crypto payment infrastructure for evaluation', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22293;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22299;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22309;

-- US company, all operations through US entity
UPDATE reply_analysis SET interests = 'US-based company, all operations through US entity. Interest in crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22315;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22316;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22317;

-- UK company, UBO from Belarus with EU residency
UPDATE reply_analysis SET interests = 'UK-registered company, UBO from Belarus with EU residency. Interest in crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22319;

UPDATE reply_analysis SET interests = 'Merchant requesting crypto payment processing rates', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22321;
UPDATE reply_analysis SET interests = 'SaaS company interested in crypto payment integration details', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22324;
UPDATE reply_analysis SET interests = 'Wants materials on crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22330;
UPDATE reply_analysis SET interests = 'Wants one-pager overview of crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22353;

-- Auto-response from business team — should be auto_response
UPDATE reply_analysis SET interests = 'Auto-response from business team review queue — not a real engagement', tags = '{}', geo_tags = '{}', intent = 'auto_response', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22364;

UPDATE reply_analysis SET interests = 'White Swan evaluating crypto payment infrastructure after ICE conference', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22370;
UPDATE reply_analysis SET interests = 'Interested in crypto payment services, requesting detailed information', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22392;
UPDATE reply_analysis SET interests = 'Wants materials on crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22407;
UPDATE reply_analysis SET interests = 'Wants one-pager overview of crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22410;

-- Not now but wants presentation for other businesses
UPDATE reply_analysis SET interests = 'Not currently relevant for main business but wants presentation for other business ventures', tags = '{"payment-gateway"}', geo_tags = '{}', intent = 'not_now', warmth_score = 2, analyzer_model = 'opus-manual' WHERE id = 22411;

UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22416;
UPDATE reply_analysis SET interests = 'Wants materials on crypto payment services', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22419;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22454;

-- GOLD: Syntes/DigitalSync US — international payments for US companies, wants English materials for partners
UPDATE reply_analysis SET interests = 'US-based company needs international payment solutions via crypto. Wants English-language materials to share with partners for joint evaluation', tags = '{"payment-gateway","fx-conversion"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22464;

UPDATE reply_analysis SET interests = 'Wants formal offer for crypto payment services to evaluate', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22490;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22521;
UPDATE reply_analysis SET interests = 'Software company evaluating crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22557;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22610;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22630;
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22643;

-- GOLD: UAE bank settlement — asking about currencies, settlement flows, conversion, fees, API
UPDATE reply_analysis SET interests = 'Needs crypto-to-fiat settlement to UAE bank account. Asking about supported currencies, settlement flows, conversion mechanism, fees, API integration, and onboarding process', tags = '{"payment-gateway","crypto-to-fiat","api-integration"}', geo_tags = '{"uae"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22644;

UPDATE reply_analysis SET interests = 'Interest in OTC crypto-fiat exchange services', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22651;
UPDATE reply_analysis SET interests = 'Mobile application company exploring crypto payment integration', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22656;
