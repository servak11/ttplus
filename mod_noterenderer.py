
"""
mod_noterenderer.py
-------------------
Converts ttplus task notes to HTML and serves them via Flask.

Data model understood by this module
-------------------------------------
Project-level properties (short-name mapped):
    db_field_shortnames = {
        "fti": "Full Task ID",
        "sti": "Short Task ID",
        "tnm": "Task Name",
        "twt": "Total Work Time",
    }

Task-level note properties (raw dict from mod_detaileditor / mod_db):
    {
        "Start Time":    "20250614065300",
        "End Time":      "20250614070337",
        "What was done": "Improve documentation of the load_data()",
        "note":          "converted to docstrings",   # may be plain text or markdown
    }

Flask integration
-----------------
Mount this blueprint in ttplus.py:

    from mod_noterenderer import note_bp
    app.register_blueprint(note_bp)

Then GET /note/<task_id>  renders the full task card.
     GET /note/<task_id>/fragment  returns the inner HTML only (for the task pane
                                   in kanban.html via fetch()).
"""

import re
import textwrap
from datetime import datetime
from flask import Blueprint, jsonify, render_template_string, abort

# ── Blueprint ──────────────────────────────────────────────────────────────────
note_bp = Blueprint("note", __name__, url_prefix="/note")

# ── Field name mappings (Requirement 9) ───────────────────────────────────────
DB_FIELD_SHORTNAMES = {
    "fti": "Full Task ID",
    "sti": "Short Task ID",
    "tnm": "Task Name",
    "twt": "Total Work Time",
}

# Reverse map for display: short → long
_SHORT_TO_LONG = DB_FIELD_SHORTNAMES
# Forward map for storage: long → short
_LONG_TO_SHORT = {v: k for k, v in DB_FIELD_SHORTNAMES.items()}


# ── Time helpers ───────────────────────────────────────────────────────────────
_TIMESTAMP_FMT = "%Y%m%d%H%M%S"


def _parse_ts(raw: str) -> datetime | None:
    """Parse ttplus compact timestamp '20250614065300' → datetime."""
    try:
        return datetime.strptime(str(raw).strip(), _TIMESTAMP_FMT)
    except (ValueError, TypeError):
        return None


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d  %H:%M")


def _duration_str(start: datetime | None, end: datetime | None) -> tuple[str, bool]:
    """
    Returns (human_readable_duration, is_missing).
    is_missing=True when end == start (timer-loss sentinel).
    """
    if start is None or end is None:
        return "unknown", True
    delta = end - start
    total_sec = int(delta.total_seconds())
    if total_sec <= 0:
        return "0 min  ⚠ missing end time", True
    h, remainder = divmod(total_sec, 3600)
    m = remainder // 60
    if h:
        return f"{h}h {m:02d}min", False
    return f"{m} min", False


# ── Markdown → HTML ───────────────────────────────────────────────────────────
def _md_to_html(text: str) -> str:
    """
    Lightweight markdown renderer — no external dependencies.
    Handles the subset relevant to ttplus task notes:
      ## / ### headings, **bold**, *italic*, `code`,
      ``` fenced code blocks, - bullet lists, blank-line paragraphs,
      [text](url) links.
    """
    if not text or not text.strip():
        return '<p class="empty">No notes.</p>'

    lines = text.splitlines()
    html_parts: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    list_open = False

    def close_list():
        nonlocal list_open
        if list_open:
            html_parts.append("</ul>")
            list_open = False

    def inline(s: str) -> str:
        """Apply inline rules: bold, italic, code, links."""
        # fenced inline code  `...`
        s = re.sub(r"`([^`]+)`", r'<code>\1</code>', s)
        # bold **...**
        s = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', s)
        # italic *...*
        s = re.sub(r"\*(.+?)\*", r'<em>\1</em>', s)
        # links [text](url)
        s = re.sub(
            r'\[([^\]]+)\]\((https?://[^\)]+)\)',
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            s,
        )
        # bare URLs
        s = re.sub(
            r'(?<!["\(])(https?://\S+)',
            r'<a href="\1" target="_blank" rel="noopener">\1</a>',
            s,
        )
        return s

    for line in lines:
        # ── fenced code block ──────────────────────────────────────────────
        if line.strip().startswith("```"):
            if in_code_block:
                lang_class = f' class="lang-{code_lines[0]}"' if code_lines and re.match(r'^\w+$', code_lines[0]) else ''
                body = code_lines[1:] if lang_class else code_lines
                close_list()
                html_parts.append(
                    f'<pre{lang_class}><code>'
                    + "\n".join(body)
                    + "</code></pre>"
                )
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                lang = line.strip()[3:].strip()
                if lang:
                    code_lines = [lang]
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # ── headings ──────────────────────────────────────────────────────
        if line.startswith("### "):
            close_list()
            html_parts.append(f"<h3>{inline(line[4:])}</h3>")
            continue
        if line.startswith("## "):
            close_list()
            html_parts.append(f"<h2>{inline(line[3:])}</h2>")
            continue
        if line.startswith("# "):
            close_list()
            html_parts.append(f"<h2>{inline(line[2:])}</h2>")
            continue

        # ── bullet list ───────────────────────────────────────────────────
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            if not list_open:
                html_parts.append("<ul>")
                list_open = True
            html_parts.append(f"<li>{inline(m.group(1))}</li>")
            continue

        # ── blank line ────────────────────────────────────────────────────
        if not line.strip():
            close_list()
            html_parts.append('<div class="spacer"></div>')
            continue

        # ── plain paragraph line ──────────────────────────────────────────
        close_list()
        html_parts.append(f"<p>{inline(line)}</p>")

    close_list()
    if in_code_block and code_lines:
        html_parts.append("<pre><code>" + "\n".join(code_lines) + "</code></pre>")

    return "\n".join(html_parts)


# ── Project property expansion ────────────────────────────────────────────────
def expand_project_fields(project: dict) -> dict:
    """
    Return a display-ready dict with long field names.
    Accepts both short keys ("fti") and long keys ("Full Task ID").
    """
    expanded = {}
    for k, v in project.items():
        long_name = _SHORT_TO_LONG.get(k, k)
        expanded[long_name] = v
    return expanded


def compress_project_fields(project: dict) -> dict:
    """
    Return a storage-ready dict with short field names.
    Accepts both long and short keys.
    """
    compressed = {}
    for k, v in project.items():
        short_name = _LONG_TO_SHORT.get(k, k)
        compressed[short_name] = v
    return compressed


# ── Task card HTML builder ────────────────────────────────────────────────────
def build_task_card_html(project: dict, task: dict) -> str:
    """
    Combine project-level and task-level data into a rendered HTML card string.

    project: dict with short or long field names (project properties)
    task:    dict with task note properties
             {
               "Start Time": "20250614065300",
               "End Time":   "20250614070337",
               "What was done": "...",
               "note": "... markdown ...",
             }
    """
    proj = expand_project_fields(project)

    start_dt = _parse_ts(task.get("Start Time", ""))
    end_dt   = _parse_ts(task.get("End Time", ""))
    duration, missing_end = _duration_str(start_dt, end_dt)

    what_done = task.get("What was done", "").strip()
    raw_note  = task.get("note", "").strip()
    note_html = _md_to_html(raw_note)

    # Goal / What-was-done: treat as short MD too
    what_done_html = _md_to_html(what_done) if what_done else '<p class="empty">No goal recorded.</p>'

    goal_missing_class = " missing" if not what_done else ""

    card_html = f"""
<div class="task-card">

  <div class="card-header">
    <div class="card-ids">
      <span class="tag">{proj.get("Full Task ID", "—")}</span>
      <span class="tag secondary">{proj.get("Short Task ID", "")}</span>
    </div>
    <h1 class="card-title">{proj.get("Task Name", "Untitled task")}</h1>
  </div>

  <div class="meta-row">
    <div class="meta-item">
      <span class="meta-label">Start</span>
      <span class="meta-value">{_fmt_dt(start_dt)}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">End</span>
      <span class="meta-value">{_fmt_dt(end_dt)}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Duration</span>
      <span class="meta-value {'warn' if missing_end else ''}">{duration}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Total work time</span>
      <span class="meta-value">{proj.get("Total Work Time", "—")}</span>
    </div>
  </div>

  <section class="section{goal_missing_class}">
    <div class="section-label">
      What was done
      {'<span class="flag">⚠ goal missing</span>' if not what_done else ''}
    </div>
    <div class="section-body goal-body">{what_done_html}</div>
  </section>

  <section class="section">
    <div class="section-label">Notes</div>
    <div class="section-body note-body">{note_html}</div>
  </section>

</div>
"""
    return card_html


# ── HTML page template ────────────────────────────────────────────────────────
_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #f4f2ed;
    --surface:  #ffffff;
    --border:   #d8d4cc;
    --text:     #1a1814;
    --text-2:   #6b6560;
    --text-3:   #9e9890;
    --accent:   #2a5fff;
    --warn:     #c2410c;
    --warn-bg:  #fff7ed;
    --warn-bd:  #fdba74;
    --code-bg:  #f0ede8;
    --mono:     'IBM Plex Mono', 'Fira Mono', monospace;
    --sans:     'IBM Plex Sans', system-ui, sans-serif;
    --radius:   6px;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --bg:      #1a1814;
      --surface: #242220;
      --border:  #3a3830;
      --text:    #e8e4dc;
      --text-2:  #9e9890;
      --text-3:  #6b6560;
      --code-bg: #2c2a26;
      --warn-bg: #2d1a0a;
      --warn-bd: #92400e;
    }
  }

  body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    padding: 2rem 1rem;
    line-height: 1.6;
  }

  .task-card {
    max-width: 720px;
    margin: 0 auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }

  /* ── header ── */
  .card-header {
    padding: 1.25rem 1.5rem 1rem;
    border-bottom: 1px solid var(--border);
  }

  .card-ids {
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
  }

  .tag {
    font-family: var(--mono);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid var(--border);
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }
  .tag.secondary { color: var(--text-3); background: transparent; }

  .card-title {
    font-size: 17px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.35;
  }

  /* ── meta row ── */
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0;
    border-bottom: 1px solid var(--border);
  }

  .meta-item {
    flex: 1;
    min-width: 140px;
    padding: 10px 1.5rem;
    border-right: 1px solid var(--border);
  }
  .meta-item:last-child { border-right: none; }

  .meta-label {
    display: block;
    font-family: var(--mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-3);
    margin-bottom: 3px;
  }

  .meta-value {
    font-family: var(--mono);
    font-size: 13px;
    color: var(--text);
  }
  .meta-value.warn {
    color: var(--warn);
  }

  /* ── sections ── */
  .section {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border);
  }
  .section:last-child { border-bottom: none; }

  .section.missing {
    background: var(--warn-bg);
    border-left: 3px solid var(--warn-bd);
  }

  .section-label {
    font-family: var(--mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-3);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .flag {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--warn);
    background: var(--warn-bg);
    border: 1px solid var(--warn-bd);
    border-radius: 4px;
    padding: 1px 6px;
  }

  /* ── markdown output ── */
  .section-body { color: var(--text-2); font-size: 14px; }

  .section-body h2 {
    font-size: 15px; font-weight: 500;
    color: var(--text); margin: 1rem 0 0.4rem;
  }
  .section-body h2:first-child { margin-top: 0; }

  .section-body h3 {
    font-size: 13px; font-weight: 500;
    color: var(--text); margin: 0.8rem 0 0.3rem;
    text-transform: uppercase; letter-spacing: 0.05em;
  }

  .section-body p { margin-bottom: 0.4rem; }
  .section-body .spacer { height: 0.5rem; }
  .section-body .empty { color: var(--text-3); font-style: italic; }

  .section-body ul {
    margin: 0.25rem 0 0.5rem 1.25rem;
  }
  .section-body li { margin-bottom: 0.2rem; }

  .section-body code {
    font-family: var(--mono);
    font-size: 12px;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
    color: var(--text);
  }

  .section-body pre {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    overflow-x: auto;
    margin: 0.5rem 0;
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.55;
    color: var(--text);
  }
  .section-body pre code {
    background: none;
    border: none;
    padding: 0;
    font-size: inherit;
  }

  .section-body a {
    color: var(--accent);
    text-decoration: none;
  }
  .section-body a:hover { text-decoration: underline; }

  .section-body strong { color: var(--text); font-weight: 500; }

  /* ── fragment mode (no outer chrome) ── */
  body.fragment {
    padding: 0;
    background: transparent;
  }
  body.fragment .task-card {
    border: none;
    border-radius: 0;
    max-width: 100%;
  }
</style>
</head>
<body class="{{ body_class }}">
{{ card_html }}
</body>
</html>"""


# ── Mock data access — replace with real mod_db calls ─────────────────────────
def _get_task_data(task_id: str) -> tuple[dict, dict] | None:
    """
    Stub: returns (project_dict, task_dict) for a given task_id.

    Replace the body of this function with:
        from mod_db import load_task
        return load_task(task_id)

    The project dict may use short or long field names — expand_project_fields()
    handles both.
    """
    # ── sample data matching the structure from the requirement ───────────────
    _SAMPLE_PROJECT = {
        "fti": "ttplus-improve-docs-001",
        "sti": "docs-001",
        "tnm": "Improve documentation of load_data()",
        "twt": "1h 03min",
    }

    _SAMPLE_TASK = {
        "Start Time": "20250614065300",
        "End Time":   "20250614070337",
        "What was done": (
            "Improve documentation of the `load_data()` method in mod_detaileditor.py"
        ),
        "note": textwrap.dedent("""\
            ## Changes made

            Converted inline comments to proper docstrings following Google style.

            - Added `Args:` section describing each parameter
            - Added `Returns:` section with type and description
            - Added `Raises:` section for `KeyError` on missing required fields

            ## Why

            `load_data()` is called from three places and the parameter contract
            was unclear — caused a bug in `ttplus.py` line 142 last week.

            ## Redmine
            https://redmine.example.com/issues/17742

            ## Surprises

            Discovered `load_data()` silently ignores unknown keys.
            Opened follow-up ticket to add a strict-mode flag.
        """),
    }

    _SAMPLE_MISSING_GOAL = {
        "fti": "ttplus-fix-timer-002",
        "sti": "timer-002",
        "tnm": "Fix timer loss on task switch",
        "twt": "0h",
    }

    _SAMPLE_TASK_MISSING = {
        "Start Time": "20250614080000",
        "End Time":   "20250614080000",   # same = timer loss
        "What was done": "",              # missing goal
        "note": "",
    }

    store = {
        "docs-001":  (_SAMPLE_PROJECT, _SAMPLE_TASK),
        "timer-002": (_SAMPLE_MISSING_GOAL, _SAMPLE_TASK_MISSING),
    }
    return store.get(task_id)


# ── Routes ────────────────────────────────────────────────────────────────────
@note_bp.route("/<task_id>")
def task_note_page(task_id: str):
    """Full standalone HTML page for a task note."""
    result = _get_task_data(task_id)
    if result is None:
        abort(404)
    project, task = result
    card_html = build_task_card_html(project, task)
    title = expand_project_fields(project).get("Task Name", task_id)
    return render_template_string(
        _PAGE_TEMPLATE,
        card_html=card_html,
        title=title,
        body_class="",
    )


@note_bp.route("/<task_id>/fragment")
def task_note_fragment(task_id: str):
    """
    Inner HTML only — for embedding in the Kanban task pane via fetch().

    Usage in kanban.html:
        const r = await fetch(`/note/${projectId}/fragment`);
        document.getElementById('pane-body').innerHTML = await r.text();
    """
    result = _get_task_data(task_id)
    if result is None:
        abort(404)
    project, task = result
    card_html = build_task_card_html(project, task)
    title = expand_project_fields(project).get("Task Name", task_id)
    return render_template_string(
        _PAGE_TEMPLATE,
        card_html=card_html,
        title=title,
        body_class="fragment",
    )


@note_bp.route("/<task_id>/json")
def task_note_json(task_id: str):
    """
    Raw structured data — useful for the AI enrichment pipeline.
    Returns both short-name (storage) and long-name (display) project fields.
    """
    result = _get_task_data(task_id)
    if result is None:
        abort(404)
    project, task = result

    start_dt = _parse_ts(task.get("Start Time", ""))
    end_dt   = _parse_ts(task.get("End Time", ""))
    duration, missing_end = _duration_str(start_dt, end_dt)

    return jsonify({
        "project": {
            "short": compress_project_fields(project),
            "long":  expand_project_fields(project),
        },
        "task": {
            "start_time":    task.get("Start Time"),
            "end_time":      task.get("End Time"),
            "duration":      duration,
            "missing_end":   missing_end,
            "what_was_done": task.get("What was done", ""),
            "note_raw":      task.get("note", ""),
            "note_html":     _md_to_html(task.get("note", "")),
            "goal_missing":  not bool(task.get("What was done", "").strip()),
        },
    })
  
