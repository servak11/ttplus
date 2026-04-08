"""
mod_flask.py  –  ARD-1: View MD notes in browser
--------------------------------------------------
Starts a Flask server in a background thread.
ttplus calls show_note(note_text, meta) to push the current
note to the browser tab.

Install deps once:
    pip install flask markdown2

Usage in ttplus.py:
    from mod_flask import NoteServer
    note_server = NoteServer()          # create once at startup
    note_server.start()                 # starts background thread

    # when user clicks "View in Browser" button:
    note_server.show_note(note_text, {
        "project": task_name,
        "task":    what_was_done,
        "start":   start_time,
        "end":     end_time,
    })
"""

import threading
import webbrowser
import markdown2
import json
import os
import re
from flask import Flask, request, jsonify, render_template_string, send_file
from datetime import datetime

# ── Flask app ──────────────────────────────────────────────────────────────────

_flask_app = Flask(__name__)

# Reference to ttplus in-memory database (set via set_database())
_database = None

def set_database(db_dict):
    """Store a reference to the ttplus in-memory database dict."""
    global _database
    _database = db_dict

# Shared state between ttplus thread and Flask thread
_current_note = {
    "html":    "<p><em>No note loaded yet. Click 'View in Browser' in ttplus.</em></p>",
    "project": "",
    "task":    "",
    "start":   "",
    "end":     "",
    "raw":     "",
    "updated": "",
}

# ── HTML template served by Flask ─────────────────────────────────────────────

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ttplus · Note Viewer</title>
  <style>
    /* ── Reset & base ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #0f0f1a;
      --surface:   #16162a;
      --border:    #2a2a45;
      --accent:    #2a7fbf;
      --accent2:   #2a8a5a;
      --text:      #c8c8e8;
      --muted:     #666688;
      --code-bg:   #1a1a2e;
      --font-mono: 'DM Mono', 'Fira Mono', 'Consolas', monospace;
      --font-body: 'Segoe UI', 'Ubuntu', sans-serif;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-body);
      font-size: 15px;
      line-height: 1.7;
      min-height: 100vh;
    }

    /* ── Header ── */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 28px;
      display: flex;
      align-items: baseline;
      gap: 14px;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .logo {
      font-family: var(--font-mono);
      font-size: 18px;
      font-weight: 700;
      color: #e8e8ff;
      letter-spacing: -0.02em;
    }
    .logo span { color: var(--accent); }

    .header-meta {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--muted);
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
    }
    .header-meta b { color: var(--text); }

    .refresh-btn {
      margin-left: auto;
      background: none;
      border: 1px solid var(--border);
      color: var(--muted);
      border-radius: 6px;
      padding: 5px 14px;
      font-size: 11px;
      cursor: pointer;
      font-family: var(--font-mono);
      letter-spacing: 0.05em;
      transition: border-color 0.15s, color 0.15s;
    }
    .refresh-btn:hover { border-color: var(--accent); color: var(--accent); }

    /* ── Layout ── */
    .layout {
      max-width: 860px;
      margin: 36px auto;
      padding: 0 24px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    /* ── Meta card ── */
    .meta-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-top: 3px solid var(--accent);
      border-radius: 10px;
      padding: 16px 22px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 32px;
      font-family: var(--font-mono);
      font-size: 12px;
    }
    .meta-row { display: flex; flex-direction: column; gap: 2px; }
    .meta-label { color: var(--muted); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; }
    .meta-value { color: var(--text); font-size: 13px; }

    /* ── Note body ── */
    .note-body {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 28px 36px;
    }

    /* Markdown rendered content */
    .note-body h1, .note-body h2, .note-body h3 {
      color: #e8e8ff;
      font-family: var(--font-mono);
      font-weight: 700;
      margin-top: 28px;
      margin-bottom: 10px;
      padding-bottom: 6px;
    }
    .note-body h1 { font-size: 20px; border-bottom: 1px solid var(--border); }
    .note-body h2 { font-size: 16px; color: var(--accent); border-bottom: 1px solid var(--border); }
    .note-body h3 { font-size: 14px; color: var(--accent2); }
    .note-body h1:first-child,
    .note-body h2:first-child { margin-top: 0; }

    .note-body p { margin-bottom: 12px; }

    .note-body ul, .note-body ol {
      padding-left: 22px;
      margin-bottom: 14px;
    }
    .note-body li { margin-bottom: 4px; }

    .note-body code {
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1px 6px;
      font-family: var(--font-mono);
      font-size: 13px;
      color: #a8d8a8;
    }

    .note-body pre {
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-left: 3px solid var(--accent);
      border-radius: 6px;
      padding: 16px 18px;
      overflow-x: auto;
      margin-bottom: 16px;
    }
    .note-body pre code {
      background: none;
      border: none;
      padding: 0;
      font-size: 13px;
    }

    .note-body blockquote {
      border-left: 3px solid var(--accent2);
      padding-left: 16px;
      color: var(--muted);
      margin: 14px 0;
      font-style: italic;
    }

    .note-body a { color: var(--accent); text-decoration: underline; }
    .note-body strong { color: #e8e8ff; }
    .note-body em { color: #a8b8d8; }

    .note-body hr {
      border: none;
      border-top: 1px solid var(--border);
      margin: 24px 0;
    }

    /* ── Plain text fallback ── */
    .plain-note {
      font-family: var(--font-mono);
      font-size: 13px;
      white-space: pre-wrap;
      color: var(--text);
      line-height: 1.7;
    }

    /* ── Footer ── */
    footer {
      text-align: center;
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--muted);
      padding: 20px;
      border-top: 1px solid var(--border);
      margin-top: 40px;
    }

    /* ── Auto-refresh indicator ── */
    .live-dot {
      display: inline-block;
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--accent2);
      margin-right: 6px;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }
  </style>
</head>
<body>

<header>
  <div class="logo">TT<span>+</span></div>
  <div class="header-meta">
    <span><b>{{ meta.project }}</b></span>
    {% if meta.task %}
    <span>{{ meta.task }}</span>
    {% endif %}
    {% if meta.start %}
    <span>{{ meta.start }} → {{ meta.end }}</span>
    {% endif %}
  </div>
  <button class="refresh-btn" onclick="location.reload()">↻ refresh</button>
</header>

<div class="layout">

  {% if meta.project or meta.task %}
  <div class="meta-card">
    <div class="meta-row">
      <span class="meta-label">Project</span>
      <span class="meta-value">{{ meta.project or '—' }}</span>
    </div>
    <div class="meta-row">
      <span class="meta-label">Task</span>
      <span class="meta-value">{{ meta.task or '—' }}</span>
    </div>
    <div class="meta-row">
      <span class="meta-label">Start</span>
      <span class="meta-value">{{ meta.start or '—' }}</span>
    </div>
    <div class="meta-row">
      <span class="meta-label">End</span>
      <span class="meta-value">{{ meta.end or '—' }}</span>
    </div>
  </div>
  {% endif %}

  <div class="note-body">
    {{ note_html | safe }}
  </div>

</div>

<footer>
  <span class="live-dot"></span>
  ttplus note viewer · last updated {{ updated }}
  · <a href="/raw" style="color:inherit">raw</a>
</footer>

<script>
  // Auto-refresh every 4 seconds so the browser picks up new notes
  // pushed from ttplus without user having to click refresh
  setTimeout(() => location.reload(), 4000);
</script>

</body>
</html>
"""

# ── Flask routes ───────────────────────────────────────────────────────────────

@_flask_app.route("/")
def index():
    return render_template_string(
        _HTML_TEMPLATE,
        note_html=_current_note["html"],
        meta=_current_note,
        updated=_current_note["updated"],
    )


@_flask_app.route("/note", methods=["POST"])
def receive_note():
    """
    Called by NoteServer.show_note().
    Expects JSON: { "note": "...", "project": "...", "task": "...",
                    "start": "...", "end": "..." }
    """
    data = request.get_json(force=True)
    raw  = data.get("note", "")

    _current_note["raw"]     = raw
    _current_note["html"]    = _render_md(raw)
    _current_note["project"] = data.get("project", "")
    _current_note["task"]    = data.get("task", "")
    _current_note["start"]   = _fmt_dt(data.get("start", ""))
    _current_note["end"]     = _fmt_dt(data.get("end", ""))
    _current_note["updated"] = datetime.now().strftime("%H:%M:%S")

    return jsonify({"status": "ok"})


@_flask_app.route("/raw")
def raw_note():
    """Plain text view of the current note."""
    from flask import Response
    return Response(_current_note["raw"], mimetype="text/plain; charset=utf-8")


# ── Kanban routes ─────────────────────────────────────────────────────────────

def _parse_hours(twt: str) -> float:
    """Convert 'HH:MM' string to decimal hours."""
    try:
        parts = twt.split(":")
        return int(parts[0]) + int(parts[1]) / 60.0
    except Exception:
        return 0.0


def _last_active(details: list) -> str:
    """Return the latest End Time from a detail list as 'YYYY-MM-DD'."""
    latest = ""
    for d in details:
        et = d.get("End Time", "")
        if et > latest:
            latest = et
    if len(latest) >= 8:
        return f"{latest[0:4]}-{latest[4:6]}-{latest[6:8]}"
    return ""


def _duration_min(start: str, end: str) -> int:
    """Compute duration in minutes between two 'YYYYMMDDHHmmSS' timestamps."""
    try:
        s = datetime.strptime(start[:12], "%Y%m%d%H%M")
        e = datetime.strptime(end[:12], "%Y%m%d%H%M")
        diff = (e - s).total_seconds() / 60
        return max(0, int(diff))
    except Exception:
        return 0


def _has_goal(note_text: str) -> bool:
    """Check if note has actual content after '## Goal'."""
    return bool(re.search(r'## Goal[^\n]*\n\s*\S', note_text))


def _build_detail(d: dict) -> dict:
    """Build a single detail dict for the kanban JS."""
    note_raw = d.get("note", "")
    what = d.get("What was done", "")
    start = d.get("Start Time", "")
    end = d.get("End Time", "")
    return {
        "start":        _fmt_dt(start),
        "end":          _fmt_dt(end),
        "what":         what,
        "note_html":    _render_md(note_raw),
        "note_raw":     note_raw,
        "duration_min": _duration_min(start, end),
        "has_goal":     _has_goal(note_raw),
        "has_what":     bool(what.strip()) and what.strip() != "add detail ...",
    }


def _build_projects() -> list:
    """Transform in-memory database into the list-of-dicts the kanban JS expects."""
    if _database is None:
        return []
    work_tasks = _database.get("work_tasks", {})
    task_details = _database.get("task_details", {})
    projects = []

    for sid, task in work_tasks.items():
        details = task_details.get(sid, [])
        built_details = [_build_detail(d) for d in details]

        issues = sum(1 for bd in built_details if not bd["has_goal"] or not bd["has_what"])

        projects.append({
            "id":            sid,
            "title":         task.get("tnm", ""),
            "status":        task.get("kbs", "backlog"),
            "tasks":         len(details),
            "hours_logged":  round(_parse_hours(task.get("twt", "00:00")), 2),
            "hours_planned": 0,
            "last_active":   _last_active(details),
            "issues":        issues,
            "type":          task.get("type", "core"),
            "details":       built_details,
        })

    return projects


@_flask_app.route("/kanban")
def kanban():
    """Serve kanban.html with live project data from tasks.json."""
    projects = _build_projects()
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kanban.html")
    with open(html_path, "r", encoding="utf-8") as f:
        template = f.read()
    # Escape </ sequences so embedded HTML in notes can't break the <script> block
    raw_json = json.dumps(projects, ensure_ascii=False)
    safe_json = raw_json.replace("</", "<\\/")
    return render_template_string(template, projects_json=safe_json)


@_flask_app.route("/api/projects/<project_id>/status", methods=["POST"])
def update_project_status(project_id):
    """Update kanban column status in the in-memory database (RAM only)."""
    data = request.get_json(force=True)
    new_status = data.get("status", "")
    if new_status not in ("backlog", "active", "review", "done"):
        return jsonify({"error": "invalid status"}), 400

    if _database is None:
        return jsonify({"error": "database not initialized"}), 500

    task = _database.get("work_tasks", {}).get(project_id)
    if not task:
        return jsonify({"error": "project not found"}), 404

    task["kbs"] = new_status
    return jsonify({"status": "ok", "id": project_id, "kbs": new_status})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _render_md(text: str) -> str:
    """Convert markdown to HTML, fall back to <pre> for plain text."""
    if not text or not text.strip():
        return "<p><em>Empty note.</em></p>"
    try:
        return markdown2.markdown(
            text,
            extras=["fenced-code-blocks", "tables", "strike",
                    "task_list", "header-ids"],
        )
    except Exception:
        # plain text fallback
        import html
        return f'<pre class="plain-note">{html.escape(text)}</pre>'


def _fmt_dt(raw: str) -> str:
    """Format ttplus datetime string 'YYYYMMDDHHmmSS' → 'YYYY-MM-DD HH:MM'."""
    raw = str(raw).strip()
    if len(raw) >= 12:
        try:
            return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}"
        except Exception:
            pass
    return raw


# ── NoteServer class (used by ttplus.py) ──────────────────────────────────────

class NoteServer:
    """
    Thin wrapper that owns the Flask background thread.

    from mod_flask import NoteServer
    server = NoteServer(port=5000)
    server.start()
    ...
    server.show_note(note_text, meta_dict)
    """

    def __init__(self, port: int = 5000):
        self.port    = port
        self.url     = f"http://127.0.0.1:{port}"
        self._thread = None
        self._started = False

    def set_database(self, db_dict):
        """Share the ttplus in-memory database with Flask routes."""
        set_database(db_dict)

    def start(self):
        """Start Flask in a daemon thread (safe to call multiple times)."""
        if self._started:
            return
        self._thread = threading.Thread(
            target=self._run_flask,
            daemon=True,   # dies automatically when ttplus exits
            name="ttplus-flask",
        )
        self._thread.start()
        self._started = True
        print(f"[mod_flask] Note viewer running at {self.url}")

    def _run_flask(self):
        # Silence Flask startup banner in the terminal
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)

        _flask_app.run(
            host="127.0.0.1",
            port=self.port,
            debug=False,
            use_reloader=False,
        )

    def show_note(self, note_text: str, meta: dict | None = None):
        """
        Push note_text to the Flask server and open browser tab.
        meta keys: project, task, start, end
        """
        import urllib.request, json

        if not self._started:
            self.start()

        payload = json.dumps({
            "note":    note_text,
            "project": (meta or {}).get("project", ""),
            "task":    (meta or {}).get("task", ""),
            "start":   (meta or {}).get("start", ""),
            "end":     (meta or {}).get("end", ""),
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{self.url}/note",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception as e:
            print(f"[mod_flask] POST /note failed: {e}")
            return

        # Open browser on first call; subsequent calls auto-refresh via JS
        webbrowser.open(self.url)

    def show_kanban(self):
        """Open the Kanban board in the browser."""
        if not self._started:
            self.start()
        webbrowser.open(f"{self.url}/kanban")


# ── Standalone test ───────────────────────────────────────────────────────────
# Run:  python3 mod_flask.py
# Then open http://127.0.0.1:5000 in browser

if __name__ == "__main__":
    import time

    server = NoteServer(port=5000)
    server.start()
    time.sleep(1)   # give Flask a moment to bind

    # Push the real note from tasks.json as a test
    test_note = """\
## Goal
Have notes display in browser to offer more readable space

## Why
because ttplus has little space to display notes, easy to edit,
but difficult to browse lists and scroll notes

## Specification
create Flask website, send note to it for rendering

## Blocker
what shall trigger note display?
"""
    server.show_note(test_note, {
        "project": "View MD notes in browser",
        "task":    "Display MD in browser",
        "start":   "20260405221020",
        "end":     "20260405221500",
    })

    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[mod_flask] Stopped.")
