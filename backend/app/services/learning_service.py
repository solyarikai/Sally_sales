"""
Learning Service — AI learning cycles and operator correction tracking.

Analyzes project conversations + operator corrections to improve reply templates and ICP knowledge.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.contact import Contact, ContactActivity, Project
from app.models.reply import ProcessedReply, ReplyPromptTemplateModel
from app.models.learning import LearningLog, OperatorCorrection
from app.models.project_knowledge import ProjectKnowledge
from app.services.openai_service import openai_service
from app.services.conversation_analysis_service import (
    get_project_conversations,
    format_conversations_for_prompt,
)

logger = logging.getLogger(__name__)

LEARNING_SYSTEM_PROMPT = """You are an expert outbound sales optimization engine. You analyze real conversations between SDRs and prospects, along with ALL operator actions on AI-generated drafts.

Your job: Update the reply prompt template and extract ICP insights based on patterns you observe.

INPUT:
1. Current reply prompt template (what the AI currently uses)
2. Real conversation threads (with prospect responses and our replies)
3. Operator actions on AI drafts — every action is a learning signal:
   - EDITED: operator changed draft before sending (learn what was wrong)
   - APPROVED: operator sent draft unchanged (learn what works — reinforce these patterns)
   - DISMISSED: operator chose not to reply (draft was bad or reply unnecessary — learn when NOT to suggest)
   - REGENERATED: operator rejected draft and asked for a new one (draft quality was poor)

ANALYSIS:
- EDITED drafts: identify patterns in how operators improve AI drafts (tone shifts, added context, removed fluff)
- APPROVED drafts: identify what the AI got right — reinforce these patterns in the template
- DISMISSED drafts: identify when AI should not suggest replies (wrong lead type, unnecessary follow-up)
- REGENERATED drafts: identify systematic quality issues (wrong tone, missing context, too long/short)
- Detect which prospect types engage positively vs negatively
- Find common objections and effective responses to them
- Note language/channel-specific patterns (email vs LinkedIn, formal vs casual)

CRITICAL — TEMPLATE FORMAT:
The "updated_template" must be a set of INSTRUCTIONS for the AI draft generator — NOT a sample reply.
It should describe: who the sender is, the product/service value proposition, tone guidelines, response rules per category, pricing details, and what to avoid.
Use {sender_name}, {sender_position_line}, {sender_company_line} as placeholders for sender identity.
Example structure:
  "You are replying as {sender_name}{sender_position_line}{sender_company_line}.
   [Company] does [value prop]. Key points: [bullet points from conversations].
   Tone: [observed tone]. For interested leads: [pattern]. For objections: [pattern]."
NEVER generate a sample reply email as the template. The template is INSTRUCTIONS, not a reply.

OUTPUT strict JSON:
{
  "updated_template": "Instructions for the AI (see format above)...",
  "icp_insights": {
    "positive_signals": ["signal1", "signal2"],
    "negative_signals": ["signal1", "signal2"],
    "qualification_criteria": ["criterion1", "criterion2"]
  },
  "objection_patterns": ["pattern1", "pattern2"],
  "change_summary": "Human-readable description of what changed and why",
  "reasoning": "Detailed reasoning for the changes"
}"""

FEEDBACK_SYSTEM_PROMPT = """You are an expert outbound sales optimization engine. You are receiving direct operator feedback about reply quality or ICP targeting.

INPUT:
1. Current reply prompt template
2. Current ICP knowledge (learned traits + signals)
3. Operator feedback text

Your job: Incorporate the operator's feedback into the template and ICP knowledge.

CRITICAL — TEMPLATE FORMAT:
The "updated_template" must be INSTRUCTIONS for the AI draft generator — NOT a sample reply.
It should describe: who the sender is, the product/service value prop, tone guidelines, response rules, and what to avoid.
Use {sender_name}, {sender_position_line}, {sender_company_line} as placeholders for sender identity.
NEVER generate a sample reply email as the template.

CRITICAL — GOLDEN EXAMPLES:
If the feedback contains an ACTUAL REPLY EXAMPLE (a real reply the operator wrote or wants the AI to produce), you MUST extract it verbatim into "golden_examples". Golden examples are the EXACT replies operators want the AI to produce — they define the tone, structure, length, and level of detail. Each example needs a "situation" label (e.g., "interested_asks_presentation", "meeting_request", "pricing_question").

OUTPUT strict JSON:
{
  "updated_template": "Instructions for the AI (NOT a sample reply)...",
  "icp_updates": {
    "positive_signals": ["signal1", "signal2"],
    "negative_signals": ["signal1"],
    "qualification_criteria": ["criterion1"]
  },
  "golden_examples": [
    {
      "situation": "short_label_for_this_type_of_reply",
      "category": "interested|meeting_request|question|etc",
      "reply_text": "The EXACT verbatim reply text from the operator, preserving all formatting, line breaks, bullet points, pricing details, signatures — NOTHING omitted or paraphrased"
    }
  ],
  "change_summary": "What changed based on the feedback",
  "reasoning": "Why these changes make sense"
}"""

MIN_QUALIFIED_THRESHOLD = 20


class LearningService:
    """Orchestrates AI learning cycles and correction tracking."""

    async def run_learning_cycle(
        self,
        session: AsyncSession,
        project_id: int,
        max_conversations: int = 100,
        force_all: bool = False,
        trigger: str = "manual",
        log_id: Optional[int] = None,
    ) -> LearningLog:
        """Run a full learning cycle: fetch conversations, analyze, update template + ICP."""

        # Create or fetch existing log
        if log_id:
            result = await session.execute(select(LearningLog).where(LearningLog.id == log_id))
            log = result.scalar_one_or_none()
            if not log:
                raise ValueError(f"LearningLog {log_id} not found")
        else:
            log = LearningLog(
                project_id=project_id,
                trigger=trigger,
                status="processing",
            )
            session.add(log)
            await session.flush()

        try:
            # Fetch project
            proj_result = await session.execute(
                select(Project).where(and_(Project.id == project_id, Project.deleted_at.is_(None)))
            )
            project = proj_result.scalar_one_or_none()
            if not project:
                log.status = "failed"
                log.error_message = "Project not found"
                return log

            # Fetch prioritized conversations
            conversations, stats = await self._fetch_prioritized_conversations(
                session, project_id, max_conversations, force_all
            )

            log.conversations_analyzed = len(conversations)
            log.conversations_email = stats.get("email", 0)
            log.conversations_linkedin = stats.get("linkedin", 0)
            log.qualified_count = stats.get("qualified", 0)

            # Check threshold
            if not force_all and stats.get("qualified", 0) < MIN_QUALIFIED_THRESHOLD and len(conversations) < MIN_QUALIFIED_THRESHOLD:
                log.status = "insufficient_data"
                log.change_summary = f"Only {stats.get('qualified', 0)} qualified conversations found (minimum: {MIN_QUALIFIED_THRESHOLD})"
                return log

            if not conversations:
                log.status = "insufficient_data"
                log.change_summary = "No conversations found for analysis"
                return log

            # Fetch recent operator corrections
            corrections = await self._get_recent_corrections(session, project_id)

            # Run analysis
            await self._analyze_and_update(session, project, conversations, corrections, log)

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)[:2000]
            logger.error(f"Learning cycle failed for project {project_id}: {e}", exc_info=True)

        return log

    async def process_feedback(
        self,
        session: AsyncSession,
        project_id: int,
        feedback_text: str,
        log_id: int | None = None,
    ) -> LearningLog:
        """Process operator feedback via Cmd+K and update template/ICP."""
        if log_id:
            # Reuse existing log created by the endpoint
            result = await session.execute(
                select(LearningLog).where(LearningLog.id == log_id)
            )
            log = result.scalar_one_or_none()
            if not log:
                log = LearningLog(
                    project_id=project_id,
                    trigger="feedback",
                    feedback_text=feedback_text,
                    status="processing",
                )
                session.add(log)
                await session.flush()
        else:
            log = LearningLog(
                project_id=project_id,
                trigger="feedback",
                feedback_text=feedback_text,
                status="processing",
            )
            session.add(log)
            await session.flush()

        try:
            proj_result = await session.execute(
                select(Project).where(and_(Project.id == project_id, Project.deleted_at.is_(None)))
            )
            project = proj_result.scalar_one_or_none()
            if not project:
                log.status = "failed"
                log.error_message = "Project not found"
                return log

            # Get current template
            current_template = ""
            if project.reply_prompt_template_id:
                tmpl_result = await session.execute(
                    select(ReplyPromptTemplateModel).where(
                        ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                    )
                )
                tmpl = tmpl_result.scalar_one_or_none()
                if tmpl:
                    current_template = tmpl.prompt_text

            # Get current ICP knowledge
            icp_result = await session.execute(
                select(ProjectKnowledge).where(
                    ProjectKnowledge.project_id == project_id,
                    ProjectKnowledge.category == "icp",
                )
            )
            icp_entries = icp_result.scalars().all()
            icp_data = {e.key: e.value for e in icp_entries}

            # Build prompt
            user_prompt = f"""Project: {project.name}

CURRENT TEMPLATE:
{current_template or '(no template set)'}

CURRENT ICP KNOWLEDGE:
{json.dumps(icp_data, indent=2) if icp_data else '(none)'}

OPERATOR FEEDBACK:
{feedback_text}

Incorporate this feedback into the template and ICP knowledge."""

            # Snapshot before
            log.before_snapshot = {
                "template": current_template,
                "icp": icp_data,
            }

            if not openai_service.is_connected():
                log.status = "failed"
                log.error_message = "OpenAI not configured"
                return log

            response = await openai_service.complete(
                prompt=user_prompt,
                system_prompt=FEEDBACK_SYSTEM_PROMPT,
                model="gpt-4o-mini",
                temperature=0.5,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            parsed = json.loads(response)

            # Update template (or create if project has none)
            if parsed.get("updated_template"):
                if project.reply_prompt_template_id:
                    await session.execute(
                        update(ReplyPromptTemplateModel)
                        .where(ReplyPromptTemplateModel.id == project.reply_prompt_template_id)
                        .values(
                            prompt_text=parsed["updated_template"],
                            version=ReplyPromptTemplateModel.version + 1,
                            updated_at=datetime.utcnow(),
                        )
                    )
                    log.template_id = project.reply_prompt_template_id
                else:
                    # Create new template and assign to project
                    new_tmpl = ReplyPromptTemplateModel(
                        name=f"{project.name} - auto",
                        prompt_text=parsed["updated_template"],
                    )
                    session.add(new_tmpl)
                    await session.flush()
                    project.reply_prompt_template_id = new_tmpl.id
                    log.template_id = new_tmpl.id

            # Update ICP knowledge
            change_type = "feedback_applied"
            if parsed.get("icp_updates"):
                for icp_key, icp_val in parsed["icp_updates"].items():
                    if icp_val:
                        await self._upsert_knowledge(
                            session, project_id, "icp", icp_key, icp_val, f"ICP: {icp_key}"
                        )
                if parsed.get("updated_template"):
                    change_type = "both"

            # Save golden examples — EXACT operator reply examples for draft generation
            golden_examples = parsed.get("golden_examples") or []
            for ex in golden_examples:
                situation = ex.get("situation", "general")
                cat = ex.get("category", "interested")
                reply_text = ex.get("reply_text", "")
                if reply_text and len(reply_text) > 20:
                    await self._upsert_knowledge(
                        session, project_id, "examples",
                        f"{cat}_{situation}",
                        reply_text,
                        f"Golden example: {cat} — {situation}",
                    )
                    logger.info(f"[LEARNING] Saved golden example: {cat}_{situation} ({len(reply_text)} chars)")

            log.after_snapshot = {
                "template": parsed.get("updated_template", current_template),
                "icp_updates": parsed.get("icp_updates"),
                "golden_examples_saved": len(golden_examples),
            }
            log.change_type = change_type
            log.change_summary = parsed.get("change_summary", "Feedback applied")
            log.ai_reasoning = parsed.get("reasoning", "")
            log.status = "completed"

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)[:2000]
            logger.error(f"Feedback processing failed for project {project_id}: {e}", exc_info=True)

        return log

    async def record_correction(
        self,
        session: AsyncSession,
        reply: ProcessedReply,
        ai_draft: Optional[str],
        ai_subject: Optional[str],
        sent_text: Optional[str],
        sent_subject: Optional[str],
        action_type: str = "send",
    ) -> Optional[OperatorCorrection]:
        """Record any operator action — send (edited or not), dismiss, regenerate."""
        was_edited = (
            action_type == "send"
            and (
                (ai_draft or "").strip() != (sent_text or "").strip()
                or (ai_subject or "").strip() != (sent_subject or "").strip()
            )
        )

        # Resolve project_id — try campaign_name match first (most reliable), then contact email
        project_id = None
        campaign_name = getattr(reply, 'campaign_name', None)
        if campaign_name:
            from sqlalchemy import text as sa_text
            proj_result = await session.execute(
                select(Project.id).where(
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
            row = proj_result.first()
            if row:
                project_id = row[0]

        if not project_id and reply.lead_email:
            contact_result = await session.execute(
                select(Contact.project_id).where(
                    func.lower(Contact.email) == reply.lead_email.lower(),
                    Contact.deleted_at.is_(None),
                )
            )
            row = contact_result.first()
            if row and row[0]:
                project_id = row[0]

        correction = OperatorCorrection(
            project_id=project_id,
            processed_reply_id=reply.id,
            ai_draft_reply=ai_draft,
            ai_draft_subject=ai_subject,
            sent_reply=sent_text,
            sent_subject=sent_subject,
            was_edited=was_edited,
            action_type=action_type,
            reply_category=reply.category,
            channel=reply.channel,
            lead_company=reply.lead_company,
        )
        session.add(correction)
        return correction

    # --- Internal methods ---

    async def _fetch_prioritized_conversations(
        self,
        session: AsyncSession,
        project_id: int,
        max_total: int,
        force_all: bool,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Fetch conversations prioritizing qualified leads with channel balance."""
        conversations = await get_project_conversations(session, project_id, max_total)

        stats = {"email": 0, "linkedin": 0, "qualified": 0, "total": len(conversations)}
        for conv in conversations:
            channels = set()
            for msg in conv.get("messages", []):
                channels.add(msg.get("channel", "email"))
            if "linkedin" in channels:
                stats["linkedin"] += 1
            else:
                stats["email"] += 1

        # Count qualified (contacts with sheet_qualification or positive categories)
        qualified_result = await session.execute(
            select(func.count(Contact.id)).where(
                and_(
                    Contact.project_id == project_id,
                    Contact.deleted_at.is_(None),
                    Contact.sheet_qualification.isnot(None),
                )
            )
        )
        stats["qualified"] = qualified_result.scalar() or 0

        return conversations, stats

    async def _get_recent_corrections(
        self, session: AsyncSession, project_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get ALL recent operator actions for analysis — sends, dismissals, regenerations."""
        result = await session.execute(
            select(OperatorCorrection)
            .where(OperatorCorrection.project_id == project_id)
            .order_by(OperatorCorrection.created_at.desc())
            .limit(limit)
        )
        corrections = result.scalars().all()
        return [
            {
                "action": c.action_type,
                "was_edited": c.was_edited,
                "category": c.reply_category,
                "channel": c.channel,
                "ai_draft": (c.ai_draft_reply or "")[:500],
                "sent": (c.sent_reply or "")[:500],
                "company": c.lead_company,
            }
            for c in corrections
        ]

    async def _analyze_and_update(
        self,
        session: AsyncSession,
        project: Project,
        conversations: List[Dict[str, Any]],
        corrections: List[Dict[str, Any]],
        log: LearningLog,
    ):
        """Core analysis: call GPT, update template + ICP, snapshot to log."""
        # Get current template
        current_template = ""
        if project.reply_prompt_template_id:
            tmpl_result = await session.execute(
                select(ReplyPromptTemplateModel).where(
                    ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                )
            )
            tmpl = tmpl_result.scalar_one_or_none()
            if tmpl:
                current_template = tmpl.prompt_text

        # Get current ICP
        icp_result = await session.execute(
            select(ProjectKnowledge).where(
                ProjectKnowledge.project_id == project.id,
                ProjectKnowledge.category == "icp",
            )
        )
        icp_entries = icp_result.scalars().all()
        icp_data = {e.key: e.value for e in icp_entries}

        # Snapshot before
        log.before_snapshot = {
            "template": current_template,
            "icp": icp_data,
        }

        # Build prompt
        formatted_convos = format_conversations_for_prompt(conversations)
        corrections_text = ""
        if corrections:
            parts = []
            for i, c in enumerate(corrections, 1):
                action = c.get("action", "send")
                if action == "dismiss":
                    parts.append(f"--- Action #{i}: DISMISSED ({c['channel']}, {c['category']}) ---")
                    parts.append(f"AI drafted (rejected): {c['ai_draft']}")
                    parts.append("Operator chose NOT to reply — draft was inadequate or reply unnecessary")
                elif action == "regenerate":
                    parts.append(f"--- Action #{i}: REGENERATED ({c['channel']}, {c['category']}) ---")
                    parts.append(f"AI draft (rejected): {c['ai_draft']}")
                    parts.append("Operator found draft unsatisfactory and requested a new one")
                elif c.get("was_edited"):
                    parts.append(f"--- Action #{i}: EDITED before send ({c['channel']}, {c['category']}) ---")
                    parts.append(f"AI drafted: {c['ai_draft']}")
                    parts.append(f"Operator sent instead: {c['sent']}")
                else:
                    parts.append(f"--- Action #{i}: APPROVED as-is ({c['channel']}, {c['category']}) ---")
                    parts.append(f"AI draft (used unchanged): {c['ai_draft']}")
                parts.append("")
            corrections_text = "\n".join(parts)

        user_prompt = f"""Project: {project.name}

CURRENT TEMPLATE:
{current_template or '(no template set)'}

CURRENT ICP KNOWLEDGE:
{json.dumps(icp_data, indent=2) if icp_data else '(none)'}

CONVERSATIONS ({len(conversations)} threads):
{formatted_convos}

OPERATOR ACTIONS ({len(corrections)} signals — edits, approvals, dismissals, regenerations):
{corrections_text or '(none yet)'}

Analyze these patterns and produce an improved template + ICP insights."""

        if not openai_service.is_connected():
            log.status = "failed"
            log.error_message = "OpenAI not configured"
            return

        response = await openai_service.complete(
            prompt=user_prompt,
            system_prompt=LEARNING_SYSTEM_PROMPT,
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        parsed = json.loads(response)

        # Update template (or create if project has none)
        change_type = None
        if parsed.get("updated_template"):
            if project.reply_prompt_template_id:
                await session.execute(
                    update(ReplyPromptTemplateModel)
                    .where(ReplyPromptTemplateModel.id == project.reply_prompt_template_id)
                    .values(
                        prompt_text=parsed["updated_template"],
                        version=ReplyPromptTemplateModel.version + 1,
                        updated_at=datetime.utcnow(),
                    )
                )
                log.template_id = project.reply_prompt_template_id
            else:
                # Create new template and assign to project
                new_tmpl = ReplyPromptTemplateModel(
                    name=f"{project.name} - auto",
                    prompt_text=parsed["updated_template"],
                )
                session.add(new_tmpl)
                await session.flush()
                project.reply_prompt_template_id = new_tmpl.id
                log.template_id = new_tmpl.id
            change_type = "template_updated"

        # Update ICP knowledge
        if parsed.get("icp_insights"):
            for icp_key, icp_val in parsed["icp_insights"].items():
                if icp_val:
                    await self._upsert_knowledge(
                        session, project.id, "icp", icp_key, icp_val, f"ICP: {icp_key}"
                    )
            change_type = "both" if change_type else "icp_updated"

        # Store objection patterns
        if parsed.get("objection_patterns"):
            await self._upsert_knowledge(
                session, project.id, "icp", "objection_patterns",
                parsed["objection_patterns"], "Objection Patterns"
            )

        # Snapshot after
        log.after_snapshot = {
            "template": parsed.get("updated_template", current_template),
            "icp_insights": parsed.get("icp_insights"),
            "objection_patterns": parsed.get("objection_patterns"),
        }
        log.change_type = change_type or "both"
        log.change_summary = parsed.get("change_summary", "Learning cycle completed")
        log.ai_reasoning = parsed.get("reasoning", "")
        log.status = "completed"

        # Send Telegram notification
        try:
            await self._notify_learning_complete(session, project, log)
        except Exception as tg_err:
            logger.warning(f"Telegram notification failed after learning: {tg_err}")

    async def _upsert_knowledge(
        self,
        session: AsyncSession,
        project_id: int,
        category: str,
        key: str,
        value: Any,
        title: str,
    ):
        """Upsert a project knowledge entry with source=learning."""
        from sqlalchemy import text as sql_text

        stmt = pg_insert(ProjectKnowledge).values(
            project_id=project_id,
            category=category,
            key=key,
            title=title,
            value=value,
            source="learning",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "category", "key"],
            set_={
                "value": stmt.excluded.value,
                "title": stmt.excluded.title,
                "source": stmt.excluded.source,
                "updated_at": sql_text("now()"),
            },
        )
        await session.execute(stmt)

    async def _notify_learning_complete(
        self, session: AsyncSession, project: Project, log: LearningLog
    ):
        """Send Telegram notification to project subscribers about learning completion."""
        from app.models.reply import TelegramSubscription
        from app.services.notification_service import send_telegram_notification

        subs_result = await session.execute(
            select(TelegramSubscription.chat_id).where(
                TelegramSubscription.project_id == project.id
            )
        )
        chat_ids = [r[0] for r in subs_result.all()]
        if not chat_ids:
            return

        msg = (
            f"<b>Learning complete</b> — {project.name}\n"
            f"Analyzed: {log.conversations_analyzed or 0} conversations\n"
            f"Changes: {log.change_summary or 'none'}\n"
            f"Trigger: {log.trigger}"
        )
        for chat_id in chat_ids:
            await send_telegram_notification(msg, chat_id=chat_id)


learning_service = LearningService()
