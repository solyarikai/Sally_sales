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


def render_classification_prompt(
    subject: str,
    body: str,
    custom_prompt: Optional[str] = None
) -> str:
    """Render the classification prompt with actual values.
    
    Args:
        subject: Email subject
        body: Email body/reply text
        custom_prompt: Optional custom prompt template
        
    Returns:
        The fully rendered prompt string
    """
    base_prompt = custom_prompt or CLASSIFICATION_PROMPT
    return base_prompt.format(
        subject=subject or "(no subject)",
        body=body or "(empty)"
    )


async def classify_reply(
    subject: str,
    body: str,
    custom_prompt: Optional[str] = None
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
        prompt = render_classification_prompt(subject, body, custom_prompt)
        
        logger.debug(f"[PROMPT DEBUG] Classification prompt:\n{prompt[:500]}...")
        
        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",  # Fast and cheap for classification
            temperature=0.1,
            max_tokens=200
        )
        
        logger.debug(f"[PROMPT DEBUG] Classification response: {response}")
        
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


def render_draft_prompt(
    subject: str,
    body: str,
    category: str,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    custom_prompt: Optional[str] = None
) -> str:
    """Render the draft reply prompt with actual values.
    
    Args:
        subject: Original email subject
        body: Original reply body
        category: Classified category
        first_name: Lead's first name
        last_name: Lead's last name
        company: Lead's company
        custom_prompt: Optional custom prompt template
        
    Returns:
        The fully rendered prompt string
    """
    base_prompt = custom_prompt or DRAFT_REPLY_PROMPT
    return base_prompt.format(
        subject=subject or "(no subject)",
        body=body or "(empty)",
        category=category,
        first_name=first_name or "",
        last_name=last_name or "",
        company=company or "their company"
    )


async def generate_draft_reply(
    subject: str,
    body: str,
    category: str,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    custom_prompt: Optional[str] = None
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
        prompt = render_draft_prompt(
            subject=subject,
            body=body,
            category=category,
            first_name=first_name,
            last_name=last_name,
            company=company,
            custom_prompt=custom_prompt
        )
        
        logger.debug(f"[PROMPT DEBUG] Draft prompt:\n{prompt[:500]}...")
        
        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=500
        )
        
        logger.debug(f"[PROMPT DEBUG] Draft response: {response}")
        
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
    import json
    logger.info("="*60)
    logger.info(f"[PROCESSOR] Starting webhook processing")
    logger.info(f"[PROCESSOR] Payload keys: {list(payload.keys())}")
    logger.info(f"[PROCESSOR] event_type: {payload.get('event_type')}")
    logger.info(f"[PROCESSOR] Full payload: {json.dumps(payload, default=str)[:2000]}")
    
    try:
        # Extract data from payload - handle Smartlead's various field names
        campaign_id = payload.get("campaign_id")
        
        # Lead email: try multiple field names
        lead_email = (
            payload.get("lead_email") or 
            payload.get("sl_lead_email") or 
            payload.get("to_email")  # In Smartlead flat format, to_email is the lead
        )
        
        # Subject
        subject = payload.get("email_subject") or payload.get("subject", "")
        
        # Reply body: prefer plain text (preview_text is cleanest, no HTML)
        body = (
            payload.get("preview_text") or  # Cleanest - just the reply text
            (payload.get("reply_message") or {}).get("text") or  # Full text version
            payload.get("reply_body") or
            (payload.get("body") or {}).get("preview_text") or
            (payload.get("body") or {}).get("email_text") or
            payload.get("email_body") or  # May contain HTML - last resort
            ""
        )
        
        # Strip HTML tags if body still contains them
        if body and "<" in body and ">" in body:
            import re
            body = re.sub(r"<[^>]+>", " ", body)  # Remove HTML tags
            body = re.sub(r"\s+", " ", body).strip()  # Clean whitespace
            # Take just first part before quoted content
            if "On " in body and " wrote:" in body:
                body = body.split("On ")[0].strip()
        
        # Lead name - extract from to_name field
        to_name = payload.get("to_name") or ""
        lead_name_parts = to_name.split() if to_name else []
        first_name = lead_name_parts[0] if len(lead_name_parts) > 0 else payload.get("first_name", "")
        last_name = " ".join(lead_name_parts[1:]) if len(lead_name_parts) > 1 else payload.get("last_name", "")
        logger.info(f"[PROCESSOR] Parsed name: first={first_name}, last={last_name} from to_name={to_name}")
        
        # Campaign name
        campaign_name = payload.get("campaign_name", "")
        
        # Inbox link - construct lead-specific URL if we have leadMap ID
        lead_map_id = (
            payload.get("sl_email_lead_map_id") or 
            payload.get("sl_email_lead_id") or
            (payload.get("body") or {}).get("lead_id")
        )
        if lead_map_id:
            inbox_link = f"https://app.smartlead.ai/app/master-inbox?action=INBOX&leadMap={lead_map_id}"
            logger.info(f"[PROCESSOR] Built inbox link with leadMap={lead_map_id}")
        else:
            inbox_link = payload.get("ui_master_inbox_link") or (payload.get("body") or {}).get("ui_master_inbox_link")
            logger.info(f"[PROCESSOR] Using generic inbox link")
        
        # Conversation history
        lead_correspondence = payload.get("leadCorrespondence", [])
        
        logger.info(f"[PROCESSOR] Extracted: campaign_id={campaign_id}, lead_email={lead_email}")
        logger.info(f"[PROCESSOR] Subject: {subject[:100] if subject else None}")
        logger.info(f"[PROCESSOR] Body: {body[:200] if body else None}")
        logger.info(f"[PROCESSOR] Name: {first_name} {last_name}")
        logger.info(f"[PROCESSOR] Inbox: {inbox_link}")
        
        if not lead_email:
            logger.warning("No lead_email in webhook payload, skipping")
            return None
        
        # Find matching automation (if any)
        automation_id = None
        automation = None
        if campaign_id:
            # Query automations where campaign_ids JSON array contains the campaign_id
            # Use raw SQL for JSON array containment since SQLAlchemy's .contains() 
            # doesn't work well with PostgreSQL JSON arrays
            from sqlalchemy import text, cast
            from sqlalchemy.dialects.postgresql import JSONB
            
            result = await session.execute(
                select(ReplyAutomation).where(
                    ReplyAutomation.active == True,
                    ReplyAutomation.is_active == True,
                    cast(ReplyAutomation.campaign_ids, JSONB).contains([campaign_id])
                ).order_by(ReplyAutomation.created_at.desc()).limit(1)
            )
            automation = result.scalar()
            if automation:
                automation_id = automation.id
                logger.info(f"[PROCESSOR] Found automation: id={automation_id}, name={automation.name}")
                logger.info(f"[PROCESSOR] Automation config: slack_channel={automation.slack_channel}, auto_classify={automation.auto_classify}")
            else:
                logger.info(f"[PROCESSOR] No automation found for campaign_id={campaign_id}")
        
        # Classify the reply
        logger.info(f"[PROCESSOR] Starting classification...")
        custom_classification_prompt = automation.classification_prompt if automation else None
        classification = await classify_reply(subject, body, custom_prompt=custom_classification_prompt)
        logger.info(f"[PROCESSOR] Classification: category={classification['category']}, confidence={classification['confidence']}")
        
        # Generate draft reply
        custom_reply_prompt = automation.reply_prompt if automation else None
        draft = await generate_draft_reply(
            subject=subject,
            body=body,
            category=classification["category"],
            first_name=first_name,
            last_name=last_name,
            company=payload.get("company_name", ""),
            custom_prompt=custom_reply_prompt
        )
        
        # Create processed reply record
        processed_reply = ProcessedReply(
            automation_id=automation_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_email=lead_email,
            lead_first_name=first_name,
            lead_last_name=last_name,
            lead_company=payload.get("company_name", ""),
            email_subject=subject,
            email_body=body,
            reply_text=body,  # Store reply text same as body
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
        
        # Send Telegram notification for high-priority categories
        from app.services.notification_service import notify_reply_needs_attention
        await notify_reply_needs_attention(processed_reply, category)
        
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
        
        # Update automation monitoring stats
        if automation:
            automation.last_run_at = datetime.utcnow()
            automation.total_processed = (automation.total_processed or 0) + 1
        
        await session.commit()
        logger.info(f"Processed reply {processed_reply.id} - category: {classification['category']}")
        
        return processed_reply
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Track error on automation if found
        if automation:
            try:
                automation.total_errors = (automation.total_errors or 0) + 1
                automation.last_error = str(e)[:500]  # Truncate long errors
                automation.last_error_at = datetime.utcnow()
                await session.commit()
            except:
                pass  # Don't fail if we can't log the error
        await session.rollback()
        raise
