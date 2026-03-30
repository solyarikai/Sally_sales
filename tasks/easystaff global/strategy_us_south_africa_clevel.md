# Deep Strategy: Finding South African C-Levels in US Companies

*Goal: Identify US-based companies with C-level executives originally from South Africa → these companies almost certainly hire contractors/freelancers in South Africa.*

---

## Why This Corridor

- Qatar→South Africa had **18.2% conversion** (best of all EasyStaff Global corridors)
- US→South Africa is an untapped corridor with zero campaigns launched yet
- South Africa has massive English-speaking tech talent pool (Cape Town, Johannesburg)
- ZAR/USD rate makes SA contractors extremely cost-effective for US companies
- Same timezone overlap (EST = SA -6h, convenient for real-time work)

---

## 1. South African Universities (Apollo / Sales Navigator filter)

### Top Universities (highest signal — executives most likely to list these)

**Tier A — Always filter for these:**
- University of Cape Town (UCT)
- University of the Witwatersrand (Wits)
- Stellenbosch University
- University of Pretoria (UP / Tuks)
- University of KwaZulu-Natal (UKZN)
- Rhodes University (now Rhodes / RU)
- University of Johannesburg (UJ)

**Tier B — Broader net:**
- Nelson Mandela University (NMU / formerly NMMU)
- University of the Free State (UFS)
- North-West University (NWU)
- University of the Western Cape (UWC)
- Cape Peninsula University of Technology (CPUT)
- Durban University of Technology (DUT)
- Tshwane University of Technology (TUT)

**Tier C — Business schools (for finance/exec roles):**
- UCT Graduate School of Business (GSB)
- Wits Business School
- GIBS (Gordon Institute of Business Science) — University of Pretoria
- Henley Business School Africa
- Stellenbosch Business School (USB)

### Apollo University Search String
```
University of Cape Town OR UCT OR Witwatersrand OR Wits OR Stellenbosch OR University of Pretoria OR UKZN OR Rhodes University OR University of Johannesburg
```

### Sales Navigator University Filter
Add each university one by one in the "School" filter. SalesNav supports multi-select — add all Tier A + B universities.

---

## 2. South African Surnames (Apollo / name filtering)

South African surnames are highly distinctive across three main groups:

### Afrikaans Surnames (most common in SA tech/business)
```
van der Merwe, Botha, du Plessis, van Niekerk, Pretorius, Joubert, Steyn,
van der Walt, Venter, Swanepoel, Coetzee, Kruger, Erasmus, du Toit,
Vermeulen, Bezuidenhout, Breytenbach, Cilliers, de Villiers, Engelbrecht,
Fourie, Grobler, Hendriks, Jansen, Klopper, le Roux, Malan, Naude,
Olivier, Potgieter, Rautenbach, Scholtz, Theron, Uys, van Rensburg,
van Wyk, Visser, Wessels, Wolmarans, de Beer, van Zyl, Barnard,
Louw, Marais, Nel, Smit, Strauss, Terblanche, Viljoen, Lombard
```

### English South African Surnames
```
Henderson, Campbell, Mitchell, Robertson, MacKenzie, Murray, Gillespie,
Hamilton, Wallace, Stewart, Gordon, Patterson, Anderson, Thompson
```
*(Less useful — overlap with US/UK/AU names. Use only in combination with university filter.)*

### Zulu/Xhosa/Sotho Surnames (very high signal — uniquely SA)
```
Nkosi, Dlamini, Zulu, Ndlovu, Mkhize, Naidoo, Govender, Pillay,
Maharaj, Moyo, Sibanda, Khumalo, Cele, Ngcobo, Shabalala, Sithole,
Mthembu, Zungu, Maseko, Radebe, Molefe, Tshabalala, Buthelezi,
Mahlangu, Modise, Motsepe, Ramaphosa, Mbeki, Patel, Naicker,
Chetty, Reddy, Singh (SA-specific when combined with SA university),
Moodley, Padayachee, Nair, Munsamy, Govender, Pillay
```

### Apollo Name Search Strategy

**Method 1 — Last name search (highest precision):**
In Apollo "People" search, use the "Last Name" field with distinctive SA surnames:
- Start with Afrikaans: `Botha`, `du Plessis`, `van der Merwe`, `Pretorius`, `Coetzee`, `Joubert`, `Steyn`, `Venter`
- Then Zulu/Xhosa: `Nkosi`, `Dlamini`, `Ndlovu`, `Mkhize`, `Khumalo`
- Then SA Indian: `Naidoo`, `Govender`, `Pillay`, `Chetty`, `Moodley`

**Method 2 — Combine name + university (higher recall):**
Less distinctive names (Patel, Singh, Anderson) → combine with SA university filter to confirm origin.

---

## 3. South African Company Experience (Apollo / Sales Navigator)

### Well-Known SA Tech Companies (filter by "Past Company")

**SA Tech / IT Services:**
- Dimension Data (now NTT)
- Naspers / Prosus
- Takealot
- Superbalist
- Capitec (fintech banking)
- Discovery (InsurTech)
- Yoco (payments)
- Luno (crypto exchange — SA-founded)
- JUMO (fintech)
- Entersekt (security)
- Clickatell (messaging)
- Synthesis Software (now part of Accenture)
- DVT (software consultancy)
- BBD (software engineering)
- Britehouse
- EOH Holdings
- Altron
- Bytes Technology
- Sanlam
- Old Mutual
- Standard Bank
- FirstRand / FNB
- Absa (was Barclays Africa)
- Investec
- Nedbank
- Vodacom
- MTN Group
- Telkom SA
- Multichoice / DSTV
- Shoprite Holdings
- Woolworths Holdings (SA)
- Pick n Pay

**SA Consulting / Professional Services:**
- Allan Gray
- Bain & Company (Cape Town office)
- McKinsey (Johannesburg office)
- Deloitte South Africa
- PwC South Africa
- KPMG South Africa

### Apollo Past Company Filter
Add these companies in the "Past Company" field. People who worked at these and now live in the US are almost certainly South African.

### Sales Navigator "Past Company" Boolean
```
"Dimension Data" OR Naspers OR Prosus OR Capitec OR Discovery OR Takealot OR Yoco OR Luno OR JUMO OR Entersekt OR Clickatell OR "Standard Bank" OR FirstRand OR Investec OR Vodacom OR MTN OR Multichoice
```

---

## 4. Platform-Specific Search Playbooks

### Apollo.io — Complete Filter Setup

**Search 1: University-based (highest precision)**
```
Company HQ: United States
Company Size: 11-500 employees
Person Title: CEO, CTO, COO, CFO, VP Engineering, VP Operations,
             Head of HR, Head of People, Director of Engineering,
             Chief People Officer, Head of Finance
School: [All Tier A + B SA universities]
Industry: Technology, IT Services, Software, Financial Services,
          Professional Services, Marketing & Advertising
```
Expected results: 200-500 people

**Search 2: Surname-based (broader net)**
```
Company HQ: United States
Company Size: 11-500 employees
Person Title: [same as above]
Person Last Name: Botha OR "du Plessis" OR "van der Merwe" OR Pretorius
                  OR Coetzee OR Joubert OR Steyn OR Venter OR Nkosi
                  OR Dlamini OR Ndlovu OR Naidoo OR Govender OR Pillay
```
Expected results: 300-800 people (needs manual review — some names overlap with Dutch/Indian diaspora)

**Search 3: Past company experience**
```
Company HQ: United States
Company Size: 11-500 employees
Person Title: [same as above]
Past Company: [SA companies from list above]
```
Expected results: 100-300 people

**Combine & Deduplicate**: Export all three lists → merge in Clay/Excel → deduplicate by email/LinkedIn URL.

### Sales Navigator — Complete Search Setup

**Search 1: School filter**
```
Current company headcount: 11-500
Geography (current): United States
Function: Engineering, Operations, Finance, Human Resources, C-Suite
Seniority: CXO, VP, Director, Owner
School: University of Cape Town, University of the Witwatersrand,
        Stellenbosch University, University of Pretoria,
        University of KwaZulu-Natal, Rhodes University,
        University of Johannesburg
```

**Search 2: Boolean keyword search**
```
Profile language: English
Geography: United States
Title: (CEO OR CTO OR COO OR CFO OR "VP" OR "Head of" OR "Director")
Keywords: ("South Africa" OR "Cape Town" OR "Johannesburg" OR
           "Stellenbosch" OR "UCT" OR "Wits")
```
*This catches people who mention SA in their summary/experience even if school isn't listed.*

**Search 3: Past company + current US**
```
Past company: Naspers, Dimension Data, Capitec, Discovery, Vodacom,
              Standard Bank, Investec, MTN, Luno, Yoco
Geography (current): United States
Seniority: CXO, VP, Director, Owner
```

### Clay.com — Enrichment & Scoring Pipeline

**Step 1: Import**
- Import Apollo/SalesNav exports into Clay table
- Columns: Name, Title, Company, Company URL, LinkedIn URL, Email

**Step 2: Enrichment columns**
Add these Clay enrichment columns:
1. **Company headcount by country** (Clay + LinkedIn) → Look for SA employees
2. **Job postings** (Clay scraper) → Any jobs posted in South Africa?
3. **Company "About" page** (Clay scraper) → Mentions of "South Africa", "Cape Town", "remote team"
4. **Technologies used** (BuiltWith/Wappalyzer via Clay) → Tech stack popular in SA?

**Step 3: AI Scoring column**
Add GPT column with prompt:
```
Based on this person's background and their company information,
rate 1-10 how likely this company hires contractors or freelancers
in South Africa. Consider:
- Person's education/work history in South Africa
- Company size and industry
- Any mentions of remote work, offshore teams, or South Africa
- Company's tech stack and engineering needs
Return: score (1-10) and one-line reasoning.
```

**Step 4: Filter & Export**
- Score >= 7 → Tier 1 (immediate outreach)
- Score 5-6 → Tier 2 (second batch)
- Score < 5 → discard

**Step 5: Email waterfall**
Clay enrichment chain: Apollo → Hunter.io → Dropcontact → ZeroBounce verification

---

## 5. LinkedIn Boolean Searches (Copy-Paste Ready)

### Search for SA-origin C-levels in US
```
("South Africa" OR "Cape Town" OR "Johannesburg" OR "Durban" OR "Pretoria" OR "Stellenbosch")
AND (CEO OR CTO OR COO OR "co-founder" OR "VP Engineering" OR "VP Operations" OR "Head of")
AND ("United States" OR "San Francisco" OR "New York" OR "Austin" OR "Miami" OR "Los Angeles" OR "Boston" OR "Seattle" OR "Denver" OR "Chicago")
```

### Search for SA alumni groups / associations
```
("South African" OR "SABAN" OR "SA diaspora")
AND (CEO OR founder OR CTO OR "head of")
AND (technology OR software OR fintech OR SaaS)
```

### Search for companies mentioning SA remote teams
```
("remote team" OR "offshore" OR "distributed team")
AND ("South Africa" OR "Cape Town" OR "ZAR")
AND (CEO OR founder OR CTO OR "head of engineering")
```

---

## 6. Additional Signal Sources

### South African Diaspora Communities (for lead discovery)
- **SABAN** (South African Business Association Network) — LinkedIn group
- **South Africans in Tech** — LinkedIn group, ~15K members
- **SA Expats in USA** — Facebook group (200K+ members) — mine for founders
- **Cape Town tech meetups** alumni now in US — Meetup.com
- **YPO / EO chapters** — South African members in US chapters

### Job Boards with SA-US Corridor Signal
- **OfferZen** (SA's top dev job board) — companies posting here AND having US HQ
- **Careers24** — SA job board, filter by companies with international presence
- **Indeed South Africa** — US companies posting SA positions

### Conferences / Events
- **AfricArena** — tech conference connecting SA/Africa startups with US investors
- **SA Innovation Summit** — attendees who relocated to US
- **Web Summit** — SA-founded companies presenting

### Crunchbase / PitchBook
- Filter: Company HQ = US, Founder nationality/origin = South Africa
- SA-founded companies that moved HQ to US (common pattern: Cape Town → SF/NYC)
- These definitively have SA teams: Luno, Yoco alumni, Clickatell alumni

---

## 7. Volume Estimates & Campaign Plan

| Source | Method | Est. Contacts | Quality |
|--------|--------|---------------|---------|
| Apollo — University filter | School = SA universities + US HQ + C-level | 200-500 | Very High |
| Apollo — Surname filter | Last name = SA surnames + US HQ + C-level | 300-800 | High (needs review) |
| Apollo — Past company | Past employer = SA companies + US HQ + C-level | 100-300 | Very High |
| SalesNav — Boolean + School | Combined boolean search | 200-400 | High |
| Clay — Job posting enrichment | US companies posting SA jobs | 100-200 | Very High |
| Clay — Technographics | US companies using Deel/Remote paying in ZAR | 50-100 | Very High |
| **Total (deduplicated)** | | **~500-1000** | |

### Recommended SmartLead Campaigns

**Campaign 1:** `EasyStaff - US - SA Diaspora CLevel Mar26`
- Source: Apollo university + surname + past company (merged, deduped)
- Size: ~500 contacts
- Sequence: 4-step, English, emphasize ZAR savings + compliance

**Campaign 2:** `EasyStaff - US - SA Job Posters Mar26`
- Source: Clay job posting enrichment
- Size: ~150 contacts
- Sequence: 4-step, reference their SA job postings specifically

**Campaign 3:** `EasyStaff - US - SA Deel Users Mar26`
- Source: Apollo technographics (Deel/Remote.com users) + Clay SA employee enrichment
- Size: ~100 contacts
- Sequence: 4-step, competitor displacement angle

---

## 8. Messaging Angles for US→SA Corridor

### Primary angle: Cost savings
> "Companies with contractors in South Africa typically save 40-60% vs US rates while getting same-timezone English-speaking talent. But payment logistics eat into those savings — Deel charges $49/contractor/month with hidden FX fees. We charge less with transparent pricing and same-day ZAR payouts."

### Secondary angle: Compliance
> "Paying contractors in South Africa? SARS compliance and B-BBEE requirements can be tricky. We handle all local paperwork, tax documentation, and ensure your contractor payments comply with SA regulations — so you don't have to."

### Tertiary angle: Speed + human support
> "No annual contracts, same-day payouts, USDT option available, and a real human answers when you need help — not a chatbot."

### Personalization hooks (for AI-generated sequences)
- Reference their SA university: "Fellow [UCT/Wits/Stellenbosch] alum here..."
- Reference their SA company experience: "I noticed you were at [Naspers/Dimension Data]..."
- Reference SA team members: "Noticed your team has engineers in Cape Town..."

---

## 9. Quick-Start Checklist

- [ ] Run Apollo Search 1 (university filter) → export CSV
- [ ] Run Apollo Search 2 (surname filter) → export CSV
- [ ] Run Apollo Search 3 (past company filter) → export CSV
- [ ] Merge all three CSVs in Clay → deduplicate by LinkedIn URL
- [ ] Add Clay AI scoring column → filter score >= 7
- [ ] Run email waterfall enrichment
- [ ] Verify emails with ZeroBounce
- [ ] Split into 3 SmartLead campaigns by source method
- [ ] Generate AI sequences using project templates
- [ ] Launch Campaign 1 (diaspora) first — highest expected conversion
