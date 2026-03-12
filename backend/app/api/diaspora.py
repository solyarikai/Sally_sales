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

    for corridor_key in corridors_to_run:
        if corridor_key not in CORRIDORS:
            return {"error": f"Unknown corridor: {corridor_key}. Options: {list(CORRIDORS.keys())}"}

        if corridor_key in _running_pipelines and _running_pipelines[corridor_key].get("status") == "running":
            continue  # Already running

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
        )

    return {
        "status": "started",
        "corridors": corridors_to_run,
        "target_count": request.target_count,
        "check_progress": "GET /api/diaspora/status",
    }


async def _run_pipeline_task(corridor_key: str, project_id: int, target_count: int):
    """Background task for running a single corridor pipeline."""
    import datetime

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
        )
        # Remove contacts from result (too large for status endpoint)
        result_summary = {k: v for k, v in result.items() if k != "contacts"}
        _running_pipelines[corridor_key]["status"] = "completed"
        _running_pipelines[corridor_key]["result"] = result_summary
    except Exception as e:
        logger.error(f"Diaspora pipeline failed for {corridor_key}: {e}", exc_info=True)
        _running_pipelines[corridor_key]["status"] = "failed"
        _running_pipelines[corridor_key]["result"] = {"error": str(e)}


@router.get("/status")
async def get_diaspora_status():
    """Get status of all running/completed diaspora pipelines."""
    return {
        "pipelines": _running_pipelines,
        "available_corridors": {k: v["label"] for k, v in CORRIDORS.items()},
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
