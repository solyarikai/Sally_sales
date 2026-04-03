# Pipeline Validation Results

**Date**: 2026-03-24
**Prompt**: EasyStaff Global v7 (no city filter) (id=20)
**Test set**: 39 companies with domains (44 qualified + 18 not qualified)

## Summary

| Metric | Count |
|--------|-------|
| Correct | 16 |
| False Negatives | 15 |
| False Positives | 3 |
| Failed | 0 |

## All Results

| Name | Company | Domain | Expected | Pipeline | Status |
|------|---------|--------|----------|----------|--------|
| Cinzia Donato | Herabiotech | herabiotech.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Adan Garay | Grandavecapital | grandavecapital.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Juan Pablo Rivero | H2 Oallegiant | h2oallegiant.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Alexander Booth | Huckleberry | consulthuckleberry.com | MATCH | MATCH | OK |
| Ramon Elias | SAM Labs | samlabs.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Karla Sanchez Guerre |  | medtrainer.com | MATCH | EMPTY_SITE |  |
| Denis Oleinik | ComingOut | comingoutspb.org | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Gosia Furmanik |  | fena.co | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Johannes Lotter |  | thomas-lotter.de | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Morim Perez | IGT Glass Hardware | glasshardware.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Subhan Huseynov |  | dqpursuit.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Daniel Nenning |  | sales4future.at | MATCH | MATCH | OK |
| Kirshen Naidoo |  | gigengineer.io | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Diksha Mulani |  | zopreneurs.com | MATCH | MATCH | OK |
| Martins Lielbardis |  | doingbusiness.live | MATCH | EMPTY_SITE |  |
| Philipp Quaderer |  | spm.li | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Laura Gonzalez |  | getvocal.ai | MATCH | MATCH | OK |
| Muhammad Asim Akram |  | myzambeel.com | MATCH | MATCH | OK |
| Fahad Al-Alaleeli |  | panunited.ae | MATCH | MATCH | OK |
| Hadi Jawad |  | sapience.ae | MATCH | MATCH | OK |
| Inaas Arabi | Block & Associates R | blockrealty.com | MATCH | EMPTY_SITE |  |
| Allan Lopez |  | puzzle.tech | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Uthpala Fernando |  | centralparkpuppies.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Surya Palli |  | 10xbrand.io | MATCH | MATCH | OK |
| Anastasija |  | fin.club | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Aleksandra Danilenko |  | amaiz.com | MATCH | NOT_A_MATCH | FALSE_NEGATIVE |
| Achal Gupt |  | frizzonstudios.ae | MATCH | MATCH | OK |
| Christina Dimitriou |  | redwalking.com | MATCH | MATCH | OK |
| Adan Garay | Grandavecapital | grandavecapital.com | NOT_A_MATCH | EMPTY_SITE |  |
| Gosia Furmanik |  | fena.co | NOT_A_MATCH | NOT_A_MATCH | OK |
| Subhan Huseynov |  | dqpursuit.com | NOT_A_MATCH | NOT_A_MATCH | OK |
| Daniel Nenning |  | sales4future.at | NOT_A_MATCH | MATCH | FALSE_POSITIVE |
| Philipp Quaderer |  | spm.li | NOT_A_MATCH | NOT_A_MATCH | OK |
| Laura Gonzalez |  | getvocal.ai | NOT_A_MATCH | NOT_A_MATCH | OK |
| Fahad Al-Alaleeli |  | panunited.ae | NOT_A_MATCH | MATCH | FALSE_POSITIVE |
| Hadi Jawad |  | sapience.ae | NOT_A_MATCH | NOT_A_MATCH | OK |
| Inaas Arabi | Block & Associates R | blockrealty.com | NOT_A_MATCH | EMPTY_SITE |  |
| Anastasija |  | fin.club | NOT_A_MATCH | NOT_A_MATCH | OK |
| Christina Dimitriou |  | redwalking.com | NOT_A_MATCH | MATCH | FALSE_POSITIVE |

## False Negatives — MUST FIX

### Cinzia Donato | Herabiotech | herabiotech.com
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not hire freelancers or remote contractors. Matches NOT_A_MATCH because it operates in the medical diagnostics field, which is not a service business that typically utilizes freelancers or remote contractors.", "company_info":

### Adan Garay | Grandavecapital | grandavecapital.com
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does entertainment finance. Matches NOT_A_MATCH because it is an investment company focused on film acquisition and production, which does not align with the specified service business segments that hire freelancers or remote contractors."

### Juan Pablo Rivero | H2 Oallegiant | h2oallegiant.com
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not fit the criteria for a service business that hires freelancers or remote contractors. Matches NOT_A_MATCH because it operates in the water recycling solutions sector, which does not involve staffing, recruitment, or outsou

### Ramon Elias | SAM Labs | samlabs.com
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website is inaccessible, displaying a '403 - Forbidden' error. Without content to analyze, it cannot be determined if the company hires freelancers or remote contractors.", "company_info": {"name": "SAM Labs", "description": "N/A", "lo

### Denis Oleinik | ComingOut | comingoutspb.org
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website is focused on providing support and consultations for LGBTQ+ individuals, which does not align with a service business that hires freelancers or remote contractors. It appears to be a non-profit organization offering fr

### Gosia Furmanik |  | fena.co
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not match any service business that likely hires freelancers or remote contractors. Matches exclusion rules due to being a software and payment solutions provider for B2B businesses, which does not indicate a reliance on freel

### Johannes Lotter |  | thomas-lotter.de
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website appears to be a personal brand for an individual offering consulting and workshop services. It does not indicate a team of 3 or more, which is required for a match. Additionally, it does not fall under any of the excluded categ

### Morim Perez | IGT Glass Hardware | glasshardware.com
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not provide services that typically hire freelancers or remote contractors. Matches NOT_A_MATCH because it is an e-commerce company selling hardware products rather than a service business.", "company_info": {"name": "IGT Glass Hardwa

### Subhan Huseynov |  | dqpursuit.com
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website focuses on data management solutions and does not indicate a service business that hires freelancers or remote contractors. It appears to be a software platform aimed at improving data accuracy and reliability for busin

### Kirshen Naidoo |  | gigengineer.io
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website does not provide sufficient information to determine the nature of the business. It appears to be a personal brand or a solo venture, which does not meet the criteria for a service business that hires freelancers or remote cont

### Philipp Quaderer |  | spm.li
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "The website focuses on engineering solutions and production services related to bonding, sputtering targets, and repair services, which does not indicate a service business that hires freelancers or remote contractors. It appears t

### Allan Lopez |  | puzzle.tech
**GPT reasoning**: ```json
{
  "segment": "NOT_A_MATCH",
  "is_target": false,
  "reasoning": "Puzzle connects U.S. companies with Latin America's software talent, which indicates a staffing or recruitment service. Matches exclusion criteria as it operates in the staffing and talent acquisition space.",
  "company_inf

### Uthpala Fernando |  | centralparkpuppies.com
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not provide a service that hires freelancers or remote contractors. Matches NOT_A_MATCH because it is an online puppy sales business, which falls under the offline category of retail and does not involve staffing or service-based cont

### Anastasija |  | fin.club
**GPT reasoning**: {"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not hire freelancers or remote contractors. Matches NOT_A_MATCH because it operates as a financial services platform and does not fit the criteria for a service business that typically hires freelancers or remote contractors.", "compa

### Aleksandra Danilenko |  | amaiz.com
**GPT reasoning**: ```json
{"segment": "NOT_A_MATCH", "is_target": false, "reasoning": "Does not provide services that typically require freelancers or remote contractors. Matches NOT_A_MATCH because it operates as a banking service offering card products and account management, which does not align with the criteria 

