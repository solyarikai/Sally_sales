"""Reply processing service for AI classification and draft generation."""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.reply import ProcessedReply, ReplyAutomation, ReplyCategory
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


# Classification prompt template
CLASSIFICATION_PROMPT = """Classify the following email reply into one of these categories:

Categories:
- interested: The person wants to learn more about the offer
- meeting_request: The person wants to schedule a call or meeting
- not_interested: The person declines or is not interested
- out_of_office: Auto-reply or out of office message
- wrong_person: Not the right contact, suggests someone else
- unsubscribe: Wants to opt out or stop receiving emails
- question: Has specific questions before deciding
- other: Doesn't fit any other category

Email Subject: {subject}

Email Reply:
{body}

Respond with ONLY a JSON object in this format:
{{"category": "<category>", "confidence": "<high|medium|low>", "reasoning": "<brief explanation>"}}
"""

# Draft reply prompt template
DRAFT_REPLY_PROMPT = """Generate a professional follow-up email reply based on this conversation.

Original email reply from prospect:
Subject: {subject}
Body: {body}

Category: {category}
Lead Name: {first_name} {last_name}
Company: {company}

Guidelines:
- Be professional and friendly
- Keep it concise (2-3 paragraphs max)
- If interested/meeting_request: suggest next steps
- If question: answer helpfully
- If not_interested: thank them politely
- If wrong_person: ask for referral
- If unsubscribe: confirm removal
- If out_of_office: no reply needed

Respond with ONLY a JSON object:
{{"subject": "Re: <subject>", "body": "<reply text>", "tone": "<professional|friendly|formal>"}}
"""


async def classify_reply(
    subject: str,
    body: str
) -> Dict[str, Any]:
    """Classify an email reply using OpenAI.
    
    Args:
        subject: Email subject
        body: Email body/reply text
        
    Returns:
        Classification result with category, confidence, reasoning
    """
    if not openai_service.is_connected():
        logger.warning("OpenAI not connected, defaulting to 'other' category")
        return {
            "category": ReplyCategory.OTHER.value,
            "confidence": "low",
            "reasoning": "OpenAI not configured"
        }
    
    try:
        prompt = CLASSIFICATION_PROMPT.format(
            subject=subject or "(no subject)",
            body=body or "(empty)"
        )
        
        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",  # Fast and cheap for classification
            temperature=0.1,
            max_tokens=200
        )
        
        # Parse JSON response
        import json
        result = json.loads(response.strip())
        
        # Validate category
        category = result.get("category", "other").lower()
        valid_categories = [c.value for c in ReplyCategory]
        if category not in valid_categories:
            category = "other"
        
        return {
            "category": category,
            "confidence": result.get("confidence", "medium"),
            "reasoning": result.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return {
            "category": ReplyCategory.OTHER.value,
            "confidence": "low",
            "reasoning": f"Classification failed: {str(e)}"
        }


async def generate_draft_reply(
    subject: str,
    body: str,
    category: str,
    first_name: str = "",
    last_name: str = "",
    company: str = ""
) -> Dict[str, Any]:
    """Generate a draft reply using OpenAI.
    
    Args:
        subject: Original email subject
        body: Original reply body
        category: Classified category
        first_name: Lead's first name
        last_name: Lead's last name
        company: Lead's company
        
    Returns:
        Draft reply with subject and body
    """
    # Skip draft for out of office
    if category == ReplyCategory.OUT_OF_OFFICE.value:
        return {
            "subject": None,
            "body": "(No reply needed for out-of-office)",
            "tone": "none"
        }
    
    if not openai_service.is_connected():
        logger.warning("OpenAI not connected, cannot generate draft")
        return {
            "subject": f"Re: {subject}",
            "body": "(Draft generation unavailable - OpenAI not configured)",
            "tone": "none"
        }
    
    try:
        prompt = DRAFT_REPLY_PROMPT.format(
            subject=subject or "(no subject)",
            body=body or "(empty)",
            category=category,
            first_name=first_name or "",
            last_name=last_name or "",
            company=company or "their company"
        )
        
        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=500
        )
        
        # Parse JSON response
        import json
        result = json.loads(response.strip())
        
        return {
            "subject": result.get("subject", f"Re: {subject}"),
            "body": result.get("body", ""),
            "tone": result.get("tone", "professional")
        }
        
    except Exception as e:
        logger.error(f"Draft generation error: {e}")
        return {
            "subject": f"Re: {subject}",
            "body": f"(Draft generation failed: {str(e)})",
            "tone": "error"
        }


async def process_reply_webhook(
    payload: Dict[str, Any],
    session: AsyncSession
) -> Optional[ProcessedReply]:
    """Process an incoming webhook from Smartlead.
    
    Args:
        payload: Webhook payload
        session: Database session
        
    Returns:
        Created ProcessedReply record
    """
    logger.info(f"Processing webhook payload: {payload.get('event_type')}")
    
    try:
        # Extract data from payload
        campaign_id = payload.get("campaign_id")
        lead_email = payload.get("lead_email")
        subject = payload.get("email_subject", "")
        body = payload.get("email_body") or payload.get("reply_text", "")
        
        # Extract inbox link from nested webhook body (Smartlead format)
        inbox_link = None
        if "body" in payload and isinstance(payload["body"], dict):
            inbox_link = payload["body"].get("ui_master_inbox_link")
        elif "ui_master_inbox_link" in payload:
            inbox_link = payload.get("ui_master_inbox_link")
        
        if not lead_email:
            logger.warning("No lead_email in webhook payload, skipping")
            return None
        
        # Find matching automation (if any)
        automation_id = None
        automation = None
        if campaign_id:
            result = await session.execute(
                select(ReplyAutomation).where(
                    ReplyAutomation.active == True,
                    ReplyAutomation.is_active == True,
                    ReplyAutomation.campaign_ids.contains([campaign_id])
                )
            )
            automation = result.scalar_one_or_none()
            if automation:
                automation_id = automation.id
        
        # Classify the reply
        classification = await classify_reply(subject, body)
        
        # Generate draft reply
        draft = await generate_draft_reply(
            subject=subject,
            body=body,
            category=classification["category"],
            first_name=payload.get("first_name", ""),
            last_name=payload.get("last_name", ""),
            company=payload.get("company_name", "")
        )
        
        # Create processed reply record
        processed_reply = ProcessedReply(
            automation_id=automation_id,
            campaign_id=campaign_id,
            campaign_name=payload.get("campaign_name"),
            lead_email=lead_email,
            lead_first_name=payload.get("first_name"),
            lead_last_name=payload.get("last_name"),
            lead_company=payload.get("company_name"),
            email_subject=subject,
            email_body=body,
            reply_text=payload.get("reply_text"),
            received_at=datetime.utcnow(),
            category=classification["category"],
            category_confidence=classification["confidence"],
            classification_reasoning=classification["reasoning"],
            draft_reply=draft["body"],
            draft_subject=draft["subject"],
            inbox_link=inbox_link,  # Smartlead master inbox link
            raw_webhook_data=payload
        )
        
        session.add(processed_reply)
        await session.flush()
        
        # Send Slack notification
        from app.services.notification_service import send_slack_notification
        
        # Determine channel - use automation config or default test channel
        channel_id = "C09REGUQWTG"  # Default: #c-replies-test
        webhook_url = None
        
        if automation_id and automation:
            channel_id = automation.slack_channel or channel_id
            webhook_url = automation.slack_webhook_url
        
        # Always send notification (even without automation for testing)
        slack_sent = await send_slack_notification(
            channel_id=channel_id,
            reply=processed_reply,
            webhook_url=webhook_url
        )
        if slack_sent:
            processed_reply.sent_to_slack = True
            processed_reply.slack_sent_at = datetime.utcnow()
        
        # Log to Google Sheets if automation has a sheet configured
        if automation and automation.google_sheet_id:
            try:
                from app.services.google_sheets_service import google_sheets_service
                reply_data = {
                    'lead_email': lead_email,
                    'lead_first_name': payload.get("first_name"),
                    'lead_last_name': payload.get("last_name"),
                    'lead_company': payload.get("company_name"),
                    'campaign_id': campaign_id,
                    'campaign_name': payload.get("campaign_name"),
                    'category': classification["category"],
                    'category_confidence': classification["confidence"],
                    'email_subject': subject,
                    'email_body': body,
                    'draft_subject': draft["subject"],
                    'draft_reply': draft["body"],
                    'classification_reasoning': classification["reasoning"],
                    'inbox_link': inbox_link,
                }
                google_sheets_service.append_reply(automation.google_sheet_id, reply_data)
                logger.info(f"Logged reply {processed_reply.id} to Google Sheet {automation.google_sheet_id}")
            except Exception as e:
                logger.error(f"Failed to log reply to Google Sheets: {e}")
        
        await session.commit()
        logger.info(f"Processed reply {processed_reply.id} - category: {classification['category']}")
        
        return processed_reply
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        await session.rollback()
        raise
