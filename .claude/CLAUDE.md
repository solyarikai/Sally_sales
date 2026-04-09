# Sales Engineer

Sales automation tooling for Sally — B2B outreach infrastructure for OnSocial (creator/influencer data API).

## Pipeline Overview

The core workflow is a 12-step leadgen pipeline (`magnum-opus/scripts/sofia/onsocial_universal_pipeline.py`):

```
Step 0: GATHER    — find companies (Clay ICP / Clay Keywords / Clay Lookalike / Apollo internal API)
Step 1: DEDUP     — skip companies already in discovered_companies
Step 2: BLACKLIST — filter against project exclusion list
Step 3: PREFILTER — remove non-target industries/sizes (deterministic)
Step 4: SCRAPE    — fetch homepage HTML via backend
Step 5: CLASSIFY  — GPT-4o-mini scores: is_target? which segment?
Step 6: VERIFY    — manual QA on classification accuracy (checkpoint)
Step 7: ADJUST    — re-classify with tuned prompt if accuracy < 90%
Step 8: EXPORT    — ship approved targets
Step 9: PEOPLE    — find decision-makers via Apollo (Puppeteer, free)
Step 10: FINDYMAIL — enrich with emails ($0.01/found)
Step 11: SEQUENCES — generate 5-step email sequences
Step 12: UPLOAD   — create SmartLead campaign & load leads
```

Key scripts: `onsocial_universal_pipeline.py` (orchestrator), `onsocial_apollo_people_search.js` (Puppeteer people search), `onsocial_apollo_companies_search.js` (company search by keywords).

## ICP Segments

| Code | Full Name | Target Profile |
|------|-----------|---------------|
| `INFPLAT` | Influencer Platforms | SaaS platforms for creator data/analytics (5-5K employees) |
| `IMAGENCY` | IM-First Agencies | Agencies with dedicated influencer practice (10-200 employees) |
| `AFFPERF` | Affiliate Performance | Affiliate platforms bundling creator data |
| `SOCCOM` | Social Commerce | Marketplace + live shopping platforms (LTK, ShopMy, Bazaarvoice) |

Filter definitions: `sofia/projects/OnSocial/docs/apollo-filters-v4.md`
Segment docs: `sofia/projects/OnSocial/docs/segment-*.md`

## Execution Environment — Hetzner

- **All scripts, DB queries, scrapers run on Hetzner.** Local machine is for code editing only.
- SSH: `ssh hetzner` (host alias in ~/.ssh/config)
- DB: `ssh hetzner "docker exec leadgen-postgres psql -U leadgen -d leadgen -c 'SQL'"`
- Backend container: `leadgen-backend` (FastAPI on port 8000)
- Deploy: `ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main && docker-compose up --build -d"`
- Env vars: `set -a && source .env && set +a` before running Python scripts directly
- **sofia/ scripts are NOT on Hetzner by default.** SCP first: `scp sofia/scripts/foo.py hetzner:~/magnum-opus-project/repo/sofia/scripts/`
- Hetzner repo path: `~/magnum-opus-project/repo`

## Google Sheets & Drive

**Use MCP tools** (`google-sheets` server) for all Sheets/Drive operations. Never write Python scripts for this. Never use service account / Docker.

**Dual Save Rule**: every CSV saved locally MUST also be uploaded to Google Sheets (same name). Every Sheets read -> save local copy.

Naming convention and protected sheets: see `.claude/rules/sheets-reference.md`

## GetSales Export

Contacts without email from Findymail -> auto-export to GetSales-ready CSV in `sofia/get_sales_hub/{dd_mm}/` (49-column format). Built into pipeline scripts.

## Local Python

- Use `python3.11` (homebrew) — has google-auth, google-api-python-client
- System `python3` (3.9) lacks dependencies, no write access to site-packages

## Project Structure

| Directory | What |
|-----------|------|
| `magnum-opus/` | Backend (FastAPI + SQLAlchemy), gathering pipeline, API — **GIT SUBMODULE** |
| `sofia/` | Sales ops: scripts, sequences, research, projects |
| `sofia/projects/OnSocial/` | OnSocial-specific sequences, docs, segments |
| `sofia/smartlead-hub/` | SmartLead campaigns, sequences, lead data |
| `tam-guide/` | Training/onboarding materials (HTML lessons) |
| `scripts/` | Shared utility scripts |
| `.claude/mcp/` | MCP servers (apollo, crona, google-sheets, smartlead, findymail, getsales, transkriptor) |
| `.claude/skills/` | Shared Claude Code skills |
| `.claude/rules/` | Path-scoped rules (sheets naming, SmartLead formatting) |

## Gotchas

- **Backend crashes on 3000+ sites** in one run — always batch by 500
- **Apollo People search** returns person location, NOT company country. For geo-based sequences, use `company_country` field from target data
- **Apollo login** requires email verification from unknown IPs — use Hetzner IP directly, no Apify proxy
- **Clay free plan** = 100 results/search, not unlimited (period resets monthly)
- **Backend API `/analyze`** requires `prompt_text`, NOT `prompt_id`
- **Classification accuracy gate**: if < 90%, must re-tune prompt before proceeding (Step 7)
- **SmartLead gotchas**: see `.claude/rules/smartlead-formatting.md`
- **Pipeline script edits**: always apply changes point-by-point to ALL copies (`sofia/scripts/`, `magnum-opus/scripts/`, Hetzner). Never overwrite the whole file — copies may have diverged with independent fixes.
