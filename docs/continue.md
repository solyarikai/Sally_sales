# Continue: Global Project Filter + Projects Page

## Current Bug: `/projects` route not matched

The browser shows `No routes matched location "/projects"` even though the route IS correctly defined in `frontend/src/App.tsx` line 114. This is a **Vite HMR issue** — the dev server didn't hot-reload the new route.

**Fix:** Restart the Vite dev server (`cd frontend && npm run dev`) or hard refresh (`Cmd+Shift+R`). If that doesn't work, check that `frontend/src/App.tsx` has the import and route:

```tsx
// Line 17
import { ProjectsPage } from './pages/ProjectsPage';

// Lines 113-118
<Route path="/projects" element={
  <Layout>
    <ProjectsPage />
  </Layout>
} />
```

---

## What Was Implemented (all code is written and saved)

### Backend (2 changes)

1. **`backend/app/api/contacts.py`** — Added `GET /contacts/projects/list-lite` endpoint (before `/projects/list`)
   - Returns `[{id, name, campaign_filters}]` — no contact count queries, instant response
   - Verified working: `curl http://localhost:8000/api/contacts/projects/list-lite` returns 16 projects

2. **`backend/app/api/replies.py`** — Added `campaign_names` query param to:
   - `GET /replies/` (line ~593) — filters ProcessedReply.campaign_name.in_(names) on main query + count query
   - `GET /replies/stats` (line ~668) — filters all 7 sub-queries (total, category, today, week, slack, status, automation)
   - Verified working: `curl "http://localhost:8000/api/replies/?campaign_names=Internal+-+Sally+B2B+general+-+Ksenia"` returns 520 filtered results

### Frontend (7 changes)

3. **`frontend/src/api/contacts.ts`** — Added:
   - `ProjectLite` interface: `{id: number, name: string, campaign_filters: string[]}`
   - `listProjectsLite()` method on `contactsApi`

4. **`frontend/src/api/replies.ts`** — Added `campaign_names?: string` param to `getReplies()` and `getReplyStats()`

5. **`frontend/src/store/appStore.ts`** — Added:
   - `currentProject: ProjectLite | null` to state
   - `setCurrentProject` action
   - `currentProject` in `partialize` for localStorage persistence
   - Import of `ProjectLite` type

6. **`frontend/src/components/Layout.tsx`** — Added:
   - `FolderOpen` icon import from lucide-react
   - `contactsApi` and `ProjectLite` imports
   - `showProjectDropdown`, `projects`, `projectDropdownRef` state
   - `useEffect` to load projects via `listProjectsLite()` on mount
   - Click-outside handler for project dropdown
   - Project selector dropdown UI (violet accent) between company selector and nav items
   - "Projects" nav item with FolderOpen icon (before "Replies")

7. **`frontend/src/pages/RepliesPage.tsx`** — Added:
   - `useAppStore` import, reads `currentProject`
   - `loadReplies`: builds `campaignNames` from `currentProject.campaign_filters.join(',')`, passes to API
   - `loadStats`: same campaign_names logic
   - Both callbacks have `currentProject` in dependency array
   - `useEffect` to reset `page` to 1 when `currentProject` changes

8. **`frontend/src/pages/ProjectsPage.tsx`** — NEW FILE with:
   - List all projects (via `listProjectsLite()`)
   - Create new project with name + campaign filter picker
   - Edit project (name + add/remove campaign filters)
   - Delete project with confirmation
   - Campaign search/autocomplete from `/contacts/campaigns` endpoint
   - CampaignPicker sub-component with search dropdown, selected chips with X to remove

9. **`frontend/src/App.tsx`** — Added:
   - `import { ProjectsPage } from './pages/ProjectsPage'`
   - `<Route path="/projects">` wrapped in `<Layout>`

## After Restart: Test Checklist

1. Open `http://localhost:5173/projects` — should show 16 existing projects with campaign counts
2. Click "New Project" → type "Rizzult" → search "rizzult" in campaign picker → add all 9 Rizzult campaigns → Create
3. Open `http://localhost:5173/replies` — should see project dropdown in header saying "All Projects"
4. Click project dropdown → select "Rizzult" → replies should filter (note: no Rizzult replies exist in local DB, so it'll show 0 — that's correct, they only exist on production)
5. Select "All Projects" → all replies show again
6. Refresh page → project filter persists (localStorage)

## Data Notes

- **No "Rizzult" project exists yet** — user needs to create it via `/projects` page
- **9 Rizzult campaigns** exist in contacts: `Rizzult Fintech 22.11.25 Aleks`, `Rizzult Shopping Aleks 09.12.25`, `Rizzult Food&Drink 24.01.26 Aleks`, etc.
- **No Rizzult replies in local DB** — the `processed_replies` table only has ~7182 replies from Internal/EasyStaff/SquareFi/Deliryo campaigns. Rizzult replies only exist on the production server (`http://46.62.210.24:8000`)
- The `campaign_names` filter is verified working with existing campaign names

## Files Changed (summary)

```
backend/app/api/contacts.py    — added list-lite endpoint
backend/app/api/replies.py     — added campaign_names filter to list + stats
frontend/src/api/contacts.ts   — added ProjectLite type + listProjectsLite()
frontend/src/api/replies.ts    — added campaign_names param
frontend/src/store/appStore.ts  — added currentProject state
frontend/src/components/Layout.tsx — added project selector + Projects nav item
frontend/src/pages/RepliesPage.tsx — wired project filter to API calls
frontend/src/pages/ProjectsPage.tsx — NEW: project management page
frontend/src/App.tsx            — added /projects route
docs/continue.md               — this file
```
