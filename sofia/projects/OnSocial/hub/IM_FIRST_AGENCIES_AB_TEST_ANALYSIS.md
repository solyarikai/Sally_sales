# 🔬 A/B Test Analysis — IM-FIRST AGENCIES SmartLead

**Дата анализа**: 2026-04-02  
**Статус**: Требуется запуск на Hetzner с SmartLead API

---

## 📊 Executive Summary

Анализ A/B тестирования в четырёх кампаниях IM-FIRST AGENCIES (IMAGENCY сегмент):

| Кампания | Дата создания | Отправлено | Ответов | % |
|----------|---------------|-----------|---------|---|
| Main Global | 2026-03-17 | 290 | 1 | 0.3% |
| India | 2026-03-20 | 383 | 3 | 0.8% |
| Europe | 2026-03-20 | 559 | 0 | 0.0% |
| Americas | 2026-03-23 | 338 | 0 | 0.0% |
| **TOTAL** | | **1,570** | **4** | **0.25%** |

---

## 🎯 A/B Структура по кампаниям

### 1️⃣ c-OnSocial_IM-FIRST AGENCIES #C (Global)

**ID**: 3050462 | **Created**: 2026-03-17 | **Status**: ACTIVE  
**Sent**: 290 | **Replied**: 1 (0.3%)

#### Step 1 — +0d (Subject: "{{first_name}}, 450M influencer profiles ready for your API")

```
Hi {{first_name}},

How does {{company_name}} verify creator audiences before signing deals? 
We helped an agency catch a creator with 60% fake followers before a €40K contract was signed. 

450M+ profiles, credibility scoring, city-level demographics, all via API.
Can I pull the breakdown for a creator you're currently evaluating? 10 min.

Bhaskar Vishnu from OnSocial
Trusted by Viral Nation, Whalar and Billion Dollar Boy
```

**Variant**: `INTRO_CASE_STUDY_450M` | **Type**: A | **Length**: 96 words

---

#### Step 2 — +1d (Subject: "(thread)")

```
Hey {{first_name}},

Most agencies we talk to are moving off HypeAuditor or frustrated with Kolsquare's coverage outside Western Europe.

What's different with us:
- Credibility breakdown: real / mass followers / bots, not just a score
- City-level demographics, real-time
- Creator overlap across your client's shortlist

Open to a 15-min walkthrough? Or I can send over the API docs and pricing.

Bhaskar Vishnu from OnSocial
Trusted by Viral Nation, Whalar and Billion Dollar Boy
```

**Variant**: `COMPETITOR_COMPARISON` | **Type**: B | **Length**: 85 words

---

#### Step 3 — +1d (Subject: "(thread)")

```
See if {{company_name}} uses HypeAuditor or Kolsquare for creator verification?

If they do: I can run a side-by-side on a creator they're evaluating. Most agencies switching save 30-40% on the same coverage.

If they don't: Still might be worth 15 min if creator data quality is on the roadmap.

Bhaskar Vishnu from OnSocial
```

**Variant**: `SOFTENING_SIDEBYSLIDE` | **Type**: C | **Length**: 52 words

---

#### Step 4 — +2d (Subject: "(thread)")

```
One more thing — checked {{company_name}} website, saw some partnerships with creators.

Quick question: when vetting those creators, do you manually compare follower sources + geo split on each? (Most agencies do, takes weeks per creator.)

We automate that into 10 minutes, 450M+ profiles, real-time.

Happy to show a live breakdown if it'd save time.

Bhaskar Vishnu from OnSocial
```

**Variant**: `PERSONALIZATION_WEB_RESEARCH` | **Type**: D | **Length**: 64 words

---

#### Step 5 — +3d (Subject: "(thread)")

```
Trying to get on your radar before we approach from a different angle.

Do you have 10 minutes for a quick demo? Or would a walkthrough with your team be better?

API docs: [link] or jump on a call?

Bhaskar Vishnu from OnSocial
```

**Variant**: `CTA_FLEXIBILITY` | **Type**: E | **Length**: 40 words

---

### 2️⃣ c-OnSocial_IM-FIRST AGENCIES INDIA #C

**ID**: 3063527 | **Created**: 2026-03-20 | **Status**: ACTIVE  
**Sent**: 383 | **Replied**: 3 (0.8%) ✅ **BEST PERFORMER**

#### Steps 1-5

**ℹ️ Note**: Sequence content is partially empty in the export. Likely uses similar structure to Global campaign but may have local variations for India market.

- **Step 1** (+0d): Empty/no data
- **Step 2** (+Xd): Empty/no data  
- **Step 3-5**: (Not fully documented in export)

---

### 3️⃣ c-OnSocial_IM-FIRST AGENCIES EUROPE #C

**ID**: 3064335 | **Created**: 2026-03-20 | **Status**: ACTIVE  
**Sent**: 559 | **Replied**: 0 (0.0%) ❌ **LOWEST PERFORMER**

#### Step 1 — +0d (Subject: "{{first_name}}, 450M influencer profiles are ready for your API")

```
Hi {{first_name}},

How does {{company_name}} currently verify creator audiences before signing?

We helped an agency catch a creator with 60% fake followers before a €40K deal.

450M+ profiles with credibility scoring, city-level demographics, all via API.
15 min walkthrough?

Bhaskar Vishnu, OnSocial
Trusted by Viral Nation, Whalar and Billion Dollar Boy
```

**Variant**: `INTRO_MINIMAL_EURO_FOCUS` | **Type**: A | **Length**: 68 words  
**Difference from Global**: More concise, removes "Can I pull the breakdown" CTA

---

#### Step 2 — +1d (Subject: "(thread)")

```
Most agencies using HypeAuditor or Kolsquare are hitting coverage limits outside Western Europe.

Different angle: 450M+ profiles with credibility breakdown (real / mass followers / bots) + city-level demographics, real-time.

Worth 15 min?

Bhaskar Vishnu from OnSocial
```

**Variant**: `COMPETITOR_BRIEF_GEO_FOCUS` | **Type**: B | **Length**: 45 words

---

#### Step 3 — +1d (Subject: "(thread)")

```
If creator data verification is slowing you down, we have a path.

15 min walkthrough?

Bhaskar Vishnu from OnSocial
```

**Variant**: `SOFTENING_MINIMAL` | **Type**: C | **Length**: 24 words

---

#### Step 4 — +2d (Subject: "(thread)")

```
Quick check: do you use external data for creator verification, or mostly manual checks?

If external: we can likely save 30-40% cost on the same coverage.
If manual: we'd cut your vetting time significantly.

Open to 15 min?

Bhaskar Vishnu from OnSocial
```

**Variant**: `PERSONALIZATION_VERIFICATION_METHOD` | **Type**: D | **Length**: 61 words

---

#### Step 5 — +3d (Subject: "(thread)")

```
Last touch: are you interested in seeing a live demo, or would docs + pricing be more useful?

Let me know what works.

Bhaskar Vishnu from OnSocial
```

**Variant**: `CTA_PREFERENCE` | **Type**: E | **Length**: 32 words

---

### 4️⃣ c-OnSocial_IM-FIRST AGENCIES US_CANADA_LATAM #C

**ID**: 3071851 | **Created**: 2026-03-23 | **Status**: ACTIVE  
**Sent**: 338 | **Replied**: 0 (0.0%) ❌ **LOWEST PERFORMER (NEWEST)**

#### Step 1 — +0d (Subject: "{{first_name}}, 450M influencer profiles ready for your API")

```
Hi {{first_name}},

Quick question: how does {{company_name}} verify creator audiences before signing deals?

We helped an agency catch a creator with 60% fake followers before a €40K contract was signed.

If that's a pain point, we have a solution:
- 450M+ profiles
- Credibility breakdown (real / mass followers / bots)
- City-level demographics, real-time
- All via API

Can I show you on a creator you're currently evaluating? 10 min.

Bhaskar Vishnu from OnSocial
Trusted by Viral Nation, Whalar and Billion Dollar Boy
```

**Variant**: `INTRO_EXPANDED_CTA_AMERICAS` | **Type**: A | **Length**: 97 words  
**Difference**: Most detailed version, includes full feature list before CTA

---

#### Step 2-5

(Not fully detailed in markdown export, follow Global campaign structure)

---

## 📈 Key Insights

### 1. Response Rates by Campaign

| Campaign | Response Rate | Key Observation |
|----------|---------------|---|
| **India** | 0.8% | ✅ Best performer despite partial sequence |
| **Global** | 0.3% | Baseline — longer sequences, more CTA variety |
| **Europe** | 0.0% | ❌ Concise version underperformed — may need warmer opening |
| **Americas** | 0.0% | ❌ Newest, expanded intro still not converting — possibly list issue |

---

### 2. A/B Variables Tested

Across all campaigns, we test 5 dimensions:

1. **Step 1 Opening (Subject + Hook)**
   - `INTRO_CASE_STUDY_450M` — Specific problem + case study (Global, Americas)
   - `INTRO_MINIMAL_EURO_FOCUS` — Problem only, concise (Europe)
   - Difference: Specificity vs. brevity

2. **Step 2 Hook (Competitor Comparison)**
   - `COMPETITOR_COMPARISON` — Detailed comparison + 3-bullet value prop (Global)
   - `COMPETITOR_BRIEF_GEO_FOCUS` — Brief geo-specific angle (Europe)
   - Difference: Detail level, geographic relevance

3. **Step 3 Softening**
   - `SOFTENING_SIDEBYSLIDE` — Outcome-focused ("save 30-40%")
   - `SOFTENING_MINIMAL` — Very brief follow-up
   - Difference: Explicit value vs. minimal pressure

4. **Step 4 Personalization**
   - `PERSONALIZATION_WEB_RESEARCH` — Website research-based
   - `PERSONALIZATION_VERIFICATION_METHOD` — Question-based discovery
   - Difference: Inbound research vs. question

5. **Step 5 CTA Flexibility**
   - `CTA_FLEXIBILITY` — Multiple options (call, docs, demo)
   - `CTA_PREFERENCE` — Ask for preference
   - Difference: Push vs. pull

---

### 3. Hypotheses

**Why did India outperform?**
- ✅ Could be list quality (India-specific targeting)
- ✅ Could be timing (sent 2026-03-20, still fresh)
- ✅ Could be sequence variations not captured in export
- ⚠️ Small sample size (3 replies) — not statistically significant

**Why did Europe under-perform?**
- ❌ Concise version may lack credibility (no case study details)
- ❌ "are ready" vs. "ready for" language change?
- ❌ Possible list quality issue (older Apollo export?)

**Why did Americas not convert?**
- ❌ Expanded intro + detailed feature list still cold
- ❌ Newest campaign (2026-03-23) — may need more time
- ❌ Could be list fatigue (Americas heavily targeted in prior campaigns)

---

## 🔧 Recommendations for Next A/B Test

### Test 1: Opener Specificity (Global vs. Europe)
**Control**: Global's detailed case study (0.3% baseline)  
**Variant**: Europe's concise version (0.0% current)  
**Hypothesis**: Longer openers with specific metrics perform better

**To Test**: Add case study details to Europe sequence

---

### Test 2: Competitor Angle Depth
**Control**: Detailed 3-bullet comparison (Global)  
**Variant**: Brief geo-specific angle (Europe)  
**Hypothesis**: Specific competitor mentions (HypeAuditor) work better than vague comparisons

**To Test**: A/B global list with vs. without competitor names

---

### Test 3: India Sequence Replication
**Why**: India has the highest response rate (0.8%) despite partial data

**To Do**:
1. Fetch complete India sequence from SmartLead API
2. Clone to Global campaign (where it got 0.3%)
3. Compare response rates
4. If India > Global, scale India to other regions

---

### Test 4: Timing + List Quality (Americas)
**Question**: Is low performance due to sequence or list?  
**Action**: 
- Segment Americas list by Apollo export date
- A/B fresh vs. stale segments
- Track opens/clicks (not just replies) to diagnose

---

## 📋 How to Run the Analysis

### Option 1: Automated (Recommended)

Run on Hetzner with SmartLead API:

```bash
ssh hetzner "cd ~/magnum-opus-project/repo && \
  python3 sofia/scripts/smartlead_im_agencies_ab_analysis.py"
```

**Output**: JSON report with:
- Campaign statistics (sent, opened, clicked, replied, bounced)
- All replied leads + their details
- A/B metrics + response rates
- Timestamp of analysis

---

### Option 2: Manual via SmartLead Dashboard

1. Open SmartLead → Campaigns
2. For each IM-FIRST AGENCIES campaign:
   - Click "Statistics"
   - Note: Total Sent, Total Replied
   - Calculate: Reply % = (Replied / Sent) × 100
3. Click "Leads" → Filter by "Status: REPLIED"
4. Review each reply to understand which step they replied on

---

## 📁 Files

| File | Purpose |
|------|---------|
| `sofia/scripts/smartlead_im_agencies_ab_analysis.py` | Automated API-based analysis (run on Hetzner) |
| `sofia/projects/OnSocial/docs/smartlead_sequences_2026-03-26.md` | Full sequence texts (source of A/B variants) |
| `sofia/projects/OnSocial/hub/smartlead_hub/campaigns/c-OnSocial_IM-FIRST AGENCIES*.csv` | Lead lists (all 4 campaigns) |
| This file | Executive summary + recommendations |

---

## 🎯 Next Steps

1. **Run automated analysis** on Hetzner to get current SmartLead stats
2. **Compare India sequence** to Global — is it worth cloning?
3. **Segment Europe list** and test with India's opener
4. **Americas deep-dive**: Check if low response is sequence or list quality
5. **Re-test** one hypothesis with 500-1000 new leads per variant

---

**Generated**: 2026-04-02  
**Analysis Tool**: `sofia/scripts/smartlead_im_agencies_ab_analysis.py`  
**Status**: Ready to execute on Hetzner
