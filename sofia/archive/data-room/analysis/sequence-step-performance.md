# OnSocial — Sequence Step Performance Analysis

Source: SmartLead API sequence analytics (smartlead_sequence_analytics.json)
Date: 2026-03-16

## Step-by-Step Performance Across All Campaigns

### Flagship: IM agencies & SaaS_US&EU (2947684)


| Step      | Sent      | Replies | Reply Rate | Bounces | Bounce Rate | % of All Replies |
| --------- | --------- | ------- | ---------- | ------- | ----------- | ---------------- |
| 1         | 1,980     | 91      | **4.6%**   | 58      | 2.9%        | **74%**          |
| 2         | 1,809     | 20      | 1.1%       | 3       | 0.2%        | 16%              |
| 3         | 1,229     | 11      | 0.9%       | 2       | 0.2%        | 9%               |
| 4         | 680       | 1       | 0.1%       | 0       | 0.0%        | 1%               |
| **Total** | **5,698** | **123** | **2.2%**   | **63**  | —           | **100%**         |


**Key insight:** Step 1 generates 74% of all replies. Each subsequent step has diminishing returns. Step 4 is effectively dead — 680 sends for 1 reply.

### IM_PLATFORMS (2990385)


| Step | Sent | Replies | Reply Rate | Bounces | Bounce Rate |
| ---- | ---- | ------- | ---------- | ------- | ----------- |
| 1    | 649  | 5       | 0.8%       | 8       | 1.2%        |
| 2    | 520  | 4       | 0.8%       | 7       | 1.3%        |
| 3    | 157  | 0       | 0.0%       | 0       | 0.0%        |
| 4    | 0    | 0       | N/A        | 0       | N/A         |


**Note:** Step 2 performs equally to Step 1 here (0.8% each). Campaign is still maturing (step 3-4 barely deployed). Higher bounce rate than flagship suggests database quality issue.

### MARKETING_AGENCIES (2990380)


| Step | Sent | Replies | Reply Rate | Bounces | Bounce Rate |
| ---- | ---- | ------- | ---------- | ------- | ----------- |
| 1    | 265  | 5       | **1.9%**   | 6       | 2.3%        |
| 2    | 191  | 0       | 0.0%       | 3       | 1.6%        |
| 3    | 2    | 0       | 0.0%       | 0       | 0.0%        |
| 4    | 0    | 0       | N/A        | 0       | N/A         |


**Note:** Step 1 works (1.9%), follow-ups generate zero replies. BUT: 0 actionable from 5 replies (all OOO/Not Interested/Wrong Person).

### 0903_AGENCIES (3012864)


| Step | Sent | Replies | Reply Rate | Bounces | Bounce Rate |
| ---- | ---- | ------- | ---------- | ------- | ----------- |
| 1    | 469  | 3       | 0.6%       | 9       | 1.9%        |
| 2    | 286  | 0       | 0.0%       | 0       | 0.0%        |
| 3    | 9    | 0       | 0.0%       | 0       | 0.0%        |
| 4    | 0    | 0       | N/A        | 0       | N/A         |


### 0903_PLATFORMS (3012806)


| Step | Sent | Replies | Reply Rate | Bounces | Bounce Rate |
| ---- | ---- | ------- | ---------- | ------- | ----------- |
| 1    | 526  | 1       | 0.2%       | 2       | 0.4%        |
| 2    | 182  | 0       | 0.0%       | 0       | 0.0%        |
| 3    | 15   | 0       | 0.0%       | 0       | 0.0%        |
| 4    | 0    | 0       | N/A        | 0       | N/A         |


**Worst performing campaign.** 526 sends, 1 reply (Do Not Contact). Zero actionable.

### 1103_PR_firms (3022952) — BROKEN


| Step | Sent   | Replies | Reply Rate | Bounces | Bounce Rate |
| ---- | ------ | ------- | ---------- | ------- | ----------- |
| 1    | **17** | 0       | 0.0%       | 0       | 0.0%        |
| 2    | 263    | 3       | 1.1%       | **28**  | **10.6%**   |
| 3    | 75     | 0       | 0.0%       | 0       | 0.0%        |
| 4    | 0      | 0       | N/A        | 0       | N/A         |


**CRITICAL ISSUES:**

1. Step 1 only sent 17 emails — campaign setup is broken. Most leads skipped Step 1.
2. Step 2 has 10.6% bounce rate — MASSIVE deliverability risk. This damages sender domain reputation.
3. All 3 replies = 2 OOO + 1 Wrong Person = 0 actionable.

## Cross-Campaign Insights

### 1. Step 1 is everything

Across all campaigns, Step 1 generates the vast majority of genuine interest. Follow-ups primarily catch OOO auto-responders returning to their inbox.

### 2. Step 4 should be eliminated or radically changed

In the flagship: 680 sends → 1 reply. That's 0.15%. The current "Are you the right person?" close doesn't work after 3 prior touches.

### 3. Bounce rates reveal database quality


| Campaign            | Step 1 Bounce Rate | Issue?                           |
| ------------------- | ------------------ | -------------------------------- |
| Flagship            | 2.9%               | Acceptable but could be lower    |
| IM_PLATFORMS        | 1.2%               | OK                               |
| MARKETING_AGENCIES  | 2.3%               | OK                               |
| 0903_AGENCIES       | 1.9%               | OK                               |
| 0903_PLATFORMS      | 0.4%               | Best                             |
| **PR_firms Step 2** | **10.6%**          | **CRITICAL — pause immediately** |


### 4. Follow-up timing matters

In the flagship, Step 2 gets 1.1% reply rate — decent for a follow-up. But in newer campaigns, Step 2 gets 0% across the board. Either:

- The newer campaigns haven't matured enough
- The follow-up copy is weaker in newer campaigns
- The flagship's high Step 2 performance is driven by OOO returns

### 5. Estimated total emails sent across all steps


| Campaign           | Total Sent (all steps) |
| ------------------ | ---------------------- |
| Flagship           | 5,698                  |
| IM_PLATFORMS       | 1,326                  |
| MARKETING_AGENCIES | 458                    |
| 0903_AGENCIES      | 764                    |
| 0903_PLATFORMS     | 723                    |
| PR_firms           | 355                    |
| **TOTAL**          | **9,324**              |


