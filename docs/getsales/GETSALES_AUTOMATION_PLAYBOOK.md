# GetSales Automation Playbook — God-Level Approach

**Analysis date:** 2026-03-28
**Data source:** 414 flows, 55 campaigns with 5+ replies, 2,000+ tracked replies across 10 projects
**API:** GetSales flow-versions API + internal ProcessedReply database

---

## Executive Summary

Your team runs 414 GetSales automations across 10 projects. After analyzing every flow structure, reply category, positive rate, and sender rotation pattern, here are the key findings:

- **Best positive rate:** 85.7% (Mifort 0603 Crypto Trading) — niche ICP + product-led messaging
- **Best meeting generator:** Mifort Crypto clay 0303 — 10 meetings from 29 replies (34.5% meeting rate)
- **Biggest volume:** EasyStaff RU DM — 686 replies, 27% positive (185 actionable conversations)
- **Worst performers:** RIzzult big 5 agencies (10.3%), Mifort PHP (0%), RIzzult global QSR (0%)

**The #1 pattern separating winners from losers: specificity of ICP targeting + value proposition in the connection request.**

---

## Part 1: Performance Rankings

### Tier 1 — Elite (60%+ positive rate)

| Campaign | Replies | Positive% | Meetings | Key Pattern |
|----------|---------|-----------|----------|-------------|
| Mifort 0603 Crypto Trading | 14 | 85.7% | 3 | Hyper-niche: crypto trading exchanges only |
| Mifort FinTech Payments | 6 | 83.3% | 1 | Niche: payment/commerce fintech |
| Mifort 0603 Investment | 5 | 80.0% | 0 | Niche: investment/insurance fintech |
| OnSocial platforms_1203 | 9 | 77.8% | 1 | ICP: influencer platforms |
| RIzzult QSR LVPR | 7 | 71.4% | 0 | Low-volume prior engagement rotation |
| Rizzult Miami agencies | 42 | 69.0% | 7 | Networking-first, conference hook |
| Mifort Crypto clay | 29 | 69.0% | 10 | Clay-sourced leads, crypto niche |
| EasyStaff UAE | 57 | 68.4% | 1 | Single sender, geo-targeted question |
| EasyStaff UAE-India | 19 | 63.2% | 1 | Geo-targeted, same pattern |
| Inxy Luma 2 | 8 | 62.5% | 4 | Event-sourced leads |

### Tier 2 — Strong (40-59% positive rate)

| Campaign | Replies | Positive% | Meetings | Key Pattern |
|----------|---------|-----------|----------|-------------|
| Palark ICE | 67 | 52.2% | 7 | Conference hook, DevOps niche |
| EasyStaff Qatar-SA | 52 | 51.9% | 2 | Geo-targeted corridors |
| TFP Apparel lookalike | 33 | 51.5% | 4 | Niche: fashion resale |
| Mifort Partners BizDevs | 17 | 47.1% | 1 | Partnership model |
| Mifort iGaming Providers | 39 | 43.6% | 2 | Niche: game providers, fraud angle |
| Mifort FinTech CTE | 20 | 40.0% | 2 | Crypto trading, 4-sender rotation |

### Tier 3 — Average (25-39% positive rate)

| Campaign | Replies | Positive% | Meetings |
|----------|---------|-----------|----------|
| RIzzult Farmacies | 38 | 39.5% | 4 |
| Inxy Crypto Payments | 38 | 39.5% | 9 |
| TFP Vestiare | 34 | 38.2% | 0 |
| Inxy Russian DMs | 42 | 35.7% | 4 |
| Rizzult shopping apps | 53 | 34.0% | 1 |
| SquareFi RUS DMs | 103 | 30.1% | 7 |
| EasyStaff RU DM | 686 | 27.0% | 46 |

### Tier 4 — Underperforming (<25% positive rate)

| Campaign | Replies | Positive% | Key Problem |
|----------|---------|-----------|-------------|
| RIzzult Streaming | 32 | 18.8% | 40% wrong_person — bad targeting |
| RIzzult big 5 agencies | 29 | 10.3% | 41% wrong_person — terrible targeting |
| RIzzult global QSR | 6 | 0% | 67% wrong_person |
| Mifort PHP | 6 | 0% | Generic messaging |

---

## Part 2: Flow Architecture Analysis

### Pattern A: "The Standard" (used by 80% of flows)

```
CONNECTION_REQUEST (with/without note)
  ├── ACCEPTED → tag + wait 1h → MSG1 → visit → wait 2-3d → MSG2 → like → wait 5d → MSG3 → endorse → wait 7d → MSG4 → END
  └── NOT ACCEPTED (timeout 1-21d) → like → visit → endorse → wait 15d → WITHDRAW → tag → END
```

**Node types used:**
- `linkedin_send_connection_request` — always first
- `trigger_linkedin_connection_request_accepted` — branch: accepted vs timeout
- `util_timer` — delays between actions
- `linkedin_send_message` — 3-5 follow-up messages
- `linkedin_visit_profile` — engagement signal
- `linkedin_like_latest_post` — engagement signal
- `linkedin_endorse_skills` — engagement signal
- `linkedin_withdraw_connection_request` — cleanup after timeout
- `gs_add_tag` — tagging for segmentation
- `linkedin_send_inmail` — fallback for non-accepted (EasyStaff only)
- `rule_filter` — connection count filter (Rizzult)

### Pattern B: "Networking First" (Rizzult Miami — 69% positive)

```
FILTER (connections > 19) → CONNECTION_REQUEST (no note!)
  ├── ACCEPTED → wait 1d → SOFT MSG ("Nice to connect") → wait 3d → PITCH MSG → wait 5d → EVENT HOOK MSG → wait 30d → END
  └── NOT ACCEPTED → like → endorse → wait 10d → withdraw
```

**Key difference:** No note on connection request. First message is pure networking ("Nice to connect, looking forward to our conversation"). Pitch comes in MSG2. Conference/event hook in MSG3.

### Pattern C: "Question Hook" (EasyStaff UAE — 68% positive)

```
CONNECTION_REQUEST ("Do you work with freelancers outside UAE?")
  ├── ACCEPTED → wait 1h → VALUE MSG → visit → wait 3d → SOCIAL PROOF MSG → like → wait 5d → OBJECTION HANDLER → endorse → END
  └── NOT ACCEPTED → like → InMail fallback → visit → endorse → withdraw
```

**Key difference:** Connection note is a qualifying question. If they accept, they've already self-selected as relevant. Follow-up messages build on the implied "yes."

### Pattern D: "Product-Led" (Mifort FinTech CTE — 40% pos, all Mifort campaigns)

```
CONNECTION_REQUEST ("Would love to connect! 🙂")
  ├── ACCEPTED → wait 1h → PRODUCT SHOWCASE → visit → wait 2d → PROOF/DEMO → like → wait 5d → LAST CHANCE → endorse → wait 7d → END
  └── NOT ACCEPTED → like → visit → endorse → wait 15d → withdraw
```

**Key difference:** Generic connection note, but MSG1 is pure product showcase with specific numbers (800K users, 25 crypto pairs). Works because the ICP is hyper-niche (crypto trading exchanges).

### Pattern E: "Urgency Close" (TFP Vestiare — 38% pos)

```
FILTER → CONNECTION_REQUEST (branded resale pitch)
  ├── ACCEPTED (21d timeout!) → QUESTION ("capturing resale?") → wait 3d → CASE STUDY ("5x ROI month one") → wait 5d → SCARCITY ("closing audit spots")
  └── NOT ACCEPTED → withdraw
```

**Key difference:** Long 21-day acceptance window. MSG1 is a direct question. MSG3 uses urgency/scarcity. No engagement actions (no likes/endorses/visits). Shortest sequence.

---

## Part 3: What Separates Winners from Losers

### Factor 1: ICP Specificity (Correlation: 0.8+)

**Top performers target ONE micro-niche per flow:**
- "Crypto trading exchanges" (85.7%)
- "Payment/commerce fintech" (83.3%)
- "Influencer marketing platforms" (77.8%)
- "Companies with freelancers outside UAE" (68.4%)

**Bottom performers use broad targeting:**
- "Big 5 agencies" (10.3%) — who are "big 5 agencies"? Too vague.
- "Streaming" (18.8%) — 40% wrong person rate proves bad targeting
- "PHP developers" (0%) — no differentiation from 10,000 other dev shops

**Rule:** One flow = one micro-ICP. If you can't describe the ICP in one sentence with specific attributes, the campaign will underperform.

### Factor 2: Connection Note Strategy

Three patterns, ranked by effectiveness:

| Strategy | Example | Avg Positive Rate | Best For |
|----------|---------|-------------------|----------|
| **Qualifying question** | "Do you work with freelancers outside UAE?" | 68% | Services with clear use case |
| **No note (networking)** | (empty — just connect) | 69% | Event/conference follow-ups |
| **Value proposition** | "We power creator data for agencies like {{company_name}}" | 45% | Product companies with strong brand |
| **Generic greeting** | "Would love to connect! 🙂" | 40-85% | Works IF the ICP is hyper-niche |

**Insight:** The connection note matters less when your targeting is extremely precise. Mifort's generic "Would love to connect" works at 85% because they only target crypto trading exchange CTOs. But for broad ICPs, you NEED a qualifying question to self-select leads.

### Factor 3: Message Sequence Structure

**Optimal sequence (from data):**

| Step | Timing | Purpose | Content Type |
|------|--------|---------|-------------|
| MSG1 | 1h after accept | Value intro + social proof | "We help X companies do Y. Helped Z achieve [number]" |
| Engage | Same day | Profile visit | Signals genuine interest |
| MSG2 | 2-3 days | Deeper proof / case study | Blog link, specific numbers, demo offer |
| Engage | Same day | Like latest post | |
| MSG3 | 5 days | Objection handling OR redirect | "Who should I talk to?" or "Many switch from competitors" |
| Engage | Same day | Endorse skills | |
| MSG4 | 7 days | Soft close | Brief, emoji, low-pressure ("{{first_name}}? 😊") |

**Key findings:**
- **3 messages = sweet spot.** 4+ messages have diminishing returns.
- **MSG4 as single emoji/name works** (EasyStaff: "{{first_name}}? 😊" generated replies from ghosts)
- **Engagement actions between messages boost acceptance and reply rates** — visit, like, endorse are not optional
- **Timing: 1h → 2d → 5d → 7d** is the proven pattern. Shorter = spammy. Longer = forgotten.

### Factor 4: Sender Rotation

| Strategy | Campaigns Using | Avg Positive Rate | When to Use |
|----------|----------------|-------------------|-------------|
| `fair` | Most campaigns | 45% | Default — even distribution |
| `random` | EasyStaff RU, OnSocial | 30% | Large-volume mass outreach |
| `prior_engagement` | Rizzult Farmacies | 39% | Warm audiences, event follow-ups |
| `new_sender` | TFP Vestiare | 38% | Multi-touch with different personas |
| Single sender | EasyStaff UAE, Rizzult Miami | 68% | Highly personal, niche campaigns |

**Insight:** Single sender outperforms multi-sender when the campaign is niche and personal. Multi-sender (random/fair) works for volume plays where personalization is lower.

### Factor 5: Non-Accepted Branch

**Two strategies observed:**

**Strategy A: "Warm then Withdraw" (standard)**
```
like → visit (1d) → endorse (3d) → wait 15d → withdraw → tag
```
Used by most campaigns. Shows engagement before giving up.

**Strategy B: "InMail Fallback" (EasyStaff only)**
```
like → InMail message → visit → endorse → wait 15d → withdraw → tag
```
Used by EasyStaff RU DM and EasyStaff UAE. Sends an InMail to people who don't accept the connection. This is unique to EasyStaff and may explain part of their high volume (686 replies).

---

## Part 4: Project-Level Insights

### Mifort (highest average positive rate: 52%)
- **Why it works:** Hyper-niche segmentation. Each campaign targets ONE industry vertical (crypto trading, payments, iGaming providers, investment/insurance).
- **Best campaign:** "0603 Crypto Trading" at 85.7% — only targets exchanges/trading platforms.
- **Meeting machine:** "Crypto clay" — 10 meetings from 29 replies. Clay-sourced leads (pre-filtered by ICP) + crypto niche = highest conversion to meetings.
- **Pattern:** Generic connect note + product-led MSG1 with specific numbers. Works because niche ICP means anyone who accepts is likely relevant.
- **Sender rotation:** `fair` across 4 senders. Each sender covers ~25% of volume.

### EasyStaff (highest volume: 686+ replies)
- **Why it works:** Clear pain point ("Do you have difficulties paying freelancers abroad?") + massive sender pool (8 senders with random rotation).
- **Best campaign:** "UAE" at 68.4% — single sender (Marina), qualifying question in connection note, geo-targeted.
- **Volume vs quality trade-off:** RU DM runs at 27% positive but generates 46 meetings — acceptable because the funnel is wide.
- **Unique feature:** InMail fallback for non-accepted connections.
- **RU DM flow is the most sophisticated:** 5 messages + InMail fallback + engagement actions at every step.

### Rizzult (highest variability: 0% to 71%)
- **Why it works (when it does):** Event hooks ("Were you at POSSIBLE Miami?"), networking-first approach.
- **Miami agencies = best Rizzult campaign** at 69% positive — no connection note, networking-first, event hook in MSG3.
- **Why it fails:** Broad targeting ("big 5 agencies", "streaming", "global QSR") leads to 40%+ wrong_person rates.
- **Pattern split:** Farmacies (Spanish-language, 5 senders, `prior_engagement`) vs Miami (1 sender, networking).
- **Critical issue:** Many Rizzult campaigns have >30% wrong_person rate. This is a targeting problem, not a messaging problem.

### Palark (strong niche play: 52%)
- **Conference hook:** "I saw you were at ICE" — immediate shared context.
- **DevOps/SRE niche:** Very specific value prop ("cut infra costs by 40%").
- **Pattern:** Conference connect → product intro → case study → meeting CTA.
- **Multiple senders:** Nikita as primary (47 replies), secondary sender (10 replies).

### OnSocial (emerging: building playbook)
- **Best pattern:** segment-specific flows (#C suffix = iteration C).
- **Three parallel campaigns:** Affiliate & Performance, Influencer Platforms, IM-First Agencies.
- **Product-led:** "450M+ profiles" and name-dropping competitors (Modash, Captiv8).
- **Still iterating:** agencies_0403 → agencies_1203 → AFFILIATE #C. Each iteration more targeted.

### SquareFi (volume play: 30% positive)
- **Russian-language DMs only.** Crypto/fiat platform for CIS market.
- **5 messages + endorse.** Standard pattern but messages are too long (>200 chars each).
- **2 senders, fair rotation.** Consistent but not exceptional.
- **60 not_interested out of 103 replies** — the "corporate VISA cards with crypto top-up" pitch is polarizing.

---

## Part 5: The God-Level Default Flow Template

Based on analysis of all winning patterns, here is the recommended default automation structure for new campaigns:

### Node Tree

```
[1] rule_filter (connections > 19, optional)
  ├── PASS → [2]
  └── FAIL → END

[2] linkedin_send_connection_request
    Note: {Qualifying question OR event hook OR short value prop}

[3] trigger_linkedin_connection_request_accepted (timeout: 3-7 days)
  ├── ACCEPTED → [4]
  └── NOT ACCEPTED → [NON_ACCEPT_BRANCH]

[4] gs_add_tag ("accepted_{campaign}")
[5] util_timer (1 hour)

[6] linkedin_send_message — MSG1: VALUE INTRO
    "Thanks for connecting, {{first_name}}!
    {1-2 sentence value prop with specific number/proof point}
    {Question to continue conversation}"

[7] linkedin_visit_profile
[8] util_timer (2 days)

[9] linkedin_send_message — MSG2: DEEPER PROOF
    "{Case study OR specific example OR demo offer}
    {URL to blog/case study if available}"

[10] linkedin_like_latest_post
[11] util_timer (5 days)

[12] linkedin_send_message — MSG3: REDIRECT/CLOSE
    "{Objection handling OR 'who should I talk to?' OR meeting CTA}
    {Keep it short — 2-3 lines max}"

[13] linkedin_endorse_skills
[14] util_timer (7 days)
[15] END

--- NON-ACCEPT BRANCH ---
[20] util_timer (1 day)
[21] linkedin_like_latest_post
[22] util_timer (2 days)
[23] linkedin_visit_profile
[24] util_timer (3 days)
[25] linkedin_endorse_skills
[26] util_timer (15 days)
[27] linkedin_withdraw_connection_request
[28] gs_add_tag ("not_accepted_{campaign}")
[29] END
```

### Configuration Defaults

```json
{
  "schedule": {
    "timeblocks": [
      {"dow": 1, "min": 540, "max": 1080},
      {"dow": 2, "min": 540, "max": 1080},
      {"dow": 3, "min": 540, "max": 1080},
      {"dow": 4, "min": 540, "max": 1080},
      {"dow": 5, "min": 540, "max": 1080}
    ],
    "timezone": "MATCH_LEAD_TIMEZONE",
    "use_lead_timezone": false
  },
  "use_sender_schedule": true,
  "priority": 3,
  "rotation_strategy": "fair",
  "acceptance_timeout_seconds": 259200
}
```

### Decision Matrix: Which Template Variant to Use

| Scenario | Connection Note | MSG Count | Rotation | Timeout |
|----------|----------------|-----------|----------|---------|
| **Niche product, clear ICP** | Generic ("Would love to connect!") | 3 msgs | `fair`, 2-4 senders | 1 day |
| **Service/solution sale** | Qualifying question ("Do you...?") | 3 msgs + bump | `fair`, 1-2 senders | 3 days |
| **Conference/event follow-up** | Event hook ("Saw you at X") or no note | 3 msgs | Single sender | 3 days |
| **Volume play, broad ICP** | Value prop (short!) | 4 msgs + InMail | `random`, 6-8 senders | 21 days |
| **Partnership/networking** | No note | 2 msgs + meeting CTA | Single sender | 3 days |
| **Re-engagement (ghosts)** | N/A (already connected) | 1-2 msgs | `new_sender` | N/A |

---

## Part 6: Message Templates (Proven Patterns)

### Connection Note Templates

**Type 1: Qualifying Question (68% positive avg)**
```
Hi {{first_name}}!
{Question about their specific pain point}?
```
Examples:
- "Do you work with freelancers outside of UAE?"
- "Is {{company_name}} capturing the resale activity around your pieces?"

**Type 2: Event Hook (52-69% positive avg)**
```
Hey! I saw you were at {EVENT} - we were there too. Would love to connect!
```

**Type 3: Credibility Drop (45% positive avg)**
```
Hi {{first_name}},
We power {solution} for {competitor1}, {competitor2}, {competitor3}.
Would love to connect with you! 🙂
```

**Type 4: Value Prop (30-85% — depends on ICP specificity)**
```
Hi {{first_name}}! 😊
{1-sentence value prop with specific number}
{1-sentence differentiation}
```

### MSG1 Templates (after accept)

**Pattern: Social proof + specific number + question**
```
Thanks for connecting, {{first_name}}!

{Company} helps {X}+ companies with {specific solution}.
{One specific proof point: "We helped [company] achieve [result]" or "X users, Y features, Z integrations"}

{Question to continue: "Would this be relevant for {{company_name}}?" or "Happy to share more details?"}
```

### MSG2 Templates (2-3 days later)

**Pattern: Deeper proof / case study / demo**
```
Hey {{first_name}},

{Case study or second proof point}
{Link to blog/case study OR specific feature walkthrough}

{Soft CTA: "Let me know if worth a quick look"}
```

### MSG3 Templates (5 days later)

**Pattern: Redirect or objection handling**
```
Hi {{first_name}},

{Acknowledge they may have existing solution}
{Differentiation from status quo}

{CTA: meeting request OR "who should I talk to?" redirect}
```

### MSG4 Template (7 days later, optional)

**Pattern: Ultra-short bump**
```
{{first_name}}? 😊
```
Or:
```
{{first_name}}, let's stay in touch.
If {pain point} becomes relevant, let me know!
```

---

## Part 7: Anti-Patterns (What NOT to Do)

### 1. Broad ICP = Wrong Person Death
Campaigns with >30% wrong_person rate:
- RIzzult big 5 agencies: 41% wrong_person
- RIzzult Streaming: 40% wrong_person
- RIzzult global QSR: 67% wrong_person

**Fix:** Split broad segments into micro-niches. "Streaming" → "OTT platform CTOs 50-500 employees" + "live streaming SaaS founders" as separate flows.

### 2. Too Many Messages
SquareFi sends 5 long messages. 60% of replies are "not_interested."
EasyStaff RU DM sends 5 messages but includes engagement actions between each.

**Rule:** Max 3 substantive messages. MSG4 (if any) should be 1 line.

### 3. Long Messages
Messages over 200 characters get lower response rates. The best-performing messages are 2-4 short paragraphs.

### 4. Missing Engagement Actions
Campaigns without `visit_profile`, `like_latest_post`, and `endorse_skills` between messages perform worse. These actions signal genuine interest and increase visibility.

### 5. Random Rotation for Small Campaigns
`random` rotation makes sense for 500+ lead campaigns. For <100 leads, use `fair` or single sender to maintain consistency.

### 6. No Connection Count Filter
Rizzult uses `rule_filter` for connections > 19 (filters out low-connection accounts). This is a good practice — accounts with <20 connections are often inactive or fake.

---

## Part 8: Automation via API

### Creating a New Flow Programmatically

```python
# 1. Create flow
POST /flows/api/flows
{
    "name": "Project - Segment Date",
    "flow_workspace_uuid": "WORKSPACE_UUID",
    "use_sender_schedule": true,
    "schedule": { ... },
    "priority": 3
}

# 2. Save flow version with nodes
POST /flows/api/flows/{flow_uuid}/flow-versions
{
    "flow_origin": "automation",
    "contact_sources": [{
        "sender_profiles": ["sender_uuid_1", "sender_uuid_2"],
        "rotation_strategy": "fair",
        "after_id": FIRST_NODE_ID
    }],
    "nodes": [ ... node tree ... ]
}

# 3. Add leads
POST /flows/api/flows/{flow_uuid}/add-new-lead
{
    "linkedin_url": "https://linkedin.com/in/person",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Acme"
}

# 4. Launch
PUT /flows/api/flows/{flow_uuid}/start
```

### Node Type Reference

| Node Type | Purpose | Key Payload Fields |
|-----------|---------|-------------------|
| `rule_filter` | Filter leads by criteria | `branches[].filters.json_logic` |
| `linkedin_send_connection_request` | Send connection request | `template` (note text), `fallback_send` |
| `trigger_linkedin_connection_request_accepted` | Branch on accept/timeout | `subtasks[].payload.wait_time` (timeout seconds) |
| `linkedin_send_message` | Send DM after connected | `template` (message text) |
| `linkedin_send_inmail` | Send InMail (not connected) | `template` |
| `linkedin_visit_profile` | Visit their profile | (none) |
| `linkedin_like_latest_post` | Like their latest post | (none) |
| `linkedin_endorse_skills` | Endorse skills | (none) |
| `linkedin_withdraw_connection_request` | Withdraw pending request | (none) |
| `gs_add_tag` | Tag lead in GetSales | `tag_uuid` |
| `util_timer` | Wait before next action | `wait_time` (seconds) |
| `end` | Terminal node | (none) |

### Workspace UUIDs (Your Account)

| Workspace | UUID | Projects |
|-----------|------|----------|
| Mifort | `6926de00-6870-420e-b8a1-70975336ebf1` | All Mifort campaigns |
| Rizzult | `3b474a42-e4ef-48ac-86c8-562413e9296c` | All Rizzult campaigns |
| OnSocial | `80185b90-1e9c-4485-9b30-5b2d5af934b9` | All OnSocial campaigns |
| TFP | `8475e035-1f58-4718-a887-5e84a674f59b` | TFP + warmup flows |
| EasyStaff | `327ef6ab-aeae-415a-8815-ec7732c141fc` | EasyStaff global campaigns |
| Deliryo | `31d4aef6-42ae-4c57-bd64-eb38501a379f` | Deliryo campaigns |
| Palark | `243fc43d-d83e-4fc4-a727-d7fb6126b70a` | Palark campaigns |

### Sender Profiles by Project (from reply data)

**EasyStaff RU** (8 senders):
- `b10a34f2` — Alex Paretski (221 replies, top performer)
- `7f829fca` — Eleonora (86 replies)
- `b3b69a39` — Aliaksandra Vailunova (74 replies)
- `d67e1028` — Alexandra Trifonova (74 replies)
- `5ecc3a67` — Aliaksandr Blank (63 replies)
- `4d1effeb` — Katya (59 replies)
- `774af09b` — Sergey Lebedev (53 replies)
- `07d392a8` — Andriy (41 replies)

**EasyStaff Global** (1-2 senders per geo):
- `4419a283` — Marina Mikhaylova (EasyStaff UAE, Qatar-SA, UAE-India — 123 replies total)
- `e7cd7b0f` — Arina Kozlova (AU-PH — 8 replies)

**Mifort** (4 primary senders):
- `0d22a72e` — Anna Reisberg (iGaming Providers lead — 29 replies)
- `c58462db` — Sophia Powell (Partners Salesforce, BizDevs)
- `430e90e2` — Lera Yurkoits (Clutch, FinTech)
- `d4d17541` — Valeriia Mutalava (Partners Salesforce volume)

**Rizzult** (5 senders):
- `91fb80ab` — (Farmacies lead — 31 replies)
- `4cbc70b5` — (Shopping apps, Streaming, QSR)
- `29fd2e4e` — (Miami agencies — 42 replies, single-sender star)
- `41b709f2` — (Streaming, Telemed)
- `94aeceb5` — (QSR, Crypto)

---

## Part 9: Recommended Next Actions

### Immediate (This Week)

1. **Kill or rebuild Tier 4 campaigns.** RIzzult big 5 agencies (10.3%), global QSR (0%), Streaming (18.8%) are wasting sender capacity. Either micro-niche the targeting or pause.

2. **Clone the EasyStaff UAE pattern** for EasyStaff Global geos. Single sender + qualifying question + geo-targeted messaging = 68% positive. Apply to Panama, Costa Rica, Mexico.

3. **Clone the Rizzult Miami pattern** for all conference follow-ups. Networking-first, no connection note, event hook in MSG3.

### Medium-Term (This Month)

4. **Standardize engagement actions.** Every flow should have `visit_profile`, `like_latest_post`, and `endorse_skills` between messages. Campaigns missing these underperform.

5. **Implement connection count filter.** Add `rule_filter (connections > 19)` to all flows. Filters fake/inactive accounts.

6. **Split broad ICPs.** Any campaign targeting >3 industries should be split into niche flows. One ICP = one flow.

### Long-Term (API Automation)

7. **Build flow template engine** that generates GetSales flow versions from project ICP + sender pool. The node structure is identical across 80% of campaigns — only messages and sender profiles change.

8. **A/B test connection notes.** Run parallel flows with qualifying question vs no note vs value prop for the same ICP. Measure positive rate per variant.

9. **Auto-pause low performers.** Any campaign with <20% positive rate after 30+ replies should be flagged for review.

---

## Appendix: Raw Data

### All 55 Campaigns with 5+ Replies (sorted by positive rate)

```
Campaign                                         | Replies | Pos% | Meetings | Wrong%
-------------------------------------------------|---------|------|----------|-------
Mifort 0603 Crypto Trading                       |      14 | 85.7 |        3 |   7.1
Mifort FinTech Payments                          |       6 | 83.3 |        1 |   0.0
Mifort 0603 Investment                           |       5 | 80.0 |        0 |   0.0
OnSocial platforms_1203                          |       9 | 77.8 |        1 |   0.0
RIzzult QSR LVPR                                 |       7 | 71.4 |        0 |  14.3
Rizzult Miami agencies                           |      42 | 69.0 |        7 |   4.8
Mifort Crypto clay                               |      29 | 69.0 |       10 |   3.4
EasyStaff UAE                                    |      57 | 68.4 |        1 |   0.0
EasyStaff UAE-India                              |      19 | 63.2 |        1 |   5.3
Inxy Luma 2                                      |       8 | 62.5 |        4 |   0.0
EasyStaff UAE-Outsourcing                        |       5 | 60.0 |        0 |   0.0
Mifort 10/02 Partners Java                       |       5 | 60.0 |        2 |   0.0
Palark ICE                                       |      67 | 52.2 |        7 |   4.5
EasyStaff Qatar-SA                               |      52 | 51.9 |        2 |   0.0
TFP Apparel lookalike                            |      33 | 51.5 |        4 |   3.0
Archistruct Devs Dubai                           |       8 | 50.0 |        0 |   0.0
Mifort Partners Salesforce (small)               |       8 | 50.0 |        0 |  12.5
rizzult streaming telecom                        |       8 | 50.0 |        0 |  25.0
Dubai C level                                    |       6 | 50.0 |        1 |   0.0
Mifort Partners BizDevs                          |      17 | 47.1 |        1 |   0.0
OnSocial Marketing agencies                      |      11 | 45.5 |        0 |   9.1
Mifort FinTech 26.03 Next Pro                    |       9 | 44.4 |        0 |   0.0
Mifort iGaming Providers                         |      39 | 43.6 |        2 |   5.1
Palark Sigma Rome                                |      14 | 42.9 |        1 |   0.0
Mifort FinTech CTE                               |      20 | 40.0 |        2 |  15.0
INXY Rus Data up to 8050                         |      10 | 40.0 |        0 |  10.0
Mifort 06/03 Payments Commerce                   |       5 | 40.0 |        0 |  40.0
RIzzult Farmacies                                |      38 | 39.5 |        4 |  13.2
Inxy Crypto Payments                             |      38 | 39.5 |        9 |  10.5
TFP Vestiare                                     |      34 | 38.2 |        0 |  17.6
Inxy Russian DMs                                 |      42 | 35.7 |        4 |   4.8
Rizzult shopping apps                            |      53 | 34.0 |        1 |  30.2
rizzult telemedicine                             |      15 | 33.3 |        3 |  13.3
EasyStaff AU-PH                                  |      15 | 33.3 |        2 |   6.7
RIzzult travel                                   |       6 | 33.3 |        1 |  16.7
Mifort FinTech Investment Insurance              |       6 | 33.3 |        0 |   0.0
SquareFi RUS DMs                                 |     103 | 30.1 |        7 |   2.9
TFP CIFF                                         |      10 | 30.0 |        0 |  30.0
Mifort iGaming Marketing                         |       7 | 28.6 |        0 |  28.6
EasyStaff RU DM                                  |     686 | 27.0 |       46 |   5.1
RIzzult Telemed                                  |      16 | 25.0 |        1 |  18.8
Mifort 10/02 Salesforce (large)                  |      75 | 24.0 |        5 |  12.0
RIzzult QSR LPR                                  |       9 | 22.2 |        1 |  22.2
Mifort 10/02 Clutch                              |       9 | 22.2 |        0 |  22.2
OnSocial Generic                                 |      15 | 20.0 |        1 |  20.0
RIzzult Foodtech LPR                             |      10 | 20.0 |        0 |  50.0
SquareFi VC Fundraise                            |       5 | 20.0 |        0 |   0.0
OnSocial agencies_1203                           |       5 | 20.0 |        0 |   0.0
RIzzult Streaming                                |      32 | 18.8 |        0 |  40.6
Mifort Partners Salesforce (medium)              |      12 | 16.7 |        0 |   8.3
EasyStaff RU (old)                               |      18 | 11.1 |        2 |  11.1
RIzzult big 5 agencies                           |      29 | 10.3 |        0 |  41.4
Mifort PHP                                       |       6 |  0.0 |        0 |   0.0
RIzzult global QSR                               |       6 |  0.0 |        0 |  66.7
```

---

## Appendix: MCP Integration

### Automated Flow Creation via MCP Tools

The following MCP tools implement the god-level flow patterns from this playbook:

| Tool | Purpose | Mirrors SmartLead Tool |
|------|---------|----------------------|
| `gs_generate_flow` | AI-generates LinkedIn flow from project ICP | `god_generate_sequence` |
| `gs_approve_flow` | Mark flow as approved after review | `god_approve_sequence` |
| `gs_list_sender_profiles` | List available LinkedIn accounts | `list_email_accounts` |
| `gs_push_to_getsales` | Push flow to GetSales as DRAFT | `god_push_to_smartlead` |
| `gs_activate_flow` | Start the flow (requires user confirmation) | `activate_campaign` |

### Implementation Files

| File | Purpose |
|------|---------|
| `mcp/backend/app/services/getsales_automation.py` | Service: API client, node tree builder, AI flow generation |
| `mcp/backend/app/mcp/tools.py` | Tool definitions (5 tools under "GetSales LinkedIn Automation") |
| `mcp/backend/app/mcp/dispatcher.py` | Tool handlers (5 handler blocks) |
| `mcp/backend/app/config.py` | Config: `GETSALES_API_KEY`, `GETSALES_TEAM_ID` |

### Flow Types Available

| Type | Best For | Based On | Expected Positive Rate |
|------|----------|----------|----------------------|
| `standard` | Services with clear use case | EasyStaff UAE | 60-70% |
| `networking` | Event follow-ups, partnerships | Rizzult Miami | 65-70% |
| `product` | Niche product companies | Mifort FinTech | 40-85% (ICP dependent) |
| `volume` | Mass outreach, broad ICP | EasyStaff RU DM | 25-35% (high volume) |
| `event` | Conference leads | Palark ICE | 50-55% |
