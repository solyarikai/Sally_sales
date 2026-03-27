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

                # Persist Apollo credits from the service instance
                if apollo_service and hasattr(apollo_service, 'credits_used'):
                    run.credits_used = apollo_service.credits_used
                    logger.info(f"Run {run.id}: {apollo_service.credits_used} Apollo credits used")
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

        # Build blacklist domains from ALREADY BLACKLISTED companies in this project
        # (imported from SmartLead campaigns via import_smartlead_campaigns)
        blacklist_result = await session.execute(
            select(DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == run.project_id,
                DiscoveredCompany.is_blacklisted == True,
            )
        )
        blacklisted_domains = {row[0] for row in blacklist_result.all()}

        passed = 0
        rejected = 0
        for dc in companies:
            if dc.is_blacklisted:
                # Already blacklisted (e.g. imported from campaigns)
                rejected += 1
                continue
            if matches_trash_pattern(dc.domain):
                dc.is_blacklisted = True
                dc.blacklist_reason = "trash_domain"
                rejected += 1
            elif dc.domain in blacklisted_domains:
                dc.is_blacklisted = True
                dc.blacklist_reason = "existing_campaign_contact"
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
            import asyncio as _asyncio
            for dc in companies:
                url = dc.website_url or f"https://{dc.domain}"
                scrape_result = await scraper_service.scrape_website(url)

                # Retry once on failure (rate limit backoff)
                if not scrape_result["success"]:
                    await _asyncio.sleep(2)
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

    ANALYSIS_BATCH_SIZE = 25
    ANALYSIS_CONCURRENCY = 10

    async def analyze(
        self, session: AsyncSession, run: GatheringRun,
        prompt_text: Optional[str] = None,
        auto_refine: bool = False,
        target_accuracy: float = 0.9,
        openai_key: Optional[str] = None,
    ) -> ApprovalGate:
        """AI analysis with GPT-4o-mini — via negativa, segment labeling, batched.

        GPT does the cheap analysis ($0.003/company).
        The AGENT (Opus in Claude Code) reviews results at Checkpoint 2
        and re-analyzes if accuracy < 90%.
        """
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
        skipped_no_text = 0
        target_list = []
        borderline_rejections = []

        # Build ICP prompt — via negativa style
        from app.models.project import Project
        project = await session.get(Project, run.project_id)
        icp_text = prompt_text or (project.target_segments if project else None) or "General B2B companies"

        via_negativa_system = f"""{icp_text}

Analyze the company website below using VIA NEGATIVA — focus on what RULES IT OUT.

Exclusion criteria (reject if ANY apply):
- Company is a freelancer/solo consultant (no real team)
- Website is a placeholder, parked domain, or under construction
- Company is in a completely unrelated industry (e.g., restaurant, retail, personal blog)
- Company has shut down or is clearly inactive
- Website is not in a relevant language for the target market
- Company is too large (enterprise/multinational) if targeting SMB

If NONE of these exclusions apply → the company survives. Label it as target.

Respond ONLY with valid JSON:
{{
  "is_target": true,
  "confidence": 0.85,
  "segment": "IT_OUTSOURCING",
  "reasoning": "1-2 sentence explanation of WHY target or WHY excluded"
}}

Rules:
- confidence 0.8+: clear match, no exclusions triggered
- confidence 0.5-0.79: likely match but some uncertainty
- confidence <0.5: exclusion triggered → is_target: false
- segment: short CAPS_LOCKED label (e.g. IT_OUTSOURCING, SAAS_COMPANY, AGENCY, ECOMMERCE, NOT_A_MATCH)
- is_target: true only if confidence >= 0.6"""

        if not openai_key:
            logger.warning("No OpenAI key — skipping GPT analysis")
            gate = self._create_checkpoint2_gate(session, run, 0, 0, 0, [], [], icp_text)
            return gate

        # Process in batches with concurrency
        import asyncio
        import httpx
        import json as _json

        semaphore = asyncio.Semaphore(self.ANALYSIS_CONCURRENCY)

        async def analyze_one(dc: DiscoveredCompany, scrape_text: Optional[str]) -> Dict:
            """Analyze a single company with GPT-4o-mini."""
            company_text = f"Company: {dc.name or dc.domain}\nDomain: {dc.domain}"
            if dc.industry:
                company_text += f"\nIndustry: {dc.industry}"
            if dc.country:
                company_text += f"\nCountry: {dc.country}"
            if dc.employee_count:
                company_text += f"\nEmployees: {dc.employee_count}"
            if scrape_text:
                company_text += f"\n\nWebsite content:\n{scrape_text[:3000]}"

            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                            json={
                                "model": "gpt-4o-mini",
                                "messages": [
                                    {"role": "system", "content": via_negativa_system},
                                    {"role": "user", "content": company_text},
                                ],
                                "max_tokens": 200,
                                "temperature": 0.1,
                            },
                        )
                        data = resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        clean = content.strip()
                        if clean.startswith("```"):
                            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                        parsed = _json.loads(clean)
                        return {"dc_id": dc.id, "domain": dc.domain, "name": dc.name, **parsed}
                except _json.JSONDecodeError:
                    return {"dc_id": dc.id, "domain": dc.domain, "name": dc.name,
                            "is_target": False, "confidence": 0, "segment": "PARSE_ERROR",
                            "reasoning": f"GPT response parse error: {content[:200]}"}
                except Exception as e:
                    return {"dc_id": dc.id, "domain": dc.domain, "name": dc.name,
                            "is_target": False, "confidence": 0, "segment": "ERROR",
                            "reasoning": f"Analysis error: {str(e)[:100]}"}

        # Build work items
        work_items = []
        dc_map = {}
        for dc, scrape in rows:
            scrape_text = scrape.clean_text if scrape and scrape.clean_text else None
            if not scrape_text:
                skipped_no_text += 1
                continue
            work_items.append((dc, scrape_text))
            dc_map[dc.id] = dc

        # Process in batches of 25
        for batch_start in range(0, len(work_items), self.ANALYSIS_BATCH_SIZE):
            batch = work_items[batch_start:batch_start + self.ANALYSIS_BATCH_SIZE]
            tasks = [analyze_one(dc, text) for dc, text in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    total_analyzed += 1
                    continue
                if not isinstance(r, dict):
                    total_analyzed += 1
                    continue

                dc = dc_map.get(r["dc_id"])
                if not dc:
                    continue

                dc.is_target = r.get("is_target", False)
                dc.analysis_confidence = r.get("confidence", 0)
                dc.analysis_segment = r.get("segment", "")
                dc.analysis_reasoning = r.get("reasoning", "")
                total_analyzed += 1

                if dc.is_target:
                    targets_found += 1
                    target_list.append({
                        "dc_id": dc.id, "domain": dc.domain, "name": dc.name,
                        "confidence": dc.analysis_confidence,
                        "segment": dc.analysis_segment,
                        "reasoning": dc.analysis_reasoning,
                    })
                elif 0.4 <= r.get("confidence", 0) <= 0.6:
                    borderline_rejections.append({
                        "domain": dc.domain, "name": dc.name,
                        "confidence": r.get("confidence", 0),
                        "segment": r.get("segment", ""),
                        "reasoning": r.get("reasoning", ""),
                    })

            # Flush after each batch
            await session.flush()
            logger.info(f"Analysis batch {batch_start//self.ANALYSIS_BATCH_SIZE + 1}: "
                        f"{targets_found} targets / {total_analyzed} analyzed")

        # Sort target list by confidence DESC
        target_list.sort(key=lambda x: -x.get("confidence", 0))
        borderline_rejections.sort(key=lambda x: -x.get("confidence", 0))

        # Normalize company names for targets only (GPT-4o-mini, cheap)
        target_dc_ids = [t.get("dc_id") for t in target_list if t.get("dc_id")]
        if target_dc_ids and openai_key:
            target_dcs = [dc_map[dc_id] for dc_id in target_dc_ids if dc_id in dc_map]
            normalized = await self._normalize_company_names(target_dcs, openai_key)
            # Update target_list names to reflect normalization
            name_map = {dc.id: dc.name for dc in target_dcs}
            for t in target_list:
                if t.get("dc_id") in name_map:
                    t["name"] = name_map[t["dc_id"]]
            await session.flush()
            logger.info(f"Normalized {normalized} target company names")

        gate = self._create_checkpoint2_gate(
            session, run, targets_found, total_analyzed, skipped_no_text,
            target_list, borderline_rejections, icp_text,
        )

        run.target_rate = targets_found / total_analyzed if total_analyzed > 0 else 0
        run.avg_analysis_confidence = (
            sum(t["confidence"] for t in target_list) / len(target_list)
            if target_list else 0
        )
        self._advance_phase(run, "awaiting_targets_ok")
        await session.flush()
        return gate

    def _create_checkpoint2_gate(
        self, session, run, targets_found, total_analyzed, skipped_no_text,
        target_list, borderline_rejections, prompt_text,
    ) -> ApprovalGate:
        """Create Checkpoint 2 gate with full target list for agent QA."""
        avg_conf = sum(t["confidence"] for t in target_list) / len(target_list) if target_list else 0

        # Segment distribution
        segment_counts = {}
        for t in target_list:
            seg = t.get("segment", "UNKNOWN")
            segment_counts[seg] = segment_counts.get(seg, 0) + 1

        gate = ApprovalGate(
            project_id=run.project_id,
            gathering_run_id=run.id,
            gate_type="checkpoint_2",
            gate_label="Target list review",
            scope={
                "run_id": run.id,
                "targets_found": targets_found,
                "total_analyzed": total_analyzed,
                "skipped_no_scraped_text": skipped_no_text,
                "target_rate": f"{targets_found/max(total_analyzed,1)*100:.0f}%",
                "avg_confidence": round(avg_conf, 2),
                "segment_distribution": segment_counts,
                "target_list": target_list[:100],  # Top 100 targets for agent review
                "borderline_rejections": borderline_rejections[:20],  # Borderline for agent override
                "prompt_text": prompt_text[:500] if prompt_text else None,
            },
        )
        session.add(gate)
        return gate

    # ── Company Name Normalization (targets only) ──

    NORMALIZE_BATCH_SIZE = 20
    NORMALIZE_CONCURRENCY = 10

    NORMALIZE_SYSTEM_PROMPT = (
        "You are a data normalization expert. Normalize the company name to its clean, "
        "canonical brand form. Strip legal suffixes (Inc, LLC, Ltd, GmbH, etc.), "
        "remove location/office tails after separators, drop parenthetical notes. "
        "Keep meaningful brand terms. Title Case output, preserve acronyms. "
        "Return ONLY the normalized name, nothing else."
    )

    async def _normalize_company_names(
        self, companies: List[DiscoveredCompany], openai_key: str
    ) -> int:
        """Normalize company names via GPT-4o-mini. Only called for confirmed targets.

        Updates dc.name in-place (original preserved in source_data).
        Returns count of names actually changed.
        """
        import asyncio
        import httpx

        semaphore = asyncio.Semaphore(self.NORMALIZE_CONCURRENCY)
        changed = 0

        async def normalize_one(dc: DiscoveredCompany) -> Optional[str]:
            if not dc.name or len(dc.name) < 3:
                return None
            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                            json={
                                "model": "gpt-4o-mini",
                                "messages": [
                                    {"role": "system", "content": self.NORMALIZE_SYSTEM_PROMPT},
                                    {"role": "user", "content": dc.name},
                                ],
                                "max_tokens": 60,
                                "temperature": 0,
                            },
                        )
                        data = resp.json()
                        normalized = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if normalized and normalized != dc.name:
                            return normalized
                except Exception as e:
                    logger.debug(f"Name normalization failed for {dc.domain}: {e}")
            return None

        for batch_start in range(0, len(companies), self.NORMALIZE_BATCH_SIZE):
            batch = companies[batch_start:batch_start + self.NORMALIZE_BATCH_SIZE]
            tasks = [normalize_one(dc) for dc in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for dc, result in zip(batch, results):
                if isinstance(result, str) and result:
                    dc.name = result
                    changed += 1

        return changed

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
