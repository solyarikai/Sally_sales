# GTM MCP — Performance Metrics

## API Response Times (Target)

| Endpoint | Target | Notes |
|----------|--------|-------|
| GET /api/health | <50ms | Health check |
| POST /api/auth/signup | <500ms | bcrypt hashing |
| POST /api/auth/login | <500ms | bcrypt verify |
| GET /api/pipeline/runs | <200ms | Batched queries (was N+1, fixed in audit) |
| GET /api/pipeline/iterations | <300ms | With target counts |
| GET /api/pipeline/runs/{id}/companies | <300ms | Paginated (50/page) |
| GET /api/pipeline/campaigns | <400ms | With sequence data |
| GET /api/contacts | <300ms | Paginated, indexed |
| POST /api/tools/call (tam_gather) | <2s | Adapter-dependent |
| POST /api/tools/call (tam_analyze) | <30s | AI analysis, GPT call |
| SSE /mcp/sse | Persistent | Streaming, reconnect with backoff |

## Frontend Load Times (Target)

| Page | Target | Notes |
|------|--------|-------|
| Pipeline page | <1s | Initial load with 50 companies |
| CRM page | <1s | Paginated, 50 contacts |
| Campaigns page | <800ms | With sequence preview |
| Account page | <500ms | Credits + usage stats |

## Database Indexes (Audit Fix)

Migration 005 added:
- `ix_gathering_runs_company_id` — gathering_runs.company_id
- `ix_company_source_links_run` — company_source_links.gathering_run_id
- `ix_extracted_contacts_project` — extracted_contacts.project_id
- `ix_mcp_replies_project` — mcp_replies.project_id
- `ix_mcp_conversation_logs_user` — mcp_conversation_logs.user_id

## Optimizations Applied

1. **N+1 query fix** (P1): list_runs — 4 batched aggregate queries instead of 80+
2. **Gzip compression** (M28): nginx serves compressed responses
3. **SSE bounded array** (M16): max 200 messages in memory
4. **SSE reconnection** (M15): exponential backoff, 5 retries
5. **Pagination caps**: all list endpoints have le= constraints
6. **Body size limit**: 10MB max request body
