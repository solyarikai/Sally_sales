"""MCP Admin Panel — standalone FastAPI app with inline HTML templates.
Reads from MCP Postgres. Auth: ilovesally / qweqweqwe.
"""
import os
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import asyncpg

app = FastAPI(title="MCP Admin")

DB_URL = os.environ.get("DATABASE_URL", "postgresql://mcp:mcp_secret@mcp-postgres:5432/mcp_leadgen")
ADMIN_USER = "ilovesally"
ADMIN_PASS = "qweqweqwe"
SESSION_SECRET = hashlib.sha256(b"mcp-admin-secret-2026").hexdigest()

pool: Optional[asyncpg.Pool] = None


def _render(template: str, **kwargs) -> str:
    """Replace %%key%% placeholders in template (avoids CSS brace conflicts)."""
    result = template
    for k, v in kwargs.items():
        result = result.replace(f"%%{k}%%", str(v))
    return result


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DB_URL.replace("+asyncpg", ""), min_size=2, max_size=5)


@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()


def check_auth(request: Request):
    token = request.cookies.get("admin_session")
    if token != SESSION_SECRET:
        raise HTTPException(302, headers={"Location": "/login"})


# ── Auth ──

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return _render(HTML_LOGIN, style=STYLE)

@app.post("/login")
async def login(request: Request):
    form = await request.form()
    if form.get("username") == ADMIN_USER and form.get("password") == ADMIN_PASS:
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("admin_session", SESSION_SECRET, httponly=True, max_age=86400)
        return resp
    return HTMLResponse(_render(HTML_LOGIN, style=STYLE).replace("<!-- error -->", '<div style="color:#ef4444;margin-bottom:16px">Invalid credentials</div>'))

@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("admin_session")
    return resp


# ── Dashboard ──

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, date_from: str = "", date_to: str = ""):
    check_auth(request)

    date_clause = ""
    params = []
    if date_from:
        params.append(date_from)
        date_clause += f" AND u.created_at >= ${len(params)}::date"
    if date_to:
        params.append(date_to + " 23:59:59")
        date_clause += f" AND u.created_at <= ${len(params)}::timestamp"

    users = await pool.fetch(f"""
        SELECT u.id, u.email, u.name, u.created_at,
            (SELECT count(*) FROM mcp_usage_logs WHERE user_id = u.id) as tool_calls,
            (SELECT coalesce(sum(credits_used), 0) FROM gathering_runs gr
                JOIN projects p ON p.id = gr.project_id WHERE p.user_id = u.id) as apollo_credits,
            (SELECT count(*) FROM mcp_conversation_logs WHERE user_id = u.id) as conversations,
            (SELECT count(*) FROM mcp_usage_logs WHERE user_id = u.id AND tool_name = 'tam_analyze') as analysis_runs,
            (SELECT count(*) FROM projects WHERE user_id = u.id) as projects
        FROM mcp_users u
        WHERE u.is_active = true {date_clause}
        ORDER BY u.created_at DESC
    """, *params)

    # Totals
    totals = await pool.fetchrow("""
        SELECT
            (SELECT count(*) FROM mcp_users WHERE is_active = true) as total_users,
            (SELECT count(*) FROM mcp_usage_logs) as total_tool_calls,
            (SELECT coalesce(sum(credits_used), 0) FROM gathering_runs) as total_apollo,
            (SELECT count(*) FROM mcp_conversation_logs) as total_conversations
    """)

    rows_html = ""
    for u in users:
        created = u["created_at"].strftime("%Y-%m-%d %H:%M") if u["created_at"] else "—"
        apollo_cost = f"${u['apollo_credits'] * 0.01:.2f}" if u['apollo_credits'] else "—"
        openai_cost = f"~${u['analysis_runs'] * 0.05:.2f}" if u['analysis_runs'] else "—"
        rows_html += f"""
        <tr>
            <td>{u['id']}</td>
            <td><a href="/user/{u['id']}">{u['email']}</a></td>
            <td>{u['name'] or '—'}</td>
            <td>{created}</td>
            <td>{u['projects']}</td>
            <td>{u['apollo_credits']} ({apollo_cost})</td>
            <td>{u['analysis_runs']} ({openai_cost})</td>
            <td>{u['tool_calls']}</td>
            <td><a href="/user/{u['id']}/conversations">{u['conversations']}</a></td>
        </tr>"""

    return _render(HTML_DASHBOARD, style=STYLE,
        rows=rows_html,
        total_users=totals["total_users"],
        total_tool_calls=totals["total_tool_calls"],
        total_apollo=totals["total_apollo"],
        total_conversations=totals["total_conversations"],
        date_from=date_from,
        date_to=date_to,
    )


# ── User Detail ──

@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    check_auth(request)

    user = await pool.fetchrow("SELECT * FROM mcp_users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # Usage by tool
    tools = await pool.fetch("""
        SELECT tool_name, count(*) as cnt
        FROM mcp_usage_logs WHERE user_id = $1
        GROUP BY tool_name ORDER BY cnt DESC
    """, user_id)

    # Recent activity
    recent = await pool.fetch("""
        SELECT tool_name, action, created_at
        FROM mcp_usage_logs WHERE user_id = $1
        ORDER BY created_at DESC LIMIT 30
    """, user_id)

    # Integrations
    integrations = await pool.fetch("""
        SELECT integration_name, is_connected, connection_info
        FROM mcp_integration_settings WHERE user_id = $1
    """, user_id)

    # Pipeline runs
    runs = await pool.fetch("""
        SELECT gr.id, gr.source_type, gr.current_phase, gr.credits_used, gr.new_companies_count,
               gr.target_rate, gr.created_at, p.name as project_name
        FROM gathering_runs gr JOIN projects p ON p.id = gr.project_id
        WHERE p.user_id = $1 ORDER BY gr.created_at DESC LIMIT 20
    """, user_id)

    tools_html = "".join(f"<tr><td>{t['tool_name']}</td><td>{t['cnt']}</td></tr>" for t in tools)
    integrations_html = "".join(f"<tr><td>{i['integration_name']}</td><td>{'✓' if i['is_connected'] else '✗'}</td><td>{i['connection_info'] or ''}</td></tr>" for i in integrations)
    runs_html = "".join(f"<tr><td>#{r['id']}</td><td>{r['project_name']}</td><td>{r['source_type']}</td><td>{r['credits_used'] or 0}</td><td>{r['current_phase']}</td><td>{r['created_at'].strftime('%m/%d %H:%M') if r['created_at'] else ''}</td></tr>" for r in runs)
    recent_html = "".join(f"<tr><td>{a['created_at'].strftime('%m/%d %H:%M') if a['created_at'] else ''}</td><td>{a['tool_name']}</td><td>{a['action']}</td></tr>" for a in recent)

    created = user["created_at"].strftime("%Y-%m-%d %H:%M") if user["created_at"] else "—"
    return _render(HTML_USER, style=STYLE,
        user_id=user_id, email=user["email"], name=user["name"] or "—", created=created,
        tools_rows=tools_html, integrations_rows=integrations_html,
        runs_rows=runs_html, recent_rows=recent_html,
    )


# ── Conversations ──

@app.get("/user/{user_id}/conversations", response_class=HTMLResponse)
async def user_conversations(request: Request, user_id: int):
    check_auth(request)

    user = await pool.fetchrow("SELECT email, name FROM mcp_users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(404, "User not found")

    convos = await pool.fetch("""
        SELECT id, session_id, direction, method, message_type, content_summary, raw_json, created_at
        FROM mcp_conversation_logs WHERE user_id = $1
        ORDER BY created_at DESC LIMIT 200
    """, user_id)

    rows_html = ""
    for c in convos:
        ts = c["created_at"].strftime("%m/%d %H:%M:%S") if c["created_at"] else ""
        direction = "→" if c["direction"] == "client_to_server" else "←"
        method = c["method"] or ""
        summary = (c["content_summary"] or "")[:120]
        session = (c["session_id"] or "")[:12]
        raw = str(c["raw_json"] or "")[:500].replace("<", "&lt;")
        rows_html += f"""
        <tr>
            <td style="white-space:nowrap">{ts}</td>
            <td>{direction}</td>
            <td style="font-family:monospace;font-size:11px">{session}...</td>
            <td><b>{method}</b></td>
            <td>{summary}</td>
            <td><details><summary style="cursor:pointer;font-size:11px">JSON</summary><pre style="font-size:10px;max-height:200px;overflow:auto;background:#f5f5f5;padding:8px;border-radius:4px">{raw}</pre></details></td>
        </tr>"""

    return _render(HTML_CONVERSATIONS, style=STYLE,
        user_id=user_id, email=user["email"], name=user["name"] or "—",
        rows=rows_html, count=len(convos),
    )


# ── HTML Templates ──

STYLE = """
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f9fa; color: #333; }
    .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 20px; font-weight: 600; margin-bottom: 16px; }
    h2 { font-size: 16px; font-weight: 600; margin: 24px 0 12px; }
    .card { background: white; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px; }
    .stats { display: flex; gap: 16px; margin-bottom: 24px; }
    .stat { background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); flex: 1; text-align: center; }
    .stat .num { font-size: 28px; font-weight: 700; }
    .stat .label { font-size: 12px; color: #888; margin-top: 4px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; color: #888; border-bottom: 2px solid #eee; }
    td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }
    tr:hover { background: #f8f8f8; }
    a { color: #3b82f6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .nav { background: white; padding: 12px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; }
    .nav a { margin-right: 16px; font-size: 13px; }
    input[type=text], input[type=password], input[type=date] { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
    button, input[type=submit] { padding: 8px 20px; border: none; border-radius: 6px; background: #3b82f6; color: white; font-size: 14px; cursor: pointer; }
    button:hover, input[type=submit]:hover { background: #2563eb; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-red { background: #fee2e2; color: #991b1b; }
</style>
"""

HTML_LOGIN = """<!DOCTYPE html><html><head><title>MCP Admin</title>%%style%%</head><body>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center">
<div class="card" style="width:360px">
    <h1 style="text-align:center;margin-bottom:24px">MCP Admin</h1>
    <!-- error -->
    <form method="post" action="/login" style="display:flex;flex-direction:column;gap:12px">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="submit" value="Login">
    </form>
</div>
</div></body></html>"""

HTML_DASHBOARD = """<!DOCTYPE html><html><head><title>MCP Admin</title>%%style%%</head><body>
<div class="nav">
    <div><b>MCP Admin</b> <a href="/" style="margin-left:16px">Dashboard</a></div>
    <a href="/logout">Logout</a>
</div>
<div class="container">
    <div class="stats">
        <div class="stat"><div class="num">{%%total_users%%}</div><div class="label">Users</div></div>
        <div class="stat"><div class="num">{%%total_apollo%%}</div><div class="label">Apollo Credits</div></div>
        <div class="stat"><div class="num">{%%total_tool_calls%%}</div><div class="label">Tool Calls</div></div>
        <div class="stat"><div class="num">{%%total_conversations%%}</div><div class="label">Messages</div></div>
    </div>

    <div class="card">
        <form method="get" action="/" style="display:flex;gap:8px;align-items:center;margin-bottom:16px">
            <input type="date" name="date_from" value="{%%date_from%%}">
            <span style="color:#888">to</span>
            <input type="date" name="date_to" value="{%%date_to%%}">
            <button type="submit">Filter</button>
        </form>
        <table>
            <thead><tr>
                <th>ID</th><th>Email</th><th>Name</th><th>Created</th><th>Projects</th>
                <th>Apollo</th><th>OpenAI</th><th>Tool Calls</th><th>Conversations</th>
            </tr></thead>
            <tbody>{%%rows%%}</tbody>
        </table>
    </div>
</div></body></html>"""

HTML_USER = """<!DOCTYPE html><html><head><title>User %%user_id%% — MCP Admin</title>%%style%%</head><body>
<div class="nav">
    <div><b>MCP Admin</b> <a href="/">Dashboard</a> → User #%%user_id%%</div>
    <a href="/logout">Logout</a>
</div>
<div class="container">
    <div class="card">
        <h1>%%email%%</h1>
        <p style="color:#888">%%name%% · Created: %%created%% · <a href="/user/%%user_id%%/conversations">View conversations</a></p>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div class="card">
            <h2>Integrations</h2>
            <table><thead><tr><th>Service</th><th>Status</th><th>Info</th></tr></thead>
            <tbody>%%integrations_rows%%</tbody></table>
        </div>
        <div class="card">
            <h2>Tool Usage</h2>
            <table><thead><tr><th>Tool</th><th>Calls</th></tr></thead>
            <tbody>%%tools_rows%%</tbody></table>
        </div>
    </div>

    <div class="card">
        <h2>Pipeline Runs</h2>
        <table><thead><tr><th>Run</th><th>Project</th><th>Source</th><th>Credits</th><th>Phase</th><th>Date</th></tr></thead>
        <tbody>%%runs_rows%%</tbody></table>
    </div>

    <div class="card">
        <h2>Recent Activity</h2>
        <table><thead><tr><th>Time</th><th>Tool</th><th>Action</th></tr></thead>
        <tbody>%%recent_rows%%</tbody></table>
    </div>
</div></body></html>"""

HTML_CONVERSATIONS = """<!DOCTYPE html><html><head><title>Conversations — %%email%% — MCP Admin</title>%%style%%</head><body>
<div class="nav">
    <div><b>MCP Admin</b> <a href="/">Dashboard</a> → <a href="/user/%%user_id%%">%%email%%</a> → Conversations</div>
    <a href="/logout">Logout</a>
</div>
<div class="container">
    <div class="card">
        <h1>Conversations — %%email%% (%%name%%)</h1>
        <p style="color:#888">%%count%% messages</p>
    </div>
    <div class="card" style="overflow-x:auto">
        <table>
            <thead><tr><th>Time</th><th>Dir</th><th>Session</th><th>Method</th><th>Summary</th><th>Raw</th></tr></thead>
            <tbody>{%%rows%%}</tbody>
        </table>
    </div>
</div></body></html>"""
