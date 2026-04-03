"""
MCP Tool Definitions for TAM Gathering — auto-generated from adapter registry.

Each registered adapter becomes an MCP tool with its JSON schema.
This module provides the tool list and execution dispatcher.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.services.gathering_adapters import ADAPTER_REGISTRY, get_adapter, list_adapters

logger = logging.getLogger(__name__)


def get_mcp_tool_definitions() -> List[Dict[str, Any]]:
    """Generate MCP tool definitions from all registered adapters.

    Returns list of tool definitions ready for MCP registration:
    [
        {
            "name": "tam_gather_apollo_companies_api",
            "description": "Apollo Organization Search (API) — ...",
            "inputSchema": { JSON Schema from adapter filter model },
        },
        ...
    ]
    """
    tools = []

    for source_type, adapter_cls in sorted(ADAPTER_REGISTRY.items()):
        adapter = adapter_cls()
        capabilities = adapter.get_capabilities()

        # Convert source_type to MCP tool name: "apollo.companies.api" → "tam_gather_apollo_companies_api"
        tool_name = f"tam_gather_{source_type.replace('.', '_')}"

        # Build input schema
        filter_schema = adapter.get_filter_schema() or {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }

        # Add standard fields to schema
        input_schema = {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "Target project ID",
                },
                "filters": filter_schema,
                "segment_id": {
                    "type": ["integer", "null"],
                    "description": "Optional segment ID to link this run to",
                },
                "notes": {
                    "type": ["string", "null"],
                    "description": "Operator notes about this run",
                },
            },
            "required": ["project_id", "filters"],
        }

        tool_def = {
            "name": tool_name,
            "description": (
                f"{capabilities.get('source_label', source_type)} — "
                f"Cost model: {capabilities.get('cost_model', 'unknown')}. "
                f"{'Requires auth.' if capabilities.get('requires_auth') else 'No auth needed.'}"
            ),
            "inputSchema": input_schema,
        }
        tools.append(tool_def)

    # Add utility tools
    tools.extend([
        {
            "name": "tam_list_sources",
            "description": "List all available TAM gathering sources with their capabilities and filter schemas.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "tam_estimate",
            "description": "Estimate cost and results for a gathering run without executing it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_type": {"type": "string", "description": "e.g. apollo.companies.api"},
                    "filters": {"type": "object", "description": "Source-specific filters"},
                },
                "required": ["source_type", "filters"],
            },
        },
        {
            "name": "tam_list_runs",
            "description": "List gathering runs for a project, optionally filtered by source type and status.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "source_type": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                },
                "required": ["project_id"],
            },
        },
        {
            "name": "tam_blacklist_check",
            "description": "Check domains against CRM + blacklist (dry run).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "domains": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": ["integer", "null"]},
                },
                "required": ["domains"],
            },
        },
    ])

    return tools


async def dispatch_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    company_id: int = 1,
) -> Dict[str, Any]:
    """Dispatch an MCP tool call to the appropriate gathering service method.

    This is the bridge between MCP tool calls and the gathering service.
    """
    from app.db import async_session_maker
    from app.services.gathering_service import gathering_service

    async with async_session_maker() as session:
        # Source-specific gathering tools
        if tool_name.startswith("tam_gather_"):
            source_type = tool_name.replace("tam_gather_", "").replace("_", ".")
            # Reconstruct dotted source type (apollo_companies_api → apollo.companies.api)
            parts = source_type.split(".")
            if len(parts) < 3:
                # Handle underscore → dot conversion more carefully
                raw = tool_name.replace("tam_gather_", "")
                # Find the matching source type from registry
                for st in ADAPTER_REGISTRY:
                    if st.replace(".", "_") == raw:
                        source_type = st
                        break

            run = await gathering_service.start_gathering(
                session=session,
                project_id=arguments["project_id"],
                company_id=company_id,
                source_type=source_type,
                filters=arguments.get("filters", {}),
                segment_id=arguments.get("segment_id"),
                notes=arguments.get("notes"),
                triggered_by="mcp_agent",
            )
            await session.commit()
            return {
                "run_id": run.id,
                "status": run.status,
                "new_companies": run.new_companies_count,
                "duplicates": run.duplicate_count,
                "raw_results": run.raw_results_count,
            }

        elif tool_name == "tam_list_sources":
            return {"sources": list_adapters()}

        elif tool_name == "tam_estimate":
            adapter = get_adapter(arguments["source_type"])
            validated = await adapter.validate(arguments["filters"])
            result = await adapter.estimate(validated)
            return {
                "estimated_companies": result.estimated_companies,
                "estimated_credits": result.estimated_credits,
                "estimated_cost_usd": result.estimated_cost_usd,
                "notes": result.notes,
            }

        elif tool_name == "tam_list_runs":
            runs = await gathering_service.get_runs(
                session,
                project_id=arguments["project_id"],
                source_type=arguments.get("source_type"),
                status=arguments.get("status"),
            )
            return {
                "runs": [
                    {
                        "id": r.id,
                        "source_type": r.source_type,
                        "status": r.status,
                        "new_companies": r.new_companies_count,
                        "raw_results": r.raw_results_count,
                        "target_rate": r.target_rate,
                        "created_at": str(r.created_at),
                    }
                    for r in runs
                ]
            }

        elif tool_name == "tam_blacklist_check":
            from app.services.domain_service import matches_trash_pattern
            results = []
            for domain in arguments["domains"]:
                domain = domain.strip().lower()
                status = "clean"
                if matches_trash_pattern(domain):
                    status = "trash_pattern"
                results.append({"domain": domain, "status": status})
            return {"total": len(results), "results": results}

        else:
            return {"error": f"Unknown tool: {tool_name}"}
