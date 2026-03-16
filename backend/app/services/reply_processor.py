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


async def _load_reference_examples(session, project_id: int, category: str = None, limit: int = 30, lead_message: str = None) -> str:
    """Load most relevant operator replies via semantic similarity.

    Primary strategy: embed the lead's message, find the N most similar past situations
    via pgvector cosine search in reference_examples table.

    Fallback: if no embeddings exist yet, falls back to legacy length-based sort from thread_messages.
    """
    try:
        # Try semantic retrieval first
        if lead_message:
            result = await _load_reference_examples_semantic(session, project_id, lead_message, limit)
            if result:
                return result

        # Fallback to legacy
        return await _load_reference_examples_legacy(session, project_id, category, limit)
    except Exception as e:
        logger.warning(f"[PROCESSOR] Reference examples loading failed (non-fatal): {e}")
        return ""


async def _load_reference_examples_semantic(session, project_id: int, lead_message: str, limit: int = 30) -> str:
    """Semantic vector search — find most similar past situations."""
    try:
        from app.services.embedding_service import get_embedding
        from app.models.learning import ReferenceExample
        from sqlalchemy import func

        # Check if we have any embeddings for this project
        count_result = await session.execute(
            select(func.count(ReferenceExample.id)).where(
                ReferenceExample.project_id == project_id,
                ReferenceExample.embedding.isnot(None),
            )
        )
        embed_count = count_result.scalar() or 0
        if embed_count == 0:
            logger.info(f"[PROCESSOR] No embeddings for project {project_id}, falling back to legacy")
            return ""

        # Embed the lead's message
        query_vector = await get_embedding(lead_message)
        if not query_vector:
            logger.warning("[PROCESSOR] Failed to embed lead message, falling back to legacy")
            return ""

        # Vector similarity search — fetch 3x limit, then re-rank by quality-weighted score
        # This ensures high-quality examples (operator-approved, feedback) surface over
        # generic thread_messages, reducing bias from unranked historical data.
        fetch_limit = min(limit * 3, embed_count)
        result = await session.execute(
            select(ReferenceExample)
            .where(
                ReferenceExample.project_id == project_id,
                ReferenceExample.embedding.isnot(None),
            )
            .order_by(ReferenceExample.embedding.cosine_distance(query_vector))
            .limit(fetch_limit)
        )
        candidates = result.scalars().all()

        # Split: golden examples (always included) vs semantic matches (ranked)
        golden_examples = []
        semantic_candidates = []
        for ex in candidates:
            if ex.source == "feedback" and (ex.quality_score or 0) >= 5:
                golden_examples.append(ex)
            else:
                semantic_candidates.append(ex)

        # Also fetch any golden examples that weren't in the similarity results
        golden_in_results = {ex.id for ex in golden_examples}
        golden_result = await session.execute(
            select(ReferenceExample).where(
                ReferenceExample.project_id == project_id,
                ReferenceExample.source == "feedback",
                ReferenceExample.quality_score >= 5,
                ReferenceExample.id.notin_(golden_in_results) if golden_in_results else True,
            )
        )
        extra_golden = golden_result.scalars().all()
        golden_examples.extend(extra_golden)

        # Re-rank semantic candidates by quality-weighted score
        ranked = []
        for idx, ex in enumerate(semantic_candidates):
            position_penalty = idx / max(len(semantic_candidates), 1)
            quality_boost = (ex.quality_score or 3) / 3.0
            score = quality_boost * (1.0 - position_penalty * 0.5)
            ranked.append((score, ex))

        ranked.sort(key=lambda x: x[0], reverse=True)
        # Reserve slots for golden examples, fill rest with semantic matches
        semantic_limit = max(limit - len(golden_examples), 0)
        examples = golden_examples + [ex for _, ex in ranked[:semantic_limit]]

        if not examples:
            return ""

        # Format for prompt — golden examples first with special label
        parts = []
        for ex in examples:
            ctx = ex.lead_context or {}
            label = "GOLDEN EXAMPLE — THIS IS THE IDEAL STYLE" if ex.source == "feedback" else f"{ex.category or 'unknown'}"
            parts.append(
                f"[{label}] Lead ({ctx.get('name', 'lead')}, {ctx.get('company', '')}):\n"
                f"\"{ex.lead_message[:500]}\"\n"
                f"Operator replied:\n"
                f"\"{ex.operator_reply}\""
            )

        logger.info(
            f"[PROCESSOR] Semantic retrieval: {len(parts)} examples for project {project_id} "
            f"(from {embed_count} total embeddings)"
        )

        return (
            "\n\n=== OPERATOR'S REAL REPLIES (YOUR PRIMARY REFERENCE — COPY THIS STYLE) ===\n"
            f"These are the {len(parts)} MOST SIMILAR situations to the current lead.\n"
            "COPY this EXACT style: same greeting, structure, detail, tone, length.\n"
            "Pick the CLOSEST matching example and adapt for the current lead.\n\n"
            + "\n\n---\n\n".join(parts)
            + "\n=== END OPERATOR'S REAL REPLIES ==="
        )
    except Exception as e:
        logger.warning(f"[PROCESSOR] Semantic retrieval failed (non-fatal): {e}")
        return ""


async def _load_reference_examples_legacy(session, project_id: int, category: str = None, limit: int = 20) -> str:
    """Legacy fallback: load operator replies sorted by length from thread_messages."""
    try:
        from app.models.reply import ProcessedReply as PRModel, ThreadMessage
        from app.models.contact import Project

        proj_result = await session.execute(
            select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            return ""

        from sqlalchemy import or_, and_, func as sa_func
        campaign_parts = []
        campaign_names = [c.lower() for c in (project.campaign_filters or []) if isinstance(c, str)]
        if campaign_names:
            campaign_parts.append(sa_func.lower(PRModel.campaign_name).in_(campaign_names))
        pname = (project.name or "").lower()
        if pname and len(pname) > 2:
            campaign_parts.append(sa_func.lower(PRModel.campaign_name).like(f"{pname}%"))

        if not campaign_parts:
            return ""

        campaign_condition = or_(*campaign_parts)

        sender_uuids = [s for s in (project.getsales_senders or []) if isinstance(s, str)]
        if sender_uuids:
            sender_text = PRModel.raw_webhook_data.op("->>")("sender_profile_uuid")
            sender_check = or_(
                PRModel.channel != "linkedin",
                sender_text.in_(sender_uuids),
            )
            project_filter = and_(campaign_condition, sender_check)
        else:
            project_filter = campaign_condition

        QUALIFIED_CATS = {"interested", "meeting_request", "question"}

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
                project_filter,
                PRModel.category.in_(list(QUALIFIED_CATS)),
            )
            .order_by(ThreadMessage.id.desc())
            .limit(100)
        )
        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return ""

        seen_prefixes = set()
        unique_rows = []
        for r in rows:
            clean_body = _strip_html_to_text(r.body)
            if len(clean_body) < 400:
                continue
            prefix = clean_body[:150].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            unique_rows.append((r, clean_body))

        if not unique_rows:
            return ""

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
            f"[PROCESSOR] Legacy: loaded {len(parts)} reference examples "
            f"for project {project_id} (category={category})"
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
        logger.warning(f"[PROCESSOR] Legacy reference examples loading failed (non-fatal): {e}")
        return ""


def _strip_markdown_formatting(text: str) -> str:
    """Remove markdown bold/italic stars from AI-generated replies."""
    if not text:
        return text
    # Bold/italic: ***text***, **text**, *text*
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Markdown bullet lists → plain dashes
    text = re.sub(r'(?m)^\s*\*\s+', '- ', text)
    return text


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
    r"\[(?:"
    r"Your |Ваш[аеи]? |Tu |Su |Ihr |"        # common prefixes
    r"вставьте |insert |add |укажите |"       # action verbs
    r"имя|name|email|link|ссылк|врем"         # common nouns
    r")"
    r"[^\[\]]{2,60}\]",                        # content inside brackets (2-60 chars)
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
- interested: The person shows ANY positive signal — wants to learn more, requests materials,
  says "send it", "yes", "ok", "давайте", "отправьте", "присылайте", or uses positive emojis
  (👍, 🤝, ✅, etc). Short affirmative replies = interested. When in doubt, classify as interested.
- meeting_request: The person wants to schedule a call or meeting
- not_interested: The person EXPLICITLY declines or says no. Includes polite declines
  like "no difficulties", "all good thanks", "not needed", "пока проблем нет",
  "сложностей нет", "нет необходимости", "нас всё устраивает", "спасибо, не надо".
  Key rule: short polite replies that acknowledge your message but express no need = not_interested.
- out_of_office: Auto-reply or out of office message
- wrong_person: Not the right contact, suggests someone else
- unsubscribe: Wants to opt out or stop receiving emails
- question: Has specific questions before deciding
- other: Doesn't fit any other category. Use ONLY when the message is truly ambiguous or irrelevant.
  Do NOT use "other" for short positive replies — those are "interested".

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
1. GOLDEN EXAMPLES are your #1 priority. If a "GOLDEN EXAMPLE" is provided, treat it as the
   EXACT template. Copy its structure, section order, bullet style, detail level, and phrasing
   as closely as possible — only changing the lead's name and adapting specific details to
   match the lead's situation. Do NOT simplify, shorten, or reorganize the golden example's format.
   If the golden example has a full pricing breakdown with per-method bullet points, yours MUST too.
   If it has a separate "Что важно знать" section, yours MUST have the same section.
2. Other REFERENCE REPLIES show the operator's natural variations. Use them for tone and phrasing,
   but the golden example's structure takes priority.
3. MIRROR THE LEAD'S FORMAT: If the prospect asks numbered questions (1, 2, 3...) or bullet points,
   answer in the SAME numbered/bulleted format, addressing each point in order. Use the golden
   example's content to fill each answer.
4. NEVER invent or change specific numbers (prices, percentages, country counts, timelines).
   Use ONLY the exact numbers from the reference examples and knowledge base provided.
   If knowledge says "120+ стран" write "120+", not "180+". If it says "5%" write "5%".
5. If no examples are provided, use these defaults:
   - interested/meeting_request: detailed response with next steps
   - question: answer helpfully with specifics
   - not_interested: thank them politely (keep short)
   - wrong_person: ask for referral (keep short)
   - unsubscribe: confirm removal (keep short)
6. Sign off with the sender name above — NEVER use placeholder brackets like [Your Name], [вставьте...], [insert...] etc.
   NEVER generate ANY text in square brackets. If you don't know a value, omit it entirely.
7. If sender name is unknown, omit the sign-off entirely.
8. NEVER use markdown formatting (no **bold**, no *italic*, no ### headers). Use plain text only.

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
    model: Optional[str] = None,
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
    # Default to Gemini 2.5 Pro — best KPI (style match) at $0.05/reply
    # Falls back to GPT-4o-mini if Gemini is unavailable
    draft_model = model or "gemini-2.5-pro"
    use_gemini = draft_model.startswith("gemini")

    # --- Gemini path ---
    if use_gemini:
        from app.services.gemini_client import gemini_generate, extract_json_from_gemini, is_gemini_available
        if not is_gemini_available():
            logger.warning("[PROCESSOR] Gemini requested but not configured, falling back to gpt-4o-mini")
            draft_model = "gpt-4o-mini"
            use_gemini = False

    if use_gemini:
        for attempt in range(max_retries):
            try:
                logger.info(f"[PROCESSOR] Gemini draft generation attempt {attempt + 1}/{max_retries} model={draft_model}")
                result_raw = await gemini_generate(
                    system_prompt="You are an AI assistant generating email reply drafts. Respond with ONLY a valid JSON object, no extra text.",
                    user_prompt=prompt,
                    temperature=0.4,
                    max_tokens=8000,  # Gemini 2.5 Pro uses thinking tokens, needs headroom
                    model=draft_model,
                )
                content = result_raw["content"]
                if not content or not content.strip():
                    raise ValueError("Gemini returned empty content")
                clean_json = extract_json_from_gemini(content)
                if not clean_json.strip():
                    raise ValueError(f"Gemini JSON extraction failed, raw: {content[:300]}")
                result = json.loads(clean_json)
                draft_body = result.get("body", "")
                draft_body = _strip_placeholder_brackets(draft_body)
                draft_body = _strip_markdown_formatting(draft_body)
                logger.info(f"[PROCESSOR] Gemini draft OK: {len(draft_body)} chars, tokens={result_raw.get('tokens', {})}")
                return {
                    "subject": result.get("subject", f"Re: {subject}"),
                    "body": draft_body,
                    "tone": result.get("tone", "professional"),
                }
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[PROCESSOR] Gemini draft attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 2)
        logger.error(f"[PROCESSOR] Gemini draft failed after {max_retries} attempts: {last_error}")
        return {
            "subject": f"Re: {subject}",
            "body": f"(Draft generation failed after {max_retries} attempts: {last_error})",
            "tone": "error",
        }

    # --- OpenAI path ---
    for attempt in range(max_retries):
        try:
            logger.debug(f"[PROMPT DEBUG] Draft generation attempt {attempt + 1}/{max_retries}")
            logger.debug(f"[PROMPT DEBUG] Draft prompt:\n{prompt[:500]}...")

            response = await openai_service.complete(
                prompt=prompt,
                model=draft_model,
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
            draft_body = _strip_markdown_formatting(draft_body)

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
            # Mark as fetched so we don't re-hit the API on every click
            reply.thread_fetched_at = datetime.utcnow()
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

        # Auto-dismiss if the last message in the thread is outbound
        # (operator already replied before we processed this inbound)
        if last_direction == "outbound" and reply.approval_status in (None, "pending"):
            reply.approval_status = "dismissed"
            reply.approved_at = datetime.utcnow()
            logger.info(f"[AUTO-DISMISS] Reply {reply.id} auto-dismissed at processing time — operator already replied via email")

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
        
        # Lead name - prioritize first_name/last_name from lead_data (SmartLead DB),
        # fall back to to_name only if it's a real person (not a system sender like bounces)
        _SYSTEM_SENDERS = {"mail delivery subsystem", "mailer-daemon", "postmaster", "mail delivery system", "automated message"}
        first_name = payload.get("first_name", "")
        last_name = payload.get("last_name", "")
        if not first_name and not last_name:
            to_name = payload.get("to_name") or ""
            if to_name.lower().strip() not in _SYSTEM_SENDERS:
                lead_name_parts = to_name.split() if to_name else []
                first_name = lead_name_parts[0] if len(lead_name_parts) > 0 else ""
                last_name = " ".join(lead_name_parts[1:]) if len(lead_name_parts) > 1 else ""
            else:
                logger.info(f"[PROCESSOR] Ignoring system sender to_name: {to_name}")
        # Final fallback: look up the contact record in our DB by email
        if not first_name and not last_name and lead_email:
            try:
                from app.models.contact import Contact
                contact_row = (await session.execute(
                    select(Contact.first_name, Contact.last_name)
                    .where(Contact.email == lead_email)
                    .limit(1)
                )).first()
                if contact_row and (contact_row.first_name or contact_row.last_name):
                    first_name = contact_row.first_name or ""
                    last_name = contact_row.last_name or ""
                    logger.info(f"[PROCESSOR] Name from contacts DB: {first_name} {last_name}")
            except Exception as e:
                logger.warning(f"[PROCESSOR] Contact lookup failed: {e}")
        logger.info(f"[PROCESSOR] Parsed name: first={first_name}, last={last_name}")
        
        # Campaign name — fall back to campaigns table lookup by campaign_id
        campaign_name = payload.get("campaign_name", "")
        if not campaign_name and campaign_id:
            try:
                from app.models.campaign import Campaign
                camp_row = (await session.execute(
                    select(Campaign.name).where(
                        Campaign.external_id == campaign_id,
                        Campaign.name.isnot(None),
                    ).limit(1)
                )).first()
                if camp_row and camp_row[0]:
                    campaign_name = camp_row[0]
                    logger.info(f"[PROCESSOR] Resolved campaign_name '{campaign_name}' from campaign_id={campaign_id} via DB")
            except Exception as e:
                logger.debug(f"[PROCESSOR] Campaign name lookup by ID failed: {e}")
        
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
        
        # Classify the reply — merge automation + project-level classification prompts
        logger.info(f"[PROCESSOR] Starting classification...")
        custom_classification_prompt = automation.classification_prompt if automation else None
        # Check for project-specific classification prompt (lightweight pre-lookup)
        if campaign_name:
            try:
                from app.models.contact import Project as _ProjCls
                from sqlalchemy import text as _sa_text
                _pre = (await session.execute(
                    select(_ProjCls.classification_prompt).where(
                        and_(
                            _ProjCls.campaign_filters.isnot(None),
                            _ProjCls.deleted_at.is_(None),
                            _sa_text(
                                "EXISTS (SELECT 1 FROM jsonb_array_elements_text(projects.campaign_filters) AS cf "
                                "WHERE LOWER(cf) = LOWER(:cname))"
                            ),
                        )
                    ).params(cname=campaign_name).limit(1)
                )).scalar()
                if _pre:
                    custom_classification_prompt = (custom_classification_prompt + "\n" + _pre) if custom_classification_prompt else _pre
                    logger.info(f"[PROCESSOR] Using project-specific classification prompt for campaign '{campaign_name}'")
            except Exception as _pe:
                logger.debug(f"[PROCESSOR] Project classification prompt lookup failed: {_pe}")
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

                # Fallback: ownership rules matching (prefix/contains/tags)
                matched_via_rules = False
                if not project:
                    from app.services.crm_sync_service import match_campaign_to_project
                    matched_pid = match_campaign_to_project(campaign_name)
                    if matched_pid:
                        proj_result = await session.execute(
                            select(Project).where(
                                and_(Project.id == matched_pid, Project.deleted_at.is_(None))
                            )
                        )
                        project = proj_result.scalar()
                        if project:
                            matched_via_rules = True

                # Auto-register: add campaign to project's campaign_filters for future exact matches
                if project and matched_via_rules and project.campaign_filters is not None:
                    existing_lower = {c.lower() for c in project.campaign_filters if isinstance(c, str)}
                    if campaign_name.lower() not in existing_lower:
                        project.campaign_filters = project.campaign_filters + [campaign_name]
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(project, "campaign_filters")
                        logger.info(f"[PROCESSOR] Auto-registered SmartLead campaign '{campaign_name}' to project '{project.name}'")
                        # Audit log
                        try:
                            from app.models.campaign_audit_log import CampaignAuditLog
                            session.add(CampaignAuditLog(
                                project_id=project.id, action="add", campaign_name=campaign_name,
                                source="auto_discovery",
                                details=f"Auto-registered from SmartLead reply webhook (ownership rules match)",
                            ))
                        except Exception:
                            pass

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
                            session, project.id, category=classification.get("category"),
                            lead_message=body,
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

        # Auto-inject Calendly slots for meeting_request/interested categories
        if project and classification.get("category") in ("meeting_request", "interested"):
            try:
                calendly_cfg = project.calendly_config
                if calendly_cfg and calendly_cfg.get("members"):
                    from app.services.calendly_service import get_slots_with_fallback
                    cal_data = await get_slots_with_fallback(calendly_cfg)
                    if cal_data.get("formatted_for_prompt"):
                        if custom_reply_prompt:
                            custom_reply_prompt += "\n\n" + cal_data["formatted_for_prompt"]
                        else:
                            custom_reply_prompt = cal_data["formatted_for_prompt"]
                        logger.info(f"[PROCESSOR] Injected Calendly slots ({len(cal_data.get('slots_display', []))} days) for {classification['category']}")
            except Exception as cal_err:
                logger.warning(f"[PROCESSOR] Calendly slot injection failed (non-fatal): {cal_err}")

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

        # Content-based dedup: hash the reply body to detect true duplicates
        # (same webhook received twice, or webhook + polling for the same reply).
        # Different replies from the same lead get their own records + notifications.
        import hashlib
        body_for_hash = (body or "").strip().lower()[:500]
        message_hash = hashlib.md5(body_for_hash.encode()).hexdigest()

        # Create new processed reply record (one per unique reply)
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
            reply_text=body,
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
            inbox_link=inbox_link,
            raw_webhook_data=payload,
            smartlead_lead_id=payload.get("sl_email_lead_id") or None,
            message_hash=message_hash,
        )
        session.add(processed_reply)
        try:
            await session.flush()
        except Exception as flush_err:
            if "uq_processed_reply_content" in str(flush_err):
                logger.info(f"[PROCESSOR] Duplicate reply (same content hash) for {lead_email}, campaign {campaign_id} — skipping")
                # Re-raise to let the caller's begin_nested() savepoint handle rollback.
                # Do NOT call session.rollback() here — it corrupts the session when
                # this function runs inside a savepoint (polling path), losing ALL
                # previously-processed replies in the same batch.
                raise
            raise
        logger.info(f"[PROCESSOR] Created ProcessedReply {processed_reply.id} for {lead_email} (hash={message_hash[:8]})")

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
                "source": "smartlead",
                "added_at": datetime.utcnow().isoformat(),
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
            from app.services.status_machine import transition_status, status_from_ai_category, derive_external_status
            target = status_from_ai_category(category)
            new_st, ok, _msg = transition_status(contact.status, target)
            if ok:
                contact.status = new_st

            # Derive client-facing external status if project has config
            if project and project.external_status_config:
                ext = derive_external_status(
                    project.external_status_config,
                    reply_category=category,
                    internal_status=contact.status,
                )
                if ext:
                    contact.status_external = ext
                    # Propagate to Google Sheet (fire-and-forget)
                    try:
                        from app.services.sheet_sync_service import sheet_sync_service
                        await sheet_sync_service.update_sheet_status(
                            contact.project_id, contact.email, ext
                        )
                    except Exception as sheet_err:
                        logger.debug(f"Sheet status update skipped: {sheet_err}")
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
        # Track error on automation in a SEPARATE session (original is rolled back)
        automation_id_local = locals().get('automation_id')
        if automation_id_local:
            try:
                from app.db import async_session_maker
                async with async_session_maker() as err_session:
                    from sqlalchemy import update as sa_update
                    await err_session.execute(
                        sa_update(ReplyAutomation)
                        .where(ReplyAutomation.id == automation_id_local)
                        .values(
                            total_errors=ReplyAutomation.total_errors + 1,
                            last_error=str(e)[:500],
                            last_error_at=datetime.utcnow(),
                        )
                    )
                    await err_session.commit()
            except Exception as log_err:
                logger.warning(f"Failed to log automation error stats: {log_err}")
        raise


async def _fetch_getsales_thread(
    session: AsyncSession,
    reply: ProcessedReply,
    conversation_uuid: str,
    sender_profile_uuid: str,
) -> bool:
    """Fetch GetSales LinkedIn conversation and store as ThreadMessage rows.

    Non-fatal: any failure is logged as a warning and returns False.
    """
    import os
    from app.services.crm_sync_service import GetSalesClient
    from sqlalchemy import delete as sa_delete

    api_key = os.getenv("GETSALES_API_KEY", "")
    if not api_key:
        logger.warning("[GETSALES_THREAD] No GETSALES_API_KEY set, skipping thread fetch")
        return False
    client = GetSalesClient(api_key)
    try:
        messages = await client.get_conversation_messages(conversation_uuid)
    finally:
        await client.close()

    if not messages:
        logger.info(f"[GETSALES_THREAD] No messages for conversation {conversation_uuid[:8]}")
        return False

    # Clear existing thread messages for this reply
    await session.execute(sa_delete(ThreadMessage).where(ThreadMessage.reply_id == reply.id))

    for idx, msg in enumerate(messages):
        msg_type = msg.get("type", "")
        direction = "outbound" if msg_type == "outbox" else "inbound"
        body = msg.get("text") or msg.get("message") or ""
        activity_at_str = msg.get("sent_at") or msg.get("created_at")
        activity_at = None
        if activity_at_str:
            try:
                from dateutil.parser import parse as dt_parse
                activity_at = dt_parse(activity_at_str)
            except Exception:
                pass

        session.add(ThreadMessage(
            reply_id=reply.id,
            direction=direction,
            channel="linkedin",
            subject=None,
            body=body,
            activity_at=activity_at,
            source="getsales",
            activity_type="linkedin_sent" if direction == "outbound" else "linkedin_replied",
            position=idx,
        ))

    reply.thread_fetched_at = datetime.utcnow()
    logger.info(f"[GETSALES_THREAD] Stored {len(messages)} messages for reply {reply.id}")
    return True


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

    # --- Content-based dedup via message_hash ---
    import hashlib
    body_for_hash = (message_text or "").strip().lower()[:500]
    message_hash = hashlib.md5(body_for_hash.encode()).hexdigest()

    # --- Find project for sender identity + prompt template ---
    custom_reply_prompt = None
    proj_sender_name = None
    proj_sender_position = None
    proj_sender_company = None
    project = None
    matched_via_prefix = False
    _knowledge_entries = []

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

            # Fallback: prefix/tag/contains matching via ownership rules
            matched_via_prefix = False
            if not project:
                from app.services.crm_sync_service import match_campaign_to_project
                matched_pid = match_campaign_to_project(flow_name)
                if matched_pid:
                    proj_result = await session.execute(
                        select(Project).where(
                            and_(Project.id == matched_pid, Project.deleted_at.is_(None))
                        )
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
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(project, "campaign_filters")
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

    # --- Auto-register GetSales campaign in campaigns table (God Panel) ---
    _project_resolved = project
    from app.services.crm_sync_service import _is_valid_campaign_name
    if flow_name and _is_valid_campaign_name(flow_name):
        try:
            from app.models.campaign import Campaign as CampaignModel
            # Check if already registered
            existing_campaign = None
            if flow_uuid:
                existing_campaign = (await session.execute(
                    select(CampaignModel).where(
                        CampaignModel.platform == "getsales",
                        CampaignModel.external_id == flow_uuid,
                    ).limit(1)
                )).scalar()
            if not existing_campaign:
                existing_campaign = (await session.execute(
                    select(CampaignModel).where(
                        CampaignModel.platform == "getsales",
                        CampaignModel.name == flow_name,
                    ).limit(1)
                )).scalar()
            if not existing_campaign:
                new_campaign = CampaignModel(
                    company_id=1,
                    platform="getsales",
                    channel="linkedin",
                    external_id=flow_uuid or None,
                    name=flow_name,
                    status="active",
                    project_id=_project_resolved.id if _project_resolved else None,
                    first_seen_at=datetime.utcnow(),
                    resolution_method=(
                        "exact_match" if (_project_resolved and not matched_via_prefix)
                        else "prefix_match" if (_project_resolved and matched_via_prefix)
                        else "unresolved"
                    ),
                    resolution_detail=(
                        f"Matched project '{_project_resolved.name}'" if _project_resolved else "No project match"
                    ),
                )
                session.add(new_campaign)
                await session.flush()
                logger.info(f"[GETSALES] Auto-registered campaign '{flow_name}' in campaigns table (id={new_campaign.id})")
            elif _project_resolved and not existing_campaign.project_id:
                existing_campaign.project_id = _project_resolved.id
                existing_campaign.resolution_method = "prefix_match" if matched_via_prefix else "exact_match"
                existing_campaign.resolution_detail = f"Matched project '{_project_resolved.name}'"
                logger.info(f"[GETSALES] Updated campaign '{flow_name}' with project '{_project_resolved.name}'")
        except Exception as camp_err:
            logger.debug(f"[GETSALES] Campaign registration failed (non-fatal): {camp_err}")

    # _knowledge_entries is initialized before the try block above

    # --- Classify ---
    linkedin_suffix = "This is a LinkedIn DM, not an email. Classify based on the message content."
    # Merge project-specific classification prompt if available
    _classify_prompt = linkedin_suffix
    if project and getattr(project, "classification_prompt", None):
        _classify_prompt = linkedin_suffix + "\n" + project.classification_prompt
        logger.info(f"[GETSALES] Using project-specific classification prompt for '{project.name}'")
    classification = await classify_reply(
        subject="(LinkedIn message)",
        body=message_text,
        custom_prompt=_classify_prompt,
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
                session, _project_for_refs.id, category=classification.get("category"),
                lead_message=message_text,
            )
            if ref_examples:
                if custom_reply_prompt:
                    custom_reply_prompt += ref_examples
                else:
                    custom_reply_prompt = ref_examples
                logger.info(f"[GETSALES] Loaded reference examples for project '{_project_for_refs.name}'")
        except Exception as ref_err:
            logger.warning(f"[GETSALES] Reference examples loading failed (non-fatal): {ref_err}")

    # --- Auto-inject Calendly slots for meeting/interested ---
    if project and classification.get("category") in ("meeting_request", "interested"):
        try:
            calendly_cfg = project.calendly_config
            if calendly_cfg and calendly_cfg.get("members"):
                from app.services.calendly_service import get_slots_with_fallback
                cal_data = await get_slots_with_fallback(calendly_cfg)
                if cal_data.get("formatted_for_prompt"):
                    if custom_reply_prompt:
                        custom_reply_prompt += "\n\n" + cal_data["formatted_for_prompt"]
                    else:
                        custom_reply_prompt = cal_data["formatted_for_prompt"]
                    logger.info(f"[GETSALES] Injected Calendly slots for {classification['category']}")
        except Exception as cal_err:
            logger.warning(f"[GETSALES] Calendly slot injection failed (non-fatal): {cal_err}")

    # --- Generate draft ---
    linkedin_draft_suffix = (
        "This is a LinkedIn message, keep reply SHORT (2-3 sentences), "
        "conversational, no subject line needed. "
        "Do NOT include any email signature, sign-off block, or contact details at the end — "
        "this is a LinkedIn DM, not an email. "
        "Do NOT use em-dashes (—). Use commas, periods, or simple dashes (-) instead."
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

    # --- Upsert ProcessedReply (one per unique reply) ---
    # Check if a reply with the same content already exists (regardless of campaign_id).
    # This handles the sync-first-then-webhook scenario: sync creates a record with
    # empty campaign info, webhook later arrives with the real automation name/UUID.
    existing_result = await session.execute(
        select(ProcessedReply).where(
            ProcessedReply.lead_email == lead_email,
            ProcessedReply.message_hash == message_hash,
        ).limit(1)
    )
    existing_reply = existing_result.scalar()

    if existing_reply:
        # Same content already exists — enrich campaign info if we have better data
        if flow_name and not existing_reply.campaign_name:
            existing_reply.campaign_name = flow_name
            existing_reply.campaign_id = flow_uuid or existing_reply.campaign_id
            logger.info(f"[GETSALES] Enriched reply {existing_reply.id} campaign: {flow_name}")
        elif flow_uuid and not existing_reply.campaign_id:
            existing_reply.campaign_id = flow_uuid
            logger.info(f"[GETSALES] Enriched reply {existing_reply.id} campaign_id: {flow_uuid}")
        else:
            logger.info(f"[GETSALES] Duplicate reply (same content hash) for {lead_email} — skipping")
        processed_reply = existing_reply
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
            message_hash=message_hash,
        )
        session.add(processed_reply)
        try:
            await session.flush()
        except Exception as flush_err:
            if "uq_processed_reply_content" in str(flush_err):
                logger.info(f"[GETSALES] Duplicate reply (race condition) for {lead_email} — skipping")
                # Re-raise to let the caller's begin_nested() savepoint handle rollback.
                # Do NOT call session.rollback() here — it corrupts the outer session
                # when this function runs inside a savepoint (polling path).
                raise
            raise
        logger.info(f"[GETSALES] Created ProcessedReply {processed_reply.id} for {lead_email} (hash={message_hash[:8]})")

    # --- Fetch LinkedIn conversation thread and store as ThreadMessage rows ---
    # SKIP during polling path (_source == "polling"): thread fetch adds ThreadMessage
    # objects whose flush can corrupt the shared session, killing the entire batch.
    # The conversation_sync loop (every 3 min) handles thread fetching independently.
    # Only run inline for webhook path (own session, safe to fail).
    is_polling = raw_data.get("_source") == "polling" or raw_data.get("automation") == "synced"
    conv_uuid = raw_data.get("linkedin_conversation_uuid")
    if conv_uuid and sender_profile_uuid and not is_polling:
        try:
            thread_ok = await _fetch_getsales_thread(session, processed_reply, conv_uuid, sender_profile_uuid)
            # Auto-dismiss if the last message in the thread is outbound
            # (operator/automation already replied before we processed this inbound)
            if thread_ok:
                from app.models.reply import ThreadMessage as TM
                last_msg = (await session.execute(
                    select(TM.direction).where(TM.reply_id == processed_reply.id)
                    .order_by(TM.position.desc()).limit(1)
                )).scalar()
                if last_msg == "outbound" and processed_reply.approval_status in (None, "pending"):
                    processed_reply.approval_status = "dismissed"
                    processed_reply.approved_at = datetime.utcnow()
                    logger.info(f"[AUTO-DISMISS] Reply {processed_reply.id} auto-dismissed at processing time — operator already replied via LinkedIn")
        except Exception as thread_err:
            logger.warning(f"[GETSALES] Thread fetch failed (non-fatal): {thread_err}")

    # NOTE: Telegram notification is NOT sent here — callers must send it
    # AFTER session.commit() succeeds, to avoid ghost notifications on rollback.
    # Use send_getsales_notification() after commit.

    return processed_reply


async def send_getsales_notification(
    processed_reply,
    contact,
    flow_name: str,
    flow_uuid: str,
    message_text: str,
    raw_data: dict,
    session=None,
) -> bool:
    """Send Telegram notification for a GetSales reply.

    Must be called AFTER session.commit() to avoid ghost notifications on rollback.
    Updates telegram_sent_at on the processed_reply (caller should commit again or
    use a separate session).
    """
    if not processed_reply or processed_reply.telegram_sent_at:
        return False

    try:
        from app.services.notification_service import notify_linkedin_reply
        from app.services.crm_sync_service import GETSALES_UUID_TO_PROJECT, GETSALES_SENDER_PROFILES

        contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Unknown"
        resolved_project_id = (
            getattr(contact, "project_id", None)
            or GETSALES_UUID_TO_PROJECT.get(flow_uuid)
        )
        # Use campaign_name from ProcessedReply if flow_name is empty
        effective_campaign = flow_name or processed_reply.campaign_name or ""
        sender_profile_uuid = (
            raw_data.get("sender_profile_uuid")
            or (raw_data.get("automation", {}) or {}).get("sender_profile_uuid")
            or ""
        )
        resolved_sender_name = GETSALES_SENDER_PROFILES.get(sender_profile_uuid or "")

        lead_uuid = raw_data.get("lead_uuid") or raw_data.get("lead", {}).get("uuid") or raw_data.get("contact", {}).get("uuid")
        inbox_link = None
        if lead_uuid:
            from app.services.crm_sync_service import GetSalesClient
            inbox_link = GetSalesClient.build_inbox_url(lead_uuid, sender_profile_uuid)

        # Fallback: resolve project by sender_profile_uuid if campaign routing fails
        _valid_campaign = effective_campaign and effective_campaign not in ("Unknown Flow", "Unknown", "synced", "")
        if not resolved_project_id and not _valid_campaign and sender_profile_uuid:
            try:
                from app.services.notification_service import _get_project_by_sender
                proj = await _get_project_by_sender(sender_profile_uuid)
                if proj:
                    resolved_project_id = proj.get("id")
                    logger.info(f"[GETSALES] Resolved project via sender UUID: {proj.get('name')} (id={resolved_project_id})")
            except Exception:
                pass

        sent = await notify_linkedin_reply(
            contact_name=contact_name,
            contact_email=contact.email or "N/A",
            flow_name=effective_campaign,
            message_text=message_text,
            campaign_name=effective_campaign,
            project_id=resolved_project_id,
            inbox_link=inbox_link,
            sender_name=resolved_sender_name,
            category=processed_reply.category,
        )
        if sent:
            processed_reply.telegram_sent_at = datetime.utcnow()
            logger.info(f"[GETSALES] Telegram notification sent for reply {processed_reply.id} (project_id={resolved_project_id})")
            # Persist the telegram_sent_at marker
            if session:
                try:
                    await session.commit()
                except Exception:
                    pass  # Non-critical — dedup marker only
            return True
    except Exception as tg_err:
        logger.warning(f"[GETSALES] Telegram notification failed (non-fatal): {tg_err}")
    return False
