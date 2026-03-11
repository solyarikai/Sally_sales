#!/usr/bin/env python3
"""MoltBot conversation monitor — zero-dependency Python 3 server."""

import json
import os
import glob
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SESSIONS_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
SESSIONS_JSON = os.path.join(SESSIONS_DIR, "sessions.json")
AUTH_TOKEN = os.environ.get("MONITOR_TOKEN", "s4lly2026")
PORT = int(os.environ.get("MONITOR_PORT", "18795"))
# When behind a reverse proxy at /monitor/, set this
PREFIX = os.environ.get("MONITOR_PREFIX", "/monitor")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MoltBot Monitor</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;color:#e0e0e0;min-height:100vh}
.header{background:#1a1a2e;padding:16px 24px;border-bottom:1px solid #333;display:flex;align-items:center;gap:16px}
.header h1{font-size:20px;color:#7c7cff}
.header .status{font-size:12px;color:#4caf50;background:#1b2e1b;padding:4px 10px;border-radius:12px}
.container{display:flex;height:calc(100vh - 57px)}
.sidebar{width:280px;background:#141420;border-right:1px solid #333;overflow-y:auto;flex-shrink:0}
.session-item{padding:14px 18px;border-bottom:1px solid #222;cursor:pointer;transition:background .15s}
.session-item:hover{background:#1a1a2e}
.session-item.active{background:#1f1f3a;border-left:3px solid #7c7cff}
.session-item .name{font-weight:600;font-size:14px;color:#ddd}
.session-item .meta{font-size:11px;color:#888;margin-top:4px}
.session-item .preview{font-size:12px;color:#666;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat{flex:1;display:flex;flex-direction:column;overflow:hidden}
.chat-header{padding:14px 24px;background:#141420;border-bottom:1px solid #333;font-weight:600}
.messages{flex:1;overflow-y:auto;padding:20px 24px}
.msg{margin-bottom:16px;max-width:80%}
.msg.user{margin-left:auto}
.msg.assistant{margin-right:auto}
.msg .bubble{padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.msg.user .bubble{background:#2a2a5a;color:#d0d0ff;border-bottom-right-radius:4px}
.msg.assistant .bubble{background:#1e2e1e;color:#c0e0c0;border-bottom-left-radius:4px}
.msg .time{font-size:10px;color:#555;margin-top:4px;padding:0 4px}
.msg.user .time{text-align:right}
.msg .cost{font-size:10px;color:#665500;margin-top:2px;padding:0 4px}
.empty{display:flex;align-items:center;justify-content:center;height:100%;color:#555;font-size:16px}
.refresh-bar{padding:8px 24px;background:#111;border-top:1px solid #333;display:flex;align-items:center;gap:12px;font-size:12px;color:#666}
.refresh-bar button{background:#2a2a5a;color:#aaa;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px}
.refresh-bar button:hover{background:#3a3a6a;color:#ddd}
#auto-refresh{accent-color:#7c7cff}
</style>
</head>
<body>
<div class="header">
  <h1>MoltBot Monitor</h1>
  <span class="status" id="status">Loading...</span>
</div>
<div class="container">
  <div class="sidebar" id="sidebar"></div>
  <div class="chat">
    <div class="chat-header" id="chat-header">Select a conversation</div>
    <div class="messages" id="messages"><div class="empty">Select a conversation from the sidebar</div></div>
    <div class="refresh-bar">
      <button onclick="refresh()">Refresh</button>
      <label><input type="checkbox" id="auto-refresh" checked> Auto-refresh 5s</label>
      <span id="last-update"></span>
    </div>
  </div>
</div>
<script>
let currentSession = null;
let currentSessionInfo = null;
let autoRefreshTimer = null;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function fetchAPI(path) {
  const r = await fetch('api/' + path);
  return r.json();
}

async function loadSessions() {
  const data = await fetchAPI('sessions');
  const sb = document.getElementById('sidebar');
  sb.innerHTML = '';
  document.getElementById('status').textContent = data.sessions.length + ' conversations';

  data.sessions.forEach(s => {
    const div = document.createElement('div');
    div.className = 'session-item' + (currentSession === s.id ? ' active' : '');
    div.innerHTML =
      '<div class="name">' + esc(s.user_name || 'Unknown') + '</div>' +
      '<div class="meta">@' + esc(s.username || '?') + ' &middot; ' + esc(s.user_id) + '</div>' +
      '<div class="meta">' + esc(s.last_activity || '') + '</div>' +
      '<div class="preview">' + esc(s.last_message || '') + '</div>';
    div.onclick = function() { currentSession = s.id; currentSessionInfo = s; loadMessages(s); };
    sb.appendChild(div);
  });
}

async function loadMessages(session) {
  const data = await fetchAPI('messages?session=' + encodeURIComponent(session.file));
  const hdr = document.getElementById('chat-header');
  hdr.textContent = (session.user_name || 'Unknown') + ' (@' + (session.username || '?') + ')';

  const box = document.getElementById('messages');
  box.innerHTML = '';

  data.messages.forEach(function(m) {
    const div = document.createElement('div');
    div.className = 'msg ' + m.role;
    let costHtml = '';
    if (m.cost) costHtml = '<div class="cost">$' + m.cost.toFixed(4) + ' &middot; ' + (m.model || '') + '</div>';
    div.innerHTML = '<div class="bubble">' + esc(m.text) + '</div><div class="time">' + esc(m.time) + '</div>' + costHtml;
    box.appendChild(div);
  });

  box.scrollTop = box.scrollHeight;
  document.getElementById('last-update').textContent = 'Updated ' + new Date().toLocaleTimeString();
  loadSessions();
}

async function refresh() {
  await loadSessions();
  if (currentSessionInfo) {
    loadMessages(currentSessionInfo);
  }
}

function setupAutoRefresh() {
  var cb = document.getElementById('auto-refresh');
  function toggle() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    if (cb.checked) autoRefreshTimer = setInterval(refresh, 5000);
  }
  cb.addEventListener('change', toggle);
  toggle();
}

loadSessions();
setupAutoRefresh();
</script>
</body>
</html>"""


def parse_sessions():
    sessions = []
    if not os.path.exists(SESSIONS_JSON):
        return sessions

    with open(SESSIONS_JSON) as f:
        sess_data = json.load(f)

    for sess_id, info in sess_data.items():
        parts = sess_id.split(":")
        user_id = parts[-1] if len(parts) >= 5 else "unknown"

        # Find matching JSONL by scanning files for this user_id
        user_name = "Unknown"
        username = ""
        last_msg = ""
        last_time = ""
        msg_count = 0
        matched_file = ""

        for jf in sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.jsonl")), key=os.path.getmtime, reverse=True):
            with open(jf) as fj:
                found = False
                for line in fj:
                    try:
                        obj = json.loads(line.strip())
                        if obj.get("type") != "message":
                            continue
                        msg = obj.get("message", {})
                        content = msg.get("content", [])
                        text = ""
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                text = c["text"]
                                break
                        if not text:
                            continue

                        if msg.get("role") == "user" and f'"sender_id": "{user_id}"' in text:
                            found = True
                            matched_file = os.path.basename(jf)
                            if '"name":' in text:
                                for p in text.split('"name":'):
                                    s = p.strip()
                                    if s.startswith('"'):
                                        n = s[1:].split('"')[0]
                                        if n and n != user_id:
                                            user_name = n
                                            break
                            if '"username":' in text:
                                for p in text.split('"username":'):
                                    s = p.strip()
                                    if s.startswith('"'):
                                        u = s[1:].split('"')[0]
                                        if u:
                                            username = u
                                            break

                        if found:
                            actual = text
                            if msg.get("role") == "user" and "```" in text:
                                pts = text.split("```")
                                if len(pts) >= 3:
                                    actual = pts[-1].strip()
                            if actual:
                                last_msg = actual[:100]
                                last_time = obj.get("timestamp", "")
                                msg_count += 1
                    except:
                        continue
                if found:
                    break

        sessions.append({
            "id": sess_id,
            "user_id": user_id,
            "user_name": user_name,
            "username": username,
            "last_message": last_msg,
            "last_activity": last_time[:19].replace("T", " ") if last_time else "",
            "msg_count": msg_count,
            "file": matched_file,
        })

    sessions.sort(key=lambda s: s.get("last_activity", ""), reverse=True)
    return sessions


def parse_messages(jsonl_filename):
    messages = []
    filepath = os.path.join(SESSIONS_DIR, jsonl_filename)
    if not os.path.exists(filepath):
        return messages

    with open(filepath) as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                if obj.get("type") != "message":
                    continue
                msg = obj.get("message", {})
                role = msg.get("role", "")
                content = msg.get("content", [])
                text = ""
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c["text"]
                        break
                if not text:
                    continue

                display_text = text
                if role == "user" and "```json" in text and "```" in text:
                    pts = text.split("```")
                    actual = pts[-1].strip()
                    if actual:
                        display_text = actual

                ts = obj.get("timestamp", "")
                usage = msg.get("usage", {})
                cost_info = usage.get("cost", {})
                cost = cost_info.get("total") if isinstance(cost_info, dict) else None

                messages.append({
                    "role": role,
                    "text": display_text,
                    "time": ts[:19].replace("T", " ") if ts else "",
                    "cost": cost,
                    "model": msg.get("model", ""),
                })
            except:
                continue
    return messages


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def check_auth(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        if token == AUTH_TOKEN:
            return True
        cookies = self.headers.get("Cookie", "")
        if f"monitor_token={AUTH_TOKEN}" in cookies:
            return True
        return False

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/login":
            params = parse_qs(parsed.query)
            token = params.get("token", [None])[0]
            if token == AUTH_TOKEN:
                self.send_response(302)
                self.send_header("Set-Cookie", f"monitor_token={AUTH_TOKEN}; Path=/; HttpOnly; Max-Age=86400")
                self.send_header("Location", PREFIX + "/")
                self.end_headers()
                return
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Invalid token")
            return

        if not self.check_auth():
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<html><body style="background:#0f0f0f;color:#e0e0e0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
            <form action="login" method="get" style="text-align:center">
            <h2 style="color:#7c7cff">MoltBot Monitor</h2>
            <input name="token" type="password" placeholder="Access token" style="padding:10px;border-radius:6px;border:1px solid #333;background:#1a1a2e;color:#ddd;font-size:16px;margin:16px 0;width:250px"><br>
            <button style="padding:10px 24px;background:#2a2a5a;color:#ddd;border:none;border-radius:6px;cursor:pointer;font-size:14px">Enter</button>
            </form></body></html>""")
            return

        if path == "/" or path == "":
            body = HTML_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/sessions":
            sessions = parse_sessions()
            self.send_json({"sessions": sessions})

        elif path == "/api/messages":
            params = parse_qs(parsed.query)
            session_file = params.get("session", [""])[0]
            if not session_file or "/" in session_file or ".." in session_file:
                self.send_json({"error": "invalid session"}, 400)
                return
            messages = parse_messages(session_file)
            self.send_json({"messages": messages})

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MoltBot Monitor running on http://0.0.0.0:{PORT}")
    print(f"Login: {PREFIX}/login?token={AUTH_TOKEN}")
    server.serve_forever()
