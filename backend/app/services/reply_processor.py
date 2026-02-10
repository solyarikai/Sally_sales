"""Reply processing service for AI classification and draft generation."""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.reply import ProcessedReply, ReplyAutomation, ReplyCategory
from app.models.contact import Contact, ContactActivity
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
        custom_prompt: Optional custom instructions (appended to base prompt)
        
    Returns:
        The fully rendered prompt string
    """
    # Always use base prompt for structure and JSON format
    prompt = CLASSIFICATION_PROMPT.format(
        subject=subject or "(no subject)",
        body=body or "(empty)"
    )
    
    # Append custom instructions if provided
    if custom_prompt:
        prompt += "\n\nAdditional instructions: " + custom_prompt

    
    return prompt


async def classify_reply(
    subject: str,
    body: str,
    custom_prompt: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Classify an email reply using OpenAI with retry logic.
    
    Args:
        subject: Email subject
        body: Email body/reply text
        custom_prompt: Optional custom classification prompt
        max_retries: Maximum number of retry attempts (default: 3)
        
    Returns:
        Classification result with category, confidence, reasoning
    """
    import asyncio
    import json
    
    if not openai_service.is_connected():
        logger.warning("OpenAI not connected, defaulting to 'other' category")
        return {
            "category": ReplyCategory.OTHER.value,
            "confidence": "low",
            "reasoning": "OpenAI not configured"
        }
    
    prompt = render_classification_prompt(subject, body, custom_prompt)
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"[PROMPT DEBUG] Classification attempt {attempt + 1}/{max_retries}")
            logger.debug(f"[PROMPT DEBUG] Classification prompt:\n{prompt[:500]}...")
            
            response = await openai_service.complete(
                prompt=prompt,
                model="gpt-4o-mini",  # Fast and cheap for classification
                temperature=0.1,
                max_tokens=200
            )
            
            logger.debug(f"[PROMPT DEBUG] Classification response: {response}")
            
            # Parse JSON response - strip markdown if present
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[-1]
                if "```" in clean_response:
                    clean_response = clean_response.rsplit("```", 1)[0]
            result = json.loads(clean_response.strip())
            
            # Validate category
            category = result.get("category", "other").lower()
            valid_categories = [c.value for c in ReplyCategory]
            if category not in valid_categories:
                logger.warning(f"Invalid category '{category}', defaulting to 'other'")
                category = "other"
            
            if attempt > 0:
                logger.info(f"[PROCESSOR] Classification succeeded after {attempt + 1} attempts")
            
            return {
                "category": category,
                "confidence": result.get("confidence", "medium"),
                "reasoning": result.get("reasoning", "")
            }
            
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {str(e)}"
            logger.warning(f"[PROCESSOR] Classification attempt {attempt + 1} failed - invalid JSON: {e}")
            # JSON errors are worth retrying - model might give valid JSON on retry
            
        except Exception as e:
            last_error = str(e)
            error_lower = last_error.lower()
            logger.warning(f"[PROCESSOR] Classification attempt {attempt + 1} failed: {e}")
            
            # Check if error is retryable (rate limit, timeout, temporary failures)
            retryable_errors = ["rate_limit", "timeout", "connection", "temporary", "overloaded", "503", "429"]
            is_retryable = any(err in error_lower for err in retryable_errors)
            
            if not is_retryable and attempt == 0:
                # Non-retryable errors on first attempt - still try once more
                # Sometimes transient issues look like permanent ones
                logger.info(f"[PROCESSOR] Will retry once despite non-retryable error")
            elif not is_retryable:
                # Non-retryable error after initial retry - give up
                logger.error(f"[PROCESSOR] Non-retryable error, giving up: {e}")
                break
        
        # Exponential backoff before retry
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
            logger.info(f"[PROCESSOR] Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    # All retries exhausted
    logger.error(f"[PROCESSOR] Classification failed after {max_retries} attempts: {last_error}")
    return {
        "category": ReplyCategory.OTHER.value,
        "confidence": "low",
        "reasoning": f"Classification failed after {max_retries} attempts: {last_error}"
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
        custom_prompt: Optional custom instructions (appended to base prompt)
        
    Returns:
        The fully rendered prompt string
    """
    # Always use base prompt for structure and JSON format
    prompt = DRAFT_REPLY_PROMPT.format(
        subject=subject or "(no subject)",
        body=body or "(empty)",
        category=category,
        first_name=first_name or "",
        last_name=last_name or "",
        company=company or "their company"
    )
    
    # Append custom instructions if provided
    if custom_prompt:
        prompt += "\n\nAdditional instructions: " + custom_prompt

    
    return prompt


async def generate_draft_reply(
    subject: str,
    body: str,
    category: str,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    custom_prompt: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Generate a draft reply using OpenAI with retry logic.
    
    Args:
        subject: Original email subject
        body: Original reply body
        category: Classified category
        first_name: Lead's first name
        last_name: Lead's last name
        company: Lead's company
        custom_prompt: Optional custom reply prompt
        max_retries: Maximum number of retry attempts (default: 3)
        
    Returns:
        Draft reply with subject and body
    """
    import asyncio
    import json
    
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
    
    prompt = render_draft_prompt(
        subject=subject,
        body=body,
        category=category,
        first_name=first_name,
        last_name=last_name,
        company=company,
        custom_prompt=custom_prompt
    )
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"[PROMPT DEBUG] Draft generation attempt {attempt + 1}/{max_retries}")
            logger.debug(f"[PROMPT DEBUG] Draft prompt:\n{prompt[:500]}...")
            
            response = await openai_service.complete(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=500
            )
            
            logger.debug(f"[PROMPT DEBUG] Draft response: {response}")
            
            # Parse JSON response - strip markdown if present
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[-1]
                if "```" in clean_response:
                    clean_response = clean_response.rsplit("```", 1)[0]
            result = json.loads(clean_response.strip())
            
            if attempt > 0:
                logger.info(f"[PROCESSOR] Draft generation succeeded after {attempt + 1} attempts")
            
            return {
                "subject": result.get("subject", f"Re: {subject}"),
                "body": result.get("body", ""),
                "tone": result.get("tone", "professional")
            }
            
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {str(e)}"
            logger.warning(f"[PROCESSOR] Draft generation attempt {attempt + 1} failed - invalid JSON: {e}")
            # JSON errors are worth retrying
            
        except Exception as e:
            last_error = str(e)
            error_lower = last_error.lower()
            logger.warning(f"[PROCESSOR] Draft generation attempt {attempt + 1} failed: {e}")
            
            # Check if error is retryable
            retryable_errors = ["rate_limit", "timeout", "connection", "temporary", "overloaded", "503", "429"]
            is_retryable = any(err in error_lower for err in retryable_errors)
            
            if not is_retryable and attempt == 0:
                logger.info(f"[PROCESSOR] Will retry once despite non-retryable error")
            elif not is_retryable:
                logger.error(f"[PROCESSOR] Non-retryable error, giving up: {e}")
                break
        
        # Exponential backoff before retry
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
            logger.info(f"[PROCESSOR] Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    # All retries exhausted
    logger.error(f"[PROCESSOR] Draft generation failed after {max_retries} attempts: {last_error}")
    return {
        "subject": f"Re: {subject}",
        "body": f"(Draft generation failed after {max_retries} attempts: {last_error})",
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
        campaign_id = str(payload.get("campaign_id", "")) or None
        
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

        # Look up project-based prompt (priority: project prompt > automation prompt > default)
        custom_reply_prompt = automation.reply_prompt if automation else None
        if campaign_name:
            try:
                from app.models.contact import Project
                from app.models.reply import ReplyPromptTemplateModel
                from sqlalchemy import String as SAString
                project_result = await session.execute(
                    select(Project).where(
                        and_(
                            Project.campaign_filters.cast(SAString).ilike(f'%{campaign_name}%'),
                            Project.reply_prompt_template_id.isnot(None),
                            Project.deleted_at.is_(None),
                        )
                    ).limit(1)
                )
                project = project_result.scalar()
                if project and project.reply_prompt_template_id:
                    template_result = await session.execute(
                        select(ReplyPromptTemplateModel).where(
                            ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                        )
                    )
                    template = template_result.scalar()
                    if template:
                        custom_reply_prompt = template.prompt_text
                        logger.info(f"[PROCESSOR] Using project prompt from '{project.name}' (template: {template.name})")
            except Exception as proj_err:
                logger.warning(f"[PROCESSOR] Project prompt lookup failed (non-fatal): {proj_err}")

        # Generate draft reply
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
        
        # Create ContactActivity for conversation history
        try:
            # Find or skip contact creation (contact may exist in CRM)
            contact = None
            if lead_email:
                from sqlalchemy import func
                result = await session.execute(
                    select(Contact).where(func.lower(Contact.email) == lead_email.lower())
                )
                contact = result.scalar()
            
            if contact:
                # Append webhook payload to smartlead_raw for debugging
                import json
                from datetime import datetime as dt
                webhook_entry = {
                    "received_at": dt.utcnow().isoformat(),
                    "type": "email_reply",
                    "category": classification["category"],
                    "payload": payload
                }
                if contact.smartlead_raw:
                    try:
                        raw = json.loads(contact.smartlead_raw) if isinstance(contact.smartlead_raw, str) else (dict(contact.smartlead_raw) if contact.smartlead_raw else {})
                        if "webhooks" not in raw:
                            raw["webhooks"] = []
                        raw["webhooks"].append(webhook_entry)
                        contact.smartlead_raw = raw
                    except:
                        contact.smartlead_raw = {"webhooks": [webhook_entry]}
                else:
                    contact.smartlead_raw = {"webhooks": [webhook_entry]}
                
                # Create activity record for this reply (with dedup check)
                snippet = body[:200] if body else None
                activity_at = datetime.utcnow()
                
                # Check for duplicate within same minute
                minute_start = activity_at.replace(second=0, microsecond=0)
                minute_end = activity_at.replace(second=59, microsecond=999999)
                existing = await session.execute(
                    select(ContactActivity).where(
                        ContactActivity.contact_id == contact.id,
                        ContactActivity.source == "smartlead",
                        ContactActivity.activity_type == "email_replied",
                        ContactActivity.activity_at >= minute_start,
                        ContactActivity.activity_at <= minute_end,
                        ContactActivity.snippet == snippet
                    )
                )
                if not existing.scalar():
                    activity = ContactActivity(
                        contact_id=contact.id,
                        company_id=contact.company_id,
                        activity_type="email_replied",
                        channel="email",
                        direction="inbound",
                        source="smartlead",
                        source_id=str(campaign_id) if campaign_id else None,
                        subject=subject,
                        body=body,
                        snippet=snippet,
                        extra_data={
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "category": classification.get("category"),
                            "processed_reply_id": processed_reply.id
                        },
                        activity_at=activity_at
                    )
                    session.add(activity)
                else:
                    logger.info(f"[SMARTLEAD] Skipping duplicate activity for contact {contact.id}")
                
                # Update contact reply status and funnel fields
                contact.has_replied = True
                contact.reply_channel = "email"
                contact.last_reply_at = datetime.utcnow()
                contact.status = "replied"
                contact.funnel_stage = "replied"
                
                # Sync reply category and sentiment
                category = classification.get("category", "other")
                contact.reply_category = category
                
                # Determine sentiment from category
                if category in ("interested", "meeting_request", "question"):
                    contact.reply_sentiment = "warm"
                elif category in ("not_interested", "unsubscribe", "wrong_person"):
                    contact.reply_sentiment = "cold"
                else:
                    contact.reply_sentiment = "neutral"
                
                logger.info(f"[PROCESSOR] Created ContactActivity for email reply from {lead_email}")
            else:
                logger.info(f"[PROCESSOR] Contact not found for {lead_email}, skipping ContactActivity creation")
        except Exception as activity_err:
            logger.warning(f"[PROCESSOR] Failed to create ContactActivity (non-fatal): {activity_err}")
        
        # Send Slack notification
        from app.services.notification_service import send_slack_notification
        
        # Determine channel - use automation config or default test channel
        channel_id = "C09REGUQWTG"  # Default: #c-replies-test
        webhook_url = None
        
        if automation_id and automation:
            channel_id = automation.slack_channel or channel_id
            webhook_url = automation.slack_webhook_url
        
        # Always send notification (even without automation for testing)
        # Wrap in try/catch to prevent Slack failures from breaking webhook processing
        try:
            slack_sent = await send_slack_notification(
                channel_id=channel_id,
                reply=processed_reply,
                webhook_url=webhook_url
            )
            if slack_sent:
                processed_reply.sent_to_slack = True
                processed_reply.slack_sent_at = datetime.utcnow()
        except Exception as slack_error:
            logger.error(f"[PROCESSOR] Slack notification failed (non-fatal): {slack_error}")
            # Continue processing - Slack failure should not break webhook handling
        
        # Send Telegram notification only for actual EMAIL_REPLY events
        # Skip for EMAIL_SENT and other event types (still stored in DB for analytics)
        event_type = payload.get("event_type", "EMAIL_REPLY")
        if event_type == "EMAIL_REPLY":
            try:
                from app.services.notification_service import notify_reply_needs_attention
                await notify_reply_needs_attention(processed_reply, classification["category"])
            except Exception as telegram_error:
                logger.error(f"[PROCESSOR] Telegram notification failed (non-fatal): {telegram_error}")
                # Continue processing - Telegram failure should not break webhook handling
        else:
            logger.info(f"[PROCESSOR] Skipping Telegram notification for event_type: {event_type}")
        
        # Log to Google Sheets if automation has a sheet configured
        if automation and automation.google_sheet_id:
            try:
                from app.services.google_sheets_service import google_sheets_service
                # Extract custom fields for job title
                custom_fields = payload.get("custom_fields", {})
                job_title = custom_fields.get("Job_title", custom_fields.get("job_title", ""))
                
                reply_data = {
                    'id': processed_reply.id,
                    'lead_email': lead_email,
                    'lead_first_name': payload.get("first_name"),
                    'lead_last_name': payload.get("last_name"),
                    'lead_company': payload.get("company_name"),
                    'job_title': job_title,
                    'linkedin_profile': payload.get("linkedin_profile", ""),
                    'campaign_id': campaign_id,
                    'campaign_name': payload.get("campaign_name"),
                    'category': classification["category"],
                    'category_confidence': classification["confidence"],
                    'email_subject': subject,
                    'email_body': body,
                    'draft_reply': draft["body"],
                    'classification_reasoning': classification["reasoning"],
                    'approval_status': 'pending',
                    'inbox_link': inbox_link,
                }
                row_number = google_sheets_service.append_reply_and_get_row(automation.google_sheet_id, reply_data)
                if row_number:
                    processed_reply.google_sheet_row = row_number
                    session.add(processed_reply)
                    await session.commit()
                logger.info(f"Logged reply {processed_reply.id} to Google Sheet {automation.google_sheet_id} at row {row_number}")
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
        automation = locals().get('automation')
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
