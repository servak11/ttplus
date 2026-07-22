# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTPlus is a work time tracker desktop application built with Python/Tkinter. It manages tasks and time entries with a two-table GUI (tasks + task details), a detail editor, and a Flask-based web layer for viewing notes in a browser.

## Running the Application

```bash
pip install -r requirements.txt
python ttplus.py
```

There are no automated tests or linting configured.

## Architecture

**Entry point:** `ttplus.py` — main Tkinter application (~850 lines), creates the GUI and orchestrates all components.

**Data layer:**
- `mod_db.py` — `Database` class providing JSON-based persistence (`tasks.json`)
- `const.py` — numeric index constants for table columns and DB fields
- Database uses short field names: `fti` (Full Task ID), `sti` (Short Task ID), `tnm` (Task Name), `twt` (Total Work Time), `lst` (Details List)
- Task details have fields: `Start Time`, `End Time`, `What was done`, `note`

**UI controls (`controls/`):**
- `tasktable.py` — `TableWidget`, a reusable TreeView wrapper for both tables
- `statusbar.py` — status bar display
- `timespin.py` — time input spinner (HH:MM)
- `datelabel.py` — date label display
- `about.py` — about dialog

**Detail editor:** `mod_detaileditor.py` — `TaskDetailEditor` class handling task note editing with date/time controls.

**Web layer (`web/`):**
- `flask_server.py` — `NoteServer`, Flask server running in a background thread for viewing notes in browser
- `note_renderer.py` — markdown-to-HTML rendering via markdown2
- `socket_listener.py` — WebSocket listener for remote triggers
- `kanban.html` — Kanban board template

**External integrations:**
- `mod_browser.py` — Selenium-based Tisoware web scraping
- `mod_timetrack.py` — time tracking deviation comparison
- `mod_buchen.py` — time sheet booking
- `mod_tt_bridge.py` — bridge to Tisoware time tracking system

**Utilities (`util/`):**
- `ts.py` — timestamp parsing/formatting helpers
- `merge_notes.py` — script to merge note databases

## Key Conventions

- Task IDs are timestamp-based (`generate_task_id()`) with 5-char MD5 short IDs (`generate_short_task_id()`)
- Configuration loads from `settings.json` via `config.py`
- Data files (`tasks.json`, `tw_data.json`) are in the project root
- The app uses threading for Flask server and socket listener alongside the Tkinter main loop
