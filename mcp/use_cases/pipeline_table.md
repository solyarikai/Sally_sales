# Pipeline Table — Requirements

## Current Issues
1. Iteration filter broken — selecting iteration shows "No companies match filters"
2. No iteration column — user can't see which run a company came from
3. No column management (hide/show, resize)
4. Table has no column resize handles

## Requirements

### 1. Iteration Filter Must Work
- "All iterations" shows all project companies
- Selecting iteration #N shows only companies linked to that run via CompanySourceLink
- Backend must filter by gathering_run_id when iteration selected

### 2. Add Iteration Column
- Shows which run(s) a company was gathered in
- One company CAN appear in multiple iterations (re-gathered)
- Display as "#14" or "#14, #15" if multiple

### 3. Column Management
- "Columns" button (like CRM has) to toggle columns on/off
- User can hide: Keywords, City, Scraped, Analysis text
- User can show: Iteration, People, Founded, Revenue
- Preferences saved in localStorage

### 4. Resizable Columns
- Drag column borders to resize
- Keep borderless table style (no AG Grid borders)
- CSS resize or drag handles on column headers

### 5. Table Style
- Borderless (current style is good)
- NOT AG Grid style with thick borders
- Light hover effect on rows (current is good)
