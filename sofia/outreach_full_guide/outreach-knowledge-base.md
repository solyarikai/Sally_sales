# Outreach Full Guide — Knowledge Base

> Полная база знаний по B2B-аутричу. Собрана из всех документов для быстрого ориентирования агента.

---

# Оглавление

1. [Collecting a Database of Contacts](#1-collecting-a-database-of-contacts)
   - [Primary Source: Apollo.io](#primary-source-apolloio)
   - [Apollo Guide](#apollo-guide)
   - [How to Use AI in Apollo](#how-to-use-ai-in-apollo)
   - [How to Find Lookalike Companies in Apollo](#how-to-find-lookalike-companies-in-apollo)
   - [Crona (Segmentation & Enrichment)](#crona-segmentation--enrichment)
   - [Clay Guide](#clay-guide)
   - [Explee](#explee)
   - [Apify](#apify)
   - [Outscraper](#outscraper)
   - [Alt/Complementary Sources](#altcomplementary-sources)
   - [Finding Russian-Speaking Contacts](#finding-russian-speaking-contacts)
   - [Conferences](#conferences)
   - [High-Intent Sources (Links)](#high-intent-sources-links)
   - [Enrichment & Email Validation](#enrichment--email-validation)
   - [Mini SOP](#mini-sop)
2. [Writing the Sequence](#2-writing-the-sequence)
   - [Phase 1: Client Information Gathering](#phase-1-client-information-gathering)
   - [Phase 2: AI-Assisted Project Analysis (JTBD)](#phase-2-ai-assisted-project-analysis)
   - [Phase 3: Sequence Creation (Email 1, 2, 3 Prompts)](#phase-3-sequence-creation-with-claude)
3. [Email Outreach Setup](#3-email-outreach-setup)
   - [Email Validation](#1-email-validation)
   - [Setting Up Mailboxes](#2-setting-up-mailboxes)
   - [Smartlead Campaign Launch](#3-smartlead-campaign-launch)
   - [Managing Responses Outside SmartLead](#guide-to-managing-email-responses-outside-smartlead)
4. [LinkedIn Outreach Setup](#4-linkedin-outreach-setup)
   - [LinkedIn Setup & SSI](#1-linkedin-setup)
   - [Getsales Setup](#2-getsales-setup)
   - [Getsales to Sheets Automation](#getsales-to-sheets-automation)
5. [Telegram Outreach Setup](#5-telegram-outreach-setup)
   - [Telegram Automation Bot](#telegram-automation-bot-spambot)
6. [Best Practices](#6-best-practices)
7. [Common Mistakes to Avoid](#common-mistakes-to-avoid)

---

# 1. Collecting a Database of Contacts

## Pre-Work Checklist

- **Check Ready-Made Segments**: if your segment exists, **copy it**. → Sally bases (internal Notion link)
- **Define ICP async** (no call needed at first): geo, headcount, industry, roles, tech, exclusions, must-haves.
- Review the conferences sheet
- **Share the ICP sheet** (Google Sheets link: `1r_NAFRnAlFRzbrhTUpyTh7416OLR7IhJU3ouiRRpaEI`) with client and grant email access
- **Only after "ICP: Approved"** → collect companies & contacts.

---

## Primary Source: Apollo.io

Best balance of coverage, contacts, UX, cost.

**Credit-smart flow:**
1. Export **companies** (no people yet).
2. Filter companies in **Crona** to ICP using web processing.
3. Pull **people** only from the filtered set.

---

## Apollo Guide

### Video Guide
- Google Drive: `1FcQAqSShhC10B6DDWqCRVxHnh1HWdMHm`

### Apollo Company Cleanup Guide

**Step 1: Navigate to Companies Section**
Go to the Companies section in Apollo.

**Step 2: Configure List Filters**
In the list filter settings, add **all existing company lists** to the exclusion filter.

> ⚠️ Critical: Make sure to exclude ALL your existing lists before proceeding with deletion. This prevents accidentally removing companies you want to keep.

**Quick Method to Exclude Lists:**
1. Click on the empty space in the Exclude field with left mouse button (LMB)
2. Press Enter
3. Repeat this process quickly until all lists are excluded

**Step 3: Delete Unwanted Companies**
1. Select all remaining companies that aren't in any list
2. **Limit**: Select no more than **50,000 companies** at once
3. Click the three dots menu (...)
4. Select Delete

**Important Notes:**
- **Temporary Search Invisibility**: After deletion, companies may not appear in search results for up to **1 hour**.
- **Company Recovery Timeline**: Deleted companies will return to the search index within **24 hours** and become available for saving again.
- **Why This Matters**: Regularly cleaning up unused companies creates space for new entries in your Apollo database.

---

## How to Use AI in Apollo

1. Чтобы точно понять, какие фильтры выставить в Apollo, я прошу нейросеть найти **20 компаний, идеально подходящих под ICP**. Опираемся на свой сегмент.

> Лучше всего использовать наш Google AI Studio, он уже обучен и запомнил всю информацию по проекту.

2. Эти компании сохраняем в лист и выгружаем. Отправляем файл в нейросеть и просим выделить фильтры, которые встречаются **чаще всего.**
3. Выставляем фильтры в Apollo, опираясь на советы нейросети.

### Как использовать AI-промпт в Apollo

Нажимаем фиолетовую кнопку - **Run custom AI prompt**

**Настройки для промпта:** Select Prompt: Perplexity Sonar

Через нашу нейросеть просим переделать промпт под свой сегмент и вставляем в поле для промпта.

### Пример AI промпта для Apollo (ICP fit check)

```
"Is this company a good fit for [Client]'s [product/platform]?"

Evaluate whether the company {{account.name}} fits the Ideal Customer Profile (ICP) for [Client], which provides [description of product]. The platform targets companies involved in [target industry/activity], who can leverage their [asset] to [desired outcome].

The company is a good fit if it matches at least one of the following profiles:

✅ Profile 1: [Profile Name]
Companies that:
- [Criterion 1]
- [Criterion 2]
- [Criterion 3]
- Preferably have [size] employees

✅ Profile 2: [Profile Name]
Companies that:
- [Criterion 1]
- [Criterion 2]

🔍 What to Look For in description/domain/scraped info:
- Mentions of: "[keyword1]", "[keyword2]", "[keyword3]"
- Keywords like: [list of keywords]
- Signs they [behavior indicator]

✍️ Output Format: [Client]-fit: [Yes / No]
Explanation: Clearly state which profile the company aligns with and why.
```

**Workflow after AI filtering:**
1. Вручную, примерно на 20 компаниях, нужно проверить, правильно ли работает промпт. При необходимости поправить сам промпт.
2. Делаем поиск по людям в этих компаниях.
3. Сохраняем людей с проверенными и с не проверенными почтами отдельно.
4. Не проверенные почты загружаем в Clay для обогащения (Find Work Email enrichment).

---

## How to Find Lookalike Companies in Apollo

### What Does Lookalike Do?
In the **Company & Lookalikes** section, you enter 1-3 companies you're targeting. The AI finds similar businesses, which you can then filter further by industry, keywords, company size, etc.

### The Problem Before:
- **Too general keywords** resulted in many irrelevant companies.
- Some businesses list only **descriptions** and not keywords — searching through descriptions pulled up a lot of junk.

**Lookalike solves this**: The AI focuses on specific segments, instead of spreading the search too thin.

### How to Use It: Step-by-Step Plan
1. Go to corporate **GPT**, describe your company, ICP, and segment.
2. Ask it to find **10 companies** that perfectly match your offer.
3. Select the top 3, and upload them into Lookalike on Apollo.
4. Add filters: industries, keywords, roles, locations — whatever works best.
5. Get a list of highly relevant companies.

---

## Crona (Segmentation & Enrichment)

> Crona — наш собственный софт. Используй его!

Old name — Leadokol.

### 1) Web Processing

#### Segmentation

**Segmentation prompt example (Deliryo project):**

```
You are helping [Client] identify companies that could potentially partner with its [product].
[Client description and value proposition].

Your task:
Analyze the company information and suggest the most suitable segment from the list below.
If several categories might apply, choose the one that seems most relevant.
Provide a brief reasoning paragraph explaining your choice.

Segments:
SEGMENT_1 — [Description]
SEGMENT_2 — [Description]
SEGMENT_3 — [Description]
OTHER — Any business that does not clearly fit the above or has limited public information.

Guidelines:
- Focus on what the company mainly does
- Language or geography clues indicate likely relevance
- Be concise, objective, and confident in your reasoning

Output format:
Line 1: One segment name → [SEGMENT_1 / SEGMENT_2 / ... / OTHER]
Line 2: 2–3 sentences explaining your reasoning in plain English.

Input:
Website:
Website text:
```

**Filter code (exclude OTHER):**
```
!{{result.<your segmentation enricher name>}}.include?("OTHER")
```

#### Create Emails (via Crona)

Crona can generate personalized email bodies based on company sector. Use templates per segment with variables:
- `{company name}` — cleaned brand name (remove Ltd, Inc, LLC, etc.)
- `{property type}` / `{location}` / `{business vertical}` — from website content

**Strict requirements for email generation:**
- Use ONLY the template matching the exact sector
- Populate variables with contextual data
- Maintain original paragraph structure
- End with call-to-action question
- NO signatures, titles, or contact info
- NO text formatting (bold, italics, underlines)
- NO additional content beyond template

#### Create Subjects (via Crona)

Subject lines are generated per sector template with `{company name}` variable.

**Requirements:**
- Maximum 50 characters total
- Currency abbreviations in CAPS (USDT, BTC)
- NO exclamation marks
- NO words in ALL CAPS (except currencies)
- NO emoji or quotation marks

#### Find Email (via Crona)

Searches for email via Findyemail and verifies it in MillionVerifier. If the email is not verified, it will simply not be added.

> Use after filtering the base!

### 2) Sales Nav Processing

#### Getting the SN Link

**Method 1 — Search for contacts from scratch** (no company list):
- Video guide available on Google Drive: `1xIzD_thqrBDZH5TZ6ymSMDjdwtPnDq2e`

**Method 2 — Search from a list of companies (CSV file):**

> This method currently works only with 'sales nav for queries' account.

### 3) How to Run 25 Rows
Video guide available.

### 4) Find Person LinkedIn from Name, Then Find Website
Video guide available.

### Crona Enrichers

**Employee count:**
```
{{stats.employee_count}}
```

**Segmentation enricher (INXY example):**

```
gpt("You are a company classification analyst for [Client] solutions. Analyze the provided company website and classify it into ONE of the following segments based on their primary business need:

**SEGMENT_1** - [Description]
- [Example company types]

**SEGMENT_2** - [Description]
- [Example company types]

**SEGMENT_3** - [Description]
- [Example company types]

**OTHER** - Companies whose business model doesn't align
- [Examples]

**OUTPUT FORMAT:**
Classification: [SEGMENT_1/SEGMENT_2/SEGMENT_3/OTHER]
Reasoning: [One paragraph]

**GUIDELINES:**
- Choose the PRIMARY need based on their core business model
- Focus on their most critical payment flow challenge
- Consider transaction volume, frequency, and direction
- Use OTHER only when no clear need

---
Input
Website Link: {{company.website}}
Website Content: {{company.website_text}}")
```

**Segmentation prompt template (generic):**

```
gpt("
COMPANY_INFO:
- Company Name: [Your company name]
- Business Description: [Brief description]
- Competitive Landscape: [Competitors]

TARGET_SEGMENTS:
1. SEGMENT_1_NAME:
   - Description: [What this segment needs]
   - Examples: [10-15 example company types]

2. SEGMENT_2_NAME:
   - Description: [What this segment needs]
   - Examples: [10-15 example company types]

3. SEGMENT_3_NAME:
   - Description: [What this segment needs]
   - Examples: [10-15 example company types]

4. OTHER: Companies that don't fit or are competitors

GUIDELINES:
- FIRST CHECK: Is this company a direct competitor? If yes → OTHER
- Choose the PRIMARY need based on core business model
- Use OTHER for competitors AND companies with no clear need

INPUT_VARIABLES:
- Website Variable: {{company.website}}
- Content Variable: {{company.website_text}}
")
```

**Message generation enricher (INXY example):**

```
gpt("You are writing personalized outreach emails for [Client] solutions. Based on the company's offer type, strictly follow the appropriate template and fill it with relevant industry details. Use the appropriate currency based on the company's country location.

**TEMPLATE_1:**
[Email body template with {placeholders}]

**TEMPLATE_2:**
[Email body template with {placeholders}]

**CURRENCY LOCALIZATION RULES:**
- UK companies → use £ (GBP)
- EU/Eurozone → use € (EUR)
- US/Canada → use $ (USD)
- Switzerland → use CHF
- Default → use $ (USD)

**STRICT INSTRUCTIONS:**
- Use ONLY the template that exactly matches the offer type
- Replace ONLY the bracketed placeholders
- Use realistic amounts in the correct currency
- Do NOT add greetings, signatures, subject lines
- Do NOT add formatting like bold, headers, or labels
- MAINTAIN all empty lines and paragraph spacing

---
Input Company
Offer type: {{result.offertype}}
Website link: {{company.website}}
Website content: {{company.website_text}}")
```

**Subject generation enricher:**

```
gpt("You are writing personalized email subject lines for [Client] solutions. Based on the company's offer type and business vertical, use the appropriate template.

**SUBJECT TEMPLATE per offer type:**
[Template with {country} {business vertical} placeholders]

**STRICT INSTRUCTIONS:**
- Use ONLY the template that matches the offer type
- Extract country and business vertical from the email message
- Output only the subject line

---
Input Company
Website link: {{company.website}}
Offer type: {{result.offertype}}
Email message: {{result.message}}")
```

### Crona FAQ

#### Базовые операции

**Check if a field is empty:**
```
{{company_website?}}
```
Returns true if the field is not empty.

**Access nested fields (after Sales Navigator processing):**
```
{{<company_linkedin_details_column>.company_website}}
```

**Access simple numeric/text fields:**
```
{{stats.employee_count}}
{{hq.state}}
```

#### Работа с энричерами

**Фильтрация по результатам энричера (true/false):**
```
{{result.callAi6?}}
```
Только строки с true проходят дальше по workflow.

**Исключение определенных сегментов:**
```
!{{result.callAi4}}.include?("OTHER")
```
`!` — инверсия условия (NOT), `.include?()` — проверка вхождения подстроки.

**Замена текста (A/B тесты):**
```
{{result.polishedFlame}}.sub('old CTA text', 'new CTA text')
```
Идеально для A/B тестов с разными CTA. Не нужно создавать отдельный энричер!

#### Типичный Workflow

```
1. Scrape Website → получаем company_website
   Filter: {{company_website?}}

2. Call AI (Segmentation) → получаем сегмент компании
   Filter: !{{result.callAi4}}.include?("OTHER")

3. Call AI (ICP Check) → проверяем соответствие роли
   Filter: {{result.callAi6?}}

4. Add Code → извлекаем доп. данные
   {{stats.employee_count}}
   {{hq.state}}

5. Call AI (Message Generation) → генерируем сообщение
   Result: polishedFlame

6. Add Code (A/B Test) → заменяем CTA
   {{result.polishedFlame}}.sub('old CTA', 'new CTA')
```

#### Извлечение email адресов с сайта

**Все email адреса через запятую:**
```
{{company.website_text}}.scan(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/i).uniq.join(", ")
```

**Первый email адрес:**
```
{{company.website_text}}[/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/i]
```

#### Извлечение номеров телефонов с сайта

**Все номера через запятую:**
```
phone_regex = /
  (?:\+?(\d{1,3})[\s\-\.]?)?
  \(?(\d{1,4})\)?[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,9})?
/x

{{company.website_text}}.scan(phone_regex).map do |match|
  match.compact.join
end.uniq.join(", ")
```

**Первый номер телефона:**
```
phone_regex = /
  (?:\+?(\d{1,3})[\s\-\.]?)?
  \(?(\d{1,4})\)?[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,4})[\s\-\.]?
  (\d{1,9})?
/x

match = {{company.website_text}}.scan(phone_regex).first
match ? match.compact.join : nil
```

### Crona — Get Info from LinkedIn URL Script

**To get the website:**
```
{{<company_linkedin_details_column>.company_website}}
```

**To get the company name:**
```
{{<company_linkedin_details_column>.company_name}}
```

### Crona Examples & Templates

Section contains high-quality benchmark examples that can be added to your account as projects upon request to your operations manager. Templates are designed to help streamline B2B outreach with enrichment and filtering processes applied based on your files.

### Crona Archive

- Old name: Leadokol
- Archive links: Notion (sally-saas), Google Drive, Google AI Studio

---

## Clay Guide

We generally use Clay through **trial accounts** because it's more cost-effective. Instead of having one corporate account, we create multiple new accounts to extend trial periods and optimize credit usage.

### How to Log Into a New Clay Account from the Same Device

1. **Create a separate Google account in a separate Chrome profile** and use it to log into Clay for the new profile.
2. **Use Dolphin Anty browser** and register the new account **via Google login** — this method works reliably. Install: https://dolphin-anty.com/ru/

### Hack: How to Get More Credits on Clay's Free Plan

1. Message Clay support asking for extra credits before buying a subscription:

```
Hi,
Could you please provide me with a small amount of credits to try out your service before I purchase a subscription?
I'd really appreciate it, especially since my previous credits were accidentally spent due to the auto-update function.
```

2. The bot will ask if this was an unexpected expense — reply **Yes**.
3. Specify how many credits you need. Some users got 200 instantly and up to 1000 after a short wait with an operator.
4. The bot will send you a guide on how to avoid wasting credits (like turning off Auto Update).

### Clay Tech Stack — Find Companies by Tech Stack via HG Insights

1. **Create a New Workbook in Clay** → click "New Workbook" → "All Sources."
2. **Select Data Source**: Search for and select "Companies by Tech Stack with HG Insights."
3. **Apply Filters**: Set filters based on product/technology name, vendor/company.
4. **Export the List** of companies.
5. **Upload to Apollo**: Import company list into Apollo, use Apollo to find and enrich contacts.

### Clay — How to Scrape Person's LinkedIn Posts
Video guides available.

### Clay — How to Find People from Companies
Video guide available.

### Clay — Find Work Email Enrichment

1. In Clay, click **New → Workbook → Import from CSV**. Upload your file.
2. Create a **Full Name** column: `{{First Name}} + " " + {{Last Name}}`
3. Click **Add Enrichment → Find Work Email**.
4. Map all values inside the enrichment settings (Person's Name → Full Name, etc.).
5. Wait for results, then export CSV with found emails.

---

## Explee

Explee — has advanced AI filters for company search.

### How to Use

**Video guides available** (Google Drive: `1hAMAR1uLMJOJCnhXhvsJodZxIzUHVtsq`)

### Filters

The slider adjusts the "strictness" of requirements and matches. Best to turn it to the right so as not to collect unsuitable items, or at least to the middle.

### Console Script (Explee Auto Parser v2.4)

**How to run:**

1. Run the setup code first (paste the full ExpleeAutoParser class code into browser console).
2. Then call:
```javascript
parser.parseAuto(1, 500)
```
`(1, 500)` = employee range to scrape.

**Scrape in batches** — run the function multiple times with non-overlapping ranges:
```javascript
parser.parseAuto(1, 500)
parser.parseAuto(501, 1000)
parser.parseAuto(1001, 2000)
```

**Key commands:**
```javascript
parser.parseAuto(1, 500)                    // basic launch
parser.parseAuto(1, 500, 100, 3000, 5000)   // with custom delays
parser.continueFromProgress()               // continue from saved progress
parser.showProgress()                       // show progress
parser.clearProgress()                      // clear progress
```

**Features of Parser v2.4:**
- CSV output instead of JSON (UTF-8 BOM for Excel)
- Auto-fill domain from email (excludes personal emails like gmail, outlook, etc.)
- LinkedIn ID → URL conversion
- Rate limit protection (429) with auto-retry (3 attempts, exponential backoff: 30s → 60s → 120s)
- Progress saving to localStorage after each range
- Continue from any saved point
- Smart delays with jitter (±30% variance)
- Partial results auto-save
- Duplicate removal by domain

**Crona — Get info from LinkedIn URL (for Explee data):**
```
{{<company_linkedin_details_column>.company_website}}
{{<company_linkedin_details_column>.company_name}}
```

---

## Apify

Video guide: Loom link `0d7bf30def5e4a46bf303c70c3dbe5b8`

### How to Scrape Glassdoor
- Link to the actor: `https://console.apify.com/actors/t2FNNV3J6mvckgV2g/input`
- Video guide available.

---

## Outscraper

**Outscraper** is a powerful tool for scraping public data — especially from **Google Maps**. It lets you pull detailed business info like name, website, email, phone number, rating, and address — all in bulk.

### What You Can Use It For:
- Collect lists of local businesses (e.g. "Clinics in Berlin", "Marketing agencies in Stockholm")
- Extract emails, websites, and phone numbers from Google Maps
- Scrape apps from the App Store or Google Play
- Use the API to automate data collection at scale

### How to Use It (3 Simple Steps):
1. Go to outscraper.com and choose a service — usually **Google Maps Data Extractor**.
2. Enter your keywords (like "real estate agents in Miami") and select the location.
3. Click start — in a few minutes you'll get a CSV file with all the business data.

### Emails & Contacts Scraper:
1. **Prepare Your Input**: Create a list of domains or URLs.
2. **Access the Service**: Navigate to Emails & Contacts Scraper on Outscraper.
3. **Input Data**: Paste list or upload CSV/XLSX/TXT file.
4. **Configure Settings**: Adjust depth of search, types of contacts.
5. **Run the Task** and wait.
6. **Download Results**: emails, phone numbers, social media links.

Video walkthrough: `https://youtu.be/TRsQjqVR7m8`

---

## Alt/Complementary Sources

- **Sales Navigator + PhantomBuster** (incl. events)
- **Waalaxy** (fast LI extraction; good free tier)
- **Crunchbase** (funding signals)
- **Scripts** (domain finder): If you **only have names**, first run the **domain script** to resolve each company's domain → **then** add to **Apollo** for enrichment (people, emails).

---

## Finding Russian-Speaking Contacts

> Russian-speaking contacts consistently show **higher conversion rates**. We strongly recommend including these profiles in your campaigns.

### Method 1: Use the Existing Base

We already have a **shared internal base** of Russian-speaking contacts collected across various projects. Many of them have Telegrams.

- Sheet 1: `1UihgB6kMBXNTDlcx28WeihLmyDgrSuh1KaafP7yhQbk`
- Sheet 2: `1f-sFX3jSNmZ7u6iWtF1Ws9-TW06fsKBT-nBLuwL9RjA`

### Method 2: Crunchbase Search
Guide available in Notion.

### Method 3: Apollo Logic (Name-Based Search)

**Проблема:** Если базово прописать окончания русских фамилий, то Apollo будет искать по точным совпадениям, что не подходит.

**Решение:** Поставить символ `*` перед буквами — это отменяет точный таргетинг и в 70-80% случаев выдаёт релевантные русскоговорящие контакты.

**Список окончаний для поиска:**
```
Name:
*ov OR *ev OR *in OR *yn OR
*ovich OR *evich OR *sky OR
*skiy OR *ova OR *eva OR *ina OR *yna OR *skaya OR *skaia
OR *itsky OR *itskaya OR *enko OR *ko OR *chuk OR *yuk OR *yan OR *ian OR *dze OR *shvili
```

Video guide: Google Drive `1-ygjPMIsd5SFvUU4Th7ZZ-bnLQE0p8EX`

### Method 4: Apollo Logic with Octoparse
Combined approach using Apollo name search + Octoparse for scraping.

### Method 5: Clay Enrichment
Guide available in Notion.

### Method 6: Filtering by University (Sales Navigator Method)

Another highly effective method — filter through **education history** in **LinkedIn Sales Navigator**.

**Steps:**
1. Go to **Sales Navigator → Lead search**
2. Use the **"University"** filter
3. Paste in the name of a university from the list below

You can combine this with location, title (e.g. CTO, Co-Founder), and industry filters.

**University List (Russia, Belarus, Ukraine, Kazakhstan):**

**Russia:**
- Lomonosov Moscow State University
- Saint Petersburg State University
- Bauman Moscow State Technical University
- Novosibirsk State University
- Moscow Institute of Physics and Technology (MIPT)
- Tomsk State University
- Moscow State Institute of International Relations (MGIMO)
- National Research University Higher School of Economics (HSE)
- Ural Federal University
- Kazan Federal University
- ITMO University
- Russian Presidential Academy of National Economy and Public Administration (RANEPA)
- Peter the Great St. Petersburg Polytechnic University
- Moscow Power Engineering Institute (MPEI)
- National University of Science and Technology MISIS
- Tomsk Polytechnic University
- Southern Federal University
- Far Eastern Federal University
- Siberian Federal University
- Saint Petersburg Electrotechnical University "LETI"
- Moscow Aviation Institute (MAI)
- Samara National Research University
- Perm State University
- Saint Petersburg Mining University
- Moscow State Technical University of Civil Aviation
- Voronezh State University
- Nizhny Novgorod State Technical University
- Moscow Polytechnic University
- Irkutsk State University
- Kazan National Research Technological University
- Omsk State University
- Ufa State Aviation Technical University
- Tyumen State University
- North-Caucasus Federal University
- Volgograd State Technical University
- Bashkir State University
- Saint Petersburg State University of Economics
- Russian State University for the Humanities
- Saint Petersburg State University of Aerospace Instrumentation
- Moscow State University of Economics, Statistics, and Informatics

**Belarus:**
- Belarusian State University (BSU)
- Belarusian National Technical University (BNTU)
- Brest State Technical University
- Grodno State University
- Minsk State Linguistic University
- Belarusian State University of Informatics and Radioelectronics
- Belarusian State Economic University
- Belarusian State Technological University
- Gomel State University
- Polotsk State University
- Vitebsk State University
- Yanka Kupala State University of Grodno
- Francisk Skorina Gomel State University
- Belarusian-Russian University
- Mogilev State University

**Ukraine:**
- Taras Shevchenko National University of Kyiv
- National Technical University of Ukraine "Igor Sikorsky Kyiv Polytechnic Institute"
- Lviv Polytechnic National University
- Kharkiv National University
- Odessa National University
- Dnipropetrovsk National University
- National University of Kyiv-Mohyla Academy
- Sumy State University
- Donetsk National University
- Zaporizhzhia National University
- Ivan Franko National University of Lviv
- Chernivtsi National University
- National University of Life and Environmental Sciences of Ukraine
- Kyiv National Economic University
- Odesa National Polytechnic University
- Vinnytsia National Technical University
- Lviv National Medical University
- Poltava National Technical University
- Kharkiv Polytechnic Institute
- Uzhhorod National University
- Mykolaiv National University
- Bukovinian State Medical University
- National Mining University
- Zhytomyr Polytechnic State University
- Chernihiv National University of Technology
- National Aerospace University (KhAI)
- Kyiv National University of Construction and Architecture
- Dnipro Polytechnic University
- Ukrainian State University of Railway Transport
- Kyiv National University of Trade and Economics

**Kazakhstan:**
- Al-Farabi Kazakh National University
- Nazarbayev University
- Kazakh-British Technical University
- Eurasian National University
- Kazakh National Medical University
- KIMEP University
- Satbayev University
- Kazakh National Agrarian University
- Karaganda State Technical University
- South Kazakhstan State University
- Pavlodar State University
- Aktobe Regional State University
- Astana Medical University
- West Kazakhstan State University
- International Information Technology University (IITU)

---

## Conferences

### Existing Base
Conferences are a powerful source of **high-intent leads** — attendees are often actively exploring new solutions.

Existing conference base: Google Sheet `1ArNLCkDpiSYQZj5OnYio-QqlQznm0fyPr1oIpJV-YfA`

**Format:**
- Full Name, Job Title, Company Name, Email, LinkedIn Profile, Country
- Conference Name, Conference URL, Conference Type (offline/online/hybrid), Sector, Country, Conference Date

### The Main Decision: Is Your Client Attending?

#### ✅ Client IS Attending

**Primary Goal:** Book face-to-face meetings at the event.

**Action Plan:**
1. **Focus on Meeting Coordination** — Pre-book meetings, create shared calendar, manage logistics
2. **Use Conference App Messaging** — Automated messages through the conference platform
3. **Supplement with Online Research** — Build backup lists from LinkedIn and other sources

#### ❌ Client is NOT Attending

**Primary Goal:** Build contact lists and reach out remotely.

**Action Plan:**
1. **Use Conference App Messaging** (if available)
2. **Focus on Online Research and Outreach**

### Section 1: Online Research & Outreach (Remote Strategy)

**Step 1: Scrape the conference**

*Scenario A: Direct People Scraping*

When conference has a public attendee directory, LinkedIn events, or conference app with attendee profiles.

**Tools:** PhantomBuster, Octoparse, Waalaxy, Manual copying.

**Process:**
1. Check the conference website for "Attendees", "Participants", or "Directory" sections
2. Use Octoparse to scrape if the list is large, copy manually if under 50 people
3. Download the event app — many have attendee directories

*Scenario B: Company-First Scraping*

When no direct attendee list, only sponsors/exhibitors/speakers. Find companies then research people via Apollo.

**SBC Summit conference scraping guide:** Google Drive `1QL24oZBDtfJI5gI1zLsgAzz0Vj3_LeqF`

### Section 2: Conference App Messaging

**When to Use:** When the conference has its own app/website where attendees can message each other.

**Setup Process:**
1. Log in to the conference app/website
2. Filter targets matching your ICP
3. Set up automated messaging with Octoparse in Standard Mode
4. One short paragraph message (no line breaks)
5. Duplicate protection to avoid messaging same person twice
6. Automatic sending with 5-second delays

**Message Template Example:**
"Hey [FirstName], saw you're at [Event]. We help [company type] improve [specific benefit]. Quick intro this week to see if there's a fit?"

### Section 3: In-Person Event Strategy

#### Pre-Event (2 Weeks Before)
- Identify 50-150 priority companies attending
- Map out key contacts (CEOs, VPs, Business Development)
- Start LinkedIn outreach 2 weeks early
- Send targeted emails
- Prepare one-page company overview and 30-second pitch
- Create shared calendar, group chat (Telegram/WhatsApp), tracking sheet

**Tracking sheet columns:** Company | Contact Name | Job Title | Meeting Time | Location | Owner | Status | Next Steps

#### During the Event (Each Day)
- **Morning Coordination (10 min):** Review who to meet, confirm times/locations, fill gaps
- **Meeting Management:** Calendar invites, reminders at 30/15/5 min, group chat coordination
- **Capture Information:** What they need, objections, commitments, next steps, who owns follow-up

#### After the Event (1-5 Days Later)
- Same-day or next-day follow-up emails with meeting recap
- Move contacts into regular outreach sequences
- Attempt to reschedule no-shows (2 attempts max)
- Update tracking sheet

---

## High-Intent Sources (Links)

| Source | Sector | Comment |
|--------|--------|---------|
| cryptwerk.com | crypto | Online directory of merchants accepting crypto |
| playtoearn.com/blockchaingames | igaming | Blockchain games directory |
| theirstack.com | tech | Find companies' tech stack (BuiltWith analog) |
| lu.ma | crypto/AI | Side conferences + TG chats |
| cryptojobslist.com | web3 | Web3 job listings |
| web3.career | web3 | Web3 job listings |
| cryptocurrencyjobs.co | web3 | Web3 job listings |
| hirify.me | hiring | Hiring Russians abroad, fits 4dev/geomotv cases |
| t.me/+RQ3-RaMtSwA5YmQy | igaming | Telegram chat |

---

## Enrichment & Email Validation

### Finding & Validating Emails (mandatory)

- **Find emails**: Clay or Findymail
- **Validate** every list with **MillionVerifier** before sending

**Flow:** Source → (If names-only: Script → Apollo enrich) → Enrich (Clay/Findymail) → **Verify (MillionVerifier)** → Send.

---

## Check the Base

### Filter Your Blacklist

**Blacklist check formula (Google Sheets):**
```
=ARRAYFORMULA(
  IF(C2:C25="", "",
    COUNTIF(
      UNIQUE(
        FILTER(
          REGEXREPLACE(
            LOWER(
              IFERROR(
                REGEXEXTRACT(
                  REGEXREPLACE(
                    REGEXREPLACE(
                      IMPORTRANGE("1_SIp1a8QA4NyAf8bdsU9b1UhNMKI3EMljRbY7BWuBvw","Blacklist!A2:A"),
                      "^https?://", ""
                    ),
                    "^www\.", ""
                  ),
                  "^(?:[^@/]+@)?([^/:?#]+)"
                ), ""
              )
            ),
            "^www\.", ""
          ),
          LOWER(
            IFERROR(
              REGEXEXTRACT(
                REGEXREPLACE(
                  REGEXREPLACE(
                    IMPORTRANGE("1_SIp1a8QA4NyAf8bdsU9b1UhNMKI3EMljRbY7BWuBvw","Blacklist!A2:A"),
                    "^https?://", ""
                  ),
                  "^www\.", ""
                ),
                "^(?:[^@/]+@)?([^/:?#]+)"
              ), ""
            )
          ) <> ""
        )
      ),
      REGEXREPLACE(
        LOWER(
          IFERROR(
            REGEXEXTRACT(
              REGEXREPLACE(
                REGEXREPLACE(C2:C25, "^https?://", ""),
                "^www\.", ""
              ),
              "^(?:[^@/]+@)?([^/:?#]+)"
            ), ""
          )
        ),
        "^www\.", ""
      )
    ) > 0
  )
)
```

### Use Crona Segmentation

Once you've exported a base from any source — **don't just trust it blindly**.

- **Use filters** on key columns like `Industry`, `Keywords`, or `Headcount`.
- **Check for match with your original targeting** — filter by the keywords you used in Apollo.
- Use **"does not contain" filters** to catch and remove irrelevant companies (e.g. stop-words like "Insurance", "Real Estate", "Logistics").
- If you spot suspicious clusters — e.g. lots of empty fields or mismatched industries — dig deeper or flag it.

**Why this works better:**
- Gives you quantitative clarity on the quality of your base
- Helps clean up irrelevant junk before launch
- Lets you adjust your Apollo query if needed

In addition to filtering, manually open a **random sample of ~20 company websites** from your base.

---

## Mini SOP

1. Check **Ready-Made Segments**.
2. Align **ICP** in shared sheet.
3. **If names-only**: run **domain script**, then **enrich in Apollo**.
4. **Apollo** companies → refine in **Crona** → pull people.
5. Fill gaps via **Sales Nav + PhantomBuster / Waalaxy / Crunchbase**.
6. **Clay/Findymail** for emails → **MillionVerifier** to clean.
7. Hand off clean CSV to outreach.

---

# 2. Writing the Sequence

## Phase 1: Client Information Gathering

Before writing any sequences, collect **maximum information** from the client. Ideally, use an AI tool to generate a comprehensive questionnaire for outreach in their specific niche.

### Key Questions to Ask:

- **Who is the client?** (Company profile, industry, size)
- **Who is their ideal client?** (Demographics, psychographics, pain points)
- **Who is a bad fit client?** (Red flags, characteristics to avoid)
- **Who typically reaches out to them?** (Current client patterns)
- **Who do they want to attract?** (Target expansion)
- **Geographic data** (Location preferences, restrictions)
- **Demographics** (Gender, age, company size, etc.)
- **Any other relevant data** for database building, sequence descriptions, offers, etc.

---

## Phase 2: AI-Assisted Project Analysis

### Step 1: Generate JTBD and Roles

After gathering all client data, upload everything to Claude AI and ask it to study the project.

**Key Positions & Roles:**
- Which job titles are responsible for these decisions?
- What roles do we need to target?

### JTBD Prompt

```
You are an expert Business Analyst specializing in identifying Jobs-To-Be-Done (JTBD) for B2B decision-makers. Your task is to analyze a company's offering and target customer profile to generate a comprehensive list of specific tasks, goals, and challenges that the target persona faces in their role.

INPUT REQUIRED:

**[PROJECT DESCRIPTION]:** Brief overview of the client's company, their solution/service, and core value proposition. Their website.

**[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title, role, industry, and company characteristics of the target decision-maker.

YOUR TASK:

Generate 5-8 specific JTBD items that this exact ICP faces in their daily work that directly connect to the client's solution. Each JTBD must be:

- **Specific and Actionable** - Not vague pain points, but concrete tasks they need to accomplish
- **Role-Relevant** - Directly tied to their job responsibilities and KPIs
- **Solution-Connected** - Addressable by the client's offering
- **Business-Impact Focused** - Connected to measurable business outcomes
- **Current and Pressing** - Things they're actively dealing with, not hypothetical

OUTPUT FORMAT:

**[APPROVED JOBS-TO-BE-DONE - JTBD]:**

1. [Specific operational task they need to complete]
2. [Goal they're trying to achieve with current limitations]
3. [Process they need to optimize or streamline]
4. [Challenge they're facing in their current workflow]
5. [Metric/KPI they're struggling to improve]
6. [Resource/time constraint they need to overcome]
7. [Compliance/risk management task they must handle]
8. [Strategic initiative they need to execute]

EXAMPLE:

**Project:** Professional moving services with loyalty program for commercial real estate management companies
**ICP:** Property Manager at commercial real estate management companies

**[APPROVED JOBS-TO-BE-DONE - JTBD]:**

1. Earn commission through loyalty program referrals while providing value to tenants
2. Organize tenant relocations with minimal time investment
3. Adapt to changing moving schedules without additional costs or delays
4. Provide high-quality moving services to increase satisfaction and retention rates
5. Streamline tenant move-in/move-out processes to reduce operational complexity
6. Ensure safe handling and transportation of tenant property to avoid damage claims
7. Coordinate furniture/equipment relocations during office renovations without disruption
8. Improve tenant experience during transitions to enhance lease renewal rates
```

### Step 2: Client Approval

Present the JTBD and position list to the client for approval. Once confirmed, **responsibility shifts** — all future correspondence will be based on pre-approved information.

---

## Phase 3: Sequence Creation with Claude

Run these prompts in sequence:

### Email 1 — First Touch

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating the FIRST TOUCH EMAIL that generates responses from busy decision-makers.

**[THE CONTEXT & TASK]** I will provide you with:
1. **[PROJECT DESCRIPTION]:** Brief overview of our client's company and offering
2. **[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title and role we target
3. **[APPROVED JOBS-TO-BE-DONE - JTBD]:** Tasks, goals, challenges this ICP faces that our client solves

**[EMAIL #1 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`How are you currently {specific task from JTBD}?

At {Company Name}, we {specific solution for their JTBD}. {Brief explanation how it works} + {concrete metric/proof}.

Would you be open to a 15-minute call to explore how we can {solve their specific JTBD task}?`

**[FILLING PRINCIPLES]**

* Each sentence under 20 words
* Concrete numbers and metrics mandatory
* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.
* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.
```

**Example output (Crypto):**

```
How are you currently managing royalty payouts to your avatar creators and handling payments from a global user base?

At Inxy, we offer a powerful API to automate mass payouts and a simple Paygate for crypto acceptance, all under our EU/Canadian regulatory licenses.

Would you be open to a 15-minute call to explore how we can streamline this for you?
```

**Example output (Moving services):**

```
How are you currently handling tenant relocations at {target company}?

At Royal Moving & Storage, we handle the full process — from packing to delivery — with licensed crews across LA. 98% damage-free track record.

Would you be open to a 15-minute call to explore how we can simplify this for you?
```

### Email 2 — Follow-Up

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating a FOLLOW-UP EMAIL that adds value and continues the conversation.

**[EMAIL #2 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`Quick note on {main aspect of the solution}.

{Operational advantage/efficiency benefit}. {Concrete metric/example with specific numbers and timing}.

{Analogy or comparison that makes the advantage clear}.

Open to a 20-minute call next week to {specific action related to JTBD}?`

**[FILLING PRINCIPLES]**
* Focus on operational efficiency/speed/process advantages
* Include concrete timings and numbers
* Show competitive advantage through efficiency
* Brevity and Scannability
* No Fluff
```

**Example output (Crypto):**

```
Quick note on automated royalty distribution.

Our system processes 10,000+ creator payouts in under 2 minutes, while manual systems typically take 3-5 business days per batch.

Think of it like having a dedicated finance team that never sleeps - handling all your creator payments instantly across 40+ countries.

Open to a 20-minute call next week to walk through your current payout workflow?
```

### Email 3 — Final Follow-Up

```
PROMPT #3: FINAL FOLLOW-UP EMAIL GENERATOR (Email #3)
You are a world-class B2B Outreach Strategist. Your expertise is in creating a FINAL FOLLOW-UP EMAIL that addresses specific competitive advantages.

**[EMAIL #3 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`One last thought on {main solution topic}.

We solve the {number} problems where most {competitors/alternatives} fail: {problem #1} ({concrete result/timing}) and {problem #2} ({specific advantage}).

If either sounds familiar, worth a quick {adjective} chat?`

**[FILLING PRINCIPLES]**
* Maximum short format
* Two concrete problems where you outperform competitors
* Confident, casual tone
* Very low-pressure CTA
* Brevity and Scannability
* No Fluff
```

**Example output (Crypto):**

```
One last thought on creator payment management.

We solve the 2 problems where most payment solutions fail: cross-border compliance (we handle 40+ jurisdictions automatically) and transaction speed (payouts in 2 minutes vs 3-5 days).

If either sounds familiar, worth a quick informal chat?
```

### Personalization Reminder

After generating these email templates, add more personalization — at least use the name of the company you are targeting:

```
How are you currently {specific task from JTBD} at **{target company}?**
```

---

# 3. Email Outreach Setup

## 1. Email Validation

- Find emails with **Clay** or **Findymail**.
- **Always** run lists through **MillionVerifier** before sending — even if sourced from trusted tools.
- **Why:** protects deliverability, lowers bounces, avoids spam issues; tools like **Smartlead** penalize dirty lists.
- **Flow: Source → Verify (MillionVerifier) → Send.**

## 2. Setting Up Mailboxes

If you need to set up email accounts, reach out to our **head of infra** — they'll handle everything: creating domains, inboxes, and getting everything connected.

We also take care of **warming up the domains** right away, so no deliverability issues later.

**Important:**
- When setting up outreach inboxes, **always add a proper email signature** — this often gets forgotten.
- If needed, **upload a profile photo** to make the account look real and trustworthy. These small details boost deliverability and response rates.

## 3. Smartlead Campaign Launch

### Campaign Naming Standard

```
{project} — {segment}
```
Example: "inxy — fintech"

### Pre-Launch Checklist

1. Ensure list is clean and email sequences are solid.
2. Drop sequences into the **#review-sequences Slack channel** for team review.
3. Only launch after review approval.

### Learning Resources
- Smartlead YouTube channel: `youtube.com/watch?v=F_BVmCYcQqE`
- Smartlead University: `smartlead.ai/smartlead-university`

### Open Rates = Always 0%

We **don't track open rates**. All emails go out as **plain text** with **no tracking**. If you see 0% opens — that's expected and by design. This improves deliverability and reduces spam risk.

### Campaign Settings

- Timeout between emails: **15 minutes**
- Max daily first touches: increased from 100 to **500**
- First touch vs follow-up ratio: **60/40** — prioritize first touches
- Up to **50 emails from 1 inbox per day**
- Add the smart server from head of infra

### A/B Testing

Create 2 variations of your first message with different subject lines or slightly different copy. Smartlead auto-splits contacts between versions.

**Pro tip:** Only change *one thing at a time* (like the subject line), so you know exactly what made the difference.

### Stop Rule

After launching a campaign, if **500 emails** have been sent without receiving any **warm responses**, the campaign should be **immediately paused**.

### Duplicate Campaigns

If working with a similar segment or just tweaking messaging, use the **"Duplicate" feature** in Smartlead to save time.

### Tags

Set up tags for your campaigns inside Smartlead right from the start, so replies are sorted into dedicated folders.

### Subsequences

Video guide: `youtube.com/watch?v=s1U_ncY5fWE`

## Remove Old Leads from Smartlead (Every Friday)

1. **Export leads** — click "Download as CSV", add as new sheet in project's lead tracker.
2. **Name the sheet** after the campaign (exact same name as in Smartlead).
3. **Delete all leads** in the campaign view.
4. **Delete the campaign** to keep dashboard clean.

## Guide to Managing Email Responses Outside SmartLead

SmartLead sometimes misses responses from leads (different email addresses, forwarding errors).

**Solution:** Use an external email client (**Thunderbird** or **Spark**).
- Add all work emails to the client.
- Regularly check for replies outside of SmartLead.

**Why:** Full visibility of all responses, prevents missed warm replies.

### Antivirus Warning

Turn off your antivirus email check (especially Avast) to avoid **advertisement subscription** at the bottom of emails. Go to Avast settings and disable this option.

---

# 4. LinkedIn Outreach Setup

## 1. LinkedIn Setup

### Sync with the Client

Before starting, align with the client regarding account usage — sometimes you use the client's account, sometimes your own.

**Important:** Before launching any campaign, always **check the SSI (Social Selling Index)**. Every time a campaign is launched, **notify the head of operations** with the current SSI. **Add the SSI to the "SSI" column in the client's Google Sheet** before creating the capacity plan.

### LinkedIn Account Rental

**Use only with anti-detect browsers:** AdsPower, GoLogin, Dolphin Anty.

Cost: $135, contact @a_trif in Telegram.

### LinkedIn Premium Subscription

Discuss the subscription cost with the client. **Ask them to provide the accounts directly or agree on a refund if you're using your own.**

### Handling Low SSI

If you notice a low SSI, inform your client:

> "I noticed that your Social Selling Index decreased by 2 points (from 49 to 47). This may have happened because we sent a large number of invites, but only 20% were accepted.
>
> Since this is an important indicator for LinkedIn (affecting message limits and reducing the risk of being blocked), would you consider planning some content marketing activities on your page?
>
> It would be great if you could post on LinkedIn at least once a week."

---

## 2. Getsales Setup

### Proxy Setup

Each LinkedIn account must use its own dedicated proxy. Buy one proxy per account and always log in through that proxy — **no exceptions**. Regularly track your SSI.

### Connection Limit

Never send more than **200 connections per LinkedIn account per week**. Safe zone is 100-200. If your SSI is below 30, **limit connections to 100 per week**.

### Adding Contacts to Getsales

1. Go to Lists → Create a list
2. Go to Import → click Import accounts → select your list
3. Go to Automation → click Add contacts
4. Select your list → click Select all

### How to Filter Contacts with Less Than 500 Connections

Video guide available.

### Automation & Tools

For automating LinkedIn outreach, we use **Getsales**. It helps manage connection requests, follow-ups, and profile visits while keeping everything personalized.

Guides: **Getsales YouTube Channel** (`youtube.com/channel/UCE-wJ2-PDodhHls8kVPx0BA`)

**Key notes:**
- **Withdrawal Queue:** Reduce pending invitations regularly. High pending queue → restrictions or bans. Withdraw invites not accepted after 1-2 weeks.
- **Connection Rate:** Keep balance between invitations and removals.

### Optional Tool: LinkedHelper

Alternative/additional tool for LinkedIn automation.

---

## Getsales to Sheets Automation

Replies from Getsales automations will be appended/updated in your Google Sheet.

### Part 1 — n8n Setup

1. **Create workflow from template:** In n8n search "Getsales reply example" and duplicate it. You'll see 3 nodes: Webhook → Execution Data → Append or update row in sheet.

2. **Configure Google Sheets node:**
   - Operation: `Append or Update Row`
   - Document: select your Google Sheet
   - Sheet: choose the exact tab
   - Mapping Column Mode: `Map Each Column Manually`
   - Column to match: unique key (commonly `Linkedin`)

3. **Map columns (Expressions only):**
```
Linkedin (match): {{ $('Webhook').item.json.body.contact.linkedin_url }}
first_name:        {{ $('Webhook').item.json.body.contact.first_name }}
last_name:         {{ $('Webhook').item.json.body.contact.last_name }}
reply_text:        {{ $('Webhook').item.json.body.last_message.text }}
reply_datetime:    {{ $('Webhook').item.json.body.last_message.sent_at }}
```

> How to find the right keys: click the Webhook node → Listen for test event, trigger a real reply in Getsales, and inspect the JSON payload.

4. **Copy the Production Webhook URL** from the Webhook node (not Test URL).

5. **Save & activate later.**

### Part 2 — Getsales Webhook

1. **Create a webhook in Getsales:**
   - Name: e.g. `n8n – Replies to Sheet`
   - Event: `Contact Replied` (or `Contact Replied LinkedIn Message`)
   - Target URL: paste the Production URL from n8n

2. **Add filters for automations:**
   - Click Add rule (for each automation)
   - Set header to **OR** (blue)
   - Select field: `Automation`, Operator: `==`, Value: your automation

3. **Single-automation safety check:** Confirm the "Not" toggle is white (disabled).

4. **Create** the webhook.

### Part 3 — Go Live & Test

1. **Activate** the n8n workflow.
2. Send yourself a message from one of the selected automations and reply.
3. Check n8n Executions → should be Success.
4. Check Google Sheet → verify new row.

### Field & Sheet Tips

- **Match column** must exist in the sheet and match the value you send.
- Keep header names stable (renaming requires remapping in n8n).
- Use ISO timestamps for easier filtering/sorting.

---

# 5. Telegram Outreach Setup

Telegram is an increasingly popular and effective outreach channel, especially in communities where LinkedIn or email might not get quick responses.

**Use cases:**
- Reach out to founders, marketers, or devs active in niche Telegram groups
- Message contacts directly after finding them on LinkedIn (if they list Telegram or use the same handle)

---

## Telegram Automation Bot (spambot)

### Quick Setup (macOS, VSCode)

```bash
# 1. Install dependencies
python3 -m venv .venv && source .venv/bin/activate && python install.py

# 2. Run the bot (ensure data.csv has contacts!)
python3 -m venv .venv && python spambot.py
```

ChatGPT guide: `chatgpt.com/share/6836173b-4cb8-800e-b007-affa3c48dfad`

### How the Bot Works

The bot is built with Python using **Telethon** (Telegram client library) and **aiogram** (Telegram bot framework).

**Architecture:**
- Uses Telegram API (API_ID: 1373613, API_HASH: 0ac5b3a05a14c3cb46330d974a52fb04)
- Each account uses its own **SOCKS5/HTTP proxy**
- Sessions stored in `./sessions/` folder
- Contacts loaded from `data.csv`
- Settings from `settings.json`

**Key parameters:**
- `sleep_time`: 30 minutes between batches
- `sleep_randomizer`: 15 minutes random variance
- `max_msg_day`: 15 messages per account per day
- Initial random delay: 30-300 seconds before starting

**Message sending logic:**
1. For contacts with phone numbers (`+` in username): imports contact, then sends message
2. For contacts with usernames: sends directly via username
3. Tracks `done` status in CSV
4. On PeerFloodError: counts flood errors, if >2 contacts SpamBot and stops
5. Random sleep between sends

**Bot commands (via Telegram bot):**
- `/set_group` — set the logging chat
- `/send` — start sending
- All incoming replies are forwarded to the log chat

### TG Troubleshooting

Video guide available.

---

# 6. Best Practices

### LinkedIn

- Don't go over daily connection limits — even on aged accounts, keep it under 50/day. Safe zone is 30-40.
- Avoid blasting the same exact message to dozens of people in a row. Add variation — change intros, angles, or at least the wording.
- Never use shady scripts or browser extensions — stick to trusted tools like Linked Helper. Unverified plugins = high risk of ban.
- Keep an eye on your **SSI (Social Selling Index)** and how people are reacting to your messages. If too many mark you as "Spam," LinkedIn will throttle or block you fast.
- Target carefully: send to people who are likely to be genuinely interested, and be polite. If LinkedIn flags your account, pause activity for a few days and slow down.

### Email

- The most common ban comes from your email provider (e.g. Google Workspace suspending outgoing mail for suspected spam).
- To avoid this:
  - **Always warm up inboxes**
  - **Ramp up gradually** — don't send hundreds of emails on Day 1
  - **Spread load across multiple inboxes/domains** — 50 emails from 5 accounts is safer than 250 from one
  - **Monitor complaints** — if someone asks to be removed, respect that immediately
- Stay respectful — there's a real person on the other end.

### Domain Reputation

- For heavy outreach, use a **secondary domain** similar to your main one (e.g. `company.co` or `trycompany.com` for cold emails).
- This protects your main domain's reputation.
- Still need to warm it up and send quality content.

### Handling Rejections

- **Short rejection ("not interested"):** Keep it polite and brief. Don't push back.
  > "Totally understand — thanks for getting back to me! If you ever need [your service] down the line, happy to reconnect."

- **"We already have a provider/solution":** Acknowledge positively, offer to stay in touch. Can ask if fully satisfied — read the tone first.
  > "Good to hear you're covered! If you ever need a backup option, happy to stay in touch."

- **"Send more info":** Not a yes, not a no. Send what they asked for + suggest follow-up.
  > "Here's a quick overview attached. Would be happy to discuss — would Friday or early next week work for a quick chat?"

  If they go quiet, follow up a few days later.

- **Angry reply or clear opt-out:** Stay professional. Remove them from your list.
  > "Sorry for the interruption — won't reach out again. Wishing you all the best!"

- **No response:** Most common. Don't take it personally. 1 main email + 2 follow-ups. After 3 touchpoints, try another channel (LinkedIn, call). Can revive cold leads months later with a new offer.

### What Separates High-Performing Campaigns

- **Solid preparation:** Clean lists, warmed-up domains, well-crafted messages. An agency spent 2 weeks personalizing for 500 contacts → 55% open rate, 15% reply rate.
- **Real personalization & value:** 100 custom emails with tailored insights → ~30% response rate, half turned into calls.
- **Multi-channel is king:** Email + LinkedIn combo works great. Send email, then LinkedIn follow-up: "Just sent you a quick note — wanted to make sure it didn't get lost."
- **Data-driven learning:** Constantly look at metrics and adjust. Test new angles. Informal tone and video intros are gaining traction.

---

# Common Mistakes to Avoid

- **Sending without checking your list** — low quality = low results or blacklisting.
- **Wall-of-text emails** — nobody reads long cold intros. Keep it short and sharp.
- **Tricking the reader** — fake "Re:" threads, misleading subject lines like "Your invoice." Gets opens but kills trust.
- **Skipping follow-ups** — most replies come on the 2nd or 3rd touch. Don't stop after one try.
- **Not learning** — what worked 2 years ago may not work today. Read, test, share insights, join sales communities (Reddit /r/sales, Telegram groups).

---

# Cursor

Запись встречи 27.01 (Google Drive: `19CSeRgZ6a26Y8ap1rf8voqL-FMTQ6e-3`)

---

> **Read the guide, you must. Outreach, do not attempt — unless you have.**
> Write, rewrite, you shall. Only then, press send.
> Protect your sender reputation, this will.
> Fail to prepare… in the spam folder, your emails will live. Forever.
