"""Slack interactivity endpoints for handling button clicks and modals."""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import json
import logging
import os
import httpx

from app.db import get_session
from app.models.reply import ProcessedReply, ReplyAutomation
from app.services.notification_service import list_slack_channels, send_test_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


class TestMessageRequest(BaseModel):
    """Request body for test message endpoint."""
    channel: str  # Channel name or ID


# ============= Channel Management Endpoints =============

@router.get("/channels")
async def get_slack_channels():
    """List Slack channels where the bot is a member.
    
    Uses users.conversations API to return only channels where the bot 
    can actually send messages.
    
    Returns:
        List of channels with id, name, and metadata
    """
    result = await list_slack_channels(include_private=True)
    return result


@router.post("/test-message")
async def send_slack_test_message(request: TestMessageRequest):
    """Send a test message to a Slack channel.
    
    Args:
        request: TestMessageRequest with channel name or ID
        
    Returns:
        Result of the test message send attempt
    """
    channel = request.channel
    
    # If channel name provided without #, add it; if it starts with C, it's an ID
    if channel.startswith("C") or channel.startswith("#"):
        channel_id = channel.lstrip("#")
    else:
        # It's a channel name, need to look up the ID
        channels_result = await list_slack_channels(include_private=True)
        if not channels_result.get("success"):
            return {"ok": False, "error": channels_result.get("error", "Failed to list channels")}
        
        # Find the channel by name
        channel_id = None
        for ch in channels_result.get("channels", []):
            if ch["name"] == channel or ch["name"] == channel.lstrip("#"):
                channel_id = ch["id"]
                break
        
        if not channel_id:
            return {
                "ok": False, 
                "error": f"Channel '{channel}' not found. Make sure the bot is a member of this channel."
            }
    
    # Send test message
    result = await send_test_notification(channel_id=channel_id)
    
    # Normalize response format
    if result.get("success"):
        return {"ok": True, "message": result.get("message", "Test message sent")}
    else:
        return {"ok": False, "error": result.get("message", "Failed to send message")}


@router.post("/interactions")
async def handle_slack_interaction(request: Request):
    """Handle Slack interactive component payloads (button clicks, modals).
    
    Slack sends interactions as form-encoded with a 'payload' JSON string.
    """
    # Parse the form data
    form_data = await request.form()
    payload_str = form_data.get("payload")
    
    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload JSON")
    
    action_type = payload.get("type")
    
    if action_type == "block_actions":
        return await handle_block_actions(payload)
    elif action_type == "view_submission":
        return await handle_view_submission(payload)
    elif action_type == "view_closed":
        # User closed modal, nothing to do
        return JSONResponse(content={"ok": True})
    
    logger.warning(f"Unknown Slack interaction type: {action_type}")
    return JSONResponse(content={"ok": True})


async def handle_block_actions(payload: dict):
    """Handle button clicks from Slack messages."""
    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse(content={"ok": True})
    
    action = actions[0]
    action_id = action.get("action_id")
    reply_id = action.get("value")
    user = payload.get("user", {})
    user_name = user.get("username", user.get("name", "Unknown"))
    
    response_url = payload.get("response_url")
    trigger_id = payload.get("trigger_id")
    
    logger.info(f"Slack action: {action_id} for reply {reply_id} by {user_name}")
    
    if action_id == "approve_reply":
        return await handle_approve(reply_id, user_name, response_url, trigger_id)
    elif action_id == "edit_reply":
        return await handle_edit(reply_id, user_name, trigger_id)
    elif action_id == "dismiss_reply":
        return await handle_dismiss(reply_id, user_name, response_url)
    
    return JSONResponse(content={"ok": True})


async def handle_approve(reply_id: str, user_name: str, response_url: str, trigger_id: str):
    """Handle Approve button click - mark as approved and show success modal."""
    from app.db.database import async_session_maker
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ProcessedReply).where(ProcessedReply.id == int(reply_id))
        )
        reply = result.scalar_one_or_none()
        
        if not reply:
            logger.error(f"Reply {reply_id} not found")
            return JSONResponse(content={"ok": True})
        
        # Update reply status
        reply.approval_status = "approved"
        reply.approved_by = user_name
        reply.approved_at = datetime.utcnow()
        await session.commit()
        
        draft_text = reply.draft_reply or "(No draft available)"
        inbox_link = reply.inbox_link  # Get the Smartlead inbox link
    
    # Update the original message to show approved status
    if response_url:
        await update_message_with_status(response_url, "approved", user_name)
    
    # Open success modal with draft to copy and inbox link
    if trigger_id and SLACK_BOT_TOKEN:
        await open_approval_modal(trigger_id, draft_text, reply_id, inbox_link)
    
    return JSONResponse(content={"ok": True})


async def handle_edit(reply_id: str, user_name: str, trigger_id: str):
    """Handle Edit button click - open modal to edit the draft."""
    from app.db.database import async_session_maker
    
    if not trigger_id or not SLACK_BOT_TOKEN:
        logger.error("Missing trigger_id or SLACK_BOT_TOKEN for edit modal")
        return JSONResponse(content={"ok": True})
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ProcessedReply).where(ProcessedReply.id == int(reply_id))
        )
        reply = result.scalar_one_or_none()
        
        if not reply:
            logger.error(f"Reply {reply_id} not found")
            return JSONResponse(content={"ok": True})
        
        draft_text = reply.draft_reply or ""
        lead_name = f"{reply.lead_first_name or ''} {reply.lead_last_name or ''}".strip() or reply.lead_email
    
    # Open edit modal
    modal = {
        "type": "modal",
        "callback_id": f"edit_reply_modal_{reply_id}",
        "title": {"type": "plain_text", "text": "Edit Draft Reply"},
        "submit": {"type": "plain_text", "text": "Save & Approve"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Editing reply for:* {lead_name}"
                }
            },
            {
                "type": "input",
                "block_id": "draft_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "draft_text",
                    "multiline": True,
                    "initial_value": draft_text
                },
                "label": {"type": "plain_text", "text": "Draft Reply"}
            }
        ],
        "private_metadata": json.dumps({"reply_id": reply_id, "user": user_name})
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/views.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"trigger_id": trigger_id, "view": modal}
        )
        result = response.json()
        if not result.get("ok"):
            logger.error(f"Failed to open edit modal: {result.get('error')}")
    
    return JSONResponse(content={"ok": True})


async def handle_dismiss(reply_id: str, user_name: str, response_url: str):
    """Handle Dismiss button click - mark as dismissed."""
    from app.db.database import async_session_maker
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ProcessedReply).where(ProcessedReply.id == int(reply_id))
        )
        reply = result.scalar_one_or_none()
        
        if not reply:
            logger.error(f"Reply {reply_id} not found")
            return JSONResponse(content={"ok": True})
        
        # Update reply status
        reply.approval_status = "dismissed"
        reply.approved_by = user_name
        reply.approved_at = datetime.utcnow()
        await session.commit()
    
    # Update the original message to show dismissed status
    if response_url:
        await update_message_with_status(response_url, "dismissed", user_name)
    
    return JSONResponse(content={"ok": True})


async def handle_view_submission(payload: dict):
    """Handle modal form submissions."""
    view = payload.get("view", {})
    callback_id = view.get("callback_id", "")
    
    if callback_id.startswith("edit_reply_modal_"):
        return await handle_edit_submission(payload)
    
    return JSONResponse(content={"ok": True})


async def handle_edit_submission(payload: dict):
    """Handle edit modal submission - save the edited draft."""
    from app.db.database import async_session_maker
    
    view = payload.get("view", {})
    values = view.get("state", {}).get("values", {})
    private_metadata = json.loads(view.get("private_metadata", "{}"))
    
    reply_id = private_metadata.get("reply_id")
    user_name = private_metadata.get("user", "Unknown")
    
    # Get the edited draft text
    draft_text = values.get("draft_input", {}).get("draft_text", {}).get("value", "")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ProcessedReply).where(ProcessedReply.id == int(reply_id))
        )
        reply = result.scalar_one_or_none()
        
        if not reply:
            logger.error(f"Reply {reply_id} not found")
            return JSONResponse(content={"ok": True})
        
        # Update reply with edited draft and approve
        reply.draft_reply = draft_text
        reply.approval_status = "approved"
        reply.approved_by = user_name
        reply.approved_at = datetime.utcnow()
        await session.commit()
    
    logger.info(f"Reply {reply_id} edited and approved by {user_name}")
    
    return JSONResponse(content={"ok": True})


async def update_message_with_status(response_url: str, status: str, user_name: str):
    """Update the original Slack message to show the action status."""
    status_emoji = "✅" if status == "approved" else "❌"
    status_text = f"{status_emoji} *{status.title()}* by {user_name}"
    
    update_payload = {
        "replace_original": False,
        "response_type": "in_channel",
        "text": status_text,
        "blocks": [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": status_text
                    }
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(response_url, json=update_payload)
        if response.status_code != 200:
            logger.error(f"Failed to update Slack message: {response.status_code}")


async def open_approval_modal(trigger_id: str, draft_text: str, reply_id: str, inbox_link: str = None):
    """Open a modal showing approval success and the draft to copy."""
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✅ *Reply Approved!*\n\nThe suggested reply has been marked as approved."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Copy this draft to send in Smartlead:*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{draft_text[:2900]}```"  # Slack limit
            }
        }
    ]
    
    # Add "Open Inbox" button if we have the inbox link
    if inbox_link:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📬 Open in Smartlead", "emoji": True},
                    "url": inbox_link,
                    "style": "primary"
                }
            ]
        })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "⚠️ _Auto-send is disabled for safety. Please copy and send manually in Smartlead._"
            }
        ]
    })
    
    modal = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Reply Approved"},
        "close": {"type": "plain_text", "text": "Done"},
        "blocks": blocks
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/views.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"trigger_id": trigger_id, "view": modal}
        )
        result = response.json()
        if not result.get("ok"):
            logger.error(f"Failed to open approval modal: {result.get('error')}")
