"""
Gathering Service — strict linear pipeline with 3 mandatory operator checkpoints.

Pipeline phases (in order, no skipping):

  GATHER+DEDUP → BLACKLIST → ★CP1 → PRE-FILTER → SCRAPE → ANALYZE → ★CP2 → VERIFY → ★CP3 → PUSH
       auto         auto     STOP       auto        auto     auto     STOP    blocked   STOP   blocked

Phase state machine (gathering_run.current_phase):
  gathered → blacklisted → awaiting_scope_ok → scope_approved → filtered →
  scraped → analyzed → awaiting_targets_ok → targets_approved →
  awaiting_verify_ok → verify_approved → verified → pushed

Checkpoints create approval_gates records. Phase cannot advance past a checkpoint
until the gate is approved. This survives session crashes — next Claude Code session
reads current_phase and knows exactly where the operator left off.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, update, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gathering import (
    GatheringRun, CompanySourceLink, CompanyScrape,
    GatheringPrompt, AnalysisRun, AnalysisResult, ApprovalGate,
)
from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
from app.models.domain import ProjectBlacklist
from app.services.gathering_adapters import get_adapter, list_adapters
from app.services.domain_service import normalize_domain

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# PHASE STATE MACHINE — the heart of pipeline enforcement
# ═══════════════════════════════════════════════════════════════

PHASE_ORDER = [
    "gathered",              # GATHER+DEDUP complete. Next: blacklist
    "awaiting_scope_ok",     # BLACKLIST done → ★ CHECKPOINT 1 — waiting for operator
    "scope_approved",        # Operator confirmed project scope
    "filtered",              # PRE-FILTER complete
    "scraped",               # SCRAPE complete
    "analyzed",              # ANALYZE complete
    "awaiting_targets_ok",   # ★ CHECKPOINT 2 — waiting for operator
    "targets_approved",      # Operator confirmed target list
    "awaiting_verify_ok",    # ★ CHECKPOINT 3 — waiting for operator
    "verify_approved",       # Operator approved FindyMail spend
    "verified",              # VERIFY (FindyMail) complete
    "pushed",                # PUSH complete
]

CHECKPOINT_PHASES = {
    "awaiting_scope_ok":   {"gate_type": "scope_verification",  "next": "scope_approved"},
    "awaiting_targets_ok": {"gate_type": "target_review",       "next": "targets_approved"},
    "awaiting_verify_ok":  {"gate_type": "findymail_cost",      "next": "verify_approved"},
}

# Which phase is required BEFORE each action




def _compute_filter_hash(filters: dict) -> str:
    canonical = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _require_phase(run: GatheringRun, required: str, action: str):
    """Raise if the run is not at the required phase."""
    if run.current_phase != required:
        current_idx = PHASE_ORDER.index(run.current_phase) if run.current_phase in PHASE_ORDER else -1
        required_idx = PHASE_ORDER.index(required)

        if run.current_phase in CHECKPOINT_PHASES:
            cp = run.current_phase.replace("awaiting_", "").replace("_ok", "")
            raise ValueError(
                f"Cannot {action}: run #{run.id} is waiting for operator approval at checkpoint '{cp}'. "
                f"Approve it first via POST /approval-gates/{{gate_id}}/approve"
            )
        elif current_idx < required_idx:
            raise ValueError(
                f"Cannot {action}: run #{run.id} is at phase '{run.current_phase}', "
                f"but '{required}' is required. Complete earlier phases first."
            )
        elif current_idx > required_idx:
            raise ValueError(
                f"Cannot {action}: run #{run.id} already past '{required}' (now at '{run.current_phase}'). "
                f"This phase was already completed."
            )


class GatheringService:
    """Orchestrates the full TAM gathering pipeline with mandatory checkpoints."""

    # ══════════════════════════════════════════════════════════
    # PHASE 1: GATHER + DEDUP (auto)
    # ══════════════════════════════════════════════════════════

    async def start_gathering(
        self,
        session: AsyncSession,
        project_id: int,
        company_id: int,
        source_type: str,
        filters: dict,
        segment_id: Optional[int] = None,
        triggered_by: str = "operator",
        input_mode: str = "structured",
        input_text: Optional[str] = None,
        notes: Optional[str] = None,
        parent_run_id: Optional[int] = None,
    ) -> GatheringRun:
        """Phase 1: Create GatheringRun, execute adapter, dedup results.
        After this, current_phase = 'gathered'. Next: blacklist."""
        adapter = get_adapter(source_type)
        cleaned_filters = await adapter.validate(filters)
        filter_hash = _compute_filter_hash(cleaned_filters)

        # Check for duplicate run (bypass if intentional re-run)
        if not parent_run_id:
            existing = await session.execute(
                select(GatheringRun).where(
                    GatheringRun.project_id == project_id,
                    GatheringRun.filter_hash == filter_hash,
                    GatheringRun.status == "completed",
                )
            )
            existing_run = existing.scalar_one_or_none()
            if existing_run:
                logger.info(f"Duplicate filter hash — returning existing run #{existing_run.id}")
                return existing_run

        run = GatheringRun(
            project_id=project_id,
            company_id=company_id,
            source_type=source_type,
            source_label=adapter.source_label,
            filters=cleaned_filters,
            filter_hash=filter_hash,
            status="running",
            current_phase="gather",
            started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
            input_mode=input_mode,
            input_text=input_text,
            notes=notes,
            segment_id=segment_id,
            parent_run_id=parent_run_id,
        )
        session.add(run)
        await session.flush()

        try:
            result = await adapter.execute(cleaned_filters)

            run.raw_results_count = result.raw_results_count
            run.credits_used = result.credits_used
            run.total_cost_usd = result.cost_usd
            run.raw_output_sample = result.companies[:50]

            if result.error_message:
                run.status = "failed"
                run.error_message = result.error_message
            else:
                dedup = await self._dedup_and_store(
                    session, run.id, project_id, company_id, result.companies
                )
                run.new_companies_count = dedup["new_companies"]
                run.duplicate_count = dedup["duplicates"]
                run.status = "running"
                run.current_phase = "gathered"

            run.completed_at = datetime.now(timezone.utc)
            if run.started_at:
                run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())

        except Exception as e:
            logger.error(f"Gathering run #{run.id} failed: {e}")
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(run)
        return run

    async def _dedup_and_store(
        self, session: AsyncSession, gathering_run_id: int,
        project_id: int, company_id: int, companies: List[dict],
    ) -> dict:
        """Normalize domains, upsert DiscoveredCompanies, create source_links."""
        new_count = 0
        dup_count = 0
        links_created = 0

        for i, company_data in enumerate(companies):
            domain = normalize_domain(company_data.get("domain", ""))
            if not domain:
                continue

            existing = await session.execute(
                select(DiscoveredCompany).where(
                    DiscoveredCompany.company_id == company_id,
                    DiscoveredCompany.project_id == project_id,
                    DiscoveredCompany.domain == domain,
                )
            )
            dc = existing.scalar_one_or_none()

            if dc:
                dup_count += 1
            else:
                dc = DiscoveredCompany(
                    company_id=company_id, project_id=project_id,
                    domain=domain, name=company_data.get("name", ""),
                    url=f"https://{domain}",
                    company_info=company_data.get("raw_apollo") or company_data,
                    status=DiscoveredCompanyStatus.NEW,
                    first_found_by=gathering_run_id,
                )
                session.add(dc)
                await session.flush()
                new_count += 1

            existing_link = await session.execute(
                select(CompanySourceLink).where(
                    CompanySourceLink.discovered_company_id == dc.id,
                    CompanySourceLink.gathering_run_id == gathering_run_id,
                )
            )
            if not existing_link.scalar_one_or_none():
                link = CompanySourceLink(
                    discovered_company_id=dc.id, gathering_run_id=gathering_run_id,
                    source_rank=i + 1, source_data=company_data,
                    source_confidence=company_data.get("source_confidence"),
                )
                session.add(link)
                links_created += 1

        await session.flush()
        return {"total_input": len(companies), "new_companies": new_count,
                "duplicates": dup_count, "source_links_created": links_created}

    # ══════════════════════════════════════════════════════════
    # PHASE 2: BLACKLIST (auto, project-scoped)
    # After this → awaiting_scope_ok (CHECKPOINT 1)
    # ══════════════════════════════════════════════════════════

    async def run_blacklist_check(
        self, session: AsyncSession, run_id: int, cross_project: bool = False,
    ) -> dict:
        """Phase 2: Project-scoped blacklist. After this, creates CHECKPOINT 1 gate."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        _require_phase(run, "gathered", "run blacklist check")

        from app.models.campaign import Campaign
        from app.models.contact import Contact, Project

        project_id = run.project_id

        # Get companies from this run
        links = await session.execute(
            select(CompanySourceLink).where(CompanySourceLink.gathering_run_id == run_id)
        )
        company_ids = [sl.discovered_company_id for sl in links.scalars().all()]

        # Get project name early (needed for gate label)
        project = await session.get(Project, project_id)
        project_name = project.name if project else f"Project #{project_id}"

        # Early exit: no companies or no domains — still create checkpoint gate
        if not company_ids:
            gate = ApprovalGate(
                project_id=project_id, gathering_run_id=run.id,
                gate_type="scope_verification",
                gate_label=f"[EMPTY] No companies to check for {project_name}",
                scope={"passed": 0, "rejected": 0, "note": "No companies in this gathering run"},
                status="pending", expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(gate)
            run.current_phase = "awaiting_scope_ok"
            await session.commit()
            return {"project_id": project_id, "project_name": project_name,
                    "total_checked": 0, "passed": 0, "rejected_total": 0,
                    "rejected_domains": [], "warning_domains": [],
                    "checkpoint": {"gate_id": gate.id, "status": "awaiting_scope_ok",
                                   "message": "No companies to check. Approve to continue."}}

        companies_result = await session.execute(
            select(DiscoveredCompany).where(DiscoveredCompany.id.in_(company_ids))
        )
        dc_list = companies_result.scalars().all()
        domains = [dc.domain for dc in dc_list if dc.domain]

        if not domains:
            gate = ApprovalGate(
                project_id=project_id, gathering_run_id=run.id,
                gate_type="scope_verification",
                gate_label=f"[NO DOMAINS] {len(dc_list)} companies but no domains for {project_name}",
                scope={"passed": len(dc_list), "rejected": 0, "note": "Companies have no domains — may need RESOLVE phase"},
                status="pending", expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(gate)
            run.current_phase = "awaiting_scope_ok"
            await session.commit()
            return {"project_id": project_id, "project_name": project_name,
                    "total_checked": len(dc_list), "passed": len(dc_list), "rejected_total": 0,
                    "rejected_domains": [], "warning_domains": [],
                    "checkpoint": {"gate_id": gate.id, "status": "awaiting_scope_ok",
                                   "message": "No domains to blacklist-check. Approve to continue."}}

        # 1. Project blacklist (case-insensitive)
        domains_lower = [d.lower() for d in domains]
        bl_result = await session.execute(
            select(ProjectBlacklist.domain, ProjectBlacklist.reason).where(
                ProjectBlacklist.project_id == project_id,
                func.lower(ProjectBlacklist.domain).in_(domains_lower),
            )
        )
        blacklisted = {row[0].lower(): row[1] for row in bl_result.fetchall()}

        # 2. Same-project campaigns
        same_project_result = await session.execute(
            select(
                func.lower(Contact.domain).label("domain"),
                func.count(Contact.id).label("contact_count"),
                func.array_agg(func.distinct(Campaign.name)).label("campaign_names"),
                func.array_agg(func.distinct(Campaign.id)).label("campaign_ids"),
            )
            .join(Campaign, and_(
                Campaign.project_id == Contact.project_id,
                Campaign.status == "active",
            ))
            .where(
                Contact.project_id == project_id,
                Contact.domain.isnot(None),
                func.lower(Contact.domain).in_([d.lower() for d in domains]),
            )
            .group_by(func.lower(Contact.domain))
        )
        same_project_domains = {}
        for row in same_project_result.fetchall():
            same_project_domains[row.domain] = {
                "contact_count": row.contact_count,
                "campaign_names": [n for n in (row.campaign_names or []) if n],
                "campaign_ids": [i for i in (row.campaign_ids or []) if i],
            }

        # 3. Cross-project warnings
        cross_project_domains = {}
        if cross_project:
            cross_result = await session.execute(
                select(
                    func.lower(Contact.domain).label("domain"),
                    Project.name.label("project_name"),
                    Project.id.label("other_project_id"),
                    func.count(Contact.id).label("contact_count"),
                    func.array_agg(func.distinct(Campaign.name)).label("campaign_names"),
                )
                .join(Project, Project.id == Contact.project_id)
                .join(Campaign, and_(
                    Campaign.project_id == Contact.project_id,
                    Campaign.status == "active",
                ))
                .where(
                    Contact.project_id != project_id,
                    Contact.domain.isnot(None),
                    func.lower(Contact.domain).in_([d.lower() for d in domains]),
                )
                .group_by(func.lower(Contact.domain), Project.name, Project.id)
            )
            for row in cross_result.fetchall():
                if row.domain not in cross_project_domains:
                    cross_project_domains[row.domain] = []
                cross_project_domains[row.domain].append({
                    "project_name": row.project_name,
                    "project_id": row.other_project_id,
                    "contact_count": row.contact_count,
                    "campaign_names": [n for n in (row.campaign_names or []) if n],
                })

        # 4. Enterprise blacklist
        enterprise_domains = set()
        try:
            from pathlib import Path
            bl_path = Path(__file__).parent.parent.parent.parent / "easystaff-global" / "enterprise_blacklist.json"
            if bl_path.exists():
                with open(bl_path) as f:
                    enterprise_domains = set(d.lower() for d in json.load(f) if isinstance(d, str))
        except Exception:
            pass

        # Apply verdicts — deduplicate by domain to avoid constraint violations
        in_bl = 0; in_same = 0; in_enterprise = 0; passed = 0
        rejected_domains = []; warning_domains = []
        seen_domains = set()

        for dc in dc_list:
            d = (dc.domain or "").lower()
            if not d or d in seen_domains:
                if d:
                    seen_domains.add(d)
                else:
                    passed += 1
                continue
            seen_domains.add(d)

            if d in blacklisted:
                dc.status = DiscoveredCompanyStatus.REJECTED
                in_bl += 1
                rejected_domains.append({"domain": d, "company_name": dc.name,
                    "reason": "project_blacklist", "detail": blacklisted[d] or "Manually blacklisted"})
            elif d in same_project_domains:
                info = same_project_domains[d]
                dc.status = DiscoveredCompanyStatus.REJECTED
                dc.in_active_campaign = True
                dc.campaign_ids_active = info["campaign_ids"]
                in_same += 1
                rejected_domains.append({"domain": d, "company_name": dc.name,
                    "reason": "same_project_campaign",
                    "detail": f"{info['contact_count']} contacts in {len(info['campaign_names'])} campaigns",
                    "campaigns": info["campaign_names"], "contact_count": info["contact_count"]})
            elif d in enterprise_domains:
                dc.status = DiscoveredCompanyStatus.REJECTED
                in_enterprise += 1
                rejected_domains.append({"domain": d, "company_name": dc.name,
                    "reason": "enterprise_blacklist", "detail": "Global enterprise blacklist"})
            else:
                passed += 1

            if d in cross_project_domains:
                for other in cross_project_domains[d]:
                    warning_domains.append({"domain": d, "company_name": dc.name,
                        "other_project_name": other["project_name"],
                        "other_project_id": other["project_id"],
                        "other_contact_count": other["contact_count"],
                        "other_campaigns": other["campaign_names"]})

        total_rejected = in_bl + in_same + in_enterprise
        run.rejected_count = total_rejected

        # ── Build project context for CP1 (replaces CP0) ──
        # CP1 is the ONLY code-enforced project confirmation.
        # It shows full project context so operator confirms scope.
        from app.models.campaign import Campaign
        active_campaigns_q = await session.execute(
            select(Campaign.name, Campaign.id, Campaign.platform, Campaign.leads_count).where(
                Campaign.project_id == project_id,
                Campaign.status == "active",
            )
        )
        project_campaigns = [
            {"name": row.name, "id": row.id, "platform": row.platform, "leads_count": row.leads_count}
            for row in active_campaigns_q.fetchall()
        ]
        total_project_contacts = (await session.execute(
            select(func.count(Contact.id)).where(Contact.project_id == project_id)
        )).scalar() or 0

        # AUTO-CREATE CHECKPOINT 1 gate
        # This is the REAL project scope confirmation (CP0 is just a CLAUDE.md hint).
        # Stores FULL detail so it survives session crashes.
        gate = ApprovalGate(
            project_id=project_id, gathering_run_id=run.id,
            gate_type="scope_verification",
            gate_label=f"Confirm project {project_name}: {passed} passed, {total_rejected} rejected",
            scope={
                "project_id": project_id,
                "project_name": project_name,
                "project_total_contacts": total_project_contacts,
                "project_active_campaigns": project_campaigns,
                "passed": passed, "rejected_total": total_rejected,
                "in_project_blacklist": in_bl, "in_same_project_campaigns": in_same,
                "in_enterprise_blacklist": in_enterprise,
                "cross_project_warnings": len(warning_domains),
                "rejected_domains": rejected_domains[:200],
                "warning_domains": warning_domains[:100],
            },
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(gate)

        run.current_phase = "awaiting_scope_ok"
        await session.commit()

        logger.info(f"Blacklist [{project_name}]: {total_rejected} rejected, {passed} passed → CHECKPOINT 1 (gate #{gate.id})")

        return {
            "project_id": project_id, "project_name": project_name,
            "project_total_contacts": total_project_contacts,
            "project_active_campaigns": project_campaigns,
            "total_checked": len(dc_list), "passed": passed,
            "rejected_total": total_rejected,
            "in_project_blacklist": in_bl,
            "in_same_project_campaigns": in_same,
            "in_enterprise_blacklist": in_enterprise,
            "cross_project_warnings": len(warning_domains),
            "rejected_domains": rejected_domains,
            "warning_domains": warning_domains,
            "checkpoint": {"gate_id": gate.id, "status": "awaiting_scope_ok",
                           "message": "Operator must approve project scope before continuing."},
        }

    # ══════════════════════════════════════════════════════════
    # CHECKPOINT APPROVAL (advances phase past a checkpoint)
    # ══════════════════════════════════════════════════════════

    async def approve_checkpoint(
        self, session: AsyncSession, gate_id: int,
        decided_by: str = "operator", note: Optional[str] = None,
    ) -> dict:
        """Approve a checkpoint gate and advance the gathering run to the next phase."""
        gate = await session.get(ApprovalGate, gate_id)
        if not gate:
            raise ValueError(f"Gate #{gate_id} not found")
        if gate.status != "pending":
            raise ValueError(f"Gate #{gate_id} is already {gate.status}")
        if not gate.gathering_run_id:
            raise ValueError(f"Gate #{gate_id} is not linked to a gathering run")

        run = await session.get(GatheringRun, gate.gathering_run_id)
        if not run:
            raise ValueError(f"Gathering run for gate #{gate_id} not found")

        # Verify the run is actually at this checkpoint
        if run.current_phase not in CHECKPOINT_PHASES:
            raise ValueError(f"Run #{run.id} is at '{run.current_phase}', not at a checkpoint")

        cp_info = CHECKPOINT_PHASES[run.current_phase]
        if gate.gate_type != cp_info["gate_type"]:
            raise ValueError(
                f"Gate type mismatch: gate is '{gate.gate_type}' but run expects '{cp_info['gate_type']}'"
            )

        # Approve
        gate.status = "approved"
        gate.decided_by = decided_by
        gate.decided_at = datetime.now(timezone.utc)
        gate.decision_note = note

        run.current_phase = cp_info["next"]
        await session.commit()

        logger.info(f"Checkpoint approved: gate #{gate_id} → run #{run.id} advanced to '{run.current_phase}'")
        return {
            "gate_id": gate_id, "status": "approved",
            "run_id": run.id, "new_phase": run.current_phase,
        }

    async def reject_checkpoint(
        self, session: AsyncSession, gate_id: int,
        decided_by: str = "operator", note: Optional[str] = None,
    ) -> dict:
        """Reject a checkpoint. Run stays at current phase (operator must fix and re-try)."""
        gate = await session.get(ApprovalGate, gate_id)
        if not gate:
            raise ValueError(f"Gate #{gate_id} not found")
        if gate.status != "pending":
            raise ValueError(f"Gate #{gate_id} is already {gate.status}")

        gate.status = "rejected"
        gate.decided_by = decided_by
        gate.decided_at = datetime.now(timezone.utc)
        gate.decision_note = note
        await session.commit()

        return {"gate_id": gate_id, "status": "rejected", "note": note}

    # ══════════════════════════════════════════════════════════
    # PHASE 3: PRE-FILTER (auto, after checkpoint 1)
    # ══════════════════════════════════════════════════════════

    _OFFLINE_PATTERNS = [
        "restaurant", "hotel", "motel", "cafe", "bakery", "pizzeria",
        "construction", "plumbing", "electrician", "hvac", "roofing",
        "dentist", "dental", "clinic", "hospital", "pharmacy",
        "church", "mosque", "temple", "school", "university",
        "car wash", "laundry", "dry clean", "hair salon", "barber",
        "funeral", "cemetery", "towing", "locksmith",
    ]
    _JUNK_SUFFIXES = [".gov", ".edu", ".mil", ".gov.ae", ".ac.uk"]

    async def run_pre_filter(self, session: AsyncSession, run_id: int) -> dict:
        """Phase 3: Deterministic rejection. Requires scope_approved phase."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        _require_phase(run, "scope_approved", "run pre-filter")

        links = await session.execute(
            select(CompanySourceLink).where(CompanySourceLink.gathering_run_id == run_id)
        )
        company_ids = [sl.discovered_company_id for sl in links.scalars().all()]

        companies_result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(company_ids),
                DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
            )
        )
        dc_list = companies_result.scalars().all()
        rejected = 0; passed = 0

        for dc in dc_list:
            name_lower = (dc.name or "").lower()
            domain_lower = (dc.domain or "").lower()
            from app.services.domain_service import matches_trash_pattern

            is_offline = any(p in name_lower for p in self._OFFLINE_PATTERNS)
            is_junk = any(domain_lower.endswith(s) for s in self._JUNK_SUFFIXES)
            is_trash = matches_trash_pattern(domain_lower) if domain_lower else False

            if is_offline or is_junk or is_trash:
                dc.status = DiscoveredCompanyStatus.REJECTED
                rejected += 1
            else:
                passed += 1

        run.current_phase = "filtered"
        await session.commit()
        logger.info(f"Pre-filter: {rejected} rejected, {passed} passed")
        return {"total_checked": len(dc_list), "rejected": rejected, "passed": passed}

    # ══════════════════════════════════════════════════════════
    # PHASE 4: SCRAPE (auto, free)
    # ══════════════════════════════════════════════════════════

    async def scrape_companies(
        self, session: AsyncSession, run_id: int,
        pages: List[str] = None, method: str = "httpx", force: bool = False,
    ) -> dict:
        """Phase 4: Scrape websites. Requires filtered phase. Free (httpx)."""
        if pages is None:
            pages = ["/"]
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        _require_phase(run, "filtered", "scrape companies")

        from app.services.scraper_service import scraper_service

        links = await session.execute(
            select(CompanySourceLink).where(CompanySourceLink.gathering_run_id == run_id)
        )
        company_ids = [sl.discovered_company_id for sl in links.scalars().all()]
        companies_result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(company_ids),
                DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
            )
        )
        dc_list = companies_result.scalars().all()

        scraped = 0; skipped = 0; errors = 0
        now = datetime.now(timezone.utc)

        for dc in dc_list:
            if not dc.domain:
                continue
            for page_path in pages:
                url = f"https://{dc.domain}{page_path}"

                if not force:
                    existing = await session.execute(
                        select(CompanyScrape).where(
                            CompanyScrape.discovered_company_id == dc.id,
                            CompanyScrape.page_path == page_path,
                            CompanyScrape.is_current == True,
                            CompanyScrape.expires_at > now,
                        )
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
                        continue

                try:
                    result = await scraper_service.scrape_website(url)

                    await session.execute(
                        update(CompanyScrape).where(
                            CompanyScrape.discovered_company_id == dc.id,
                            CompanyScrape.page_path == page_path,
                            CompanyScrape.is_current == True,
                        ).values(is_current=False)
                    )

                    max_ver = await session.execute(
                        select(func.max(CompanyScrape.version)).where(
                            CompanyScrape.discovered_company_id == dc.id,
                            CompanyScrape.page_path == page_path,
                        )
                    )
                    next_version = (max_ver.scalar() or 0) + 1
                    clean_text = result.get("text", "")
                    raw_html = result.get("html", "")

                    scrape = CompanyScrape(
                        discovered_company_id=dc.id, url=url, page_path=page_path,
                        raw_html=raw_html[:100000] if raw_html else None,
                        clean_text=clean_text[:50000] if clean_text else None,
                        page_metadata={"title": result.get("title", ""), "status_code": result.get("status_code")},
                        ttl_days=180, expires_at=now + timedelta(days=180),
                        is_current=True, version=next_version, scrape_method=method,
                        scrape_status="success" if result.get("success") else "error",
                        error_message=result.get("error"),
                        http_status_code=result.get("status_code"),
                        html_size_bytes=len(raw_html) if raw_html else 0,
                        text_size_bytes=len(clean_text) if clean_text else 0,
                    )
                    session.add(scrape)

                    if page_path == "/" and clean_text:
                        dc.scraped_text = clean_text[:50000]
                        dc.scraped_html = raw_html[:100000] if raw_html else None
                        dc.scraped_at = now
                        if dc.status == DiscoveredCompanyStatus.NEW:
                            dc.status = DiscoveredCompanyStatus.SCRAPED
                    scraped += 1

                except Exception as e:
                    logger.error(f"Scrape failed for {url}: {e}")
                    errors += 1

        run.current_phase = "scraped"
        await session.commit()
        logger.info(f"Scrape: {scraped} scraped, {skipped} skipped, {errors} errors")
        return {"scraped": scraped, "skipped": skipped, "errors": errors, "total": len(dc_list)}

    # ══════════════════════════════════════════════════════════
    # PHASE 5: ANALYZE (auto, cheap)
    # After this → awaiting_targets_ok (CHECKPOINT 2)
    # ══════════════════════════════════════════════════════════

    async def run_analysis(
        self, session: AsyncSession, run_id: int,
        model: str = "gpt-4o-mini", prompt_text: str = "",
        prompt_name: Optional[str] = None,
    ) -> dict:
        """Phase 5: AI analysis. Requires scraped phase. Creates CHECKPOINT 2 after."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        _require_phase(run, "scraped", "run analysis")

        from app.services.company_search_service import company_search_service

        # Create analysis run with prompt tracking
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        prompt = await self.get_or_create_prompt(
            session, run.company_id,
            name=prompt_name or f"Analysis {prompt_hash[:8]}",
            prompt_text=prompt_text, project_id=run.project_id,
            model_default=model, created_by="pipeline",
        )

        analysis_run = AnalysisRun(
            project_id=run.project_id, company_id=run.company_id,
            prompt_id=prompt.id, model=model,
            prompt_hash=prompt_hash, prompt_text=prompt_text,
            scope_filter={"gathering_run_id": run_id},
            triggered_by="pipeline", status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(analysis_run)
        await session.flush()

        # Get companies with scraped text
        links = await session.execute(
            select(CompanySourceLink).where(CompanySourceLink.gathering_run_id == run_id)
        )
        company_ids = [sl.discovered_company_id for sl in links.scalars().all()]

        # Count ALL non-rejected companies (including those without scraped text)
        all_eligible = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(company_ids),
                DiscoveredCompany.status != DiscoveredCompanyStatus.REJECTED,
            )
        )
        all_eligible_list = all_eligible.scalars().all()
        total_eligible = len(all_eligible_list)
        skipped_no_text = sum(1 for dc in all_eligible_list if not dc.scraped_text)

        # Only analyze companies WITH scraped text
        dc_list = [dc for dc in all_eligible_list if dc.scraped_text]

        total = 0; targets = 0; rejected = 0; total_tokens = 0; total_cost = 0.0
        target_list = []
        BATCH_SIZE = 25   # Commit to DB every 25 results
        CONCURRENCY = 10  # Parallel GPT-4o-mini requests — proven safe rate
        import asyncio as _aio
        sem = _aio.Semaphore(CONCURRENCY)

        async def analyze_one(dc):
            """Analyze single company with semaphore for rate limiting."""
            async with sem:
                try:
                    result = await company_search_service.analyze_company(
                        content=dc.scraped_text or "", target_segments=prompt_text,
                        domain=dc.domain, is_html=False,
                        custom_system_prompt=prompt_text,
                    )
                    # Parse CAPS_LOCKED segment from matched_segment if present
                    seg = result.get("matched_segment", "")
                    if seg and seg == seg.upper() and "_" in seg:
                        # Already CAPS_LOCKED format — use as-is
                        pass
                    elif seg:
                        # Convert to CAPS_LOCKED: "real_estate" → "REAL_ESTATE"
                        result["matched_segment"] = seg.upper().replace(" ", "_")
                    return dc, result
                except Exception as e:
                    logger.error(f"Analysis failed for {dc.domain}: {e}")
                    return dc, None

        # Process in batches: fire BATCH_SIZE concurrent calls, commit, repeat
        for batch_start in range(0, len(dc_list), BATCH_SIZE):
            batch = dc_list[batch_start:batch_start + BATCH_SIZE]
            results = await _aio.gather(*[analyze_one(dc) for dc in batch])

            for dc, analysis in results:
                if not analysis:
                    continue

                is_target = analysis.get("is_target", False)
                confidence = analysis.get("confidence", 0.0)
                tokens = analysis.get("tokens_used", 0)
                cost = tokens * 0.00000015

                ar = AnalysisResult(
                    analysis_run_id=analysis_run.id, discovered_company_id=dc.id,
                    is_target=is_target, confidence=confidence,
                    segment=analysis.get("matched_segment"),
                    reasoning=analysis.get("reasoning", ""),
                    scores=analysis.get("scores"), raw_output=json.dumps(analysis),
                    tokens_used=tokens, cost_usd=cost,
                )
                session.add(ar)

                dc.is_target = is_target
                dc.confidence = confidence
                dc.reasoning = analysis.get("reasoning", "")
                dc.matched_segment = analysis.get("matched_segment")
                dc.latest_analysis_run_id = analysis_run.id
                dc.latest_analysis_verdict = is_target
                dc.latest_analysis_segment = analysis.get("matched_segment")

                if is_target:
                    dc.status = DiscoveredCompanyStatus.ANALYZED
                    targets += 1
                    target_list.append({
                        "domain": dc.domain, "name": dc.name,
                        "confidence": confidence,
                        "segment": analysis.get("matched_segment"),
                        "reasoning": (analysis.get("reasoning", ""))[:200],
                    })
                else:
                    rejected += 1

                total += 1; total_tokens += tokens; total_cost += cost

            # Commit after each batch
            analysis_run.total_analyzed = total
            analysis_run.targets_found = targets
            analysis_run.rejected_count = rejected
            analysis_run.total_tokens = total_tokens
            analysis_run.total_cost_usd = total_cost
            await session.commit()
            logger.info(f"Analysis {batch_start + len(batch)}/{len(dc_list)}: {targets} targets ({total} analyzed)")

        analysis_run.total_analyzed = total
        analysis_run.targets_found = targets
        analysis_run.rejected_count = rejected
        analysis_run.total_tokens = total_tokens
        analysis_run.total_cost_usd = total_cost
        analysis_run.status = "completed"
        analysis_run.completed_at = datetime.now(timezone.utc)
        if total > 0:
            analysis_run.avg_confidence = sum(
                r["confidence"] for r in target_list
            ) / max(targets, 1) if targets > 0 else 0

        # Update prompt stats
        if prompt.id:
            await self.update_prompt_stats(session, prompt.id)

        # Update gathering run effectiveness
        if run.new_companies_count:
            run.target_rate = targets / max(run.new_companies_count, 1)
            run.avg_analysis_confidence = analysis_run.avg_confidence

        run.current_phase = "analyzed"
        await session.flush()

        # AUTO-CREATE CHECKPOINT 2 gate
        # Store FULL target list so it survives session crashes
        sorted_targets = sorted(target_list, key=lambda x: x["confidence"], reverse=True)
        gate = ApprovalGate(
            project_id=run.project_id, gathering_run_id=run.id,
            gate_type="target_review",
            gate_label=f"Review {targets} targets ({total} analyzed, {int(targets/max(total,1)*100)}% rate)",
            scope={
                "targets_found": targets, "total_analyzed": total,
                "total_eligible": total_eligible,
                "skipped_no_scraped_text": skipped_no_text,
                "rejected": rejected,
                "analysis_run_id": analysis_run.id,
                "avg_confidence": analysis_run.avg_confidence,
                "total_cost_usd": float(total_cost),
                "target_list": sorted_targets[:500],  # cap at 500 for DB size
            },
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(gate)

        run.current_phase = "awaiting_targets_ok"
        await session.commit()

        if skipped_no_text > 0:
            logger.warning(f"Analysis: {skipped_no_text}/{total_eligible} companies skipped (no scraped text)")
        logger.info(f"Analysis: {targets}/{total} targets → CHECKPOINT 2 (gate #{gate.id})")
        return {
            "analysis_run_id": analysis_run.id,
            "total_eligible": total_eligible,
            "skipped_no_scraped_text": skipped_no_text,
            "total_analyzed": total, "targets_found": targets,
            "rejected": rejected, "avg_confidence": analysis_run.avg_confidence,
            "total_cost_usd": float(total_cost),
            "target_list": sorted(target_list, key=lambda x: x["confidence"], reverse=True),
            "checkpoint": {"gate_id": gate.id, "status": "awaiting_targets_ok",
                           "message": "Operator must review and approve target list before FindyMail."},
        }

    # ══════════════════════════════════════════════════════════
    # PHASE 6: VERIFY (FindyMail — BLOCKED until checkpoint 3)
    # ══════════════════════════════════════════════════════════

    async def prepare_verification(self, session: AsyncSession, run_id: int) -> dict:
        """After checkpoint 2 approved: calculate FindyMail cost and create CHECKPOINT 3."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        _require_phase(run, "targets_approved", "prepare verification")

        # Count emails to verify
        links = await session.execute(
            select(CompanySourceLink).where(CompanySourceLink.gathering_run_id == run_id)
        )
        company_ids = [sl.discovered_company_id for sl in links.scalars().all()]
        target_companies = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.id.in_(company_ids),
                DiscoveredCompany.is_target == True,
            )
        )
        targets = target_companies.scalars().all()
        email_count = sum(1 for t in targets if t.emails_found)  # rough estimate
        estimated_cost = max(len(targets), email_count) * 0.01  # $0.01/email

        gate = ApprovalGate(
            project_id=run.project_id, gathering_run_id=run.id,
            gate_type="findymail_cost",
            gate_label=f"Approve FindyMail: ~{len(targets)} companies, est. ${estimated_cost:.2f}",
            scope={"target_companies": len(targets), "estimated_emails": max(len(targets), email_count),
                   "estimated_cost_usd": estimated_cost},
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(gate)

        run.current_phase = "awaiting_verify_ok"
        await session.commit()

        return {
            "target_companies": len(targets),
            "estimated_cost_usd": estimated_cost,
            "checkpoint": {"gate_id": gate.id, "status": "awaiting_verify_ok",
                           "message": f"Approve FindyMail spend of ~${estimated_cost:.2f}?"},
        }

    # ══════════════════════════════════════════════════════════
    # PROMPT MANAGEMENT
    # ══════════════════════════════════════════════════════════

    async def get_or_create_prompt(
        self, session: AsyncSession, company_id: int, name: str, prompt_text: str,
        project_id: Optional[int] = None, category: str = "icp_analysis",
        model_default: str = "gpt-4o-mini", created_by: Optional[str] = None,
    ) -> GatheringPrompt:
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        existing = await session.execute(
            select(GatheringPrompt).where(GatheringPrompt.prompt_hash == prompt_hash)
        )
        prompt = existing.scalar_one_or_none()
        if prompt:
            return prompt

        prompt = GatheringPrompt(
            company_id=company_id, project_id=project_id, name=name,
            prompt_text=prompt_text, prompt_hash=prompt_hash,
            category=category, model_default=model_default, created_by=created_by,
        )
        session.add(prompt)
        await session.flush()
        return prompt

    async def list_prompts(
        self, session: AsyncSession, company_id: int,
        project_id: Optional[int] = None, category: Optional[str] = None,
    ) -> List[GatheringPrompt]:
        query = select(GatheringPrompt).where(
            GatheringPrompt.company_id == company_id, GatheringPrompt.is_active == True,
        )
        if project_id:
            query = query.where(
                (GatheringPrompt.project_id == project_id) | (GatheringPrompt.project_id.is_(None))
            )
        if category:
            query = query.where(GatheringPrompt.category == category)
        return (await session.execute(query.order_by(GatheringPrompt.usage_count.desc()))).scalars().all()

    async def update_prompt_stats(self, session: AsyncSession, prompt_id: int) -> None:
        runs = await session.execute(
            select(AnalysisRun).where(AnalysisRun.prompt_id == prompt_id, AnalysisRun.status == "completed")
        )
        completed = runs.scalars().all()
        if not completed:
            return
        prompt = await session.get(GatheringPrompt, prompt_id)
        if not prompt:
            return
        prompt.usage_count = len(completed)
        prompt.total_companies_analyzed = sum(r.total_analyzed or 0 for r in completed)
        total_targets = sum(r.targets_found or 0 for r in completed)
        if prompt.total_companies_analyzed > 0:
            prompt.avg_target_rate = total_targets / prompt.total_companies_analyzed
        confidences = [r.avg_confidence for r in completed if r.avg_confidence is not None]
        if confidences:
            prompt.avg_confidence = sum(confidences) / len(confidences)

    # ══════════════════════════════════════════════════════════
    # READ OPERATIONS
    # ══════════════════════════════════════════════════════════

    async def get_run_detail(self, session: AsyncSession, run_id: int) -> Optional[GatheringRun]:
        return await session.get(GatheringRun, run_id)

    async def get_runs(
        self, session: AsyncSession, project_id: int,
        source_type: Optional[str] = None, status: Optional[str] = None,
        page: int = 1, page_size: int = 50,
    ) -> List[GatheringRun]:
        query = select(GatheringRun).where(GatheringRun.project_id == project_id).order_by(GatheringRun.created_at.desc())
        if source_type:
            query = query.where(GatheringRun.source_type == source_type)
        if status:
            query = query.where(GatheringRun.status == status)
        return (await session.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    async def get_run_companies(
        self, session: AsyncSession, run_id: int, page: int = 1, page_size: int = 50,
    ) -> List[DiscoveredCompany]:
        query = (
            select(DiscoveredCompany)
            .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
            .where(CompanySourceLink.gathering_run_id == run_id)
            .order_by(CompanySourceLink.source_rank)
            .offset((page - 1) * page_size).limit(page_size)
        )
        return (await session.execute(query)).scalars().all()

    async def get_company_scrapes(
        self, session: AsyncSession, discovered_company_id: int, current_only: bool = True,
    ) -> List[CompanyScrape]:
        query = select(CompanyScrape).where(CompanyScrape.discovered_company_id == discovered_company_id)
        if current_only:
            query = query.where(CompanyScrape.is_current == True)
        return (await session.execute(query.order_by(CompanyScrape.page_path, CompanyScrape.version.desc()))).scalars().all()

    async def get_pending_gates(self, session: AsyncSession, project_id: int) -> List[ApprovalGate]:
        return (await session.execute(
            select(ApprovalGate).where(ApprovalGate.project_id == project_id, ApprovalGate.status == "pending")
            .order_by(ApprovalGate.created_at.desc())
        )).scalars().all()

    async def get_analysis_runs(
        self, session: AsyncSession, project_id: int, page: int = 1, page_size: int = 50,
    ) -> List[AnalysisRun]:
        return (await session.execute(
            select(AnalysisRun).where(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

    async def compare_analysis_runs(self, session: AsyncSession, run_a_id: int, run_b_id: int) -> dict:
        results_a = {r.discovered_company_id: r for r in
            (await session.execute(select(AnalysisResult).where(AnalysisResult.analysis_run_id == run_a_id))).scalars().all()}
        results_b = {r.discovered_company_id: r for r in
            (await session.execute(select(AnalysisResult).where(AnalysisResult.analysis_run_id == run_b_id))).scalars().all()}

        all_ids = set(results_a.keys()) | set(results_b.keys())
        agreements = disagreements = only_a = only_b = 0
        details = []
        for cid in all_ids:
            a, b = results_a.get(cid), results_b.get(cid)
            if a and b:
                if a.is_target == b.is_target:
                    agreements += 1
                else:
                    disagreements += 1
                    details.append({"discovered_company_id": cid,
                        "run_a_target": a.is_target, "run_a_confidence": a.confidence,
                        "run_b_target": b.is_target, "run_b_confidence": b.confidence})
            elif a: only_a += 1
            else: only_b += 1

        return {"run_a_id": run_a_id, "run_b_id": run_b_id, "total_compared": len(all_ids),
                "agreements": agreements, "disagreements": disagreements,
                "only_in_a": only_a, "only_in_b": only_b, "disagreement_details": details}

    # ══════════════════════════════════════════════════════════
    # CANCEL + RE-ANALYZE
    # ══════════════════════════════════════════════════════════

    async def cancel_run(self, session: AsyncSession, run_id: int, reason: str = "") -> GatheringRun:
        """Cancel a gathering run at any phase. Sets status to cancelled."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        if run.current_phase == "pushed":
            raise ValueError(f"Run #{run_id} is already completed (pushed)")

        # Cancel any pending gates for this run
        pending_gates = await session.execute(
            select(ApprovalGate).where(
                ApprovalGate.gathering_run_id == run_id,
                ApprovalGate.status == "pending",
            )
        )
        for gate in pending_gates.scalars().all():
            gate.status = "rejected"
            gate.decision_note = f"Run cancelled: {reason}"
            gate.decided_at = datetime.now(timezone.utc)

        run.status = "cancelled"
        run.error_message = reason or "Cancelled by operator"
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)
        logger.info(f"Run #{run_id} cancelled at phase '{run.current_phase}': {reason}")
        return run

    async def re_analyze(
        self, session: AsyncSession, run_id: int,
        model: str = "gpt-4o-mini", prompt_text: str = "",
        prompt_name: Optional[str] = None,
    ) -> dict:
        """Re-run analysis with a different prompt. Only allowed at CP2 (awaiting_targets_ok).
        Rejects the current CP2 gate, resets to 'scraped', runs new analysis."""
        run = await session.get(GatheringRun, run_id)
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        if run.current_phase != "awaiting_targets_ok":
            raise ValueError(
                f"Re-analyze only allowed at checkpoint 2 (awaiting_targets_ok). "
                f"Run #{run_id} is at '{run.current_phase}'."
            )

        # Reject the current CP2 gate
        pending_gates = await session.execute(
            select(ApprovalGate).where(
                ApprovalGate.gathering_run_id == run_id,
                ApprovalGate.gate_type == "target_review",
                ApprovalGate.status == "pending",
            )
        )
        for gate in pending_gates.scalars().all():
            gate.status = "rejected"
            gate.decision_note = "Re-analyzing with different prompt"
            gate.decided_at = datetime.now(timezone.utc)

        # Reset phase to scraped so run_analysis can execute
        run.current_phase = "scraped"
        await session.commit()

        # Run new analysis (creates new AnalysisRun + new CP2 gate)
        return await self.run_analysis(session, run_id, model=model, prompt_text=prompt_text, prompt_name=prompt_name)

    # ══════════════════════════════════════════════════════════
    # MATERIALIZED VIEW REFRESH
    # ══════════════════════════════════════════════════════════

    @staticmethod
    async def refresh_active_campaign_domains(session: AsyncSession) -> None:
        try:
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY active_campaign_domains"))
            await session.commit()
            logger.info("Refreshed active_campaign_domains")
        except Exception as e:
            logger.warning(f"Mat view refresh failed: {e}")


gathering_service = GatheringService()
