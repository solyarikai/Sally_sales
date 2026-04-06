"""Crona MCP Server — exposes Crona API as Claude tools."""
import json
import os
from functools import lru_cache

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

from client import CronaClient  # noqa: E402

mcp = FastMCP("Crona")


@lru_cache(maxsize=1)
def get_client() -> CronaClient:
    return CronaClient()


# ------------------------------------------------------------------
# Account & Credits
# ------------------------------------------------------------------


@mcp.tool()
def whoami() -> str:
    """Get current account info (email, name, credits balance)."""
    data = get_client().whoami()
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def credits_balance() -> str:
    """Get current credits balance."""
    balance = get_client().credits_balance()
    return f"Credits balance: {balance}"


@mcp.tool()
def get_subscription() -> str:
    """Get current subscription info (tier, status, plan limit, next grant date)."""
    data = get_client().get_subscription()
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def spent_credits_by_month() -> str:
    """Get credits spent per month (last 6 months)."""
    data = get_client().spent_credits()
    return json.dumps(data, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Projects
# ------------------------------------------------------------------


@mcp.tool()
def list_projects() -> str:
    """List all Crona projects."""
    projects = get_client().list_projects()
    if not projects:
        return "No projects found."
    lines = [f"[{p['id']}] {p['name']} — status: {p.get('status', '?')}, rows: {p.get('rows_count', '?')}" for p in projects]
    return "\n".join(lines)


@mcp.tool()
def get_project(project_id: int) -> str:
    """Get details of a specific project by ID."""
    data = get_client().get_project(project_id)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def create_project(
    name: str,
    source_type: str = "",
    source_urls: str = "",
    sales_nav_cookies: str = "",
    sales_nav_user_agent: str = "",
    with_preprocessing: bool = True,
    max_pages: int = 0,
) -> str:
    """
    Create a new Crona project.

    Args:
        name: Project name.
        source_type: 'sales_navigator' or 'websites_list' (leave empty to set later).
        source_urls: Comma-separated Sales Navigator search URLs (for sales_navigator type).
        sales_nav_cookies: Sales Navigator session cookies JSON string.
        sales_nav_user_agent: Browser user agent for Sales Navigator.
        with_preprocessing: Enable preprocessing for sales_navigator (default True).
        max_pages: Max pages to scrape from Sales Navigator (0 = unlimited).
    """
    urls = [u.strip() for u in source_urls.split(",") if u.strip()] if source_urls else None
    data = get_client().create_project(
        name=name,
        source_type=source_type or None,
        source_urls=urls,
        sales_nav_cookies=sales_nav_cookies or None,
        sales_nav_user_agent=sales_nav_user_agent or None,
        with_preprocessing=with_preprocessing,
        max_pages=max_pages or None,
    )
    return f"Project created: id={data['id']}, name={data['name']}"


@mcp.tool()
def update_project(
    project_id: int,
    name: str = "",
    source_type: str = "",
    source_urls: str = "",
    sales_nav_cookies: str = "",
    with_preprocessing: bool = True,
    max_pages: int = 0,
) -> str:
    """Update project settings."""
    kwargs: dict = {}
    if name:
        kwargs["name"] = name
    if source_type:
        kwargs["source_type"] = source_type
    if source_urls:
        kwargs["source_urls"] = [u.strip() for u in source_urls.split(",") if u.strip()]
    if sales_nav_cookies:
        kwargs["sales_nav_cookies"] = sales_nav_cookies
    if source_type == "sales_navigator":
        kwargs["with_preprocessing"] = with_preprocessing
    if max_pages:
        kwargs["max_pages"] = max_pages
    data = get_client().update_project(project_id, **kwargs)
    return f"Project updated: id={data['id']}, name={data['name']}"


@mcp.tool()
def delete_project(project_id: int) -> str:
    """Delete a project by ID."""
    get_client().delete_project(project_id)
    return f"Project {project_id} deleted."


@mcp.tool()
def upload_source_file(project_id: int, source_type: str, file_path: str) -> str:
    """
    Upload a source file to a project.

    Args:
        project_id: Project ID.
        source_type: 'websites_list' or 'sales_navigator'.
        file_path: Absolute path to the CSV file to upload.
    """
    data = get_client().upload_source_file(project_id, source_type, file_path)
    return f"File uploaded. Project rows: {data.get('rows_count', '?')}"


@mcp.tool()
def get_project_status(project_id: int) -> str:
    """Get current run status of a project (pending/running/completed/failed/cancelled)."""
    s = get_client().get_project_status(project_id)
    parts = [f"status: {s['status']}"]
    if s.get("running_stage"):
        parts.append(f"stage: {s['running_stage']}")
    if s.get("processed_percentage") is not None:
        parts.append(f"progress: {s['processed_percentage']}%")
    if s.get("collected_amount") is not None:
        parts.append(f"collected: {s['collected_amount']} rows")
    if s.get("error_message"):
        parts.append(f"error: {s['error_message']}")
    return " | ".join(parts)


@mcp.tool()
def get_project_results(project_id: int, page: int = 1) -> str:
    """
    Get last run results for a project (paginated, ~100 rows per page).

    Args:
        project_id: Project ID.
        page: Page number (starts at 1).
    """
    data = get_client().get_last_results(project_id, page=page)
    rows = data.get("data", [])
    total_pages = data.get("total", 1)
    if not rows:
        return f"No data on page {page}."
    header = rows[0] if rows else []
    result_lines = [f"Page {page}/{total_pages}, {len(rows)-1} data rows"]
    result_lines.append("Columns: " + ", ".join(str(h) for h in header))
    for row in rows[1:6]:  # show first 5 data rows as preview
        result_lines.append(str(row))
    if len(rows) > 6:
        result_lines.append(f"... and {len(rows)-6} more rows")
    return "\n".join(result_lines)


@mcp.tool()
def download_results_url(project_id: int) -> str:
    """Get the download URL for project results CSV. Use this to download results manually."""
    url = get_client().download_last_results_url(project_id)
    return f"Download URL: {url}\nAdd header: Authorization: <your-token>"


# ------------------------------------------------------------------
# Enrichers
# ------------------------------------------------------------------


@mcp.tool()
def list_enricher_types() -> str:
    """List all available enricher types with descriptions and credit costs."""
    types = get_client().list_enricher_types()
    lines = []
    for t in types:
        args = [a["name"] for a in t.get("arguments", [])]
        lines.append(
            f"- {t['name']} | {t.get('display_name', '')} | credits: {t.get('credits_amount', '?')} | args: {args}"
        )
    return "\n".join(lines)


@mcp.tool()
def list_enrichers(project_id: int) -> str:
    """List all enrichers configured for a project."""
    enrichers = get_client().list_enrichers(project_id)
    if not enrichers:
        return "No enrichers configured."
    lines = []
    for e in sorted(enrichers, key=lambda x: x["order"]):
        lines.append(
            f"[{e['id']}] order={e['order']} | {e['type']} | field: {e['field_name']} | name: {e['name']} | credits: {e['credits_amount']}"
        )
    return "\n".join(lines)


@mcp.tool()
def get_enricher(project_id: int, enricher_id: int) -> str:
    """Get details of a specific enricher including its code and arguments."""
    data = get_client().get_enricher(project_id, enricher_id)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def create_enricher(
    project_id: int,
    name: str,
    field_name: str,
    enricher_type: str,
    order: int,
    code: str = "",
    arguments_json: str = "{}",
) -> str:
    """
    Add an enricher step to a project pipeline.

    Args:
        project_id: Project ID.
        name: Human-readable enricher name.
        field_name: Output column name (letters, numbers, underscores only).
        enricher_type: One of: filter, enricher, person_linkedin_details,
                       company_linkedin_details, code, call_ai, scrape_website,
                       person_verified_email, google_search, scrape_linkedin_posts,
                       filter_code, filter_call_ai, find_person_linkedin,
                       linkedin_activity_score, one_input_find_person_linkedin.
        order: Position in the pipeline (1 = first).
        code: Ruby code (for 'code' type) or leave empty for other types.
        arguments_json: JSON string with enricher arguments, e.g. '{"prompt": "..."}' for call_ai.
    """
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        return f"Error: invalid JSON in arguments_json: {arguments_json}"

    data = get_client().create_enricher(
        project_id=project_id,
        name=name,
        field_name=field_name,
        enricher_type=enricher_type,
        order=order,
        code=code,
        arguments=args,
    )
    warnings = data.get("warnings")
    msg = f"Enricher created: id={data['id']}, type={data['type']}, credits={data['credits_amount']}"
    if warnings:
        msg += f"\nWarnings: {warnings}"
    return msg


@mcp.tool()
def update_enricher(
    project_id: int,
    enricher_id: int,
    name: str = "",
    field_name: str = "",
    code: str = "",
    order: int = 0,
    arguments_json: str = "",
) -> str:
    """Update an existing enricher. Only provided fields are updated."""
    kwargs: dict = {}
    if name:
        kwargs["name"] = name
    if field_name:
        kwargs["field_name"] = field_name
    if code:
        kwargs["code"] = code
    if order:
        kwargs["order"] = order
    if arguments_json:
        try:
            kwargs["arguments"] = json.loads(arguments_json)
        except json.JSONDecodeError:
            return f"Error: invalid JSON in arguments_json"
    data = get_client().update_enricher(project_id, enricher_id, **kwargs)
    return f"Enricher updated: id={data['id']}"


@mcp.tool()
def delete_enricher(project_id: int, enricher_id: int) -> str:
    """Delete an enricher from a project."""
    get_client().delete_enricher(project_id, enricher_id)
    return f"Enricher {enricher_id} deleted from project {project_id}."


@mcp.tool()
def get_available_columns(project_id: int, enricher_id: int) -> str:
    """Get columns available as input for an enricher (from previous pipeline steps)."""
    columns = get_client().get_available_columns(project_id, enricher_id)
    return json.dumps(columns, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Project Runs
# ------------------------------------------------------------------


@mcp.tool()
def run_project(
    project_id: int,
    enricher_id: int = 0,
    run_dataset_id: int = 0,
    required_amount: int = 0,
) -> str:
    """
    Start a project run.

    Args:
        project_id: Project ID.
        enricher_id: Run only this enricher (0 = run all enrichers).
        run_dataset_id: Use specific dataset as input (0 = use project source).
        required_amount: Limit number of rows to process (0 = all).
    """
    data = get_client().run_project(
        project_id=project_id,
        enricher_id=enricher_id or None,
        run_dataset_id=run_dataset_id or None,
        required_amount=required_amount or None,
    )
    return f"Project run started: run_id={data['id']}, status={data['status']}"


@mcp.tool()
def wait_for_project(project_id: int, timeout_minutes: int = 60) -> str:
    """
    Wait for a running project to complete (polls every 15 seconds).

    Args:
        project_id: Project ID to monitor.
        timeout_minutes: Max wait time in minutes (default 60).
    """
    try:
        status = get_client().wait_for_completion(
            project_id,
            poll_interval=15,
            timeout=timeout_minutes * 60,
        )
        return f"Project {project_id} finished: status={status['status']}" + (
            f", error: {status['error_message']}" if status.get("error_message") else ""
        )
    except TimeoutError as e:
        return f"Timeout: {e}"


@mcp.tool()
def cancel_project_run(project_id: int, run_id: int) -> str:
    """Cancel a running project run."""
    data = get_client().cancel_project_run(project_id, run_id)
    return f"Run {run_id} cancelled: status={data['status']}"


# ------------------------------------------------------------------
# Enricher Runs (history)
# ------------------------------------------------------------------


@mcp.tool()
def list_enricher_runs(project_id: int, enricher_id: int) -> str:
    """List all past runs for a specific enricher."""
    runs = get_client().list_enricher_runs(project_id, enricher_id)
    if not runs:
        return "No runs found."
    lines = [
        f"[{r['id']}] run_at={r['run_at']} | rows={r.get('run_dataset_rows_count', '?')} | dataset_id={r.get('run_dataset_id', '?')}"
        for r in runs
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
