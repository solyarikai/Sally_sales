# Sales Engineer

Sales automation tooling for Sally — B2B outreach infrastructure for OnSocial (creator/influencer data API).

## ICP Segments

| Code       | Full Name             | Target Profile                                      |
| ---------- | --------------------- | --------------------------------------------------- |
| `INFPLAT`  | Influencer Platforms  | SaaS for creator data/analytics                     |
| `IMAGENCY` | IM-First Agencies     | Agencies with dedicated influencer practice        |
| `AFFPERF`  | Affiliate Performance | Affiliate platforms bundling creator data           |
| `SOCCOM`   | Social Commerce       | Live shopping / creator marketplaces (LTK, ShopMy)  |

Filters: `sofia/projects/OnSocial/docs/apollo-filters-v5.md`
Segment docs: `sofia/projects/OnSocial/docs/segment-*.md`

## Execution — Hetzner

All scripts, DB queries, scrapers run on Hetzner. Local machine = code editing only.

- SSH: `ssh hetzner` (alias in `~/.ssh/config`)
- Repo: `~/magnum-opus-project/repo`
- DB: `ssh hetzner "docker exec leadgen-postgres psql -U leadgen -d leadgen -c 'SQL'"`
- Backend container: `leadgen-backend` (FastAPI :8000)
- Deploy: `ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main && docker-compose up --build -d"`
- Hetzner python = `python3` (3.12), local python = `python3.11` (homebrew, has google-auth)
- `sofia/` scripts not on Hetzner by default — SCP first

## Integration Rules (`.claude/reference/` — read on demand)

- **SmartLead formatting** → `.claude/reference/smartlead-formatting.md`
- **GetSales CSV format** → `.claude/reference/getsales-formatting.md`
- **Pipeline phase state machine** → `.claude/reference/pipeline-phases.md`
- **Classify prompt format** → `.claude/reference/classify-prompt-format.md`
- **Company normalization** → `.claude/reference/company-normalization.md`
- **Google Sheets naming** → `.claude/reference/sheets-reference.md`
- **Sheets naming & protected tabs** → `sheets-reference.md`

Google Sheets/Drive — use MCP tools only, never Python/service-account. Dual save: local CSV ↔ Sheets with same name.

## Destructive Gotchas (non-obvious, will corrupt data)

- **NEVER bypass scraping** — don't populate `scraped_text` from Apollo descriptions. Too sparse → ~2% target rate vs expected 20-40%. Debug scrape endpoint instead (DB locks, event loop blocking).
- **NEVER test `/analyze` endpoint** — backend re-classifies ALL companies in the run with whatever prompt you send, even test stubs. Verify via code/logs only.
- **Backend crashes on 3000+ sites/run** — always batch by 500.
- **`--apollo-csv` does NOT feed findymail/upload** — loads into Step 9 cache. For `--from-step upload`, write contacts to `state/onsocial/enriched.json` directly.
- **Pre-populate `state/onsocial/upload_log.json`** with `{"SEGMENT": {"campaign_id": N}}` to reuse existing SmartLead campaign on `--from-step upload`.
- **SmartLead DRAFT leads count = 0** via local smartlead.py (`total_stats` omitted). Verify via direct API from Hetzner.
- **Classification accuracy gate**: < 90% → re-tune prompt (Step 7) before proceeding.
- **Pipeline script edits — apply to ALL copies**: `sofia/scripts/`, `magnum-opus/scripts/`, Hetzner. Copies diverge independently.
- **Findymail / SmartLead / blacklist — always via pipeline**, never custom scripts. Pipeline handles dedup, logging, state.
- **Apollo login** requires email verify from unknown IPs — use Hetzner IP, no Apify proxy.
- **`postgres COPY TO '/tmp/...'`** writes inside container. Extract: `docker cp leadgen-postgres:/tmp/file.csv /tmp/file.csv`.

## Data Integrity Rules

- **Never assume duplicates without verifying by linkedin_url/nickname.** Files with different dates are different exports — don't skip them. Always check field-level match, not just filename similarity.
- **Before declaring "0 new contacts"** — verify by actually comparing nicknames, not by assumption.
- **Two files named similarly ≠ same data.** Date in filename = different snapshot. Always read and compare.

## Epistemic Rules (don't assert without checking)

- **Never state facts about a file without reading it first.** Filename, path, or context don't tell you the contents. Read first, then claim.
- **Never state facts about live data (counts, statuses, campaign state, API responses) from memory.** Query or fetch first.
- **Never state facts about external products, APIs, or services without verifying.** Training data is stale. If context suggests the fact matters — use Exa to check.
- **Hedging is required when unverified.** Say "probably", "likely", or "I'd need to check" rather than asserting. One false confident claim wastes more time than one honest hedge.

## Structure

- `magnum-opus/` — backend, gathering pipeline (**git submodule**)
- `sofia/` — sales ops: scripts, sequences, projects, research
- `sofia/smartlead-hub/` — campaigns, sequences, lead data
- `.claude/mcp/` — MCP servers (apollo, smartlead, findymail, getsales, google-sheets, crona, transkriptor)
- `.claude/rules/` — path-scoped integration rules
