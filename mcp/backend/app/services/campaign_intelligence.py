"""Campaign Intelligence Service — GOD_SEQUENCE pattern extraction + sequence generation.

Adapted for MCP: per-user API keys, no scheduler deps.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.campaign import (
    CampaignSnapshot, CampaignPattern, CampaignIntelligenceRun,
    GeneratedSequence, Campaign,
)
from app.models.project import Project

logger = logging.getLogger(__name__)

# Default timing pattern from top campaigns
DEFAULT_TIMING = [0, 3, 4, 7, 7]  # Days: send, follow-up 1, 2, 3, 4


class CampaignIntelligenceService:
    """GOD_SEQUENCE: learn from campaigns, extract patterns, generate sequences."""

    def __init__(self, gemini_key: Optional[str] = None, openai_key: Optional[str] = None):
        self._gemini_key = gemini_key
        self._openai_key = openai_key

    async def score_campaigns(self, session: AsyncSession, company_id: int,
                               project_id: Optional[int] = None) -> List[Dict]:
        """Score and rank campaigns by quality metrics."""
        query = select(CampaignSnapshot).where(
            CampaignSnapshot.company_id == company_id,
            CampaignSnapshot.is_latest == True,
        )
        if project_id:
            query = query.where(CampaignSnapshot.project_id == project_id)
        query = query.order_by(desc(CampaignSnapshot.quality_score))

        result = await session.execute(query)
        snapshots = result.scalars().all()

        return [
            {
                "campaign_id": s.campaign_id,
                "name": s.campaign_name,
                "quality_score": s.quality_score,
                "warm_reply_rate": s.warm_reply_rate,
                "meeting_rate": s.meeting_rate,
                "leads_count": s.leads_count,
                "market": s.market,
            }
            for s in snapshots
        ]

    async def get_patterns(self, session: AsyncSession, company_id: int,
                            scope_level: Optional[str] = None,
                            market: Optional[str] = None) -> List[Dict]:
        """Get active patterns for sequence generation."""
        query = select(CampaignPattern).where(
            CampaignPattern.company_id == company_id,
            CampaignPattern.is_active == True,
        )
        if scope_level:
            query = query.where(CampaignPattern.scope_level == scope_level)
        if market:
            query = query.where(
                (CampaignPattern.market == market) | (CampaignPattern.market == None)
            )

        result = await session.execute(query)
        patterns = result.scalars().all()

        return [
            {
                "id": p.id,
                "scope_level": p.scope_level,
                "pattern_type": p.pattern_type,
                "title": p.title,
                "description": p.description,
                "confidence": p.confidence,
                "market": p.market,
            }
            for p in patterns
        ]

    async def generate_sequence(
        self,
        session: AsyncSession,
        project_id: int,
        campaign_name: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> GeneratedSequence:
        """Generate a 5-step email sequence using patterns + project knowledge."""
        project = await session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Assemble context from patterns (3-level knowledge)
        patterns = await self.get_patterns(session, project.company_id)

        # Build generation prompt
        context_parts = []
        if project.target_segments:
            context_parts.append(f"ICP: {project.target_segments}")
        if project.target_industries:
            context_parts.append(f"Industries: {project.target_industries}")
        if project.sender_name:
            context_parts.append(f"Sender: {project.sender_name}")
        if project.sender_company:
            context_parts.append(f"Company: {project.sender_company}")

        for p in patterns[:10]:
            context_parts.append(f"[{p['scope_level']}:{p['pattern_type']}] {p['title']}: {p['description'][:200]}")

        if instructions:
            context_parts.append(f"Additional instructions: {instructions}")

        generation_prompt = "\n".join(context_parts)
        name = campaign_name or f"{project.name} - Generated"

        # Generate sequence with AI (GPT-4o-mini) or fall back to template
        steps = await self._generate_steps_ai(project, generation_prompt, instructions)
        if not steps:
            steps = self._generate_steps_template(project)

        # Normalize subject lines — clean names, no special chars
        steps = self._normalize_subjects(steps)

        model = "gpt-4o-mini" if isinstance(steps, list) and len(steps) > 0 and "AI-generated" in str(steps[0].get("body", "")[:1]) == False else "template_v1"

        seq = GeneratedSequence(
            project_id=project_id,
            company_id=project.company_id,
            campaign_name=name,
            generation_prompt=generation_prompt,
            patterns_used=[p["id"] for p in patterns[:10]],
            sequence_steps=steps,
            sequence_step_count=len(steps),
            rationale="Generated using project ICP + GPT-4o-mini. Timing: Day 0/3/4/7/7.",
            status="draft",
            model_used="gpt-4o-mini",
        )
        session.add(seq)
        await session.flush()

        return seq

    async def _generate_steps_ai(self, project, context: str, instructions: Optional[str] = None) -> Optional[list]:
        """Generate sequence steps with GPT-4o-mini."""
        try:
            from app.config import settings
            openai_key = self._openai_key or settings.OPENAI_API_KEY
            if not openai_key:
                return None

            import httpx, json

            sender = project.sender_name or "Team"
            company = project.sender_company or "our company"

            prompt = f"""Generate a 5-step cold email sequence for B2B outreach.

Context:
{context}
{f'Instructions: {instructions}' if instructions else ''}

Sender: {sender} from {company}

Requirements:
- 5 steps on days 0, 3, 4, 7, 7
- Use {{{{first_name}}}} and {{{{company}}}} as merge tags (double curly braces)
- Step 1: opening email, short, personal
- Step 2: follow-up, add value
- Step 3: different angle or social proof
- Step 4: brief, respect their time
- Step 5: breakup email, last chance
- Each subject must be under 60 chars, human-readable, no asterisks or special chars
- Sign off as {sender}

Return ONLY a JSON array of 5 objects: {{"step": N, "day": N, "subject": "...", "body": "..."}}"""

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "messages": [
                        {"role": "system", "content": "You write cold email sequences. Return ONLY valid JSON array."},
                        {"role": "user", "content": prompt},
                    ], "max_tokens": 2000, "temperature": 0.7},
                )
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Parse JSON
                clean = content.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                steps = json.loads(clean)
                if isinstance(steps, list) and len(steps) >= 3:
                    return steps
        except Exception as e:
            logger.error(f"AI sequence generation failed: {e}")
        return None

    def _normalize_subjects(self, steps: list) -> list:
        """Clean subject lines — strip special chars, asterisks, excess punctuation."""
        import re
        for step in steps:
            subj = step.get("subject", "")
            if not subj:
                continue
            # Remove asterisks, backticks, brackets used for emphasis
            subj = re.sub(r'[*`\[\]]', '', subj)
            # Collapse multiple spaces
            subj = re.sub(r'\s{2,}', ' ', subj)
            # Remove leading/trailing punctuation (except ?)
            subj = subj.strip(' -–—:;,.')
            step["subject"] = subj
        return steps

    def _generate_steps_template(self, project) -> list:
        """Fallback template sequence."""
        sender = project.sender_name or "Team"
        company = project.sender_company or "our company"
        return [
            {"step": 1, "day": 0, "subject": "Quick question about {{company}}", "body": f"Hi {{{{first_name}}}},\n\nI noticed {{{{company}}}} is expanding — we help companies like yours with {company}.\n\nWould it make sense to chat for 15 min this week?\n\nBest,\n{sender}"},
            {"step": 2, "day": 3, "subject": "Re: Quick question about {{company}}", "body": f"Hi {{{{first_name}}}},\n\nJust following up. Companies similar to {{{{company}}}} typically see results within the first month.\n\nHappy to share specifics — does Thursday or Friday work?\n\nBest,\n{sender}"},
            {"step": 3, "day": 4, "subject": "{{company}} + " + company, "body": f"Hi {{{{first_name}}}},\n\nOne more thought — I put together a quick overview of how {company} could help {{{{company}}}} specifically.\n\nWorth a look?\n\nBest,\n{sender}"},
            {"step": 4, "day": 7, "subject": "One more thought for {{company}}", "body": f"Hi {{{{first_name}}}},\n\nI know you're busy. We've helped companies in your space reduce costs by 30-40%. If that's interesting, I'd love 15 min.\n\nIf not, no worries at all.\n\nBest,\n{sender}"},
            {"step": 5, "day": 7, "subject": "Should I close the loop?", "body": f"Hi {{{{first_name}}}},\n\nThis will be my last note. If timing isn't right, I totally get it.\n\nBut if there's even a small chance this could be useful for {{{{company}}}}, I'd love to connect.\n\nBest,\n{sender}"},
        ]

    async def push_to_smartlead(
        self,
        session: AsyncSession,
        sequence_id: int,
        smartlead_service,
    ) -> Dict[str, Any]:
        """Push an approved sequence to SmartLead as a DRAFT campaign."""
        seq = await session.get(GeneratedSequence, sequence_id)
        if not seq:
            raise ValueError("Sequence not found")
        if seq.status != "approved":
            raise ValueError("Sequence must be approved before pushing")

        # Create DRAFT campaign in SmartLead
        campaign_data = await smartlead_service.create_campaign(seq.campaign_name or "MCP Generated")
        if not campaign_data:
            raise ValueError("Failed to create SmartLead campaign")

        campaign_id = campaign_data.get("id")

        # Set sequences
        await smartlead_service.set_campaign_sequences(campaign_id, seq.sequence_steps)

        # Update tracking
        seq.pushed_at = datetime.utcnow()
        seq.status = "pushed"

        # Create local campaign record
        campaign = Campaign(
            project_id=seq.project_id,
            company_id=seq.company_id,
            name=seq.campaign_name,
            external_id=str(campaign_id),
            platform="smartlead",
            status="draft",
        )
        session.add(campaign)
        await session.flush()
        seq.pushed_campaign_id = campaign.id

        return {
            "smartlead_campaign_id": campaign_id,
            "url": f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics",
            "status": "draft",
        }
