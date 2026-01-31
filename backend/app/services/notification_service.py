"""Notification service for sending alerts to Slack and other channels."""
import os
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Slack Bot Token from environment
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


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
    """Format a ProcessedReply into a Slack message.
    
    Args:
        reply: ProcessedReply model instance
        
    Returns:
        Slack message payload
    """
    category = reply.category or "other"
    emoji = CATEGORY_EMOJIS.get(category, "📧")
    
    # Build lead info
    lead_name = " ".join(filter(None, [reply.lead_first_name, reply.lead_last_name])) or reply.lead_email
    lead_info = lead_name
    if reply.lead_company:
        lead_info = f"{lead_name} ({reply.lead_company})"
    
    # Truncate long content
    reply_preview = (reply.email_body or reply.reply_text or "")[:500]
    if len(reply.email_body or reply.reply_text or "") > 500:
        reply_preview += "..."
    
    draft_preview = (reply.draft_reply or "")[:500]
    if len(reply.draft_reply or "") > 500:
        draft_preview += "..."
    
    # Build Slack blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} New Email Reply - {category.replace('_', ' ').title()}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*From:*\n{lead_info}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Category:*\n{category.replace('_', ' ').title()}"
                }
            ]
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Subject:*\n{reply.email_subject or '(no subject)'}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Campaign:*\n{reply.campaign_name or reply.campaign_id or 'Unknown'}"
                }
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Reply:*\n```{reply_preview}```"
            }
        }
    ]
    
    # Add draft reply if available
    if draft_preview and draft_preview != "(No reply needed for out-of-office)":
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggested Draft:*\n```{draft_preview}```"
                }
            }
        ])
    
    # Add confidence info if available
    if reply.classification_reasoning:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Classification: {reply.category_confidence or 'unknown'} confidence - {reply.classification_reasoning}_"
                }
            ]
        })
    
    return {
        "blocks": blocks,
        "text": f"{emoji} New reply from {lead_info}: {category.replace('_', ' ').title()}"  # Fallback text
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
            "blocks": message.get("blocks", [])
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
                "blocks": message["blocks"]
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
