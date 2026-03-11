"""Notification service for sending alerts to Slack and other channels."""
import os
import httpx
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Slack Bot Token from environment
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


async def get_slack_token_status() -> Dict[str, Any]:
    """Check if Slack Bot Token is configured and has required permissions.
    
    Returns:
        Dict with configured status, scopes, and any missing permissions
    """
    if not SLACK_BOT_TOKEN:
        return {
            "configured": False,
            "bot_token": False,
            "message": "SLACK_BOT_TOKEN not set in environment",
            "scopes": [],
            "missing_scopes": ["channels:read", "chat:write"],
            "bot_user_id": None,
            "team": None
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://slack.com/api/auth.test",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                }
            )
            
            result = response.json()
            
            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                return {
                    "configured": True,
                    "bot_token": True,
                    "valid": False,
                    "message": f"Slack token invalid: {error}",
                    "scopes": [],
                    "missing_scopes": ["channels:read", "chat:write"],
                    "bot_user_id": None,
                    "team": None
                }
            
            # Get the scopes from token info
            # Note: auth.test doesn't return scopes, we need to check via apps.permissions.info
            # or just try to call the APIs and see if they work
            
            # Check if we can list channels (tests channels:read)
            channels_response = await client.get(
                "https://slack.com/api/conversations.list",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                params={"types": "public_channel", "limit": 1}
            )
            channels_result = channels_response.json()
            
            has_channels_read = channels_result.get("ok", False)
            missing_scopes = []
            
            if not has_channels_read:
                missing_scopes.append("channels:read")
            
            return {
                "configured": True,
                "bot_token": True,
                "valid": True,
                "message": "Slack Bot Token is valid" if not missing_scopes else f"Missing scopes: {', '.join(missing_scopes)}",
                "scopes": [],  # Would need OAuth token info endpoint
                "missing_scopes": missing_scopes,
                "has_channels_read": has_channels_read,
                "has_chat_write": True,  # Assume true if token is valid
                "bot_user_id": result.get("user_id"),
                "team": result.get("team"),
                "team_id": result.get("team_id")
            }
            
    except Exception as e:
        logger.error(f"Error checking Slack token status: {e}")
        return {
            "configured": True,
            "bot_token": True,
            "valid": False,
            "message": f"Error checking token: {str(e)}",
            "scopes": [],
            "missing_scopes": ["channels:read", "chat:write"],
            "bot_user_id": None,
            "team": None
        }


async def list_slack_channels(include_private: bool = False) -> Dict[str, Any]:
    """List Slack channels where the bot is a member (using users.conversations API).
    
    IMPORTANT: Uses users.conversations instead of conversations.list to only return
    channels where the bot can actually send messages.
    
    Args:
        include_private: Whether to include private channels the bot is a member of
        
    Returns:
        Dict with channels list or error message
    """
    if not SLACK_BOT_TOKEN:
        return {
            "success": False,
            "channels": [],
            "error": "SLACK_BOT_TOKEN not configured",
            "action_required": "Set SLACK_BOT_TOKEN in environment variables"
        }
    
    try:
        channels = []
        cursor = None
        types = "public_channel,private_channel" if include_private else "public_channel"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Paginate through all channels using users.conversations
            # This returns ONLY channels where the bot is a member
            while True:
                params = {
                    "types": types,
                    "exclude_archived": "true",
                    "limit": 200
                }
                if cursor:
                    params["cursor"] = cursor
                
                # Use users.conversations instead of conversations.list
                # This ensures we only get channels where the bot can post
                response = await client.get(
                    "https://slack.com/api/users.conversations",
                    headers={
                        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    params=params
                )
                
                result = response.json()
                
                if not result.get("ok"):
                    error = result.get("error", "Unknown error")
                    
                    # Handle specific errors with user-friendly messages
                    if error == "missing_scope":
                        return {
                            "success": False,
                            "channels": [],
                            "error": "Missing required Slack permission: channels:read",
                            "action_required": "Go to api.slack.com/apps → Your App → OAuth & Permissions → Add 'channels:read' scope → Reinstall app"
                        }
                    elif error == "invalid_auth":
                        return {
                            "success": False,
                            "channels": [],
                            "error": "Slack Bot Token is invalid",
                            "action_required": "Check SLACK_BOT_TOKEN in environment variables"
                        }
                    elif error == "token_revoked":
                        return {
                            "success": False,
                            "channels": [],
                            "error": "Slack Bot Token has been revoked",
                            "action_required": "Reinstall the Slack app and update SLACK_BOT_TOKEN"
                        }
                    
                    return {
                        "success": False,
                        "channels": [],
                        "error": f"Slack API error: {error}",
                        "action_required": None
                    }
                
                # Process channels - all returned channels are ones the bot is a member of
                for channel in result.get("channels", []):
                    channels.append({
                        "id": channel["id"],
                        "name": channel["name"],
                        "is_private": channel.get("is_private", False),
                        "is_member": True,  # users.conversations only returns member channels
                        "num_members": channel.get("num_members", 0),
                        "topic": channel.get("topic", {}).get("value", ""),
                        "purpose": channel.get("purpose", {}).get("value", "")
                    })
                
                # Check for more pages
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        
        # Sort by name
        channels.sort(key=lambda x: x["name"])
        
        return {
            "success": True,
            "channels": channels,
            "total": len(channels),
            "error": None,
            "action_required": None,
            "note": "Only showing channels where bot is a member. Invite bot to other channels to see them here."
        }
        
    except Exception as e:
        logger.error(f"Error listing Slack channels: {e}")
        return {
            "success": False,
            "channels": [],
            "error": f"Failed to list channels: {str(e)}",
            "action_required": None
        }


async def create_slack_channel(name: str, is_private: bool = False) -> Dict[str, Any]:
    """Create a new Slack channel.
    
    Args:
        name: Channel name (will be converted to lowercase, no spaces)
        is_private: Whether to create a private channel
        
    Returns:
        Dict with created channel info or error
    """
    if not SLACK_BOT_TOKEN:
        return {
            "success": False,
            "channel": None,
            "error": "SLACK_BOT_TOKEN not configured"
        }
    
    # Normalize channel name
    clean_name = name.lower().replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric characters except hyphens
    clean_name = "".join(c for c in clean_name if c.isalnum() or c == "-")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/conversations.create",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": clean_name,
                    "is_private": is_private
                }
            )
            
            result = response.json()
            
            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                
                if error == "missing_scope":
                    scope_needed = "groups:write" if is_private else "channels:write"
                    return {
                        "success": False,
                        "channel": None,
                        "error": f"Missing required permission: {scope_needed}",
                        "action_required": f"Go to api.slack.com/apps → Your App → OAuth & Permissions → Add '{scope_needed}' scope → Reinstall app"
                    }
                elif error == "name_taken":
                    return {
                        "success": False,
                        "channel": None,
                        "error": f"Channel name '{clean_name}' is already taken"
                    }
                elif error == "invalid_name":
                    return {
                        "success": False,
                        "channel": None,
                        "error": f"Invalid channel name: {clean_name}"
                    }
                
                return {
                    "success": False,
                    "channel": None,
                    "error": f"Failed to create channel: {error}"
                }
            
            channel = result.get("channel", {})
            return {
                "success": True,
                "channel": {
                    "id": channel.get("id"),
                    "name": channel.get("name"),
                    "is_private": channel.get("is_private", False)
                },
                "error": None
            }
            
    except Exception as e:
        logger.error(f"Error creating Slack channel: {e}")
        return {
            "success": False,
            "channel": None,
            "error": f"Failed to create channel: {str(e)}"
        }


# Category emoji mapping
CATEGORY_EMOJIS = {
    "interested": "🟢",
    "meeting_request": "📅",
    "not_interested": "🔴",
    "out_of_office": "🏖️",
    "wrong_person": "🔄",
    "unsubscribe": "🚫",
    "question": "❓",
    "other": "📧"
}


def format_slack_message(reply) -> Dict[str, Any]:
    """Format a ProcessedReply into a CONCISE Slack message.
    
    Per UX guidelines: Keep notifications SHORT and actionable.
    - Line 1: Emoji + Category + Name (clickable link to inbox) + Company
    - Line 2-3: Message preview (max 100 chars)
    - Line 4-5: Draft preview (max 100 chars)
    - Line 6: Buttons with short labels + Open Inbox link
    
    Args:
        reply: ProcessedReply model instance
        
    Returns:
        Slack message payload
    """
    category = reply.category or "other"
    emoji = CATEGORY_EMOJIS.get(category, "📧")
    category_label = category.replace('_', ' ').title()
    
    # Build lead info (single line)
    lead_name = " ".join(filter(None, [reply.lead_first_name, reply.lead_last_name])) or reply.lead_email
    
    # Get inbox link if available
    inbox_link = getattr(reply, 'inbox_link', None)
    
    # Make name clickable if we have inbox link
    if inbox_link:
        lead_name_display = f"<{inbox_link}|{lead_name}>"
    else:
        lead_name_display = lead_name
    
    lead_info = f"{lead_name_display} @ {reply.lead_company}" if reply.lead_company else lead_name_display
    
    # Concise header: Emoji + Category + Name (linked) + Company
    header_text = f"{emoji} *{category_label}* | {lead_info}"
    
    # Truncate message preview (max 100 chars)
    message_text = (reply.email_body or reply.reply_text or "").strip()
    message_preview = message_text[:100] + "..." if len(message_text) > 100 else message_text
    
    # Truncate draft preview (max 100 chars)
    draft_text = (reply.draft_reply or "").strip()
    draft_preview = draft_text[:100] + "..." if len(draft_text) > 100 else draft_text
    
    reply_id = getattr(reply, 'id', 0)
    
    # Build CONCISE Slack blocks
    blocks = [
        # Line 1: Header with emoji, category, name, company
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text
            }
        },
        # Lines 2-3: Quoted message preview
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f">{message_preview}"
            }
        }
    ]
    
    # Lines 4-5: Draft preview (if available and not OOO)
    if draft_preview and draft_preview != "(No reply needed for out-of-office)":
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"💡 _{draft_preview}_"
            }
        })
    
    # Line 6: Action buttons with SHORT labels (OK / Edit / Skip / Open Inbox)
    action_buttons = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "OK", "emoji": True},
            "style": "primary",
            "action_id": "approve_reply",
            "value": str(reply_id)
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Edit", "emoji": True},
            "action_id": "edit_reply",
            "value": str(reply_id)
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Skip", "emoji": True},
            "action_id": "dismiss_reply",
            "value": str(reply_id)
        }
    ]
    
    # Add "Open Inbox" button if we have the link
    if inbox_link:
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "📬 Inbox", "emoji": True},
            "url": inbox_link
        })
    
    blocks.append({
        "type": "actions",
        "block_id": f"reply_actions_{reply_id}",
        "elements": action_buttons
    })
    
    return {
        "blocks": blocks,
        "text": f"{emoji} {category_label} - {lead_info}"  # Fallback text
    }


async def send_slack_notification(
    channel_id: str,
    reply,
    webhook_url: Optional[str] = None
) -> bool:
    """Send a notification to Slack using Bot Token API.
    
    Args:
        channel_id: Slack channel ID (e.g., C09REGUQWTG)
        reply: ProcessedReply model instance or dict with reply data
        webhook_url: Optional fallback webhook URL (deprecated)
        
    Returns:
        True if sent successfully
    """
    if not SLACK_BOT_TOKEN:
        logger.warning("No SLACK_BOT_TOKEN configured in environment")
        # Fallback to webhook if available
        if webhook_url:
            return await send_slack_via_webhook(webhook_url, reply)
        return False
    
    try:
        message = format_slack_message(reply)
        
        payload = {
            "channel": channel_id,
            "text": message.get("text", "New email reply"),
            "blocks": message.get("blocks", []),
            "unfurl_links": False,
            "unfurl_media": False
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            result = response.json()
            
            if result.get("ok"):
                reply_id = getattr(reply, 'id', 'unknown')
                logger.info(f"Slack notification sent for reply {reply_id}")
                return True
            else:
                logger.error(f"Slack API error: {result.get('error')}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False


async def send_slack_via_webhook(webhook_url: str, reply) -> bool:
    """Fallback: Send notification via webhook URL.
    
    Args:
        webhook_url: Slack incoming webhook URL
        reply: ProcessedReply model instance
        
    Returns:
        True if sent successfully
    """
    if not webhook_url:
        return False
    
    try:
        message = format_slack_message(reply)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=message)
            
            if response.status_code == 200:
                reply_id = getattr(reply, 'id', 'unknown')
                logger.info(f"Slack webhook notification sent for reply {reply_id}")
                return True
            else:
                logger.error(f"Slack webhook failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending Slack webhook: {e}")
        return False


async def send_test_notification(channel_id: str = None, webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """Send a test notification to verify Slack integration is working."""
    if not channel_id:
        from app.core.config import settings as _cfg
        channel_id = _cfg.SLACK_DEFAULT_CHANNEL
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Test Notification",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Your Reply Automation is configured correctly! 🎉"
                }
            }
        ],
        "text": "Test notification - Reply Automation is working!"
    }
    
    # Try Bot Token first
    if SLACK_BOT_TOKEN:
        try:
            payload = {
                "channel": channel_id,
                "text": message["text"],
                "blocks": message["blocks"],
                "unfurl_links": False,
                "unfurl_media": False
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                result = response.json()
                
                if result.get("ok"):
                    return {"success": True, "message": "Test notification sent successfully via Bot Token"}
                else:
                    error = result.get("error", "Unknown error")
                    return {"success": False, "message": f"Slack API error: {error}"}
                    
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}
    
    # Fallback to webhook
    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=message)
                
                if response.status_code == 200:
                    return {"success": True, "message": "Test notification sent via webhook"}
                else:
                    return {"success": False, "message": f"Slack returned: {response.status_code}"}
                    
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    return {"success": False, "message": "No SLACK_BOT_TOKEN configured and no webhook URL provided"}


# ============= Telegram Notifications =============

# Telegram configuration — single source of truth is config.py / .env
from app.core.config import settings as _tg_settings
TELEGRAM_BOT_TOKEN = _tg_settings.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = _tg_settings.TELEGRAM_CHAT_ID

import asyncio as _asyncio
_project_cache = {"data": {}, "last_refresh": None}
_PROJECT_CACHE_TTL = 300
_project_cache_lock = _asyncio.Lock()

# God Panel — track which campaigns have been resolution-tracked (one update per process lifetime)
_seen_campaigns: set = set()


async def send_telegram_notification(
    message: str, 
    chat_id: str = None, 
    parse_mode: str = "HTML",
    max_retries: int = 3
) -> bool:
    """Send a notification to Telegram with retry and exponential backoff.
    
    Args:
        message: The message to send (HTML or Markdown)
        chat_id: Target chat ID. Defaults to admin TELEGRAM_CHAT_ID.
        parse_mode: Parse mode for formatting (HTML or Markdown)
        max_retries: Number of retry attempts on failure
        
    Returns:
        True if sent successfully, False otherwise
    """
    import asyncio
    
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        logger.warning("Telegram not configured - missing BOT_TOKEN or CHAT_ID")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data={
                    "chat_id": target_chat,
                    "text": message,
                    "parse_mode": parse_mode
                })
                
                result = response.json()
                
                if result.get("ok"):
                    logger.info(f"Telegram notification sent to {target_chat}")
                    return True
                
                # Handle Telegram rate limiting (429)
                if response.status_code == 429:
                    retry_after = result.get("parameters", {}).get("retry_after", 5)
                    logger.warning(f"Telegram rate limit, waiting {retry_after}s (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    continue
                    
                error_desc = result.get('description', '')
                logger.error(f"Telegram API error: {error_desc} (attempt {attempt + 1})")

                # If HTML parsing failed, retry without parse_mode
                if "can't parse entities" in error_desc.lower() and parse_mode:
                    logger.warning(f"Telegram HTML parse error, retrying without parse_mode")
                    try:
                        fallback_resp = await client.post(url, data={
                            "chat_id": target_chat,
                            "text": message,
                        })
                        if fallback_resp.json().get("ok"):
                            logger.info(f"Telegram notification sent (plaintext fallback) to {target_chat}")
                            return True
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Telegram send error (attempt {attempt + 1}): {e}")

        # Exponential backoff before retry
        if attempt < max_retries - 1:
            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
            await asyncio.sleep(wait)

    logger.error(f"Telegram notification failed after {max_retries} attempts to {target_chat}")
    return False


async def _ensure_cache_fresh():
    """Refresh the project cache if stale."""
    from datetime import datetime

    now = datetime.utcnow()
    if (not _project_cache["last_refresh"] or
        (now - _project_cache["last_refresh"]).total_seconds() > _PROJECT_CACHE_TTL):
        if not _project_cache_lock.locked():
            async with _project_cache_lock:
                try:
                    await _refresh_project_cache()
                except Exception as e:
                    logger.warning(f"Failed to refresh project cache: {e}")


async def _track_campaign_resolution(campaign_name: str, method: str, detail: str, project_id: int = None):
    """Fire-and-forget: update campaign's resolution_method in campaigns table.
    Deduped by _seen_campaigns set — one update per campaign per process lifetime."""
    if campaign_name in _seen_campaigns:
        return
    _seen_campaigns.add(campaign_name)
    try:
        from app.db import async_session_maker
        from app.models.campaign import Campaign as CampaignModel
        from sqlalchemy import select, func
        async with async_session_maker() as session:
            result = await session.execute(
                select(CampaignModel).where(
                    func.lower(CampaignModel.name) == campaign_name.lower()
                ).limit(1)
            )
            campaign = result.scalar()
            if campaign:
                if not campaign.resolution_method or campaign.resolution_method == "unresolved":
                    campaign.resolution_method = method
                    campaign.resolution_detail = detail
                if project_id and not campaign.project_id:
                    campaign.project_id = project_id
                await session.commit()
    except Exception as e:
        logger.debug(f"Campaign resolution tracking failed (non-fatal): {e}")


async def _get_project_for_campaign(campaign_name: str):
    """Find the project that owns a campaign.

    CRITICAL: The returned project's name is used to build the Telegram
    notification "Open in Replies UI" link as ?project=<name>.  If this
    returns None the link has no project param and the UI shows nothing.

    Matching strategy (in order):
      1. Exact match against campaign_filters
      2. Prefix match: campaign name starts with a project's known prefix
         — prefer LONGEST matching prefix to resolve "easystaff" vs "easystaff global"
      3. DB fallback: look up campaign by name in campaigns table → project_id
    """
    await _ensure_cache_fresh()

    campaign_lower = campaign_name.lower()

    # 1. Exact match against campaign_filters
    for project_data in _project_cache["data"].values():
        filters = project_data.get("campaign_filters") or []
        for f in filters:
            if isinstance(f, str) and f.lower() == campaign_lower:
                _asyncio.ensure_future(_track_campaign_resolution(
                    campaign_name, "exact_match",
                    f"Exact match in campaign_filters of project '{project_data.get('name')}'",
                    project_data.get("id"),
                ))
                return project_data

    # 2. Prefix match — pick the LONGEST matching project name
    #    (e.g. "easystaff global" beats "easystaff" for "easystaff -canada_eu")
    best_match = None
    best_len = 0
    for project_data in _project_cache["data"].values():
        project_name = (project_data.get("name") or "").lower()
        if not project_name or len(project_name) < 4:
            continue
        if campaign_lower.startswith(project_name) or campaign_lower.startswith(project_name.replace(" ", "_")):
            if len(project_name) > best_len:
                best_match = project_data
                best_len = len(project_name)
    if best_match:
        _asyncio.ensure_future(_track_campaign_resolution(
            campaign_name, "prefix_match",
            f"Matched prefix '{best_match.get('name')}' (len={best_len})",
            best_match.get("id"),
        ))
        return best_match

    # 3. DB fallback: look up campaigns table for project_id
    try:
        from app.db import async_session_maker
        from app.models.contact import Campaign
        from sqlalchemy import select, func
        async with async_session_maker() as session:
            result = await session.execute(
                select(Campaign.project_id).where(
                    func.lower(Campaign.name) == campaign_lower,
                    Campaign.project_id.isnot(None),
                ).limit(1)
            )
            row = result.first()
            if row and row[0]:
                project_data = _project_cache["data"].get(row[0])
                if project_data:
                    logger.info(f"Campaign '{campaign_name}' resolved to project {row[0]} via DB fallback")
                    _asyncio.ensure_future(_track_campaign_resolution(
                        campaign_name, "db_fallback",
                        f"Found in campaigns table → project {row[0]}",
                        row[0],
                    ))
                    return project_data
    except Exception as e:
        logger.debug(f"DB campaign lookup failed (non-fatal): {e}")

    # Unresolved — track it
    _asyncio.ensure_future(_track_campaign_resolution(
        campaign_name, "unresolved", "No project match found"
    ))
    return None


async def _get_project_by_id(project_id: int):
    """Get project data (with subscribers) by project ID. Uses in-memory cache."""
    await _ensure_cache_fresh()
    return _project_cache["data"].get(project_id)


async def _get_project_by_sender(sender_uuid: str):
    """Find project by sender_profile_uuid in getsales_senders. Returns first match."""
    await _ensure_cache_fresh()
    for project_data in _project_cache["data"].values():
        senders = project_data.get("getsales_senders") or []
        if sender_uuid in senders:
            return project_data
    return None


async def _refresh_project_cache():
    """Refresh the in-memory project-campaign mapping cache, including subscribers."""
    from datetime import datetime
    from app.db import async_session_maker
    from app.models.contact import Project
    from app.models.reply import TelegramSubscription
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Project).where(Project.deleted_at.is_(None))
        )
        projects = result.scalars().all()
        
        # Load all subscriptions in one query
        subs_result = await session.execute(select(TelegramSubscription))
        all_subs = subs_result.scalars().all()
        subs_by_project: dict[int, list[str]] = {}
        for s in all_subs:
            subs_by_project.setdefault(s.project_id, []).append(s.chat_id)
        
        cache = {}
        for p in projects:
            cache[p.id] = {
                "id": p.id,
                "name": p.name,
                "telegram_chat_id": p.telegram_chat_id,
                "telegram_subscribers": subs_by_project.get(p.id, []),
                "campaign_filters": p.campaign_filters or [],
                "getsales_senders": p.getsales_senders or [],
                "telegram_notification_config": p.telegram_notification_config or {},
            }
        
        _project_cache["data"] = cache
        _project_cache["last_refresh"] = datetime.utcnow()
        logger.info(f"Project cache refreshed: {len(cache)} projects")


def _category_indicator(category: str) -> str:
    """Color-coded emoji indicator for Telegram notifications."""
    cat = (category or "").lower()
    if cat in ("interested", "meeting_request", "question"):
        return "🟢"
    if cat in ("not_interested", "unsubscribe", "wrong_person"):
        return "🔴"
    if cat in ("out_of_office",):
        return "🟡"
    return "📧"


# Human-readable status labels for compact mode
_CATEGORY_LABELS = {
    "interested": "Interested",
    "meeting_request": "Meeting Request",
    "question": "Question",
    "not_interested": "Not Interested",
    "unsubscribe": "Unsubscribe",
    "wrong_person": "Wrong Person",
    "out_of_office": "OOO",
    "positive": "Positive",
    "negotiating_meeting": "Meeting",
    "scheduled": "Meeting Booked",
}


def _category_label(category: str) -> str:
    """Human-readable status label."""
    return _CATEGORY_LABELS.get((category or "").lower(), (category or "New Reply").replace("_", " ").title())


async def notify_reply_needs_attention(reply, category: str, campaign_name: str = None) -> bool:
    """Send Telegram notification for new replies with per-project routing.
    
    - Admin (TELEGRAM_CHAT_ID) always receives ALL replies
    - If the campaign belongs to a project with telegram_chat_id, 
      the operator's chat receives it too
    """
    from app.core.config import settings
    from urllib.parse import quote
    raw = reply.raw_webhook_data or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    from_email = raw.get("from_email") or ""
    inbox_line_email = f"\n<b>Inbox:</b> {from_email}" if from_email else ""

    project = None
    if campaign_name:
        try:
            project = await _get_project_for_campaign(campaign_name)
        except Exception as e:
            logger.warning(f"Project routing failed (non-fatal): {e}")

    project_param = ""
    if project:
        project_param = f"&project={quote(project['name'].lower().replace(' ', '-'))}"
    replies_ui_url = f"{settings.FRONTEND_URL}/tasks/replies?lead={quote(reply.lead_email)}{project_param}"

    indicator = _category_indicator(category)
    project_line = f"\n<b>Project:</b> {project['name']}" if project else ""

    body_raw = (reply.email_body or reply.reply_text or "No body").strip()
    body_lines = body_raw.split("\n")
    body_trimmed = "\n".join(l for l in body_lines[:8] if l.strip())
    if len(body_trimmed) > 200:
        body_trimmed = body_trimmed[:200] + "…"
    # Escape HTML entities to prevent Telegram parse errors
    from html import escape as _html_escape
    body_trimmed = _html_escape(body_trimmed)

    # Translation for non-RU/EN messages
    translation_line = ""
    translated = getattr(reply, "translated_body", None)
    detected_lang = getattr(reply, "detected_language", None)
    logger.debug(f"[NOTIFY] Reply {getattr(reply, 'id', '?')}: lang={detected_lang}, translated_body={'set' if translated else 'None'}")
    if not translated:
        # Try to detect and translate on the fly
        try:
            from app.services.reply_processor import detect_and_translate
            lang_info = await detect_and_translate(body_raw[:1000])
            translated = lang_info.get("translation")
            if translated:
                logger.info(f"[NOTIFY] On-the-fly translation for reply {getattr(reply, 'id', '?')}: lang={lang_info.get('language')}")
        except Exception as tr_err:
            logger.warning(f"[NOTIFY] On-the-fly translation failed: {tr_err}")
    if translated:
        tr_trimmed = _html_escape(translated.strip())
        tr_lines = tr_trimmed.split("\n")
        tr_trimmed = "\n".join(l for l in tr_lines[:6] if l.strip())
        if len(tr_trimmed) > 200:
            tr_trimmed = tr_trimmed[:200] + "…"
        translation_line = f"\n\n🌐 <b>Translation:</b>\n<i>{tr_trimmed}</i>"

    # Reply time
    time_line = ""
    received_at = getattr(reply, "received_at", None)
    if received_at:
        try:
            time_line = f"\n<b>Time:</b> {received_at.strftime('%b %d, %Y at %H:%M')} UTC"
        except Exception:
            pass

    _subj = _html_escape(reply.email_subject or 'No subject')
    _company = _html_escape(reply.lead_company or 'Unknown')
    _campaign = _html_escape(campaign_name or 'Unknown')

    # Build full (default) message — always sent to admin
    full_message = f"""{indicator} <b>New Email Reply!</b>

<b>From:</b> {reply.lead_email}
<b>Subject:</b> {_subj}
<b>Company:</b> {_company}
<b>Campaign:</b> {_campaign}{project_line}{inbox_line_email}{time_line}

<b>Message:</b>
<code>{body_trimmed}</code>{translation_line}

<a href="{replies_ui_url}">📋 Open in Replies UI</a>  ·  <a href="{reply.inbox_link or 'https://app.smartlead.ai/app/master-inbox'}">📬 Open in SmartLead</a>"""

    # Build compact message for projects that opted in
    tg_config = project.get("telegram_notification_config", {}) if project else {}
    hide_fields = set(tg_config.get("hide_fields", []))
    compact = tg_config.get("compact", False)

    if compact:
        label = _category_label(category)
        parts = [f"{indicator} <b>{label}</b>"]
        if "email" not in hide_fields:
            parts.append(f"<b>{reply.lead_email}</b>")
        if "company" not in hide_fields:
            parts.append(f"Company: {_company}")
        if "subject" not in hide_fields:
            parts.append(f"Subject: {_subj}")
        if "campaign" not in hide_fields:
            parts.append(f"Campaign: {_campaign}")
        if "project" not in hide_fields and project:
            parts.append(f"Project: {project['name']}")
        if "inbox" not in hide_fields and from_email:
            parts.append(f"Inbox: {from_email}")
        if "time" not in hide_fields and time_line:
            parts.append(f"Time: {received_at.strftime('%b %d, %H:%M') if received_at else ''}")
        # Message body always shown
        parts.append(f"\n<code>{body_trimmed}</code>")
        if translation_line:
            parts.append(translation_line.strip())
        parts.append(f'\n<a href="{replies_ui_url}">📋 Open in Replies UI</a>  ·  <a href="{reply.inbox_link or "https://app.smartlead.ai/app/master-inbox"}">📬 Open in SmartLead</a>')
        compact_message = "\n".join(parts)
    else:
        compact_message = None

    # 1. Always send full message to admin chat
    admin_sent = await send_telegram_notification(full_message.strip(), chat_id=TELEGRAM_CHAT_ID)
    sent_chats = {TELEGRAM_CHAT_ID}

    # 2. Route to project subscribers (compact if configured, full otherwise)
    if project:
        subscriber_msg = compact_message or full_message
        for subscriber_chat in project.get("telegram_subscribers", []):
            if subscriber_chat not in sent_chats:
                await send_telegram_notification(subscriber_msg.strip(), chat_id=subscriber_chat)
                sent_chats.add(subscriber_chat)
        if len(sent_chats) > 1:
            logger.info(f"Reply notification sent to {len(sent_chats)} chats for project '{project.get('name')}'")

    return admin_sent


async def notify_linkedin_reply(
    contact_name: str,
    contact_email: str,
    flow_name: str,
    message_text: str,
    campaign_name: str = None,
    project_id: int = None,
    inbox_link: str = None,
    sender_name: str = None,
    category: str = None,
) -> bool:
    """Send Telegram notification for LinkedIn replies with per-project routing.

    Routing priority:
      1. campaign_name / flow_name → campaign_filters match
      2. project_id direct lookup (fallback for polled replies without flow info)
    """
    from app.core.config import settings
    from urllib.parse import quote
    raw_text = (message_text or "").strip()
    msg_lines = raw_text.split("\n")
    message_preview = "\n".join(l for l in msg_lines[:8] if l.strip())
    if len(message_preview) > 200:
        message_preview = message_preview[:200] + "…"
    from html import escape as _html_escape
    message_preview = _html_escape(message_preview)
    inbox_line = ""
    if inbox_link:
        inbox_line = f'\n<a href="{inbox_link}">💼 Open in GetSales</a>'

    # Find project first so we can include it in the Replies UI link
    project = None
    lookup_name = campaign_name or flow_name
    if lookup_name:
        try:
            project = await _get_project_for_campaign(lookup_name)
        except Exception as e:
            logger.warning(f"LinkedIn campaign routing failed (non-fatal): {e}")

    if not project and project_id:
        try:
            project = await _get_project_by_id(project_id)
            if project:
                logger.info(f"LinkedIn reply routed via project_id={project_id} ({project.get('name')})")
        except Exception as e:
            logger.warning(f"LinkedIn project_id routing failed (non-fatal): {e}")

    is_real_email = contact_email and "@linkedin.placeholder" not in contact_email and not contact_email.startswith("gs_")

    project_param = ""
    if project:
        project_param = f"&project={quote(project['name'].lower().replace(' ', '-'))}"
    # Always include lead email in URL (even placeholder) for direct linking
    if contact_email:
        replies_ui_url = f"{settings.FRONTEND_URL}/tasks/replies?lead={quote(contact_email)}{project_param}"
    elif project_param:
        replies_ui_url = f"{settings.FRONTEND_URL}/tasks/replies?{project_param.lstrip('&')}"
    else:
        replies_ui_url = None
    replies_line = f'\n<a href="{replies_ui_url}">📋 Open in Replies UI</a>' if replies_ui_url else ""

    indicator = _category_indicator(category) if category else "🔗"
    sender_line = f"\n<b>Sender:</b> {sender_name}" if sender_name else ""
    campaign_display = campaign_name or flow_name
    campaign_line = f"\n<b>Campaign:</b> {campaign_display}" if campaign_display else ""
    project_line = f"\n<b>Project:</b> {project['name']}" if project else ""
    email_line = f"\n<b>Email:</b> {contact_email}" if is_real_email else ""

    # Translation for non-RU/EN messages
    translation_line = ""
    if raw_text and len(raw_text) > 10:
        try:
            from app.services.reply_processor import detect_and_translate
            lang_info = await detect_and_translate(raw_text[:1000])
            tr = lang_info.get("translation")
            if tr:
                tr_trimmed = _html_escape(tr.strip())
                tr_lines = tr_trimmed.split("\n")
                tr_trimmed = "\n".join(l for l in tr_lines[:6] if l.strip())
                if len(tr_trimmed) > 200:
                    tr_trimmed = tr_trimmed[:200] + "…"
                translation_line = f"\n\n🌐 <b>Translation:</b>\n<i>{tr_trimmed}</i>"
        except Exception:
            pass

    full_message = f"""{indicator} <b>New LinkedIn Reply!</b>

<b>From:</b> {contact_name}{email_line}{campaign_line}{project_line}{sender_line}

<b>Message:</b>
<code>{message_preview}</code>{translation_line}
{replies_line}{inbox_line}"""

    # Build compact message for projects that opted in
    tg_config = project.get("telegram_notification_config", {}) if project else {}
    hide_fields = set(tg_config.get("hide_fields", []))
    compact = tg_config.get("compact", False)

    if compact:
        label = _category_label(category) if category else "LinkedIn Reply"
        parts = [f"{indicator} <b>{label}</b>"]
        parts.append(f"<b>{contact_name}</b>")
        if "email" not in hide_fields and is_real_email:
            parts.append(contact_email)
        if "campaign" not in hide_fields and campaign_display:
            parts.append(f"Campaign: {campaign_display}")
        if "project" not in hide_fields and project:
            parts.append(f"Project: {project['name']}")
        parts.append(f"\n<code>{message_preview}</code>")
        if translation_line:
            parts.append(translation_line.strip())
        link_parts = []
        if replies_line:
            link_parts.append(replies_line.strip())
        if inbox_line:
            link_parts.append(inbox_line.strip())
        if link_parts:
            parts.append("\n" + "  ·  ".join(link_parts))
        compact_message = "\n".join(parts)
    else:
        compact_message = None

    # 1. Always send full message to admin
    admin_sent = await send_telegram_notification(full_message.strip(), chat_id=TELEGRAM_CHAT_ID)
    sent_chats = {TELEGRAM_CHAT_ID}

    # 2. Route to project subscribers (compact if configured, full otherwise)
    if project:
        subscriber_msg = compact_message or full_message
        for subscriber_chat in project.get("telegram_subscribers", []):
            if subscriber_chat not in sent_chats:
                await send_telegram_notification(subscriber_msg.strip(), chat_id=subscriber_chat)
                sent_chats.add(subscriber_chat)
        if len(sent_chats) > 1:
            logger.info(f"LinkedIn reply sent to {len(sent_chats)} chats for project '{project.get('name')}'")

    return admin_sent
