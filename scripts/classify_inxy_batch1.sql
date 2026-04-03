-- Batch 1: Warm replies (schedule_call, send_info, interested_vague) — 50 replies
-- Classified by Opus directly with financial-only tags + corridor geo

-- 22141: "Давайте в 8. На час созвонимся" — pure scheduling, no financial detail
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22141;

-- 22160: Gabriel Jatombliansky, EGC/IvyAscent — iGaming, scheduling call
UPDATE reply_analysis SET interests = 'iGaming company interested in crypto payment acceptance for gaming platform', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22160;

-- 22180: "Hey, can we speak about some partnership?" — crypto payments, LinkedIn
UPDATE reply_analysis SET interests = 'Exploring partnership opportunity around crypto payments', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22180;

-- 22209: "Tamara, very happy to have a chat" — generic warm
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22209;

-- 22241: Александра Паттури, COO WAML app / TransCryptio — bringing CEO+CTO to meeting
UPDATE reply_analysis SET interests = 'TransCryptio (WAML app) evaluating crypto payment infrastructure, bringing CEO and CTO to meeting', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22241;

-- 22294: Fabio Parlascino, Crelora — Ecom Berlin, crypto payments
UPDATE reply_analysis SET interests = 'E-commerce company exploring crypto payment acceptance after Ecom Berlin conference', tags = '{"payment-gateway","ecommerce"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22294;

-- 22295: Alexey Vysokov, Far Rainbow Srl — scheduling
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22295;

-- 22298: George Tskhadadze, tr-sys.eu, Georgia — transaction systems
UPDATE reply_analysis SET interests = 'Transaction systems company evaluating crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22298;

-- 22314: "Доброе утро. Оптимально на след неделе" — pure scheduling
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22314;

-- 22323: Trust Payments — seems to be offering THEIR services back
UPDATE reply_analysis SET interests = 'Trust Payments offering their own payment services — potential partner rather than customer', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22323;

-- 22344: Aleksei Malenkin, CTO Monetech, Mexico — scheduling
UPDATE reply_analysis SET interests = 'Fintech company evaluating crypto payment infrastructure', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22344;

-- 22357: Rainer Seyer, countr.de — WHITE-LABEL for POS terminals, asked about GDPR, fees
UPDATE reply_analysis SET interests = 'POS terminal company exploring white-label crypto payment integration for retail terminals. Asking about EU server location (GDPR), fees under 1%, and integration approach', tags = '{"white-label","payment-gateway","pos-terminal","api-integration"}', geo_tags = '{"europe"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22357;

-- 22358: Diamantis Kyriakakis, MobiWeb — ICE follow-up, crypto infra
UPDATE reply_analysis SET interests = 'MobiWeb evaluating crypto payment acceptance, mass payout automation, and OTC exchange services', tags = '{"payment-gateway","mass-disbursements"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22358;

-- 22390: "да это интересно, напишите в tg" — redirect to Telegram
UPDATE reply_analysis SET interests = 'General interest in crypto payment infrastructure, redirecting to Telegram', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22390;

-- 22412: Dzmitry Khabibullin, CEO GlobalTips — scheduling
UPDATE reply_analysis SET interests = 'Global tips/payments company evaluating crypto payment gateway', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22412;

-- 22433: Дмитрий Золотарев, CoLabs — NOT interested, counter-selling AI tool
UPDATE reply_analysis SET interests = 'Not interested in crypto payments. Counter-offered AI sales research tool for beta access', tags = '{}', geo_tags = '{}', intent = 'not_now', warmth_score = 1, analyzer_model = 'opus-manual' WHERE id = 22433;

-- 22434: GOLD — wants to pay employee in Belarus via crypto → fiat on Belarus card
UPDATE reply_analysis SET interests = 'Needs crypto-to-fiat payout to employee in Belarus. Wants to pay using crypto and have fiat delivered to Belarusian bank card', tags = '{"crypto-to-fiat","contractor-payouts"}', geo_tags = '{"belarus"}', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22434;

-- 22437: QZen Family Office — interested, redirect to Telegram
UPDATE reply_analysis SET interests = 'Family office interested in crypto payment infrastructure', tags = '{"treasury-management"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22437;

-- 22440: GOLD — crypto payment for tourism product on European market in 2026
UPDATE reply_analysis SET interests = 'Planning crypto payment integration for tourism product on European market in 2026. Needs pricing, supported cryptocurrencies, withdrawal options, and integration requirements', tags = '{"payment-gateway","api-integration","multi-currency","crypto-to-fiat"}', geo_tags = '{"europe"}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22440;

-- 22442: George Tskhadadze again — just scheduling
UPDATE reply_analysis SET interests = 'Transaction systems company proceeding with meeting', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22442;

-- 22466: "Фокус как на прием так и отправку" — BOTH receiving AND sending
UPDATE reply_analysis SET interests = 'Interested in both crypto payment acceptance (paygate) and crypto payouts — dual-direction crypto-fiat', tags = '{"payment-gateway","mass-disbursements","crypto-to-fiat"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22466;

-- 22471: Encoded Cyrillic, scheduling with some back-and-forth
UPDATE reply_analysis SET interests = 'Interest in crypto payment processing, had prior blockers being discussed', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22471;

-- 22473: GOLD — Regolith, asking USDT/USDC acceptance, networks, conversion fees
UPDATE reply_analysis SET interests = 'Regolith needs USDT and USDC payment acceptance. Asking about commission rates, supported blockchain networks, and crypto-to-fiat conversion fees', tags = '{"payment-gateway","crypto-to-fiat","stablecoin-settlement"}', geo_tags = '{}', offer_responded_to = 'paygate', intent = 'pricing', analyzer_model = 'opus-manual' WHERE id = 22473;

-- 22480: "Давайте запланируем созвон" — Madrid timezone, scheduling
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22480;

-- 22489: Svetlana Kaltovich, CFO Geomotiv — has 2 existing partners
UPDATE reply_analysis SET interests = 'Already has 2 crypto payment partners. No urgent need but willing to compare alternative offer', tags = '{"have-solution"}', geo_tags = '{}', intent = 'not_now', warmth_score = 2, analyzer_model = 'opus-manual' WHERE id = 22489;

-- 22519: "Проект расформирован" — project dissolved
UPDATE reply_analysis SET interests = 'Project for Fotostrana has been dissolved — no longer relevant', tags = '{}', geo_tags = '{}', intent = 'not_now', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22519;

-- 22525: Vlad, Fotostrana — redirect to Telegram
UPDATE reply_analysis SET interests = 'Fotostrana interested in crypto payment acceptance and/or payouts', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22525;

-- 22542: Tatyana + Ivan Antonov, Agency Navy — financial director engaged
UPDATE reply_analysis SET interests = 'Creative agency interested in crypto payments, financial director actively engaged', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22542;

-- 22554: GOLD — ADJACENT DEMAND: buy crypto from company bank accounts, send to contractors
UPDATE reply_analysis SET interests = 'Reverse need: wants to buy crypto from company bank accounts and transfer to contractors. Needs fiat-to-crypto on-ramp plus crypto payout to performers', tags = '{"on-ramp","fiat-to-crypto","contractor-payouts"}', geo_tags = '{}', intent = 'adjacent_demand', offer_responded_to = 'payout', analyzer_model = 'opus-manual' WHERE id = 22554;

-- 22573: Mike Amirov, Solves — counter-deal, wants referrals
UPDATE reply_analysis SET interests = 'Not directly interested in crypto payments. Proposes referral partnership — wants INXY to introduce developer clients to Solves in exchange', tags = '{}', geo_tags = '{}', intent = 'not_now', warmth_score = 1, analyzer_model = 'opus-manual' WHERE id = 22573;

-- 22590: Roman Peterson — already uses crypto corporate cards, OTC MM desks
UPDATE reply_analysis SET interests = 'Already using crypto-fiat payments via crypto corporate cards and OTC market maker desks. Exploring additional or alternative OTC solutions', tags = '{"have-solution","crypto-to-fiat"}', geo_tags = '{}', offer_responded_to = 'otc', analyzer_model = 'opus-manual' WHERE id = 22590;

-- 22608: Vincenzo, ThinkTradeFinance — wants to RESELL INXY services
UPDATE reply_analysis SET interests = 'Trade finance platform wants to resell INXY crypto-fiat exchange services to their clients. Interested in white-label or partnership for cross-border settlements', tags = '{"white-label","fx-conversion","treasury-management"}', geo_tags = '{}', offer_responded_to = 'otc', analyzer_model = 'opus-manual' WHERE id = 22608;

-- 22636: Michelle, Luma — generic scheduling for January
UPDATE reply_analysis SET interests = 'General interest in crypto-fiat OTC exchange services', tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22636;

-- 22645: Aigerim, Almaty — Baxity lookalike campaign, scheduling
UPDATE reply_analysis SET interests = 'General interest in crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22645;

-- 22694: Raymond Carapella, TiltPayments, US & Caribbean — payment platform
UPDATE reply_analysis SET interests = 'Payment platform company exploring crypto payment infrastructure for US and Caribbean operations', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22694;

-- 22765: Ivo Kadlic, AnyCoin.cz — crypto exchange asking what paygate means
UPDATE reply_analysis SET interests = 'Crypto exchange platform (Anycoin.cz) asking about paygate — whether it means fiat transfer for crypto purchase. Wants detailed product explanation', tags = '{"payment-gateway"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22765;

-- 22928: Ritvars Radvilavics, Bedford Pay, FCA EMI — partnership/revshare
UPDATE reply_analysis SET interests = 'UK FCA-regulated EMI (Bedford Pay) exploring crypto payment partnership or revenue share model. Interested in both using INXY solutions and cross-selling their EMI services', tags = '{"payment-gateway","white-label","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22928;

-- 23520: Heikki Ruhanen, COO Fairway, Helsinki — scheduling demo
UPDATE reply_analysis SET interests = 'Software development company evaluating crypto payment solutions for integration', tags = '{"payment-gateway","api-integration"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23520;

-- 23658: Jessica, Anonybit — scheduling
UPDATE reply_analysis SET interests = 'Identity verification company exploring crypto payment infrastructure', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 23658;

-- 23886: Vladislav Gershkovich — will study and return
UPDATE reply_analysis SET interests = 'Interest in crypto payment acceptance with sub-1% commission for fiat withdrawal', tags = '{"payment-gateway","crypto-to-fiat"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 23886;

-- 23910: "где вы на моем сайте увидели платежи?" — wrong target, confused
UPDATE reply_analysis SET interests = 'Does not understand relevance of crypto payments to their business — likely wrong target', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 23910;

-- 22111: Paul Goldfinch, Start Investments — wants to know how it works
UPDATE reply_analysis SET interests = 'Investment company wants to understand how crypto payment infrastructure works before scheduling', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22111;

-- 22114: "пришлите one-pager, а клиент только в крипте может платить?"
UPDATE reply_analysis SET interests = 'Wants one-pager. Asking whether customers can only pay in crypto or also fiat — evaluating crypto payment acceptance', tags = '{"payment-gateway"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22114;

-- 22115: Osvaldas Kazlauskas, Finsupport, Tallinn/Oslo — "Let us explore both options"
UPDATE reply_analysis SET interests = 'Financial services company exploring both crypto payment acceptance and payout solutions', tags = '{"payment-gateway","mass-disbursements"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22115;

-- 22116: Osvaldas again — scheduling follow-up
UPDATE reply_analysis SET interests = 'Financial services company proceeding with evaluation of crypto payment and payout solutions', tags = '{"payment-gateway","mass-disbursements"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22116;

-- 22121: "If you want to advertise this service with us" — counter-sell, not interested
UPDATE reply_analysis SET interests = 'Not interested in crypto payments. Offering advertising/media placement services instead', tags = '{}', geo_tags = '{}', intent = 'not_relevant', warmth_score = 0, analyzer_model = 'opus-manual' WHERE id = 22121;

-- 22124: Kea — banking + crypto for high-risk industries, exploring collaboration
UPDATE reply_analysis SET interests = 'Crypto banking solutions provider (Kea) exploring collaboration. Already provides banking and crypto solutions to high-risk industries', tags = '{"payment-gateway","fintech"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22124;

-- 22128: "Можем сегодня созвониться. После 13.00 по Дублину" — scheduling, LinkedIn
UPDATE reply_analysis SET interests = NULL, tags = '{}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22128;

-- 22129: Kirk, iGaming — reconnect in April
UPDATE reply_analysis SET interests = 'iGaming company interested in crypto payment infrastructure, scheduling for later', tags = '{"payment-gateway"}', geo_tags = '{}', analyzer_model = 'opus-manual' WHERE id = 22129;

-- 22134: "Да, можете прислать one-pager"
UPDATE reply_analysis SET interests = 'Wants one-pager overview of crypto payment infrastructure services', tags = '{"payment-gateway"}', geo_tags = '{}', offer_responded_to = 'paygate', analyzer_model = 'opus-manual' WHERE id = 22134;
