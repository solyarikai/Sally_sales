"""Gathering Service — pipeline orchestrator adapted for MCP.

Linear pipeline with 3 mandatory checkpoints:
  gather → blacklist → CP1 → pre_filter → scrape → analyze → CP2 → verify → CP3 → push

Phase enforcement: each method checks current_phase before proceeding.
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.gathering import (
    GatheringRun, CompanySourceLink, CompanyScrape,
    GatheringPrompt, AnalysisRun, AnalysisResult, ApprovalGate,
)
from app.models.pipeline import DiscoveredCompany
from app.models.project import Project
from app.services.domain_service import normalize_domain, matches_trash_pattern

logger = logging.getLogger(__name__)

# Phase order for enforcement
PHASE_ORDER = [
    "gather", "blacklist", "awaiting_scope_ok", "pre_filter",
    "scrape", "analyze", "awaiting_targets_ok", "prepare_verification",
    "awaiting_verify_ok", "verified", "push", "completed",
]


class GatheringService:
    """Pipeline orchestrator with phase enforcement and checkpoint gates."""

    # ── Phase enforcement ──

    def _check_phase(self, run: GatheringRun, expected: str):
        if run.current_phase != expected:
            raise ValueError(
                f"Run {run.id} is in phase '{run.current_phase}', "
                f"expected '{expected}'. Cannot skip phases."
            )

    def _advance_phase(self, run: GatheringRun, to_phase: str):
        run.current_phase = to_phase
        run.updated_at = datetime.utcnow()

    # ── Phase 1: Gather + Dedup ──

    async def start_gathering(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        source_type: str,
        filters: Dict[str, Any],
        triggered_by: str = "mcp",
        apollo_service=None,
    ) -> GatheringRun:
        """Create a new gathering run and execute the gather phase."""
        filter_json = json.dumps(filters, sort_keys=True)
        filter_hash = hashlib.sha256(filter_json.encode()).hexdigest()[:16]

        run = GatheringRun(
            project_id=project_id,
            company_id=company_id,
            source_type=source_type,
            filters=filters,
            filter_hash=filter_hash,
            status="running",
            current_phase="gather",
            started_at=datetime.utcnow(),
            triggered_by=triggered_by,
        )
        session.add(run)
        await session.flush()

        # Execute adapter
        adapter = self._get_adapter(source_type, apollo_service=apollo_service)
        if adapter:
            try:
                results = await adapter.gather(filters)
                run.raw_results_count = len(results)

                # Dedup against existing discovered companies
                new_count = 0
                dup_count = 0
                for company_data in results:
                    domain = normalize_domain(company_data.get("domain", ""))
                    if not domain:
                        continue

                    # Check if already discovered for this project
                    existing = await session.execute(
                        select(DiscoveredCompany).where(
                            DiscoveredCompany.project_id == project_id,
                            DiscoveredCompany.domain == domain,
                        )
                    )
                    if existing.scalar_one_or_none():
                        dup_count += 1
                        continue

                    # Create new discovered company
                    dc = DiscoveredCompany(
                        project_id=project_id,
                        company_id=company_id,
                        domain=domain,
                        name=company_data.get("name"),
                        industry=company_data.get("industry"),
                        employee_count=company_data.get("employee_count"),
                        country=company_data.get("country"),
                        city=company_data.get("city"),
                        description=company_data.get("description"),
                        linkedin_url=company_data.get("linkedin_url"),
                        source_data=company_data.get("source_data"),
                    )
                    session.add(dc)
                    await session.flush()

                    # Link to this run
                    link = CompanySourceLink(
                        discovered_company_id=dc.id,
                        gathering_run_id=run.id,
                        source_data=company_data.get("source_data"),
                    )
                    session.add(link)
                    new_count += 1

                run.new_companies_count = new_count
                run.duplicate_count = dup_count
            except Exception as e:
                logger.error(f"Gathering adapter {source_type} failed: {e}")
                run.error_message = str(e)
                run.error_count = 1

        self._advance_phase(run, "blacklist")
        return run

    def _get_adapter(self, source_type: str, apollo_service=None):
        """Get the appropriate gathering adapter."""
        if source_type == "apollo.companies.api":
            from app.services.gathering_adapters.apollo_org_api import ApolloOrgApiAdapter
            return ApolloOrgApiAdapter(apollo_service=apollo_service)
        elif source_type == "manual.companies.manual":
            from app.services.gathering_adapters.manual import ManualAdapter
            return ManualAdapter()
        return None

    # ── Phase 2: Blacklist Check ──

    async def blacklist_check(
        self, session: AsyncSession, run: GatheringRun
    ) -> ApprovalGate:
        """Check gathered companies against existing campaigns. Creates CP1 gate."""
        self._check_phase(run, "blacklist")

        # Get all discovered companies for this run
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_blacklisted == False,
            )
        )
        companies = result.scalars().all()

        passed = 0
        rejected = 0
        for dc in companies:
            if matches_trash_pattern(dc.domain):
                dc.is_blacklisted = True
                dc.blacklist_reason = "trash_domain"
                rejected += 1
            else:
                passed += 1

        run.rejected_count = rejected

        # Get project info for the gate scope
        project = await session.get(Project, run.project_id)

        gate = ApprovalGate(
            project_id=run.project_id,
            gathering_run_id=run.id,
            gate_type="checkpoint_1",
            gate_label="Project scope + blacklist review",
            scope={
                "project_id": run.project_id,
                "project_name": project.name if project else "Unknown",
                "run_id": run.id,
                "source_type": run.source_type,
                "total_gathered": run.raw_results_count,
                "new_companies": run.new_companies_count,
                "passed_blacklist": passed,
                "rejected_blacklist": rejected,
            },
        )
        session.add(gate)
        self._advance_phase(run, "awaiting_scope_ok")
        await session.flush()
        return gate

    # ── Phase 3: Pre-Filter ──

    async def pre_filter(self, session: AsyncSession, run: GatheringRun) -> Dict:
        """Deterministic pre-filtering: remove companies too small, wrong industry, etc."""
        self._check_phase(run, "pre_filter")

        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_blacklisted == False,
                DiscoveredCompany.is_pre_filtered == False,
            )
        )
        companies = result.scalars().all()

        passed = 0
        filtered = 0
        for dc in companies:
            # Basic pre-filter: skip companies with no domain
            if not dc.domain or len(dc.domain) < 4:
                dc.is_pre_filtered = True
                dc.pre_filter_reason = "invalid_domain"
                filtered += 1
            else:
                passed += 1

        self._advance_phase(run, "scrape")
        return {"passed": passed, "filtered": filtered}

    # ── Phase 4: Scrape ──

    async def scrape(
        self, session: AsyncSession, run: GatheringRun,
        scraper_service=None,
    ) -> Dict:
        """Scrape websites for all non-blacklisted companies."""
        self._check_phase(run, "scrape")

        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_blacklisted == False,
                DiscoveredCompany.is_pre_filtered == False,
            )
        )
        companies = result.scalars().all()

        scraped = 0
        errors = 0

        if scraper_service:
            for dc in companies:
                url = dc.website_url or f"https://{dc.domain}"
                scrape_result = await scraper_service.scrape_website(url)

                scrape_record = CompanyScrape(
                    discovered_company_id=dc.id,
                    url=url,
                    scrape_status="success" if scrape_result["success"] else "error",
                    clean_text=scrape_result.get("text"),
                    error_message=scrape_result.get("error"),
                    http_status_code=scrape_result.get("status_code"),
                    text_size_bytes=len(scrape_result.get("text", "")) if scrape_result.get("text") else 0,
                )
                session.add(scrape_record)

                if scrape_result["success"]:
                    scraped += 1
                else:
                    errors += 1
        else:
            scraped = len(companies)

        self._advance_phase(run, "analyze")
        return {"scraped": scraped, "errors": errors, "total": len(companies)}

    # ── Phase 5: Analyze ──

    async def analyze(
        self, session: AsyncSession, run: GatheringRun,
        prompt_text: Optional[str] = None,
        auto_refine: bool = False,
        target_accuracy: float = 0.9,
        openai_key: Optional[str] = None,
    ) -> ApprovalGate:
        """AI analysis with GPT-4o-mini to identify target companies."""
        self._check_phase(run, "analyze")

        # Get companies with scraped text
        from app.models.gathering import CompanyScrape
        result = await session.execute(
            select(DiscoveredCompany, CompanyScrape)
            .outerjoin(CompanyScrape, (CompanyScrape.discovered_company_id == DiscoveredCompany.id) & (CompanyScrape.is_current == True))
            .where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_blacklisted == False,
                DiscoveredCompany.is_pre_filtered == False,
            )
        )
        rows = result.all()

        targets_found = 0
        total_analyzed = 0

        # Build ICP prompt
        icp_prompt = prompt_text or "Analyze if this company matches the target ICP."

        # Analyze each company with GPT-4o-mini
        if openai_key:
            import httpx
            for dc, scrape in rows:
                company_text = f"Company: {dc.name or dc.domain}\nDomain: {dc.domain}\nIndustry: {dc.industry or 'Unknown'}\nCountry: {dc.country or 'Unknown'}\nEmployees: {dc.employee_count or 'Unknown'}"
                if scrape and scrape.clean_text:
                    company_text += f"\nWebsite content:\n{scrape.clean_text[:3000]}"

                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                            json={
                                "model": "gpt-4o-mini",
                                "messages": [
                                    {"role": "system", "content": f"You analyze companies against an ICP (Ideal Customer Profile). Respond ONLY with valid JSON: {{\"is_target\": true/false, \"confidence\": 0.0-1.0, \"segment\": \"brief category\", \"reasoning\": \"1-2 sentence explanation\"}}"},
                                    {"role": "user", "content": f"ICP: {icp_prompt}\n\n{company_text}\n\nIs this company a target? JSON only:"},
                                ],
                                "max_tokens": 200,
                                "temperature": 0.1,
                            },
                        )
                        data = resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                        # Parse GPT response
                        import json as _json
                        try:
                            # Strip markdown code blocks if present
                            clean = content.strip()
                            if clean.startswith("```"):
                                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                            parsed = _json.loads(clean)
                            dc.is_target = parsed.get("is_target", False)
                            dc.analysis_confidence = parsed.get("confidence", 0.5)
                            dc.analysis_segment = parsed.get("segment", "")
                            dc.analysis_reasoning = parsed.get("reasoning", "")
                            total_analyzed += 1
                            if dc.is_target:
                                targets_found += 1
                        except _json.JSONDecodeError:
                            dc.analysis_reasoning = f"GPT response parse error: {content[:200]}"
                            total_analyzed += 1

                except Exception as e:
                    logger.error(f"GPT analysis failed for {dc.domain}: {e}")
                    dc.analysis_reasoning = f"Analysis error: {str(e)[:100]}"
                    total_analyzed += 1
        else:
            logger.warning("No OpenAI key — skipping GPT analysis")

        gate = ApprovalGate(
            project_id=run.project_id,
            gathering_run_id=run.id,
            gate_type="checkpoint_2",
            gate_label="Target list review",
            scope={
                "run_id": run.id,
                "targets_found": targets_found,
                "total_analyzed": total_analyzed,
                "target_rate": f"{targets_found/total_analyzed*100:.0f}%" if total_analyzed > 0 else "0%",
                "auto_refine": auto_refine,
                "prompt_text": prompt_text[:200] if prompt_text else None,
            },
        )
        session.add(gate)
        run.target_rate = targets_found / total_analyzed if total_analyzed > 0 else 0
        self._advance_phase(run, "awaiting_targets_ok")
        await session.flush()
        return gate

    # ── Phase 6: Prepare Verification ──

    async def prepare_verification(
        self, session: AsyncSession, run: GatheringRun
    ) -> ApprovalGate:
        """Create CP3 gate with FindyMail cost estimate."""
        self._check_phase(run, "prepare_verification")

        # Count target companies that need email verification
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.is_enriched == False,
            )
        )
        targets = result.scalars().all()
        email_count = len(targets) * 3  # ~3 contacts per company estimate
        cost_estimate = email_count * 0.01  # $0.01 per FindyMail verification

        gate = ApprovalGate(
            project_id=run.project_id,
            gathering_run_id=run.id,
            gate_type="checkpoint_3",
            gate_label="FindyMail cost approval",
            scope={
                "run_id": run.id,
                "target_companies": len(targets),
                "emails_to_verify": email_count,
                "estimated_cost_usd": round(cost_estimate, 2),
            },
        )
        session.add(gate)
        self._advance_phase(run, "awaiting_verify_ok")
        await session.flush()
        return gate

    # ── Phase 7: Run Verification ──

    async def run_verification(
        self, session: AsyncSession, run: GatheringRun,
        findymail_service=None, apollo_service=None,
    ) -> Dict:
        """Run FindyMail email verification on approved targets."""
        self._check_phase(run, "verified")

        # TODO: Wire in actual FindyMail + Apollo enrichment
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())

        return {"status": "completed", "run_id": run.id}

    # ── Gate Management ──

    async def approve_gate(
        self, session: AsyncSession, gate: ApprovalGate,
        decided_by: str, note: Optional[str] = None,
    ) -> None:
        """Approve a checkpoint gate and advance the run."""
        gate.status = "approved"
        gate.decided_by = decided_by
        gate.decided_at = datetime.utcnow()
        gate.decision_note = note

        if gate.gathering_run_id:
            run = await session.get(GatheringRun, gate.gathering_run_id)
            if run:
                phase_map = {
                    "awaiting_scope_ok": "pre_filter",
                    "awaiting_targets_ok": "prepare_verification",
                    "awaiting_verify_ok": "verified",
                }
                next_phase = phase_map.get(run.current_phase)
                if next_phase:
                    self._advance_phase(run, next_phase)

    async def reject_gate(
        self, session: AsyncSession, gate: ApprovalGate,
        decided_by: str, note: Optional[str] = None,
    ) -> None:
        """Reject a checkpoint gate and cancel the run."""
        gate.status = "rejected"
        gate.decided_by = decided_by
        gate.decided_at = datetime.utcnow()
        gate.decision_note = note

        if gate.gathering_run_id:
            run = await session.get(GatheringRun, gate.gathering_run_id)
            if run:
                run.status = "cancelled"
                run.completed_at = datetime.utcnow()

    # ── Queries ──

    async def get_runs(
        self, session: AsyncSession, project_id: int
    ) -> List[GatheringRun]:
        result = await session.execute(
            select(GatheringRun)
            .where(GatheringRun.project_id == project_id)
            .order_by(GatheringRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending_gates(
        self, session: AsyncSession, project_id: int
    ) -> List[ApprovalGate]:
        result = await session.execute(
            select(ApprovalGate).where(
                ApprovalGate.project_id == project_id,
                ApprovalGate.status == "pending",
            )
        )
        return list(result.scalars().all())

    async def list_prompts(
        self, session: AsyncSession, company_id: int,
        project_id: Optional[int] = None,
    ) -> List[GatheringPrompt]:
        query = select(GatheringPrompt).where(
            GatheringPrompt.company_id == company_id,
            GatheringPrompt.is_active == True,
        )
        if project_id:
            query = query.where(GatheringPrompt.project_id == project_id)
        result = await session.execute(query.order_by(GatheringPrompt.created_at.desc()))
        return list(result.scalars().all())
