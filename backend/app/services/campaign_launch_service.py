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


def _html_to_telegram(html: str) -> str:
    """Convert SmartLead HTML email body to Telegram-compatible plain text.

    Preserves line breaks and paragraph structure.
    """
    if not html:
        return ""

    from html import unescape

    text = html

    # Convert line breaks: <br>, <br/>, <br />
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # Convert block elements to line breaks
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities (&lt; &gt; &amp; &nbsp; etc.)
    text = unescape(text)

    # Replace &nbsp; that might remain
    text = text.replace('\u00a0', ' ')

    # Normalize multiple newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove trailing spaces on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    return text.strip()


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

            # If template has variables, try to substitute from first lead
            if "{{" in subject_preview or "{{" in body_html:
                try:
                    result = await smartlead_service.get_campaign_leads(campaign_external_id, offset=0, limit=1)
                    leads = result.get("leads", [])
                    if leads:
                        custom_fields = leads[0].get("custom_fields") or {}
                        lead_data = {
                            "first_name": leads[0].get("first_name", ""),
                            "last_name": leads[0].get("last_name", ""),
                            "email": leads[0].get("email", ""),
                            "company_name": leads[0].get("company_name", ""),
                            **custom_fields
                        }
                        # Substitute {{Variable}} with actual values
                        for key, value in lead_data.items():
                            if value:
                                subject_preview = subject_preview.replace("{{" + key + "}}", str(value))
                                body_html = body_html.replace("{{" + key + "}}", str(value))
                except Exception as e:
                    logger.debug(f"Could not substitute template variables: {e}")

            body_preview = _html_to_telegram(body_html)
    except Exception as e:
        logger.warning(f"Failed to fetch sequences for campaign {campaign_external_id}: {e}")

    # 2. Build Telegram message
    project_line = f"\n<b>Project:</b> {_escape_html(project_name)}" if project_name else "\n<b>Project:</b> Not assigned"

    # Escape HTML but preserve newlines for Telegram
    body_text = _escape_html(body_preview)

    smartlead_url = f"https://app.smartlead.ai/app/email-campaign/{campaign_external_id}/overview"

    message = f"""🚀 #check <b>Campaign Launched</b>

<b>Campaign:</b> {_escape_html(campaign_name)}{project_line}

<b>Subject:</b> {_escape_html(subject_preview)}

<b>Email:</b>
{body_text}

<a href="{smartlead_url}">📬 Open in SmartLead</a>"""

    # Telegram message limit is 4096 chars, truncate if needed
    if len(message) > 4000:
        # Recalculate with truncated body
        max_body_len = 4000 - (len(message) - len(body_text)) - 20
        body_text = _escape_html(body_preview[:max_body_len]) + "..."
        message = f"""🚀 #check <b>Campaign Launched</b>

<b>Campaign:</b> {_escape_html(campaign_name)}{project_line}

<b>Subject:</b> {_escape_html(subject_preview)}

<b>Email:</b>
{body_text}

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

    # Get custom_fields from first lead in campaign (for variable substitution)
    sample_custom_fields = {}
    try:
        result = await smartlead_service.get_campaign_leads(campaign_id, offset=0, limit=1)
        leads = result.get("leads", [])
        if leads and len(leads) > 0:
            sample_custom_fields = leads[0].get("custom_fields") or {}
            if sample_custom_fields:
                logger.info(f"Copied {len(sample_custom_fields)} custom fields from sample lead for test leads")
    except Exception as e:
        logger.debug(f"Could not get sample lead custom_fields: {e}")

    leads = []
    for email in emails:
        custom_fields = {**sample_custom_fields, "is_test_lead": "true"}
        leads.append({
            "email": email,
            "first_name": "Test",
            "last_name": "Lead",
            "company_name": "TEST - DELETE",
            "custom_fields": custom_fields
        })

    try:
        result = await smartlead_service.add_leads_to_campaign(
            campaign_id,
            leads
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
