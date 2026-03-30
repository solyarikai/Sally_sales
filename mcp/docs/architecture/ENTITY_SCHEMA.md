# MCP Entity Schema — Relationships & Flow

## Core Entities

```
User (mcp_users)
  ├── Projects (1:N)
  │     ├── target_segments (ICP + website context)
  │     ├── sender_name/company/position
  │     ├── campaign_filters (SmartLead campaign matching rules)
  │     │
  │     ├── GatheringRuns (1:N) — one per segment+geo combination
  │     │     ├── source_type, filters, credits_used
  │     │     ├── current_phase (gather→blacklist→CP1→filter→scrape→analyze→CP2→campaign)
  │     │     ├── CompanySourceLinks → DiscoveredCompanies (N:M)
  │     │     └── ApprovalGates (checkpoints)
  │     │
  │     ├── DiscoveredCompanies (1:N, unique by domain per project)
  │     │     ├── is_blacklisted (from imported campaigns)
  │     │     ├── is_target, analysis_segment, analysis_confidence
  │     │     ├── CompanyScrapes (website content)
  │     │     └── ExtractedContacts (people found at this company)
  │     │
  │     ├── GeneratedSequences (email sequences)
  │     │     └── pushed_campaign_id → Campaigns
  │     │
  │     └── Campaigns (SmartLead campaigns, DRAFT until activated)
  │           ├── external_id (SmartLead campaign ID)
  │           └── status (draft/active/paused)
  │
  ├── IntegrationSettings (API keys: smartlead, apollo, openai, gemini)
  ├── ApiTokens (auth)
  ├── UsageLogs (every tool call)
  └── ConversationLogs (MCP protocol messages)
```

## Flow: From User Prompt to Campaign

```
User: "Gather IT consulting in Miami and video production in London for EasyStaff"
  │
  ▼
parse_gathering_intent → {segments: [IT_CONSULTING/Miami, VIDEO_PROD/London]}
  │
  ▼ (per segment)
tam_gather → GatheringRun created, companies from Apollo
  │
  ▼
tam_blacklist_check → cross-check against project's imported campaigns
  │                    (project-level blacklist, NOT per-pipeline)
  ▼
tam_approve_checkpoint (CP1) → user confirms scope
  │
  ▼
tam_scrape → website content fetched
  │
  ▼
tam_analyze → GPT classifies targets with user's segment label
  │
  ▼
tam_approve_checkpoint (CP2) → user reviews targets
  │
  ▼
god_generate_sequence → GOD_SEQUENCE with offer context
  │
  ▼
god_push_to_smartlead → DRAFT campaign (NEVER auto-activated)
  │
  ▼
test email auto-sent → user checks inbox
  │
  ▼
activate_campaign → ONLY after explicit user approval
```

## Blacklist = Project Level

Blacklist is NOT per-pipeline. It's per-project:
- When user imports "petr" campaigns → contacts loaded to project's blacklist
- ALL pipelines under this project check against the SAME blacklist
- Blacklist progress shown on PROJECT page (not pipeline page)
- Multiple pipelines can run simultaneously — all check same blacklist

## Multi-Project in One Prompt

```
User: "Gather IT consulting Miami for EasyStaff AND influencer platforms UK for OnSocial"
  │
  ▼
Agent detects: 2 different projects
  ├── EasyStaff-Global: IT consulting, Miami
  └── OnSocial-UK: influencer platforms, UK

Each project:
  1. Check/create project
  2. Ask about existing campaigns (if not known)
  3. Import blacklist (project-level)
  4. Run pipeline(s)
  5. Generate campaign
```
