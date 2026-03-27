# Writing the sequence

## Phase 1: Client Information Gathering

Before writing any sequences, collect **maximum information** from the client. Ideally, use an AI tool (like GPT-5) to generate a comprehensive questionnaire for outreach in their specific niche.

### Key Questions to Ask:

- **Who is the client?** (Company profile, industry, size)
- **Who is their ideal client?** (Demographics, psychographics, pain points)
- **Who is a bad fit client?** (Red flags, characteristics to avoid)
- **Who typically reaches out to them?** (Current client patterns)
- **Who do they want to attract?** (Target expansion)
- **Geographic data** (Location preferences, restrictions)
- **Demographics** (Gender, age, company size, etc.)
- **Any other relevant data** for database building, sequence descriptions, offers, etc.

## Phase 2: AI-Assisted Project Analysis

### Step 1: Generate JTBD and Roles

After gathering all client data, upload everything to [Claude ai](https://www.notion.so/0899e6533b364080b603a284cfb15162?pvs=21) and ask it to study the project.

**Key Positions & Roles:**

- Which job titles are responsible for these decisions?
- What roles do we need to target?

### JTBD

Prompt:

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

**Project:** Professional moving services with loyalty program for commercial real estate management companies **ICP:** Property Manager at commercial real estate management companies

**[APPROVED JOBS-TO-BE-DONE - JTBD]:**

1. Earn commission through loyalty program referrals while providing value to tenants
2. Organize tenant relocations with minimal time investment to avoid distraction from core responsibilities
3. Adapt to changing moving schedules and renovation timelines without additional costs or delays
4. Provide high-quality moving services to tenants to increase satisfaction and retention rates
5. Streamline tenant move-in/move-out processes to reduce operational complexity
6. Ensure safe handling and transportation of tenant property to avoid damage claims and liability
7. Coordinate furniture and equipment relocations during office renovations without disrupting tenant operations
8. Improve tenant experience during transitions to enhance lease renewal rates
```

### Step 2: Client Approval

Present the JTBD and position list to the client for approval. Once confirmed, **responsibility shifts** - all future correspondence will be based on pre-approved information.

## Phase 3: Sequence Creation with Claude

Run these prompts in a 

### Email 1

### Prompt

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating the **FIRST TOUCH EMAIL** that generates responses from busy decision-makers.
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

**Example 1 (End-User - Crypto Avatar Platform):**

- Company Info: website: coinavatar.com, content: A platform for users to create crypto avatars.
- **Good Output:**

How are you currently managing royalty payouts to your avatar creators and handling payments from a global user base?

At Inxy, we offer a powerful API to automate mass payouts and a simple Paygate for crypto acceptance, all under our EU/Canadian regulatory licenses.

Would you be open to a 15-minute call to explore how we can streamline this for you?

**Example 2 (Infrastructure Provider - Payment Gateway):**

- Company Info: website: onchainpay.io, content: a crypto payment gateway.
- **Good Output:**

As a crypto payment processor, how do you currently ensure regulatory compliance and operational resilience for your transaction flow?

We provide a fully licensed (EU VASP/Canadian MSB) payment infrastructure that can act as a 'reliable backup partner' to enhance your service stability and compliance.

Would a 15-minute strategic call to explore this be worthwhile?
```

### Example

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating the FIRST TOUCH EMAIL that generates responses from busy decision-makers.

[THE CONTEXT & TASK] I will provide you with:

1. [PROJECT DESCRIPTION]: Let Royal Moving & Storage in Los Angeles handle your relocation from start to finish with trusted crews who know the city inside and out.

2. [IDEAL CUSTOMER PROFILE - ICP]: Director of Operations (COO, CXO, and other executives)

3. [APPROVED JOBS-TO-BE-DONE - JTBD]:  Partnership with the company (commission based)

Job #1: Optimizing operational processes and increasing efficiency.

When a management company works with multiple properties and tenants, I need to improve logistics and coordination of movements to save time, reduce costs, and increase efficiency.

Job #2: Increase tenant satisfaction.

When tenants move or need help with relocation, I want to offer them high-quality and convenient services with minimal effort on our part to improve the customer experience and the company's reputation.

Job #3: Reduce risks and damage.

When tenants' belongings need to be moved, I want to avoid damage and loss by ensuring their safe storage and transportation to avoid additional costs.

[EMAIL #1 TEMPLATE - FILL THIS EXACT TEMPLATE]

`How are you currently {specific task from JTBD}?

At {Company Name}, we {specific solution for their JTBD}. {Brief explanation how it works} + {concrete metric/proof}.

Would you be open to a 15-minute call to explore how we can {solve their specific JTBD task}?`

[FILLING PRINCIPLES]

* Each sentence under 20 words

* Concrete numbers and metrics mandatory

* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.

* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.

Example 1 (End-User - Crypto Avatar Platform):

- Company Info: website: coinavatar.com, content: A platform for users to create crypto avatars.

- Good Output:

How are you currently managing royalty payouts to your avatar creators and handling payments from a global user base?

At Inxy, we offer a powerful API to automate mass payouts and a simple Paygate for crypto acceptance, all under our EU/Canadian regulatory licenses.

Would you be open to a 15-minute call to explore how we can streamline this for you?

Example 2 (Infrastructure Provider - Payment Gateway):

- Company Info: website: onchainpay.io, content: a crypto payment gateway.

- Good Output:

As a crypto payment processor, how do you currently ensure regulatory compliance and operational resilience for your transaction flow?

We provide a fully licensed (EU VASP/Canadian MSB) payment infrastructure that can act as a 'reliable backup partner' to enhance your service stability and compliance.

Would a 15-minute strategic call to explore this be worthwhile?
```

### Email 2

### Prompt

```

You are a world-class B2B Outreach Strategist. Your expertise is in creating a **FOLLOW-UP EMAIL** that adds value and continues the conversation.
**[THE CONTEXT & TASK]** I will provide you with:
1. **[PROJECT DESCRIPTION]:** Brief overview of our client's company and offering
2. **[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title and role we target
3. **[APPROVED JOBS-TO-BE-DONE - JTBD]:** Tasks, goals, challenges this ICP faces that our client solves
**[EMAIL #2 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`Quick note on {main aspect of the solution}.

{Operational advantage/efficiency benefit}. {Concrete metric/example with specific numbers and timing}.

{Analogy or comparison that makes the advantage clear}.

Open to a 20-minute call next week to {specific action related to JTBD}?`

**[FILLING PRINCIPLES]**
* Focus on operational efficiency/speed/process advantages
* Include concrete timings and numbers
* Show competitive advantage through efficiency
* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.
* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.

**Example 1 (Crypto Avatar Platform Follow-up):**

Quick note on automated royalty distribution.

Our system processes 10,000+ creator payouts in under 2 minutes, while manual systems typically take 3-5 business days per batch.

Think of it like having a dedicated finance team that never sleeps - handling all your creator payments instantly across 40+ countries.

Open to a 20-minute call next week to walk through your current payout workflow?

**Example 2 (Payment Gateway Follow-up):**

Quick note on transaction processing redundancy.

We maintain 99.97% uptime through our multi-node infrastructure, processing backup transactions in under 200ms when primary systems face issues.

It's like having a backup generator that kicks in before you even notice the power went out.

Open to a 20-minute call next week to discuss your current failover protocols?
```

### Example

```
You are a world-class B2B Outreach Strategist. Your expertise is in creating a FOLLOW-UP EMAIL that adds value and continues the conversation.

[THE CONTEXT & TASK]

I will provide you with:

[PROJECT DESCRIPTION]: Let Royal Moving & Storage in Los Angeles handle your relocation from start to finish with trusted crews who know the city inside and out.

[IDEAL CUSTOMER PROFILE - ICP]: Director of Operations (COO, CXO, and other executives)

[APPROVED JOBS-TO-BE-DONE - JTBD]: Partnership with the company (commission based)

Job #1: Optimizing operational processes and increasing efficiency. When a management company works with multiple properties and tenants, I need to improve logistics and coordination of movements to save time, reduce costs, and increase efficiency.

Job #2: Increase tenant satisfaction. When tenants move or need help with relocation, I want to offer them high-quality and convenient services with minimal effort on our part to improve the customer experience and the company's reputation.

Job #3: Reduce risks and damage. When tenants' belongings need to be moved, I want to avoid damage and loss by ensuring their safe storage and transportation to avoid additional costs.

[EMAIL #2 TEMPLATE - FILL THIS EXACT TEMPLATE]

Quick note on {main aspect of the solution}.
{Operational advantage/efficiency benefit}.
{Concrete metric/example with specific numbers and timing}. {Analogy or comparison that makes the advantage clear}.
Open to a 20-minute call next week to {specific action related to JTBD}?

[FILLING PRINCIPLES]

Focus on operational efficiency/speed/process advantages

Include concrete timings and numbers

Show competitive advantage through efficiency

Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.

No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.

Example 1 (Crypto Avatar Platform Follow-up):
Quick note on automated royalty distribution. Our system processes 10,000+ creator payouts in under 2 minutes, while manual systems typically take 3-5 business days per batch. Think of it like having a dedicated finance team that never sleeps - handling all your creator payments instantly across 40+ countries. Open to a 20-minute call next week to walk through your current payout workflow?

Example 2 (Payment Gateway Follow-up):
Quick note on transaction processing redundancy. We maintain 99.97% uptime through our multi-node infrastructure, processing backup transactions in under 200ms when primary systems face issues. It's like having a backup generator that kicks in before you even notice the power went out. Open to a 20-minute call next week to discuss your current failover protocols?
```

### Email 3

### Prompt

```
PROMPT #3: FINAL FOLLOW-UP EMAIL GENERATOR (Email #3)
You are a world-class B2B Outreach Strategist. Your expertise is in creating a **FINAL FOLLOW-UP EMAIL** that addresses specific competitive advantages.
**[THE CONTEXT & TASK]** I will provide you with:
1. **[PROJECT DESCRIPTION]:** Brief overview of our client's company and offering
2. **[IDEAL CUSTOMER PROFILE - ICP]:** Specific job title and role we target
3. **[APPROVED JOBS-TO-BE-DONE - JTBD]:** Tasks, goals, challenges this ICP faces that our client solves
**[EMAIL #3 TEMPLATE - FILL THIS EXACT TEMPLATE]**

`One last thought on {main solution topic}.

We solve the {number} problems where most {competitors/alternatives} fail: {problem #1} ({concrete result/timing}) and {problem #2} ({specific advantage}).

If either sounds familiar, worth a quick {adjective} chat?`

**[FILLING PRINCIPLES]**
* Maximum short format
* Two concrete problems where you outperform competitors
* Confident, casual tone
* Very low-pressure CTA
* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.
* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.

**Example 1 (Crypto Avatar Platform Final):**

One last thought on creator payment management.

We solve the 2 problems where most payment solutions fail: cross-border compliance (we handle 40+ jurisdictions automatically) and transaction speed (payouts in 2 minutes vs 3-5 days).

If either sounds familiar, worth a quick informal chat?

**Example 2 (Payment Gateway Final):**

One last thought on payment infrastructure reliability.

We solve the 2 problems where most crypto processors struggle: regulatory coverage (dual EU/Canadian licenses vs single jurisdiction) and system redundancy (99.97% uptime vs industry 99.5%).

If either resonates, worth a quick strategic chat?
```

### Example

PROMPT #3: FINAL FOLLOW-UP EMAIL GENERATOR (Email #3)
You are a world-class B2B Outreach Strategist. Your expertise is in creating a

**FINAL FOLLOW-UP EMAIL**

that addresses specific competitive advantages.

**[THE CONTEXT & TASK]**

I will provide you with:
[PROJECT DESCRIPTION]: Let Royal Moving & Storage in Los Angeles handle your relocation from start to finish with trusted crews who know the city inside and out. [IDEAL CUSTOMER PROFILE - ICP]: Director of Operations (COO, CXO, and other executives) [APPROVED JOBS-TO-BE-DONE - JTBD]: Partnership with the company (commission based) Job #1: Optimizing operational processes and increasing efficiency. When a management company works with multiple properties and tenants, I need to improve logistics and coordination of movements to save time, reduce costs, and increase efficiency. Job #2: Increase tenant satisfaction. When tenants move or need help with relocation, I want to offer them high-quality and convenient services with minimal effort on our part to improve the customer experience and the company's reputation. Job #3: Reduce risks and damage. When tenants' belongings need to be moved, I want to avoid damage and loss by ensuring their safe storage and transportation to avoid additional costs.

**[EMAIL #3 TEMPLATE - FILL THIS EXACT TEMPLATE]**

```
One last thought on {main solution topic}.
We solve the {number} problems where most {competitors/alternatives} fail: {problem #1} ({concrete result/timing}) and {problem #2} ({specific advantage}).
If either sounds familiar, worth a quick {adjective} chat?
```

**[FILLING PRINCIPLES]**

* Maximum short format
* Two concrete problems where you outperform competitors
* Confident, casual tone
* Very low-pressure CTA
* Brevity and Scannability: Short sentences (under 20 words), small paragraphs (1-3 sentences). Scannable in under 10 seconds.
* No Fluff: Skip clichés, buzzwords, formal language. Write like a helpful expert to a peer.

**Example 1 (Crypto Avatar Platform Final):**

One last thought on creator payment management.
We solve the 2 problems where most payment solutions fail: cross-border compliance (we handle 40+ jurisdictions automatically) and transaction speed (payouts in 2 minutes vs 3-5 days).
If either sounds familiar, worth a quick informal chat?

**Example 2 (Payment Gateway Final):**

One last thought on payment infrastructure reliability.
We solve the 2 problems where most crypto processors struggle: regulatory coverage (dual EU/Canadian licenses vs single jurisdiction) and system redundancy (99.97% uptime vs industry 99.5%).
If either resonates, worth a quick strategic chat?

After generating these email templated don’t forget to add more personalization, at least use the name of the company you are targeting.

For example add company name

```
How are you currently {specific task from JTBD} at **{target company}?**
```

![telegram-cloud-photo-size-2-5366200477303304038-y.jpg](Writing%20the%20sequence/telegram-cloud-photo-size-2-5366200477303304038-y.jpg)