# Background Gathering — Architecture Fix Needed

## Problem
`start_gathering()` blocks the API call while the adapter runs. Apollo scraper takes 1-2 hours. The HTTP request times out. Can't run multiple cities in parallel.

## Solution
Make `start_gathering()` async:
1. Create GatheringRun record, commit immediately
2. Return run ID to caller
3. Launch adapter in background task (`asyncio.create_task`)
4. Background task updates run status when done
5. Poll via `GET /runs/{id}` to check completion

## Changes needed in `gathering_service.py`
- Add `background: bool = True` parameter to `start_gathering()`
- Move adapter execution to `_execute_gathering_background()` method
- Background method uses its own `async_session_maker()` session (not the caller's)
- Duplicate check should also match `status="running"` (not just completed)

## Status
- LA gathering is running via pipeline API (blocking call, will complete in ~1-2 hours)
- NYC imported: 2,061 new companies, run #56, all filters stored as arrays
- Next: fix background execution, then launch Miami, Riyadh, London in parallel
