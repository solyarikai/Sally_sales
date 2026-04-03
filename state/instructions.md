# Instructions - Magnum Opus Project

## SAFETY RULES (CRITICAL - NEVER VIOLATE)

### 1. SMARTLEAD: READ-ONLY
- **NEVER** send messages via Smartlead API
- **NEVER** modify lead data in Smartlead
- **ONLY** read campaigns, leads, and replies
- If any code attempts to write to Smartlead, STOP and report blocker

### 2. GOOGLE SHEETS: CREATE NEW ONLY
- **NEVER** modify existing sheets
- **ONLY** create new sheets for logging
- Always use service account credentials

### 3. SLACK: DRAFT PREVIEW
- Show AI drafts for human approval
- **NEVER** auto-send replies without human confirmation
- Use interactive buttons: Approve / Edit / Skip

### 4. APOLLO: NO CREDITS
- Test API calls before production usage
- Company exports should NOT spend credits
- Use search endpoints that are free/cheap

---

## Project Context

**Project:** Magnum Opus - Lead Generation Platform
**Server:** 46.62.210.24 (Hetzner)
**User:** leadokol

### Repositories & Branches

| Feature | Repo | Branch |
|---------|------|--------|
| Reply Automation | sally-saas/magnum-opus | replies310126 |
| Data Search | sally-saas/magnum-opus | data300126 |
| Auto-coder | sally-saas/auto-coder | main |

### Stack
- Backend: Python/FastAPI (port 8000)
- Frontend: React/TypeScript (nginx, port 80)
- Database: PostgreSQL (Docker: leadgen-postgres)
- Cache: Redis (Docker: leadgen-redis)
- Deployment: Docker Compose

### URLs
- App: http://46.62.210.24
- API: http://46.62.210.24:8000/api/
- Replies: http://46.62.210.24/replies
- Data Search: http://46.62.210.24/data-search

### API Keys (in .env)
- SMARTLEAD_API_KEY
- SLACK_BOT_TOKEN
- OPENAI_API_KEY
- GOOGLE_APPLICATION_CREDENTIALS
- APOLLO_API_KEY (for data search)

---

## Current Feature: Reply Automation (replies310126)

### 4-Step Setup Wizard
1. Select Smartlead campaigns
2. Create/select Google Sheet
3. Configure Slack notifications ← **COMPLETED: Channel selector dropdown**
4. Review and activate

### Key Files
**Backend:**
- `backend/app/services/smartlead_service.py` - READ-ONLY Smartlead integration
- `backend/app/services/notification_service.py` - Slack notifications
- `backend/app/services/google_sheets_service.py` - Google Sheets (create only)
- `backend/app/api/replies.py` - Reply automation endpoints

**Frontend:**
- `frontend/src/pages/RepliesPage.tsx` - Main wizard page
- `frontend/src/api/replies.ts` - API client

---

## Future Feature: AI SDR (PROJECT-BASED)

AI Sales Development Representative that:
1. Analyzes all contacts in the system
2. Groups by PROJECT (each project has its own contacts)
3. Auto-generates TAM (Total Addressable Market) per project
4. Creates go-to-market plan per project
5. Generates pitch templates per industry/segment
6. Delivers offer recommendations automatically

### Project Structure
Each project should have:
- Name, description
- Target industries/segments
- Associated contacts (from CRM)
- Generated TAM analysis
- Generated GTM plan
- Generated pitch templates

---

## CRM: Contacts Table

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| project_id | UUID | FK to projects table |
| email | String | Contact email |
| first_name | String | First name |
| last_name | String | Last name |
| company_name | String | Company |
| company_domain | String | Website domain |
| job_title | String | Position |
| industry | String | Industry/segment |
| company_size | String | Employee range |
| location | String | Country/city |
| source | String | Where contact came from (apollo, smartlead, manual) |
| smartlead_lead_id | String | If from Smartlead |
| apollo_person_id | String | If from Apollo |
| status | String | lead, contacted, replied, qualified, customer |
| last_contacted | DateTime | Last outreach date |
| notes | Text | Free-form notes |
| created_at | DateTime | When added |
| updated_at | DateTime | Last modified |

### Views Needed
- All contacts (filterable by project)
- Contacts by project
- Contacts by status
- Contacts by source

---

## Data Search Feature (data300126)

### Explee-like UX
1. Chat input for natural language query
2. AI parses into Apollo filters
3. Show applied filters as chips (removable)
4. Results table with company data
5. Refinement chat to narrow results
6. Per-row feedback (thumbs up/down)

### Hybrid Search Approach
1. Direct: Parse query → Apollo filters → Search
2. Reverse Engineering: Get known companies → Extract their Apollo attributes → Search with real filters
3. Verification: Crona scrape websites → OpenAI verify matches → Return only verified

### Key Services
- `reverse_engineering_service.py` - Extract filters from known companies
- `verification_service.py` - Crona + OpenAI to verify matches

---

## Core Principles

### 1. Code Over AI
- Build scripts for repetitive tasks
- Don't rely on AI for things a bash/python script can do
- Create reusable tools, not one-off AI prompts

### 2. BLOCKER HANDLING (CRITICAL)
When you encounter a blocker requiring user action:
1. STOP working on that task
2. Write to `state/blocker.txt`:
   - What is blocked
   - EXACTLY what user needs to do (step by step)
   - Link to relevant docs/settings
3. Bot will immediately notify user via Telegram
4. Move to next task or wait

**Example blockers:**
- "Slack Bot Token needs channels:read scope. Go to api.slack.com/apps → OAuth & Permissions → Add scope"
- "Google credentials file not found. Upload service account JSON"
- "Smartlead API returning 429. Rate limited, wait 1 hour."

### 3. Testing
- End-to-end tests preferred
- Tests should run WITHOUT AI
- `./run_tests.sh` should work standalone
- Tests must pass before commit

### 4. Git Workflow
- Work on appropriate branch (replies310126, data300126, etc.)
- Commit after each meaningful change
- Message format: "Session N: brief description"
- Push when tests pass

---

## Docker Commands

```bash
# View containers
docker ps

# Restart backend
docker restart leadgen-backend

# Rebuild everything
docker-compose down && docker-compose up -d --build

# View logs
docker logs leadgen-backend -f

# Rebuild frontend only
docker-compose build --no-cache frontend && docker-compose up -d frontend
```

---

## Response Format

When completing a task, write to `state/response.txt`:
1. What you did (1-2 sentences)
2. Files changed (list)
3. Tests run (if any)
4. Next steps
5. Any blockers → write to `state/blocker.txt`

---

## STATE PERSISTENCE (Timeout Recovery)

**Purpose:** If agent times out (typically 5 min), it can resume immediately by reading state files.

### State Files

| File | Purpose | Format |
|------|---------|--------|
| `state/agent_progress.md` | Human-readable progress log | Markdown |
| `state/session_context.json` | Machine-readable state | JSON |
| `state/tasks.md` | Full task list | Markdown |
| `state/blocker.txt` | Active blockers | Markdown |

### Agent Progress Protocol

**On Session Start:**
1. Read `state/session_context.json` to get last state
2. Check if `status` is "active" (means last session timed out)
3. Read `action_queue` to continue where left off
4. Resume from `current_task.step`

**During Session (Every Major Action):**
1. Update `state/agent_progress.md` with:
   - Current task and step
   - Progress percentage
   - Files modified
   - Last 5 actions
2. Update `state/session_context.json` with:
   - `last_updated` timestamp
   - `current_task.step` and `progress_percent`
   - `action_queue` (what's left to do)
   - `files_modified` list

**On Session Complete:**
1. Set `status` to "completed" in session_context.json
2. Clear `action_queue`
3. Write final summary to `state/response.txt`

### Recovery Example

```json
// session_context.json after timeout
{
  "status": "active",  // <-- Means timeout, not completed
  "current_task": {
    "id": "task-7",
    "step": 3,
    "total_steps": 5
  },
  "action_queue": [
    "Add quick-action buttons",
    "Improve mobile responsiveness"
  ]
}
```

Agent reads this and immediately:
1. Sees task-7 step 3 was in progress
2. Continues with "Add quick-action buttons"
3. No need to ask user what to do next

### Best Practices

- Update state files BEFORE starting long operations
- Keep `action_queue` accurate (remove completed, add new)
- Log file modifications as they happen
- Include enough context to resume without re-reading code
