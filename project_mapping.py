"""Task name -> project code mapping for mod_buchungskorrektur.

The mapping lives in project_mapping.json next to this file, keyed by project
code, each holding the ttplus task names booked to it:

    {"9300_2026": ["Meetings", ...], "Allg. Aufgaben 2026": [...], ...}

A tasks.json database records no project, so every task name needs an entry
here. New names are added with assign_task() once the user picks a project.
"""

import json
from pathlib import Path

PROJECT_MAPPING_PATH = Path(__file__).with_name("project_mapping.json")


def load_project_mapping(path: Path = PROJECT_MAPPING_PATH) -> dict[str, list[str]]:
    """Read project code -> list of task names. A missing file means empty."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_project_mapping(mapping: dict[str, list[str]],
                         path: Path = PROJECT_MAPPING_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
        f.write("\n")


def invert_mapping(mapping: dict[str, list[str]]) -> dict[str, str]:
    """Task name -> project code, the lookup parse_json_file() uses."""
    return {task: project
            for project, tasks in mapping.items()
            for task in tasks}


# Loaded once at import. TASK_PROJECT_MAP is updated in place by assign_task(),
# so importers holding a reference see new assignments straight away.
PROJECT_TASKS = load_project_mapping()
TASK_PROJECT_MAP = invert_mapping(PROJECT_TASKS)


def assign_task(task: str, project: str):
    """Map a task name to a project and write the file back.

    A task already mapped to another project is moved, not duplicated, so the
    inverted lookup and the file stay consistent.
    """
    for tasks in PROJECT_TASKS.values():
        if task in tasks:
            tasks.remove(task)
    PROJECT_TASKS.setdefault(project, []).append(task)
    TASK_PROJECT_MAP[task] = project
    save_project_mapping(PROJECT_TASKS)
