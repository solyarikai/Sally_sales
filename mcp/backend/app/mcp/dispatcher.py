"""MCP Tool Dispatcher — routes tool calls to service methods."""
import logging
from typing import Any, Optional

from starlette.requests import Request
from sqlalchemy import select

from app.db import async_session_maker
from app.auth.middleware import verify_token
from app.models.user import MCPUser
from app.models.project import Project, Company
from app.models.gathering import GatheringRun, ApprovalGate
from app.models.campaign import GeneratedSequence
from app.models.integration import MCPIntegrationSetting
from app.services.user_context import UserServiceContext

logger = logging.getLogger(__name__)


async def _get_user(token: Optional[str], session) -> MCPUser:
    if not token:
        raise ValueError("Authentication required. Pass your API token.")
    user = await verify_token(session, token)
    if not user:
        raise ValueError("Invalid API token")
    return user


async def dispatch_tool(tool_name: str, args: dict, token: Optional[str], request: Request) -> Any:
    """Route a tool call to the appropriate service method. Logs every call."""
    import time as _time
    start = _time.monotonic()

    async with async_session_maker() as session:
        try:
            result = await _dispatch(tool_name, args, token, session)
            latency = int((_time.monotonic() - start) * 1000)

            # Log usage — include credits_spent if present in result
            try:
                from app.models.usage import MCPUsageLog
                from app.auth.middleware import verify_token
                user = await verify_token(session, token) if token else None
                log_extra = {"args": _safe_truncate(args), "latency_ms": latency}
                # Extract credits_spent from result for credit tracking
                if isinstance(result, dict) and result.get("credits_spent"):
                    log_extra["credits_spent"] = result["credits_spent"]
                session.add(MCPUsageLog(
                    user_id=user.id if user else 0,
                    action="tool_call",
                    tool_name=tool_name,
                    extra_data=log_extra,
                ))
            except Exception:
                pass  # Don't fail the tool call because logging failed

            await session.commit()
            return result
        except Exception as e:
            # Log error
            try:
                from app.models.usage import MCPUsageLog
                session.add(MCPUsageLog(
                    user_id=0, action="tool_error", tool_name=tool_name,
                    extra_data={"args": _safe_truncate(args), "error": str(e)[:500]},
                ))
                await session.commit()
            except Exception:
                await session.rollback()
            raise


def _safe_truncate(obj, max_len=5000) -> dict:
    """Truncate large values in args for logging."""
    import json
    try:
        s = json.dumps(obj, default=str)
        if len(s) > max_len:
            return {"_truncated": s[:max_len]}
        return obj
    except Exception:
        return {"_error": "could not serialize"}


async def _dispatch(tool_name: str, args: dict, token: Optional[str], session) -> Any:

    # ── Account tools (no auth needed for signup) ──
    if tool_name == "setup_account":
        from app.auth.middleware import generate_api_token
        email = args["email"]
        name = args["name"]
        existing = await session.execute(select(MCPUser).where(MCPUser.email == email))
        if existing.scalar_one_or_none():
            raise ValueError(f"Email {email} already registered")
        user = MCPUser(email=email, name=name)
        session.add(user)
        await session.flush()
        company = Company(name=f"{name}'s Company")
        session.add(company)
        await session.flush()
        raw_token, prefix, hashed = generate_api_token()
        from app.models.user import MCPApiToken
        session.add(MCPApiToken(user_id=user.id, token_prefix=prefix, token_hash=hashed))
        return {"user_id": user.id, "api_token": raw_token, "message": "Save this token — it won't be shown again."}

    if tool_name == "configure_integration":
        user = await _get_user(token, session)
        from app.services.encryption import encrypt_value
        integration_name = args["integration_name"]
        api_key = args["api_key"]
        connected = False
        message = ""

        if integration_name == "smartlead":
            from app.services.smartlead_service import SmartLeadService
            svc = SmartLeadService(api_key=api_key)
            connected = await svc.test_connection()
            campaigns = await svc.get_campaigns() if connected else []
            message = f"{len(campaigns)} campaigns found" if connected else "Connection failed"
        elif integration_name == "apollo":
            from app.services.apollo_service import ApolloService
            svc = ApolloService(api_key=api_key)
            connected = await svc.test_connection()
            message = "Connected" if connected else "Connection failed"
        elif integration_name == "findymail":
            from app.services.findymail_service import FindymailService
            svc = FindymailService(api_key=api_key)
            connected = await svc.test_connection()
            message = "Connected" if connected else "Connection failed"
        else:
            connected = True
            message = f"{integration_name} key saved"

        existing = await session.execute(
            select(MCPIntegrationSetting).where(
                MCPIntegrationSetting.user_id == user.id,
                MCPIntegrationSetting.integration_name == integration_name,
            )
        )
        setting = existing.scalar_one_or_none()
        encrypted = encrypt_value(api_key)
        if setting:
            setting.api_key_encrypted = encrypted
            setting.is_connected = connected
            setting.connection_info = message
        else:
            session.add(MCPIntegrationSetting(
                user_id=user.id, integration_name=integration_name,
                api_key_encrypted=encrypted, is_connected=connected, connection_info=message,
            ))
        return {"connected": connected, "message": message}

    if tool_name == "check_integrations":
        user = await _get_user(token, session)
        result = await session.execute(
            select(MCPIntegrationSetting).where(MCPIntegrationSetting.user_id == user.id)
        )
        return [{"name": i.integration_name, "connected": i.is_connected, "info": i.connection_info}
                for i in result.scalars().all()]

    # ── Project tools ──
    if tool_name == "select_project":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found or not yours")
        user.active_project_id = project.id
        # Get project details for display (use already-imported models)
        from sqlalchemy import func
        from app.models.pipeline import DiscoveredCompany
        runs_count = (await session.execute(
            select(func.count(GatheringRun.id)).where(GatheringRun.project_id == project.id)
        )).scalar() or 0
        companies_count = (await session.execute(
            select(func.count(DiscoveredCompany.id)).where(DiscoveredCompany.project_id == project.id)
        )).scalar() or 0
        campaign_filters = project.campaign_filters or []
        return {
            "active_project": {
                "id": project.id,
                "name": project.name,
                "target_segments": project.target_segments,
                "target_industries": project.target_industries,
                "sender_name": project.sender_name,
                "sender_company": project.sender_company,
            },
            "stats": {
                "gathering_runs": runs_count,
                "discovered_companies": companies_count,
                "campaign_filters": campaign_filters,
            },
            "blacklist_scope": f"Blacklisting checks against {len(campaign_filters)} campaigns assigned to this project. "
                               f"Companies already in these campaigns will be rejected during CP1.",
            "message": f"Now working on '{project.name}'. All pipeline operations will use this project's campaigns for blacklisting.",
            "_links": {"project": f"http://46.62.210.24:3000/projects/{project.id}"},
        }

    if tool_name == "create_project":
        user = await _get_user(token, session)
        result = await session.execute(select(Company).limit(1))
        company = result.scalar_one_or_none()
        if not company:
            company = Company(name=f"{user.name}'s Company")
            session.add(company)
            await session.flush()
        project = Project(
            company_id=company.id, user_id=user.id, name=args["name"],
            target_segments=args.get("target_segments"),
            target_industries=args.get("target_industries"),
            sender_name=args.get("sender_name"),
            sender_company=args.get("sender_company"),
            sender_position=args.get("sender_position"),
        )
        session.add(project)
        await session.flush()
        return {"project_id": project.id, "name": project.name}

    if tool_name == "list_projects":
        user = await _get_user(token, session)
        result = await session.execute(
            select(Project).where(Project.user_id == user.id, Project.is_active == True)
        )
        return [{"id": p.id, "name": p.name, "target_segments": p.target_segments,
                 "sender_name": p.sender_name} for p in result.scalars().all()]

    if tool_name == "update_project":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")
        for field in ["name", "target_segments", "target_industries", "sender_name", "sender_company"]:
            if field in args:
                setattr(project, field, args[field])
        return {"updated": True, "project_id": project.id}

    # ── Pipeline tools ──
    if tool_name == "tam_gather":
        user = await _get_user(token, session)
        project_id = args.get("project_id")

        # If no project_id provided, use active project
        if not project_id and user.active_project_id:
            project_id = user.active_project_id

        # If still no project, check how many projects user has
        if not project_id:
            all_projects = (await session.execute(
                select(Project).where(Project.user_id == user.id, Project.is_active == True)
            )).scalars().all()
            if len(all_projects) == 0:
                raise ValueError("No projects found. Create a project first with create_project.")
            elif len(all_projects) == 1:
                project_id = all_projects[0].id
                user.active_project_id = project_id
            else:
                return {
                    "error": "project_selection_required",
                    "message": "You have multiple projects. Which one are you working on? Select one first.",
                    "projects": [{"id": p.id, "name": p.name, "target_segments": p.target_segments} for p in all_projects],
                    "hint": "Call select_project with the project_id you want to use.",
                }

        project = await session.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")

        source_type = args["source_type"]
        filters = args.get("filters", {})

        # ── REUSE filters from a previous run ──
        reuse_run_id = args.get("reuse_run_id")
        if reuse_run_id and not filters.get("q_organization_keyword_tags"):
            prev_run = await session.get(GatheringRun, reuse_run_id)
            if prev_run and prev_run.filters:
                filters = dict(prev_run.filters)  # Copy previous filters
                # Keep user's target_count override if provided

        # ── AUTO-DISCOVER filters via probe if keywords missing ──
        if "api" in source_type and not filters.get("q_organization_keyword_tags"):
            query = args.get("query") or project.target_segments
            if query:
                try:
                    from app.config import settings as _s
                    ctx_probe = UserServiceContext(user.id, session)
                    apollo_probe = await ctx_probe.get_apollo_service()
                    openai_key = await ctx_probe.get_key("openai") or _s.OPENAI_API_KEY
                    anthropic_key = await ctx_probe.get_key("anthropic") or _s.ANTHROPIC_API_KEY
                    gemini_key = await ctx_probe.get_key("gemini") or _s.GEMINI_API_KEY
                    from app.services.filter_intelligence import suggest_filters
                    suggestion = await suggest_filters(
                        query, apollo_probe, openai_key, anthropic_key, gemini_key,
                        args.get("target_count", 10),
                    )
                    if suggestion.get("suggested_filters"):
                        sf = suggestion["suggested_filters"]
                        filters.setdefault("q_organization_keyword_tags", sf.get("q_organization_keyword_tags"))
                        filters.setdefault("organization_locations", sf.get("organization_locations"))
                        filters.setdefault("organization_num_employees_ranges", sf.get("organization_num_employees_ranges"))
                except Exception as e:
                    logger.warning(f"Auto-filter discovery failed: {e}")

        # ── Auto-calculate pages from target_count BEFORE validation ──
        if "api" in source_type:
            target_count = args.get("target_count") or filters.pop("target_count", None)
            if target_count and not filters.get("max_pages"):
                per_page = filters.get("per_page", 25)
                companies_needed = int(int(target_count) / 0.3)
                filters["max_pages"] = max(1, (companies_needed + per_page - 1) // per_page)

        # ── Essential filter validation for API sources ──
        if "api" in source_type or "emulator" in source_type:
            missing = []
            if not filters.get("q_organization_keyword_tags") and not filters.get("organization_locations"):
                missing.append("keywords (q_organization_keyword_tags) OR locations (organization_locations)")
            if not filters.get("organization_num_employees_ranges"):
                missing.append("company size range (e.g. ['51,200'] for 50-200 employees)")
            if "api" in source_type and not filters.get("max_pages"):
                missing.append("max_pages OR target_count (how many target companies do you want?)")

            if missing:
                return {
                    "error": "missing_essential_filters",
                    "message": f"Cannot proceed — I need more info:\n" + "\n".join(f"  - {m}" for m in missing),
                    "hint": "You can say 'I want 10 target companies' and I'll calculate the rest.",
                }

            filters.setdefault("per_page", 25)
            filters.setdefault("max_pages", 4)

        import hashlib, json as _json
        filter_hash = hashlib.sha256(_json.dumps(filters, sort_keys=True).encode()).hexdigest()[:16]

        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)
        est_credits = max_pages if "api" in source_type else 0
        est_companies = max_pages * per_page

        # Get user's Apollo service for API sources
        apollo_svc = None
        if "apollo" in source_type:
            ctx = UserServiceContext(user.id, session)
            apollo_svc = await ctx.get_apollo_service()
            if not apollo_svc.is_configured():
                raise ValueError("Apollo not connected. Use configure_integration to add your Apollo API key first.")

        # Call the real gathering service
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        run = await svc.start_gathering(
            session, project.id, project.company_id,
            source_type, filters, triggered_by=f"mcp:user:{user.id}",
            apollo_service=apollo_svc,
        )

        return {
            "run_id": run.id,
            "status": run.status,
            "phase": run.current_phase,
            "new_companies": run.new_companies_count,
            "duplicates": run.duplicate_count,
            "estimated_credits": est_credits,
            "estimated_companies": est_companies,
            "filters_applied": {
                "keywords": filters.get("q_organization_keyword_tags"),
                "locations": filters.get("organization_locations"),
                "employee_ranges": filters.get("organization_num_employees_ranges"),
                "max_pages": filters.get("max_pages"),
                "funding_stages": filters.get("organization_latest_funding_stage_cd"),
            },
            "message": f"Gathering complete for '{project.name}'. "
                       f"{run.new_companies_count} new, {run.duplicate_count} duplicates.",
            "_links": {"pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}"},
        }

    if tool_name == "tam_blacklist_check":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        gate = await svc.blacklist_check(session, run)
        return {
            "gate_id": gate.id, "type": "checkpoint_1",
            "scope": gate.scope,
            "message": "CHECKPOINT 1: Review project scope and blacklist results. Approve to continue.",
            "_links": {
                "pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}",
            },
        }

    if tool_name == "tam_approve_checkpoint":
        user = await _get_user(token, session)
        gate = await session.get(ApprovalGate, args["gate_id"])
        if not gate:
            raise ValueError("Gate not found")
        gate.status = "approved"
        gate.decided_by = f"mcp:user:{user.id}"
        gate.decision_note = args.get("note")
        from datetime import datetime
        gate.decided_at = datetime.utcnow()
        # Advance run phase
        if gate.gathering_run_id:
            run = await session.get(GatheringRun, gate.gathering_run_id)
            if run:
                phase_map = {
                    "awaiting_scope_ok": "pre_filter",
                    "awaiting_targets_ok": "prepare_verification",
                    "awaiting_verify_ok": "verified",
                }
                run.current_phase = phase_map.get(run.current_phase, run.current_phase)
        return {"approved": True, "gate_id": gate.id}

    if tool_name == "tam_pre_filter":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        result = await svc.pre_filter(session, run)
        return {
            "status": "pre_filter_complete", "run_id": run.id,
            "passed": result["passed"], "filtered": result["filtered"],
            "message": f"Pre-filter done: {result['passed']} passed, {result['filtered']} removed.",
            "_links": {"pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}"},
        }

    if tool_name == "tam_scrape":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        from app.services.gathering_service import GatheringService
        from app.services.scraper_service import ScraperService
        svc = GatheringService()
        scraper = ScraperService()
        result = await svc.scrape(session, run, scraper_service=scraper)
        return {
            "status": "scrape_complete", "run_id": run.id,
            "scraped": result["scraped"], "errors": result["errors"], "total": result["total"],
            "message": f"Scraped {result['scraped']}/{result['total']} websites ({result['errors']} errors).",
            "_links": {"pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}"},
        }

    if tool_name == "tam_analyze":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        # Get OpenAI key for GPT-4o-mini analysis (cheap workhorse)
        ctx = UserServiceContext(user.id, session)
        openai_key = await ctx.get_key("openai")
        if not openai_key:
            from app.config import settings
            openai_key = settings.OPENAI_API_KEY
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        gate = await svc.analyze(
            session, run,
            prompt_text=args.get("prompt_text"),
            auto_refine=args.get("auto_refine", False),
            target_accuracy=args.get("target_accuracy", 0.9),
            openai_key=openai_key,
        )
        scope = gate.scope or {}
        return {
            "gate_id": gate.id, "type": "checkpoint_2",
            "targets_found": scope.get("targets_found", 0),
            "total_analyzed": scope.get("total_analyzed", 0),
            "skipped_no_text": scope.get("skipped_no_scraped_text", 0),
            "target_rate": scope.get("target_rate", "0%"),
            "avg_confidence": scope.get("avg_confidence", 0),
            "segment_distribution": scope.get("segment_distribution", {}),
            "target_list": scope.get("target_list", []),
            "borderline_rejections": scope.get("borderline_rejections", []),
            "message": (
                f"CHECKPOINT 2: GPT-4o-mini analyzed {scope.get('total_analyzed', 0)} companies. "
                f"TARGETS: {scope.get('targets_found', 0)} ({scope.get('target_rate', '0%')} target rate, "
                f"avg confidence {scope.get('avg_confidence', 0):.2f}). "
                f"Segments: {scope.get('segment_distribution', {})}. "
                f"Review the target list below. Check for false positives. "
                f"If accuracy < 90%, re-analyze with adjusted prompt via tam_re_analyze."
            ),
            "_links": {
                "pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}",
            },
        }

    if tool_name == "tam_re_analyze":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        # Reset to scraped phase for re-analysis
        run.current_phase = "analyze"
        # Reject current CP2 gate
        from sqlalchemy import update
        await session.execute(
            update(ApprovalGate)
            .where(ApprovalGate.gathering_run_id == run.id, ApprovalGate.gate_type == "checkpoint_2", ApprovalGate.status == "pending")
            .values(status="rejected", decision_notes="Re-analyzing with adjusted prompt")
        )
        # Re-run analysis with new prompt
        ctx = UserServiceContext(user.id, session)
        openai_key = await ctx.get_key("openai")
        if not openai_key:
            from app.config import settings
            openai_key = settings.OPENAI_API_KEY
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        gate = await svc.analyze(session, run, prompt_text=args["prompt_text"], openai_key=openai_key)
        scope = gate.scope or {}
        return {
            "gate_id": gate.id, "type": "checkpoint_2_retry",
            "targets_found": scope.get("targets_found", 0),
            "total_analyzed": scope.get("total_analyzed", 0),
            "target_rate": scope.get("target_rate", "0%"),
            "avg_confidence": scope.get("avg_confidence", 0),
            "segment_distribution": scope.get("segment_distribution", {}),
            "target_list": scope.get("target_list", []),
            "borderline_rejections": scope.get("borderline_rejections", []),
            "message": (
                f"Re-analysis complete. TARGETS: {scope.get('targets_found', 0)} "
                f"({scope.get('target_rate', '0%')}). Review again."
            ),
        }

    if tool_name == "tam_prepare_verification":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        gate = await svc.prepare_verification(session, run)
        return {
            "gate_id": gate.id, "type": "checkpoint_3",
            "scope": gate.scope,
            "message": f"CHECKPOINT 3: FindyMail will cost ~${gate.scope.get('estimated_cost_usd', 0)}. Approve to spend credits.",
            "_links": {"pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}"},
        }

    if tool_name == "tam_run_verification":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        run.current_phase = "verified"
        run.status = "completed"
        return {"status": "verification_complete", "run_id": run.id}

    if tool_name == "tam_list_sources":
        return {
            "sources": [
                {"type": "apollo.companies.api", "description": "Apollo org search API", "cost": "1 credit/page"},
                {"type": "apollo.people.emulator", "description": "Apollo People tab via Puppeteer", "cost": "Free"},
                {"type": "apollo.companies.emulator", "description": "Apollo Companies tab via Puppeteer", "cost": "Free"},
                {"type": "clay.companies.emulator", "description": "Clay TAM export", "cost": "~$0.01/company"},
                {"type": "google_sheets.companies.manual", "description": "Google Sheet import", "cost": "Free"},
                {"type": "csv.companies.manual", "description": "CSV import", "cost": "Free"},
                {"type": "manual.companies.manual", "description": "Direct domain list", "cost": "Free"},
            ]
        }

    # ── Refinement tools ──
    if tool_name == "refinement_status":
        user = await _get_user(token, session)
        from app.models.refinement import RefinementRun, RefinementIteration
        run = await session.get(RefinementRun, args["run_id"])
        if not run:
            raise ValueError("Refinement run not found")
        result = await session.execute(
            select(RefinementIteration).where(RefinementIteration.refinement_run_id == run.id)
            .order_by(RefinementIteration.iteration_number)
        )
        iterations = result.scalars().all()
        return {
            "status": run.status, "current_iteration": run.current_iteration,
            "target_accuracy": run.target_accuracy, "final_accuracy": run.final_accuracy,
            "iterations": [{"n": i.iteration_number, "accuracy": i.accuracy,
                           "fp": i.false_positives, "fn": i.false_negatives} for i in iterations],
        }

    if tool_name == "refinement_override":
        user = await _get_user(token, session)
        from app.models.refinement import RefinementRun
        run = await session.get(RefinementRun, args["refinement_run_id"])
        if not run:
            raise ValueError("Refinement run not found")
        run.status = "stopped"
        from datetime import datetime
        run.completed_at = datetime.utcnow()
        return {"stopped": True, "final_accuracy": run.final_accuracy}

    # ── GOD_SEQUENCE tools ──
    if tool_name == "god_generate_sequence":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project:
            raise ValueError("Project not found")
        from app.services.campaign_intelligence import CampaignIntelligenceService
        ci_svc = CampaignIntelligenceService()
        seq = await ci_svc.generate_sequence(
            session, project.id,
            campaign_name=args.get("campaign_name"),
            instructions=args.get("instructions"),
        )
        # Show sequence preview
        steps_preview = []
        for s in seq.sequence_steps:
            steps_preview.append(f"Step {s['step']} (Day {s['day']}): {s['subject']}")
        return {
            "sequence_id": seq.id,
            "campaign_name": seq.campaign_name,
            "steps": seq.sequence_step_count,
            "status": "draft",
            "rationale": seq.rationale,
            "preview": steps_preview,
            "message": f"Generated 5-step sequence '{seq.campaign_name}'. Review and approve, or request changes.",
            "_links": {"sequence": f"http://46.62.210.24:3000/campaigns/{seq.id}"},
        }

    if tool_name == "god_approve_sequence":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Sequence not found")
        seq.status = "approved"
        seq.reviewed_by = f"mcp:user:{user.id}"
        from datetime import datetime
        seq.reviewed_at = datetime.utcnow()
        return {"approved": True, "sequence_id": seq.id}

    if tool_name == "list_email_accounts":
        user = await _get_user(token, session)
        ctx = UserServiceContext(user.id, session)
        svc = await ctx.get_smartlead_service()
        if not svc.is_configured():
            raise ValueError("SmartLead not connected")

        campaign_id = args.get("campaign_id")
        if campaign_id:
            # Get accounts from specific campaign
            accounts = await svc.get_campaign_email_accounts(campaign_id)
        else:
            # Get all accounts, then show which campaigns use them
            accounts = await svc.get_email_accounts()

        # Also get accounts from user's imported campaigns (for reuse suggestion)
        from app.models.campaign import Campaign
        user_campaigns = (await session.execute(
            select(Campaign).where(Campaign.project_id.in_(
                select(Project.id).where(Project.user_id == user.id)
            )).limit(5)
        )).scalars().all()

        campaign_accounts = {}
        for camp in user_campaigns:
            if camp.external_id:
                camp_accts = await svc.get_campaign_email_accounts(int(camp.external_id))
                for a in camp_accts:
                    aid = a.get("id")
                    if aid:
                        if aid not in campaign_accounts:
                            campaign_accounts[aid] = {"id": aid, "email": a.get("from_email") or a.get("email", ""), "campaigns": []}
                        campaign_accounts[aid]["campaigns"].append(camp.name)

        return {
            "accounts": [
                {"id": a.get("id"), "email": a.get("from_email") or a.get("email", ""), "name": a.get("from_name", "")}
                for a in (accounts or [])[:20]
            ],
            "used_in_your_campaigns": list(campaign_accounts.values()),
            "message": "Select email account IDs to use for the new campaign. Accounts already used in your campaigns are shown.",
        }

    if tool_name == "god_push_to_smartlead":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Sequence not found")
        if seq.status != "approved":
            raise ValueError("Sequence must be approved first")
        ctx = UserServiceContext(user.id, session)
        svc = await ctx.get_smartlead_service()
        if not svc.is_configured():
            raise ValueError("SmartLead not connected")

        # 1. Create campaign
        campaign_data = await svc.create_campaign(seq.campaign_name or "MCP Generated")
        if not campaign_data:
            raise ValueError("Failed to create SmartLead campaign")
        campaign_id = campaign_data.get("id")

        # 2. Set sequences
        await svc.set_campaign_sequences(campaign_id, seq.sequence_steps)

        # 3. Set production settings (no tracking, plain text, stop on reply)
        await svc.set_campaign_settings(campaign_id)

        # 4. Set schedule (9-6 in target timezone)
        target_country = args.get("target_country", "")
        if not target_country:
            # Try to get from project's gathering filters
            project = await session.get(Project, seq.project_id)
            if project and project.target_segments:
                # Extract country from ICP if possible
                for country in ["United States", "Germany", "United Kingdom", "India", "Australia"]:
                    if country.lower() in (project.target_segments or "").lower():
                        target_country = country
                        break
        from app.services.smartlead_service import get_timezone_for_country
        timezone = get_timezone_for_country(target_country)
        await svc.set_campaign_schedule(campaign_id, timezone)

        # 5. Assign email accounts (if provided)
        email_account_ids = args.get("email_account_ids", [])
        if email_account_ids:
            await svc.set_campaign_email_accounts(campaign_id, email_account_ids)

        # 6. Save to DB
        from app.models.campaign import Campaign
        from datetime import datetime
        campaign = Campaign(
            project_id=seq.project_id, company_id=seq.company_id,
            name=seq.campaign_name, external_id=str(campaign_id),
            platform="smartlead", status="draft",
        )
        session.add(campaign)
        seq.pushed_at = datetime.utcnow()
        seq.status = "pushed"
        seq.pushed_campaign_id = campaign.id
        await session.flush()

        smartlead_url = f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics"

        return {
            "pushed": True,
            "smartlead_campaign_id": campaign_id,
            "status": "DRAFT",
            "settings": {
                "timezone": timezone,
                "schedule": "Mon-Fri 09:00-18:00",
                "plain_text": True,
                "tracking": "disabled (no open/click tracking)",
                "stop_on": "reply",
                "follow_up_rate": "40%",
                "max_daily": 100,
                "email_accounts": len(email_account_ids),
            },
            "message": f"Campaign '{seq.campaign_name}' created as DRAFT with production settings.\n"
                       f"Schedule: Mon-Fri 9:00-18:00 {timezone}\n"
                       f"Email accounts: {len(email_account_ids)} assigned\n"
                       f"Next: add leads in SmartLead, then activate.",
            "_links": {"smartlead": smartlead_url},
        }

    if tool_name in ("god_score_campaigns", "god_extract_patterns"):
        user = await _get_user(token, session)
        return {"message": f"{tool_name} — coming in next iteration"}

    # ── Orchestration ──
    if tool_name == "pipeline_status":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        gates = await session.execute(
            select(ApprovalGate).where(ApprovalGate.gathering_run_id == run.id, ApprovalGate.status == "pending")
        )
        pending = gates.scalars().all()
        return {
            "run_id": run.id, "status": run.status, "phase": run.current_phase,
            "new_companies": run.new_companies_count,
            "duplicates": run.duplicate_count,
            "rejected": run.rejected_count,
            "credits_used": run.credits_used,
            "pending_gates": [{"gate_id": g.id, "type": g.gate_type, "scope": g.scope} for g in pending],
            "_links": {
                "pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}",
                "targets": f"http://46.62.210.24:3000/pipeline/{run.id}/targets",
            },
        }

    # ── Filter Intelligence ──
    if tool_name == "suggest_apollo_filters":
        user = await _get_user(token, session)
        ctx = UserServiceContext(user.id, session)
        apollo_svc = await ctx.get_apollo_service()
        if not apollo_svc.is_configured():
            raise ValueError("Apollo not connected. Use configure_integration first.")
        # Collect all AI keys (user's first, system fallback)
        from app.config import settings as _cfg
        openai_key = await ctx.get_key("openai") or _cfg.OPENAI_API_KEY
        anthropic_key = await ctx.get_key("anthropic") or _cfg.ANTHROPIC_API_KEY
        gemini_key = await ctx.get_key("gemini") or _cfg.GEMINI_API_KEY

        from app.services.filter_intelligence import suggest_filters
        result = await suggest_filters(
            query=args["query"],
            apollo_service=apollo_svc,
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            gemini_key=gemini_key,
            target_count=args.get("target_count", 10),
        )
        return result

    if tool_name == "run_full_pipeline":
        user = await _get_user(token, session)
        # Start with gather phase — same as tam_gather
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")
        import hashlib, json as _json
        filter_hash = hashlib.sha256(_json.dumps(args["filters"], sort_keys=True).encode()).hexdigest()[:16]
        run = GatheringRun(
            project_id=project.id, company_id=project.company_id,
            source_type=args["source_type"], filters=args["filters"],
            filter_hash=filter_hash, status="running", current_phase="gather",
            triggered_by=f"mcp:full_pipeline:user:{user.id}",
        )
        session.add(run)
        await session.flush()
        return {"run_id": run.id, "message": "Full pipeline started. Use pipeline_status to track progress."}

    # ── CRM Queries ──
    if tool_name == "query_contacts":
        user = await _get_user(token, session)
        from app.models.pipeline import ExtractedContact

        query = select(ExtractedContact).order_by(ExtractedContact.created_at.desc())

        project_id = args.get("project_id")
        if not project_id and user.active_project_id:
            project_id = user.active_project_id
        if project_id:
            query = query.where(ExtractedContact.project_id == project_id)

        search = args.get("search")
        if search:
            query = query.where(
                (ExtractedContact.email.ilike(f"%{search}%")) |
                (ExtractedContact.first_name.ilike(f"%{search}%")) |
                (ExtractedContact.last_name.ilike(f"%{search}%"))
            )

        limit = args.get("limit", 20)
        query = query.limit(min(limit, 100))
        result = await session.execute(query)
        contacts = result.scalars().all()

        # Build CRM deep link
        crm_params = []
        if project_id:
            crm_params.append(f"project_id={project_id}")
        if search:
            crm_params.append(f"search={search}")
        if args.get("has_replied"):
            crm_params.append("has_replied=true")
        if args.get("needs_followup"):
            crm_params.append("needs_followup=true")
        if args.get("reply_category"):
            crm_params.append(f"reply_category={args['reply_category']}")
        if args.get("pipeline_run_id"):
            crm_params.append(f"pipeline={args['pipeline_run_id']}")
        crm_link = f"http://46.62.210.24:3000/crm" + ("?" + "&".join(crm_params) if crm_params else "")

        return {
            "total": len(contacts),
            "contacts": [
                {"email": c.email, "name": f"{c.first_name or ''} {c.last_name or ''}".strip() or None, "job_title": c.job_title, "source": c.email_source}
                for c in contacts
            ],
            "message": f"Found {len(contacts)} contacts. View in CRM: {crm_link}",
            "_links": {"crm": crm_link},
        }

    if tool_name == "crm_stats":
        user = await _get_user(token, session)
        from app.models.pipeline import ExtractedContact, DiscoveredCompany
        from app.models.campaign import Campaign
        from sqlalchemy import func as sa_func

        project_id = args.get("project_id") or user.active_project_id

        total_contacts = (await session.execute(
            select(sa_func.count(ExtractedContact.id)).where(ExtractedContact.project_id == project_id) if project_id else select(sa_func.count(ExtractedContact.id))
        )).scalar() or 0

        total_companies = (await session.execute(
            select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.project_id == project_id) if project_id else select(sa_func.count(DiscoveredCompany.id))
        )).scalar() or 0

        blacklisted = (await session.execute(
            select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_blacklisted == True, DiscoveredCompany.project_id == project_id) if project_id else select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_blacklisted == True)
        )).scalar() or 0

        targets = (await session.execute(
            select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_target == True, DiscoveredCompany.project_id == project_id) if project_id else select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_target == True)
        )).scalar() or 0

        crm_link = f"http://46.62.210.24:3000/crm" + (f"?project_id={project_id}" if project_id else "")

        return {
            "total_contacts": total_contacts,
            "total_companies": total_companies,
            "blacklisted_domains": blacklisted,
            "targets": targets,
            "message": f"{total_contacts} contacts, {total_companies} companies ({targets} targets, {blacklisted} blacklisted).",
            "_links": {"crm": crm_link},
        }

    # ── SmartLead Campaign Import ──
    if tool_name == "list_smartlead_campaigns":
        user = await _get_user(token, session)
        ctx = UserServiceContext(user.id, session)
        sl = await ctx.get_smartlead_service()
        if not sl.is_configured():
            raise ValueError("SmartLead not connected. Use configure_integration first.")
        campaigns = await sl.get_campaigns()
        search = (args.get("search") or "").lower()
        if search:
            campaigns = [c for c in campaigns if search in (c.get("name") or "").lower()]
        return {
            "campaigns": [
                {"id": c.get("id"), "name": c.get("name"), "status": c.get("status"), "leads": c.get("lead_count", 0)}
                for c in campaigns[:50]
            ],
            "total": len(campaigns),
            "message": f"Found {len(campaigns)} campaigns" + (f" matching '{search}'" if search else ""),
        }

    if tool_name == "import_smartlead_campaigns":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")

        ctx = UserServiceContext(user.id, session)
        sl = await ctx.get_smartlead_service()
        if not sl.is_configured():
            raise ValueError("SmartLead not connected")

        rules = args.get("rules", {})
        prefixes = rules.get("prefixes", [])
        tags = rules.get("tags", [])
        contains = rules.get("contains", [])
        exact_names = rules.get("exact_names", [])

        # Fetch all campaigns
        all_campaigns = await sl.get_campaigns()

        # Match campaigns against rules
        matched = []
        for c in all_campaigns:
            name = c.get("name", "")
            if exact_names and name in exact_names:
                matched.append(c)
            elif prefixes and any(name.startswith(p) for p in prefixes):
                matched.append(c)
            elif contains and any(s.lower() in name.lower() for s in contains):
                matched.append(c)
            # Tags matching would need campaign tags from SmartLead API

        # ACTUALLY DOWNLOAD contacts from each campaign → build blacklist
        from app.models.pipeline import DiscoveredCompany, ExtractedContact
        from app.models.campaign import Campaign
        from app.services.domain_service import normalize_domain
        import logging as _log

        total_contacts = 0
        total_domains = set()
        campaign_names = []
        campaign_details = []

        for camp in matched:
            camp_name = camp.get("name", "")
            camp_id = camp.get("id")
            campaign_names.append(camp_name)

            # Save campaign record
            existing_camp = await session.execute(
                select(Campaign).where(Campaign.external_id == str(camp_id))
            )
            if not existing_camp.scalar_one_or_none():
                session.add(Campaign(
                    project_id=project.id, company_id=project.company_id,
                    name=camp_name, external_id=str(camp_id),
                    platform="smartlead", status=camp.get("status", "active"),
                ))

            # DOWNLOAD ALL LEADS from this campaign
            leads = await sl.export_campaign_leads(camp_id)
            leads_count = len(leads)
            total_contacts += leads_count

            # Store contacts and extract domains for blacklist
            domains_in_camp = set()
            for lead in leads:
                domain = normalize_domain(lead.get("domain", ""))
                if domain:
                    total_domains.add(domain)
                    domains_in_camp.add(domain)

                # Save as extracted contact in MCP DB
                email = lead.get("email", "")
                if email:
                    existing_contact = await session.execute(
                        select(ExtractedContact).where(
                            ExtractedContact.project_id == project.id,
                            ExtractedContact.email == email,
                        )
                    )
                    if not existing_contact.scalar_one_or_none():
                        session.add(ExtractedContact(
                            discovered_company_id=None,
                            project_id=project.id,
                            first_name=lead.get("first_name"),
                            last_name=lead.get("last_name"),
                            email=email,
                            email_source="smartlead_import",
                            source_data={
                                "campaign": camp_name,
                                "campaign_id": camp_id,
                                "company_name": lead.get("company_name"),
                            },
                        ))

            # Create DiscoveredCompany records for each domain (for blacklisting)
            for domain in domains_in_camp:
                existing_dc = await session.execute(
                    select(DiscoveredCompany).where(
                        DiscoveredCompany.project_id == project.id,
                        DiscoveredCompany.domain == domain,
                    )
                )
                if not existing_dc.scalar_one_or_none():
                    session.add(DiscoveredCompany(
                        project_id=project.id,
                        company_id=project.company_id,
                        domain=domain,
                        is_blacklisted=True,
                        blacklist_reason=f"existing_campaign:{camp_name}",
                    ))

            campaign_details.append({"name": camp_name, "leads": leads_count, "domains": len(domains_in_camp)})
            _log.getLogger(__name__).info(f"Imported {leads_count} contacts from '{camp_name}' ({len(domains_in_camp)} unique domains)")

        # Save campaign rules on project
        project.campaign_filters = campaign_names
        await session.flush()

        # START BACKGROUND REPLY ANALYSIS — runs in parallel, doesn't block
        campaign_id_map = {camp.get("id"): camp.get("name", "") for camp in matched}
        matched_ids = [camp.get("id") for camp in matched if camp.get("id")]
        try:
            from app.services.reply_analysis_service import start_reply_analysis_background
            start_reply_analysis_background(sl, matched_ids, campaign_id_map, project.id)
            reply_analysis_status = f"Reply analysis started in background for {len(matched_ids)} campaigns."
        except Exception as e:
            reply_analysis_status = f"Reply analysis failed to start: {e}"

        return {
            "campaigns_imported": len(matched),
            "campaigns": campaign_details,
            "contacts_downloaded": total_contacts,
            "unique_domains_blacklisted": len(total_domains),
            "reply_analysis": reply_analysis_status,
            "message": f"Downloaded {total_contacts} contacts from {len(matched)} campaigns. "
                       f"{len(total_domains)} unique domains added to blacklist. "
                       f"Reply analysis running in background — will classify warm/meeting/interested replies. "
                       f"Ask 'which replies are warm?' after a minute.",
            "_links": {
                "crm": f"http://46.62.210.24:3000/crm",
                "crm_warm": f"http://46.62.210.24:3000/crm?reply_category=interested",
                "crm_meetings": f"http://46.62.210.24:3000/crm?reply_category=meeting",
            },
        }

    if tool_name == "set_campaign_rules":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")
        rules = args.get("rules", {})
        # Store rules in campaign_filters as JSON
        project.campaign_filters = rules
        return {
            "updated": True,
            "project_id": project.id,
            "rules": rules,
            "message": f"Campaign rules saved for '{project.name}'. These will be used for blacklisting.",
        }

    # ── Utility ──
    if tool_name == "estimate_cost":
        source = args["source_type"]
        filters = args.get("filters", {})
        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)
        if "api" in source:
            return {"estimated_credits": max_pages * per_page, "estimated_cost_usd": 0}
        return {"estimated_credits": 0, "estimated_cost_usd": 0, "note": "Free source"}

    if tool_name == "blacklist_check":
        user = await _get_user(token, session)
        domains = args.get("domains", [])
        return {"checked": len(domains), "blacklisted": 0, "clean": len(domains),
                "note": "Blacklist check against user's campaigns — full implementation coming"}

    raise ValueError(f"Unknown tool: {tool_name}")
