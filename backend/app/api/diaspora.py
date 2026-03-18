"""
Diaspora Contact Gathering API.

Endpoints for finding C-level contacts from target countries
working in employer countries using Clay + GPT name classification.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel

from app.services.diaspora_service import (
    CORRIDORS,
    classify_names_by_origin,
    create_master_sheet,
    run_all_corridors,
    run_diaspora_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diaspora", tags=["diaspora"])

# Track running pipelines
_running_pipelines: dict[str, dict] = {}


class DiasporaGatherRequest(BaseModel):
    corridor: Optional[str] = None  # e.g., "uae-pakistan". None = all corridors
    project_id: int = 9  # easystaff global
    target_count: int = 1000
    mode: str = "full"  # "university" | "full" | "full_tam" (all approaches for max TAM)
    existing_sheet_id: Optional[str] = None  # Append results to existing sheet
    skip_to: Optional[str] = None  # Skip to phase: "surname", "title_split", "industry"


class DiasporaStatusResponse(BaseModel):
    running: dict
    corridors: dict


@router.post("/gather")
async def start_diaspora_gather(
    request: DiasporaGatherRequest,
    background_tasks: BackgroundTasks,
):
    """Start diaspora contact gathering pipeline.

    Runs in background. Check progress via GET /api/diaspora/status.
    """
    corridors_to_run = (
        [request.corridor] if request.corridor else list(CORRIDORS.keys())
    )

    # Validate corridors
    for corridor_key in corridors_to_run:
        if corridor_key not in CORRIDORS:
            return {"error": f"Unknown corridor: {corridor_key}. Options: {list(CORRIDORS.keys())}"}

    # Check if any are already running
    already_running = [k for k in corridors_to_run
                       if k in _running_pipelines and _running_pipelines[k].get("status") == "running"]
    if already_running:
        return {"error": f"Already running: {already_running}", "check_progress": "GET /api/diaspora/status"}

    if len(corridors_to_run) == 1:
        # Single corridor — run directly
        corridor_key = corridors_to_run[0]
        _running_pipelines[corridor_key] = {
            "status": "running",
            "started_at": None,
            "progress": [],
            "result": None,
        }
        background_tasks.add_task(
            _run_pipeline_task,
            corridor_key,
            request.project_id,
            request.target_count,
            request.mode,
            request.existing_sheet_id,
            request.skip_to,
        )
    else:
        # Multiple corridors — run SEQUENTIALLY in one task (they share Puppeteer)
        for k in corridors_to_run:
            _running_pipelines[k] = {
                "status": "queued",
                "started_at": None,
                "progress": [],
                "result": None,
            }
        background_tasks.add_task(
            _run_all_corridors_sequential,
            corridors_to_run,
            request.project_id,
            request.target_count,
            request.mode,
            request.existing_sheet_id,
        )

    return {
        "status": "started",
        "corridors": corridors_to_run,
        "target_count": request.target_count,
        "check_progress": "GET /api/diaspora/status",
    }


async def _run_pipeline_task(
    corridor_key: str, project_id: int, target_count: int,
    mode: str = "full", existing_sheet_id: Optional[str] = None,
    skip_to: Optional[str] = None,
):
    """Background task for running a single corridor pipeline."""
    import datetime

    _running_pipelines[corridor_key]["status"] = "running"
    _running_pipelines[corridor_key]["started_at"] = datetime.datetime.now().isoformat()

    async def on_progress(msg: str):
        _running_pipelines[corridor_key]["progress"].append(msg)
        # Keep only last 50 messages
        if len(_running_pipelines[corridor_key]["progress"]) > 50:
            _running_pipelines[corridor_key]["progress"] = _running_pipelines[corridor_key]["progress"][-50:]

    try:
        result = await run_diaspora_pipeline(
            corridor_key=corridor_key,
            project_id=project_id,
            target_count=target_count,
            on_progress=on_progress,
            mode=mode,
            existing_sheet_id=existing_sheet_id,
            skip_to=skip_to,
        )
        # Remove contacts from result (too large for status endpoint)
        result_summary = {k: v for k, v in result.items() if k != "contacts"}
        _running_pipelines[corridor_key]["status"] = "completed"
        _running_pipelines[corridor_key]["result"] = result_summary
    except Exception as e:
        logger.error(f"Diaspora pipeline failed for {corridor_key}: {e}", exc_info=True)
        _running_pipelines[corridor_key]["status"] = "failed"
        _running_pipelines[corridor_key]["result"] = {"error": str(e)}


async def _run_all_corridors_sequential(
    corridor_keys: list[str], project_id: int, target_count: int,
    mode: str = "full", existing_sheet_id: Optional[str] = None,
):
    """Run multiple corridors one after another (they share Puppeteer)."""
    for corridor_key in corridor_keys:
        await _run_pipeline_task(corridor_key, project_id, target_count, mode, existing_sheet_id)


@router.get("/status")
async def get_diaspora_status():
    """Get status of all running/completed diaspora pipelines."""
    # Return only last 100 progress lines to avoid timeout on large responses
    slim_pipelines = {}
    for k, v in _running_pipelines.items():
        slim = dict(v)
        prog = slim.get("progress", [])
        slim["progress"] = prog[-100:] if len(prog) > 100 else prog
        slim["total_progress_lines"] = len(prog)
        slim_pipelines[k] = slim
    return {
        "pipelines": slim_pipelines,
        "available_corridors": {k: v["label"] for k, v in CORRIDORS.items()},
    }


@router.post("/gather-all")
async def start_diaspora_gather_all(
    background_tasks: BackgroundTasks,
    project_id: int = 9,
    target_count: int = 5000,
    mode: str = "full_tam",
    existing_sheet_id: Optional[str] = None,
):
    """Start ALL corridors in parallel writing to ONE master Google Sheet.

    Creates a single sheet with tabs: UAE-Pakistan, AU-Philippines, Arabic-SouthAfrica, Approaches Log.
    All corridors run concurrently, each writing to its own tab.
    """
    # Check if any are already running
    already_running = [k for k in CORRIDORS
                       if k in _running_pipelines and _running_pipelines[k].get("status") == "running"]
    if already_running:
        return {"error": f"Already running: {already_running}", "check_progress": "GET /api/diaspora/status"}

    # Create or reuse ONE master sheet
    sheet_id = existing_sheet_id
    if not sheet_id:
        try:
            sheet_id = create_master_sheet()
        except Exception as e:
            return {"error": f"Failed to create master sheet: {e}"}

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    # Run corridors SEQUENTIALLY — parallel Puppeteer instances cause
    # health check timeouts and container restarts from CPU/memory pressure
    for corridor_key in CORRIDORS:
        _running_pipelines[corridor_key] = {
            "status": "queued",
            "started_at": None,
            "progress": [],
            "result": None,
        }
    asyncio.create_task(
        _run_all_corridors_sequential(list(CORRIDORS.keys()), project_id, target_count, mode, sheet_id)
    )

    return {
        "status": "started",
        "corridors": list(CORRIDORS.keys()),
        "target_count": target_count,
        "mode": mode,
        "sheet_url": sheet_url,
        "sheet_id": sheet_id,
        "check_progress": "GET /api/diaspora/status",
    }


@router.post("/classify-names")
async def classify_names(
    target_country: str = Query(..., description="Target country: Pakistan, Philippines, South Africa"),
    names: list[dict] = [],
):
    """Classify a list of names by likely country of origin.

    Input: [{"name": "Muhammad Khan", "title": "CEO", "company": "Acme Inc"}, ...]
    Output: same list with added _origin_score and _origin_match fields.
    """
    if not names:
        return {"error": "No names provided"}

    classified = await classify_names_by_origin(names, target_country)
    matched = [c for c in classified if c.get("_origin_match")]

    return {
        "total": len(classified),
        "matched": len(matched),
        "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
        "contacts": classified,
    }
