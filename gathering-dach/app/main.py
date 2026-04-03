"""
DACH→LATAM Gathering Pipeline — FastAPI
========================================

Endpoints:
  POST /start          — Start Phase 1 (Puppeteer scrape DACH companies)
  GET  /status         — Current pipeline state
  GET  /cp1            — CHECKPOINT 1: company list for review
  POST /cp1/approve    — Approve company list (optionally exclude domains)
  POST /phase2/start   — Start Phase 2 (CFO→CEO→COO at approved domains)
  GET  /cp2            — CHECKPOINT 2: contact count for review
  POST /export         — Export contacts to Google Sheets

State machine:
  idle → phase1_running → phase1_done → [CP1] → phase1_approved
       → phase2_running → phase2_done → [CP2] → exported
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app import db
from app.apollo import ApolloClient
from app import pipeline as pipe
from app.scraper import SEARCH_LOCATIONS, LATAM_KEYWORDS, SIZE_RANGES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APOLLO_KEY = os.getenv("APOLLO_API_KEY", "")
PROJECT_ID = int(os.getenv("PROJECT_ID", "9"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("DB initialised")
    yield


app = FastAPI(
    title="DACH→LATAM Gathering Pipeline",
    description="Finds CEO/CFO contacts at DACH companies with LATAM employees for EasyStaff Global",
    version="1.0.0",
    lifespan=lifespan,
)

# In-memory progress tracker (cleared per run)
_progress: dict = {}
_phase1_task: Optional[asyncio.Task] = None
_phase2_task: Optional[asyncio.Task] = None


def _apollo() -> ApolloClient:
    if not APOLLO_KEY:
        raise HTTPException(status_code=500, detail="APOLLO_API_KEY not set")
    return ApolloClient(APOLLO_KEY)


# ── /start ────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    notes: str = "DACH/Nordic companies with LATAM/international team presence — EasyStaff Global"
    project_id: int = PROJECT_ID


@app.post("/start", summary="Start Phase 1: Puppeteer scrape of DACH companies")
async def start_phase1(body: StartRequest, bg: BackgroundTasks):
    """
    Phase 1 is FREE (0 Apollo credits).
    Puppeteer scrapes Apollo Companies UI for DACH/Nordic companies (10–500 employees)
    with keywords indicating LATAM/international team presence.
    Extracts unique company domains for Phase 2.
    """
    run = db.get_latest_run()
    if run and run["state"] in ("phase1_running", "phase2_running"):
        raise HTTPException(400, detail=f"Pipeline already running in state: {run['state']}")

    phase1_filters = {
        "method": "puppeteer_companies_ui",
        "locations": SEARCH_LOCATIONS,
        "keywords": LATAM_KEYWORDS,
        "size_ranges": SIZE_RANGES,
    }
    run_id = db.create_run(body.project_id, phase1_filters, body.notes)
    _progress.clear()
    _progress["run_id"] = run_id
    _progress["state"] = "phase1_running"

    async def progress_cb(data: dict):
        _progress.update(data)

    async def _run():
        try:
            count = await pipe.run_phase1(run_id, progress_cb)
            _progress["state"] = "phase1_done"
            _progress["unique_domains"] = count
        except Exception as e:
            logger.error(f"Phase 1 failed: {e}", exc_info=True)
            db.set_run_state(run_id, "failed")
            _progress["state"] = "failed"
            _progress["error"] = str(e)

    global _phase1_task
    _phase1_task = asyncio.create_task(_run())

    return {
        "run_id": run_id,
        "state": "phase1_running",
        "message": "Phase 1 started (Puppeteer scrape). GET /status to track. GET /cp1 when done.",
        "searching": {
            "locations": SEARCH_LOCATIONS,
            "keywords": LATAM_KEYWORDS,
            "size_ranges": SIZE_RANGES,
            "estimated_duration": "1–3 hours (7 countries × all keywords)",
        },
    }


# ── /status ───────────────────────────────────────────────────────────────────

@app.get("/status", summary="Current pipeline state and progress")
async def status():
    run = db.get_latest_run()
    if not run:
        return {"state": "idle", "message": "No run yet. POST /start to begin."}

    run_id = run["id"]
    companies_count = len(db.get_companies(run_id))
    contacts_count = db.count_contacts(run_id)

    return {
        "run_id": run_id,
        "state": run["state"],
        "companies_found": companies_count,
        "contacts_found": contacts_count,
        "progress": _progress,
        "next_action": _next_action(run["state"]),
    }


def _next_action(state: str) -> str:
    return {
        "idle": "POST /start",
        "phase1_running": "Wait, then GET /status to check",
        "phase1_done": "GET /cp1 to review companies, then POST /cp1/approve",
        "phase1_approved": "POST /phase2/start",
        "phase2_running": "Wait, then GET /status",
        "phase2_done": "GET /cp2 to review, then POST /export",
        "exported": "Done! Check Google Sheet.",
        "failed": "Check /status for error, then POST /start again",
    }.get(state, "Unknown state")


# ── /cp1 — Checkpoint 1 ───────────────────────────────────────────────────────

@app.get("/cp1", summary="CHECKPOINT 1: review company list before Phase 2")
async def checkpoint1():
    """
    Shows all companies found in Phase 1 with their LATAM presence data.
    Review this list before approving to start Phase 2.
    """
    run = db.get_latest_run()
    if not run or run["state"] not in ("phase1_done", "phase1_approved"):
        raise HTTPException(400, detail=f"Phase 1 not complete yet. State: {run['state'] if run else 'idle'}")

    companies = db.get_companies(run["id"])

    import json

    return {
        "run_id": run["id"],
        "state": run["state"],
        "summary": {
            "total_companies": len(companies),
            "top_hq_countries": _top_countries(companies),
            "top_industries": _top_industries(companies),
        },
        "companies": [
            {
                "domain": c["domain"],
                "name": c["name"],
                "hq_country": c["hq_country"],
                "employees": c["employees"],
                "industry": c["industry"],
                "approved": bool(c["approved"]),
            }
            for c in companies[:200]  # first 200 for review
        ],
        "instructions": (
            "Review the list. POST /cp1/approve to proceed "
            "(optionally pass exclude_domains list to remove false positives)."
        ),
    }


def _top_countries(companies: list, n: int = 10) -> dict:
    counts: dict = {}
    for c in companies:
        k = c["hq_country"] or "unknown"
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:n])


def _top_industries(companies: list, n: int = 10) -> dict:
    counts: dict = {}
    for c in companies:
        k = c["industry"] or "unknown"
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:n])


# ── /cp1/approve ──────────────────────────────────────────────────────────────

class CP1ApproveRequest(BaseModel):
    exclude_domains: List[str] = []


@app.post("/cp1/approve", summary="Approve company list — moves to Phase 2 ready")
async def approve_checkpoint1(body: CP1ApproveRequest):
    run = db.get_latest_run()
    if not run or run["state"] != "phase1_done":
        raise HTTPException(400, detail=f"Not in phase1_done state. Current: {run['state'] if run else 'idle'}")

    # Mark exclusions
    excluded = 0
    for domain in body.exclude_domains:
        db.set_company_approval(run["id"], domain.lower().strip(), False)
        excluded += 1

    approved_companies = db.get_companies(run["id"], approved_only=True)
    db.set_run_state(run["id"], "phase1_approved")
    _progress["state"] = "phase1_approved"

    return {
        "run_id": run["id"],
        "state": "phase1_approved",
        "approved_companies": len(approved_companies),
        "excluded": excluded,
        "message": f"Approved {len(approved_companies)} companies. POST /phase2/start to begin CEO/CFO search.",
        "estimated_contacts": f"~{len(approved_companies) * 1}-{len(approved_companies) * 2} CEO/CFO contacts",
    }


# ── /phase2/start ─────────────────────────────────────────────────────────────

@app.post("/phase2/start", summary="Start Phase 2: find CEO/CFO at approved companies")
async def start_phase2():
    """
    Phase 2 is FREE (0 Apollo credits).
    Searches /mixed_people/api_search for CEO/CFO at approved company domains.
    Target: 5000 contacts.
    """
    run = db.get_latest_run()
    if not run or run["state"] != "phase1_approved":
        raise HTTPException(400, detail=f"Phase 1 not approved yet. State: {run['state'] if run else 'idle'}")

    approved = db.get_companies(run["id"], approved_only=True)
    if not approved:
        raise HTTPException(400, detail="No approved companies. Run /cp1/approve first.")

    _progress["state"] = "phase2_running"

    async def progress_cb(data: dict):
        _progress.update(data)

    async def _run():
        try:
            count = await pipe.run_phase2(run["id"], _apollo(), progress_cb)
            _progress["state"] = "phase2_done"
            _progress["total_contacts"] = count
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}", exc_info=True)
            db.set_run_state(run["id"], "failed")
            _progress["state"] = "failed"
            _progress["error"] = str(e)

    global _phase2_task
    _phase2_task = asyncio.create_task(_run())

    return {
        "run_id": run["id"],
        "state": "phase2_running",
        "searching_at": len(approved),
        "target_contacts": pipe.TARGET_CONTACTS,
        "titles": pipe.ALL_EXEC_TITLES,
        "message": "Phase 2 started. GET /status to track. GET /cp2 when done.",
    }


# ── /cp2 — Checkpoint 2 ───────────────────────────────────────────────────────

@app.get("/cp2", summary="CHECKPOINT 2: review contact count before export")
async def checkpoint2():
    run = db.get_latest_run()
    if not run or run["state"] not in ("phase2_done", "exported"):
        raise HTTPException(400, detail=f"Phase 2 not complete yet. State: {run['state'] if run else 'idle'}")

    contacts = db.get_contacts(run["id"])

    # Sample first 10 for review
    sample = [
        {
            "name": f"{c['first_name']} {c['last_name']}".strip(),
            "title": c["title"],
            "company": c["company_domain"],
            "linkedin": c["linkedin_url"],
        }
        for c in contacts[:10]
    ]

    return {
        "run_id": run["id"],
        "state": run["state"],
        "total_contacts": len(contacts),
        "sample": sample,
        "message": "POST /export to write to Google Sheets.",
    }


# ── /export ───────────────────────────────────────────────────────────────────

@app.post("/export", summary="Export contacts to Google Sheets")
async def export():
    run = db.get_latest_run()
    if not run or run["state"] not in ("phase2_done", "exported"):
        raise HTTPException(400, detail=f"Phase 2 not complete. State: {run['state'] if run else 'idle'}")

    contacts = db.get_contacts(run["id"])
    companies = db.get_companies(run["id"], approved_only=True)

    try:
        from app.sheets import export_contacts, export_companies

        contacts_url = export_contacts(run["id"], contacts)
        companies_url = export_companies(run["id"], companies)

        db.set_run_state(run["id"], "exported")
        _progress["state"] = "exported"

        return {
            "state": "exported",
            "contacts_exported": len(contacts),
            "companies_exported": len(companies),
            "sheet_url": contacts_url,
        }
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Export failed: {e}")


# ── /reset ────────────────────────────────────────────────────────────────────

@app.post("/reset", summary="Cancel current run (data preserved in DB)")
async def reset():
    """Cancel a stuck run. Data in SQLite is preserved — won't lose work."""
    global _phase1_task, _phase2_task
    for task in [_phase1_task, _phase2_task]:
        if task and not task.done():
            task.cancel()
    run = db.get_latest_run()
    if run:
        db.set_run_state(run["id"], "cancelled")
    _progress.clear()
    _progress["state"] = "cancelled"
    return {"state": "cancelled"}


@app.get("/health")
async def health():
    return {"ok": True, "apollo_configured": bool(APOLLO_KEY)}
