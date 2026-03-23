# GOD_SEQUENCE — Knowledge Base Snapshot

**Generated**: 2026-03-23 15:45 UTC
**Source**: EasyStaff Global — 55 warm leads, 3,500+ replies, 170 campaigns, 8 prompt iterations (V1→V8)
**Status**: Seed data — will be updated weekly by AI extraction from new campaign performance

---

## How It's Stored

Each pattern = 1 row in `campaign_patterns` table (PostgreSQL). The `description` field is the actual knowledge text that gets injected into the Gemini prompt when generating a new sequence.

```sql
SELECT id, scope_level, business_key, pattern_type, pattern_key,
       title, confidence, created_at
FROM campaign_patterns
WHERE is_active = true
ORDER BY scope_level, pattern_type;
```

---

## LEVEL 1: UNIVERSAL PATTERNS (scope_level='universal')

These apply to EVERY project — EasyStaff, Inxy, Mifort, anyone.

---

### Pattern #1: subject_line / first_name_dash_pain_point

**Confidence**: 0.92 | **Scope**: universal | **Channel**: email

```
Subject line format: "{{first_name}} – paying freelancers abroad?"

Why it works: Personal (first name), immediately relevant (pain point as question),
short enough for mobile preview. The en-dash (–) is visually distinctive vs hyphen.

Evidence: EasyStaff Global's top-performing subject across 170 campaigns.
Step 1 triggers 25% of all warm replies. Karen Scorrano replied in 40 minutes.
Muhammad Arshad replied in 50 minutes. Both from Step 1 with this subject format.

How to apply: "[Name] – [core pain as yes/no question]?"
Examples:
- "{{first_name}} – paying contractors in multiple countries?"
- "{{first_name}} – spending too much on Deel?"
- "{{first_name}} – managing remote team payments?"

DO NOT: Use generic subjects ("Quick question", "Following up"), clickbait,
or long subjects that get cut off on mobile.
```

---

### Pattern #2: body_structure / four_paragraph_arc

**Confidence**: 0.88 | **Scope**: universal | **Channel**: email

```
Step 1 body structure that generates 25% of warm replies:

Paragraph 1 (Hook): One sentence stating what you do + key differentiator.
"We at [Company] help companies [solve X] with [key differentiator]."

Paragraph 2 (Capability): 1-2 sentences expanding on HOW, listing 2-3 specific methods.
"You can [method 1], [method 2], and [method 3] – all [handled/managed] by us."

Paragraph 3 (Proof): Specific case study with numbers. Geography-personalized.
"Recently helped a [{{city}}] [industry] switch from [Competitor] to [result],
saving them $X/month on [specific cost category]."

Paragraph 4 (CTA): Soft question, not a calendar link.
"Would you like to calculate the cost benefit for your case?"

Key metrics:
- Total length: 4-6 short paragraphs, under 150 words
- No bullet points in Step 1 (save for Step 2)
- Signature: Name, Title, Company, trust line ("Trusted by X+ teams")
- The proof paragraph with {{city}} personalization drives recognition
```

---

### Pattern #3: timing / day_0_3_4_7_7

**Confidence**: 0.95 | **Scope**: universal | **Channel**: email

```
Optimal sequence timing proven across EasyStaff Global campaigns:

Step 1: Day 0 — Hook + value prop + proof + CTA (25% of warm replies)
Step 2: Day 3 — Competitor displacement + bullet points (31% of warm replies)
Step 3: Day 4 — Pricing transparency + video offer (14% of warm replies)
Step 4: Day 7 — Channel switch: "LinkedIn or Telegram?" + "Sent from iPhone" (31% of warm replies)
Step 5: Day 7 — Final: acknowledge they're busy, restate value, soft close

Why this spacing:
- Day 0-3 gap: enough for Step 1 to be read but not forgotten
- Day 3-4 (1 day gap): rapid follow-up creates urgency cluster
- Day 4-7 (3 day gap): breathing room before channel switch
- Day 7-7 (same day): Steps 4+5 can hit on same day = last push

Key insight: Steps 2 and 4 TIED at 31% each. Step 2 catches competitor-frustrated buyers.
Step 4 catches people who don't read email carefully ("Sent from iPhone" pattern breaks).

DO NOT skip any step — each catches a different buyer archetype.
```

---

### Pattern #4: cta / cost_calculation_question

**Confidence**: 0.82 | **Scope**: universal | **Channel**: email

```
Step 1 CTA should be a question offering value, not asking for time.

Best: "Would you like to calculate the cost benefit for your case?"
Good: "Can I send you a 2-minute walkthrough video?"
OK: "Open to a quick demo call this week?"

Why it works: The prospect gets something (a calculation, a video) rather than
giving something (their time). "For your case" implies personalization.

Evidence: 9 out of 36 warm leads replied to Step 1. All Step 1 CTAs were
value-offering questions. Zero warm replies came from Steps with "Let me know
if you'd like to schedule a call" type CTAs in isolation.

Step progression:
- Step 1: Value offer ("calculate cost benefit")
- Step 2: Direct ask ("Open to a quick demo call?")
- Step 3: Low-commitment offer ("Can I send you a video?")
- Step 4: Channel switch ("Would it be easier on LinkedIn or Telegram?")
- Step 5: Empathy close ("If improving payments is still a goal, I'm here")

Each CTA matches the step's purpose. Don't use the same CTA pattern twice.
```

---

### Pattern #5: tone / casual_professional_no_hype

**Confidence**: 0.90 | **Scope**: universal | **Channel**: email

```
Tone that works for B2B cold outreach across all markets:

DO: Write like a person texting a business contact. Short sentences.
Contractions OK. First person. Specific numbers instead of adjectives.

DON'T: Use hype words (revolutionary, cutting-edge, game-changing, innovative,
seamless, robust, leverage). Don't use exclamation marks. Don't say "I hope
this email finds you well."

Evidence: Step 4 uses "Sent from my iPhone" as the signature — the most casual
element — and it triggers 31% of warm replies. The informality breaks the
"automated outreach" pattern and feels like a real person.

Example of good tone:
"We at Easystaff help companies pay freelancers globally with fees under 1%"
(specific number, plain language, no hype)

Example of bad tone:
"Our revolutionary platform seamlessly handles your international payments
with cutting-edge technology" (every word is a red flag)

Russian market note: Same principle applies. Danila's successful EasyStaff RU
sequences use conversational Russian, not corporate-speak.
```

---

### Pattern #6: opener / direct_value_statement

**Confidence**: 0.87 | **Scope**: universal | **Channel**: email

```
First line of Step 1: state the value, not the introduction.

Good: "We at Easystaff help companies pay freelancers globally with fees under 1%"
Bad: "My name is Petr and I'm the BDM at Easystaff, a leading global payroll platform"

Why: The prospect doesn't care who you are. They care what you can do for them.
Lead with the benefit, include the company name naturally.

The word "help" is key — it positions you as solving their problem, not selling.

Evidence: All 9 Step 1 warm replies came from sequences starting with a direct
value statement. Zero came from self-introduction openers.
```

---

### Pattern #7: sequence_flow / escalation_from_value_to_empathy

**Confidence**: 0.93 | **Scope**: universal | **Channel**: email

```
Each step serves a different purpose and catches a different buyer type:

Step 1 (VALUE): State what you do, proof point, soft CTA
→ Catches: Impulse buyers with immediate need (25% of warm replies)

Step 2 (COMPETITION): Name competitors, bullet-point advantages
→ Catches: Frustrated users of Deel/Upwork/Wise (31% of warm replies)

Step 3 (PRICE): Transparent pricing, offer to send walkthrough
→ Catches: Enterprise/price-sensitive buyers who need numbers (14%)

Step 4 (CHANNEL SWITCH): "LinkedIn or Telegram?" + "Sent from iPhone"
→ Catches: People who don't read email carefully (31%)

Step 5 (EMPATHY): "I know you're busy", acknowledge they have a solution,
soft restatement of value
→ Catches: Long-cycle buyers who need multiple touches

CRITICAL: Steps 2-5 use EMPTY subject (thread as replies to Step 1).
Only Step 1 has a subject line. This keeps the entire sequence in one
email thread — higher visibility, lower spam risk.

The "Sent from iPhone" in Step 4 is a deliberate pattern-break. It looks
like a real person dashing off a quick message, not an automated sequence.
```

---

### Pattern #8: objection_preempt / pricing_transparency_step3

**Confidence**: 0.84 | **Scope**: universal | **Channel**: email

```
Step 3 should include transparent pricing numbers.

Pattern: "Our pricing is transparent: from 3% or a flat $39 per task.
Free withdrawals for freelancers. Mass payouts via Excel upload.
For 50+ contractors/month, we offer custom rates below any competitor."

Why: 10% of objections are "too expensive / not worth switching."
Showing pricing proactively filters out non-buyers AND signals confidence.
Hiding pricing behind "let's jump on a call" feels like a trap.

Enterprise trigger: "For 50+ contractors/month, we offer custom rates"
makes enterprise buyers self-identify. Adam Naser (45 roles RFP) replied
to Step 3 specifically because he saw volume pricing was available.

Evidence: Step 3 catches 14% of warm replies — all price-sensitive buyers.
These leads tend to be larger deals (enterprise RFPs, 50+ contractor teams).

Offer to send a "2-minute walkthrough video" as the CTA — low commitment,
high information density.
```

---

## LEVEL 2: BUSINESS PATTERNS (scope_level='business', business_key='easystaff.io')

These apply to EasyStaff Global (project 9) AND EasyStaff RU (project 40).
NOT shared with Inxy, Mifort, TFP — different businesses.

---

### Pattern #9: proof_point / competitor_displacement_story

**Confidence**: 0.91 | **Scope**: business (easystaff.io) | **Channel**: email

```
Step 2 should name specific competitors the prospect likely uses.

Pattern: "Many companies we talk to are moving off Upwork or are frustrated
with Deel's inflexibility."

Why: 90-100% of qualified leads already use SOMETHING. Naming the competitor
creates instant recognition ("that's me!") and positions you as the upgrade.

Competitors to name (by market):
- US/Global: Deel, Rippling, Upwork, Fiverr, Wise, Payoneer
- EU: Deel, Remote.com, Wise, bank wires
- Gulf: Wise, bank transfers, Payoneer
- AU: Deel, Wise, bank transfers

Step 2 should follow with bullet points showing HOW you're better:
- "Cut out the middleman: Save the 10-20% marketplace fees"
- "No annual contracts: Pay only for what you use"
- "Same-day payouts to any country, real human support"

Evidence: Step 2 generates 31% of warm replies — tied with Step 4 for #1.
Avanish Anand (CEO, Zoth) forwarded Step 2 to product lead: "Pls discuss."
CEO delegation = strongest buying signal. Triggered by competitor naming.
```

---

### Pattern #10: proof_point / specific_savings_number

**Confidence**: 0.86 | **Scope**: business (easystaff.io) | **Channel**: email

```
Dollar amounts > percentages > adjectives.

Good: "saving them $3,000/month on platform fees and exchange rates"
OK: "saving them 70% on international payment costs"
Bad: "significant cost savings on your global payroll"

Why: $3,000/month is tangible and relatable. "70%" requires the prospect to
calculate what 70% of THEIR spend is. "Significant" means nothing.

The number should be realistic for the ICP company size (10-50 employees).
$3,000/month for 50 contractors = $60/contractor/month savings. Believable.

Pair the number with the cost category: "platform fees and exchange rates"
tells them WHAT they're overpaying on, not just that they're overpaying.

Evidence: The "$3,000/month" figure appears in EasyStaff's top-performing
Step 1 across all regional campaigns. Johannes Lotter (50 contractors)
signed after seeing the math applied to his team size.
```

---

## LEVEL 3: PROJECT PATTERNS (scope_level='project', project_id=9)

These apply ONLY to EasyStaff Global. Not to EasyStaff RU (different market, language, ICP).

---

### Pattern #11: personalization / city_in_proof_paragraph

**Confidence**: 0.85 | **Scope**: project (easystaff global, id=9) | **Channel**: email

```
Use {{city}} in the proof/case study paragraph, not in the greeting.

Pattern: "Recently helped a {{city}} agency switch from [Competitor] to [our solution],
saving them $X/month..."

Why it works: Creates geographic recognition ("they work with companies in MY city")
without feeling like a mail merge. The city appears in a natural sentence, not as
"Hey, I noticed you're based in {{city}}!" which feels automated.

Evidence: AU-PH campaign with {{city}} personalization (Sydney/Melbourne split)
outperformed generic version. James Martin (Blue Ocean Angels, Sydney) — meeting
booked same day after reading about "a Sydney company."

Custom field setup: Upload contacts with city in custom_fields dict.
SmartLead template: {{city}} resolves from the contact's custom field.

DO NOT: Put {{city}} in subject line or greeting. It belongs in the proof paragraph.
```

---

## The Assembled Prompt (what Gemini actually sees)

When `POST /api/campaign-intelligence/generate-sequence/ {"project_id": 9}` is called, the system assembles all 3 levels into this prompt structure:

```
## LEVEL 1: UNIVERSAL COLD EMAIL PATTERNS
(Apply to ALL projects — how cold email works)

**[subject_line] {{first_name}} – [pain point question]** (confidence: 92%)
Subject line format: "{{first_name}} – paying freelancers abroad?"
Why it works: Personal (first name), immediately relevant...
[... full text of pattern #1 ...]

**[timing] 5-step cadence: Day 0 → 3 → 4 → 7 → 7** (confidence: 95%)
[... full text of pattern #3 ...]

**[tone] Casual-professional tone, zero hype words** (confidence: 90%)
[... full text of pattern #5 ...]

[... all 8 universal patterns ...]


## LEVEL 2: BUSINESS KNOWLEDGE — easystaff.io
(What this business sells, competitors, objections, proof points)

Company: easystaff.io
Sender: Petr Nikolaev, BDM

**[proof_point] Name the competitor they're switching FROM** (confidence: 91%)
[... full text of pattern #9 ...]

**[proof_point] Use specific dollar savings, not percentages** (confidence: 86%)
[... full text of pattern #10 ...]

### Shared knowledge from other projects of this business:
  [outreach] EasyStaff RU outreach rules: Russian conversational tone, CIS corridors...
  [gtm] EasyStaff RU GTM strategy: Russian DMs, conference follow-ups...


## LEVEL 3: PROJECT CONTEXT — easystaff global
(This project's ICP, market, target segments, specific knowledge)

Target Segments: Digital agencies, creative agencies, IT services, 10-50 employees
Target Industries: Marketing, Design, Software Development, Animation, Video Production

**[personalization] {{city}} variable in case study paragraph** (confidence: 85%)
[... full text of pattern #11 ...]

[icp] target_description: Companies with 5-50 freelancers globally, frustrated with Deel/Wise/Upwork...
[outreach] sequence_strategy: 5-step email, competitor displacement in Step 2...
[gtm] corridor_prioritization: UAE→India (#1), US→Mexico (#2), AU→Philippines (#3)...


## REFERENCE SEQUENCE (top performer: Petr ES Gulf)
Quality score: 0.0342 | Warm rate: 3.42% | Meeting rate: 0.85%

  Step 1 (day +0): Hi {{first_name}}, We at Easystaff help companies pay...
  Step 2 (day +3): Following up. Many companies we talk to are moving off Upwork...
  Step 3 (day +4): Just making sure my emails are getting through. Our pricing...
  Step 4 (day +7): Would it be easier to connect on LinkedIn or Telegram?...
  Step 5 (day +7): Hi {{first_name}}, I know you're busy...


## CAMPAIGN NAME: Petr ES Manchester-Edinburgh
## CUSTOM INSTRUCTIONS
Focus on UK agencies, mention Deel displacement, use £ not $
```

This entire text (~3,000 tokens) is sent to Gemini 2.5 Pro, which generates a 5-step sequence applying all patterns to this specific project's context.

---

## Update Schedule

- **Weekly**: AI extraction cycle analyzes top 20 campaigns, creates/updates patterns
- **On campaign performance data**: Quality scores recalculated daily from new replies
- **Manual**: Operator can add patterns via API or seed script
- **Cross-pollination**: When a pattern works in one project, the weekly extraction may promote it to universal if it generalizes

## Database Schema (actual columns)

```sql
CREATE TABLE campaign_patterns (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    scope_level     VARCHAR(20) NOT NULL DEFAULT 'universal',  -- universal | business | project
    project_id      INTEGER REFERENCES projects(id),            -- NULL for universal
    business_key    VARCHAR(255),                                -- e.g. 'easystaff.io'
    pattern_type    VARCHAR(50) NOT NULL,     -- subject_line, timing, tone, etc.
    pattern_key     VARCHAR(100) NOT NULL,    -- unique slug
    title           VARCHAR(255) NOT NULL,    -- human-readable
    description     TEXT NOT NULL,            -- THE ACTUAL KNOWLEDGE (injected into prompt)
    market          VARCHAR(50),             -- en, ru, ar, NULL=all
    channel         VARCHAR(50),             -- email, linkedin, NULL=all
    segment         VARCHAR(100),
    confidence      FLOAT,                   -- 0.0-1.0
    evidence_campaign_ids  JSONB,            -- snapshot IDs
    evidence_summary       TEXT,
    sample_size     INTEGER,
    version         INTEGER DEFAULT 1,
    supersedes_id   INTEGER REFERENCES campaign_patterns(id),
    is_active       BOOLEAN DEFAULT true,
    extraction_run_id INTEGER REFERENCES campaign_intelligence_runs(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

The `description` field IS the knowledge. It's plain text, injected directly into the Gemini prompt. No vector embeddings, no complex retrieval — just text assembled from 3 scoped levels.
