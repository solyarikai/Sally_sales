# Frontend Performance Analysis — 2026-03-23

## Before: Single Monolithic Bundle

| File | Raw | Gzipped |
|------|-----|---------|
| `index-DEoHxAer.js` | **2,612 KB** | **695 KB** |
| `index-Doe1E0iP.css` | 347 KB | 57 KB |
| **Total JS** | **2,612 KB** | **695 KB** |

Every page, every library, every icon loaded on first visit — even if user only opens Replies.

---

## After: Route-Based Code Splitting + Vendor Chunking

### Core (loaded on every page)

| Chunk | Raw | Gzipped | Contents |
|-------|-----|---------|----------|
| `index-CRp9FwhU.js` | 320 KB | 104 KB | App shell, Layout, shared utils, Radix UI |
| `vendor-react-*.js` | 48 KB | 17 KB | React, ReactDOM, React Router |
| `index-*.css` | 347 KB | 57 KB | All styles (Tailwind) |
| **Core total** | **715 KB** | **178 KB** | |

### Vendor chunks (loaded on-demand)

| Chunk | Raw | Gzipped | Loaded by |
|-------|-----|---------|-----------|
| `vendor-ag-grid-*.js` | 1,070 KB | 302 KB | ContactsPage, PipelinePage, QueryDashboardPage, AllProspectsPage |
| `vendor-markdown-*.js` | 157 KB | 48 KB | ProjectChatPage, ProjectKnowledgePage (chat) |

### Page chunks (loaded on navigation)

| Page | Raw | Gzipped |
|------|-----|---------|
| ReplyQueue.js | 52 KB | 14 KB |
| TasksPage.js | 10 KB | 3 KB |
| DataSearchPage.js | 55 KB | 14 KB |
| ContactsPage.js | 112 KB | 25 KB |
| KnowledgePage.js | 121 KB | 28 KB |
| DatasetsPage.js | 131 KB | 33 KB |
| SearchResultsPage.js | 77 KB | 16 KB |
| ProjectPage.js | 59 KB | 12 KB |
| KnowledgeBasePage.js | 56 KB | 11 KB |
| PipelinePage.js | 33 KB | 8 KB |
| GodPanelPage.js | 24 KB | 6 KB |
| All others | < 30 KB each | < 8 KB each |

---

## Impact: Replies Page (Operator's Main Workflow)

The operator opens `/tasks/replies` from Telegram on iPhone Safari.

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| JS downloaded | 2,612 KB | ~430 KB | **-84%** |
| JS gzipped | 695 KB | ~138 KB | **-80%** |
| Chunks loaded | 1 | 4 | Core + vendor-react + TasksPage + ReplyQueue |
| ag-grid loaded | Yes (1,070 KB) | **No** | Never loaded on Replies |
| Markdown loaded | Yes (157 KB) | **No** | Never loaded on Replies |

### Estimated Load Time (4G mobile, ~10 Mbps)

| Metric | Before | After |
|--------|--------|-------|
| JS download | ~560ms | ~110ms |
| JS parse/compile | ~800ms | ~200ms |
| **Time to interactive** | **~1.4s** | **~0.3s** |

---

## Changes Made

### 1. Route-Based Code Splitting (`App.tsx`)
- All 23 page components converted to `React.lazy()` + dynamic `import()`
- Each page becomes its own chunk, loaded on first navigation
- `<Suspense>` wrapper with minimal spinner fallback
- Named exports handled via `.then(m => ({ default: m.X }))` adapter

### 2. Vendor Chunk Splitting (`vite.config.ts`)
- `vendor-react`: React + ReactDOM + React Router (always loaded, cached forever)
- `vendor-ag-grid`: ag-grid-community + ag-grid-react (only 4 pages need it)
- `vendor-markdown`: react-markdown + remark-gfm (only chat pages need it)
- Build target: `es2020` (drops legacy polyfills)

### 3. iOS Safari Fix (`ReplyQueue.tsx`, `index.html`)
- Added `viewport-fit=cover` to viewport meta tag
- Added `safe-area-inset-bottom` padding to sticky actions bar
- Send button now clears Safari's bottom toolbar on iPhone

---

## What's NOT Loaded (by page)

| Page | Skipped chunks |
|------|---------------|
| `/tasks/replies` | ag-grid (1,070 KB), markdown (157 KB), all other pages |
| `/contacts` | markdown (157 KB), all non-grid pages |
| `/projects/:id/chat` | ag-grid (1,070 KB), all non-chat pages |
| `/god-panel` | ag-grid (1,070 KB), markdown (157 KB) |

---

## Future Optimizations (Not Done)

1. **ag-grid selective modules**: Replace `AllCommunityModule` with only needed modules (~400 KB savings on grid pages)
2. **CSS code splitting**: Currently all Tailwind CSS loads at once (347 KB) — could split per page
3. **Preload hints**: Add `<link rel="modulepreload">` for likely next navigations
4. **Service worker**: Cache vendor chunks for instant repeat visits
