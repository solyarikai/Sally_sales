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
from app.models.campaign import GeneratedSequence, Campaign
from app.models.integration import MCPIntegrationSetting
from app.models.pipeline import DiscoveredCompany, ExtractedContact
from app.models.usage import MCPUsageLog, MCPConversationLog
from app.models.reply import MCPReply
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
                from app.auth.middleware import verify_token
                user = await verify_token(session, token) if token else None
                log_extra = {"args": _safe_truncate(args), "latency_ms": latency}
                # Extract credits_spent from result for credit tracking
                if isinstance(result, dict) and result.get("credits_spent"):
                    log_extra["credits_spent"] = result["credits_spent"]
                # For setup_account, user doesn't exist yet — get ID from result
                uid = user.id if user else None
                if not uid and isinstance(result, dict) and result.get("user_id"):
                    uid = result["user_id"]
                if uid:
                    session.add(MCPUsageLog(
                        user_id=uid,
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

    # ── Login (no auth needed — this IS the auth) ──
    if tool_name == "login":
        token_val = args.get("token", "")
        if not token_val.startswith("mcp_"):
            raise ValueError("Token must start with mcp_. Sign up at http://46.62.210.24:3000/setup to get one.")
        user = await _get_user(token_val, session)
        from app.mcp.server import _session_tokens, _session_user_tokens, mcp_server
        _session_tokens["_latest"] = token_val
        # Store per MCP session for concurrent user isolation
        try:
            ctx = mcp_server.request_context
            _session_user_tokens[id(ctx.session)] = token_val
        except (LookupError, AttributeError):
            pass
        return {"user_id": user.id, "name": user.name, "email": user.email,
                "message": f"Logged in as {user.name}. All tools ready."}

    if tool_name == "get_context":
        user = await _get_user(token, session)
        from sqlalchemy import func

        # Projects
        projects = (await session.execute(
            select(Project).where(Project.user_id == user.id, Project.is_active == True)
        )).scalars().all()

        # Pipeline runs (GatheringRun already imported at module level)
        runs = (await session.execute(
            select(GatheringRun).where(
                GatheringRun.project_id.in_([p.id for p in projects])
            ).order_by(GatheringRun.created_at.desc()).limit(10)
        )).scalars().all() if projects else []

        # Draft campaigns
        drafts = (await session.execute(
            select(Campaign).where(
                Campaign.project_id.in_([p.id for p in projects]),
                Campaign.status.in_(["draft", "DRAFT", "DRAFTED"]),
            )
        )).scalars().all() if projects else []

        # Reply counts
        reply_count = 0
        warm_count = 0
        if projects:
            pids = [p.id for p in projects]
            reply_count = (await session.execute(
                select(func.count(MCPReply.id)).where(MCPReply.project_id.in_(pids))
            )).scalar() or 0
            warm_count = (await session.execute(
                select(func.count(MCPReply.id)).where(
                    MCPReply.project_id.in_(pids),
                    MCPReply.category.in_(["interested", "meeting_request", "question"]),
                )
            )).scalar() or 0

        # Recent conversations
        recent_convos = (await session.execute(
            select(MCPConversationLog).where(
                MCPConversationLog.user_id == user.id
            ).order_by(MCPConversationLog.created_at.desc()).limit(5)
        )).scalars().all()

        # Auto-set active project if user has exactly 1
        if len(projects) == 1 and not user.active_project_id:
            user.active_project_id = projects[0].id

        # Pending approval gates
        pending_gates = []
        if projects:
            gate_result = await session.execute(
                select(ApprovalGate).where(
                    ApprovalGate.gathering_run_id.in_([r.id for r in runs]),
                    ApprovalGate.status == "pending",
                )
            )
            pending_gates = gate_result.scalars().all()

        context = {
            "user": {"name": user.name, "email": user.email},
            "active_project_id": user.active_project_id,
            "projects": [{"id": p.id, "name": p.name, "icp": (p.target_segments or "")[:100]} for p in projects],
            "pipeline_runs": [{"id": r.id, "phase": r.current_phase, "companies": r.new_companies_count, "project_id": r.project_id} for r in runs],
            "draft_campaigns": [{"id": c.id, "name": c.name, "status": c.status, "smartlead_url": f"https://app.smartlead.ai/app/email-campaigns-v2/{c.external_id}/analytics" if c.external_id else None} for c in drafts],
            "replies": {"total": reply_count, "warm": warm_count},
            "recent_activity": [{"method": c.method, "summary": c.content_summary, "at": str(c.created_at)} for c in recent_convos],
            "message": (
                f"Welcome back, {user.name}!\n\n"
                + (f"You have {len(projects)} project{'s' if len(projects) != 1 else ''}: {', '.join(p.name for p in projects)}\n" if projects else "No projects yet. Create one with create_project.\n")
                + (f"{len(runs)} pipeline run{'s' if len(runs) != 1 else ''} ({sum(1 for r in runs if r.current_phase in ('awaiting_targets_ok','awaiting_scope_ok'))} awaiting approval)\n" if runs else "")
                + (f"{len(drafts)} DRAFT campaign{'s' if len(drafts) != 1 else ''} pending review\n" if drafts else "")
                + (f"{reply_count} replies tracked ({warm_count} warm)\n" if reply_count else "")
                + "\nWhat would you like to do?"
            ),
        }

        # Action items for state restoration
        if pending_gates:
            g = pending_gates[0]
            context["action_required"] = {
                "type": "checkpoint_approval",
                "gate_id": g.id,
                "run_id": g.gathering_run_id,
                "checkpoint": g.gate_type,
                "message": f"Pending checkpoint: {g.gate_type}. Approve or reject to continue.",
            }
        if drafts:
            context["action_required_campaigns"] = [{
                "id": c.id, "name": c.name, "status": "DRAFT",
                "message": "Check test email and activate when ready.",
            } for c in drafts]

        return context

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
        integrations = {i.integration_name: {"connected": i.is_connected, "info": i.connection_info}
                        for i in result.scalars().all()}

        REQUIRED = ["apollo", "smartlead", "openai"]
        missing = [k for k in REQUIRED if k not in integrations or not integrations[k]["connected"]]

        return {
            "integrations": [{"name": k, **v} for k, v in integrations.items()],
            "required_for_campaigns": REQUIRED,
            "missing_required": missing,
            "ready": len(missing) == 0,
            "message": (
                "All required integrations connected! Ready to create campaigns."
                if not missing else
                f"Missing required keys: {', '.join(missing)}. Connect them with configure_integration to start creating campaigns."
            ),
        }

    # ── Project tools ──
    if tool_name == "select_project":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found or not yours")
        user.active_project_id = project.id
        # Get project details for display (use already-imported models)
        from sqlalchemy import func
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

        # Scrape website to extract value proposition for ICP context
        website = args.get("website")
        target_segments = args.get("target_segments") or ""
        website_context = ""
        skip_scrape = args.get("skip_scrape", False)
        if website and not skip_scrape:
            import httpx as _httpx
            try:
                async with _httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(website)
                    if resp.status_code == 200:
                        import re
                        html = resp.text
                        # Strip HTML tags for plain text
                        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()[:2000]
                        website_context = f"\n\nCompany website ({website}): {text}"
            except Exception as e:
                website_context = f"\n\nWebsite scrape failed: {e}"

        if website_context:
            target_segments = (target_segments + website_context).strip()

        project = Project(
            company_id=company.id, user_id=user.id, name=args["name"],
            target_segments=target_segments or None,
            target_industries=args.get("target_industries"),
            sender_name=args.get("sender_name"),
            sender_company=args.get("sender_company"),
            sender_position=args.get("sender_position"),
        )
        session.add(project)
        await session.flush()
        return {
            "project_id": project.id,
            "name": project.name,
            "website_scraped": bool(website_context),
            "message": f"Project '{project.name}' created." + (f" Website {website} scraped for ICP context." if website_context else " Consider providing a website URL for better sequence generation."),
        }

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

    # ── Intent Parsing ──
    if tool_name == "parse_gathering_intent":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")

        # Get user's offer from project context (for competitor exclusion)
        user_offer = project.target_segments or ""
        if project.sender_company:
            user_offer = f"{project.sender_company}: {user_offer}"

        # Get API keys
        from app.services.encryption import decrypt_value
        openai_key = gemini_key = None
        for svc_name in ("openai", "gemini"):
            r = await session.execute(
                select(MCPIntegrationSetting).where(
                    MCPIntegrationSetting.user_id == user.id,
                    MCPIntegrationSetting.integration_name == svc_name,
                )
            )
            row = r.scalar_one_or_none()
            if row and row.api_key_encrypted:
                try:
                    key = decrypt_value(row.api_key_encrypted)
                    if svc_name == "openai":
                        openai_key = key
                    else:
                        gemini_key = key
                except Exception:
                    pass

        from app.services.intent_parser import parse_gathering_intent
        result = await parse_gathering_intent(
            query=args["query"],
            user_offer=user_offer,
            openai_key=openai_key,
            gemini_key=gemini_key,
        )

        segments = result.get("segments", [])
        n = result.get("pipelines_needed", len(segments))

        return {
            **result,
            "message": (
                f"Parsed query into {n} segment{'s' if n > 1 else ''}: "
                + ", ".join(s.get("label", "?") for s in segments)
                + (f". Competitor exclusions: {result.get('competitor_exclusions', [])}" if result.get("competitor_exclusions") else "")
                + f"\n\n{'Call tam_gather ONCE per segment.' if n > 1 else 'Call tam_gather with this segment.'}"
            ),
        }

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

        result = {
            "run_id": run.id,
            "status": run.status,
            "phase": run.current_phase,
            "new_companies": run.new_companies_count,
            "existing_in_project": run.duplicate_count,
            "source_type": source_type,
            "message": (
                f"Gathered {run.new_companies_count} companies from {source_type.split('.')[0].upper()} "
                f"for project '{project.name}'. "
                + (f"{run.new_companies_count} new, {run.duplicate_count} duplicate (already gathered for this project)."
                   if run.duplicate_count > 0
                   else f"All {run.new_companies_count} are new to this project.")
            ),
            "_links": {"pipeline": f"http://46.62.210.24:3000/pipeline/{run.id}"},
        }
        # Only include cost info for paid sources
        if est_credits > 0:
            result["estimated_credits"] = est_credits
        return result

    if tool_name == "tam_blacklist_check":
        user = await _get_user(token, session)
        run = await session.get(GatheringRun, args["run_id"])
        if not run:
            raise ValueError("Run not found")
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        gate = await svc.blacklist_check(session, run)
        project = await session.get(Project, run.project_id)

        # M7: Trigger background reply analysis IN PARALLEL with blacklist
        try:
            import asyncio as _asyncio
            from app.services.reply_analysis_service import start_background_analysis
            _asyncio.create_task(start_background_analysis(run.project_id, user.id))
            logger.info(f"Background reply analysis started for project {run.project_id}")
        except Exception as e:
            logger.debug(f"Background reply analysis skip: {e}")

        scope = gate.scope or {}
        return {
            "gate_id": gate.id, "type": "checkpoint_1",
            "project_name": project.name if project else "Unknown",
            "scope": scope,
            "message": f"CHECKPOINT 1: Blacklist check complete for project '{project.name if project else 'Unknown'}'. "
                       f"Checked {scope.get('companies_checked', 0)} companies, "
                       f"{scope.get('companies_passed', 0)} passed, "
                       f"{scope.get('companies_rejected', 0)} rejected. "
                       f"Approve to continue.",
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

        # Multi-step prompt chain support
        prompt_steps = args.get("prompt_steps")
        if prompt_steps and isinstance(prompt_steps, list) and len(prompt_steps) > 0:
            gate = await svc.analyze_multi_step(
                session, run,
                prompt_steps=prompt_steps,
                openai_key=openai_key,
            )
        else:
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
            .values(status="rejected", decision_note="Re-analyzing with adjusted prompt")
        )
        # Re-run analysis with new prompt
        ctx = UserServiceContext(user.id, session)
        openai_key = await ctx.get_key("openai")
        if not openai_key:
            from app.config import settings
            openai_key = settings.OPENAI_API_KEY
        from app.services.gathering_service import GatheringService
        svc = GatheringService()
        prompt_text = args.get("prompt_text")
        prompt_steps = args.get("prompt_steps")
        if prompt_steps and isinstance(prompt_steps, list):
            gate = await svc.analyze_multi_step(session, run, prompt_steps=prompt_steps, openai_key=openai_key)
        else:
            gate = await svc.analyze(session, run, prompt_text=prompt_text, openai_key=openai_key)
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
                f"Re-analysis complete. Classified {scope.get('total_analyzed', 0)} companies. "
                f"TARGETS: {scope.get('targets_found', 0)} ({scope.get('target_rate', '0%')}). "
                f"Segments: {scope.get('segment_distribution', {})}. "
                f"Review the updated target list."
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
        from app.services.gathering_adapters.source_router import list_sources
        return {"sources": list_sources()}

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
    if tool_name == "smartlead_generate_sequence":
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

    if tool_name == "smartlead_approve_sequence":
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
        user_campaigns = (await session.execute(
            select(Campaign).where(Campaign.project_id.in_(
                select(Project.id).where(Project.user_id == user.id)
            ))
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

    if tool_name == "check_destination":
        # M1: When both SmartLead and GetSales keys present, ask which platform
        user = await _get_user(token, session)
        ctx = UserServiceContext(user.id, session)
        sl_configured = (await ctx.get_smartlead_service()).is_configured()
        gs_key = await ctx.get_key("getsales")
        gs_configured = bool(gs_key)

        if sl_configured and gs_configured:
            return {
                "both_configured": True,
                "question": "destination_selection",
                "message": "You have both SmartLead (email) and GetSales (LinkedIn) connected. Which platform should we use?",
                "options": ["SmartLead (email outreach)", "GetSales (LinkedIn outreach)", "Both"],
            }
        elif sl_configured:
            return {"destination": "smartlead", "message": "SmartLead configured. Will push email campaign."}
        elif gs_configured:
            return {"destination": "getsales", "message": "GetSales configured. Will push LinkedIn flow."}
        else:
            raise ValueError("No outreach platform configured. Connect SmartLead or GetSales in Setup.")

    if tool_name == "smartlead_push_campaign":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Sequence not found")
        if seq.status != "approved":
            raise ValueError("Sequence must be approved first")

        # M5: Require email accounts — agent MUST call list_email_accounts first
        if not args.get("email_account_ids"):
            raise ValueError("email_account_ids required. Call list_email_accounts first and ask the user which accounts to use.")

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

        # 3. Set production settings (M3: match reference campaign 3070919)
        # Hardcoded in SmartLeadService: no tracking, plain text, stop on reply, 40% follow-up
        await svc.set_campaign_settings(campaign_id)

        # 4. Set schedule (M2: 9-18 in target contact timezone)
        target_country = args.get("target_country", "")
        if not target_country:
            # Try to get from project's gathering filters or gathered contact geo
            project = await session.get(Project, seq.project_id)
            if project and project.target_segments:
                for country in ["United States", "Germany", "United Kingdom", "India", "Australia", "UAE", "Canada", "France", "Netherlands", "Switzerland"]:
                    if country.lower() in (project.target_segments or "").lower():
                        target_country = country
                        break
            # Also check gathered contacts' most common country
            if not target_country:
                from sqlalchemy import func as sa_func
                geo_result = await session.execute(
                    select(DiscoveredCompany.country, sa_func.count(DiscoveredCompany.id))
                    .join(CompanySourceLink, CompanySourceLink.discovered_company_id == DiscoveredCompany.id)
                    .where(DiscoveredCompany.is_target == True, DiscoveredCompany.country.isnot(None))
                    .group_by(DiscoveredCompany.country)
                    .order_by(sa_func.count(DiscoveredCompany.id).desc())
                    .limit(1)
                )
                top_country = geo_result.first()
                if top_country:
                    target_country = top_country[0]
        from app.services.smartlead_service import get_timezone_for_country
        timezone = get_timezone_for_country(target_country or "United States")
        await svc.set_campaign_schedule(campaign_id, timezone)

        # 5. Assign email accounts — MUST be provided by user
        email_account_ids = args.get("email_account_ids", [])
        if email_account_ids:
            await svc.set_campaign_email_accounts(campaign_id, email_account_ids)
        # If no accounts provided, campaign stays without accounts — agent must ask user

        # 6. Save to DB
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

        # 7. Upload target contacts to SmartLead campaign
        leads_uploaded = 0
        try:
            contacts_result = await session.execute(
                select(ExtractedContact, DiscoveredCompany)
                .outerjoin(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
                .where(
                    ExtractedContact.project_id == seq.project_id,
                    DiscoveredCompany.is_target == True,
                    ExtractedContact.email.isnot(None),
                )
            )
            contacts = contacts_result.all()
            if contacts:
                lead_list = []
                for contact, company in contacts:
                    lead = {
                        "email": contact.email,
                        "first_name": contact.first_name or "",
                        "last_name": contact.last_name or "",
                        "company_name": company.name if company else "",  # normalized name
                        "custom_fields": {
                            "segment": company.analysis_segment if company else "",
                            "source_company_name": (company.source_data or {}).get("source_company_name", "") if company else "",
                            "domain": company.domain if company else "",
                            "pipeline_run": str(seq.project_id),
                        },
                    }
                    lead_list.append(lead)
                if lead_list:
                    await svc.add_leads_to_campaign(campaign_id, lead_list)
                    leads_uploaded = len(lead_list)
                    campaign.leads_count = leads_uploaded
        except Exception as e:
            logger.warning(f"Failed to upload contacts to SmartLead: {e}")

        # 7b. Add test leads ONLY when the user is a known test account
        _TEST_ACCOUNTS = {"pn@getsally.io", "services@getsally.io"}
        if user.email in _TEST_ACCOUNTS:
            test_leads = [
                {"email": "pn@getsally.io", "first_name": "Petr", "last_name": "Test", "company_name": "TEST - DELETE", "custom_fields": {"is_test_lead": "true"}},
                {"email": "services@getsally.io", "first_name": "Services", "last_name": "Test", "company_name": "TEST - DELETE", "custom_fields": {"is_test_lead": "true"}},
            ]
            try:
                await svc.add_leads_to_campaign(campaign_id, test_leads)
                leads_uploaded += len(test_leads)
            except Exception as e:
                logger.debug(f"Test leads add failed: {e}")

        # 8. Auto-send test email to the user's own email
        test_email_result = None
        try:
            test_email_result = await svc.send_test_email(
                campaign_id=campaign_id,
                test_email=user.email,
                sequence_number=1,
            )
            logger.info(f"Test email sent to {user.email} for campaign {campaign_id}: {test_email_result}")
        except Exception as e:
            logger.warning(f"Auto test email failed for campaign {campaign_id}: {e}")
            test_email_result = {"ok": False, "error": str(e)}

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
            "test_email": test_email_result,
            "user_email": user.email,
            "message": (
                f"Campaign '{seq.campaign_name}' created as DRAFT.\n\n"
                f"SmartLead: {smartlead_url}\n"
                f"Schedule: Mon-Fri 9:00-18:00 {timezone}\n"
                f"Email accounts: {len(email_account_ids)} assigned\n"
                f"Leads uploaded: {leads_uploaded} target contacts\n\n"
                + (f"Check your inbox at {user.email} — test email sent!\n\n" if test_email_result and test_email_result.get("ok") else
                   f"Test email could not be sent ({test_email_result.get('error', 'no email accounts') if test_email_result else 'no accounts assigned'}). Assign email accounts first.\n\n")
                + f"I'll launch after your approval. Before activating, you can:\n"
                + f"- Review the sequence in SmartLead\n"
                + f"- Edit any email step (tell me which to change)\n"
                + f"- Override target companies (tell me which to add/remove)\n"
                + f"- Provide feedback on the companies or sequence\n\n"
                + f"Once satisfied, say 'activate' to start sending."
            ),
            "_links": {
                "smartlead": smartlead_url,
                "campaigns": "http://46.62.210.24:3000/campaigns",
                "pipeline": f"http://46.62.210.24:3000/pipeline/{run.id if 'run' in dir() else ''}",
            },
        }

    if tool_name == "send_test_email":
        user = await _get_user(token, session)
        ctx = UserServiceContext(user.id, session)
        svc = await ctx.get_smartlead_service()
        if not svc.is_configured():
            raise ValueError("SmartLead not connected")
        test_email = args.get("test_email") or user.email
        result = await svc.send_test_email(
            campaign_id=args["campaign_id"],
            test_email=test_email,
            sequence_number=args.get("sequence_number", 1),
        )
        return {**result, "sent_to": test_email}

    if tool_name in ("smartlead_score_campaigns", "smartlead_extract_patterns"):
        user = await _get_user(token, session)
        return {"message": f"{tool_name} — coming in next iteration"}

    # ── GetSales LinkedIn Automation ──

    if tool_name == "gs_generate_flow":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project:
            raise ValueError("Project not found")

        from app.config import settings as _cfg
        from app.services.getsales_automation import GetSalesAutomationService
        gs_key = _cfg.GETSALES_API_KEY
        gs_team = _cfg.GETSALES_TEAM_ID
        if not gs_key:
            raise ValueError("GetSales not configured (GETSALES_API_KEY missing)")

        svc = GetSalesAutomationService(gs_key, gs_team or "7430")
        gemini_key = getattr(_cfg, "GEMINI_API_KEY", None)
        openai_key = getattr(_cfg, "OPENAI_API_KEY", None)

        seq = await svc.generate_flow(
            session, project.id,
            flow_name=args.get("flow_name"),
            flow_type=args.get("flow_type", "standard"),
            instructions=args.get("instructions"),
            gemini_key=gemini_key,
            openai_key=openai_key,
        )

        flow_data = seq.sequence_steps or {}
        messages = flow_data.get("messages", [])
        conn_note = flow_data.get("connection_note", "")

        preview = []
        if conn_note:
            preview.append(f"Connection note: {conn_note[:100]}...")
        for i, msg in enumerate(messages):
            preview.append(f"MSG{i+1}: {msg[:100]}...")

        return {
            "sequence_id": seq.id,
            "flow_name": seq.campaign_name,
            "flow_type": flow_data.get("flow_type", "standard"),
            "messages": len(messages),
            "status": "draft",
            "rationale": seq.rationale,
            "preview": preview,
            "connection_note": conn_note,
            "full_messages": messages,
            "include_inmail": flow_data.get("include_inmail", False),
            "message": (
                f"Generated LinkedIn flow '{seq.campaign_name}' ({flow_data.get('flow_type', 'standard')} type).\n\n"
                f"Connection note: {conn_note[:150] if conn_note else '(none — networking style)'}\n"
                f"Messages: {len(messages)} follow-ups\n"
                f"InMail fallback: {'Yes' if flow_data.get('include_inmail') else 'No'}\n\n"
                f"Review the messages above. You can:\n"
                f"- Edit any message (tell me which to change)\n"
                f"- Change flow type (standard/networking/product/volume/event)\n"
                f"- Say 'approve' when ready to push to GetSales"
            ),
        }

    if tool_name == "gs_approve_flow":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Flow not found")
        from datetime import datetime
        seq.status = "approved"
        seq.reviewed_by = f"mcp:user:{user.id}"
        seq.reviewed_at = datetime.utcnow()
        return {"approved": True, "sequence_id": seq.id}

    if tool_name == "gs_list_sender_profiles":
        user = await _get_user(token, session)
        from app.config import settings as _cfg
        from app.services.getsales_automation import GetSalesAutomationService
        gs_key = _cfg.GETSALES_API_KEY
        gs_team = _cfg.GETSALES_TEAM_ID
        if not gs_key:
            raise ValueError("GetSales not configured")
        svc = GetSalesAutomationService(gs_key, gs_team or "7430")

        profiles = await svc.get_sender_profiles()
        workspaces = await svc.get_workspaces()

        return {
            "sender_profiles": [
                {
                    "uuid": p.get("uuid", ""),
                    "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                    "status": p.get("status", ""),
                    "linkedin_url": p.get("linkedin_url", ""),
                }
                for p in (profiles or [])
            ],
            "workspaces": [
                {"uuid": w.get("uuid", ""), "name": w.get("name", "")}
                for w in (workspaces or [])
            ],
            "message": "Select sender profile UUIDs and optionally a workspace UUID for the flow.",
        }

    if tool_name == "gs_push_to_getsales":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Flow not found")
        if seq.status != "approved":
            raise ValueError("Flow must be approved first. Call gs_approve_flow.")

        from app.config import settings as _cfg
        from app.services.getsales_automation import (
            GetSalesAutomationService, get_timezone_for_country,
            TIMING_STANDARD, TIMING_NETWORKING, TIMING_VOLUME,
        )
        gs_key = _cfg.GETSALES_API_KEY
        gs_team = _cfg.GETSALES_TEAM_ID
        if not gs_key:
            raise ValueError("GetSales not configured")
        svc = GetSalesAutomationService(gs_key, gs_team or "7430")

        flow_data = seq.sequence_steps or {}
        flow_type = flow_data.get("flow_type", "standard")

        # Select timing based on flow type
        timing = {
            "standard": TIMING_STANDARD,
            "product": TIMING_STANDARD,
            "networking": TIMING_NETWORKING,
            "event": TIMING_NETWORKING,
            "volume": TIMING_VOLUME,
        }.get(flow_type, TIMING_STANDARD)

        # Resolve timezone
        target_country = args.get("target_country", "")
        if not target_country and seq.project_id:
            project = await session.get(Project, seq.project_id)
            if project and project.target_segments:
                for country in ["United States", "Germany", "United Kingdom", "India", "Australia", "UAE", "Russia"]:
                    if country.lower() in (project.target_segments or "").lower():
                        target_country = country
                        break
        timezone = get_timezone_for_country(target_country)

        # Build node tree
        node_tree = svc.build_node_tree(
            connection_note=flow_data.get("connection_note", ""),
            messages=flow_data.get("messages", []),
            timing=timing,
            include_inmail=flow_data.get("include_inmail", False),
            inmail_text=flow_data.get("inmail_text"),
        )

        # 1. Create flow
        flow_result = await svc.create_flow(
            name=seq.campaign_name or "MCP Generated",
            workspace_uuid=args.get("workspace_uuid"),
            timezone=timezone,
        )
        if not flow_result:
            raise ValueError("Failed to create GetSales flow")
        flow_uuid = flow_result.get("uuid")
        if not flow_uuid:
            raise ValueError(f"GetSales returned no UUID: {flow_result}")

        # 2. Save flow version with nodes
        sender_uuids = args.get("sender_profile_uuids", [])
        rotation = args.get("rotation_strategy", "fair")

        version_result = await svc.save_flow_version(
            flow_uuid=flow_uuid,
            nodes=node_tree,
            sender_profile_uuids=sender_uuids,
            rotation_strategy=rotation,
        )

        # 3. Upload target contacts from pipeline
        leads_uploaded = 0
        try:
            contacts_result = await session.execute(
                select(ExtractedContact, DiscoveredCompany)
                .outerjoin(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
                .where(
                    ExtractedContact.project_id == seq.project_id,
                    DiscoveredCompany.is_target == True,
                )
            )
            contacts = contacts_result.all()
            for contact, company in contacts:
                linkedin_url = contact.linkedin_url if hasattr(contact, 'linkedin_url') else None
                if not linkedin_url:
                    continue
                lead_data = {
                    "linkedin_url": linkedin_url,
                    "first_name": contact.first_name or "",
                    "last_name": contact.last_name or "",
                    "company_name": company.name if company else "",
                }
                result = await svc.add_lead_to_flow(flow_uuid, lead_data)
                if result:
                    leads_uploaded += 1
        except Exception as e:
            logger.warning(f"Failed to upload contacts to GetSales: {e}")

        # 4. Save campaign to DB
        campaign = Campaign(
            project_id=seq.project_id,
            company_id=seq.company_id,
            name=seq.campaign_name,
            external_id=flow_uuid,
            platform="getsales",
            status="draft",
            leads_count=leads_uploaded,
        )
        session.add(campaign)
        from datetime import datetime
        seq.pushed_at = datetime.utcnow()
        seq.status = "pushed"
        await session.flush()

        getsales_url = f"https://amazing.getsales.io/flow/{flow_uuid}/builder"

        return {
            "pushed": True,
            "flow_uuid": flow_uuid,
            "status": "DRAFT",
            "settings": {
                "timezone": timezone,
                "schedule": "Mon-Fri 09:00-18:00",
                "sender_profiles": len(sender_uuids),
                "rotation_strategy": rotation,
                "flow_type": flow_type,
                "messages": len(flow_data.get("messages", [])),
                "include_inmail": flow_data.get("include_inmail", False),
            },
            "leads_uploaded": leads_uploaded,
            "version_saved": version_result is not None,
            "message": (
                f"Flow '{seq.campaign_name}' created as DRAFT in GetSales.\n\n"
                f"GetSales: {getsales_url}\n"
                f"Schedule: Mon-Fri 9:00-18:00 {timezone}\n"
                f"Sender profiles: {len(sender_uuids)} assigned ({rotation} rotation)\n"
                f"Leads uploaded: {leads_uploaded} target contacts\n\n"
                f"Review the flow in GetSales Builder, then say 'activate' when ready to start."
            ),
            "_links": {
                "getsales_builder": getsales_url,
                "getsales_flow": f"https://amazing.getsales.io/flow/{flow_uuid}",
            },
        }

    if tool_name == "gs_activate_flow":
        user = await _get_user(token, session)
        if not args.get("user_confirmation"):
            raise ValueError("SAFETY: user_confirmation required. Quote the user's exact words confirming activation.")

        from app.config import settings as _cfg
        from app.services.getsales_automation import GetSalesAutomationService
        gs_key = _cfg.GETSALES_API_KEY
        gs_team = _cfg.GETSALES_TEAM_ID
        if not gs_key:
            raise ValueError("GetSales not configured")
        svc = GetSalesAutomationService(gs_key, gs_team or "7430")

        result = await svc.start_flow(args["flow_uuid"])

        from datetime import datetime
        session.add(MCPUsageLog(
            user_id=user.id,
            tool_name="gs_activate_flow",
            action="flow_activated",
            extra_data={
                "flow_uuid": args["flow_uuid"],
                "user_confirmation": args["user_confirmation"],
                "timestamp": str(datetime.utcnow()),
            },
        ))

        return {
            "activated": True,
            "flow_uuid": args["flow_uuid"],
            "status": "ACTIVE",
            "message": f"Flow {args['flow_uuid']} is now ACTIVE. LinkedIn outreach will begin.",
            "_links": {"getsales": f"https://amazing.getsales.io/flow/{args['flow_uuid']}/builder"},
        }

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

        query = select(ExtractedContact).order_by(ExtractedContact.created_at.desc())

        project_id = args.get("project_id")
        if not project_id and user.active_project_id:
            project_id = user.active_project_id
        if project_id:
            query = query.where(ExtractedContact.project_id == project_id)
        else:
            # NEVER return global data — scope to user's projects
            user_pids = await session.execute(select(Project.id).where(Project.user_id == user.id))
            pids = [pid for (pid,) in user_pids.all()]
            if pids:
                query = query.where(ExtractedContact.project_id.in_(pids))
            else:
                return {"total": 0, "contacts": [], "message": "No projects yet."}

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
        from sqlalchemy import func as sa_func

        project_id = args.get("project_id") or user.active_project_id

        # User-scope: get user's project IDs
        user_pids = await session.execute(select(Project.id).where(Project.user_id == user.id))
        pids = [pid for (pid,) in user_pids.all()]

        if project_id:
            scope_filter_ec = ExtractedContact.project_id == project_id
            scope_filter_dc = DiscoveredCompany.project_id == project_id
        elif pids:
            scope_filter_ec = ExtractedContact.project_id.in_(pids)
            scope_filter_dc = DiscoveredCompany.project_id.in_(pids)
        else:
            return {"total_contacts": 0, "total_companies": 0, "blacklisted_domains": 0, "targets": 0, "message": "No projects yet."}

        total_contacts = (await session.execute(select(sa_func.count(ExtractedContact.id)).where(scope_filter_ec))).scalar() or 0
        total_companies = (await session.execute(select(sa_func.count(DiscoveredCompany.id)).where(scope_filter_dc))).scalar() or 0
        blacklisted = (await session.execute(select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_blacklisted == True, scope_filter_dc))).scalar() or 0
        targets = (await session.execute(select(sa_func.count(DiscoveredCompany.id)).where(DiscoveredCompany.is_target == True, scope_filter_dc))).scalar() or 0

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
        # Uses 3-tier funnel: SmartLead FREE → keyword OOO filter → GPT-4o-mini for real conversations
        campaign_id_map = {camp.get("id"): camp.get("name", "") for camp in matched}
        matched_ids = [camp.get("id") for camp in matched if camp.get("id")]
        try:
            from app.services.reply_analysis_service import start_reply_analysis_background
            # Pass OpenAI key for Tier 3 AI classification
            openai_key = None
            from app.services.encryption import decrypt_value
            openai_setting = await session.execute(
                select(MCPIntegrationSetting).where(
                    MCPIntegrationSetting.user_id == user.id,
                    MCPIntegrationSetting.integration_name == "openai",
                )
            )
            openai_row = openai_setting.scalar_one_or_none()
            if openai_row and openai_row.api_key_encrypted:
                try:
                    openai_key = decrypt_value(openai_row.api_key_encrypted)
                except Exception:
                    pass
            start_reply_analysis_background(sl, matched_ids, campaign_id_map, project.id, openai_key)
            reply_analysis_status = f"Reply analysis started in background for {len(matched_ids)} campaigns (3-tier: SmartLead→OOO filter→GPT-4o-mini)."
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
        source = args.get("source_type", "apollo.companies.api")
        filters = args.get("filters") or {}
        max_pages = filters.get("max_pages", 4)
        per_page = filters.get("per_page", 25)
        if "api" in source:
            return {"estimated_credits": max_pages, "estimated_cost_usd": 0,
                    "estimated_companies": max_pages * per_page,
                    "note": f"{max_pages} pages × {per_page} per page = {max_pages * per_page} companies. 1 credit per page."}
        return {"estimated_credits": 0, "estimated_cost_usd": 0, "note": "Free source"}

    if tool_name == "blacklist_check":
        user = await _get_user(token, session)
        domains = args.get("domains", [])
        return {"checked": len(domains), "blacklisted": 0, "clean": len(domains),
                "note": "Blacklist check against user's campaigns — full implementation coming"}

    # ── Reply tools ──
    if tool_name in ("replies_summary", "replies_list", "replies_followups", "replies_deep_link"):
        user = await _get_user(token, session)
        return await _handle_reply_tool(tool_name, args, user, session)

    # ── Feedback & Editing tools ──
    if tool_name == "smartlead_edit_sequence":
        user = await _get_user(token, session)
        seq = await session.get(GeneratedSequence, args["sequence_id"])
        if not seq:
            raise ValueError("Sequence not found")
        project = await session.get(Project, seq.project_id)
        if not project or project.user_id != user.id:
            raise ValueError("Sequence not found")

        steps = seq.sequence_steps or []
        step_idx = args["step_number"] - 1
        if step_idx < 0 or step_idx >= len(steps):
            raise ValueError(f"Step {args['step_number']} not found (sequence has {len(steps)} steps)")

        old_step = steps[step_idx].copy()
        if "subject" in args and args["subject"] is not None:
            steps[step_idx]["subject"] = args["subject"]
        if "body" in args and args["body"] is not None:
            steps[step_idx]["body"] = args["body"]
        seq.sequence_steps = steps
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(seq, "sequence_steps")

        # Push to SmartLead if campaign exists
        smartlead_pushed = False
        if seq.pushed_campaign_id:
            campaign = await session.get(Campaign, seq.pushed_campaign_id)
            if campaign and campaign.external_id:
                from app.services.smartlead_service import SmartLeadService
                sl = SmartLeadService()
                if sl.is_configured():
                    await sl.set_campaign_sequences(int(campaign.external_id), steps)
                    smartlead_pushed = True

        return {
            "updated": True,
            "step": args["step_number"],
            "old_subject": old_step.get("subject", ""),
            "new_subject": steps[step_idx].get("subject", ""),
            "smartlead_synced": smartlead_pushed,
            "message": f"Email {args['step_number']} updated and synced." + (f" Changes pushed to SmartLead." if smartlead_pushed else " Save to push changes to SmartLead."),
        }

    if tool_name == "edit_campaign_accounts":
        user = await _get_user(token, session)
        from app.services.smartlead_service import SmartLeadService
        sl = SmartLeadService()
        if not sl.is_configured():
            raise ValueError("SmartLead not configured")
        await sl.set_campaign_email_accounts(args["campaign_id"], args["email_account_ids"])
        return {
            "updated": True,
            "campaign_id": args["campaign_id"],
            "accounts_set": len(args["email_account_ids"]),
            "message": f"{len(args['email_account_ids'])} email accounts assigned to campaign {args['campaign_id']}.",
        }

    if tool_name == "override_company_target":
        user = await _get_user(token, session)
        company = await session.get(DiscoveredCompany, args["company_id"])
        if not company:
            raise ValueError("Company not found")
        project = await session.get(Project, company.project_id)
        if not project or project.user_id != user.id:
            raise ValueError("Company not found")

        old_target = company.is_target
        company.is_target = args["is_target"]
        company.analysis_reasoning = (
            f"[USER OVERRIDE] {args.get('reasoning', 'No reason given')}. "
            f"Previous: is_target={old_target}, AI: {(company.analysis_reasoning or 'none')[:200]}"
        )
        return {
            "updated": True,
            "company": company.name or company.domain,
            "was_target": old_target,
            "now_target": args["is_target"],
            "message": f"Override applied: {'target' if args['is_target'] else 'NOT target'} — {company.name or company.domain}. User override stored for learning.",
        }

    if tool_name == "provide_feedback":
        user = await _get_user(token, session)
        project = await session.get(Project, args["project_id"])
        if not project or project.user_id != user.id:
            raise ValueError("Project not found")

        from datetime import datetime
        log = MCPUsageLog(
            user_id=user.id,
            tool_name="user_feedback",
            action=args["feedback_type"],
            extra_data={
                "project_id": args["project_id"],
                "feedback_type": args["feedback_type"],
                "feedback_text": args["feedback_text"],
                "context": args.get("context"),
                "timestamp": str(datetime.utcnow()),
            },
        )
        session.add(log)
        return {
            "stored": True,
            "feedback_type": args["feedback_type"],
            "message": f"Feedback stored for '{project.name}'. Will be used in future runs — most recent feedback takes priority.",
        }

    if tool_name == "activate_campaign":
        user = await _get_user(token, session)
        if not args.get("user_confirmation"):
            raise ValueError("SAFETY: user_confirmation required. Quote the user's exact words confirming activation.")

        ctx = UserServiceContext(user.id, session)
        sl = await ctx.get_smartlead_service()
        if not sl.is_configured():
            raise ValueError("SmartLead not configured. Use configure_integration to add your SmartLead API key.")
        await sl.update_campaign_status(args["campaign_id"], "START")

        # Enable reply monitoring on activation
        from app.models.campaign import Campaign as CampaignModel
        campaign_result = await session.execute(
            select(CampaignModel).where(CampaignModel.external_id == str(args["campaign_id"]))
        )
        campaign_record = campaign_result.scalar_one_or_none()
        if campaign_record:
            campaign_record.status = "active"
            campaign_record.monitoring_enabled = True
            campaign_record.created_by = "mcp"

        from datetime import datetime
        log = MCPUsageLog(
            user_id=user.id,
            tool_name="activate_campaign",
            action="campaign_activated",
            extra_data={
                "campaign_id": args["campaign_id"],
                "user_confirmation": args["user_confirmation"],
                "monitoring_enabled": True,
                "timestamp": str(datetime.utcnow()),
            },
        )
        session.add(log)
        return {
            "activated": True,
            "campaign_id": args["campaign_id"],
            "status": "ACTIVE",
            "monitoring_enabled": True,
            "message": f"Campaign {args['campaign_id']} is now ACTIVE. Reply monitoring is ON by default.\n\nI'll track replies and classify them automatically. Want me to also send Telegram notifications for warm replies?",
            "_links": {"smartlead": f"https://app.smartlead.ai/app/email-campaigns-v2/{args['campaign_id']}/analytics"},
        }

    raise ValueError(f"Unknown tool: {tool_name}")


async def _resolve_project_id(project_name: str, user, session) -> int | None:
    """Resolve a project name to project_id. Returns None if not found.
    If multiple projects match, returns the most recent one.
    """
    from sqlalchemy import func as sa_func
    result = await session.execute(
        select(Project).where(
            Project.user_id == user.id,
            sa_func.lower(Project.name) == project_name.lower(),
        ).order_by(Project.id.desc()).limit(1)
    )
    project = result.scalar_one_or_none()
    return project.id if project else None


async def _resolve_project(project_name: str, user, session):
    """Resolve project name to full Project object.
    If multiple projects match, returns the most recent one.
    """
    from sqlalchemy import func as sa_func
    result = await session.execute(
        select(Project).where(
            Project.user_id == user.id,
            sa_func.lower(Project.name) == project_name.lower(),
        ).order_by(Project.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


def _get_campaign_name_filter(project) -> str | None:
    """Extract a campaign name substring filter from project's campaign_filters.

    campaign_filters is a list of full campaign names (e.g. ["Petr ES Australia", "Petr ES Gulf"]).
    We find the longest common prefix across all names — that's the search pattern.
    For ["Petr ES Australia", "Petr ES Gulf", "UAE-Pakistan Petr 16/03"] → "Petr" (appears in all).
    """
    if not project or not project.campaign_filters:
        return None
    filters = project.campaign_filters
    if isinstance(filters, list) and filters:
        str_filters = [f for f in filters if isinstance(f, str) and len(f) > 2]
        if not str_filters:
            return None

        # Find common words across all campaign names
        # Split each name into words, find words that appear in most names
        from collections import Counter
        word_counts = Counter()
        for name in str_filters:
            words = set(w.lower() for w in name.split() if len(w) > 2)
            for w in words:
                word_counts[w] += 1

        # Find the word that appears in the most campaign names
        if word_counts:
            best_word, count = word_counts.most_common(1)[0]
            # Only use if it appears in at least 60% of campaigns
            if count >= len(str_filters) * 0.6:
                return best_word

        # Fallback: use longest common prefix
        sorted_filters = sorted(str_filters)
        first, last = sorted_filters[0], sorted_filters[-1]
        prefix = ""
        for a, b in zip(first, last):
            if a.lower() == b.lower():
                prefix += a
            else:
                break
        prefix = prefix.strip(" -_")
        if len(prefix) >= 3:
            return prefix

        # Last resort: shortest filter
        return min(str_filters, key=len)

    if isinstance(filters, dict):
        prefixes = filters.get("prefixes", [])
        contains = filters.get("contains", [])
        candidates = prefixes + contains
        if candidates:
            return min(candidates, key=len)
    return None


async def _call_replies_api(path: str, params: dict | None = None) -> dict:
    """Call MCP's OWN replies API (NOT main backend — fully independent).

    ARCHITECTURE RULE: MCP NEVER calls main backend. All data is in MCP's own DB.
    This function calls the MCP backend's own /api/replies/ endpoints.
    """
    import httpx
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=15) as client:
            resp = await client.get(f"/api/{path}", params=params, headers={"X-Company-ID": "1"})
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"API returned {resp.status_code}", "detail": resp.text[:500]}
    except Exception as e:
        return {"error": f"MCP replies API unreachable: {e}"}


async def _handle_reply_tool(tool_name: str, args: dict, user, session) -> dict:
    """Handle all reply-related tool calls.

    Data source: MCP's own reply data (mcp_replies table + analysis cache).
    NEVER calls main backend. Fully independent.
    """
    from app.services.reply_analysis_service import get_cached_analysis

    UI_BASE = "http://46.62.210.24:3000"

    if tool_name == "replies_summary":
        project_name = args["project_name"]
        project_id = await _resolve_project_id(project_name, user, session)
        if not project_id:
            return {"error": f"Project '{project_name}' not found"}

        # Try MCP cache first
        cached = get_cached_analysis(project_id)
        if cached and cached.get("replies"):
            replies = cached["replies"]
            summary = cached.get("summary", {})
            cats = summary.get("by_category", {})
            total = len(replies)
            warm = sum(1 for r in replies if r.get("category") in ("interested", "meeting_request"))
            needs_reply = sum(1 for r in replies if r.get("needs_reply"))
            return {
                "project": project_name,
                "total_replies": total,
                "categories": cats,
                "warm_leads": warm,
                "needs_reply": needs_reply,
                "ooo_filtered": summary.get("ooo_skipped", 0),
                "ai_classified": summary.get("ai_classified", 0),
                "analysis_duration": f"{summary.get('duration_seconds', 0)}s",
                "analyzed_at": cached.get("analyzed_at", ""),
                "campaigns_analyzed": cached.get("campaigns", []),
                "message": f"Reply summary for '{project_name}': {total} total replies across {len(cached.get('campaigns', []))} campaigns. "
                           f"{warm} warm leads, {needs_reply} need reply. "
                           f"({summary.get('ooo_skipped', 0)} OOO auto-filtered, {summary.get('ai_classified', 0)} AI-classified).",
                "_links": {
                    "replies_ui": f"{UI_BASE}/tasks?project={project_name}",
                    "warm_replies": f"{UI_BASE}/crm?reply_category=interested&project={project_name}",
                    "meetings": f"{UI_BASE}/crm?reply_category=meeting_request&project={project_name}",
                    "followups": f"{UI_BASE}/crm?needs_followup=true&project={project_name}",
                },
            }

        # Fallback to MCP's own replies API — scope by campaign_filters
        project = await _resolve_project(project_name, user, session)
        campaign_filter = _get_campaign_name_filter(project)
        # /counts doesn't support campaign_name_contains, so fetch replies and aggregate
        params = {"received_since": "all", "page_size": 100, "group_by_contact": "true"}
        if campaign_filter:
            params["campaign_name_contains"] = campaign_filter
        data = await _call_replies_api("replies/", params)
        if "error" in data:
            return data

        replies = data.get("replies", [])
        total = data.get("total", len(replies))
        # Aggregate categories
        cats = {}
        for r in replies:
            cat = r.get("category", "other")
            cats[cat] = cats.get(cat, 0) + 1
        warm = cats.get("interested", 0) + cats.get("meeting_request", 0)
        return {
            "project": project_name,
            "total_replies": total,
            "categories": cats,
            "warm_leads": warm,
            "campaign_filter": campaign_filter,
            "message": f"Reply summary for '{project_name}' (campaigns matching '{campaign_filter}'): {total} total replies, {warm} warm.",
            "_links": {
                "replies_ui": f"{UI_BASE}/tasks?project={project_name}",
                "warm_replies": f"{UI_BASE}/crm?reply_category=interested&project={project_name}",
            },
        }

    if tool_name == "replies_list":
        project_name = args.get("project_name")
        category_filter = args.get("category")
        search_filter = args.get("search")
        needs_reply_filter = args.get("needs_reply")

        if project_name:
            project_id = await _resolve_project_id(project_name, user, session)
            if not project_id:
                return {"error": f"Project '{project_name}' not found"}

            # Try MCP cache
            cached = get_cached_analysis(project_id)
            if cached and cached.get("replies"):
                replies = cached["replies"]

                # Apply filters
                if category_filter:
                    replies = [r for r in replies if r.get("category") == category_filter]
                if search_filter:
                    s = search_filter.lower()
                    replies = [r for r in replies if s in (r.get("email", "") + r.get("name", "") + r.get("company", "")).lower()]
                if needs_reply_filter is not None:
                    val = str(needs_reply_filter).lower() == "true"
                    replies = [r for r in replies if r.get("needs_reply") == val]

                # Sort by received_at desc
                replies.sort(key=lambda r: r.get("received_at", ""), reverse=True)

                cards = []
                for r in replies[:30]:
                    cards.append({
                        "lead_name": r.get("name", ""),
                        "lead_email": r.get("email", ""),
                        "company": r.get("company", ""),
                        "category": r.get("category", "other"),
                        "confidence": r.get("confidence", 0),
                        "campaign": r.get("campaign_name", ""),
                        "message_preview": r.get("reply_text", "")[:200],
                        "received_at": r.get("received_at", ""),
                        "needs_reply": r.get("needs_reply", False),
                        "reasoning": r.get("reasoning", ""),
                    })

                return {
                    "total": len(replies),
                    "replies": cards,
                    "message": f"Found {len(replies)} replies" + (f" in category '{category_filter}'" if category_filter else ""),
                    "_links": {
                        "replies_ui": f"{UI_BASE}/tasks?project={project_name}" + (f"&category={category_filter}" if category_filter else ""),
                        "crm_filtered": f"{UI_BASE}/crm?reply_category={category_filter}&project={project_name}" if category_filter else f"{UI_BASE}/crm?project={project_name}",
                    },
                }

        # Fallback to MCP's own replies API — scope by campaign_filters
        params: dict = {"received_since": "all", "page_size": 30, "group_by_contact": "true"}
        if project_name:
            project = await _resolve_project(project_name, user, session)
            campaign_filter = _get_campaign_name_filter(project)
            if campaign_filter:
                params["campaign_name_contains"] = campaign_filter
        if category_filter:
            params["category"] = category_filter
        if search_filter:
            params["lead_email"] = search_filter
        if needs_reply_filter is not None:
            params["needs_reply"] = str(needs_reply_filter).lower()
        if args.get("page"):
            params["page"] = args["page"]

        data = await _call_replies_api("replies/", params)
        if "error" in data:
            return data
        replies = data.get("replies", [])
        cards = [{
            "lead_name": r.get("lead_name") or r.get("lead_email", ""),
            "lead_email": r.get("lead_email", ""),
            "company": r.get("company_name") or r.get("lead_company", ""),
            "category": r.get("category", "unknown"),
            "campaign": r.get("campaign_name", ""),
            "message_preview": (r.get("email_body") or r.get("reply_text") or "")[:200],
            "received_at": r.get("received_at", ""),
        } for r in replies[:30]]

        return {
            "total": data.get("total", len(cards)),
            "replies": cards,
            "message": f"Found {data.get('total', len(cards))} replies",
            "_links": {"replies_ui": f"{UI_BASE}/tasks" + (f"?project={project_name}" if project_name else "")},
        }

    if tool_name == "replies_followups":
        project_name = args.get("project_name")

        if project_name:
            project_id = await _resolve_project_id(project_name, user, session)
            if not project_id:
                return {"error": f"Project '{project_name}' not found"}

            # Try MCP cache — followups = needs_reply=true
            cached = get_cached_analysis(project_id)
            if cached and cached.get("replies"):
                replies = [r for r in cached["replies"] if r.get("needs_reply")]
                replies.sort(key=lambda r: r.get("received_at", ""), reverse=True)

                cards = [{
                    "lead_name": r.get("name", ""),
                    "lead_email": r.get("email", ""),
                    "company": r.get("company", ""),
                    "category": r.get("category", ""),
                    "campaign": r.get("campaign_name", ""),
                    "received_at": r.get("received_at", ""),
                    "reasoning": r.get("reasoning", ""),
                } for r in replies[:30]]

                return {
                    "total": len(replies),
                    "replies": cards,
                    "message": f"{len(replies)} leads need follow-up for '{project_name}'. "
                               f"These are interested, meeting requests, and questions that haven't been replied to yet.",
                    "_links": {
                        "followups_ui": f"{UI_BASE}/crm?needs_followup=true&project={project_name}",
                        "warm_leads": f"{UI_BASE}/crm?reply_category=interested&project={project_name}",
                    },
                }

        # Fallback — scope by campaign_filters
        params = {"needs_followup": "true", "received_since": "all", "page_size": 30}
        if project_name:
            project = await _resolve_project(project_name, user, session)
            campaign_filter = _get_campaign_name_filter(project)
            if campaign_filter:
                params["campaign_name_contains"] = campaign_filter
        data = await _call_replies_api("replies/", params)
        if "error" in data:
            return data
        replies = data.get("replies", [])
        cards = [{
            "lead_name": r.get("lead_name") or r.get("lead_email", ""),
            "lead_email": r.get("lead_email", ""),
            "company": r.get("company_name", ""),
            "category": r.get("category", ""),
            "campaign": r.get("campaign_name", ""),
            "received_at": r.get("received_at", ""),
        } for r in replies[:30]]
        return {
            "total": data.get("total", len(cards)),
            "replies": cards,
            "message": f"{data.get('total', len(cards))} leads need follow-up",
            "_links": {"followups_ui": f"{UI_BASE}/tasks/followups"},
        }

    if tool_name == "replies_deep_link":
        project_name = args["project_name"]
        category = args.get("category", "")
        tab = args.get("tab", "")

        # Build CRM deep link (more useful than tasks page)
        query_params = [f"project={project_name}"]
        if category:
            query_params.append(f"reply_category={category}")

        crm_url = f"{UI_BASE}/crm?" + "&".join(query_params)
        tasks_url = f"{UI_BASE}/tasks?" + "&".join(query_params)

        return {
            "crm_url": crm_url,
            "tasks_url": tasks_url,
            "message": f"Open replies for '{project_name}' in the browser",
            "_links": {"crm": crm_url, "tasks": tasks_url},
        }

    return {"error": f"Unknown reply tool: {tool_name}"}
