"""Campaign launch notification service.

Sends notifications when SmartLead campaigns transition to ACTIVE status:
1. Telegram notification with #check tag and email preview
2. Adds test leads (SDR + admin) to receive the first email
"""
import logging
import re
from typing import Optional, List

from app.core.config import settings
from app.services.smartlead_service import smartlead_service
from app.services.notification_service import send_telegram_notification, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags from text for preview."""
    if not html:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _escape_html(text: str) -> str:
    """Escape HTML entities for Telegram."""
    from html import escape
    return escape(text) if text else ""


async def notify_campaign_launched(
    campaign_id: int,
    campaign_external_id: str,
    campaign_name: str,
    project_id: Optional[int],
    project_name: Optional[str],
    project_telegram_chat: Optional[str],
    sdr_email: Optional[str],
) -> bool:
    """Send notifications when a campaign is launched.

    Args:
        campaign_id: Internal campaign ID
        campaign_external_id: SmartLead campaign ID
        campaign_name: Campaign name
        project_id: Project ID (if assigned)
        project_name: Project name (if assigned)
        project_telegram_chat: Project's Telegram chat ID for operator notification
        sdr_email: SDR email to receive test email

    Returns:
        True if notifications sent successfully
    """
    logger.info(f"Campaign launched: '{campaign_name}' (external_id={campaign_external_id})")

    # 1. Get campaign sequences for email preview
    subject_preview = "—"
    body_preview = ""
    try:
        sequences = await smartlead_service.get_campaign_sequences(campaign_external_id)
        if sequences:
            first_seq = sequences[0] if isinstance(sequences, list) else sequences
            subject_preview = (first_seq.get("subject") or "—")[:100]
            body_html = first_seq.get("email_body") or ""
            body_preview = _strip_html_tags(body_html)[:500]
    except Exception as e:
        logger.warning(f"Failed to fetch sequences for campaign {campaign_external_id}: {e}")

    # 2. Build Telegram message
    project_line = f"\n<b>Project:</b> {_escape_html(project_name)}" if project_name else "\n<b>Project:</b> Not assigned"
    body_text = _escape_html(body_preview[:400])
    if len(body_preview) > 400:
        body_text += "..."

    smartlead_url = f"https://app.smartlead.ai/app/email-campaign/{campaign_external_id}/overview"

    message = f"""🚀 #check <b>Campaign Launched</b>

<b>Campaign:</b> {_escape_html(campaign_name)}{project_line}

<b>Subject:</b> {_escape_html(subject_preview)}

<b>Body preview:</b>
<code>{body_text}</code>

<a href="{smartlead_url}">📬 Open in SmartLead</a>"""

    # 3. Send to admin
    admin_sent = await send_telegram_notification(message, chat_id=TELEGRAM_CHAT_ID)

    # 4. Send to project operator (if different from admin)
    if project_telegram_chat and project_telegram_chat != TELEGRAM_CHAT_ID:
        await send_telegram_notification(message, chat_id=project_telegram_chat)
        logger.info(f"Sent campaign launch notification to project chat {project_telegram_chat}")

    # 5. Add test leads to campaign
    test_emails = [settings.ADMIN_TEST_EMAIL]
    if sdr_email and sdr_email.lower() != settings.ADMIN_TEST_EMAIL.lower():
        test_emails.append(sdr_email)

    await add_test_leads_to_campaign(campaign_external_id, test_emails)

    return admin_sent


async def add_test_leads_to_campaign(campaign_id: str, emails: List[str]) -> bool:
    """Add test leads to a campaign so SmartLead sends them the first email.

    Args:
        campaign_id: SmartLead campaign ID
        emails: List of email addresses to add as test leads

    Returns:
        True if leads were added successfully
    """
    if not emails:
        return True

    leads = []
    for email in emails:
        leads.append({
            "email": email,
            "first_name": "Test",
            "last_name": "Lead",
            "company_name": "TEST - DELETE",
            "custom_fields": {"is_test_lead": "true"}
        })

    try:
        result = await smartlead_service.add_leads_to_campaign(
            campaign_id,
            leads,
            settings={"ignore_global_block_list": True}
        )
        if result.get("success"):
            logger.info(f"Added {len(emails)} test leads to campaign {campaign_id}: {emails}")
            return True
        else:
            logger.warning(f"Failed to add test leads to campaign {campaign_id}: {result.get('error')}")
            return False
    except Exception as e:
        # Log but don't fail — notification is more important
        logger.warning(f"Failed to add test leads to campaign {campaign_id}: {e}")
        return False
