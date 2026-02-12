---
name: Pipeline and Chat UI fixes
overview: Fix the Pipeline page filters (move to column headers like CRM, add loading indicator, add cost tracking) and restore project selection in the Data Search chat page by connecting it to the global project store.
todos:
  - id: pipeline-column-filters
    content: Move Pipeline page filters (project, status, target, search) into table column headers
    status: completed
  - id: pipeline-loading
    content: Add loading indicator to project dropdown while projects load
    status: completed
  - id: pipeline-cost
    content: Add cost/spending summary card to Pipeline page using search spending API
    status: completed
  - id: chat-project
    content: Connect DataSearchPage chat to global currentProject from app store
    status: completed
  - id: deploy-ui
    content: Build, deploy to Hetzner, verify UI changes
    status: completed
isProject: false
---

# Pipeline and Chat UI Fixes

Three areas to fix based on the UI feedback in [tasks/ui.md](tasks/ui.md):

## 1. Pipeline page: move filters into column headers (like CRM table)

Currently the Pipeline page has standalone filter dropdowns above the table (project, status, target-only, search). The user wants these embedded in the table column headers, like the CRM contacts table does.

**Current filters** in [frontend/src/pages/PipelinePage.tsx](frontend/src/pages/PipelinePage.tsx) lines 427-473:

- Project dropdown (standalone `<select>`)
- Status dropdown (standalone `<select>`)
- Target-only checkbox (standalone)
- Domain/name search (standalone input)

**Fix:** Move these into the table header row as clickable column header dropdowns:

- **Domain** column header gets the search input (inline)
- **Status** column header gets a dropdown filter
- **Project** column header gets a dropdown filter
- **Is Target** column header gets a toggle
- Add a loading spinner on the project dropdown while projects load (fix the `_projectsLoading` unused var)

## 2. Pipeline page: add cost/spending tracking

The user wants to see how much the data costs — Apollo credits, Yandex API, Crona scraping, etc.

The backend already has a spending endpoint: `GET /search/projects/{project_id}/spending` (in [backend/app/api/search.py](backend/app/api/search.py)). The Pipeline stats card already shows Apollo contacts count. Add a "Cost" summary card using the spending data from the search API.

## 3. Chat page: restore project selection

Currently [frontend/src/pages/DataSearchPage.tsx](frontend/src/pages/DataSearchPage.tsx) line 559 has:

```typescript
const [selectedProjectId] = useState<number | null>(null);
```

No setter — project selection is dead. The chat mode (`searchMode === 'chat'`) ignores the global `currentProject` from the app store entirely.

**Fix:** Connect the chat to the global project selector in Layout:

- Import `useAppStore` and read `currentProject`
- When `currentProject` changes, auto-load that project's chat via `loadProjectChat(currentProject.id)`
- Remove the broken `searchMode` toggle (chat/reverse/project tabs) and just use the global project context
- If no project is selected globally, show the "Select a Project" prompt with project buttons (already exists at line 1332)

## Files to modify

- [frontend/src/pages/PipelinePage.tsx](frontend/src/pages/PipelinePage.tsx) — column header filters, loading indicator, cost card
- [frontend/src/pages/DataSearchPage.tsx](frontend/src/pages/DataSearchPage.tsx) — connect chat to global project store
- [frontend/src/api/pipeline.ts](frontend/src/api/pipeline.ts) — add spending API call if not present

