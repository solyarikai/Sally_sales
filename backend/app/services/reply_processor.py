"""Reply processing service for AI classification and draft generation."""
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.reply import ProcessedReply, ReplyAutomation, ReplyCategory, ThreadMessage
from app.models.contact import Contact, ContactActivity
from app.services.openai_service import openai_service
from app.services.smartlead_service import smartlead_request

logger = logging.getLogger(__name__)


def _format_knowledge_context(knowledge_entries, category: str = None) -> str:
    """Format knowledge entries into a prompt-friendly context string.

    Files are separated with a CRITICAL instruction block so the AI reliably
    includes document links when the prospect requests materials.
    Golden examples are included with STRICT instructions to follow them exactly.
    ALL examples are included regardless of category — the operator uses the same
    style/structure across categories.
    """
    regular = []
    files = []
    examples = []
    for entry in knowledge_entries:
        if entry.category == "files":
            label = entry.title or entry.key
            files.append(f"  {label}: {entry.value}")
        elif entry.category == "examples":
            examples.append(entry)
        else:
            regular.append(f"- [{entry.category}] {entry.key}: {entry.value}")

    parts = ["\n\nProject Knowledge Base:"]
    if regular:
        parts.append("\n".join(regular))
    if files:
        parts.append(
            "\n\n=== IMPORTANT: FILE ATTACHMENT RULES ===\n"
            "Project files available to send:\n"
            + "\n".join(files)
            + "\n\nRULES (follow strictly):\n"
            "1. If the prospect asks for a presentation, materials, pricing, "
            "conditions, documents, or any info — mention that you are attaching "
            "the relevant file. Example: \"Прикрепляю презентацию\" or "
            "\"Sending the presentation along with this email\".\n"
            "2. Do NOT paste file URLs or links into the reply text. "
            "The operator will attach files separately. Just mention the attachment.\n"
            "3. If the prospect did NOT ask for any files or materials, "
            "do NOT mention any attachments.\n"
            "=== END FILE RULES ==="
        )
    if examples:
        example_parts = []
        for ex in examples[:10]:  # Up to 10 examples for rich context
            example_parts.append(f"--- Example ({ex.title or ex.key}) ---\n{ex.value}\n--- End example ---")
        parts.append(
            "\n\n=== REFERENCE REPLIES FROM OPERATOR (YOUR #1 PRIORITY) ===\n"
            "These are REAL replies the operator wrote. They define the EXACT style you must follow.\n"
            "Your draft MUST replicate:\n"
            "- The SAME structure (greeting, then detailed body, then call-to-action, then signature)\n"
            "- The SAME level of detail (full pricing breakdowns, bullet point lists, specific numbers)\n"
            "- The SAME tone, language style, and formatting\n"
            "- The SAME length — if the example is long and detailed, yours must be too\n"
            "Adapt names/company for the current lead, but COPY the structure and detail level.\n\n"
            + "\n\n".join(example_parts)
            + "\n=== END REFERENCE REPLIES ==="
        )
    return "\n".join(parts)


def _strip_html_to_text(html_text: str) -> str:
    """Strip HTML tags, preserving line breaks and list markers."""
    import re as _re, html as _html
    if not html_text:
        return ""
    text = _re.sub(r'<br\s*/?>', '\n', html_text)
    text = _re.sub(r'</div>', '\n', text)
    text = _re.sub(r'</li>', '\n', text)
    text = _re.sub(r'<li[^>]*>', '• ', text)
    text = _re.sub(r'<[^>]+>', '', text)
    text = _html.unescape(text)
    text = _re.sub(r'\n{3,}', '\n\n', text)
    text = _re.sub(r'  +', ' ', text)
    return text.strip()


async def _load_reference_examples(session, project_id: int, category: str = None, limit: int = 20) -> str:
    """Load operator's actual sent replies as few-shot reference examples.

    Primary source: thread_messages (outbound, >300 chars) — full-text operator replies
    from SmartLead conversations. These are the REAL examples with no truncation.
    Matched to project via ProcessedReply campaign → project campaign_filters.

    Strategy: fetch 100 most recent outbound messages, prioritize by:
    1. Same category as current lead (exact match)
    2. Qualified categories (interested, meeting_request, question) — these have the
       best detailed replies with pricing and CTAs
    3. Longer replies first (more detail = better reference)
    4. Skip short follow-ups and scheduling messages (<400 chars clean text)
    """
    try:
        from app.models.reply import ProcessedReply as PRModel, ThreadMessage
        from app.models.contact import Project

        # Get project to determine campaign filters
        proj_result = await session.execute(
            select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            return ""

        # Build campaign filter conditions (same as _build_project_campaign_filter)
        from sqlalchemy import or_, func as sa_func
        filter_parts = []
        campaign_names = [c.lower() for c in (project.campaign_filters or []) if isinstance(c, str)]
        if campaign_names:
            filter_parts.append(sa_func.lower(PRModel.campaign_name).in_(campaign_names))
        pname = (project.name or "").lower()
        if pname and len(pname) > 2:
            filter_parts.append(sa_func.lower(PRModel.campaign_name).like(f"{pname}%"))

        if not filter_parts:
            return ""

        # Qualified categories — these produce the best reference replies
        QUALIFIED_CATS = {"interested", "meeting_request", "question"}

        # Fetch a large pool, then select the best examples
        query = (
            select(
                ThreadMessage.body,
                PRModel.email_body,
                PRModel.lead_first_name,
                PRModel.lead_company,
                PRModel.category,
                PRModel.channel,
            )
            .join(PRModel, ThreadMessage.reply_id == PRModel.id)
            .where(
                ThreadMessage.direction == "outbound",
                sa_func.length(ThreadMessage.body) > 300,
                or_(*filter_parts),
                # Only load qualified categories — skip not_interested, unsubscribe, etc.
                PRModel.category.in_(list(QUALIFIED_CATS)),
            )
            .order_by(ThreadMessage.id.desc())
            .limit(100)  # Large pool for dedup + selection
        )
        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return ""

        # Deduplicate by content similarity (skip near-identical replies)
        seen_prefixes = set()
        unique_rows = []
        for r in rows:
            clean_body = _strip_html_to_text(r.body)
            # Skip short follow-ups — only keep substantive replies
            if len(clean_body) < 400:
                continue
            prefix = clean_body[:150].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            unique_rows.append((r, clean_body))

        if not unique_rows:
            return ""

        # Priority sort:
        # 1. Same category, longest first (most detailed)
        # 2. Other qualified categories, longest first
        same_cat = sorted(
            [(r, b) for r, b in unique_rows if r.category == category],
            key=lambda x: len(x[1]), reverse=True
        )
        other_cat = sorted(
            [(r, b) for r, b in unique_rows if r.category != category],
            key=lambda x: len(x[1]), reverse=True
        )
        sorted_rows = (same_cat + other_cat)[:limit]

        parts = []
        for r, clean_body in sorted_rows:
            lead_msg = _strip_html_to_text(r.email_body or "")[:400]
            parts.append(
                f"[{r.category or 'unknown'}] Lead ({r.lead_first_name or 'lead'}, "
                f"{r.lead_company or ''}):\n"
                f"\"{lead_msg}\"\n"
                f"Operator replied:\n"
                f"\"{clean_body}\""
            )

        logger.info(
            f"[PROCESSOR] Loaded {len(parts)} reference examples from thread_messages "
            f"for project {project_id} (category={category}, "
            f"same_cat={len(same_cat)}, other={len(other_cat)})"
        )

        return (
            "\n\n=== OPERATOR'S REAL REPLIES (YOUR PRIMARY REFERENCE — COPY THIS STYLE) ===\n"
            "These are ACTUAL replies the operator sent to real leads. "
            "Your draft MUST replicate this EXACT style:\n"
            "- Same greeting pattern\n"
            "- Same level of detail (if they write full pricing with bullet points, you do too)\n"
            "- Same structure (greeting → context → details → CTA → signature)\n"
            "- Same tone and language\n"
            "- Same length — NEVER shorten or summarize what the operator writes in detail\n"
            "- If operator includes specific numbers/rates, you MUST include the SAME numbers\n"
            "Pick the CLOSEST matching example and adapt it for the current lead.\n\n"
            + "\n\n---\n\n".join(parts)
            + "\n=== END OPERATOR'S REAL REPLIES ==="
        )
    except Exception as e:
        logger.warning(f"[PROCESSOR] Reference examples loading failed (non-fatal): {e}")
        return ""


def _parse_source_timestamp(payload: dict) -> Optional[datetime]:
    """Extract the ORIGINAL reply timestamp from the source platform data.
    
    Tries multiple fields in priority order. Returns None if no valid timestamp found.
    """
    candidates = [
        payload.get("time_replied"),
        payload.get("event_timestamp"),
        payload.get("reply_time"),
        payload.get("time"),
    ]
    for raw in candidates:
        if not raw:
            continue
        ts = str(raw).strip()
        if not ts:
            continue
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            if parsed.year >= 2020:
                return parsed
        except (ValueError, TypeError):
            pass
        try:
            from dateutil.parser import parse as parse_dt
            parsed = parse_dt(ts).replace(tzinfo=None)
            if parsed.year >= 2020:
                return parsed
        except Exception:
            pass
    return None


# Regex for placeholder brackets GPT sometimes generates despite instructions.
# Matches patterns like [Your Name], [Ваше имя], [Tu Nombre], [Your Contact Information], etc.
_PLACEHOLDER_RE = re.compile(
    r"\[(?:Your |Ваш[аеи]? |Tu |Su |Ihr )"  # common prefixes
    r"[^\[\]]{2,40}\]",                        # content inside brackets (2-40 chars)
    re.IGNORECASE,
)


def _strip_placeholder_brackets(text: str) -> str:
    """Remove GPT-generated placeholder brackets like [Your Name], [Ваше имя] etc."""
    if not text:
        return text
    cleaned = _PLACEHOLDER_RE.sub("", text)
    # Collapse multiple blank lines that may result from removal
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


async def detect_and_translate(text: str) -> dict:
    """Detect language and translate to English if not en/ru.

    Returns {"language": "xx", "translation": "..." or None}.
    Uses a single GPT-4o-mini call for both detection and translation.
    """
    if not text or len(text.strip()) < 10:
        return {"language": None, "translation": None}
    try:
        prompt = (
            "Analyze this text. Return JSON: {\"language\": \"<ISO 639-1 code>\", \"translation\": <English translation string or null>}\n"
            "Rules:\n"
            "- If language is English (en) or Russian (ru), set translation to null\n"
            "- Otherwise, provide an accurate English translation preserving formatting\n"
            "- Keep line breaks, bullet points, and structure intact\n\n"
            f"Text:\n{text[:3000]}"
        )
        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        import json
        parsed = json.loads(response)
        return {
            "language": parsed.get("language"),
            "translation": parsed.get("translation"),
        }
    except Exception as e:
        logger.warning(f"[TRANSLATE] Language detection failed (non-fatal): {e}")
        return {"language": None, "translation": None}


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
Lead Company: {company}

You are replying as: {sender_name}{sender_position_line}{sender_company_line}

CRITICAL RULES:
1. If REFERENCE REPLIES or GOLDEN EXAMPLES are provided below, they are your PRIMARY guide.
   Match their structure, detail level, tone, and length EXACTLY. Do NOT shorten or simplify.
   If the reference has full pricing breakdowns with bullet points, YOUR reply must too.
2. If no examples are provided, use these defaults:
   - interested/meeting_request: detailed response with next steps
   - question: answer helpfully with specifics
   - not_interested: thank them politely (keep short)
   - wrong_person: ask for referral (keep short)
   - unsubscribe: confirm removal (keep short)
3. Sign off with the sender name above — NEVER use placeholder brackets like [Your Name] etc.
4. If sender name is unknown, omit the sign-off entirely.

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
                max_tokens=200,
                response_format={"type": "json_object"},
            )

            logger.debug(f"[PROMPT DEBUG] Classification response: {response}")

            # Parse JSON response - strip markdown if present
            clean_response = response.strip()
            if not clean_response:
                raise ValueError("OpenAI returned empty response for classification")
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
            
            # Check if error is retryable (rate limit, timeout, temporary failures, empty response)
            retryable_errors = ["rate_limit", "timeout", "connection", "temporary", "overloaded", "503", "429", "empty response"]
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
    custom_prompt: Optional[str] = None,
    sender_name: Optional[str] = None,
    sender_position: Optional[str] = None,
    sender_company: Optional[str] = None,
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
        sender_name: Name of the person sending the reply (from Project)
        sender_position: Position/title of the sender (from Project)
        sender_company: Company of the sender (from Project)
        
    Returns:
        The fully rendered prompt string
    """
    # Build optional sender context lines
    sender_position_line = f", {sender_position}" if sender_position else ""
    sender_company_line = f" at {sender_company}" if sender_company else ""

    format_vars = dict(
        subject=subject or "(no subject)",
        body=body or "(empty)",
        category=category,
        first_name=first_name or "",
        last_name=last_name or "",
        company=company or "their company",
        sender_name=sender_name or "the operator",
        sender_position_line=sender_position_line,
        sender_company_line=sender_company_line,
    )

    # If custom_prompt is a full template (contains {subject} placeholder),
    # use it as the main prompt with all format vars injected.
    # Otherwise, append it as additional instructions to the base prompt.
    if custom_prompt and "{subject}" in custom_prompt:
        try:
            prompt = custom_prompt.format(**format_vars)
        except (KeyError, IndexError):
            # Fallback: if template has unknown placeholders, use base + append
            prompt = DRAFT_REPLY_PROMPT.format(**format_vars)
            prompt += "\n\nAdditional instructions: " + custom_prompt
    else:
        prompt = DRAFT_REPLY_PROMPT.format(**format_vars)
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
    max_retries: int = 3,
    sender_name: Optional[str] = None,
    sender_position: Optional[str] = None,
    sender_company: Optional[str] = None,
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
        sender_name: Name of the person sending the reply (from Project)
        sender_position: Position/title of the sender (from Project)
        sender_company: Company of the sender (from Project)
        
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
        custom_prompt=custom_prompt,
        sender_name=sender_name,
        sender_position=sender_position,
        sender_company=sender_company,
    )
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"[PROMPT DEBUG] Draft generation attempt {attempt + 1}/{max_retries}")
            logger.debug(f"[PROMPT DEBUG] Draft prompt:\n{prompt[:500]}...")
            
            response = await openai_service.complete(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.4,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            logger.debug(f"[PROMPT DEBUG] Draft response: {response}")

            # Parse JSON response - strip markdown if present
            clean_response = response.strip()
            if not clean_response:
                raise ValueError("OpenAI returned empty response for draft generation")
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[-1]
                if "```" in clean_response:
                    clean_response = clean_response.rsplit("```", 1)[0]
            result = json.loads(clean_response.strip())
            
            if attempt > 0:
                logger.info(f"[PROCESSOR] Draft generation succeeded after {attempt + 1} attempts")
            
            draft_body = result.get("body", "")
            # Strip GPT placeholder brackets like [Your Name], [Ваше имя], etc.
            draft_body = _strip_placeholder_brackets(draft_body)

            return {
                "subject": result.get("subject", f"Re: {subject}"),
                "body": draft_body,
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
            
            # Check if error is retryable (rate limit, timeout, temporary failures, empty response)
            retryable_errors = ["rate_limit", "timeout", "connection", "temporary", "overloaded", "503", "429", "empty response"]
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


async def _fetch_and_cache_thread(
    reply: ProcessedReply,
    session: AsyncSession,
) -> bool:
    """Fetch Smartlead message-history and store as ThreadMessage rows.

    Non-fatal: any failure is logged as a warning and returns False.
    On success sets reply.thread_fetched_at and returns True.
    Also detects replied_externally (last message outbound).
    """
    from app.core.config import settings as _settings
    from sqlalchemy import delete as sa_delete

    try:
        api_key = _settings.SMARTLEAD_API_KEY or ""
        if not api_key or not reply.campaign_id:
            logger.info(f"[THREAD_CACHE] Skipping: api_key={'set' if api_key else 'EMPTY'}, campaign_id={reply.campaign_id}")
            return False

        # --- Resolve lead_id (same chain as sync_conversation_histories) ---
        lead_id = reply.smartlead_lead_id

        if not lead_id:
            # Try contact.smartlead_id
            if reply.lead_email:
                from sqlalchemy import func
                row = (await session.execute(
                    select(Contact.smartlead_id).where(
                        func.lower(Contact.email) == reply.lead_email.lower(),
                        Contact.deleted_at.is_(None),
                    )
                )).first()
                if row and row[0]:
                    lead_id = str(row[0])

        if not lead_id and reply.raw_webhook_data and isinstance(reply.raw_webhook_data, dict):
            lead_id = str(
                reply.raw_webhook_data.get("sl_email_lead_id")
                or reply.raw_webhook_data.get("sl_lead_id")
                or reply.raw_webhook_data.get("lead_id")
                or ""
            ).strip() or None

        if not lead_id:
            logger.info(f"[THREAD_CACHE] No lead_id for reply {reply.id}, skipping thread fetch")
            return False

        # Persist lead_id for next time
        if not reply.smartlead_lead_id:
            reply.smartlead_lead_id = lead_id

        # --- Fetch message-history via smartlead_request (429-tolerant) ---
        resp = await smartlead_request(
            "GET",
            f"https://server.smartlead.ai/api/v1/campaigns/{reply.campaign_id}/leads/{lead_id}/message-history",
            params={"api_key": api_key},
            timeout=15.0,
        )

        if resp.status_code != 200:
            logger.warning(f"[THREAD_CACHE] Smartlead returned {resp.status_code} for reply {reply.id}")
            return False

        from app.services.smartlead_service import parse_history_response
        history_entries = parse_history_response(resp.json())
        if not history_entries:
            logger.info(f"[THREAD_CACHE] Empty history for reply {reply.id}")
            return False

        # --- Replace cached messages (idempotent) ---
        await session.execute(
            sa_delete(ThreadMessage).where(ThreadMessage.reply_id == reply.id)
        )

        last_direction = None
        for idx, entry in enumerate(history_entries):
            msg_type = (entry.get("type") or "").upper()
            direction = "outbound" if msg_type == "SENT" else "inbound"
            last_direction = direction
            body = entry.get("email_body") or entry.get("email_text") or entry.get("message") or ""
            subject = entry.get("email_subject") or entry.get("subject") or ""
            time_str = entry.get("time") or entry.get("created_at") or ""

            activity_at = None
            if time_str:
                try:
                    from dateutil.parser import parse as parse_dt
                    activity_at = parse_dt(time_str)
                    if activity_at.tzinfo:
                        activity_at = activity_at.replace(tzinfo=None)
                except Exception:
                    pass

            session.add(ThreadMessage(
                reply_id=reply.id,
                direction=direction,
                channel="email",
                subject=subject,
                body=body,
                activity_at=activity_at,
                source="smartlead",
                activity_type="email_sent" if direction == "outbound" else "email_replied",
                position=idx,
            ))

        reply.thread_fetched_at = datetime.utcnow()

        # Update last_touched_at from the last message timestamp
        if history_entries:
            last_ts = history_entries[-1].get("time") or history_entries[-1].get("created_at")
            if last_ts:
                try:
                    from dateutil.parser import parse as parse_dt
                    lt = parse_dt(last_ts)
                    if lt.tzinfo:
                        lt = lt.replace(tzinfo=None)
                    reply.last_touched_at = lt
                except Exception:
                    pass

        logger.info(
            f"[THREAD_CACHE] Cached {len(history_entries)} messages for reply {reply.id}"
        )
        return True

    except Exception as e:
        logger.warning(f"[THREAD_CACHE] Failed to fetch/cache thread for reply {reply.id}: {e}")
        return False


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
        
        # Inbox link — only use trusted sources:
        # 1. ui_master_inbox_link from webhook (SmartLead provides the correct URL)
        # 2. sl_email_lead_map_id (the leadMap identifier, NOT the per-campaign lead ID)
        # NEVER use sl_email_lead_id — it's the per-campaign lead ID and produces
        # broken master inbox links (wrong leadMap= value).
        inbox_link = (
            payload.get("ui_master_inbox_link")
            or (payload.get("body") or {}).get("ui_master_inbox_link")
        )
        if not inbox_link:
            lead_map_id = payload.get("sl_email_lead_map_id") or ""
            if lead_map_id and lead_map_id != "":
                inbox_link = f"https://app.smartlead.ai/app/master-inbox?action&leadMap={lead_map_id}"
        if not inbox_link:
            inbox_link = "https://app.smartlead.ai/app/master-inbox"
        
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

        # Skip empty/meaningless reply bodies — no point classifying or drafting
        _body_stripped = (body or "").strip().lower()
        if not _body_stripped or _body_stripped in ("(no content)", "(empty)", "no content", "empty"):
            campaign_name = payload.get("campaign_name") or payload.get("flow_name") or "unknown"
            source = payload.get("_source", "webhook")
            logger.warning(f"[PROCESSOR] Skipping empty reply body: lead={lead_email} campaign={campaign_name} source={source}")
            return None

        # Reject outbound sends masquerading as EMAIL_REPLY events
        import re
        outbound_pattern = r"^Email \d+ sent to .+ for campaign"
        if re.match(outbound_pattern, body.strip()):
            logger.info(f"[PROCESSOR] Rejecting outbound send masquerading as reply: {body[:120]}")
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

        custom_reply_prompt = automation.reply_prompt if automation else None
        project = None
        proj_sender_name = None
        proj_sender_position = None
        proj_sender_company = None
        if campaign_name:
            try:
                from app.models.contact import Project
                from app.models.reply import ReplyPromptTemplateModel
                from sqlalchemy import text as sa_text

                # Case-insensitive match: find project where campaign_filters array
                # contains campaign_name (ignoring case)
                project_result = await session.execute(
                    select(Project).where(
                        and_(
                            Project.campaign_filters.isnot(None),
                            Project.deleted_at.is_(None),
                            sa_text(
                                "EXISTS (SELECT 1 FROM jsonb_array_elements_text(projects.campaign_filters) AS cf "
                                "WHERE LOWER(cf) = LOWER(:cname))"
                            ),
                        )
                    ).params(cname=campaign_name).limit(1)
                )
                project = project_result.scalar()
                if project:
                    # Extract sender identity fields
                    proj_sender_name = project.sender_name
                    proj_sender_position = project.sender_position
                    proj_sender_company = project.sender_company
                    logger.info(f"[PROCESSOR] Project '{project.name}' sender: {proj_sender_name}, {proj_sender_position}, {proj_sender_company}")

                    # If project has a custom prompt template, use it
                    if project.reply_prompt_template_id:
                        template_result = await session.execute(
                            select(ReplyPromptTemplateModel).where(
                                ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                            )
                        )
                        template = template_result.scalar()
                        if template:
                            custom_reply_prompt = template.prompt_text
                            logger.info(f"[PROCESSOR] Using project prompt from '{project.name}' (template: {template.name})")
                            # Track template usage for learning system
                            try:
                                template.usage_count = (template.usage_count or 0) + 1
                                template.last_used_at = datetime.utcnow()
                            except Exception:
                                pass
                    # Load project knowledge to enrich the prompt
                    try:
                        from app.models.project_knowledge import ProjectKnowledge
                        knowledge_result = await session.execute(
                            select(ProjectKnowledge).where(
                                ProjectKnowledge.project_id == project.id
                            )
                        )
                        knowledge_entries = knowledge_result.scalars().all()
                        if knowledge_entries:
                            knowledge_context = _format_knowledge_context(knowledge_entries, category=classification.get("category"))
                            if custom_reply_prompt:
                                custom_reply_prompt += knowledge_context
                            else:
                                custom_reply_prompt = knowledge_context
                            logger.info(f"[PROCESSOR] Loaded {len(knowledge_entries)} knowledge entries for project '{project.name}'")
                    except Exception as ke:
                        logger.warning(f"[PROCESSOR] Knowledge loading failed (non-fatal): {ke}")

                    # Load reference examples from operator's past replies
                    try:
                        ref_examples = await _load_reference_examples(
                            session, project.id, category=classification.get("category")
                        )
                        if ref_examples:
                            if custom_reply_prompt:
                                custom_reply_prompt += ref_examples
                            else:
                                custom_reply_prompt = ref_examples
                            logger.info(f"[PROCESSOR] Loaded reference examples for project '{project.name}'")
                    except Exception as ref_err:
                        logger.warning(f"[PROCESSOR] Reference examples loading failed (non-fatal): {ref_err}")
            except Exception as proj_err:
                logger.warning(f"[PROCESSOR] Project prompt lookup failed (non-fatal): {proj_err}")

        # Track classification cost (non-fatal)
        try:
            if project:
                from app.services.cost_service import cost_service
                await cost_service.record_cost(
                    session, project.id, "openai_4o_mini_1k",
                    units=1, description="reply classification",
                )
        except Exception as cost_err:
            logger.debug(f"[PROCESSOR] Cost tracking failed: {cost_err}")

        # Generate draft reply
        draft = await generate_draft_reply(
            subject=subject,
            body=body,
            category=classification["category"],
            first_name=first_name,
            last_name=last_name,
            company=payload.get("company_name", ""),
            custom_prompt=custom_reply_prompt,
            sender_name=proj_sender_name,
            sender_position=proj_sender_position,
            sender_company=proj_sender_company,
        )
        
        # Detect language & translate if needed (non-blocking)
        lang_info = await detect_and_translate(body)
        detected_lang = lang_info.get("language")
        translated_body = lang_info.get("translation")
        translated_draft = None
        if detected_lang and detected_lang not in ("en", "ru") and draft.get("body"):
            draft_lang = await detect_and_translate(draft["body"])
            if draft_lang.get("translation"):
                translated_draft = draft_lang["translation"]

        # Determine received_at: use actual reply timestamp from source platform
        received_at = _parse_source_timestamp(payload) or datetime.utcnow()

        # Check for existing ProcessedReply (same email + campaign).
        # If the lead replied again after operator responded, UPDATE the record
        # instead of creating a duplicate — keeps one row per (email, campaign)
        # with the latest reply data, and re-surfaces it for operator attention.
        from sqlalchemy import func as sa_func
        existing_pr_result = await session.execute(
            select(ProcessedReply).where(
                and_(
                    sa_func.lower(ProcessedReply.lead_email) == lead_email.lower(),
                    ProcessedReply.campaign_id == campaign_id,
                )
            ).limit(1)
        )
        existing_pr = existing_pr_result.scalar_one_or_none()

        if existing_pr:
            # Snapshot previous version before overwriting (prevents data loss)
            prev = {
                "email_body": existing_pr.email_body,
                "email_subject": existing_pr.email_subject,
                "category": existing_pr.category,
                "draft_reply": existing_pr.draft_reply,
                "draft_subject": existing_pr.draft_subject,
                "approval_status": existing_pr.approval_status,
                "received_at": existing_pr.received_at.isoformat() if existing_pr.received_at else None,
                "updated_at": existing_pr.updated_at.isoformat() if existing_pr.updated_at else None,
            }
            old_raw = existing_pr.raw_webhook_data or {}
            if not isinstance(old_raw, dict):
                old_raw = {}
            versions = old_raw.get("_previous_versions", [])
            versions.append(prev)
            # Keep last 10 versions max
            if len(versions) > 10:
                versions = versions[-10:]

            # Update existing record with new reply data
            if received_at > (existing_pr.received_at or datetime.min):
                existing_pr.received_at = received_at
            existing_pr.email_body = body
            existing_pr.reply_text = body
            existing_pr.email_subject = subject
            existing_pr.category = classification["category"]
            existing_pr.category_confidence = classification["confidence"]
            existing_pr.classification_reasoning = classification["reasoning"]
            existing_pr.draft_reply = draft["body"]
            existing_pr.draft_subject = draft["subject"]
            existing_pr.draft_generated_at = datetime.utcnow()
            existing_pr.approval_status = None  # Re-surface for operator
            existing_pr.detected_language = detected_lang
            existing_pr.translated_body = translated_body
            existing_pr.translated_draft = translated_draft
            new_raw = dict(payload) if isinstance(payload, dict) else {}
            new_raw["_previous_versions"] = versions
            existing_pr.raw_webhook_data = new_raw
            existing_pr.updated_at = datetime.utcnow()
            existing_pr.source = existing_pr.source or "smartlead"
            existing_pr.channel = existing_pr.channel or "email"
            if campaign_name:
                existing_pr.campaign_name = campaign_name
            # Backfill / update smartlead_lead_id + invalidate thread cache
            existing_pr.smartlead_lead_id = (
                existing_pr.smartlead_lead_id
                or payload.get("sl_email_lead_id")
                or None
            )
            existing_pr.thread_fetched_at = None  # invalidate so thread is re-fetched
            if inbox_link:
                existing_pr.inbox_link = inbox_link
            processed_reply = existing_pr
            await session.flush()
            logger.info(f"[PROCESSOR] Updated existing ProcessedReply {existing_pr.id} for {lead_email} with new reply")
        else:
            # Create new processed reply record
            processed_reply = ProcessedReply(
                automation_id=automation_id,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                source="smartlead",
                channel="email",
                lead_email=lead_email,
                lead_first_name=first_name,
                lead_last_name=last_name,
                lead_company=payload.get("company_name", ""),
                email_subject=subject,
                email_body=body,
                reply_text=body,  # Store reply text same as body
                received_at=received_at,
                category=classification["category"],
                category_confidence=classification["confidence"],
                classification_reasoning=classification["reasoning"],
                draft_reply=draft["body"],
                draft_subject=draft["subject"],
                draft_generated_at=datetime.utcnow(),
                detected_language=detected_lang,
                translated_body=translated_body,
                translated_draft=translated_draft,
                inbox_link=inbox_link,  # Smartlead master inbox link
                raw_webhook_data=payload,
                smartlead_lead_id=payload.get("sl_email_lead_id") or None,
            )
            session.add(processed_reply)
            try:
                await session.flush()
            except Exception as flush_err:
                if "uq_processed_reply_email_campaign" in str(flush_err):
                    logger.info(f"[PROCESSOR] Concurrent insert caught by unique constraint for {lead_email}, campaign {campaign_id}")
                    await session.rollback()
                    return None
                raise
            logger.info(f"[PROCESSOR] Created new ProcessedReply {processed_reply.id} for {lead_email}")
        
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
            
            # If contact doesn't exist, create one from the webhook data
            # This fixes a critical bug where 97%+ of reply senders were never
            # imported into the contacts table
            new_campaign_entry = {
                "name": campaign_name,
                "id": str(campaign_id) if campaign_id else None,
                "source": "smartlead"
            } if campaign_name or campaign_id else None

            if not contact:
                logger.info(f"[PROCESSOR] Contact not found for {lead_email}, creating from reply data")
                contact = Contact(
                    company_id=1,  # Default company
                    email=lead_email.lower().strip(),
                    first_name=first_name or None,
                    last_name=last_name or None,
                    company_name=payload.get("company_name") or None,
                    source="smartlead",
                    status="replied",
                    last_reply_at=datetime.utcnow(),
                )
                session.add(contact)
                await session.flush()  # Get contact.id
                if new_campaign_entry:
                    contact.set_platform("smartlead", {"campaigns": [new_campaign_entry]})
                logger.info(f"[PROCESSOR] Created contact id={contact.id} for {lead_email}")
            else:
                # Update reply tracking on existing contact
                contact.mark_replied("email")
                contact.mark_synced("smartlead")

                # Merge new campaign into platform_state (dedup by name+id)
                if new_campaign_entry:
                    existing_campaigns = contact.get_platform("smartlead").get("campaigns", [])
                    already_listed = any(
                        isinstance(c, dict) and c.get("id") == new_campaign_entry["id"] and c.get("name") == new_campaign_entry["name"]
                        for c in existing_campaigns
                    )
                    if not already_listed:
                        contact.set_platform("smartlead", {"campaigns": existing_campaigns + [new_campaign_entry]})
                        logger.info(f"[PROCESSOR] Added campaign '{campaign_name}' to contact {contact.id}")

            # Append webhook payload to smartlead_raw for debugging
            import json
            webhook_entry = {
                "received_at": datetime.utcnow().isoformat(),
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
                    raw["webhooks"] = raw["webhooks"][-20:]
                    contact.update_platform_raw("smartlead", raw)
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning(f"[PROCESSOR] Failed to parse smartlead_raw, resetting: {e}")
                    contact.update_platform_raw("smartlead", {"webhooks": [webhook_entry]})
            else:
                contact.update_platform_raw("smartlead", {"webhooks": [webhook_entry]})
            
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
            contact.mark_replied("email")

            # Use status machine for forward-only transition
            category = classification.get("category", "other")
            from app.services.status_machine import transition_status, status_from_ai_category
            target = status_from_ai_category(category)
            new_st, ok, _msg = transition_status(contact.status, target)
            if ok:
                contact.status = new_st
            logger.info(f"[PROCESSOR] Updated contact {contact.id} with reply data from {lead_email}")
        except Exception as activity_err:
            logger.warning(f"[PROCESSOR] Failed to create ContactActivity (non-fatal): {activity_err}")
        
        # Send Slack notification
        from app.services.notification_service import send_slack_notification
        
        # Determine channel - use automation config or default test channel
        from app.core.config import settings as _cfg
        channel_id = _cfg.SLACK_DEFAULT_CHANNEL
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
        
        # Send Telegram notification only for actual inbound replies
        # Uses DB-backed dedup (telegram_sent_at) to prevent duplicates even after Redis flush
        event_type = payload.get("event_type", "EMAIL_REPLY")
        should_notify = event_type == "EMAIL_REPLY"

        if should_notify and payload.get("_source") == "api_polling":
            # Only notify for recent polled replies (< 2 hours old)
            time_replied = payload.get("time_replied")
            if time_replied:
                try:
                    if isinstance(time_replied, str):
                        replied_dt = datetime.fromisoformat(time_replied.replace("Z", "+00:00")).replace(tzinfo=None)
                    else:
                        replied_dt = time_replied
                    age = datetime.utcnow() - replied_dt
                    if age > timedelta(hours=2):
                        should_notify = False
                        logger.info(f"[PROCESSOR] Skipping Telegram for old polled reply ({age.days}d old): {lead_email}")
                except Exception:
                    pass  # If we can't parse the time, notify anyway

        # DB-backed dedup: check if Telegram was already sent for this reply
        # (survives Redis flush, prevents duplicate notifications)
        if should_notify and processed_reply.telegram_sent_at:
            should_notify = False
            logger.info(f"[PROCESSOR] Skipping Telegram — already sent at {processed_reply.telegram_sent_at}")

        # Also check Redis for fast dedup (avoids DB queries on re-processed replies)
        if should_notify:
            try:
                from app.services.cache_service import cache_service
                if cache_service.is_connected and cache_service._redis:
                    redis_key = f"telegram:reply:{processed_reply.id}"
                    already_sent = await cache_service._redis.get(redis_key)
                    if already_sent:
                        should_notify = False
                        logger.info(f"[PROCESSOR] Skipping Telegram — Redis dedup hit for reply {processed_reply.id}")
            except Exception:
                pass  # Redis failure should not block notifications

        if should_notify:
            try:
                from app.services.notification_service import notify_reply_needs_attention
                campaign_name = payload.get("campaign_name") or processed_reply.campaign_name
                sent = await notify_reply_needs_attention(
                    processed_reply, 
                    classification["category"],
                    campaign_name=campaign_name
                )
                if sent:
                    # Mark as sent in DB (source of truth for dedup)
                    processed_reply.telegram_sent_at = datetime.utcnow()
                    # Also cache in Redis (fast dedup, 48h TTL)
                    try:
                        from app.services.cache_service import cache_service
                        if cache_service.is_connected and cache_service._redis:
                            await cache_service._redis.set(
                                f"telegram:reply:{processed_reply.id}", "1", ex=48 * 3600
                            )
                    except Exception:
                        pass  # Redis failure is non-fatal
            except Exception as telegram_error:
                logger.error(f"[PROCESSOR] Telegram notification failed (non-fatal): {telegram_error}")
        else:
            logger.info(f"[PROCESSOR] Skipping Telegram for event_type: {event_type}, source: {payload.get('_source', 'webhook')}")
        
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
                logger.info(f"Logged reply {processed_reply.id} to Google Sheet {automation.google_sheet_id} at row {row_number}")
            except Exception as e:
                logger.error(f"Failed to log reply to Google Sheets: {e}")
        
        # Update automation monitoring stats
        if automation:
            automation.last_run_at = datetime.utcnow()
            automation.total_processed = (automation.total_processed or 0) + 1

        # Increment campaign's sl_reply_count so polling knows this reply
        # was already caught by webhook and won't trigger redundant pagination.
        # Only for real webhooks — polling writes the definitive count directly.
        is_from_polling = payload.get("_source") == "api_polling"
        if campaign_id and not is_from_polling:
            try:
                from app.models.campaign import Campaign as CampaignModel
                camp_result = await session.execute(
                    select(CampaignModel).where(
                        CampaignModel.external_id == str(campaign_id),
                        CampaignModel.platform == "smartlead",
                    ).limit(1)
                )
                camp = camp_result.scalar_one_or_none()
                if camp:
                    camp.sl_reply_count = (camp.sl_reply_count or 0) + 1
                    logger.info(f"[PROCESSOR] Webhook incremented campaign {campaign_id} sl_reply_count → {camp.sl_reply_count}")
            except Exception as camp_err:
                logger.warning(f"[PROCESSOR] Failed to increment sl_reply_count (non-fatal): {camp_err}")

        await session.commit()
        logger.info(f"Processed reply {processed_reply.id} - category: {classification['category']}")
        
        return processed_reply
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        await session.rollback()
        # Track error on automation if found (in separate transaction)
        automation = locals().get('automation')
        if automation:
            try:
                automation.total_errors = (automation.total_errors or 0) + 1
                automation.last_error = str(e)[:500]  # Truncate long errors
                automation.last_error_at = datetime.utcnow()
                await session.commit()
            except Exception as log_err:
                logger.warning(f"Failed to log automation error stats: {log_err}")
                await session.rollback()
        raise


async def process_getsales_reply(
    message_text: str,
    contact: "Contact",
    flow_name: str,
    flow_uuid: str,
    message_id: str,
    activity_at: datetime,
    raw_data: dict,
    session: AsyncSession,
) -> Optional[ProcessedReply]:
    """Process a GetSales LinkedIn reply: classify, generate draft, create/update ProcessedReply.

    Used by both the webhook path (crm_sync.py) and the polling path
    (crm_sync_service.sync_getsales_replies) so classification + draft logic
    lives in one place.

    Returns the created/updated ProcessedReply, or None if skipped.
    """
    from sqlalchemy import func as sa_func

    lead_email = (contact.email or "").lower().strip()
    if not lead_email:
        logger.warning(f"[GETSALES] Skipping reply — contact {contact.id} has no email")
        return None

    # --- Dedup: check for existing ProcessedReply ---
    existing_pr = None
    # Step 1: if we have a real automation UUID, try exact match
    if flow_uuid:
        exact_result = await session.execute(
            select(ProcessedReply).where(
                and_(
                    ProcessedReply.source == "getsales",
                    sa_func.lower(ProcessedReply.lead_email) == lead_email,
                    ProcessedReply.campaign_id == flow_uuid,
                )
            ).limit(1)
        )
        existing_pr = exact_result.scalar_one_or_none()

    # Step 2: broader match by lead_email only.
    # Catches: polling without automation → webhook with automation, or vice versa.
    if not existing_pr:
        broader_result = await session.execute(
            select(ProcessedReply).where(
                and_(
                    ProcessedReply.source == "getsales",
                    sa_func.lower(ProcessedReply.lead_email) == lead_email,
                )
            ).order_by(ProcessedReply.created_at.desc()).limit(1)
        )
        existing_pr = broader_result.scalar_one_or_none()
        if existing_pr:
            logger.info(f"[GETSALES] Found existing reply {existing_pr.id} via broader match (campaign_id {existing_pr.campaign_id} != {flow_uuid})")

    if existing_pr and existing_pr.received_at and activity_at and activity_at <= existing_pr.received_at:
        # Still allow update if we have new campaign info for an unclassified record.
        # Polling creates records with empty campaign_name; the webhook arrives later
        # with the real automation but older activity_at (from linkedin_message.sent_at).
        has_new_campaign_info = flow_name and (not existing_pr.campaign_name)
        if not has_new_campaign_info:
            logger.info(f"[GETSALES] Skipping older/duplicate reply for {lead_email} (existing received_at={existing_pr.received_at})")
            return existing_pr
        logger.info(f"[GETSALES] Allowing update for {lead_email}: existing has no campaign, webhook has '{flow_name}'")

    # --- Find project for sender identity + prompt template ---
    custom_reply_prompt = None
    proj_sender_name = None
    proj_sender_position = None
    proj_sender_company = None

    if flow_name:
        try:
            from app.models.contact import Project
            from app.models.reply import ReplyPromptTemplateModel
            from sqlalchemy import text as sa_text

            # Try exact match first
            project_result = await session.execute(
                select(Project).where(
                    and_(
                        Project.campaign_filters.isnot(None),
                        Project.deleted_at.is_(None),
                        sa_text(
                            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(projects.campaign_filters) AS cf "
                            "WHERE LOWER(cf) = LOWER(:cname))"
                        ),
                    )
                ).params(cname=flow_name).limit(1)
            )
            project = project_result.scalar()

            # Prefix match: campaign name starts with project name
            matched_via_prefix = False
            if not project:
                proj_result = await session.execute(
                    select(Project).where(
                        and_(
                            Project.deleted_at.is_(None),
                            sa_text("LOWER(:cname) LIKE LOWER(projects.name) || '%'"),
                        )
                    ).params(cname=flow_name).limit(1)
                )
                project = proj_result.scalar()
                if project:
                    matched_via_prefix = True

            if project:
                # Auto-register new campaign name so future exact matches work
                if matched_via_prefix and project.campaign_filters is not None:
                    existing_lower = {c.lower() for c in project.campaign_filters if isinstance(c, str)}
                    if flow_name.lower() not in existing_lower:
                        project.campaign_filters = project.campaign_filters + [flow_name]
                        logger.info(f"[GETSALES] Auto-registered campaign '{flow_name}' to project '{project.name}'")

                proj_sender_name = project.sender_name
                proj_sender_position = project.sender_position
                proj_sender_company = project.sender_company
                logger.info(f"[GETSALES] Project '{project.name}' sender: {proj_sender_name}")

                if project.reply_prompt_template_id:
                    tmpl_result = await session.execute(
                        select(ReplyPromptTemplateModel).where(
                            ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                        )
                    )
                    tmpl = tmpl_result.scalar()
                    if tmpl:
                        custom_reply_prompt = tmpl.prompt_text
                        logger.info(f"[GETSALES] Using project prompt template '{tmpl.name}'")
                # Load project knowledge
                try:
                    from app.models.project_knowledge import ProjectKnowledge
                    knowledge_result = await session.execute(
                        select(ProjectKnowledge).where(
                            ProjectKnowledge.project_id == project.id
                        )
                    )
                    knowledge_entries = knowledge_result.scalars().all()
                    # Store entries — will be formatted after classification (to match category)
                    _knowledge_entries = knowledge_entries
                    logger.info(f"[GETSALES] Loaded {len(knowledge_entries)} knowledge entries")
                except Exception as ke:
                    logger.warning(f"[GETSALES] Knowledge loading failed (non-fatal): {ke}")
        except Exception as proj_err:
            logger.warning(f"[GETSALES] Project lookup failed (non-fatal): {proj_err}")

    _knowledge_entries = locals().get("_knowledge_entries", [])

    # --- Classify ---
    linkedin_suffix = "This is a LinkedIn DM, not an email. Classify based on the message content."
    classification = await classify_reply(
        subject="(LinkedIn message)",
        body=message_text,
        custom_prompt=linkedin_suffix,
    )
    logger.info(f"[GETSALES] Classification: {classification['category']} ({classification['confidence']})")

    # --- Format knowledge AFTER classification to include matching golden examples ---
    if _knowledge_entries:
        knowledge_context = _format_knowledge_context(_knowledge_entries, category=classification.get("category"))
        if custom_reply_prompt:
            custom_reply_prompt += knowledge_context
        else:
            custom_reply_prompt = knowledge_context

    # --- Load reference examples from operator's past replies ---
    _project_for_refs = locals().get("project")
    if _project_for_refs:
        try:
            ref_examples = await _load_reference_examples(
                session, _project_for_refs.id, category=classification.get("category")
            )
            if ref_examples:
                if custom_reply_prompt:
                    custom_reply_prompt += ref_examples
                else:
                    custom_reply_prompt = ref_examples
                logger.info(f"[GETSALES] Loaded reference examples for project '{_project_for_refs.name}'")
        except Exception as ref_err:
            logger.warning(f"[GETSALES] Reference examples loading failed (non-fatal): {ref_err}")

    # --- Generate draft ---
    linkedin_draft_suffix = (
        "This is a LinkedIn message, keep reply SHORT (2-3 sentences), "
        "conversational, no subject line needed."
    )
    combined_prompt = linkedin_draft_suffix
    if custom_reply_prompt:
        combined_prompt = custom_reply_prompt + "\n\n" + linkedin_draft_suffix

    draft = await generate_draft_reply(
        subject="LinkedIn conversation",
        body=message_text,
        category=classification["category"],
        first_name=contact.first_name or "",
        last_name=contact.last_name or "",
        company=contact.company_name or "",
        custom_prompt=combined_prompt,
        sender_name=proj_sender_name,
        sender_position=proj_sender_position,
        sender_company=proj_sender_company,
    )

    # --- Build GetSales inbox link ---
    lead_uuid = raw_data.get("lead_uuid") or raw_data.get("lead", {}).get("uuid") or raw_data.get("contact", {}).get("uuid")
    sender_profile_uuid = (
        raw_data.get("sender_profile_uuid")
        or (raw_data.get("automation", {}) or {}).get("sender_profile_uuid")
        or ""
    )
    inbox_link = None
    if lead_uuid:
        from app.services.crm_sync_service import GetSalesClient
        inbox_link = GetSalesClient.build_inbox_url(lead_uuid, sender_profile_uuid)

    # --- Detect language & translate ---
    lang_info = await detect_and_translate(message_text)
    detected_lang = lang_info.get("language")
    translated_body = lang_info.get("translation")
    translated_draft = None
    if detected_lang and detected_lang not in ("en", "ru") and draft.get("body"):
        draft_lang = await detect_and_translate(draft["body"])
        if draft_lang.get("translation"):
            translated_draft = draft_lang["translation"]

    # --- Create or update ProcessedReply ---
    if existing_pr:
        existing_pr.received_at = activity_at
        existing_pr.email_body = message_text
        existing_pr.reply_text = message_text
        existing_pr.category = classification["category"]
        existing_pr.category_confidence = classification["confidence"]
        existing_pr.classification_reasoning = classification["reasoning"]
        existing_pr.draft_reply = draft.get("body")
        existing_pr.draft_subject = draft.get("subject")
        existing_pr.draft_generated_at = datetime.utcnow()
        existing_pr.detected_language = detected_lang
        existing_pr.translated_body = translated_body
        existing_pr.translated_draft = translated_draft
        existing_pr.approval_status = None  # Re-surface for operator
        existing_pr.raw_webhook_data = raw_data
        existing_pr.updated_at = datetime.utcnow()
        # Only overwrite campaign info if we have a real automation-derived flow_name.
        # Empty flow_name means we couldn't determine the automation (e.g. "synced") —
        # never overwrite a known campaign with empty/unknown values.
        if flow_name:
            existing_pr.campaign_name = flow_name
            existing_pr.campaign_id = flow_uuid
        if inbox_link:
            existing_pr.inbox_link = inbox_link
        processed_reply = existing_pr
        await session.flush()
        logger.info(f"[GETSALES] Updated ProcessedReply {existing_pr.id} for {lead_email}")
    else:
        processed_reply = ProcessedReply(
            source="getsales",
            channel="linkedin",
            campaign_id=flow_uuid,
            campaign_name=flow_name,
            lead_email=lead_email,
            lead_first_name=contact.first_name,
            lead_last_name=contact.last_name,
            lead_company=contact.company_name,
            email_subject="LinkedIn conversation",
            email_body=message_text,
            reply_text=message_text,
            received_at=activity_at,
            category=classification["category"],
            category_confidence=classification["confidence"],
            classification_reasoning=classification["reasoning"],
            draft_reply=draft.get("body"),
            draft_subject=draft.get("subject"),
            draft_generated_at=datetime.utcnow(),
            detected_language=detected_lang,
            translated_body=translated_body,
            translated_draft=translated_draft,
            raw_webhook_data=raw_data,
            inbox_link=inbox_link,
        )
        session.add(processed_reply)
        try:
            await session.flush()
        except Exception as flush_err:
            if "uq_processed_reply_email_campaign" in str(flush_err):
                logger.info(f"[GETSALES] Concurrent insert caught by unique constraint for {lead_email}")
                await session.rollback()
                return None
            raise
        logger.info(f"[GETSALES] Created ProcessedReply {processed_reply.id} for {lead_email}")

    # --- Telegram notification (dedup via telegram_sent_at) ---
    if processed_reply and not processed_reply.telegram_sent_at:
        try:
            from app.services.notification_service import notify_linkedin_reply
            from app.services.crm_sync_service import GETSALES_UUID_TO_PROJECT

            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Unknown"
            resolved_project_id = (
                getattr(contact, "project_id", None)
                or GETSALES_UUID_TO_PROJECT.get(flow_uuid)
            )
            from app.services.crm_sync_service import GETSALES_SENDER_PROFILES
            resolved_sender_name = GETSALES_SENDER_PROFILES.get(sender_profile_uuid or "")

            sent = await notify_linkedin_reply(
                contact_name=contact_name,
                contact_email=contact.email or "N/A",
                flow_name=flow_name or processed_reply.campaign_name or "",
                message_text=message_text,
                campaign_name=flow_name or processed_reply.campaign_name,
                project_id=resolved_project_id,
                inbox_link=inbox_link,
                sender_name=resolved_sender_name,
                category=processed_reply.category,
            )
            if sent:
                processed_reply.telegram_sent_at = datetime.utcnow()
                logger.info(f"[GETSALES] Telegram notification sent for reply {processed_reply.id} (project_id={resolved_project_id})")
        except Exception as tg_err:
            logger.warning(f"[GETSALES] Telegram notification failed (non-fatal): {tg_err}")

    return processed_reply
