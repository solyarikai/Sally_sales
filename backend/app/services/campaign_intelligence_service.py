"""
Campaign Intelligence Service — GOD_SEQUENCE.

Learns from top-performing campaigns, extracts reusable patterns,
and generates optimized sequences for new campaigns.

Four stages:
1. score_campaigns() — DB-only, computes quality scores
2. create_snapshots() — freezes metrics + fetches sequences from SmartLead
3. extract_patterns() — AI analyzes top snapshots, writes campaign_patterns
4. generate_sequence() — AI combines patterns + project ICP → new sequence
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, case, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.campaign_intelligence import (
    CampaignSnapshot, CampaignPattern, CampaignIntelligenceRun, GeneratedSequence,
)
from app.models.reply import ProcessedReply, ReplyCategory
from app.models.contact import Project
from app.models.project_knowledge import ProjectKnowledge

logger = logging.getLogger(__name__)

# Scoring weights
WARM_WEIGHT = 0.6
MEETING_WEIGHT = 0.25
QUESTION_WEIGHT = 0.15
DEFAULT_MIN_LEADS = 50

# Market detection from campaign name patterns
MARKET_PATTERNS = {
    "ru": ["russian", "ru ", " ru", "рус", "dms", "dm "],
    "ar": ["arabic", " ar ", "saudi", "sa "],
    "en": [],  # default
}

PATTERN_TYPES = [
    "subject_line", "body_structure", "timing", "personalization",
    "cta", "tone", "proof_point", "opener", "objection_preempt", "sequence_flow",
]


def _detect_market(campaign_name: str) -> str:
    """Detect market from campaign name."""
    name_lower = campaign_name.lower()
    for market, keywords in MARKET_PATTERNS.items():
        if any(kw in name_lower for kw in keywords):
            return market
    return "en"


def _compute_quality_score(warm_rate: float, meeting_rate: float, question_rate: float) -> float:
    return (warm_rate * WARM_WEIGHT) + (meeting_rate * MEETING_WEIGHT) + (question_rate * QUESTION_WEIGHT)


async def score_campaigns(
    session: AsyncSession,
    company_id: int,
    min_leads: int = DEFAULT_MIN_LEADS,
    project_id: Optional[int] = None,
    market: Optional[str] = None,
) -> list[dict]:
    """
    Score all campaigns by reply performance. Pure DB queries, no external API calls.

    Returns list of dicts sorted by quality_score desc.
    """
    # Build campaign filter
    campaign_filter = [Campaign.company_id == company_id, Campaign.leads_count > 0]
    if project_id:
        campaign_filter.append(Campaign.project_id == project_id)

    # Get all campaigns with leads
    campaigns_result = await session.execute(
        select(
            Campaign.id, Campaign.name, Campaign.platform, Campaign.channel,
            Campaign.project_id, Campaign.leads_count, Campaign.external_id,
        ).where(*campaign_filter)
    )
    campaigns = campaigns_result.all()
    if not campaigns:
        return []

    campaign_ids_by_name = {c.name: c for c in campaigns}
    campaign_names = list(campaign_ids_by_name.keys())

    # Count replies by category per campaign
    reply_counts = await session.execute(
        select(
            ProcessedReply.campaign_name,
            func.count().label("total"),
            func.sum(case(
                (ProcessedReply.category.in_(["interested", "meeting_request"]), 1),
                else_=0,
            )).label("warm"),
            func.sum(case(
                (ProcessedReply.category == "meeting_request", 1),
                else_=0,
            )).label("meetings"),
            func.sum(case(
                (ProcessedReply.category == "question", 1),
                else_=0,
            )).label("questions"),
            func.sum(case(
                (ProcessedReply.category == "not_interested", 1),
                else_=0,
            )).label("not_interested"),
            func.sum(case(
                (ProcessedReply.category == "out_of_office", 1),
                else_=0,
            )).label("ooo"),
            func.sum(case(
                (ProcessedReply.category == "wrong_person", 1),
                else_=0,
            )).label("wrong_person"),
        ).where(
            ProcessedReply.campaign_name.in_(campaign_names),
        ).group_by(ProcessedReply.campaign_name)
    )
    reply_stats = {row.campaign_name: row for row in reply_counts.all()}

    # Build scored list
    scored = []
    for c in campaigns:
        stats = reply_stats.get(c.name)
        leads = c.leads_count or 1
        detected_market = _detect_market(c.name)

        if market and detected_market != market:
            continue

        warm = int(stats.warm or 0) if stats else 0
        meetings = int(stats.meetings or 0) if stats else 0
        questions = int(stats.questions or 0) if stats else 0
        total_replies = int(stats.total or 0) if stats else 0
        not_interested = int(stats.not_interested or 0) if stats else 0
        ooo = int(stats.ooo or 0) if stats else 0
        wrong_person = int(stats.wrong_person or 0) if stats else 0

        warm_rate = warm / leads
        meeting_rate = meetings / leads
        question_rate = questions / leads
        quality = _compute_quality_score(warm_rate, meeting_rate, question_rate)

        scored.append({
            "campaign_id": c.id,
            "campaign_name": c.name,
            "platform": c.platform,
            "channel": c.channel,
            "project_id": c.project_id,
            "external_id": c.external_id,
            "leads_count": leads,
            "total_replies": total_replies,
            "warm_replies": warm,
            "meetings_count": meetings,
            "questions_count": questions,
            "not_interested_count": not_interested,
            "ooo_count": ooo,
            "wrong_person_count": wrong_person,
            "warm_reply_rate": round(warm_rate, 4),
            "meeting_rate": round(meeting_rate, 4),
            "quality_score": round(quality, 4),
            "market": detected_market,
            "min_sample_size_met": leads >= min_leads,
        })

    scored.sort(key=lambda x: x["quality_score"], reverse=True)
    return scored


async def create_snapshots(
    session: AsyncSession,
    company_id: int,
    campaign_scores: list[dict],
    force: bool = False,
) -> list[CampaignSnapshot]:
    """
    Create snapshots for scored campaigns. Fetches sequences from SmartLead.

    Only creates new snapshots if:
    - No snapshot exists yet, OR
    - Existing latest snapshot is older than 7 days, OR
    - force=True
    """
    if not campaign_scores:
        return []

    # Check existing latest snapshots
    campaign_ids = [s["campaign_id"] for s in campaign_scores]
    existing = await session.execute(
        select(CampaignSnapshot.campaign_id, CampaignSnapshot.snapshotted_at, CampaignSnapshot.snapshot_version)
        .where(
            CampaignSnapshot.campaign_id.in_(campaign_ids),
            CampaignSnapshot.is_latest == True,
        )
    )
    existing_map = {row.campaign_id: row for row in existing.all()}

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Fetch sequences for SmartLead campaigns
    smartlead_sequences = {}
    smartlead_campaigns = [s for s in campaign_scores if s["platform"] == "smartlead" and s.get("external_id")]
    if smartlead_campaigns:
        try:
            from app.services.crm_sync_service import get_crm_sync_service
            sync_service = get_crm_sync_service()
            if sync_service.smartlead:
                for sc in smartlead_campaigns:
                    try:
                        seqs = await sync_service.smartlead.get_campaign_sequences(sc["external_id"])
                        smartlead_sequences[sc["campaign_id"]] = seqs
                    except Exception as e:
                        logger.warning(f"Failed to fetch sequences for campaign {sc['campaign_name']}: {e}")
        except Exception as e:
            logger.error(f"Failed to get SmartLead service: {e}")

    created = []
    for score in campaign_scores:
        cid = score["campaign_id"]
        ex = existing_map.get(cid)

        # Skip if recent snapshot exists and not forced
        if ex and not force:
            if ex.snapshotted_at and ex.snapshotted_at.replace(tzinfo=timezone.utc) > seven_days_ago:
                continue

        # Mark old snapshot as not latest
        if ex:
            await session.execute(
                update(CampaignSnapshot)
                .where(CampaignSnapshot.campaign_id == cid, CampaignSnapshot.is_latest == True)
                .values(is_latest=False)
            )

        # Build sequence data
        seq_steps = smartlead_sequences.get(cid)
        seq_step_count = len(seq_steps) if seq_steps else None
        seq_total_days = None
        if seq_steps:
            try:
                delays = [s.get("seq_delay_details", {}).get("delay_in_days", 0) for s in seq_steps]
                seq_total_days = sum(delays)
            except (TypeError, AttributeError):
                pass

        new_version = (ex.snapshot_version + 1) if ex else 1

        snapshot = CampaignSnapshot(
            campaign_id=cid,
            project_id=score.get("project_id"),
            company_id=company_id,
            leads_count=score["leads_count"],
            total_replies=score["total_replies"],
            warm_replies=score["warm_replies"],
            meetings_count=score["meetings_count"],
            questions_count=score["questions_count"],
            not_interested_count=score["not_interested_count"],
            ooo_count=score["ooo_count"],
            wrong_person_count=score["wrong_person_count"],
            warm_reply_rate=score["warm_reply_rate"],
            meeting_rate=score["meeting_rate"],
            quality_score=score["quality_score"],
            campaign_name=score["campaign_name"],
            platform=score["platform"],
            channel=score["channel"],
            market=score["market"],
            sequence_steps=seq_steps,
            sequence_step_count=seq_step_count,
            sequence_total_days=seq_total_days,
            snapshot_version=new_version,
            is_latest=True,
            min_sample_size_met=score["min_sample_size_met"],
        )
        session.add(snapshot)
        created.append(snapshot)

    if created:
        await session.commit()
        logger.info(f"Created {len(created)} campaign snapshots")

    return created


async def extract_patterns(
    session: AsyncSession,
    company_id: int,
    market: Optional[str] = None,
    trigger: str = "scheduled",
    min_leads: int = DEFAULT_MIN_LEADS,
    top_n: int = 20,
) -> CampaignIntelligenceRun:
    """
    AI analyzes top-performing campaign snapshots and extracts reusable patterns.

    Selects top N snapshots by quality_score, sends to Gemini 2.5 Pro,
    upserts patterns into campaign_patterns table.
    """
    run = CampaignIntelligenceRun(
        company_id=company_id,
        trigger=trigger,
        market_filter=market,
        min_sample_size=min_leads,
        status="processing",
    )
    session.add(run)
    await session.flush()

    try:
        # Select top snapshots
        snapshot_filter = [
            CampaignSnapshot.company_id == company_id,
            CampaignSnapshot.is_latest == True,
            CampaignSnapshot.min_sample_size_met == True,
        ]
        if market:
            snapshot_filter.append(CampaignSnapshot.market == market)

        top_snapshots = (await session.execute(
            select(CampaignSnapshot)
            .where(*snapshot_filter)
            .order_by(desc(CampaignSnapshot.quality_score))
            .limit(top_n)
        )).scalars().all()

        if len(top_snapshots) < 3:
            run.status = "failed"
            run.error_message = f"Not enough campaigns with data (found {len(top_snapshots)}, need at least 3)"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            return run

        run.campaigns_analyzed = len(top_snapshots)
        run.top_campaigns_count = len(top_snapshots)
        run.snapshots_used = [s.id for s in top_snapshots]

        # Build AI prompt
        system_prompt = _build_extraction_system_prompt()
        user_prompt = _build_extraction_user_prompt(top_snapshots)
        prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()[:16]

        # Call Gemini
        from app.services.gemini_client import gemini_generate
        result = await gemini_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=8000,
            model="gemini-2.5-pro-preview-06-05",
        )

        run.model_used = result.get("model", "gemini-2.5-pro")
        run.tokens_used = result.get("tokens", {}).get("total", 0)
        run.prompt_hash = prompt_hash

        # Estimate cost (Gemini 2.5 Pro pricing)
        input_tokens = result.get("tokens", {}).get("input", 0)
        output_tokens = result.get("tokens", {}).get("output", 0)
        run.cost_usd = (input_tokens * 1.25 / 1_000_000) + (output_tokens * 10.0 / 1_000_000)

        # Parse AI response
        content = result.get("content", "")
        run.ai_reasoning = content
        patterns_data = _parse_patterns_response(content)

        if not patterns_data:
            run.status = "failed"
            run.error_message = "AI returned no parseable patterns"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            return run

        # Upsert patterns
        created_count = 0
        updated_count = 0
        snapshot_ids = [s.id for s in top_snapshots]

        for p in patterns_data:
            p_type = p.get("pattern_type", "")
            p_key = p.get("pattern_key", "")
            if p_type not in PATTERN_TYPES or not p_key:
                continue

            p_market = p.get("market") or market

            # Check if pattern exists
            existing_pattern = (await session.execute(
                select(CampaignPattern).where(
                    CampaignPattern.company_id == company_id,
                    CampaignPattern.pattern_type == p_type,
                    CampaignPattern.pattern_key == p_key,
                    CampaignPattern.market == p_market,
                    CampaignPattern.is_active == True,
                )
            )).scalar_one_or_none()

            if existing_pattern:
                # Version: deactivate old, create new
                existing_pattern.is_active = False
                new_pattern = CampaignPattern(
                    company_id=company_id,
                    pattern_type=p_type,
                    pattern_key=p_key,
                    title=p.get("title", p_key),
                    description=p.get("description", ""),
                    market=p_market,
                    channel=p.get("channel"),
                    confidence=p.get("confidence", 0.5),
                    evidence_campaign_ids=snapshot_ids,
                    evidence_summary=p.get("evidence_summary"),
                    sample_size=len(top_snapshots),
                    version=existing_pattern.version + 1,
                    supersedes_id=existing_pattern.id,
                    is_active=True,
                    extraction_run_id=run.id,
                )
                session.add(new_pattern)
                updated_count += 1
            else:
                new_pattern = CampaignPattern(
                    company_id=company_id,
                    pattern_type=p_type,
                    pattern_key=p_key,
                    title=p.get("title", p_key),
                    description=p.get("description", ""),
                    market=p_market,
                    channel=p.get("channel"),
                    confidence=p.get("confidence", 0.5),
                    evidence_campaign_ids=snapshot_ids,
                    evidence_summary=p.get("evidence_summary"),
                    sample_size=len(top_snapshots),
                    version=1,
                    is_active=True,
                    extraction_run_id=run.id,
                )
                session.add(new_pattern)
                created_count += 1

        run.patterns_created = created_count
        run.patterns_updated = updated_count
        run.patterns_total = created_count + updated_count
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()

        logger.info(
            f"[GOD_SEQUENCE] Extraction complete: {created_count} created, "
            f"{updated_count} updated from {len(top_snapshots)} campaigns"
        )
        return run

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)[:2000]
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        logger.error(f"[GOD_SEQUENCE] Extraction failed: {e}")
        return run


async def generate_sequence(
    session: AsyncSession,
    project_id: int,
    company_id: int,
    campaign_name: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    step_count: int = 5,
) -> GeneratedSequence:
    """
    Generate an optimized campaign sequence by combining learned patterns
    with project-specific ICP and business context.
    """
    # Load project
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # Detect market from project campaigns
    detected_market = "en"
    if project.campaign_filters:
        for cf in project.campaign_filters[:3]:
            detected_market = _detect_market(cf)
            if detected_market != "en":
                break

    # Load active patterns (market-specific + universal)
    patterns_result = await session.execute(
        select(CampaignPattern).where(
            CampaignPattern.company_id == company_id,
            CampaignPattern.is_active == True,
            CampaignPattern.market.in_([detected_market, None]),
        ).order_by(desc(CampaignPattern.confidence))
    )
    patterns = patterns_result.scalars().all()

    # Load project knowledge
    knowledge_result = await session.execute(
        select(ProjectKnowledge).where(
            ProjectKnowledge.project_id == project_id,
            ProjectKnowledge.category.in_(["icp", "outreach", "gtm"]),
        )
    )
    knowledge_items = knowledge_result.scalars().all()

    # Load a top-performing sequence as structural reference
    ref_snapshot = (await session.execute(
        select(CampaignSnapshot).where(
            CampaignSnapshot.company_id == company_id,
            CampaignSnapshot.is_latest == True,
            CampaignSnapshot.min_sample_size_met == True,
            CampaignSnapshot.sequence_steps.isnot(None),
            CampaignSnapshot.market == detected_market,
        ).order_by(desc(CampaignSnapshot.quality_score)).limit(1)
    )).scalar_one_or_none()

    # Build prompt
    system_prompt = _build_generation_system_prompt(step_count)
    user_prompt = _build_generation_user_prompt(
        project=project,
        patterns=patterns,
        knowledge_items=knowledge_items,
        ref_snapshot=ref_snapshot,
        campaign_name=campaign_name,
        custom_instructions=custom_instructions,
        step_count=step_count,
    )

    # Call Gemini
    from app.services.gemini_client import gemini_generate
    result = await gemini_generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
        max_tokens=8000,
        model="gemini-2.5-pro-preview-06-05",
    )

    content = result.get("content", "")
    sequence_steps = _parse_sequence_response(content)

    if not sequence_steps:
        raise ValueError("AI failed to generate valid sequence steps")

    # Build knowledge snapshot for audit
    knowledge_snapshot = {
        "project_name": project.name,
        "target_segments": project.target_segments,
        "target_industries": project.target_industries,
        "sender_name": project.sender_name,
        "sender_position": project.sender_position,
        "sender_company": project.sender_company,
        "knowledge_keys": [{"category": k.category, "key": k.key, "title": k.title} for k in knowledge_items],
    }

    tokens = result.get("tokens", {})
    input_tokens = tokens.get("input", 0)
    output_tokens = tokens.get("output", 0)

    gen = GeneratedSequence(
        project_id=project_id,
        company_id=company_id,
        generation_prompt=user_prompt[:5000],
        patterns_used=[p.id for p in patterns],
        project_knowledge_snapshot=knowledge_snapshot,
        campaign_name=campaign_name or f"{project.name} - Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        sequence_steps=sequence_steps,
        sequence_step_count=len(sequence_steps),
        rationale=content,
        status="draft",
        model_used=result.get("model", "gemini-2.5-pro"),
        tokens_used=tokens.get("total", 0),
        cost_usd=(input_tokens * 1.25 / 1_000_000) + (output_tokens * 10.0 / 1_000_000),
    )
    session.add(gen)
    await session.commit()
    await session.refresh(gen)

    logger.info(f"[GOD_SEQUENCE] Generated {len(sequence_steps)}-step sequence for project {project.name}")
    return gen


async def push_sequence_to_smartlead(
    session: AsyncSession,
    generated_id: int,
) -> dict:
    """
    Push an approved generated sequence to SmartLead as a new DRAFT campaign.

    Does NOT add leads or activate — operator does that manually.
    """
    gen = await session.get(GeneratedSequence, generated_id)
    if not gen:
        raise ValueError(f"Generated sequence {generated_id} not found")
    if gen.status != "approved":
        raise ValueError(f"Sequence must be approved before pushing (current: {gen.status})")

    from app.services.crm_sync_service import get_crm_sync_service
    sync_service = get_crm_sync_service()
    if not sync_service.smartlead:
        raise RuntimeError("SmartLead service not available")

    # Create campaign
    campaign_result = await sync_service.smartlead.create_campaign(gen.campaign_name)
    campaign_id = campaign_result["id"]

    # Format sequences for SmartLead API
    sl_sequences = []
    for step in gen.sequence_steps:
        sl_sequences.append({
            "seq_number": step.get("seq_number", step.get("step", 1)),
            "seq_delay_details": {"delay_in_days": step.get("delay_days", 0)},
            "subject": step.get("subject", ""),
            "email_body": step.get("body", step.get("email_body", "")),
        })

    success = await sync_service.smartlead.set_campaign_sequences(campaign_id, sl_sequences)
    if not success:
        raise RuntimeError(f"Failed to set sequences on SmartLead campaign {campaign_id}")

    # Register campaign in DB
    db_campaign = Campaign(
        company_id=gen.company_id,
        project_id=gen.project_id,
        platform="smartlead",
        channel="email",
        external_id=str(campaign_id),
        name=gen.campaign_name,
        status="paused",
        resolution_method="god_sequence",
        resolution_detail=f"Generated by GOD_SEQUENCE (gen_id={gen.id})",
    )
    session.add(db_campaign)
    await session.flush()

    # Update generated sequence
    gen.status = "pushed"
    gen.pushed_campaign_id = db_campaign.id
    gen.pushed_at = datetime.now(timezone.utc)
    await session.commit()

    logger.info(f"[GOD_SEQUENCE] Pushed campaign '{gen.campaign_name}' to SmartLead (ID: {campaign_id})")
    return {
        "smartlead_campaign_id": campaign_id,
        "db_campaign_id": db_campaign.id,
        "campaign_name": gen.campaign_name,
        "steps": len(sl_sequences),
    }


# ===== Prompt builders =====

def _build_extraction_system_prompt() -> str:
    return """You are a cold outreach expert analyzing top-performing email campaigns.

Your task: examine the campaign sequences provided and extract REUSABLE PATTERNS that explain
why these campaigns outperform others. Focus on what is generalizable, not campaign-specific.

Return a JSON array of pattern objects. Each pattern:
```json
{
  "pattern_type": "subject_line|body_structure|timing|personalization|cta|tone|proof_point|opener|objection_preempt|sequence_flow",
  "pattern_key": "unique_slug_for_this_pattern",
  "title": "Human-readable pattern name",
  "description": "Detailed description of the pattern — what it is, how to apply it, with examples from the campaigns",
  "market": "en|ru|ar|null",
  "channel": "email|linkedin|null",
  "confidence": 0.0-1.0,
  "evidence_summary": "Which campaigns demonstrate this pattern and how"
}
```

Rules:
- Extract 10-20 patterns per analysis
- Each pattern must be actionable — someone should be able to apply it to write a new sequence
- Include specific examples from the campaign text where relevant
- Confidence should reflect how consistently the pattern appears across top campaigns
- Market should be null if the pattern applies universally
- Focus on WHAT MAKES THESE CAMPAIGNS DIFFERENT from average cold outreach

Return ONLY the JSON array, no other text."""


def _build_extraction_user_prompt(snapshots: list[CampaignSnapshot]) -> str:
    lines = ["Here are the top-performing campaigns ranked by quality score:\n"]
    for i, s in enumerate(snapshots, 1):
        lines.append(f"## Campaign #{i}: {s.campaign_name}")
        lines.append(f"Market: {s.market} | Leads: {s.leads_count} | Warm replies: {s.warm_replies} "
                     f"| Meetings: {s.meetings_count} | Quality score: {s.quality_score:.4f}")
        lines.append(f"Warm reply rate: {s.warm_reply_rate:.2%} | Meeting rate: {s.meeting_rate:.2%}")

        if s.sequence_steps:
            lines.append(f"\nSequence ({s.sequence_step_count} steps, {s.sequence_total_days} days total):")
            for step in s.sequence_steps:
                step_num = step.get("seq_number", "?")
                delay = step.get("seq_delay_details", {}).get("delay_in_days", 0)
                subject = step.get("subject", "(thread reply)")
                body = step.get("email_body", "")
                # Truncate long bodies
                if len(body) > 800:
                    body = body[:800] + "..."
                lines.append(f"\n  Step {step_num} (day +{delay}):")
                if subject:
                    lines.append(f"  Subject: {subject}")
                lines.append(f"  Body: {body}")
        else:
            lines.append("  (sequence content not available)")

        lines.append("")

    return "\n".join(lines)


def _build_generation_system_prompt(step_count: int) -> str:
    return f"""You are a cold outreach expert generating a {step_count}-step email sequence for SmartLead.

You will receive:
1. PROVEN PATTERNS from top-performing campaigns — apply these
2. BUSINESS CONTEXT — the specific company, product, ICP
3. REFERENCE SEQUENCE — a top-performing sequence structure to follow

Generate a {step_count}-step email sequence as a JSON array:
```json
[
  {{
    "seq_number": 1,
    "delay_days": 0,
    "subject": "Subject line for step 1",
    "body": "HTML email body"
  }},
  ...
]
```

Rules:
- Step 1 MUST have a subject line. Steps 2+ MUST have empty subject "" (they thread as replies)
- Use SmartLead variables: {{{{first_name}}}}, {{{{company_name}}}}, {{{{city}}}}, {{{{Sender Name}}}}
- HTML format: use <br> for line breaks, <br><br> for paragraphs
- Typical timing: Day 0 → Day 3 → Day 4-5 → Day 7 → Day 7-10
- Apply the proven patterns but adapt them to this specific business
- Include a signature block in step 1 with sender name, position, company
- Keep emails concise — 4-6 short paragraphs max per step
- Each step should add NEW value, not just "following up"

Return ONLY the JSON array, no other text."""


def _build_generation_user_prompt(
    project: Project,
    patterns: list[CampaignPattern],
    knowledge_items: list[ProjectKnowledge],
    ref_snapshot: Optional[CampaignSnapshot],
    campaign_name: Optional[str],
    custom_instructions: Optional[str],
    step_count: int,
) -> str:
    lines = []

    # Section 1: Patterns
    lines.append("## PROVEN PATTERNS FROM TOP CAMPAIGNS\n")
    if patterns:
        for p in patterns[:15]:  # Limit to avoid token bloat
            lines.append(f"**[{p.pattern_type}] {p.title}** (confidence: {p.confidence:.0%})")
            lines.append(f"{p.description}\n")
    else:
        lines.append("No patterns extracted yet. Use general cold outreach best practices.\n")

    # Section 2: Business context
    lines.append("## BUSINESS CONTEXT\n")
    lines.append(f"Company: {project.sender_company or project.name}")
    if project.sender_name:
        lines.append(f"Sender: {project.sender_name}, {project.sender_position or 'BDM'}")
    if project.target_segments:
        lines.append(f"Target Segments: {project.target_segments}")
    if project.target_industries:
        lines.append(f"Target Industries: {project.target_industries}")

    for ki in knowledge_items:
        value = ki.value if isinstance(ki.value, str) else json.dumps(ki.value, default=str)
        if len(value) > 500:
            value = value[:500] + "..."
        lines.append(f"\n[{ki.category}] {ki.title or ki.key}: {value}")

    # Section 3: Reference sequence
    if ref_snapshot and ref_snapshot.sequence_steps:
        lines.append(f"\n## REFERENCE SEQUENCE (top performer: {ref_snapshot.campaign_name})")
        lines.append(f"Quality score: {ref_snapshot.quality_score:.4f} | "
                     f"Warm rate: {ref_snapshot.warm_reply_rate:.2%} | "
                     f"Meeting rate: {ref_snapshot.meeting_rate:.2%}")
        for step in ref_snapshot.sequence_steps:
            step_num = step.get("seq_number", "?")
            delay = step.get("seq_delay_details", {}).get("delay_in_days", 0)
            lines.append(f"\n  Step {step_num} (day +{delay}): {step.get('email_body', '')[:400]}")

    # Section 4: Custom instructions
    if campaign_name:
        lines.append(f"\n## CAMPAIGN NAME: {campaign_name}")
    if custom_instructions:
        lines.append(f"\n## CUSTOM INSTRUCTIONS\n{custom_instructions}")

    return "\n".join(lines)


# ===== Response parsers =====

def _parse_patterns_response(content: str) -> list[dict]:
    """Parse AI response into pattern dicts."""
    return _extract_json_array(content)


def _parse_sequence_response(content: str) -> list[dict]:
    """Parse AI response into sequence step dicts."""
    return _extract_json_array(content)


def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from text that may contain markdown fences."""
    import re
    # Try to find JSON array in markdown code block
    match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON array
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return []


# ===== Scheduler entry point =====

async def run_campaign_intelligence_cycle(company_id: int = 1, force: bool = False):
    """
    Full intelligence cycle: score → snapshot → (weekly) extract.

    Called by CRMScheduler daily.
    """
    from app.db import async_session_maker

    async with async_session_maker() as session:
        # Step 1: Score
        scores = await score_campaigns(session, company_id)
        if not scores:
            logger.info("[GOD_SEQUENCE] No campaigns to score")
            return

        logger.info(f"[GOD_SEQUENCE] Scored {len(scores)} campaigns, "
                    f"top: {scores[0]['campaign_name']} ({scores[0]['quality_score']:.4f})")

        # Step 2: Snapshot
        snapshots = await create_snapshots(session, company_id, scores, force=force)

        # Step 3: Extract (only if new snapshots were created)
        if snapshots or force:
            # Check if last extraction was > 7 days ago
            last_run = (await session.execute(
                select(CampaignIntelligenceRun.completed_at)
                .where(
                    CampaignIntelligenceRun.company_id == company_id,
                    CampaignIntelligenceRun.status == "completed",
                )
                .order_by(desc(CampaignIntelligenceRun.completed_at))
                .limit(1)
            )).scalar_one_or_none()

            should_extract = force or last_run is None
            if last_run and not force:
                last_run_utc = last_run.replace(tzinfo=timezone.utc) if last_run.tzinfo is None else last_run
                should_extract = (datetime.now(timezone.utc) - last_run_utc).days >= 7

            if should_extract:
                await extract_patterns(session, company_id, trigger="scheduled" if not force else "manual")
            else:
                logger.info("[GOD_SEQUENCE] Skipping extraction (last run < 7 days ago)")
        else:
            logger.info("[GOD_SEQUENCE] No new snapshots, skipping extraction")
