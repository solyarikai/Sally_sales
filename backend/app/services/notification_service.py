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


async def send_test_notification(channel_id: str = "C09REGUQWTG", webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """Send a test notification to verify Slack integration is working.
    
    Args:
        channel_id: Slack channel ID (default: #c-replies-test)
        webhook_url: Optional fallback webhook URL
        
    Returns:
        Result dict with success status and message
    """
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
