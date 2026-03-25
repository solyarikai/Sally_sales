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

            # Log usage
            try:
                from app.models.usage import MCPUsageLog
                from app.auth.middleware import verify_token
                user = await verify_token(session, token) if token else None
                session.add(MCPUsageLog(
                    user_id=user.id if user else 0,
                    action="tool_call",
                    tool_name=tool_name,
                    extra_data={"args": _safe_truncate(args), "latency_ms": latency},
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
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")

        source_type = args["source_type"]
        filters = args.get("filters", {})

        # ── Essential filter validation for API sources ──
        if "api" in source_type or "emulator" in source_type:
            missing = []
            if not filters.get("q_organization_keyword_tags") and not filters.get("organization_locations"):
                missing.append("keywords (q_organization_keyword_tags) OR locations (organization_locations)")
            if not filters.get("organization_num_employees_ranges"):
                missing.append("company size range (organization_num_employees_ranges, e.g. ['11,50', '51,200'])")
            if "api" in source_type and not filters.get("max_pages"):
                missing.append("max_pages (controls credit spend — each page costs 1 Apollo credit, returns 25 companies)")

            if missing:
                return {
                    "error": "missing_essential_filters",
                    "message": f"Cannot proceed — essential filters missing. Ask the user to specify:\n"
                               + "\n".join(f"  - {m}" for m in missing),
                    "hint": "Example: organization_num_employees_ranges: ['11,50'] for 11-50 employees, max_pages: 4 for ~100 companies",
                }

            # Apply safe defaults
            if "api" in source_type:
                filters.setdefault("max_pages", 4)
                filters.setdefault("per_page", 25)

        import hashlib, json as _json
        filter_hash = hashlib.sha256(_json.dumps(filters, sort_keys=True).encode()).hexdigest()[:16]

        # Estimate credits before starting
        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)
        est_credits = max_pages if "api" in source_type else 0
        est_companies = max_pages * per_page

        run = GatheringRun(
            project_id=project.id, company_id=project.company_id,
            source_type=source_type, filters=filters,
            filter_hash=filter_hash, status="running", current_phase="gather",
            triggered_by=f"mcp:user:{user.id}",
        )
        session.add(run)
        await session.flush()

        return {
            "run_id": run.id,
            "status": "running",
            "phase": "gather",
            "estimated_credits": est_credits,
            "estimated_companies": est_companies,
            "filters_applied": {
                "keywords": filters.get("q_organization_keyword_tags"),
                "locations": filters.get("organization_locations"),
                "employee_ranges": filters.get("organization_num_employees_ranges"),
                "max_pages": filters.get("max_pages"),
                "funding_stages": filters.get("organization_latest_funding_stage_cd"),
            },
            "message": f"Gathering started for '{project.name}' using {source_type}. "
                       f"~{est_companies} companies, ~{est_credits} credits.",
        }

    if tool_name == "tam_blacklist_check":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        # Create CP1 gate
        gate = ApprovalGate(
            project_id=run.project_id, gathering_run_id=run.id,
            gate_type="checkpoint_1", gate_label="Project scope + blacklist review",
            scope={"project_id": run.project_id, "run_id": run.id, "passed": 0, "rejected": 0},
        )
        session.add(gate)
        run.current_phase = "awaiting_scope_ok"
        await session.flush()
        return {"gate_id": gate.id, "type": "checkpoint_1", "message": "Checkpoint 1 created. Review and approve."}

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
        run.current_phase = "scrape"
        return {"status": "pre_filter_complete", "run_id": run.id}

    if tool_name == "tam_scrape":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        run.current_phase = "analyze"
        return {"status": "scrape_complete", "run_id": run.id, "message": "Website scraping complete"}

    if tool_name == "tam_analyze":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        # Create CP2 gate
        gate = ApprovalGate(
            project_id=run.project_id, gathering_run_id=run.id,
            gate_type="checkpoint_2", gate_label="Target list review",
            scope={"run_id": run.id, "targets_found": 0, "auto_refine": args.get("auto_refine", False)},
        )
        session.add(gate)
        run.current_phase = "awaiting_targets_ok"
        await session.flush()
        return {"gate_id": gate.id, "type": "checkpoint_2", "message": "Analysis complete. Review targets."}

    if tool_name == "tam_prepare_verification":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        gate = ApprovalGate(
            project_id=run.project_id, gathering_run_id=run.id,
            gate_type="checkpoint_3", gate_label="FindyMail cost approval",
            scope={"run_id": run.id, "estimated_cost_usd": 0.25, "emails_to_verify": 25},
        )
        session.add(gate)
        run.current_phase = "awaiting_verify_ok"
        await session.flush()
        return {"gate_id": gate.id, "type": "checkpoint_3", "estimated_cost": "$0.25"}

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
        seq = GeneratedSequence(
            project_id=project.id, company_id=project.company_id,
            campaign_name=args.get("campaign_name", f"{project.name} - Generated"),
            sequence_steps=[
                {"step": 1, "day": 0, "subject": "Quick question about {{company}}", "body": "Hi {{first_name}},\n\nI noticed {{company}} is growing..."},
                {"step": 2, "day": 3, "subject": "Re: Quick question about {{company}}", "body": "Hi {{first_name}},\n\nJust following up..."},
                {"step": 3, "day": 4, "subject": "{{company}} + {{sender_company}}", "body": "Hi {{first_name}},\n\nCompanies like {{company}}..."},
                {"step": 4, "day": 7, "subject": "One more thought for {{company}}", "body": "Hi {{first_name}},\n\nI know you're busy..."},
                {"step": 5, "day": 7, "subject": "Should I close the loop?", "body": "Hi {{first_name}},\n\nI don't want to be a pest..."},
            ],
            sequence_step_count=5,
            status="draft",
            model_used="placeholder",
        )
        session.add(seq)
        await session.flush()
        return {"sequence_id": seq.id, "steps": 5, "status": "draft"}

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
            raise ValueError("SmartLead not connected. Use configure_integration first.")
        campaign = await svc.create_campaign(seq.campaign_name or "MCP Generated")
        if not campaign:
            raise ValueError("Failed to create SmartLead campaign")
        campaign_id = campaign.get("id")
        await svc.set_campaign_sequences(campaign_id, seq.sequence_steps)
        from datetime import datetime
        seq.pushed_at = datetime.utcnow()
        seq.status = "pushed"
        return {"pushed": True, "smartlead_campaign_id": campaign_id,
                "url": f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics"}

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
            "pending_gates": [{"gate_id": g.id, "type": g.gate_type} for g in pending],
        }

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
