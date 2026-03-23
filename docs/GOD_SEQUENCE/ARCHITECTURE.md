# GOD_SEQUENCE — Campaign Intelligence System

**Purpose**: Learn from top-performing campaigns across all projects, extract reusable patterns, and auto-generate optimized sequences for new campaigns.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     DAILY (cheap, DB-only)                       │
│                                                                 │
│  1. SCORE ──── Query ProcessedReply + Campaign tables            │
│     │          Compute warm_reply_rate, meeting_rate per campaign │
│     v                                                            │
│  2. SNAPSHOT ── Freeze metrics + fetch sequences from SmartLead  │
│     │           Store in campaign_snapshots (one per campaign)    │
│     v                                                            │
│  [Weekly gate — only run extraction every 7 days]               │
│                                                                 │
│  3. EXTRACT ── Send top 20 campaigns to Gemini 2.5 Pro          │
│     │          AI identifies patterns across subjects, timing,   │
│     │          personalization, CTAs, tone, proof points         │
│     v                                                            │
│     campaign_patterns table updated                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│               PIPELINE STEP 10 (after people search)             │
│                                                                 │
│  4. GENERATE ── Load patterns + project ICP + sender identity    │
│     │           Send to Gemini → get 5-step sequence             │
│     v                                                            │
│  5. REVIEW ──── Operator reviews draft sequence                  │
│     │                                                            │
│     v                                                            │
│  6. PUSH ────── Create SmartLead campaign (DRAFT, no leads)      │
└─────────────────────────────────────────────────────────────────┘
```

## Integration with Gathering Pipeline

GOD_SEQUENCE is **Step 10** in the TAM gathering pipeline — right between FindyMail verification and SmartLead push:

```
... → STEP 9: FindyMail verification → STEP 10: GOD_SEQUENCE → STEP 11: SmartLead push
```

When the pipeline reaches the campaign creation step, instead of manually writing a sequence, the system:
1. Loads proven patterns from the `campaign_patterns` table
2. Loads the project's ICP, business context, sender identity
3. Generates an optimized 5-step sequence via Gemini 2.5 Pro
4. Operator reviews and approves before SmartLead campaign is created

---

## The Knowledge Base — What It Actually Contains

The knowledge base is the `campaign_patterns` table. Each row is one discrete, actionable pattern extracted from real campaign performance data.

### Real Patterns (seeded from EasyStaff Global)

These 11 patterns were extracted from 55 warm/qualified leads, 3,500+ total replies across 170 campaigns:

#### [subject_line] `first_name_dash_pain_point` (confidence: 92%)

> **Format**: `"{{first_name}} – paying freelancers abroad?"`
>
> Personal (first name), immediately relevant (pain point as question), short for mobile.
> The en-dash (–) is visually distinctive vs hyphen.
>
> Evidence: Karen Scorrano replied in 40 minutes. Muhammad Arshad in 50 minutes.
> Both from Step 1 with this format.

#### [body_structure] `four_paragraph_arc` (confidence: 88%)

> **Arc**: Hook → Value → Proof → CTA
>
> - P1 (Hook): "We at [Company] help companies [solve X] with [differentiator]"
> - P2 (Capability): 1-2 sentences, 2-3 specific methods
> - P3 (Proof): Case study with {{city}} + specific dollar savings
> - P4 (CTA): Soft question ("Would you like to calculate the cost benefit?")
>
> Under 150 words. No bullet points in Step 1 (save for Step 2).

#### [timing] `day_0_3_4_7_7` (confidence: 95%)

> **Cadence**: Day 0 → Day 3 → Day 4 → Day 7 → Day 7
>
> Step reply distribution from 36 warm leads:
> - Step 1: 25% (impulse buyers)
> - Step 2: **31%** (competitor-frustrated)
> - Step 3: 14% (price-sensitive enterprise)
> - Step 4: **31%** (channel-preference leads)
>
> Steps 2 and 4 tied at 31%. Don't skip any step — each catches a different buyer type.

#### [personalization] `city_in_proof_paragraph` (confidence: 85%)

> Use {{city}} in the proof paragraph, NOT in the greeting.
>
> Good: "Recently helped a {{city}} agency switch from Deel..."
> Bad: "Hey, I noticed you're based in {{city}}!"
>
> James Martin (Blue Ocean Angels, Sydney) booked same-day meeting after reading about "a Sydney company."

#### [cta] `cost_calculation_question` (confidence: 82%)

> Step 1 CTA offers value, doesn't ask for time.
>
> Best: "Would you like to calculate the cost benefit for your case?"
> Each step has a different CTA — never repeat the same pattern.

#### [tone] `casual_professional_no_hype` (confidence: 90%)

> Write like texting a business contact. Short sentences. Specific numbers.
>
> NEVER use: revolutionary, cutting-edge, game-changing, seamless, robust, leverage.
> Step 4's "Sent from my iPhone" is the most casual element — triggers 31% of warm replies.

#### [proof_point] `competitor_displacement_story` (confidence: 91%)

> Step 2: Name the competitor they're switching FROM.
>
> "Many companies we talk to are moving off Upwork or are frustrated with Deel's inflexibility."
> 90-100% of qualified leads already use something. Naming creates instant recognition.
>
> Avanish Anand (CEO) forwarded Step 2 to product lead: "Pls discuss." — triggered by competitor naming.

#### [opener] `direct_value_statement` (confidence: 87%)

> Open with what you DO, not who you ARE.
>
> Good: "We at Easystaff help companies pay freelancers globally with fees under 1%"
> Bad: "My name is Petr and I'm the BDM at Easystaff, a leading global payroll platform"

#### [sequence_flow] `escalation_from_value_to_empathy` (confidence: 93%)

> 5-step escalation: Value → Competition → Price → Channel → Empathy
>
> Each step serves a different purpose. Steps 2-5 use EMPTY subject (thread as replies).
> Step 4's "Sent from iPhone" is a deliberate pattern-break.

#### [objection_preempt] `pricing_transparency_step3` (confidence: 84%)

> Show exact pricing in Step 3, not behind a call.
>
> "From 3% or a flat $39 per task. Free withdrawals. Mass payouts via Excel upload."
> Enterprise buyers self-identify with: "For 50+ contractors/month, custom rates."
> Adam Naser (45 roles RFP) replied to Step 3 because he saw volume pricing.

#### [proof_point] `specific_savings_number` (confidence: 86%)

> Dollar amounts > percentages > adjectives.
>
> Good: "saving them $3,000/month on platform fees and exchange rates"
> Bad: "significant cost savings on your global payroll"
> Johannes Lotter (50 contractors) signed after seeing the math.

---

## How Sequence Generation Works

When `POST /api/campaign-intelligence/generate-sequence/` is called:

### Input

```json
{
  "project_id": 9,
  "campaign_name": "Petr ES Manchester-Edinburgh",
  "custom_instructions": "Focus on UK agencies, mention Deel displacement"
}
```

### What the system loads

1. **11 active patterns** from `campaign_patterns` (filtered by market)
2. **Project knowledge** from `project_knowledge` (ICP, outreach strategy, GTM)
3. **Project identity**: sender_name="Petr Nikolaev", sender_position="BDM", sender_company="Easystaff"
4. **Top-performing reference sequence** from `campaign_snapshots` (highest quality_score with sequences)

### What Gemini generates

A 5-step sequence in SmartLead format, applying all patterns:

```json
[
  {
    "seq_number": 1,
    "delay_days": 0,
    "subject": "{{first_name}} – paying contractors across Europe?",
    "body": "Hi {{first_name}},<br><br>We at Easystaff help companies pay freelancers globally with fees under 1% – zero fees for your freelancers.<br><br>You can pay contractors via cards, PayPal, and USDT wallets – all paperwork handled by us.<br><br>Recently helped a {{city}} agency switch from Deel to paying 30 contractors across 5 countries, saving them £2,200/month on platform fees and exchange rates.<br><br>Would you like to calculate the cost benefit for your case?<br><br>Petr Nikolaev<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide"
  },
  {
    "seq_number": 2,
    "delay_days": 3,
    "subject": "",
    "body": "Hi {{first_name}},<br><br>Following up. Many UK agencies we talk to are moving off Deel or are frustrated with high Upwork commissions.<br><br>We offer a better way:<br>- Cut out the middleman: Save the 10-20% freelance marketplace fees<br>- No annual contracts: Pay only for what you use<br>- Same-day payouts to any country, real human support (no bots)<br>- One compliant B2B invoice for all freelancer payments<br><br>Open to a quick demo call this week?"
  },
  {
    "seq_number": 3,
    "delay_days": 4,
    "subject": "",
    "body": "Hi {{first_name}},<br><br>Just making sure my emails are getting through.<br><br>Our pricing is transparent: from 3% or a flat $39 per task. Free withdrawals for freelancers. Mass payouts via Excel upload.<br><br>For 50+ contractors/month, we offer custom rates below any competitor.<br><br>Can I send you a 2-minute walkthrough video?"
  },
  {
    "seq_number": 4,
    "delay_days": 7,
    "subject": "",
    "body": "Would it be easier to connect on LinkedIn or Telegram?<br><br>If you already have a payment solution, happy to compare – many clients switch after seeing the total cost difference.<br><br>Sent from my iPhone"
  },
  {
    "seq_number": 5,
    "delay_days": 7,
    "subject": "",
    "body": "Hi {{first_name}},<br><br>I know you're busy and probably have a payment solution already.<br><br>But many UK agencies switch to us for better terms, real human support, and fewer issues with global payouts compared to Deel's rigid systems or Wise's hidden fees.<br><br>If improving international payments is still a goal, I'm here to help.<br><br>Petr Nikolaev<br>BDM, Easystaff<br>Trusted by 5,000+ teams worldwide"
  }
]
```

### Rationale (AI explains its choices)

> Applied `first_name_dash_pain_point` subject pattern with UK-specific pain point ("contractors across Europe").
> Used `four_paragraph_arc` body structure with £ currency for UK market.
> Timing follows proven `day_0_3_4_7_7` cadence.
> Step 2 names Deel and Upwork as UK-relevant competitors per `competitor_displacement_story`.
> Step 3 shows transparent pricing per `pricing_transparency_step3`.
> Step 4 uses "Sent from my iPhone" pattern-break per `sequence_flow` pattern.
> {{city}} placed in proof paragraph per `city_in_proof_paragraph` pattern.

---

## AI Models & Cost

| Stage | Model | Cost per Run |
|-------|-------|-------------|
| Pattern Extraction (weekly) | Gemini 2.5 Pro | ~$0.10-0.30 |
| Sequence Generation (on-demand) | Gemini 2.5 Pro | ~$0.05-0.10 |
| Fallback | GPT-4o-mini | ~$0.003-0.01 |

**Monthly estimate**: 4 extractions + ~10 generations = **~$1.60/month**

---

## Database Tables

| Table | Rows (est.) | Purpose |
|-------|------------|---------|
| `campaign_patterns` | 11+ (growing) | Extracted best practices, versioned |
| `campaign_snapshots` | 1 per campaign | Frozen performance + sequences |
| `campaign_intelligence_runs` | 1/week | Audit trail for extraction cycles |
| `generated_sequences` | On-demand | AI sequences awaiting review |

---

## API Endpoints

```
GET  /api/campaign-intelligence/scores/        — Live campaign ranking
GET  /api/campaign-intelligence/patterns/       — Knowledge base contents
GET  /api/campaign-intelligence/runs/           — Extraction history
POST /api/campaign-intelligence/refresh/        — Manual extraction trigger
POST /api/campaign-intelligence/generate-sequence/  — Generate for project
POST /api/campaign-intelligence/generated/{id}/approve/
POST /api/campaign-intelligence/generated/{id}/push/   — Create SmartLead DRAFT
POST /api/campaign-intelligence/generated/{id}/reject/
```

---

## Seed Script

To populate the knowledge base with real EasyStaff patterns:

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && docker exec leadgen-backend \
  python -m app.scripts.seed_campaign_patterns"
```

This seeds 11 patterns extracted from 55 warm leads, 3,500+ replies, 170 campaigns.
The weekly extraction cycle will update and expand these as new campaign data comes in.

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/models/campaign_intelligence.py` | 4 SQLAlchemy models |
| `backend/app/services/campaign_intelligence_service.py` | Core: score → snapshot → extract → generate → push |
| `backend/app/api/campaign_intelligence.py` | REST endpoints |
| `backend/app/scripts/seed_campaign_patterns.py` | Seed with real EasyStaff patterns |
| `backend/app/services/crm_scheduler.py` | Daily intelligence cycle |
| `docs/GOD_SEQUENCE/ARCHITECTURE.md` | This document |
