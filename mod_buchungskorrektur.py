"""Automate Buchungskorrektur posting to Tisoware via REST API.

Reads work entries either from a markdown log (project code written between
colons on each line) or straight from a ttplus tasks.json database, maps
project codes to activities, and posts them to Tisoware's Buchungskorrektur
workflow.
"""

import json
import re
import sys
import importlib.util
from datetime import datetime, date
from getpass import getpass
from pathlib import Path
from typing import NamedTuple, Optional
from configparser import ConfigParser

RED = "\033[31m"
BOLD = "\033[1m"
OFF = "\033[0m"

# Tisoware's AJAX save reply, per toSaveIn() in wf.workflow.js: an empty body
# or "OK!" means saved; otherwise the body splits on "!#!" and the part after
# the separator decides -- a page name (e.g. "wf_my") means saved, an empty
# part means the server raised a warning and wrote nothing until the request
# is repeated with wrnnflg=true. No separator at all is a hard error.
SEPARATOR = "!#!"

def load_http_client():
    """Load tisobridge.http_client without triggering main.py import."""
    http_client_path = Path.home() / 'tisobridge' / 'tisobridge' / 'http_client.py'
    spec = importlib.util.spec_from_file_location("_http_client_module", http_client_path)
    http_client = importlib.util.module_from_spec(spec)
    sys.modules['_http_client_module'] = http_client
    spec.loader.exec_module(http_client)
    return http_client

PROD_URL = "http://menlogphost5.menlosystems.local/tisoware/twwebclient"

# tisobridge is only needed to talk to the server. Keep the import failure
# recoverable so the parsing and overlap logic stays importable (and
# testable) on a machine without it.
try:
    http_client = load_http_client()
    TisoClient = http_client.TisoClient
    Booking = http_client.Booking
    PROD_URL = http_client.PROD_URL
    TISOBRIDGE_ERROR = None
except Exception as e:
    http_client = None
    TisoClient = None
    Booking = None
    TISOBRIDGE_ERROR = e

ALLG_PATTERN = r"[Aa]llg"
ENTWICKLUNG_PATTERN = r"[Ee]ntw"

# "Bemerkung zum Antrag" on the Buchungskorrektur form.
ANTRAG_INFO = "Nachbuchung"

HEADER_WIDTH = 70


class LogEntry(NamedTuple):
    date: date
    from_time: str
    to_time: str
    project: str
    comment: str
    # Originating ttplus task name. Only set when the entries came from a
    # tasks.json database; the markdown log folds it into the comment.
    # project is None when the task name has no PROJECT mapping yet.
    task: str = ""


PROJECT_ACTIVITY_MAP = {
    "9300_2026": "65.10",
    "Allg. Aufgaben 2026": "10.10",
    "9567_AQURA": "54.10",
}

# ttplus task name -> project code. A tasks.json database records no project,
# so the mapping is recovered from how the same task names were booked in the
# July 2026 log. A name that is missing here stops the run rather than being
# guessed at, so nothing lands on the wrong project.
TASK_PROJECT_MAP = {
    "#19078: ESD conformant box": "9300_2026",
    "#19118 MWUBC Bias Controller Firmware": "9567_AQURA",
    "#19183 canopen-bootloader": "9567_AQURA",
    "Bringin up new PC": "9300_2026",
    "Issue #19397": "9300_2026",
    "Meetings": "Allg. Aufgaben 2026",
    "Refactor MiGA 3.0rc": "9300_2026",
    "Timekeeping": "Allg. Aufgaben 2026",
    "coffee tool": "9300_2026",
}

# Placeholder rows entered on Thursday so the reported work percentage came
# out right. The Friday work itself is logged under the real projects, so
# booking these would double-count it.
IGNORED_TASKS = {
    "Friday task pleaceholder / Planner",
}

# Tisoware's Kommentar field is short, so only a prefix of the task name goes
# in front of the description as context.
TASK_NAME_PREFIX = 13
COMMENT_SEPARATOR = "/"

# Tisoware refuses a day totalling more than this.
MAX_DAY_MINUTES = 10 * 60

# Not a Tisoware rule, only worth pointing out in the summary.
FULL_DAY_MINUTES = 8 * 60


def parse_log_file(path: Path) -> list[LogEntry]:
    """Parse markdown log in format: 07 DD.MM HH:MM - DD.MM HH:MM :Project: Comment"""
    entries = []
    pattern = re.compile(
        r'(\d+)\s+'
        r'(\d+)\.(\d+)\s+(\d+):(\d+)\s+-\s+'
        r'(\d+)\.(\d+)\s+(\d+):(\d+)\s+'
        r':([^:]+):\s*(.+)'
    )

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = pattern.match(line)
            if not m:
                continue

            month, start_d, start_m, start_h, start_min, \
            end_d, end_m, end_h, end_min, project, comment = m.groups()

            year = 2026
            month = int(month)
            start_date = date(year, month, int(start_d))

            entries.append(LogEntry(
                date=start_date,
                from_time=f"{start_h}:{start_min}",
                to_time=f"{end_h}:{end_min}",
                project=project.strip(),
                comment=comment.strip(),
            ))

    return entries


def build_comment(task: str, done: str) -> str:
    """Kommentar text: a short task-name prefix, then what was done."""
    return f"{task[:TASK_NAME_PREFIX].rstrip()}{COMMENT_SEPARATOR}{done}"


def parse_json_file(path: Path) -> list[LogEntry]:
    """Parse a ttplus tasks.json database into log entries.

    work_tasks maps a short task id to metadata carrying the task name (tnm);
    task_details maps the same id to the timed rows, whose "Start Time" and
    "End Time" are YYYYMMDDHHMMSS. A task name with no TASK_PROJECT_MAP entry
    yields project=None for the caller to report -- see find_unmapped().

    Every row is returned as recorded, including IGNORED_TASKS rows and any
    that end before they start, so that dropping them stays visible to the
    caller (see drop_ignored() and find_inverted()).
    """
    with open(path) as f:
        db = json.load(f)

    tasks = db.get("work_tasks", {})
    details = db.get("task_details", {})

    entries = []
    for sti, rows in details.items():
        task = tasks.get(sti, {}).get("tnm", "")
        for row in rows:
            start = row.get("Start Time", "")
            end = row.get("End Time", "")
            if len(start) < 12 or len(end) < 12:
                continue
            entries.append(LogEntry(
                date=date(int(start[0:4]), int(start[4:6]), int(start[6:8])),
                from_time=f"{start[8:10]}:{start[10:12]}",
                to_time=f"{end[8:10]}:{end[10:12]}",
                project=TASK_PROJECT_MAP.get(task),
                comment=build_comment(task, row.get("What was done", "")),
                task=task,
            ))

    return entries


def load_entries(path: Path) -> list[LogEntry]:
    """Read either a tasks.json database or a markdown log, by suffix.

    Returns every row; call drop_ignored() to apply IGNORED_TASKS.
    """
    if path.suffix.lower() == ".json":
        return parse_json_file(path)
    return parse_log_file(path)


def drop_ignored(entries: list[LogEntry]) -> list[LogEntry]:
    """Remove rows whose task is in IGNORED_TASKS. Markdown entries carry no
    task name and so are never affected."""
    return [e for e in entries if e.task not in IGNORED_TASKS]


def find_unmapped(entries: list[LogEntry]) -> dict[str, int]:
    """Task names with no project mapping, and how many entries each covers."""
    counts = {}
    for e in entries:
        if e.project is None:
            counts[e.task] = counts.get(e.task, 0) + 1
    return counts


def group_by_date(entries: list[LogEntry]) -> dict[date, list[LogEntry]]:
    """Group entries by date."""
    grouped = {}
    for entry in entries:
        if entry.date not in grouped:
            grouped[entry.date] = []
        grouped[entry.date].append(entry)
    return grouped


def classify_save_response(body: str) -> tuple[str, str]:
    """Map a save reply onto ("saved" | "warning" | "error", message).

    Mirrors toSaveIn() in wf.workflow.js; see SEPARATOR above.
    """
    body = body.strip()
    if body == "" or body == "OK!":
        return "saved", body
    if SEPARATOR not in body:
        return "error", body
    message, _, tail = body.partition(SEPARATOR)
    if tail.strip() in ("", "1"):
        return "warning", message.strip()
    return "saved", message.strip()


def save_bookings(client: TisoClient, bookings: list, info: str,
                  force: bool = False):
    """Post the save AJAX. force=True replays the JS toSaveIn(1) path, i.e.
    "Dennoch speichern?" answered with yes.

    Reimplemented here rather than calling client.save_bookings() because
    that one hardcodes wrnnflg=false and so can never clear a warning.
    """
    if client.page is None:
        raise RuntimeError("no page state; call open_buchung_edit() first")
    if client.page.fields.get("fld") != "wf_newdata":
        raise RuntimeError(
            f"expected fld=wf_newdata (booking-edit form), got"
            f" {client.page.fields.get('fld')!r}"
        )
    default_cc = ""
    m = re.search(r"CC=([^!]+)", client.page.fields.get("Default", ""))
    if m:
        default_cc = m.group(1)

    overrides = {
        "ajax": "ajax",
        "sbm": "save",
        "wrnnflg": "true" if force else "false",
        "confirmedChange": "false",
        "actFeld": "Comment",
        "inf": info,
        "cntbchngntmgdvr": str(len(bookings)),
        "aRwtbldocu": "0",
    }
    for i, b in enumerate(bookings):
        overrides[f"tbl{i}"] = json.dumps(b.to_row(i, default_cc))
    return client._submit_form_ajax(overrides)


class Aborted(Exception):
    """Ctrl-C or Ctrl-D at a prompt. Unwinds to main() for a clean exit."""


def ask(prompt: str) -> str:
    """input() that turns Ctrl-C / Ctrl-D into Aborted instead of a traceback."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Aborted() from None


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_minutes(entries: list[LogEntry]) -> int:
    return sum(to_minutes(e.to_time) - to_minutes(e.from_time)
               for e in entries)


def format_day_header(date_str: str, count: int, minutes: int) -> str:
    """Day banner with the total right-aligned to the rule below it."""
    left = f"Date: {date_str} ({count} entries)"
    right = f"TOTAL: {to_hhmm(minutes)}"
    pad = max(1, HEADER_WIDTH - len(left) - len(right))
    return f"{left}{' ' * pad}{right}"


def find_inverted(entries: list[LogEntry]) -> list[int]:
    """Indices of entries whose end time is before their start time. A stop
    recorded against the wrong row leaves these in the database; they would
    make the day total too small and confuse the overlap arithmetic."""
    return [i for i, e in enumerate(entries)
            if to_minutes(e.to_time) < to_minutes(e.from_time)]


def swap_inverted(entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
    """Read every backwards entry the other way round, which is what a
    swapped pair of timestamps means."""
    out = list(entries)
    notes = []
    for i in find_inverted(out):
        notes.append(f"[{i}] {out[i].from_time}-{out[i].to_time} ->"
                     f" {out[i].to_time}-{out[i].from_time}")
        out[i] = out[i]._replace(from_time=out[i].to_time,
                                 to_time=out[i].from_time)
    return sorted(out, key=lambda e: to_minutes(e.from_time)), notes


def resolve_inverted(entries: list[LogEntry]) -> Optional[list[LogEntry]]:
    """Interactively clear backwards entries. Returns the adjusted entries, or
    None to skip the day."""
    while True:
        inverted = find_inverted(entries)
        if not inverted:
            return sorted(entries, key=lambda e: to_minutes(e.from_time))

        flagged = set(inverted)
        print(f"\n{BOLD}{len(inverted)} entry(s) end before they start:{OFF}")
        for i in inverted:
            span = (to_minutes(entries[i].to_time)
                    - to_minutes(entries[i].from_time))
            print(f"  {RED}[{i}] {entries[i].from_time}-{entries[i].to_time}"
                  f" ({span} min){OFF}")
        print()
        print_day_entries(entries, flagged)

        print("\n  1 = swap the times (read them the other way round)")
        print("  d = drop an entry")
        print("  k = skip this day")
        choice = ask("Choose [1/d/k]: ").lower()

        if choice == "k":
            return None

        if choice == "1":
            entries, notes = swap_inverted(entries)
            for note in notes:
                print(f"  {note}")
            continue

        if choice == "d":
            entries = drop_entry(entries)
            continue

        print("  please answer 1, d or k")


def trim_from_end(entries: list[LogEntry],
                  limit: int = MAX_DAY_MINUTES) -> tuple[list[LogEntry], list[str]]:
    """Cut the day back to the limit, taking the minutes off the latest
    entries first.

    Shortening only the last entry is not enough -- on 19.08 the day was 60
    min over but its last entry only ran 45 min -- so the cut walks backwards,
    consuming one entry at a time. An entry that is used up entirely is
    dropped rather than left as a zero-length booking.
    """
    out = sorted(entries, key=lambda e: to_minutes(e.from_time))
    excess = day_minutes(out) - limit
    if excess <= 0:
        return out, []

    notes = []
    keep = list(out)
    for i in range(len(keep) - 1, -1, -1):
        if excess <= 0:
            break
        span = to_minutes(keep[i].to_time) - to_minutes(keep[i].from_time)
        if span <= 0:
            continue
        cut = min(span, excess)
        if cut == span:
            notes.append(f"[{i}] {keep[i].from_time}-{keep[i].to_time}"
                         f" dropped (-{cut} min)")
            keep[i] = None
        else:
            new_end = to_hhmm(to_minutes(keep[i].to_time) - cut)
            notes.append(f"[{i}] end {keep[i].to_time} ->"
                         f" {new_end} (-{cut} min)")
            keep[i] = keep[i]._replace(to_time=new_end)
        excess -= cut

    return [e for e in keep if e is not None], notes


def resolve_over_limit(entries: list[LogEntry],
                       limit: int = MAX_DAY_MINUTES) -> Optional[list[LogEntry]]:
    """Interactively bring a day under the Tisoware limit. Returns the
    adjusted entries, or None to skip the day."""
    while True:
        total = day_minutes(entries)
        if total <= limit:
            return entries

        print(f"\n{BOLD}Day totals {to_hhmm(total)}, over the"
              f" {to_hhmm(limit)} limit -- Tisoware will refuse it:{OFF}")
        print()
        print_day_entries(entries, set())

        print(f"\n  1 = trim {total - limit} min off the end of the day"
              f" (down to {to_hhmm(limit)})")
        print("  d = drop an entry")
        print("  k = skip this day")
        choice = ask("Choose [1/d/k]: ").lower()

        if choice == "k":
            return None

        if choice == "1":
            entries, notes = trim_from_end(entries, limit)
            for note in notes:
                print(f"  {note}")
            continue

        if choice == "d":
            entries = drop_entry(entries)
            continue

        print("  please answer 1, d or k")


def drop_entry(entries: list[LogEntry]) -> list[LogEntry]:
    """Prompt for an index and remove it. Returns entries unchanged if the
    answer is not a valid index."""
    raw = ask("  index to drop: ")
    if not raw.isdigit() or int(raw) >= len(entries):
        print("  no such index")
        return entries
    dropped = entries[int(raw)]
    print(f"  dropping {dropped.from_time}-{dropped.to_time}"
          f" {dropped.comment}")
    return entries[:int(raw)] + entries[int(raw) + 1:]


def day_flags(entries: list[LogEntry]) -> list[str]:
    """Repairs a day needs before it can be posted. Hour deviations are not
    listed here -- they are reported as a signed figure by day_delta()."""
    rows = sorted(entries, key=lambda e: to_minutes(e.from_time))
    flags = []
    if find_inverted(rows):
        flags.append("backwards")
    if find_overlaps(rows):
        flags.append("overlap")
    if not flags:
        flags.append("clean")
    return flags


def day_delta(minutes: int) -> tuple[str, bool]:
    """Signed deviation from a full day, and whether it is out of the
    workable band: short of 8 h, or past the 10 h Tisoware refuses."""
    diff = minutes - FULL_DAY_MINUTES
    sign = "-" if diff < 0 else "+"
    text = f"{sign}{to_hhmm(abs(diff))}"
    bad = minutes < FULL_DAY_MINUTES or minutes > MAX_DAY_MINUTES
    return text, bad


def print_summary(grouped: dict[date, list[LogEntry]],
                  dates: list[date],
                  skipped: list[date] = (),
                  emptied: list[date] = ()):
    """One line per day: weekday, date, total, entry count, what it needs."""
    notes = {d: "skipped" for d in skipped}
    notes.update({d: "ignored" for d in emptied})

    def row(label: str, total: str, count: str,
            delta: str, needs: str,
            delta_bad: bool = False, needs_bad: bool = False) -> str:
        """Cells are padded before any colour is applied -- an escape
        sequence counted as width would break the right edge."""
        delta_cell = f"{delta:>8}"
        needs_width = max(len(needs), HEADER_WIDTH - 36)
        needs_cell = f"{needs:<{needs_width}}"
        if delta_bad:
            delta_cell = f"{RED}{delta_cell}{OFF}"
        if needs_bad:
            needs_cell = f"{RED}{needs_cell}{OFF}"
        return (f"{label:10} {total:>6} {count:>7} {delta_cell}"
                f"  {needs_cell}")

    print()
    print(row("Day", "Total", "Entries", "vs 8h", "Needs"))
    print("-" * HEADER_WIDTH)

    for d in sorted(set(dates) | set(notes)):
        label = f"{d.strftime('%a')} {d.strftime('%d.%m')}"
        if d in notes:
            print(row(label, "-", "-", "-", notes[d], needs_bad=True))
            continue
        rows = grouped[d]
        minutes = day_minutes(rows)
        delta, bad = day_delta(minutes)
        flags = day_flags(rows)
        print(row(label, to_hhmm(minutes), str(len(rows)), delta,
                  ", ".join(flags), delta_bad=bad,
                  needs_bad=flags[0] != "clean"))

    print("-" * HEADER_WIDTH)
    total = sum(day_minutes(grouped[d]) for d in dates)
    print(f"{len(dates)} day(s) to post, {to_hhmm(total)} total")

    # Over the limit is the one deviation the server acts on, so name those
    # days rather than leaving them as a red figure in the table.
    over = [d for d in dates if day_minutes(grouped[d]) > MAX_DAY_MINUTES]
    if over:
        print(f"{RED}Over {to_hhmm(MAX_DAY_MINUTES)} and will be refused: "
              + ", ".join(d.strftime("%d.%m") for d in over) + OFF)


def find_overlaps(entries: list[LogEntry]) -> list[tuple[int, int]]:
    """Index pairs (i, j) in a start-sorted list where entry i runs past the
    start of entry j. Tisoware rejects these with "Die Buchung bis X
    ueberlappt die Buchung ab Y"."""
    pairs = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if to_minutes(entries[j].from_time) < to_minutes(entries[i].to_time):
                pairs.append((i, j))
    return pairs


def print_day_entries(entries: list[LogEntry], flagged: set[int]):
    for idx, e in enumerate(entries):
        span = to_minutes(e.to_time) - to_minutes(e.from_time)
        line = (f"  [{idx}] {e.from_time}-{e.to_time} ({span / 60:.2f}h) "
                f"{e.project:20} {e.comment}")
        print(f"{RED}{line}{OFF}" if idx in flagged else line)


def find_contained(entries: list[LogEntry]) -> list[tuple[int, int]]:
    """Index pairs (outer, inner) where the inner entry lies entirely inside
    the outer one -- typically a meeting logged while a longer task was still
    running.

    Neither align direction fits this case: shortening the outer entry throws
    away the time *after* the inner one, and pushing the inner entry out to
    the outer end would collapse it. Splitting the outer entry around the
    inner one is the repair that keeps the real time. See split_around().
    """
    pairs = []
    for i, outer in enumerate(entries):
        outer_span = to_minutes(outer.to_time) - to_minutes(outer.from_time)
        for j, inner in enumerate(entries):
            if i == j:
                continue
            inner_span = to_minutes(inner.to_time) - to_minutes(inner.from_time)
            if (to_minutes(outer.from_time) <= to_minutes(inner.from_time)
                    and to_minutes(inner.to_time) <= to_minutes(outer.to_time)
                    and outer_span > inner_span):
                pairs.append((i, j))
    return pairs


def split_around(entries: list[LogEntry], outer: int,
                 inner: int) -> tuple[list[LogEntry], list[str]]:
    """Cut the enclosing entry in two so the inner entry sits between the
    halves, keeping all of the enclosing entry's time except the minutes the
    inner one occupies. A half of zero length is dropped rather than kept."""
    o, n = entries[outer], entries[inner]
    # Guard the precondition. Splitting around an entry that is not inside
    # the outer one silently *extends* the outer entry to reach it, which
    # would book time that was never worked.
    if not (to_minutes(o.from_time) <= to_minutes(n.from_time)
            and to_minutes(n.to_time) <= to_minutes(o.to_time)):
        return entries, [f"cannot split [{outer}] {o.from_time}-{o.to_time}:"
                         f" [{inner}] {n.from_time}-{n.to_time} is not"
                         f" inside it"]

    halves = [o._replace(to_time=n.from_time), o._replace(from_time=n.to_time)]
    kept = [h for h in halves
            if to_minutes(h.to_time) > to_minutes(h.from_time)]

    notes = [f"[{outer}] {o.from_time}-{o.to_time} split around"
             f" [{inner}] {n.from_time}-{n.to_time} -> "
             + " + ".join(f"{h.from_time}-{h.to_time}" for h in kept)]
    if len(kept) < len(halves):
        notes.append(f"  one half was empty, {len(kept)} kept")

    rest = [e for k, e in enumerate(entries) if k != outer]
    return sorted(rest + kept, key=lambda e: to_minutes(e.from_time)), notes


DAY_END_MINUTES = 24 * 60


def move_after(entries: list[LogEntry], moving: int,
               anchor: int) -> tuple[list[LogEntry], list[str]]:
    """Relocate an entry whole, keeping its duration, so it starts when the
    anchor entry ends.

    align_later_start() moves only the start and leaves the end where it was,
    which shortens the record and refuses outright when that would collapse
    it. Moving keeps the length, so the day total is unchanged and the entry
    can never come out backwards -- the minutes are relocated, not lost.
    """
    e, a = entries[moving], entries[anchor]
    span = to_minutes(e.to_time) - to_minutes(e.from_time)
    new_start = to_minutes(a.to_time)
    new_end = new_start + span

    if new_end > DAY_END_MINUTES:
        return entries, [f"cannot move [{moving}]: {to_hhmm(new_start)}"
                         f" + {span} min runs past midnight"]

    moved = e._replace(from_time=to_hhmm(new_start), to_time=to_hhmm(new_end))
    rest = [x for k, x in enumerate(entries) if k != moving]
    notes = [f"[{moving}] {e.from_time}-{e.to_time} ->"
             f" {moved.from_time}-{moved.to_time}"
             f" (after [{anchor}] ending {a.to_time}, {span} min kept)"]
    return sorted(rest + [moved], key=lambda x: to_minutes(x.from_time)), notes


def move_entry(entries: list[LogEntry]) -> list[LogEntry]:
    """Prompt for an entry and what to put it behind, then relocate it whole.
    Returns entries unchanged if either answer is not a valid index."""
    raw = ask("  index to move: ")
    if not raw.isdigit() or int(raw) >= len(entries):
        print("  no such index")
        return entries
    moving = int(raw)

    raw = ask("  place it after index: ")
    if not raw.isdigit() or int(raw) >= len(entries):
        print("  no such index")
        return entries
    anchor = int(raw)

    if anchor == moving:
        print("  cannot place an entry after itself")
        return entries

    out, notes = move_after(entries, moving, anchor)
    for note in notes:
        print(f"  {note}")
    return out


def align_earlier_end(entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
    """Pull the earlier booking's end back to the later one's start, so the
    earlier entry gives up the overlapping minutes."""
    out = list(entries)
    notes = []
    for i, j in find_overlaps(out):
        new_end = out[j].from_time
        if to_minutes(new_end) <= to_minutes(out[i].from_time):
            notes.append(f"cannot shorten [{i}]: {out[i].from_time}-"
                         f"{out[i].to_time} would collapse, drop one instead")
            continue
        notes.append(f"[{i}] end {out[i].to_time} -> {new_end}")
        out[i] = out[i]._replace(to_time=new_end)
    return sorted(out, key=lambda e: to_minutes(e.from_time)), notes


def align_later_start(entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
    """Push the later booking's start forward to the earlier one's end, so the
    later entry gives up the overlapping minutes."""
    out = list(entries)
    notes = []
    for i, j in find_overlaps(out):
        new_start = out[i].to_time
        if to_minutes(new_start) >= to_minutes(out[j].to_time):
            notes.append(f"cannot shift [{j}]: {out[j].from_time}-"
                         f"{out[j].to_time} would collapse, drop one instead")
            continue
        notes.append(f"[{j}] start {out[j].from_time} -> {new_start}")
        out[j] = out[j]._replace(from_time=new_start)
    return sorted(out, key=lambda e: to_minutes(e.from_time)), notes


def resolve_overlaps(entries: list[LogEntry]) -> Optional[list[LogEntry]]:
    """Interactively clear overlaps. Returns the adjusted entries, or None to
    skip the day."""
    while True:
        overlaps = find_overlaps(entries)
        if not overlaps:
            return entries

        contained = find_contained(entries)
        flagged = {i for pair in overlaps for i in pair}
        print(f"\n{BOLD}{len(overlaps)} overlap(s) -- Tisoware will refuse"
              f" these:{OFF}")
        for i, j in overlaps:
            if (i, j) in contained:
                print(f"  {RED}[{i}] {entries[i].from_time}-"
                      f"{entries[i].to_time} encloses [{j}]"
                      f" {entries[j].from_time}-{entries[j].to_time}{OFF}")
                continue
            cut = to_minutes(entries[i].to_time) - to_minutes(entries[j].from_time)
            print(f"  {RED}[{i}] ends {entries[i].to_time} but [{j}] starts"
                  f" {entries[j].from_time} ({cut} min){OFF}")
        print()
        print_day_entries(entries, flagged)

        i, j = overlaps[0]
        splittable = (i, j) in contained
        print(f"\n  1 = align down: end of the earlier entry"
              f" -> {entries[j].from_time} (shortens it)")
        collapses = (to_minutes(entries[i].to_time)
                     >= to_minutes(entries[j].to_time))
        print(f"  2 = align up:   start of the later entry"
              f" -> {entries[i].to_time}"
              f" ({'would collapse it' if collapses else 'shortens it'})")
        if splittable:
            halves, _ = split_around(entries, i, j)
            kept = [h for h in halves if h.comment == entries[i].comment]
            print(f"  s = split [{i}] around [{j}] -> "
                  + " + ".join(f"{h.from_time}-{h.to_time}" for h in kept))
        print("  m = move an entry whole, behind another (keeps its length)")
        print("  d = drop an entry")
        print("  k = skip this day")
        keys = "1/2/s/m/d/k" if splittable else "1/2/m/d/k"
        choice = ask(f"Choose [{keys}]: ").lower()

        if choice == "k":
            return None

        if choice == "m":
            entries = move_entry(entries)
            continue

        if choice in ("1", "2"):
            entries, notes = (align_earlier_end(entries) if choice == "1"
                              else align_later_start(entries))
            for note in notes:
                print(f"  {note}")
            continue

        if choice == "s" and splittable:
            entries, notes = split_around(entries, i, j)
            for note in notes:
                print(f"  {note}")
            continue

        if choice == "d":
            entries = drop_entry(entries)
            continue

        print(f"  please answer {keys.replace('/', ', ')}")


def get_activity_pattern(project: str) -> str:
    """Get activity search pattern for a project."""
    if project in PROJECT_ACTIVITY_MAP:
        return PROJECT_ACTIVITY_MAP[project]
    return ALLG_PATTERN


def post_bookings_for_date(
    client: TisoClient,
    trans_name: str,
    date_obj: date,
    entries: list[LogEntry],
    dry_run: bool = False,
    info: str = ANTRAG_INFO,
) -> bool:
    """Post all bookings for a single date. Returns True if successful."""
    date_str = date_obj.strftime("%d.%m.%Y")
    entries = sorted(entries, key=lambda e: to_minutes(e.from_time))
    logged_minutes = day_minutes(entries)

    print(f"\n{'=' * HEADER_WIDTH}")
    print(format_day_header(date_str, len(entries), logged_minutes))
    print('=' * HEADER_WIDTH)

    # Backwards entries first: they distort the day total and would make the
    # overlap comparison meaningless.
    entries = resolve_inverted(entries)
    if entries is None:
        print("Day skipped")
        return False

    entries = resolve_overlaps(entries)
    if entries is None:
        print("Day skipped")
        return False

    entries = resolve_over_limit(entries)
    if entries is None:
        print("Day skipped")
        return False

    # A saved Antrag ends the workflow and leaves the session on wf_my (the
    # "Wollen Sie einen weiteren Antrag anlegen?" state). Re-enter the
    # Buchungskorrektur transaction first, which is what clicking "Ja" does,
    # otherwise open_buchung_edit posts a spent form and save refuses.
    try:
        client.navigate(trans_name)
        client.open_buchung_edit(date_str)
    except Exception as e:
        print(f"Error opening date {date_str}: {e}")
        return False

    resolved = []
    for entry in entries:
        try:
            activity_pattern = get_activity_pattern(entry.project)
            aid, alabel = client.resolve_activity(
                entry.project,
                activity_pattern,
                ALLG_PATTERN,
                ENTWICKLUNG_PATTERN,
            )
            resolved.append((entry, aid, alabel))
            print(f"  {entry.from_time}-{entry.to_time} "
                  f"{entry.project!r:20} {aid:>4} {alabel!r:30} {entry.comment!r}")
        except Exception as e:
            print(f"  ERROR resolving {entry.project}: {e}")
            return False

    if not resolved:
        print("No entries to post")
        return False

    final_minutes = day_minutes(entries)
    if final_minutes != logged_minutes:
        print(f"  {'TOTAL: ' + to_hhmm(final_minutes):>{HEADER_WIDTH - 2}}"
              f"  (was {to_hhmm(logged_minutes)} as logged)")

    bookings = [
        Booking(
            from_time=e.from_time,
            to_time=e.to_time,
            project=e.project,
            activity=aid,
            comment=e.comment,
        )
        for e, aid, _ in resolved
    ]

    if dry_run:
        print(f"\n--dry-run: not saving {len(bookings)} booking(s)")
        return True

    confirm = ask(f"\nSave {len(bookings)} booking(s)? [y/N] ").lower()
    if confirm not in ("y", "yes", "j", "ja"):
        print("Skipped")
        return False

    try:
        resp = save_bookings(client, bookings, info)
        status, message = classify_save_response(resp.text)
        print(f"\nServer replied ({resp.status_code}): {resp.text.strip()[:200]!r}")

        if status == "warning":
            # Nothing was written yet; the server wants the toSaveIn(1) reply.
            print(f"\n{BOLD}Server warning -- NOT saved yet:{OFF}")
            print(f"  {message}")
            again = ask("Save anyway? [y/N] ").lower()
            if again not in ("y", "yes", "j", "ja"):
                print("NOT SAVED")
                return False
            resp = save_bookings(client, bookings, info, force=True)
            status, message = classify_save_response(resp.text)
            print(f"Server replied ({resp.status_code}):"
                  f" {resp.text.strip()[:200]!r}")

        if status == "saved":
            print("SAVED")
            return True

        print(f"FAILED: {message}")
        return False
    except Exception as e:
        print(f"Save error: {e}")
        return False


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """Load Tisoware credentials from ~/.tisobridge.conf or user input."""
    config = ConfigParser()
    config.read(Path.home() / ".tisobridge.conf")

    user = None
    password = None

    if config.has_section("default"):
        section = config["default"]
        user = section.get("user")
        password = section.get("password")

    if not user:
        user = ask("Tisoware username: ")
    if not password:
        try:
            password = getpass("Tisoware password: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Aborted() from None

    return user, password


def main(
    log_path: Path,
    start_date: Optional[date] = None,
    dry_run: bool = False,
    url: str = PROD_URL,
    end_date: Optional[date] = None,
    skip_dates: frozenset = frozenset(),
    summary: bool = False,
):
    """Parse log or tasks.json and post Buchungskorrektur entries."""
    print(f"Reading entries from {log_path}...")
    raw = load_entries(log_path)
    entries = drop_ignored(raw)

    if not entries:
        print("No entries found")
        return

    if len(entries) != len(raw):
        names = ", ".join(sorted({e.task for e in raw
                                  if e.task in IGNORED_TASKS}))
        print(f"Ignoring {len(raw) - len(entries)} entries from: {names}")

    grouped = group_by_date(entries)
    # Dates that had rows but lost every one of them to IGNORED_TASKS. They
    # are gone from grouped, so carry them separately to report below.
    emptied = sorted(set(group_by_date(raw)) - set(grouped))

    if start_date is None:
        start_date = min(grouped.keys())

    dates_to_post = sorted(d for d in grouped
                           if d >= start_date
                           and (end_date is None or d <= end_date)
                           and d not in skip_dates)

    bound = f" to {end_date}" if end_date else ""
    print(f"Found {len(entries)} entries across {len(grouped)} dates")
    print(f"Will post {len(dates_to_post)} date(s) from {start_date}{bound}")

    # Every requested skip in range, whether or not it holds entries -- a
    # sick day with nothing logged still belongs in the report.
    skipped = sorted(d for d in skip_dates
                     if d >= start_date
                     and (end_date is None or d <= end_date))
    if skipped and not summary:
        print("Skipping by request: "
              + ", ".join(d.strftime("%d.%m") for d in skipped))

    # Only the entries actually in scope need a project; complain before
    # anything is sent rather than booking them somewhere plausible.
    in_scope = [e for d in dates_to_post for e in grouped[d]]
    unmapped = find_unmapped(in_scope)
    if unmapped:
        print(f"\n{RED}No project mapping for:{OFF}")
        for name, count in sorted(unmapped.items()):
            print(f"  {name!r} ({count} entries)")
        print("\nAdd them to TASK_PROJECT_MAP (or IGNORED_TASKS) and re-run.")
        return

    in_range = [d for d in emptied
                if d >= start_date
                and (end_date is None or d <= end_date)
                and d not in skip_dates]
    if in_range and not summary:
        print(f"{RED}Nothing left to post on: "
              + ", ".join(d.strftime("%d.%m") for d in in_range)
              + " -- every entry was ignored" + OFF)

    if summary:
        print_summary(grouped, dates_to_post, skipped, in_range)
        return

    if dry_run:
        print("\n[DRY-RUN] Showing entries without posting...")
        client = None
    else:
        if TisoClient is None:
            print(f"Error: cannot load tisobridge ({TISOBRIDGE_ERROR}).")
            print("Posting needs ~/tisobridge plus 'requests' and"
                  " 'beautifulsoup4'; --dry-run works without it.")
            return
        user, password = load_credentials()
        print(f"\nLogging in as {user!r} against {url}...")
        client = TisoClient(base_url=url)
        try:
            client.login(user, password)
            # Resolve the menu entry once, from the welcome page that carries
            # menujson; later pages are re-entered via navigate(trans_name).
            trans_name = client.page.trans_name_for("Buchungskorrektur")
            if trans_name is None:
                print("Error: 'Buchungskorrektur' not found in the menu")
                return
        except Exception as e:
            print(f"Login error: {e}")
            return

    success_count = 0
    overlap_days = []
    inverted_days = []
    over_limit_days = []
    saved_days = []
    aborted_on = None
    for position, d in enumerate(dates_to_post):
        if dry_run:
            rows = sorted(grouped[d], key=lambda e: to_minutes(e.from_time))
            overlaps = find_overlaps(rows)
            inverted = find_inverted(rows)
            flagged = {i for pair in overlaps for i in pair} | set(inverted)
            if overlaps:
                overlap_days.append(d)
            if inverted:
                inverted_days.append(d)
            total = day_minutes(rows)
            if total > MAX_DAY_MINUTES:
                over_limit_days.append(d)

            print(f"\n{'=' * HEADER_WIDTH}")
            print(format_day_header(d.strftime('%d.%m.%Y'), len(rows),
                                    day_minutes(rows)))
            print('=' * HEADER_WIDTH)

            for idx, entry in enumerate(rows):
                activity_pattern = get_activity_pattern(entry.project)
                duration = (to_minutes(entry.to_time)
                            - to_minutes(entry.from_time)) / 60

                line = (f"  {entry.from_time}-{entry.to_time} ({duration:.2f}h) "
                        f"{entry.project!r:20} [activity: {activity_pattern!r}]")
                print(f"{RED}{line}{OFF}" if idx in flagged else line)
                print(f"    Comment: {entry.comment!r}")

            for i in inverted:
                print(f"  {RED}BACKWARDS: [{i}] {rows[i].from_time}-"
                      f"{rows[i].to_time} ends before it starts{OFF}")
            for i, j in overlaps:
                print(f"  {RED}OVERLAP: ends {rows[i].to_time} but next starts"
                      f" {rows[j].from_time} -- Tisoware will refuse this{OFF}")
            if total > MAX_DAY_MINUTES:
                print(f"  {RED}OVER LIMIT: {to_hhmm(total)} exceeds"
                      f" {to_hhmm(MAX_DAY_MINUTES)}"
                      f" -- Tisoware will refuse this{OFF}")
            success_count += 1
        else:
            try:
                if post_bookings_for_date(client, trans_name, d, grouped[d],
                                          dry_run=dry_run):
                    success_count += 1
                    saved_days.append(d)
            except (Aborted, KeyboardInterrupt):
                aborted_on = dates_to_post[position:]
                break

    if not dry_run:
        print(f"\n{'=' * HEADER_WIDTH}")
        if aborted_on:
            print("Interrupted.")
        if saved_days:
            print(f"Saved {len(saved_days)} day(s): "
                  + ", ".join(d.strftime("%d.%m") for d in saved_days))
        else:
            print("Nothing was saved.")

        remaining = aborted_on if aborted_on else [
            d for d in dates_to_post if d not in saved_days]
        if remaining:
            print(f"Not saved: "
                  + ", ".join(d.strftime("%d.%m") for d in remaining))
            print(f"Resume with: python3 {Path(sys.argv[0]).name}"
                  f" --from {remaining[0].strftime('%d.%m.%Y')}")
        return

    if dry_run:
        print(f"\n{'='*70}")
        print(f"Processed {success_count}/{len(dates_to_post)} date(s)")

        total_hours = 0
        for d in dates_to_post:
            for entry in grouped[d]:
                total_hours += (to_minutes(entry.to_time)
                                - to_minutes(entry.from_time)) / 60

        print(f"Total hours across all days: {total_hours:.1f}h")
        for label, days, keys in (
            ("Overlaps", overlap_days, "1/2/d/s"),
            ("Backwards entries", inverted_days, "1/d/s"),
            ("Over 10h", over_limit_days, "1/d/s"),
        ):
            if days:
                shown = ", ".join(d.strftime("%d.%m") for d in days)
                print(f"{RED}{label} on: {shown}"
                      f" -- these need {keys} on the real run{OFF}")


if __name__ == "__main__":
    import argparse
    def a_date(s):
        return datetime.strptime(s, "%d.%m.%Y").date()

    parser = argparse.ArgumentParser(
        description="Post Buchungskorrektur entries to Tisoware from a ttplus"
                    " tasks.json database or a markdown log"
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path.home() / "ttplus" / "ml-test" / "2026-July" / "2026-July.md",
        help="Path to a tasks.json database (.json) or a markdown log",
    )
    parser.add_argument(
        "--from",
        type=a_date,
        dest="start_date",
        default=None,
        help="Start date (dd.mm.yyyy), default: first entry",
    )
    parser.add_argument(
        "--to",
        type=a_date,
        dest="end_date",
        default=None,
        help="Last date (dd.mm.yyyy), default: last entry",
    )
    parser.add_argument(
        "--skip",
        type=lambda s: frozenset(a_date(p) for p in s.split(",") if p.strip()),
        default=frozenset(),
        help="Dates to leave out, comma separated (dd.mm.yyyy), e.g. sick leave",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview and exit without saving",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="One line per day (total, entries, what it needs) and exit",
    )
    parser.add_argument(
        "--url",
        default=PROD_URL,
        help=f"Tisoware URL (default: {PROD_URL})",
    )

    args = parser.parse_args()
    try:
        main(args.log, args.start_date, args.dry_run, args.url,
             args.end_date, args.skip, args.summary)
    except (Aborted, KeyboardInterrupt):
        # Anything the day loop did not already report (Ctrl-C at the login
        # prompt, or between days).
        print("\nAborted, nothing further was sent.")
        sys.exit(130)
