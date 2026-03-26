"""Replies API — stubs for main app's TasksPage/ReplyQueue compatibility.

The main app's TasksPage calls these endpoints. We return empty results
until SmartLead reply tracking is set up for MCP campaigns.
"""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/replies", tags=["replies"])


@router.get("")
@router.get("/")
async def list_replies(
    page: int = 1,
    page_size: int = 30,
    needs_reply: Optional[bool] = None,
    category: Optional[str] = None,
    project_id: Optional[int] = None,
    campaign: Optional[str] = None,
    search: Optional[str] = None,
    received_since: Optional[str] = None,
    include_all: Optional[bool] = None,
):
    """List replies — returns empty until reply tracking is set up."""
    return {
        "replies": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/counts")
async def reply_counts(
    project_id: Optional[int] = None,
    needs_reply: Optional[bool] = None,
    include_all: Optional[bool] = None,
):
    """Reply counts by category."""
    return {
        "all": 0,
        "meetings": 0,
        "interested": 0,
        "questions": 0,
        "other": 0,
        "not_interested": 0,
        "ooo": 0,
        "wrong_person": 0,
        "unsubscribe": 0,
    }


@router.get("/{reply_id}")
async def get_reply(reply_id: int):
    """Single reply detail."""
    from fastapi import HTTPException
    raise HTTPException(404, "No replies yet — SmartLead reply tracking not set up")


@router.get("/{reply_id}/full-history")
async def reply_history(reply_id: int):
    """Reply conversation history."""
    return {"messages": []}
