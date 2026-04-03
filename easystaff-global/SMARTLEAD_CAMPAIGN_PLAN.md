# SmartLead Campaign Plan — EasyStaff Global

## Status: READY TO EXECUTE (next session)

## Campaign Setup

**ONE campaign** with ALL Petr + Pavel sender inboxes (48 total from "Accounts infra" sheet).

### Sender Inboxes
- Source "Petr": 33 inboxes (petr@... and rinat@... domains)
- Source "Pavel": 15 inboxes (petr@... and rinat@... domains)
- All connected to ONE campaign, SmartLead rotates automatically

### Signature Variable
`{{sender_name}}` column in contact data:
- If inbox email starts with `petr@` → signature shows "Petr Nikolaev"
- If inbox email starts with `rinat@` or `rinat.k@` → signature shows "Rinat Karimov"
- SmartLead matches sender to contact row — signature in `{{sender_name}}` must align with inbox name

**IMPORTANT**: Since signature is removed from inbox level and set via contact column, SmartLead will use the `{{sender_name}}` value from the contact row. To make it work: contacts are split ~68% "Petr Nikolaev" / ~32% "Rinat Karimov" (matching inbox ratio). SmartLead assigns inboxes randomly but the signature in the email body matches whoever sends it via the built-in sender name tag.

**Actually simplest approach**: Use SmartLead's built-in `{{Sender Name}}` tag which auto-pulls from inbox settings. Re-add sender names to inbox settings instead of removing them. This guarantees alignment.

### Sequence (from campaign 3048388)

**Step 1** (Day 0) — Subject: `{{first_name}} – paying freelancers abroad?`
```html
Hi {{first_name}},<br><br>We at Easystaff help companies pay freelancers globally with fees under 1% – zero fees for your freelancers.<br><br>You can pay contractors via cards, PayPal, and USDT wallets – all paperwork handled by us.<br><br>Recently helped a {{city}} agency switch from Deel to paying 50 contractors across 8 countries, saving them $4,000/month on platform fees and exchange rates.<br><br>Would you like to calculate the cost benefit for your case?<br><br>{{Sender Name}}<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide
```

**Step 2** (Day 3):
```html
Hi {{first_name}},<br><br>Following up. Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility.<br><br>We offer a better way:<br>- Cut out the middleman: Save the 10-20% freelance marketplace fees<br>- No annual contracts: Pay only for what you use<br>- Same-day payouts to any country, real human support (no bots)<br>- One compliant B2B invoice for all freelancer payments<br><br>Open to a quick demo call this week?
```

**Step 3** (Day 7):
```html
Hi {{first_name}},<br><br>Just making sure my emails are getting through.<br><br>Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.<br><br>For 50+ contractors/month, we offer custom rates below any competitor.<br><br>Can I send you a 2-minute walkthrough video?
```

**Step 4** (Day 14):
```html
Would it be easier to connect on LinkedIn or Telegram?<br><br>If you already have a payment solution, happy to compare – many clients switch after seeing the total cost difference.<br><br>Sent from my iPhone
```

### Contact Columns to Upload

| Column | SmartLead Variable | Example |
|--------|-------------------|---------|
| email | (primary) | john@agency.com |
| first_name | {{first_name}} | John |
| last_name | {{last_name}} | Smith |
| company_name | {{company_name}} | Imperial Leisure |
| job_title | {{job_title}} | CEO |
| linkedin_url | {{linkedin_url}} | linkedin.com/in/... |
| domain | {{domain}} | imperialleisure.com |
| segment | {{segment}} | DIGITAL_AGENCY |
| city | {{city}} | London |
| email_source | {{email_source}} | apollo / findymail |
| sender_name | {{sender_name}} | Petr Nikolaev |

### Geo Case Study
ONE case study for all, just swap city:
> Recently helped a {{city}} agency switch from Deel to paying 50 contractors across 8 countries, saving them $4,000/month on platform fees and exchange rates.

City comes from the gathering run (which city the company was found in).

### Contact Data

**4,946 verified contacts** from 3,729 companies:
- Max 3 per company
- All verified emails (Apollo or FindyMail)
- Blacklisted against 46,341 campaign domains
- 308 companies already in active campaigns excluded

### SQL to Export

```sql
SELECT
  c.value->>'email' as email,
  split_part(c.value->>'name', ' ', 1) as first_name,
  CASE WHEN array_length(string_to_array(c.value->>'name', ' '), 1) > 1
    THEN split_part(c.value->>'name', ' ', 2) ELSE '' END as last_name,
  dc.name as company_name,
  c.value->>'title' as job_title,
  c.value->>'linkedin_url' as linkedin_url,
  dc.domain,
  dc.matched_segment as segment,
  -- city from gathering run
  CASE
    WHEN gr.notes LIKE '%London%' THEN 'London'
    WHEN gr.notes LIKE '%Dubai%' OR gr.notes LIKE '%UAE%' THEN 'Dubai'
    -- ... (map all cities)
  END as city,
  COALESCE(c.value->>'email_source', 'apollo') as email_source
FROM discovered_companies dc
JOIN company_source_links csl ON csl.discovered_company_id = dc.id
JOIN gathering_runs gr ON csl.gathering_run_id = gr.id,
  jsonb_array_elements(dc.company_info::jsonb->'contacts') c
WHERE dc.project_id = 9 AND dc.is_target = true
  AND (dc.in_active_campaign IS NULL OR dc.in_active_campaign = false)
  AND (c.value->>'is_verified')::boolean = true
  AND c.value->>'email' IS NOT NULL AND c.value->>'email' != ''
```

### SmartLead API Calls Needed

1. `POST /api/v1/campaigns/create` — create campaign
2. `POST /api/v1/campaigns/{id}/sequences` — add 4-step sequence
3. `POST /api/v1/campaigns/{id}/leads` — upload contacts with custom columns
4. `POST /api/v1/campaigns/{id}/email-accounts` — connect all 48 inboxes
5. Campaign settings: timezone, sending schedule, daily limit per inbox
