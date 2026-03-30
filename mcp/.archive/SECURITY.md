# MCP Security & Data Isolation

## ABSOLUTE RULE: User Data Isolation

Every user sees ONLY their own data. No exceptions.

### Main App (old approach — DO NOT replicate)
- Single shared account: `ilovesally` / `BdaP31NNXX4ZCyvU`
- Everyone sees everything
- No user isolation
- URL: http://46.62.210.24

### MCP System (new approach — STRICT isolation)
- Each user signs up with their own email
- Each user gets their own API token (`mcp_xxx...`)
- Each user connects their own API keys (SmartLead, Apollo, etc.)
- Each user creates their own projects
- Each user sees ONLY:
  - Their own projects
  - Their own pipeline runs
  - Their own gathered companies
  - Their own imported contacts
  - Their own campaigns
  - Their own usage logs
- **No user can see another user's data. EVER.**

## Authentication Method

### API Token (current)
- Token format: `mcp_` + 64 hex chars
- Created at signup, shown once
- Stored as bcrypt hash in DB
- Passed via `X-MCP-Token` header or `Authorization: Bearer` header

### Web UI Session (to implement)
- User logs in via web UI with email + token (or future: email + password)
- Backend sets an HTTP-only cookie with session ID
- Session stored in Redis (expires after 24h)
- Cookie sent automatically on every request
- Links shared via URL work only if the user is logged in
- If not logged in → redirect to `/setup` (login page)

### MCP SSE Connection
- Token passed in the first POST to `/mcp/messages` via `Authorization: Bearer` header
- Stored per-session in `_session_tokens` dict
- All tool calls in that session use this token

### Telegram Bot
- Telegram user ID mapped to MCP token via Redis session
- Token stored after first `setup_account` call
- All subsequent tool calls use stored token

## Data Scoping Rules

Every database query MUST include `user_id` or `project.user_id` filter.

### Endpoints that MUST be user-scoped

| Endpoint | Scope by |
|----------|----------|
| `GET /api/contacts` | `project.user_id = current_user.id` |
| `GET /api/contacts/stats` | Same |
| `GET /api/pipeline/runs` | `run.project.user_id = current_user.id` |
| `GET /api/pipeline/projects` | `project.user_id = current_user.id` |
| `GET /api/pipeline/crm/*` | `project.user_id = current_user.id` |
| `GET /api/pipeline/iterations` | Same |
| `GET /api/pipeline/usage-logs` | `log.user_id = current_user.id` |
| `GET /api/replies` | `project.user_id = current_user.id` |
| All MCP tool calls | Token → user_id → filter everything |

### Endpoints that are public (no auth)

| Endpoint | Why |
|----------|-----|
| `GET /api/health` | Health check |
| `POST /api/auth/signup` | Creating new account |
| `GET /api/pipeline/runs/{id}` | Shared via link (read-only, no sensitive data) |

### What happens when user shares a link

When a user shares `http://46.62.210.24:3000/pipeline/8`:
- The pipeline page loads and shows the run data (read-only, no auth required for viewing)
- But CRM links like `/crm?project_id=3` require login
- If not logged in → redirect to `/setup`

## Cookie-Based Session for Web UI

### Flow:
1. User opens `/setup`, enters email + API token
2. Backend verifies token → creates session → sets cookie
3. All subsequent page loads include cookie → backend extracts user_id
4. Contacts/CRM/Tasks pages filter by user_id automatically

### Implementation:
```python
# On login:
session_id = secrets.token_hex(32)
await redis.set(f"session:{session_id}", user_id, ex=86400)
response.set_cookie("mcp_session", session_id, httponly=True, samesite="lax")

# On every request:
session_id = request.cookies.get("mcp_session")
user_id = await redis.get(f"session:{session_id}")
```

### Why cookie + token (not just token)?
- Token auth works for API calls and MCP protocol
- But web UI needs cookie-based auth so:
  - Links work without pasting token in URL
  - Browser automatically sends cookie
  - No token exposure in URLs or localStorage (httponly cookie)

## NEVER DO

- Never return data from other users
- Never trust client-side filtering (always filter on backend)
- Never put user tokens in URLs
- Never log full API tokens (only prefix)
- Never share Redis sessions between users
- Never skip user_id filter in any query
