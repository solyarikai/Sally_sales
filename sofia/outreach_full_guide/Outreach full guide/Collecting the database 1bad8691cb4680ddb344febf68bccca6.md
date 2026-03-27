# Collecting the database

- **Check Ready-Made Segments**: if your segment exists, **copy it**. → [Sally bases](https://www.notion.so/201d8691cb468005b8dfcc31c8c6127b?pvs=21)
- **Define ICP async** (no call needed at first): geo, headcount, industry, roles, tech, exclusions, must-haves.
- Review the [conferences sheet](Collecting%20the%20database%201bad8691cb4680ddb344febf68bccca6.md)
- **Share the [ICP sheet](https://docs.google.com/spreadsheets/d/1r_NAFRnAlFRzbrhTUpyTh7416OLR7IhJU3ouiRRpaEI/edit?gid=1908117331#gid=1908117331)** with client and grant email access:
- **Only after “ICP: Approved”** → collect companies & contacts.

## **Primary account and contact sources**

## Primary Source: Apollo.io

- Best balance of coverage, contacts, UX, cost.
    
    [Apollo guide](Collecting%20the%20database/Apollo%20guide%201aed8691cb4680f6a1d6cae555a8b579.md)
    
- **Credit-smart flow**:
    1. Export **companies** (no people yet).
    2. Filter companies in **Crona** to ICP using web processing.
        
        [Crona ](Collecting%20the%20database/Crona%20265d8691cb4680bbb539f22d55202607.md)
        
    3. Pull **people** only from the filtered set.

## 3) Alt/Complementary Sources

- **Sales Navigator + PhantomBuster** (incl. events). → [How-to](https://www.notion.so/caed0db2805349d186a1f9e5c9adb2c6?pvs=21)
- **Waalaxy** (fast LI extraction; good free tier).
- **Crunchbase** (funding signals). → [Guide](https://www.notion.so/1b2d8691cb468040ad3cc3723ac7b942?pvs=21)
- Explee - has advanced ai filters [Explee](Collecting%20the%20database/Explee%2026cd8691cb4680bf8816e5f4d3e8e448.md)
- **Scripts** (domain finder):
    - If you **only have names**, first run the **domain script** to resolve each company’s domain → **then** add to **Apollo** for enrichment (people, emails).
    - [Scripts](https://www.notion.so/852fb2b5c94f43b2aaabd371aed2b69c?pvs=21)

## 4) Enrichment & Presets

- **Clay** for enrichment (emails, LI URLs, company info, competitors).
    - If you only have **LinkedIn profile URLs**, use Clay’s **LinkedIn Profile** block to pull name/title/company/location.
    - [Clay guide](Collecting%20the%20database/Clay%20guide%201b2d8691cb4680f79ab8da20aa8084f9.md)
- **Crona Presets** for reusable segment filters. → [Crona](Collecting%20the%20database/Crona%20265d8691cb4680bbb539f22d55202607.md). It’s our own software use it!

**Normalization (Crona + Sheets AI)**

**Have existing company list from Apollo/other?**

**Actively prospecting through web processing /Sales Navigator processing in crona?**
→ Use **Crona enrichers** 

**Key difference:** Crona normalizes as you prospect, Sheets normalizes existing data.

## 5) Finding & Validating Emails (mandatory)

- **Find emails**: **Clay** or **Findymail** (in Access).
    - How-to (Clay): [link](https://www.notion.so/118d8691cb46803fbc5fffccd69c04ba?pvs=21)
- **Validate** every list with **MillionVerifier** before sending.

**Flow:** Source → (If names-only: **Script → Apollo enrich**) → Enrich (Clay/Findymail) → **Verify (MillionVerifier)** → Send.

## 6) Mini SOP

1. Check **Ready-Made Segments**.
2. Align **ICP** in shared sheet.
3. **If names-only**: run **domain script**, then **enrich in Apollo**.
4. **Apollo** companies → refine in **Crona** → pull people.
5. Fill gaps via **Sales Nav + PhantomBuster / Waalaxy / Crunchbase**.
6. **Clay/Findymail** for emails → **MillionVerifier** to clean.
7. Hand off clean CSV to outreach.

[Clay guide](Collecting%20the%20database/Clay%20guide%201b2d8691cb4680f79ab8da20aa8084f9.md)

## Target Russian speaking contacts

<aside>
🧠

If you’re running outreach to Russian-speaking contacts — **great choice**

</aside>

We’ve consistently seen **higher conversion rates**

in this segment, so we strongly recommend including these profiles in your campaigns.

[How to Find Russian-Speaking Contacts (High-Converting!)](Collecting%20the%20database/How%20to%20Find%20Russian-Speaking%20Contacts%20(High-Conver%201ced8691cb4680f697d2fc74ae6bd5f1.md)

## Check the Base

## Filter your blacklist

### video guide

[Запись экрана 2025-10-13 в 18.44.46.mov](Collecting%20the%20database/%D0%97%D0%B0%D0%BF%D0%B8%D1%81%D1%8C_%D1%8D%D0%BA%D1%80%D0%B0%D0%BD%D0%B0_2025-10-13_%D0%B2_18.44.46.mov)

[Запись экрана 2025-10-13 в 19.08.01.mov](Collecting%20the%20database/%D0%97%D0%B0%D0%BF%D0%B8%D1%81%D1%8C_%D1%8D%D0%BA%D1%80%D0%B0%D0%BD%D0%B0_2025-10-13_%D0%B2_19.08.01.mov)

### formula

```jsx
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
                      "^https?://", 
                      ""
                    ), 
                    "^www\.", 
                    ""
                  ), 
                  "^(?:[^@/]+@)?([^/:?#]+)"
                ), 
                ""
              )
            ),
            "^www\.",
            ""
          ),
          LOWER(
            IFERROR(
              REGEXEXTRACT(
                REGEXREPLACE(
                  REGEXREPLACE(
                    IMPORTRANGE("1_SIp1a8QA4NyAf8bdsU9b1UhNMKI3EMljRbY7BWuBvw","Blacklist!A2:A"), 
                    "^https?://", 
                    ""
                  ), 
                  "^www\.", 
                  ""
                ), 
                "^(?:[^@/]+@)?([^/:?#]+)"
              ), 
              ""
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
                "^www\.", 
                ""
              ), 
              "^(?:[^@/]+@)?([^/:?#]+)"
            ), 
            ""
          )
        ),
        "^www\.",
        ""
      )
    ) > 0
  )
)
```

## Use crona segmentation

[Crona ](Collecting%20the%20database/Crona%20265d8691cb4680bbb539f22d55202607.md) 

Once you’ve exported a  base from any source — **don’t just trust it blindly**.

- **Use filters** on key columns like `Industry`, `Keywords`, or `Headcount`.
- **Check for match with your original targeting** — for example, filter by the keywords you used in Apollo to see how many companies actually match.
- Use **“does not contain” filters** to catch and remove irrelevant companies (e.g. based on stop-words like "Insurance", "Real Estate", "Logistics" — depending on your case).
- If you spot suspicious clusters — e.g. lots of empty fields or mismatched industries — dig deeper or flag it.

✅ Why this works better:

– Gives you **quantitative clarity** on the quality of your base

– Helps clean up irrelevant junk before launch

– Lets you adjust your Apollo query if needed

In addition to filtering in Google Sheets, it’s still worth manually opening a **random sample of ~20 company websites** from your base.

## Conferences

## Existing base

Conferences are a powerful source of **high-intent leads** — attendees are often actively exploring new solutions.

You can work with a base collected from past events 

[https://docs.google.com/spreadsheets/d/1ArNLCkDpiSYQZj5OnYio-QqlQznm0fyPr1oIpJV-YfA/edit?gid=1952588758#gid=1952588758](https://docs.google.com/spreadsheets/d/1ArNLCkDpiSYQZj5OnYio-QqlQznm0fyPr1oIpJV-YfA/edit?gid=1952588758#gid=1952588758)

<aside>
💡

Format: 

- **Full Name** – имя и фамилия
- **Job Title** – должность
- **Company Name** – название компании
- **Email** – рабочая почта
- **LinkedIn Profile** – желательно, но не обязательно
- **Country** – страна/регион (если известен)

- **Conference Name** – название конференции
- **Conference URL** – ссылка на сайт или страницу ивента
- **Conference Type** – офлайн / онлайн / гибрид
- Sector
- Country
- **Conference Date** – дата проведения
</aside>

## Conferences process

## The Main Decision: Is Your Client Attending?

### ✅ Your Client IS Attending the Conference

**Primary Goal:** Book face-to-face meetings at the event

**Your Action Plan:**

1. **Focus on Meeting Coordination** (Section 3)
    - Pre-book meetings before the event
    - Create shared calendar and communication group
    - Manage day-of logistics and follow-ups
2. **Use Conference App Messaging** (Section 2)
    - Send automated messages through the conference platform
    - Great for last-minute meeting requests
3. **Supplement with Online Research** (Section 1)
    - Build backup lists from LinkedIn and other sources

### ❌ Your Client is NOT Attending the Conference

**Primary Goal:** Build contact lists and reach out remotely

**Your Action Plan:**

1. **Use Conference App Messaging** (Section 2) - if the conference has a messaging system
2. **Focus on Online Research and Outreach** (Section 1)

---

## Section 1: Online Research & Outreach (Remote Strategy)

**Step 1: Scrape the conference**

*Scenario A: Direct People Scraping*

**What this looks like:**

- Conference website has a public attendee directory
- You can see individual names, job titles, and sometimes contact info
- LinkedIn Sales Navigator shows "People who attended [Conference Name]"
- Conference app displays attendee profiles directly

**Tools to use:**

- **PhantomBuster** - LinkedIn Events Attendees scraper
- **Octoparse** - Website scraping for public attendee lists
- **Waalaxy** - Quick LinkedIn profile extraction
- **Manual copying** - For smaller lists

**Step-by-step process:**

1. **Check the conference website**
    - Look for "Attendees," "Participants," or "Directory" sections
    - Some conferences show speaker lists, sponsor contacts, or networking directories
    - Use Octoparse to scrape if the list is large
    - Copy manually if it's a small list (under 50 people)
2. **Use the conference mobile app**
    - Download the event app if available
    - Many apps have attendee directories or networking features
    - Screenshot or manually copy contact information
    - Note: Some apps allow direct messaging (covered in Section 2)
    
    **Review these guides**
    
    [SBC **Summit conference scraping** (1)](Collecting%20the%20database/SBC%20Summit%20conference%20scraping%20(1)%20269d8691cb468028b5bbf6bebcd19bd4.md)
    
    ‣ 
    

*Scenario B: Company-First Scraping*

**What this looks like:**

- No direct attendee list available
- Conference shows sponsors, exhibitors, or speaking companies
- You can find companies but need to research people separately via apollo ([review)](Collecting%20the%20database%201bad8691cb4680ddb344febf68bccca6.md)

---

## Section 2: Conference App Messaging

### When to Use This

Use when the conference has its own app or website where attendees can message each other.

**Review these guides**

[SBC **Summit conference scraping**](Collecting%20the%20database/SBC%20Summit%20conference%20scraping%2025ad8691cb46808aa9c0c818a7433ea2.md)

‣ 

### Setup Process

**Step 1: Access the Conference Platform**

- Log in to the conference app/website
- Ensure you can access the attendee directory and messaging features

**Step 2: Filter Your Targets**

- Find people who match your ideal customer profile

**Step 3: Set Up Automated Messaging**

- Use Octoparse software in Standard Mode
- Create one short paragraph message (no line breaks)
- Set up duplicate protection to avoid messaging the same person twice
- Enable automatic sending with 5-second delays

**Message Template Example:**
"Hey [FirstName], saw you're at [Event]. We help [company type] improve [specific benefit]. Quick intro this week to see if there's a fit?"

---

## Section 3: In-Person Event Strategy (When Your Client Attends)

### Goal

Convert your presence at the event into qualified sales meetings through systematic pre-booking and day-of coordination.

### Pre-Event (2 Weeks Before to Day Before)

**Create Your Target List**

- Identify 50-150 priority companies attending
- Map out key contacts (CEOs, VPs, Business Development)

**Pre-Book Meetings**

- Start LinkedIn outreach 2 weeks early
- Send targeted emails to key prospects
- Create a simple one-page company overview
- Prepare a 30-second pitch about your services

**Set Up Operations**

- Create a shared calendar with your client
- Set up a group chat (Telegram/WhatsApp) for real-time coordination
- Create a tracking sheet with: Company | Contact Name | Job Title | Meeting Time | Location | Owner | Status | Next Steps

### During the Event (Each Day)

**Morning Coordination (10 minutes)**

- Review who you must meet today
- Confirm times and locations
- Identify gaps and fill with last-minute outreach

**Meeting Management**

- Every meeting gets a calendar invite
- Send reminders 30, 15, and 5 minutes before each meeting
- Coordinate via group chat if people are running late

**Capture Information Quickly**
After each conversation, note:

- What they need
- Any objections or concerns
- What they committed to
- Next steps
- Who owns the follow-up

### After the Event (1-5 Days Later)

- Send same-day or next-day follow-up emails with meeting recap
- Move contacts into your regular outreach sequences
- Attempt to reschedule no-shows (2 attempts max)
- Update tracking sheet with qualification status and next steps

---

## Another high intent sources

[Explee](Collecting%20the%20database/Explee%2026cd8691cb4680bf8816e5f4d3e8e448.md)

[Apify](Collecting%20the%20database/Apify%20230d8691cb46808ab9e0d65e528c081c.md)

[Outscraper guide](Collecting%20the%20database/Outscraper%20guide%20209d8691cb468051a1f7ddb2f794a381.md)

[Untitled](Collecting%20the%20database/Untitled%201f3d8691cb46800583bbc571f987f14e.csv)

[Cursor](Collecting%20the%20database/Cursor%202f5d8691cb468042b9a2d023786a42ed.md)