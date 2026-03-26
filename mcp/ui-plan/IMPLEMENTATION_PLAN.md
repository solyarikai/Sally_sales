# MCP UI — Component Reuse Implementation Plan

## Context

The MCP UI has garbage custom components instead of reusing the main app's production-grade ones. User asked 5+ times to REUSE. The goal: main app components imported directly via Vite alias, MCP backend serves compatible API responses. Fix once → fixed everywhere.

## Architecture: Vite Alias (NOT copy)

```
mcp/frontend/vite.config.ts:
  resolve: {
    alias: {
      '@main': '../../frontend/src'   // points to main app's source
    }
  }
```

MCP pages import directly from main app:
```tsx
import { ContactsPage } from '@main/pages/ContactsPage'
import { ReplyQueue } from '@main/components/ReplyQueue'
import { themeColors } from '@main/lib/themeColors'
```

**Fix once in main app → fixed in MCP automatically. No copying, no drift.**

## Steps

### Step 1: Vite alias + dependencies

**Files**: `mcp/frontend/vite.config.ts`, `mcp/frontend/package.json`

Add `@main` alias. Install ALL main app deps so imports resolve:
- axios, zustand, @tanstack/react-table, @radix-ui/react-toast
- clsx, tailwind-merge, react-hot-toast
- ag-grid-community, ag-grid-react, lucide-react (already installed)

### Step 2: API compatibility layer

**File**: `mcp/frontend/src/api/client.ts`

Main app uses axios with `.get()/.post()/.patch()`. Create compatible client:

```ts
import axios from 'axios'
export const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => {
  config.headers['X-Company-ID'] = '1'
  config.headers['X-MCP-Token'] = localStorage.getItem('mcp_token') || ''
  return config
})
```

### Step 3: MCP backend `/api/contacts` endpoint

**File**: `mcp/backend/app/api/contacts.py` (NEW)

Serve the EXACT same API contract as main app:
- `GET /api/contacts` → `{contacts, total, page, page_size, total_pages}`
- `GET /api/contacts/stats` → `{total, by_status, by_segment, by_source, by_project}`
- `GET /api/contacts/filters` → `{statuses, sources, segments, geos, projects}`
- `GET /api/contacts/projects/names` → `[{id, name}]`

Each contact returns: id, email, first_name, last_name, company_name, domain, job_title, source, status, has_replied, campaigns, created_at, updated_at

### Step 4: Pages via @main alias

| MCP Route | Source | Import | Notes |
|-----------|--------|--------|-------|
| `/crm` | Main app ContactsPage | `@main/pages/ContactsPage` | AG Grid, 15+ columns, URL filters |
| `/tasks/:tab` | Main app TasksPage | `@main/pages/TasksPage` | Tabs: replies, follow-ups. Category subtabs: Meetings, Interested, Questions, etc. Shows ReplyQueue with AI drafts, approve/skip/warm buttons |
| `/tasks/replies` | TasksPage tab=replies | Same component, tab routing | Default tab |
| `/tasks/followups` | TasksPage tab=followups | Same component, tab routing | Follow-up drafts |
| `/projects` | Main app ProjectsPage | `@main/pages/ProjectsPage` | Project list, create, ICP, sender, campaigns |
| `/projects/:id` | Main app ProjectPage | `@main/pages/ProjectPage` | Project detail with sub-tabs |
| `/actions` | Main app OperatorActionsPage | `@main/pages/OperatorActionsPage` | Operator corrections log → links to Learning |
| `/knowledge/:tab` | Main app KnowledgePage | `@main/pages/KnowledgePage` | Tab=logs for Learning (operator corrections, patterns learned) |
| `/pipeline` | Keep MCP version | Local | Pipeline runs list |
| `/pipeline/:runId` | Keep MCP version | Local | Pipeline detail (MCP-specific) |
| `/setup` | Keep MCP version | Local | MCP-specific auth/tokens |

**Key**: Tasks page uses tab routing (`/tasks/replies`, `/tasks/followups`) matching the main app's pattern. The screenshot shows: Replies tab (with count badge), Follow-ups tab (with count badge), Meetings tab. Category subtabs within replies: All, Meetings, Interested, Questions, Not Interested, OOO, Wrong Person, Unsubscribe.

### Step 5: Delete stubs

Remove all duplicated stubs in `mcp/frontend/src/`:
- components/Toast.tsx → use @main
- components/ErrorBoundary.tsx → use @main
- components/ConfirmDialog.tsx → use @main
- components/filters.tsx → use @main
- lib/utils.ts → use @main
- lib/themeColors.ts → use @main
- hooks/useTheme.ts → use @main
- store/appStore.ts → use @main

### Step 6: Docker build context

Update `mcp/frontend/Dockerfile` to include main app source in build context:
```dockerfile
# Need access to ../../frontend/src for @main alias
COPY ../../frontend/src /main-app-src
```

Or: mount via docker-compose volume:
```yaml
mcp-frontend:
  build:
    context: ../  # repo root, so both frontend/ and mcp/frontend/ are accessible
    dockerfile: mcp/frontend/Dockerfile
```

## Files to modify

| File | Change |
|------|--------|
| `mcp/frontend/vite.config.ts` | Add @main alias |
| `mcp/frontend/package.json` | Add axios, zustand, @tanstack, @radix-ui, etc. |
| `mcp/frontend/Dockerfile` | Adjust build context for @main access |
| `mcp/docker-compose.mcp.yml` | Adjust build context for frontend |
| `mcp/frontend/src/api/client.ts` | Rewrite as axios instance |
| `mcp/frontend/src/App.tsx` | Import from @main, add Learning route |
| `mcp/backend/app/api/contacts.py` | NEW: /api/contacts with main app contract |
| `mcp/backend/app/main.py` | Mount contacts router |
| Delete 8+ stub files | Remove duplicated garbage |

## Verification

1. `docker-compose up --build mcp-frontend` → builds without errors
2. `http://46.62.210.24:3000/crm` → AG Grid with real contacts, URL filters work
3. `http://46.62.210.24:3000/crm?search=dileep` → filters to dileep
4. `http://46.62.210.24:3000/replies` → real ReplyQueue
5. Click contact row → ContactDetailModal with conversation tab
6. Edit main app's ContactsPage.tsx → automatically reflected in MCP
