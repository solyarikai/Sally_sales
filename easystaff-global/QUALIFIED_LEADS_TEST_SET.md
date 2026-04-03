# EasyStaff Global — Complete Test Set for Pipeline Validation

**Date**: 2026-03-24
**Source**: Google Sheet "Easystaff Global <> Sally", Leads tab, Status column filtered
**Purpose**: Every qualified lead must pass the pipeline. Any rejection = false negative = prompt must be fixed.

---

## QUALIFIED (Засчитываем) — 26 leads

These MUST be accepted by the pipeline. If rejected = prompt is broken.

| # | Name | Email | Domain | Notes |
|---|------|-------|--------|-------|
| 1 | Cinzia Donato | cinzia@herabiotech.com | herabiotech.com | 9 emp, interest for future |
| 2 | Juan Pablo Rivero | jprivero@h2oallegiant.com | h2oallegiant.com | 3 emp, US→MX, 4-5 contractors, Wise+Upwork |
| 3 | Alexander Booth | alex@consulthuckleberry.com | consulthuckleberry.com | 1 emp, US→CO/PH, 12 people |
| 4 | Ramon Elias | ramon.elias@samlabs.com | samlabs.com | 40 emp, CEO approved, 9 contractors, Rippling switcher |
| 5 | Karla Sanchez | karla.sanchez@medtrainer.com | medtrainer.com | US, 87 emp, ADP switcher |
| 6 | Denis Oleinik | (Executive director) | comingoutspb.org | SIGNED, LT→RF, 30+ people |
| 7 | Johannes Lotter | j.lotter@lottermedia.com | lottermedia.com | SIGNED CONTRACT, DE→RU/BY, 50 people |
| 8 | Morim Perez | m.perez@igt-glasshardware.com | igt-glasshardware.com | US, glass mfg, freelancers DO/AR/CO, Deel $45+$5 |
| 9 | Kirshen Naidoo | kirshen@gigengineer.io | gigengineer.io | South Africa, Qatar |
| 10 | Diksha Mulani | diksha@zopreneurs.com | zopreneurs.com | Dubai, Zoho partner |
| 11 | Martins Lielbardis | martins@doingbusiness.live | doingbusiness.live | EU→UA payouts |
| 12 | Muhammad Asim Akram | asim@tazahtech.com | tazahtech.com | Dubai, logistics/tech |
| 13 | Rashid Shaikh | rashid@riviafragrances.com | riviafragrances.com | UAE, contractors outside UAE |
| 14 | Arik Bendaud | arik@affilroi.com | affilroi.com | 200+ freelancers, ICE meeting |
| 15 | Dimitre Tzonev | dt@firstbyt.com | firstbyt.com | |
| 16 | Allan Lopez | allan@puzzle.tech | puzzle.tech | US→HN, 90 emp + 50 freelancers, Tipalti $60/person |
| 17 | Uthpala Fernando | uthpala@petpos.com | petpos.com | US→PH/BO/SriLanka, pays via Wise |
| 18 | Ameer Hashish | ameer@gamingaudiences.com | gamingaudiences.com | Pakistan payouts, bank + crypto |
| 19 | Artem Medvedev | artem@betterthin.gs | betterthin.gs | EE→EU, 12 people, Kraken crypto+fiat |
| 20 | Surya Palli | surya@igamingrealtalk.com | igamingrealtalk.com | UAE, USDT, up to $10k |
| 21 | Matthew Steley | | (gmail — no corp domain) | Crypto payments |
| 22 | Jerome Sombilon | sombilon...@gmail.com | (gmail — no corp domain) | Pays through another platform |
| 23 | Hamlet Mirzoyan | hamlet@saviorhire.com | saviorhire.com | |
| 24 | Marco | marco.kowalewski@moviton.com | moviton.com | UAE→CO, 7 people, $10k/payment |
| 25 | Aleksandra Danilenko | aleksandra.danilenko@amaiz.com | amaiz.com | Banking/fintech |
| 26 | Achal Gupt | achal@frizzonstudios.ae | frizzonstudios.ae | Dubai, team in India, pays Lebanon+EU |
| 27 | Lizelle Van Schouwenburg | (from Telegram) | tactilegames.com | CFO, 250-360 emp, 50+ nationalities, LATAM freelancers |

### Companies with domains (can be tested): 25
### Companies without domains (gmail only): 2

---

## NOT QUALIFIED (Не засчитываем) — 18 leads

These SHOULD be rejected by the pipeline. If accepted = false positive.

| # | Name | Company | Website | Why Not Qualified |
|---|------|---------|---------|-------------------|
| 1 | Adan Garay | Grandave Capital | grandavecapital.com | Uses outsource, not interested |
| 2 | Gosia Furmanik | Fena.co | fena.co | Non-target, wanted to pitch own services |
| 3 | Subhan Huseynov | DQ Pursuit | dqpursuit.com | Hires within USA only, uses Gusto |
| 4 | Daniel Nenning | Sales for Future | sales4future.at | |
| 5 | Philipp Quaderer | SPM | spm.li | All employees on payroll, no contractors |
| 6 | Laura Gonzalez | GetVocal AI | getvocal.ai | All employed, all in Europe |
| 7 | Fahad Al-Alaleeli | Pan United | panunited.ae | Already has bank setup, very low commission |
| 8 | Hadi Jawad | Sapience | sapience.ae | |
| 9 | Gabriel Jatombliansky | | (no domain) | |
| 10 | Inaas Arabi | Block & Associates | blockrealty.com | |
| 11 | Muhammad Farrukh Zubair | | (no domain) | |
| 12 | Nojoud Alamoudi | | (no domain) | |
| 13 | Milen Marinov | | (no domain) | Huge fintech, needed rails not payroll |
| 14 | Ahmed Naji | | (no domain) | Contractors maybe but not sure |
| 15 | Lavanya Arumughan | | (no domain) | Looking for EOR, not payroll |
| 16 | Anastasija | Fin.club | fin.club | |
| 17 | Igor Ristovic | | (no domain) | |
| 18 | Christina Dimitriou | Red Walking | redwalking.com | |

---

## Pipeline Validation Results (V7 prompt, 2026-03-24)

### Summary
- **Correct**: 16
- **False Negatives** (qualified but rejected): **15** — UNACCEPTABLE
- **False Positives** (not qualified but accepted): 3
- **Empty/failed scrape**: 5

### False Negatives — MUST FIX

| Company | Domain | Why GPT Rejected | Why It's Wrong |
|---------|--------|-----------------|----------------|
| Herabiotech | herabiotech.com | "medical diagnostics, not service business" | They have international team, interested in EasyStaff |
| H2O Allegiant | h2oallegiant.com | "water recycling, not service business" | US→MX corridor, 4-5 contractors, Wise user |
| SAM Labs | samlabs.com | "403 Forbidden, can't analyze" | EdTech product co, 9 contractors, Rippling switcher |
| ComingOut | comingoutspb.org | "LGBTQ support org, not service business" | SIGNED customer, 30+ people across 10 countries |
| Fena.co | fena.co | "software/payment provider, excluded" | Fintech with international team |
| LotterMedia | thomas-lotter.de | "personal brand, solo" | SIGNED CONTRACT, 50 people in RU/BY |
| IGT Glass | glasshardware.com | "e-commerce selling hardware" | Manufacturing, freelancers in DO/AR/CO, Deel user |
| DQ Pursuit | dqpursuit.com | "data management solutions" | (correctly rejected — this is NOT QUALIFIED) |
| Gig Engineer | gigengineer.io | "personal brand, solo" | SA/Qatar, qualified meeting |
| SPM | spm.li | "engineering, not service business" | (correctly rejected — no contractors) |
| Puzzle.tech | puzzle.tech | "staffing/recruitment = competitor" | CUSTOMER, 50 freelancers, uses Tipalti $60/person |
| Central Park Puppies | centralparkpuppies.com | "puppy sales, offline retail" | US→PH/BO/SriLanka, pays contractors via Wise |
| Fin.club | fin.club | "financial platform" | (correctly rejected — NOT QUALIFIED) |
| Amaiz | amaiz.com | "banking service" | Has international team |

### Root Cause: The V7 prompt asks "Is this a SERVICE BUSINESS that hires freelancers?"

Our actual customers are ANY company that pays people internationally:
- Product companies (SAM Labs, MedTrainer, IGT Glass)
- Manufacturing (glass, water recycling)
- Fintech (Fena, Amaiz)
- Pet businesses (Central Park Puppies)
- Media/music (LotterMedia)
- Nonprofits (ComingOut)
- Talent platforms (Puzzle.tech — excluded as "competitor" but is a CUSTOMER)

### What the prompt SHOULD ask:
"Does this company likely have team members, contractors, or freelancers in multiple countries?"
NOT: "Is this a service business?"
